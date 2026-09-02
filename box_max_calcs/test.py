"""
Étape 1 du projet :
- détecter la grille HoYoLAB
- compter les personnages
- extraire chaque case
- sauvegarder les crops
- générer un fichier JSON

Version segmentation :
- on garde le comptage actuel
- on détecte ensuite les vraies lignes par recherche locale sur le contenu
- on construit les bornes des cases à partir des séparateurs réels
"""

from PIL import Image
import numpy as np
import sys
import json
import math
from pathlib import Path

REFERENCE_WIDTH = 1000
CYCLE_RATIO_GUESS = 0.241
N_ROWS_FOR_CALIBRATION = 6
SEARCH_WINDOW_RATIO = 0.025
GROUP_GAP_RATIO = 0.01
HEADER_OFFSET_RATIO = 0.015
FOOTER_GUARD_RATIO = 0.30
MAX_CONSECUTIVE_EMPTY_ROWS = 2
TAIL_SEARCH_MARGIN = 6
BANNER_TARGET = np.array([211, 189, 148])


def load_normalized_image(image_path: str):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    scale = REFERENCE_WIDTH / w
    new_h = int(h * scale)
    img = img.resize((REFERENCE_WIDTH, new_h), Image.Resampling.LANCZOS)
    rgb = np.array(img)
    gray = np.array(img.convert("L"))
    return img, rgb, gray


def row_energy(gray_arr: np.ndarray) -> np.ndarray:
    grad = np.abs(np.diff(gray_arr.astype(float), axis=0))
    return grad.sum(axis=1)


def build_separator_profile(gray_arr: np.ndarray, width: int) -> np.ndarray:
    x0 = int(width * 0.02)
    x1 = int(width * 0.98)

    grad = np.abs(np.diff(gray_arr[:, x0:x1].astype(float), axis=0)).mean(axis=1)

    kernel_size = 9
    kernel = np.ones(kernel_size, dtype=float) / kernel_size
    smooth = np.convolve(grad, kernel, mode="same")

    profile = np.zeros(gray_arr.shape[0], dtype=float)
    profile[:-1] = smooth
    profile[-1] = smooth[-1] if len(smooth) else 0.0
    return profile


def find_banner_bottom(rgb_arr: np.ndarray) -> int:
    h, w, _ = rgb_arr.shape
    search_limit = min(h, int(w * 0.6))
    center_col = rgb_arr[:search_limit, w // 2, :].astype(int)
    dist = np.sqrt(((center_col - BANNER_TARGET) ** 2).sum(axis=1))
    matches = np.where(dist < 30)[0]
    return int(matches[-1]) if len(matches) else 0


def find_header_start(energy: np.ndarray, width: int, min_search_start: int) -> int:
    cycle_guess = CYCLE_RATIO_GUESS * width
    search_window = max(6, int(width * SEARCH_WINDOW_RATIO))
    group_gap = max(3, int(width * GROUP_GAP_RATIO))

    search_start = max(int(width * 0.05), min_search_start)
    search_limit = min(len(energy), int(width * 1.0))

    band = energy[search_start:search_limit]
    threshold = np.percentile(band, 97)

    candidates = [y for y in range(search_start, search_limit) if energy[y] > threshold]

    grouped = []
    for y in candidates:
        if not grouped or y - grouped[-1] > group_gap:
            grouped.append(y)

    for start in grouped:
        pos = start
        cyc = cycle_guess
        ok = True

        for _ in range(4):
            expected = pos + cyc
            lo = max(0, int(expected - search_window))
            hi = min(len(energy), int(expected + search_window))
            if hi <= lo:
                ok = False
                break

            window = energy[lo:hi]
            local_max = lo + int(np.argmax(window))

            if energy[local_max] < 0.3 * energy[start]:
                ok = False
                break

            delta = local_max - pos
            cyc = 0.5 * cyc + 0.5 * delta
            pos = local_max

        if ok:
            return start

    raise ValueError("Impossible de localiser le début de la grille.")


def mean_saturation(crop: np.ndarray) -> float:
    if crop.size == 0:
        return 0.0

    r = crop[..., 0].astype(float)
    g = crop[..., 1].astype(float)
    b = crop[..., 2].astype(float)

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)

    sat = np.where(maxc > 0, (maxc - minc) / (maxc + 1e-6), 0.0)
    return float(sat.mean())


def local_energy(gray_arr: np.ndarray, row_top: int, row_height: int, x0: int, x1: int) -> float:
    h, _ = gray_arr.shape
    bottom = min(h, row_top + row_height)

    if row_top < 0 or bottom <= row_top or x1 <= x0:
        return 0.0

    crop = gray_arr[row_top:bottom, x0:x1].astype(float)
    if crop.size == 0:
        return 0.0

    gy = np.abs(np.diff(crop, axis=0)).mean() if crop.shape[0] > 1 else 0.0
    gx = np.abs(np.diff(crop, axis=1)).mean() if crop.shape[1] > 1 else 0.0
    return float(gx + gy)


def portrait_scores(
    rgb_arr: np.ndarray,
    gray_arr: np.ndarray,
    row_top: int,
    row_height: int,
    x0: int,
    x1: int,
):
    h = rgb_arr.shape[0]
    bottom = min(h, row_top + row_height)

    if row_top < 0 or bottom <= row_top or x1 <= x0:
        return 0.0, 0.0

    rgb_crop = rgb_arr[row_top:bottom, x0:x1]
    sat = mean_saturation(rgb_crop)
    eng = local_energy(gray_arr, row_top, row_height, x0, x1)
    return sat, eng


def calibrate_header_and_cycle(rgb: np.ndarray, gray: np.ndarray):
    height, width = gray.shape
    energy = row_energy(gray)

    banner_bottom = find_banner_bottom(rgb)
    header_offset = max(4, int(width * HEADER_OFFSET_RATIO))
    header_start = find_header_start(energy, width, banner_bottom + header_offset)

    cycle_est = CYCLE_RATIO_GUESS * width
    current = header_start
    reference_peak = energy[header_start]
    search_window = max(6, int(width * SEARCH_WINDOW_RATIO))

    for _ in range(N_ROWS_FOR_CALIBRATION - 1):
        expected = current + cycle_est
        lo = max(0, int(expected - search_window))
        hi = min(height - 1, int(expected + search_window))
        if hi <= lo:
            break

        window = energy[lo:hi]
        local_max = lo + int(np.argmax(window))

        if energy[local_max] < 0.2 * reference_peak:
            break

        delta = local_max - current
        cycle_est = 0.5 * cycle_est + 0.5 * delta
        current = local_max

    return width, height, energy, header_start, cycle_est


def count_characters_from_data(
    rgb: np.ndarray,
    gray: np.ndarray,
    width: int,
    height: int,
    header: int,
    cycle: float,
) -> int:
    row_height = int(round(cycle))
    footer_guard = int(width * FOOTER_GUARD_RATIO)
    max_valid_bottom = height - footer_guard

    left_x0 = int(width * 0.04)
    left_x1 = int(width * 0.22)
    right_x0 = int(width * 0.54)
    right_x1 = int(width * 0.72)

    usable = max(0, max_valid_bottom - header)
    n_rows_estimate = max(1, round(usable / cycle))

    row_data = {}

    for i in range(1, n_rows_estimate + TAIL_SEARCH_MARGIN + 1):
        row_top = int(round(header + (i - 1) * cycle))
        if row_top + row_height > max_valid_bottom:
            break

        left_sat, left_eng = portrait_scores(rgb, gray, row_top, row_height, left_x0, left_x1)
        right_sat, right_eng = portrait_scores(rgb, gray, row_top, row_height, right_x0, right_x1)

        row_data[i] = {
            "left_sat": left_sat,
            "left_eng": left_eng,
            "right_sat": right_sat,
            "right_eng": right_eng,
        }

    if not row_data:
        return 0

    early_sat = []
    early_eng = []

    for i in range(1, min(4, len(row_data)) + 1):
        if i in row_data:
            early_sat.extend([row_data[i]["left_sat"], row_data[i]["right_sat"]])
            early_eng.extend([row_data[i]["left_eng"], row_data[i]["right_eng"]])

    ref_sat = float(np.mean(early_sat)) if early_sat else 0.15
    ref_eng = float(np.mean(early_eng)) if early_eng else 8.0

    sat_threshold = 0.35 * ref_sat
    eng_threshold = 0.35 * ref_eng

    best_row = 0
    last_left_present = False
    last_right_present = False
    consecutive_empty = 0

    for i in sorted(row_data):
        d = row_data[i]

        left_present = (d["left_sat"] > sat_threshold) and (d["left_eng"] > eng_threshold)
        right_present = (d["right_sat"] > sat_threshold) and (d["right_eng"] > eng_threshold)

        if left_present or right_present:
            best_row = i
            last_left_present = left_present
            last_right_present = right_present
            consecutive_empty = 0
        else:
            consecutive_empty += 1
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY_ROWS:
                break

    if best_row == 0:
        return 0

    return (best_row - 1) * 2 + int(last_left_present) + int(last_right_present)


def row_candidate_score(
    rgb: np.ndarray,
    gray: np.ndarray,
    energy: np.ndarray,
    y: int,
    row_height: int,
    left_x0: int,
    left_x1: int,
    right_x0: int,
    right_x1: int,
    expected_y: float,
    search_margin: int,
    energy_ref: float,
) -> float:
    left_sat, left_eng = portrait_scores(rgb, gray, y, row_height, left_x0, left_x1)
    right_sat, right_eng = portrait_scores(rgb, gray, y, row_height, right_x0, right_x1)

    edge = float(energy[min(max(0, y), len(energy) - 1)])
    edge_ratio = edge / (energy_ref + 1e-6)
    distance_penalty = abs(y - expected_y) / max(1.0, float(search_margin))

    score = (
        left_sat + right_sat
        + 0.02 * (left_eng + right_eng)
        + 0.12 * edge_ratio
        - 0.08 * distance_penalty
    )
    return float(score)


def find_best_row_top_near(
    rgb: np.ndarray,
    gray: np.ndarray,
    energy: np.ndarray,
    expected_y: float,
    row_height: int,
    left_x0: int,
    left_x1: int,
    right_x0: int,
    right_x1: int,
    low: int,
    high: int,
    search_margin: int,
    energy_ref: float,
) -> int:
    h = gray.shape[0]
    low = max(0, low)
    high = min(h - row_height, high)

    if high <= low:
        return max(0, min(h - row_height, int(round(expected_y))))

    best_y = int(round(expected_y))
    best_score = -1e18

    for y in range(low, high + 1):
        score = row_candidate_score(
            rgb=rgb,
            gray=gray,
            energy=energy,
            y=y,
            row_height=row_height,
            left_x0=left_x0,
            left_x1=left_x1,
            right_x0=right_x0,
            right_x1=right_x1,
            expected_y=expected_y,
            search_margin=search_margin,
            energy_ref=energy_ref,
        )
        if score > best_score:
            best_score = score
            best_y = y

    return best_y


def track_row_tops(
    rgb: np.ndarray,
    gray: np.ndarray,
    energy: np.ndarray,
    header: int,
    cycle: float,
    n_rows: int,
    width: int,
    height: int,
):
    if n_rows <= 0:
        return []

    footer_guard = int(width * FOOTER_GUARD_RATIO)
    max_valid_bottom = height - footer_guard

    row_height_guess = max(1, int(round(cycle)))
    search_margin = max(10, int(width * 0.03))

    left_x0 = int(width * 0.04)
    left_x1 = int(width * 0.22)
    right_x0 = int(width * 0.54)
    right_x1 = int(width * 0.72)

    energy_ref = max(1.0, float(energy[min(max(0, header), len(energy) - 1)]))

    first_top = find_best_row_top_near(
        rgb=rgb,
        gray=gray,
        energy=energy,
        expected_y=header,
        row_height=row_height_guess,
        left_x0=left_x0,
        left_x1=left_x1,
        right_x0=right_x0,
        right_x1=right_x1,
        low=header - search_margin // 2,
        high=header + search_margin // 2,
        search_margin=search_margin,
        energy_ref=energy_ref,
    )

    row_tops = [first_top]
    current_cycle = cycle

    for _ in range(1, n_rows):
        prev_top = row_tops[-1]
        expected = prev_top + current_cycle

        low = max(prev_top + int(0.60 * current_cycle), int(expected - search_margin))
        high = min(max_valid_bottom - row_height_guess, int(expected + search_margin))

        best_top = find_best_row_top_near(
            rgb=rgb,
            gray=gray,
            energy=energy,
            expected_y=expected,
            row_height=row_height_guess,
            left_x0=left_x0,
            left_x1=left_x1,
            right_x0=right_x0,
            right_x1=right_x1,
            low=low,
            high=high,
            search_margin=search_margin,
            energy_ref=energy_ref,
        )

        delta = best_top - prev_top

        if delta <= 0:
            best_top = int(round(expected))
            delta = best_top - prev_top

        if delta < 0.60 * current_cycle or delta > 1.40 * current_cycle:
            best_top = int(round(expected))
            delta = best_top - prev_top

        row_tops.append(best_top)
        current_cycle = 0.7 * current_cycle + 0.3 * delta

    return row_tops


def find_local_min(profile: np.ndarray, center: int, radius: int, low: int, high: int) -> int:
    low = max(0, low)
    high = min(len(profile) - 1, high)

    if high <= low:
        return max(0, min(len(profile) - 1, center))

    lo = max(low, center - radius)
    hi = min(high, center + radius)

    if hi <= lo:
        return max(0, min(len(profile) - 1, center))

    window = profile[lo:hi + 1]
    return lo + int(np.argmin(window))


def build_row_boundaries(
    row_tops,
    cycle: float,
    separator_profile: np.ndarray,
    max_valid_bottom: int,
):
    if not row_tops:
        return []

    if len(row_tops) >= 2:
        typical_gap = float(np.median(np.diff(row_tops)))
    else:
        typical_gap = float(cycle)

    if typical_gap <= 0:
        typical_gap = float(cycle)

    search_radius = max(6, int(0.08 * typical_gap))

    boundaries = []
    first_boundary = max(0, int(round(row_tops[0] - 0.05 * typical_gap)))
    boundaries.append(first_boundary)

    for i in range(len(row_tops) - 1):
        rough = int(round((row_tops[i] + row_tops[i + 1]) / 2))
        low = boundaries[-1] + 1
        high = max_valid_bottom - 1

        boundary = find_local_min(
            profile=separator_profile,
            center=rough,
            radius=search_radius,
            low=low,
            high=high,
        )
        boundary = max(boundaries[-1] + 1, boundary)
        boundaries.append(boundary)

    rough_last = min(max_valid_bottom, int(round(row_tops[-1] + 0.95 * typical_gap)))
    last_boundary = find_local_min(
        profile=separator_profile,
        center=rough_last,
        radius=search_radius,
        low=boundaries[-1] + 1,
        high=max_valid_bottom,
    )
    last_boundary = max(boundaries[-1] + 1, last_boundary)
    boundaries.append(last_boundary)

    return boundaries


def build_cells(width: int, height: int, boundaries, count: int):
    n_rows = len(boundaries) - 1
    if n_rows <= 0:
        return []

    left_cell_x0 = int(width * 0.02)
    left_cell_x1 = int(width * 0.495)
    right_cell_x0 = int(width * 0.505)
    right_cell_x1 = int(width * 0.98)

    cells = []
    index = 1

    for row_idx in range(n_rows):
        y0 = max(0, min(height, boundaries[row_idx]))
        y1 = max(0, min(height, boundaries[row_idx + 1]))

        if y1 <= y0:
            continue

        cells.append({
            "index": index,
            "row": row_idx + 1,
            "column": "left",
            "bbox": [left_cell_x0, y0, left_cell_x1, y1],
        })
        index += 1

        is_last_row = (row_idx == n_rows - 1)
        odd_count = (count % 2 == 1)

        if not (is_last_row and odd_count):
            cells.append({
                "index": index,
                "row": row_idx + 1,
                "column": "right",
                "bbox": [right_cell_x0, y0, right_cell_x1, y1],
            })
            index += 1

    return cells


def analyze_image(image_path: str):
    img, rgb, gray = load_normalized_image(image_path)
    width, height, energy, header, cycle = calibrate_header_and_cycle(rgb, gray)

    count = count_characters_from_data(
        rgb=rgb,
        gray=gray,
        width=width,
        height=height,
        header=header,
        cycle=cycle,
    )

    if count <= 0:
        return img, width, height, [], 0

    n_rows = math.ceil(count / 2)

    row_tops = track_row_tops(
        rgb=rgb,
        gray=gray,
        energy=energy,
        header=header,
        cycle=cycle,
        n_rows=n_rows,
        width=width,
        height=height,
    )

    footer_guard = int(width * FOOTER_GUARD_RATIO)
    max_valid_bottom = height - footer_guard
    separator_profile = build_separator_profile(gray, width)

    boundaries = build_row_boundaries(
        row_tops=row_tops,
        cycle=cycle,
        separator_profile=separator_profile,
        max_valid_bottom=max_valid_bottom,
    )

    cells = build_cells(
        width=width,
        height=height,
        boundaries=boundaries,
        count=count,
    )

    return img, width, height, cells, count


def save_cells_and_json(image_path: str, output_root: str = "output"):
    img, width, height, cells, count = analyze_image(image_path)

    image_name = Path(image_path).stem
    out_dir = Path(output_root) / image_name
    cells_dir = out_dir / "cells"

    out_dir.mkdir(parents=True, exist_ok=True)
    cells_dir.mkdir(parents=True, exist_ok=True)

    json_cells = []

    for cell in cells:
        x0, y0, x1, y1 = cell["bbox"]
        crop = img.crop((x0, y0, x1, y1))

        filename = f"cell_{cell['index']:03d}.png"
        rel_path = f"cells/{filename}"
        crop.save(cells_dir / filename)

        json_cells.append({
            "index": cell["index"],
            "row": cell["row"],
            "column": cell["column"],
            "bbox": cell["bbox"],
            "image": rel_path,
        })

    data = {
        "source_image": str(image_path),
        "count": count,
        "image_size": {
            "width": width,
            "height": height,
        },
        "cells": json_cells,
    }

    json_path = out_dir / "roster.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data, json_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python test.py <chemin_vers_image>")
        sys.exit(1)

    image_path = sys.argv[1]

    try:
        data, json_path = save_cells_and_json(image_path)
        print(f"Nombre de personnages détectés : {data['count']}")
        print(f"JSON généré : {json_path}")
    except Exception as e:
        print(f"Erreur : {e}")
        sys.exit(1)
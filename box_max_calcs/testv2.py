from PIL import Image, ImageDraw
import numpy as np
import argparse
import json
import sys
from pathlib import Path

# ============================================================
# CONFIG GLOBALE
# ============================================================

REFERENCE_WIDTH = 1000

# Détection header (repris de la logique actuelle)

CYCLE_RATIO_GUESS = 0.241
SEARCH_WINDOW_RATIO = 0.025
GROUP_GAP_RATIO = 0.01
HEADER_OFFSET_RATIO = 0.015
BANNER_TARGET = np.array([211, 189, 148])

# Zones finales de crop des deux colonnes (fait)

LEFT_CELL_X = (0.04, 0.4825)
RIGHT_CELL_X = (0.515, 0.955)

# Zones de scan vertical pour détecter les clusters sombres
# À CALIBRER selon la position réelle de la bordure/boîte de nom

LEFT_SCAN_X = (0.27, 0.275)
RIGHT_SCAN_X = (0.74, 0.745)

# Fenêtre verticale de recherche du cluster sombre
# relative au top de la ligne
# À CALIBRER selon la position réelle de la boîte de nom

ANCHOR_SEARCH_Y0 = 0
ANCHOR_SEARCH_Y1 = 200

# Masque "sombre"

DARK_LUMA_THRESHOLD = 28
DARK_MAX_CHANNEL = 28

# Détection de runs sur le profil vertical

PROFILE_SMOOTH_KERNEL = 5
PROFILE_THRESHOLD_MIN = 0.16

RUN_MIN_LENGTH = 5
RUN_MAX_LENGTH = 150
RUN_MERGE_GAP = 2

# Ajustement local du top de ligne via énergie verticale

TOP_REFINE_RADIUS = 0

# Modèle hauteur de carte à partir de la longueur du cluster
# height = BASE_CARD_HEIGHT + RUN_TO_HEIGHT_SCALE * (run_length - BASE_RUN_LENGTH)
# À CALIBRER

BASE_RUN_LENGTH = 100
BASE_CARD_HEIGHT = 200
RUN_TO_HEIGHT_SCALE = 1.0
MIN_CARD_HEIGHT = 214
MAX_CARD_HEIGHT = 270

# Espace entre deux lignes après la carte la plus basse
# À CALIBRER

INTER_ROW_GAP = 30

# Garde bas image

FOOTER_GUARD_RATIO = 0.30

# Contrôle

MAX_ROWS = 80
MAX_CONSECUTIVE_MISSES = 2

# ============================================================
# OUTILS DE BASE
# ============================================================

def load_normalized_image(image_path: str):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    scale = REFERENCE_WIDTH / w
    new_h = int(round(h * scale))
    img = img.resize((REFERENCE_WIDTH, new_h), Image.Resampling.LANCZOS)
    rgb = np.array(img)
    gray = np.array(img.convert("L"))
    return img, rgb, gray


def row_energy(gray_arr: np.ndarray) -> np.ndarray:
    grad = np.abs(np.diff(gray_arr.astype(float), axis=0))
    return grad.sum(axis=1)


def smooth1d(arr: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return arr.copy()
    kernel = np.ones(k, dtype=float) / k
    return np.convolve(arr, kernel, mode="same")

 
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ============================================================
# HEADER
# ============================================================


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
    if len(band) == 0:
        raise ValueError("Bande de recherche vide pour le header.")

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

 
def detect_first_row_top(rgb: np.ndarray, gray: np.ndarray):
    height, width = gray.shape
    energy = row_energy(gray)
    banner_bottom = find_banner_bottom(rgb)
    header_offset = max(4, int(width * HEADER_OFFSET_RATIO))
    first_top = find_header_start(energy, width, banner_bottom + header_offset)
    return first_top, energy

# ============================================================
# MASQUE SOMBRE / PROFILS / RUNS
# ============================================================

def make_dark_mask(rgb_arr: np.ndarray) -> np.ndarray:
    r = rgb_arr[..., 0].astype(float)
    g = rgb_arr[..., 1].astype(float)
    b = rgb_arr[..., 2].astype(float)

    luma = 0.299 * r + 0.587 * g + 0.114 * b
    maxc = np.maximum(np.maximum(r, g), b)

    # "sombre" tolérant

    mask = (luma < DARK_LUMA_THRESHOLD) & (maxc < DARK_MAX_CHANNEL)
    return mask


def band_dark_profile(dark_mask: np.ndarray, x0: int, x1: int) -> np.ndarray:
    h, w = dark_mask.shape
    x0 = clamp(x0, 0, w - 1)
    x1 = clamp(x1, x0 + 1, w)
    band = dark_mask[:, x0:x1]
    profile = band.mean(axis=1).astype(float)
    profile = smooth1d(profile, PROFILE_SMOOTH_KERNEL)
    return profile


def compute_profile_threshold(profile: np.ndarray, start_y: int, end_y: int) -> float:
    start_y = clamp(start_y, 0, len(profile) - 1)
    end_y = clamp(end_y, start_y + 1, len(profile))
    band = profile[start_y:end_y]
    if len(band) == 0:
        return PROFILE_THRESHOLD_MIN

    p95 = float(np.percentile(band, 95))
    thr = max(PROFILE_THRESHOLD_MIN, 0.45 * p95)
    return thr


def extract_runs(profile: np.ndarray, threshold: float,
                 min_len: int = RUN_MIN_LENGTH,
                 max_len: int = RUN_MAX_LENGTH,
                 merge_gap: int = RUN_MERGE_GAP):
    active = profile >= threshold
    raw = []
 
    in_run = False
    start = 0
    for i, val in enumerate(active):
        if val and not in_run:
            start = i
            in_run = True
        elif not val and in_run:
            raw.append([start, i - 1])
            in_run = False
 
    if in_run:
        raw.append([start, len(active) - 1])
 
    # merge petits gaps
    merged = []
    for s, e in raw:
        if not merged:
            merged.append([s, e])
        else:
            prev_s, prev_e = merged[-1]
            if s - prev_e - 1 <= merge_gap:
                merged[-1][1] = e
            else:
                merged.append([s, e])
 
    runs = []
    for s, e in merged:
        length = e - s + 1
        if length < min_len:
            continue
        if max_len is not None and length > max_len:
            continue
 
        segment = profile[s:e + 1]
        runs.append({
            "start": int(s),
            "end": int(e),
            "length": int(length),
            "mean_profile": float(segment.mean()),
            "peak_profile": float(segment.max()),
        })
 
    return runs
 
 
def offset_runs(runs, offset: int):
    out = []
    for r in runs:
        rr = dict(r)
        rr["start"] += offset
        rr["end"] += offset
        out.append(rr)
    return out
 
 
def estimate_split_threshold(lengths):
    vals = sorted(int(v) for v in lengths if v is not None)
    if len(vals) < 2:
        return BASE_RUN_LENGTH + 3
 
    diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    best_idx = int(np.argmax(diffs))
    if diffs[best_idx] >= 2:
        return 0.5 * (vals[best_idx] + vals[best_idx + 1])
 
    return float(np.median(vals))
 
 
def predict_card_height(run_length: int) -> int:
    if run_length is None:
        return BASE_CARD_HEIGHT
 
    height = BASE_CARD_HEIGHT + RUN_TO_HEIGHT_SCALE * (run_length - BASE_RUN_LENGTH)
    height = int(round(height))
    height = clamp(height, MIN_CARD_HEIGHT, MAX_CARD_HEIGHT)
    return height
 
 
# ============================================================
# RECHERCHE DU CLUSTER PAR LIGNE
# ============================================================
 
def refine_top_from_energy(energy: np.ndarray, expected_y: int, radius: int = TOP_REFINE_RADIUS) -> int:
    lo = clamp(int(expected_y - radius), 0, len(energy) - 1)
    hi = clamp(int(expected_y + radius), lo + 1, len(energy))
    window = energy[lo:hi]
    return int(lo + np.argmax(window))
 
 
def find_best_run_near_top(profile: np.ndarray, top_y: int, threshold: float):
    lo = int(top_y + ANCHOR_SEARCH_Y0)
    hi = int(top_y + ANCHOR_SEARCH_Y1)
 
    lo = clamp(lo, 0, len(profile) - 1)
    hi = clamp(hi, lo + 1, len(profile))
 
    window = profile[lo:hi]
    runs = extract_runs(window, threshold)
 
    if not runs:
        return None
 
    # On préfère un run long + dense, légèrement favorisé s'il est proche du centre de la fenêtre
    center_ref = lo + 0.65 * (hi - lo)
 
    best = None
    best_score = -1e18
 
    for r in runs:
        abs_start = lo + r["start"]
        abs_end = lo + r["end"]
        abs_center = 0.5 * (abs_start + abs_end)
 
        score = (
            2.0 * r["length"]
            + 80.0 * r["mean_profile"]
            + 20.0 * r["peak_profile"]
            - 0.03 * abs(abs_center - center_ref)
        )
 
        if score > best_score:
            best_score = score
            best = {
                "start": int(abs_start),
                "end": int(abs_end),
                "length": int(r["length"]),
                "mean_profile": float(r["mean_profile"]),
                "peak_profile": float(r["peak_profile"]),
                "score": float(score),
                "window": [int(lo), int(hi)],
            }
 
    return best
 
 
# ============================================================
# SEGMENTATION
# ============================================================
 
def segment_image(image_path: str, output_root: str = "output_test"):
    img, rgb, gray = load_normalized_image(image_path)
    height, width = gray.shape
 
    first_top, energy = detect_first_row_top(rgb, gray)
 
    footer_guard = int(width * FOOTER_GUARD_RATIO)
    max_valid_bottom = height - footer_guard
 
    # x fixes
    left_cell_x0 = int(width * LEFT_CELL_X[0])
    left_cell_x1 = int(width * LEFT_CELL_X[1])
    right_cell_x0 = int(width * RIGHT_CELL_X[0])
    right_cell_x1 = int(width * RIGHT_CELL_X[1])
 
    left_scan_x0 = int(width * LEFT_SCAN_X[0])
    left_scan_x1 = int(width * LEFT_SCAN_X[1])
    right_scan_x0 = int(width * RIGHT_SCAN_X[0])
    right_scan_x1 = int(width * RIGHT_SCAN_X[1])
 
    dark = make_dark_mask(rgb)
 
    left_profile = band_dark_profile(dark, left_scan_x0, left_scan_x1)
    right_profile = band_dark_profile(dark, right_scan_x0, right_scan_x1)
 
    left_threshold = compute_profile_threshold(left_profile, first_top, max_valid_bottom)
    right_threshold = compute_profile_threshold(right_profile, first_top, max_valid_bottom)
 
    # Runs globaux sur toute la zone utile
    left_global_runs = extract_runs(left_profile[first_top:max_valid_bottom], left_threshold)
    right_global_runs = extract_runs(right_profile[first_top:max_valid_bottom], right_threshold)
 
    left_global_runs = offset_runs(left_global_runs, first_top)
    right_global_runs = offset_runs(right_global_runs, first_top)
 
    # Boucle lignes
    rows = []
    left_lengths = []
    right_lengths = []
 
    expected_top = first_top
    misses = 0
 
    for row_idx in range(1, MAX_ROWS + 1):
        if expected_top >= max_valid_bottom - MIN_CARD_HEIGHT:
            break
 
        top = refine_top_from_energy(energy, int(round(expected_top)), TOP_REFINE_RADIUS)
        left_run = find_best_run_near_top(left_profile, top, left_threshold)
        right_run = find_best_run_near_top(right_profile, top, right_threshold)


        left_valid = left_run is not None
        right_valid = right_run is not None
 
        if not left_valid and not right_valid:
            misses += 1
            if misses >= MAX_CONSECUTIVE_MISSES:
                break
            expected_top = expected_top + BASE_CARD_HEIGHT + INTER_ROW_GAP
            continue
 
        misses = 0
 
        left_length = left_run["length"] if left_valid else None
        right_length = right_run["length"] if right_valid else None
 
        left_lengths.append(left_length)
        right_lengths.append(right_length)
 
        left_height = predict_card_height(left_length)
        right_height = predict_card_height(right_length)
 
        left_bottom = clamp(top + left_height, top + 1, max_valid_bottom)
        right_bottom = clamp(top + right_height, top + 1, max_valid_bottom)
 
        row = {
            "row": row_idx,
            "top": int(top),
            "left": {
                "detected": bool(left_valid),
                "run": left_run,
                "run_length": left_length,
                "predicted_height": int(left_height),
                "bbox": [left_cell_x0, int(top), left_cell_x1, int(left_bottom)],
            },
            "right": {
                "detected": bool(right_valid),
                "run": right_run,
                "run_length": right_length,
                "predicted_height": int(right_height),
                "bbox": [right_cell_x0, int(top), right_cell_x1, int(right_bottom)],
            },
        }
 
        rows.append(row)
 
        next_top = max(left_bottom, right_bottom) + INTER_ROW_GAP
        if next_top <= top:
            break
        expected_top = next_top
 
    # seuil de split pour étiqueter normal/anomalie
    all_lengths = [v for v in left_lengths + right_lengths if v is not None]
    split_threshold = estimate_split_threshold(all_lengths) if all_lengths else (BASE_RUN_LENGTH + 3)
 
    for row in rows:
        for side in ("left", "right"):
            rl = row[side]["run_length"]
            if rl is None:
                label = "missing"
            else:
                label = "anomaly" if rl > split_threshold else "normal"
            row[side]["label"] = label
 
    return {
        "img": img,
        "rgb": rgb,
        "gray": gray,
        "width": width,
        "height": height,
        "first_top": int(first_top),
        "max_valid_bottom": int(max_valid_bottom),
        "left_profile": left_profile,
        "right_profile": right_profile,
        "left_threshold": float(left_threshold),
        "right_threshold": float(right_threshold),
        "left_global_runs": left_global_runs,
        "right_global_runs": right_global_runs,
        "left_lengths": left_lengths,
        "right_lengths": right_lengths,
        "rows": rows,
        "split_threshold": float(split_threshold),
        "scan_bands": {
            "left": [left_scan_x0, left_scan_x1],
            "right": [right_scan_x0, right_scan_x1],
        },
    }
 
 
# ============================================================
# SAUVEGARDE
# ============================================================
 
def save_results(image_path: str, output_root: str = "output_test"):
    result = segment_image(image_path, output_root)
 
    img = result["img"]
    width = result["width"]
    height = result["height"]
    rows = result["rows"]
 
    image_name = Path(image_path).stem
    out_dir = Path(output_root) / image_name
    crops_dir = out_dir / "crops"
 
    out_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)
 
    # Sauvegarde des crops
    crops_json = []
 
    for row in rows:
        row_idx = row["row"]
 
        for side in ("left", "right"):
            bbox = row[side]["bbox"]
            x0, y0, x1, y1 = bbox
 
            crop = img.crop((x0, y0, x1, y1))
            filename = f"row_{row_idx:02d}_{side}.png"
            crop.save(crops_dir / filename)
 
            crops_json.append({
                "row": row_idx,
                "column": side,
                "bbox": bbox,
                "file": f"crops/{filename}",
                "run_length": row[side]["run_length"],
                "label": row[side]["label"],
                "predicted_height": row[side]["predicted_height"],
                "detected": row[side]["detected"],
            })
 
    # Image debug overlay
    debug_img = img.copy()
    draw = ImageDraw.Draw(debug_img)
 
    # bandes de scan
    lx0, lx1 = result["scan_bands"]["left"]
    rx0, rx1 = result["scan_bands"]["right"]
    draw.rectangle([lx0, result["first_top"], lx1, result["max_valid_bottom"]], outline=(0, 255, 255), width=2)
    draw.rectangle([rx0, result["first_top"], rx1, result["max_valid_bottom"]], outline=(0, 255, 255), width=2)
 
    # lignes / runs / bboxes
    for row in rows:
        top = row["top"]
        draw.line([(0, top), (width - 1, top)], fill=(255, 255, 0), width=2)
 
        for side, color in (("left", (0, 255, 0)), ("right", (255, 0, 0))):
            bbox = row[side]["bbox"]
            draw.rectangle(bbox, outline=color, width=3)
 
            run = row[side]["run"]
            if run is not None:
                xmid = (lx0 + lx1) // 2 if side == "left" else (rx0 + rx1) // 2
                draw.line([(xmid, run["start"]), (xmid, run["end"])], fill=(255, 0, 255), width=3)
 
    debug_img.save(out_dir / "debug_overlay.png")
 
    # Lists simples demandées
    left_lengths_simple = [int(v) if v is not None else None for v in result["left_lengths"]]
    right_lengths_simple = [int(v) if v is not None else None for v in result["right_lengths"]]
 
    with open(out_dir / "left_cluster_lengths.txt", "w", encoding="utf-8") as f:
        f.write(json.dumps(left_lengths_simple, ensure_ascii=False, indent=2))
 
    with open(out_dir / "right_cluster_lengths.txt", "w", encoding="utf-8") as f:
        f.write(json.dumps(right_lengths_simple, ensure_ascii=False, indent=2))
 
    # JSON complet
    data = {
        "source_image": str(image_path),
        "image_size": {
            "width": width,
            "height": height,
        },
        "first_row_top": result["first_top"],
        "max_valid_bottom": result["max_valid_bottom"],
        "thresholds": {
            "left_profile_threshold": result["left_threshold"],
            "right_profile_threshold": result["right_threshold"],
            "split_threshold": result["split_threshold"],
        },
        "scan_bands": result["scan_bands"],
        "cluster_lengths": {
            "left": left_lengths_simple,
            "right": right_lengths_simple,
        },
        "global_runs": {
            "left": result["left_global_runs"],
            "right": result["right_global_runs"],
        },
        "rows": rows,
        "crops": crops_json,
        "config": {
            "REFERENCE_WIDTH": REFERENCE_WIDTH,
            "LEFT_CELL_X": LEFT_CELL_X,
            "RIGHT_CELL_X": RIGHT_CELL_X,
            "LEFT_SCAN_X": LEFT_SCAN_X,
            "RIGHT_SCAN_X": RIGHT_SCAN_X,
            "ANCHOR_SEARCH_Y0": ANCHOR_SEARCH_Y0,
            "ANCHOR_SEARCH_Y1": ANCHOR_SEARCH_Y1,
            "DARK_LUMA_THRESHOLD": DARK_LUMA_THRESHOLD,
            "DARK_MAX_CHANNEL": DARK_MAX_CHANNEL,
            "BASE_RUN_LENGTH": BASE_RUN_LENGTH,
            "BASE_CARD_HEIGHT": BASE_CARD_HEIGHT,
            "RUN_TO_HEIGHT_SCALE": RUN_TO_HEIGHT_SCALE,
            "MIN_CARD_HEIGHT": MIN_CARD_HEIGHT,
            "MAX_CARD_HEIGHT": MAX_CARD_HEIGHT,
            "INTER_ROW_GAP": INTER_ROW_GAP,
        }
    }
 
    with open(out_dir / "segmentation_debug.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
 
    return out_dir, data
 
 
# ============================================================
# MAIN
# ============================================================
 
def main():
    parser = argparse.ArgumentParser(description="Test de segmentation HoYoLAB par clusters sombres verticaux.")
    parser.add_argument("image_path", help="Chemin de l'image à traiter")
    parser.add_argument("--output", default="output_test", help="Dossier racine de sortie")
    args = parser.parse_args()
 
    try:
        out_dir, data = save_results(args.image_path, args.output)
        print(f"Sortie : {out_dir}")
        print(f"Lignes détectées : {len(data['rows'])}")
        print(f"Cluster lengths left  : {data['cluster_lengths']['left']}")
        print(f"Cluster lengths right : {data['cluster_lengths']['right']}")
    except Exception as e:
        print(f"Erreur : {e}")
        sys.exit(1)
 
 
if __name__ == "__main__":
    main()
from PIL import Image, ImageDraw

import numpy as np

import argparse

import json

import sys

from pathlib import Path

 

# python3 testv3.py box_100.jpg --output output_test

# ============================================================

# CONFIG GLOBALE 

# ============================================================

 

REFERENCE_WIDTH = 1000

 

# Header / footer : 30% de la largeur de l'image redimensionnée

HEADER_RATIO = 0.26

FOOTER_RATIO = 0.30

 

# Couleur cible EXACTE de l'encadrement gris

TARGET_GRAY_RGB = np.array([31, 31, 31], dtype=np.uint8)   # #1f1f1f

 

# Tolérance couleur

# 0 = match exact uniquement

COLOR_TOLERANCE = 10.9

 

# Zones finales de crop des deux colonnes

LEFT_CELL_X = (0.04, 0.4825)

RIGHT_CELL_X = (0.515, 0.955)

 

# Colonnes vecteurs de pixels : largeur = 1 pixel

# Tu règles ici la position X de la colonne de scan

LEFT_VECTOR_X_RATIO = 0.257

RIGHT_VECTOR_X_RATIO = 0.73

 

# Longueur minimale d'un run pour être gardé

# Laisse à 1 si tu veux du brut sans filtrage

MIN_RUN_LENGTH = 100

 

 

# ============================================================

# UTILITAIRES

# ============================================================

 

def clamp(v, lo, hi):

    return max(lo, min(hi, v))

 

 

def load_normalized_image(image_path: str):

    img = Image.open(image_path).convert("RGB")

    w, h = img.size

 

    scale = REFERENCE_WIDTH / w

    new_h = int(round(h * scale))

 

    img = img.resize((REFERENCE_WIDTH, new_h), Image.Resampling.LANCZOS)

    rgb = np.array(img)

    return img, rgb

 

 

def compute_layout_bounds(width: int, height: int):

    header_y = int(round(width * HEADER_RATIO))

    footer_guard = int(round(width * FOOTER_RATIO))

    scan_bottom = height - footer_guard

 

    if scan_bottom <= header_y:

        raise ValueError(

            f"Zone de scan invalide : header_y={header_y}, scan_bottom={scan_bottom}"

        )

 

    return header_y, scan_bottom, footer_guard

 

 

def color_match_mask(column_rgb: np.ndarray) -> np.ndarray:

    """

    column_rgb: shape (N, 3)

    Retourne un masque booléen des pixels qui matchent exactement la couleur cible,

    ou avec tolérance si COLOR_TOLERANCE > 0.

    """

    diff = np.abs(column_rgb.astype(int) - TARGET_GRAY_RGB.astype(int))

    return np.all(diff <= COLOR_TOLERANCE, axis=1)

 

 

def extract_runs_from_mask(mask: np.ndarray, y_offset: int, min_run_length: int = 1):

    """

    Convertit un masque booléen 1D en liste de runs continus.

    """

    runs = []

    in_run = False

    start = 0

 

    for i, matched in enumerate(mask):

        if matched and not in_run:

            start = i

            in_run = True

        elif not matched and in_run:

            end = i - 1

            length = end - start + 1

            if length >= min_run_length:

                runs.append({

                    "start": int(y_offset + start),

                    "end": int(y_offset + end),

                    "length": int(length),

                })

            in_run = False

 

    if in_run:

        end = len(mask) - 1

        length = end - start + 1

        if length >= min_run_length:

            runs.append({

                "start": int(y_offset + start),

                "end": int(y_offset + end),

                "length": int(length),

            })

 

    return runs

 

 

def scan_single_pixel_column(rgb_arr: np.ndarray, x: int, y0: int, y1: int):

    """

    Scanne UNE colonne de largeur 1 pixel entre y0 et y1.

    """

    h, w, _ = rgb_arr.shape

    x = clamp(x, 0, w - 1)

    y0 = clamp(y0, 0, h - 1)

    y1 = clamp(y1, y0 + 1, h)

 

    column = rgb_arr[y0:y1, x, :]   # shape (N, 3)

    mask = color_match_mask(column)

    runs = extract_runs_from_mask(mask, y_offset=y0, min_run_length=MIN_RUN_LENGTH)

 

    return runs, mask

 

 

def ratios_to_pixels(width: int):

    left_x0 = int(round(width * LEFT_CELL_X[0]))

    left_x1 = int(round(width * LEFT_CELL_X[1]))

    right_x0 = int(round(width * RIGHT_CELL_X[0]))

    right_x1 = int(round(width * RIGHT_CELL_X[1]))

 

    left_probe_x = int(round(width * LEFT_VECTOR_X_RATIO))

    right_probe_x = int(round(width * RIGHT_VECTOR_X_RATIO))

 

    return {

        "left_cell": [left_x0, left_x1],

        "right_cell": [right_x0, right_x1],

        "left_probe_x": left_probe_x,

        "right_probe_x": right_probe_x,

    }

 

 

# ============================================================

# SEGMENTATION

# ============================================================

 

def build_cells_from_runs(runs, x0: int, x1: int, side: str):

    """

    Chaque run vertical correspond à une box.

    """

    cells = []

 

    for idx, run in enumerate(runs, start=1):

        y0 = run["start"]

        y1 = run["end"] + 1  # PIL crop: borne basse exclusive

 

        cells.append({

            "index": idx,

            "column": side,

            "run_start": run["start"],

            "run_end": run["end"],

            "run_length": run["length"],

            "bbox": [x0, y0, x1, y1],

        })

 

    return cells

 

 

def analyze_image(image_path: str):

    img, rgb = load_normalized_image(image_path)

    height, width, _ = rgb.shape

 

    header_y, scan_bottom, footer_guard = compute_layout_bounds(width, height)

    px = ratios_to_pixels(width)

 

    left_runs, left_mask = scan_single_pixel_column(

        rgb_arr=rgb,

        x=px["left_probe_x"],

        y0=header_y,

        y1=scan_bottom,

    )

 

    right_runs, right_mask = scan_single_pixel_column(

        rgb_arr=rgb,

        x=px["right_probe_x"],

        y0=header_y,

        y1=scan_bottom,

    )

 

    left_cells = build_cells_from_runs(

        runs=left_runs,

        x0=px["left_cell"][0],

        x1=px["left_cell"][1],

        side="left",

    )

 

    right_cells = build_cells_from_runs(

        runs=right_runs,

        x0=px["right_cell"][0],

        x1=px["right_cell"][1],

        side="right",

    )

 

    return {

        "img": img,

        "rgb": rgb,

        "width": width,

        "height": height,

        "header_y": header_y,

        "scan_bottom": scan_bottom,

        "footer_guard": footer_guard,

        "left_probe_x": px["left_probe_x"],

        "right_probe_x": px["right_probe_x"],

        "left_cell_x": px["left_cell"],

        "right_cell_x": px["right_cell"],

        "left_runs": left_runs,

        "right_runs": right_runs,

        "left_cells": left_cells,

        "right_cells": right_cells,

        "left_mask_length": int(len(left_mask)),

        "right_mask_length": int(len(right_mask)),

    }

 

 

# ============================================================

# SAUVEGARDE

# ============================================================

 

def save_crops(img: Image.Image, cells, out_dir: Path):

    out_dir.mkdir(parents=True, exist_ok=True)

    saved = []

 

    for cell in cells:

        x0, y0, x1, y1 = cell["bbox"]

        crop = img.crop((x0, y0, x1, y1))

 

        filename = f"{cell['column']}_box_{cell['index']:03d}.png"

        crop.save(out_dir / filename)

 

        item = dict(cell)

        item["file"] = filename

        saved.append(item)

 

    return saved

 

 

def build_debug_overlay(img: Image.Image, analysis: dict) -> Image.Image:

    debug = img.copy()

    draw = ImageDraw.Draw(debug)

 

    w = analysis["width"]

    h = analysis["height"]

 

    header_y = analysis["header_y"]

    scan_bottom = analysis["scan_bottom"]

 

    left_probe_x = analysis["left_probe_x"]

    right_probe_x = analysis["right_probe_x"]

 

    left_x0, left_x1 = analysis["left_cell_x"]

    right_x0, right_x1 = analysis["right_cell_x"]

 

    # Header / bas de scan

    draw.line([(0, header_y), (w - 1, header_y)], fill=(255, 255, 0), width=2)

    draw.line([(0, scan_bottom), (w - 1, scan_bottom)], fill=(255, 128, 0), width=2)

 

    # Colonnes de scan

    draw.line([(left_probe_x, header_y), (left_probe_x, scan_bottom)], fill=(0, 255, 255), width=2)

    draw.line([(right_probe_x, header_y), (right_probe_x, scan_bottom)], fill=(0, 255, 255), width=2)

 

    # Runs gauche

    for run in analysis["left_runs"]:

        y0 = run["start"]

        y1 = run["end"]

        draw.line([(left_probe_x, y0), (left_probe_x, y1)], fill=(255, 0, 255), width=3)

        draw.rectangle([left_x0, y0, left_x1, y1 + 1], outline=(0, 255, 0), width=3)

 

    # Runs droite

    for run in analysis["right_runs"]:

        y0 = run["start"]

        y1 = run["end"]

        draw.line([(right_probe_x, y0), (right_probe_x, y1)], fill=(255, 0, 255), width=3)

        draw.rectangle([right_x0, y0, right_x1, y1 + 1], outline=(255, 0, 0), width=3)

 

    return debug

 

 

def save_results(image_path: str, output_root: str = "output_gray_runs"):

    analysis = analyze_image(image_path)

    img = analysis["img"]

 

    image_name = Path(image_path).stem

    out_dir = Path(output_root) / image_name

    left_dir = out_dir / "left"

    right_dir = out_dir / "right"

 

    out_dir.mkdir(parents=True, exist_ok=True)

 

    left_saved = save_crops(img, analysis["left_cells"], left_dir)

    right_saved = save_crops(img, analysis["right_cells"], right_dir)

 

    debug_img = build_debug_overlay(img, analysis)

    debug_img.save(out_dir / "debug_overlay.png")

 

    # Fichiers texte simples

    with open(out_dir / "left_runs.json", "w", encoding="utf-8") as f:

        json.dump(analysis["left_runs"], f, ensure_ascii=False, indent=2)

 

    with open(out_dir / "right_runs.json", "w", encoding="utf-8") as f:

        json.dump(analysis["right_runs"], f, ensure_ascii=False, indent=2)

 

    data = {

        "source_image": str(image_path),

        "image_size": {

            "width": analysis["width"],

            "height": analysis["height"],

        },

        "config": {

            "REFERENCE_WIDTH": REFERENCE_WIDTH,

            "HEADER_RATIO": HEADER_RATIO,

            "FOOTER_RATIO": FOOTER_RATIO,

            "TARGET_GRAY_RGB": TARGET_GRAY_RGB.tolist(),

            "COLOR_TOLERANCE": COLOR_TOLERANCE,

            "LEFT_CELL_X": LEFT_CELL_X,

            "RIGHT_CELL_X": RIGHT_CELL_X,

            "LEFT_VECTOR_X_RATIO": LEFT_VECTOR_X_RATIO,

            "RIGHT_VECTOR_X_RATIO": RIGHT_VECTOR_X_RATIO,

            "MIN_RUN_LENGTH": MIN_RUN_LENGTH,

        },

        "computed": {

            "header_y": analysis["header_y"],

            "scan_bottom": analysis["scan_bottom"],

            "footer_guard": analysis["footer_guard"],

            "left_probe_x": analysis["left_probe_x"],

            "right_probe_x": analysis["right_probe_x"],

            "left_cell_x": analysis["left_cell_x"],

            "right_cell_x": analysis["right_cell_x"],

        },

        "left_runs": analysis["left_runs"],

        "right_runs": analysis["right_runs"],

        "left_count": len(analysis["left_runs"]),

        "right_count": len(analysis["right_runs"]),

        "left_crops": left_saved,

        "right_crops": right_saved,

    }

 

    with open(out_dir / "segmentation.json", "w", encoding="utf-8") as f:

        json.dump(data, f, ensure_ascii=False, indent=2)

 

    return out_dir, data

 

 

# ============================================================

# MAIN

# ============================================================

 

def main():

    parser = argparse.ArgumentParser(

        description="Segmentation déterministe par runs verticaux exacts de gris #1f1f1f"

    )

    parser.add_argument("image_path", help="Chemin vers l'image à traiter")

    parser.add_argument("--output", default="output_gray_runs", help="Dossier de sortie")

    args = parser.parse_args()

 

    try:

        out_dir, data = save_results(args.image_path, args.output)

        print(f"Sortie : {out_dir}")

        print(f"Gauche : {data['left_count']} runs détectés")

        print(f"Droite : {data['right_count']} runs détectés")

        print(f"left_runs  : {data['left_runs']}")

        print(f"right_runs : {data['right_runs']}")

    except Exception as e:

        print(f"Erreur : {e}")

        sys.exit(1)

 

 

if __name__ == "__main__":

    main()
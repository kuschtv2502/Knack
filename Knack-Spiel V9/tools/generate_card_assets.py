"""Schneidet die 32 Knack-Karten sauber aus der gelieferten Vorlage.

Benötigt nur zur Neuerzeugung der Assets Pillow::

    py -3 -m pip install Pillow
    py -3 tools/generate_card_assets.py PFAD_ZUR_VORLAGE.jpg

Das Spiel selbst lädt ausschließlich die fertigen PNG-Dateien und braucht
keine externen Python-Pakete.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


EXPECTED_SOURCE_SIZE = (5517, 4463)
FACE_SIZE = (381, 533)
LARGE_SIZE = (96, 134)
SMALL_SIZE = (40, 56)

SUIT_GRID = {
    "herz": {
        "x": (152, 669, 1187, 1704, 2221),
        "y": (554, 1186, 1813),
    },
    "karo": {
        "x": (2892, 3409, 3926, 4443, 4960),
        "y": (584, 1199, 1813),
    },
    "kreuz": {
        "x": (152, 669, 1187, 1704, 2221),
        "y": (2568, 3173, 3789),
    },
    "pik": {
        "x": (2892, 3409, 3926, 4443, 4960),
        "y": (2567, 3175, 3789),
    },
}

# (Zeile, Spalte) innerhalb eines Farbblocks der Vorlage.
RANK_POSITION = {
    "ass": (0, 0),
    "7": (1, 1),
    "8": (1, 2),
    "9": (1, 3),
    "10": (1, 4),
    "bube": (2, 0),
    "dame": (2, 1),
    "koenig": (2, 2),
}


def rounded_card(face: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Skaliert eine Kartenfläche mit weichen Ecken und dezentem Schatten."""

    scale = size[0] / LARGE_SIZE[0]
    margin = max(2, round(4 * scale))
    shadow_offset = max(2, round(4 * scale))
    face_size = (size[0] - margin * 2, size[1] - margin * 2)
    resized = face.resize(face_size, Image.Resampling.LANCZOS).convert("RGBA")

    radius = max(3, round(7 * scale))
    face_mask = Image.new("L", face_size, 0)
    ImageDraw.Draw(face_mask).rounded_rectangle(
        (0, 0, face_size[0] - 1, face_size[1] - 1),
        radius=radius,
        fill=255,
    )
    resized.putalpha(face_mask)

    result = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow_mask = Image.new("L", size, 0)
    ImageDraw.Draw(shadow_mask).rounded_rectangle(
        (
            margin + shadow_offset,
            margin + shadow_offset,
            margin + shadow_offset + face_size[0] - 1,
            margin + shadow_offset + face_size[1] - 1,
        ),
        radius=radius,
        fill=105,
    )
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(max(1, round(2 * scale))))
    shadow.putalpha(shadow_mask)
    result.alpha_composite(shadow)
    result.alpha_composite(resized, (margin, margin))
    return result


def card_back(size: tuple[int, int]) -> Image.Image:
    scale = size[0] / LARGE_SIZE[0]
    margin = max(2, round(4 * scale))
    radius = max(3, round(7 * scale))
    result = Image.new("RGBA", size, (0, 0, 0, 0))

    shadow_mask = Image.new("L", size, 0)
    ImageDraw.Draw(shadow_mask).rounded_rectangle(
        (margin + 3, margin + 3, size[0] - 1, size[1] - 1),
        radius=radius,
        fill=105,
    )
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(max(1, round(2 * scale))))
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow.putalpha(shadow_mask)
    result.alpha_composite(shadow)

    face_box = (margin, margin, size[0] - margin - 1, size[1] - margin - 1)
    face_mask = Image.new("L", size, 0)
    ImageDraw.Draw(face_mask).rounded_rectangle(face_box, radius=radius, fill=255)
    design = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(design)
    draw.rounded_rectangle(face_box, radius=radius, fill="#173f63", outline="#f2d076", width=max(1, round(2 * scale)))
    inset = max(5, round(8 * scale))
    inner = (margin + inset, margin + inset, size[0] - margin - inset - 1, size[1] - margin - inset - 1)
    draw.rounded_rectangle(inner, radius=max(2, radius // 2), outline="#f8f4e8", width=max(1, round(scale)))
    spacing = max(7, round(13 * scale))
    diamond = max(2, round(3 * scale))
    for y in range(inner[1] + spacing // 2, inner[3], spacing):
        for x in range(inner[0] + spacing // 2, inner[2], spacing):
            shift = spacing // 2 if ((y - inner[1]) // spacing) % 2 else 0
            cx = x + shift
            if cx + diamond >= inner[2]:
                continue
            draw.polygon(
                ((cx, y - diamond), (cx + diamond, y), (cx, y + diamond), (cx - diamond, y)),
                fill="#e2b84b",
            )
    design.putalpha(face_mask)
    result.alpha_composite(design)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Große JPG-Kartenvorlage")
    args = parser.parse_args()
    source = Image.open(args.source).convert("RGB")
    if source.size != EXPECTED_SOURCE_SIZE:
        raise SystemExit(
            f"Falsche Vorlagengröße: {source.size}; erwartet {EXPECTED_SOURCE_SIZE}."
        )

    output = Path(__file__).resolve().parents[1] / "assets" / "cards"
    for size_name, size in (("large", LARGE_SIZE), ("small", SMALL_SIZE)):
        target = output / size_name
        target.mkdir(parents=True, exist_ok=True)
        for suit, grid in SUIT_GRID.items():
            for rank, (row, column) in RANK_POSITION.items():
                left = grid["x"][column]
                top = grid["y"][row]
                face = source.crop((left, top, left + FACE_SIZE[0], top + FACE_SIZE[1]))
                rounded_card(face, size).save(target / f"{rank}_{suit}.png", optimize=True)
        card_back(size).save(target / "back.png", optimize=True)

    print(f"Kartenbilder erstellt: {output}")


if __name__ == "__main__":
    main()

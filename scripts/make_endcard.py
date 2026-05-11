"""
End-card generator.

Composes a 1080x1920 PNG end-card with:
- Black background
- Logo (PNG with transparency) in the upper third, centered, scaled to 60% width
- Gold divider line
- "Concert" label in gold
- Title in bold white (event name)
- Date and address in dimmer text

Usage:
    python make_endcard.py --logo logo.png --title "Jardin des Capucins" \\
        --date "Samedi 23 mai 2026 — 11:00" \\
        --addr1 "Rue du Marché 2" --addr2 "1630 Bulle (CH)" \\
        --out end_card.png

Then convert to a 5-second video clip:
    ffmpeg -y -loop 1 -framerate 25 -i end_card.png \\
        -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \\
        -t 5 -vf "fade=t=in:st=0:d=0.6" \\
        -c:v libx264 -preset veryfast -crf 22 -pix_fmt yuv420p \\
        -c:a aac -b:a 128k -shortest end_card.mp4
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont


FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
]
FONT_CANDIDATES_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arial.ttf",
]


def pick(candidates):
    for c in candidates:
        if os.path.exists(c):
            return c
    raise RuntimeError(f"No font found in candidates: {candidates}")


def draw_centered(draw, text, y_norm, font, fill, canvas_w, canvas_h):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text(((canvas_w - w) // 2, int(canvas_h * y_norm)), text, fill=fill, font=font)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--logo", default=None, help="Path to logo PNG (RGBA, transparent bg ideal)")
    ap.add_argument("--label", default="Concert", help="Small label above title (e.g. 'Concert')")
    ap.add_argument("--title", required=True, help="Main title (venue or event name)")
    ap.add_argument("--date", required=True, help="Date line")
    ap.add_argument("--addr1", default="", help="Address line 1")
    ap.add_argument("--addr2", default="", help="Address line 2")
    ap.add_argument("--accent", default="#C8B482", help="Hex color for accent text + divider")
    ap.add_argument("--out", default="end_card.png")
    ap.add_argument("--w", type=int, default=1080)
    ap.add_argument("--h", type=int, default=1920)
    args = ap.parse_args()

    OUT_W, OUT_H = args.w, args.h
    canvas = Image.new("RGB", (OUT_W, OUT_H), (0, 0, 0))

    if args.logo and os.path.exists(args.logo):
        logo = Image.open(args.logo).convert("RGBA")
        target_w = int(OUT_W * 0.60)
        ratio = target_w / logo.width
        target_h = int(logo.height * ratio)
        logo = logo.resize((target_w, target_h), Image.LANCZOS)
        logo_x = (OUT_W - target_w) // 2
        logo_y = int(OUT_H * 0.18)
        canvas.paste(logo, (logo_x, logo_y), logo)

    font_bold = ImageFont.truetype(pick(FONT_CANDIDATES_BOLD), 70)
    font_label = ImageFont.truetype(pick(FONT_CANDIDATES_BOLD), 58)
    font_sub = ImageFont.truetype(pick(FONT_CANDIDATES_REG), 44)

    draw = ImageDraw.Draw(canvas)

    # Hex → RGB for accent
    accent_hex = args.accent.lstrip("#")
    accent_rgb = tuple(int(accent_hex[i:i+2], 16) for i in (0, 2, 4))

    # Divider line
    draw.rectangle(
        [(OUT_W * 0.30, OUT_H * 0.545), (OUT_W * 0.70, OUT_H * 0.547)],
        fill=accent_rgb,
    )

    # Label (e.g. "Concert")
    draw_centered(draw, args.label, 0.56, font_label, accent_rgb, OUT_W, OUT_H)
    # Title
    draw_centered(draw, args.title, 0.62, font_bold, (255, 255, 255), OUT_W, OUT_H)
    # Date
    draw_centered(draw, args.date, 0.71, font_sub, (220, 220, 220), OUT_W, OUT_H)
    # Address
    if args.addr1:
        draw_centered(draw, args.addr1, 0.77, font_sub, (180, 180, 180), OUT_W, OUT_H)
    if args.addr2:
        draw_centered(draw, args.addr2, 0.81, font_sub, (180, 180, 180), OUT_W, OUT_H)

    canvas.save(args.out, "PNG")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()

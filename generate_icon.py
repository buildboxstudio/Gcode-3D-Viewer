"""
Generate a cool 3D-printing themed app icon (icon.ico).
Draws an isometric layered cube on a gradient background.
Run: python generate_icon.py
"""
import os
import math
from PIL import Image, ImageDraw


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def draw_icon(size):
    # Supersample for smooth edges
    ss = 4
    S = size * ss
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Rounded gradient background ---
    radius = int(S * 0.22)
    top_col = (38, 42, 90)      # deep navy
    bot_col = (120, 60, 200)    # purple
    grad = Image.new('RGB', (S, S), top_col)
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / S
        r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
        g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
        b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
        gd.line([(0, y), (S, y)], fill=(r, g, b))

    # rounded mask
    mask = Image.new('L', (S, S), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(img)

    # --- Isometric layered cube ---
    cx, cy = S / 2, S / 2 + S * 0.02
    r = S * 0.30

    A = (cx, cy - r)                       # top
    B = (cx + r * 0.866, cy - r * 0.5)     # right-upper
    C = (cx + r * 0.866, cy + r * 0.5)     # right-lower
    D = (cx, cy + r)                       # bottom
    E = (cx - r * 0.866, cy + r * 0.5)     # left-lower
    F = (cx - r * 0.866, cy - r * 0.5)     # left-upper
    G = (cx, cy)                           # center

    top_face = (190, 225, 255)
    left_face = (95, 150, 245)
    right_face = (55, 95, 190)

    draw.polygon([A, B, G, F], fill=top_face)
    draw.polygon([F, G, D, E], fill=left_face)
    draw.polygon([B, C, D, G], fill=right_face)

    # --- Layer lines (the 3D printing look) ---
    n_layers = 6
    line_w = max(1, int(ss * 1.2))
    left_line = (70, 120, 215)
    right_line = (40, 70, 150)
    for i in range(1, n_layers):
        t = i / n_layers
        # Left face: parallel to F->G, from top edge (F-G) down to (E-D)
        p1 = lerp(F, E, t)
        p2 = lerp(G, D, t)
        draw.line([p1, p2], fill=left_line, width=line_w)
        # Right face: parallel to B->G, from (B-C) down to (G-D)
        q1 = lerp(B, C, t)
        q2 = lerp(G, D, t)
        draw.line([q1, q2], fill=right_line, width=line_w)

    # Outline edges for crispness
    edge = (225, 240, 255)
    ew = max(1, int(ss * 1.4))
    for a, b in [(A, B), (B, C), (C, D), (D, E), (E, F), (F, A),
                 (A, G), (B, G), (D, G)]:
        draw.line([a, b], fill=edge, width=ew)

    # --- Nozzle accent (small triangle above cube) ---
    nz = S * 0.07
    nozzle = [(cx, A[1] - nz * 1.6), (cx - nz, A[1] - nz * 0.2),
              (cx + nz, A[1] - nz * 0.2)]
    draw.polygon(nozzle, fill=(255, 210, 90))

    # Downscale
    return img.resize((size, size), Image.LANCZOS)


def main():
    d = os.path.dirname(os.path.abspath(__file__))
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_icon(s) for s in sizes]
    out = os.path.join(d, 'icon.ico')
    images[-1].save(out, format='ICO',
                    sizes=[(s, s) for s in sizes])
    # Also save a PNG preview
    images[-1].save(os.path.join(d, 'icon.png'))
    print(f"Icon saved: {out}")


if __name__ == '__main__':
    main()

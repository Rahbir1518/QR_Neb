"""Generate static (permanent) QR codes for https://www.myneb.si/ with the neb logo.

Outputs (in ./output):
  neb_qr_classic.png  - black/white QR, logo in the middle
  neb_qr_branded.png  - QR styled like the neb app icon
"""
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFilter

URL = "https://www.myneb.si/"
HERE = Path(__file__).parent
LOGO = Image.open(HERE / "assets" / "neb.png").convert("RGBA")
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

SIZE = 2048  # final image size in px


def qr_matrix(version=None):
    # Error correction H tolerates ~30% damage, so the centre logo is safe.
    qr = qrcode.QRCode(version=version, error_correction=qrcode.constants.ERROR_CORRECT_H, border=0)
    qr.add_data(URL)
    qr.make(fit=version is None)
    return qr.get_matrix()


def rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return m


def logo_tile(px):
    """The neb icon, resized, with its own rounded corners kept transparent."""
    return LOGO.resize((px, px), Image.LANCZOS)


# --------------------------------------------------------------------------- classic
def classic():
    m = qr_matrix()
    n = len(m)
    quiet = 4
    cell = SIZE // (n + 2 * quiet)
    dim = cell * (n + 2 * quiet)
    img = Image.new("RGBA", (dim, dim), "white")
    d = ImageDraw.Draw(img)
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                x0, y0 = (x + quiet) * cell, (y + quiet) * cell
                d.rectangle((x0, y0, x0 + cell - 1, y0 + cell - 1), fill="black")

    # Logo ~22% of QR width, on a white rounded pad
    qr_px = n * cell
    lp = int(qr_px * 0.22)
    pad = int(lp * 0.12)
    cx = dim // 2
    d.rounded_rectangle(
        (cx - lp // 2 - pad, cx - lp // 2 - pad, cx + lp // 2 + pad, cx + lp // 2 + pad),
        radius=int(lp * 0.28), fill="white",
    )
    tile = logo_tile(lp)
    img.alpha_composite(tile, (cx - lp // 2, cx - lp // 2))
    img = img.convert("RGB").resize((SIZE, SIZE), Image.NEAREST)
    img.save(OUT / "neb_qr_classic.png")


# --------------------------------------------------------------------------- branded
def logo_gradient():
    """Vertical gradient sampled row-by-row from the logo (ignoring the white mark)."""
    import numpy as np
    a = np.asarray(LOGO).astype(float)
    rows = []
    for y in range(a.shape[0]):
        px = a[y][(a[y, :, 3] == 255) & (a[y, :, :3].min(axis=1) < 250)][:, :3]
        rows.append(px.mean(axis=0) if len(px) else None)
    # fill gaps
    last = next(r for r in rows if r is not None)
    for i, r in enumerate(rows):
        rows[i] = last = (r if r is not None else last)
    col = np.array(rows).astype(np.uint8)[:, None, :].repeat(8, axis=1)
    img = Image.fromarray(col, "RGB").resize((SIZE, SIZE), Image.BICUBIC)
    return img.filter(ImageFilter.GaussianBlur(SIZE * 0.01))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def branded():
    m = qr_matrix()
    n = len(m)

    # Background: the logo itself, blurred & stretched -> same gradient, no "n"
    bg = logo_gradient()
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(bg, (0, 0), rounded_mask((SIZE, SIZE), int(SIZE * 0.215)))  # icon-like corners

    # White card that holds the code (keeps contrast high for scanners)
    margin = int(SIZE * 0.085)
    card = SIZE - 2 * margin
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((margin, margin, SIZE - margin, SIZE - margin),
                        radius=int(card * 0.14), fill=(255, 255, 255, 245))

    quiet = 2.6  # modules of white space inside the card
    cell = card / (n + 2 * quiet)
    ox = oy = margin + quiet * cell

    # Module colours: deep versions of the logo's teal (top) -> slate (bottom)
    top, bottom = (46, 92, 104), (52, 70, 82)

    def col(y):
        return lerp(top, bottom, y / (n - 1)) + (255,)

    def in_finder(x, y):
        return (x < 7 and y < 7) or (x >= n - 7 and y < 7) or (x < 7 and y >= n - 7)

    # Data modules: rounded "pill" dots, merged with neighbours like the logo's strokes
    r = cell * 0.5
    for y in range(n):
        for x in range(n):
            if not m[y][x] or in_finder(x, y):
                continue
            x0, y0 = ox + x * cell, oy + y * cell
            c = col(y)
            inset = 0
            d.rounded_rectangle((x0 + inset, y0 + inset, x0 + cell - inset, y0 + cell - inset),
                                radius=r - inset, fill=c)
            # bridge to right / down neighbour so runs look like continuous strokes
            if x + 1 < n and m[y][x + 1] and not in_finder(x + 1, y):
                d.rectangle((x0 + cell / 2, y0 + inset, x0 + cell * 1.5, y0 + cell - inset), fill=c)
            if y + 1 < n and m[y + 1][x] and not in_finder(x, y + 1):
                d.rectangle((x0 + inset, y0 + cell / 2, x0 + cell - inset, y0 + cell * 1.5), fill=c)

    # Finder patterns as rounded squares (echoing the icon shape)
    for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):
        x0, y0 = ox + fx * cell, oy + fy * cell
        c = col(fy + 3)
        d.rounded_rectangle((x0, y0, x0 + 7 * cell, y0 + 7 * cell), radius=cell * 2.2, fill=c)
        d.rounded_rectangle((x0 + cell, y0 + cell, x0 + 6 * cell, y0 + 6 * cell),
                            radius=cell * 1.5, fill="white")
        d.rounded_rectangle((x0 + 2 * cell, y0 + 2 * cell, x0 + 5 * cell, y0 + 5 * cell),
                            radius=cell * 1.1, fill=c)

    # Centre: the real neb icon with a soft shadow, on a white clearing
    lp = int(n * cell * 0.24)
    cx = SIZE // 2
    clear = int(lp * 0.14)
    d.rounded_rectangle((cx - lp // 2 - clear, cx - lp // 2 - clear,
                         cx + lp // 2 + clear, cx + lp // 2 + clear),
                        radius=int(lp * 0.3), fill="white")
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (cx - lp // 2, cx - lp // 2 + lp * 0.04, cx + lp // 2, cx + lp // 2 + lp * 0.04),
        radius=int(lp * 0.22), fill=(40, 70, 80, 90))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(lp * 0.05)))
    canvas.alpha_composite(logo_tile(lp), (cx - lp // 2, cx - lp // 2))

    canvas.save(OUT / "neb_qr_branded.png")


# --------------------------------------------------------------------------- logo mosaic
def logo_shaped(version=5, tile=0.86, n_dot=0.70, light_mix=0.15, out="neb_qr_logo_shaped.png"):
    """The QR modules form a mosaic of the neb icon: the white 'n' arrow is drawn
    by the tiles themselves.

    Every module is a tile coloured from the logo at that spot, then pushed to a
    dark or light shade depending on the QR bit, so contrast stays high.
    """
    import numpy as np

    m = qr_matrix(version)
    n = len(m)
    logo = np.asarray(LOGO.resize((1024, 1024), Image.LANCZOS)).astype(float)
    # mask of the white 'n' mark
    nmask = (logo[..., 3] > 250) & (logo[..., :3].min(axis=2) > 248)
    grad = logo_gradient().resize((1024, 1024))
    g = np.asarray(grad).astype(float)

    # Canvas: icon shape, softly washed gradient (visible in the gaps & border)
    bg = Image.blend(grad, Image.new("RGB", grad.size, "white"), 0.35).resize((SIZE, SIZE))
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(bg, (0, 0), rounded_mask((SIZE, SIZE), int(SIZE * 0.215)))
    d = ImageDraw.Draw(canvas)

    margin = SIZE * 0.095
    cell = (SIZE - 2 * margin) / n
    ox = oy = margin

    def sample(x, y):
        """logo info at the centre of module (x, y): (is_in_n, base colour)"""
        px = int((ox + (x + 0.5) * cell) / SIZE * 1023)
        py = int((oy + (y + 0.5) * cell) / SIZE * 1023)
        r = 6  # look at a small window so thin edges count
        win = nmask[max(py - r, 0):py + r, max(px - r, 0):px + r]
        return win.mean() > 0.5, g[py, px]

    def mix(c, t, k):
        return tuple(int(c[i] + (t[i] - c[i]) * k) for i in range(3)) + (255,)

    DEEP = (22, 52, 64)      # dark tiles outside the n
    MID = (24, 62, 76)      # dark tiles inside the n (still dark enough to scan)

    def colour(x, y, is_dark):
        in_n, base = sample(x, y)
        if in_n:
            return (255, 255, 255, 255)  # dark modules get a dot drawn on top
        # outside: dark = deep teal tinted by the local gradient, light = the logo's own colour
        return mix(base, DEEP, 0.88) if is_dark else mix(base, (255, 255, 255), light_mix)

    # Function patterns (finders + alignment) are drawn separately
    fixed = [[False] * n for _ in range(n)]
    finders = ((0, 0), (n - 7, 0), (0, n - 7))
    for fx, fy in finders:
        for y in range(max(fy - 1, 0), min(fy + 8, n)):
            for x in range(max(fx - 1, 0), min(fx + 8, n)):
                fixed[y][x] = True

    t = cell * tile / 2
    for y in range(n):
        for x in range(n):
            if fixed[y][x]:
                continue
            cx, cy = ox + (x + 0.5) * cell, oy + (y + 0.5) * cell
            d.rounded_rectangle((cx - t, cy - t, cx + t, cy + t), radius=t * 0.45,
                                fill=colour(x, y, m[y][x]))
            if m[y][x] and sample(x, y)[0]:
                k = cell * n_dot / 2
                d.ellipse((cx - k, cy - k, cx + k, cy + k), fill=MID)

    # Finders as rounded mosaic-style rings on a pale pad
    for fx, fy in finders:
        x0, y0 = ox + fx * cell, oy + fy * cell
        p = cell * 0.95
        d.rounded_rectangle((x0 - p, y0 - p, x0 + 7 * cell + p, y0 + 7 * cell + p),
                            radius=cell * 2.6, fill="white")
        d.rounded_rectangle((x0, y0, x0 + 7 * cell, y0 + 7 * cell), radius=cell * 2.0, fill=DEEP)
        d.rounded_rectangle((x0 + cell, y0 + cell, x0 + 6 * cell, y0 + 6 * cell),
                            radius=cell * 1.4, fill="white")
        d.rounded_rectangle((x0 + 2 * cell, y0 + 2 * cell, x0 + 5 * cell, y0 + 5 * cell),
                            radius=cell * 1.0, fill=DEEP)

    canvas.save(OUT / out)


if __name__ == "__main__":
    classic()
    branded()
    logo_shaped()
    print("Saved to", OUT)

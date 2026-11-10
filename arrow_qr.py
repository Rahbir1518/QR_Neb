"""QR code cut into the neb 'n' arrow shape -> output/neb_qr_arrow.png

The QR grid is clipped to an n-arrow silhouette. Modules outside the shape are
dropped (read as light); error correction level H recovers them. The three
finder squares sit in the arch corners and the foot of the left leg.
"""
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw, ImageFilter
from make_qr import logo_gradient, lerp, URL

HERE = Path(__file__).parent
OUT = HERE / "output"


def matrix(version, mask):
    q = qrcode.QRCode(version=version, error_correction=qrcode.constants.ERROR_CORRECT_H,
                      border=0, mask_pattern=mask)
    q.add_data(URL)
    q.make(fit=False)
    return q.get_matrix()


def shape_mask(n, k, pad, hole_w, arch, head_y, head_w, tip_dx):
    """n-arrow silhouette in module units (k px per module, pad modules of border)."""
    W = int((n + 2 * pad) * k)
    S = lambda v: (v + pad) * k  # module coord -> px
    m = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(m)
    # outer body: big round top corners (the arch), smaller at the feet
    d.rounded_rectangle((S(-pad), S(-pad), S(n + pad), S(n / 2)), radius=5.5 * k,
                        corners=(True, True, False, False), fill=255)
    d.rounded_rectangle((S(-pad), S(n / 2 - 1), S(n + pad), S(n + pad)), radius=2.0 * k,
                        corners=(False, False, True, True), fill=255)
    # inner hole under the arch (left leg must keep >= 9 modules: finder + format info)
    a = 9.0
    b = a + hole_w
    d.rounded_rectangle((S(a), S(arch), S(b), S(n + pad) + 5), radius=hole_w / 2 * k,
                        corners=(True, True, False, False), fill=0)
    # right leg ends in a downward arrowhead: clear everything below head_y right of hole,
    # then add the arrowhead triangle back (with barbs sticking out on both sides)
    d.rectangle((S(b), S(head_y), S(n + pad) + 5, S(n + pad) + 5), fill=0)
    # narrow the leg above the head so the barbs read
    d.rectangle((S(n - 0.0), S(9.5), S(n + pad) + 5, S(head_y)), fill=0)
    tip_x = (b - head_w + n + pad) / 2 + tip_dx
    d.polygon([(S(b - head_w), S(head_y)), (S(n + pad), S(head_y)), (S(tip_x), S(n + pad))], fill=255)
    return m


def function_cells(n):
    cells = set()
    for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):
        for y in range(max(fy - 1, 0), min(fy + 8, n)):
            for x in range(max(fx - 1, 0), min(fx + 8, n)):
                cells.add((x, y))
    for i in range(n):  # timing
        cells.add((6, i)); cells.add((i, 6))
    for i in range(9):  # format (top-left copy)
        cells.add((8, i)); cells.add((i, 8))
    ver = (n - 17) // 4
    if ver >= 2:
        c = n - 7
        for y in range(c - 2, c + 3):
            for x in range(c - 2, c + 3):
                cells.add((x, y))
    return cells


def render(version=3, mask=4, size=2048, pad=1.6, hole_w=6.0, arch=0.52, head_y=0.68,
           head_w=3.0, tip_dx=0.0, out="neb_qr_arrow.png", report=False):
    m = matrix(version, mask)
    n = len(m)
    k = size / (n + 2 * pad)
    sm = shape_mask(n, k, pad, hole_w, arch * n, head_y * n, head_w, tip_dx)

    def inside(x, y):  # whole module inside the silhouette (check corners + centre)
        pts = [(x + 0.5, y + 0.5), (x + .1, y + .1), (x + .9, y + .1), (x + .1, y + .9), (x + .9, y + .9)]
        return all(sm.getpixel((min(int((px + pad) * k), sm.width - 1),
                                min(int((py + pad) * k), sm.height - 1))) for px, py in pts)

    inc = [[inside(x, y) for x in range(n)] for y in range(n)]
    lost_func = [c for c in function_cells(n) if not inc[c[1]][c[0]]]
    dropped_dark = sum(1 for y in range(n) for x in range(n) if m[y][x] and not inc[y][x])
    if report:
        print(f"v{version} n={n} dropped dark modules={dropped_dark} "
              f"({dropped_dark / (n * n):.1%}), lost function cells={len(lost_func)}")

    # --- draw
    W = sm.width
    grad = logo_gradient().resize((W, W))
    fill = Image.blend(grad, Image.new("RGB", (W, W), "white"), 0.40)
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    img.paste(fill, (0, 0), sm)
    d = ImageDraw.Draw(img)

    top, bottom = (24, 58, 70), (38, 54, 64)
    col = lambda y: lerp(top, bottom, y / (n - 1)) + (255,)
    finders = ((0, 0), (n - 7, 0), (0, n - 7))
    in_finder = lambda x, y: any(fx <= x < fx + 7 and fy <= y < fy + 7 for fx, fy in finders)
    g = k * 0.07
    for y in range(n):
        for x in range(n):
            if m[y][x] and inc[y][x] and not in_finder(x, y):
                x0, y0 = (x + pad) * k, (y + pad) * k
                d.rounded_rectangle((x0 + g, y0 + g, x0 + k - g, y0 + k - g), radius=k * 0.3, fill=col(y))
    for fx, fy in finders:
        x0, y0 = (fx + pad) * k, (fy + pad) * k
        c = col(fy + 3)
        d.rounded_rectangle((x0, y0, x0 + 7 * k, y0 + 7 * k), radius=k * 2.0, fill=c)
        d.rounded_rectangle((x0 + k, y0 + k, x0 + 6 * k, y0 + 6 * k), radius=k * 1.4, fill="white")
        d.rounded_rectangle((x0 + 2 * k, y0 + 2 * k, x0 + 5 * k, y0 + 5 * k), radius=k * 1.0, fill=c)

    # thin outline like the sketch, in the logo's teal
    edge = sm.filter(ImageFilter.FIND_EDGES)
    edge = edge.point(lambda v: 255 if v > 40 else 0).filter(
        ImageFilter.MaxFilter(max(3, int(k * 0.18) | 1)))
    img.paste((70, 120, 134, 255), (0, 0), edge)

    # final canvas with white margin
    canvas = Image.new("RGBA", (W + int(4 * k), W + int(4 * k)), (0, 0, 0, 0))
    canvas.alpha_composite(img, (int(2 * k), int(2 * k)))
    canvas.save(OUT / out)
    return dropped_dark, len(lost_func)


if __name__ == "__main__":
    render(report=True)

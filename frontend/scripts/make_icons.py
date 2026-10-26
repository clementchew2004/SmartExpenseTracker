"""Rasterise the receipt icon (same geometry as public/icon.svg) to PNGs, stdlib only.

Run from frontend/:  python3 scripts/make_icons.py public
"""
import struct, sys, zlib

TEAL, WHITE = (15, 118, 110), (255, 255, 255)

def in_round_rect(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r); cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

def in_receipt(x, y):
    # body 160..352 x 128..384, top corners r16, zigzag bottom (teeth 24 wide, 16 deep)
    if not (160 <= x <= 352 and 128 <= y <= 384):
        return False
    if y < 144 and not in_round_rect(x, y, 160, 128, 352, 400, 16):
        return False
    t = (352 - x) % 48           # one tooth pair = 48px: down 16 over 24, up 16 over 24
    edge = 384 - (t / 24 * 16 if t <= 24 else (48 - t) / 24 * 16)
    return y <= edge

BARS = [(200, 184, 312, 204), (200, 232, 312, 252), (200, 280, 264, 300)]

def colour(x, y, rounded):
    if rounded and not in_round_rect(x, y, 0, 0, 512, 512, 112):
        return None                      # transparent outside the rounded square
    if in_receipt(x, y) and not any(in_round_rect(x, y, a, b, c, d, 10) for a, b, c, d in BARS):
        return WHITE
    return TEAL

def render(size, rounded, ss=4):
    rows = []
    scale = 512 / size
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            r = g = b = a = 0
            for sy in range(ss):
                for sx in range(ss):
                    c = colour((px + (sx + .5) / ss) * scale, (py + (sy + .5) / ss) * scale, rounded)
                    if c:
                        r += c[0]; g += c[1]; b += c[2]; a += 1
            n = ss * ss
            row += bytes([r // a, g // a, b // a, 255 * a // n] if a else [0, 0, 0, 0])
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))

out = sys.argv[1]
for name, size, rounded in [("icon-192.png", 192, True), ("icon-512.png", 512, True),
                            ("icon-maskable-512.png", 512, False), ("apple-touch-icon.png", 180, False)]:
    open(f"{out}/{name}", "wb").write(render(size, rounded))
    print("wrote", name)

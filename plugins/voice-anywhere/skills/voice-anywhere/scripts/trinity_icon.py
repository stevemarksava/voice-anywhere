"""Trinity knot icon for Voice Anywhere.

A Python port of Steve Marks' Trinity Knot mark: one unbroken flame in three colours
(orange, blue, violet) weaving over and under itself. Rendered with Pillow, supersampled,
on a transparent background so it works as a tray icon and as a Windows .ico file.

    frames = KnotFrames(size=64)      # pre-renders everything once (well under a second)
    frames.image("idle")              # dimmed knot: on, not listening
    frames.image("speaking", i, lvl)  # full colour, glow follows voice level 0..1
    frames.image("transcribing", i)   # full colour, steady glow
    frames.image("paused")            # greyscale
    write_ico("voice-anywhere.ico")
"""
from __future__ import annotations

import math

TAU = math.pi * 2
R, D, PER = 1.45, 1.0, 120
PAL = [
    {"outer": (255, 95, 0), "mid": (255, 165, 20), "core": (255, 248, 200)},     # orange
    {"outer": (0, 120, 255), "mid": (35, 210, 255), "core": (210, 250, 255)},    # blue
    {"outer": (145, 20, 255), "mid": (195, 85, 255), "core": (245, 215, 255)},   # violet
]


def _smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _lerp(a, b, t):
    return a + (b - a) * t


def knot_path():
    """Centre-line of the knot: three circular arcs, PER points each, with normals and depth."""
    centres = []
    for i in range(3):
        a = -math.pi / 2 + i * TAU / 3
        centres.append((a, D * math.cos(a), D * math.sin(a)))

    def inter(p, q):
        dx, dy = q[1] - p[1], q[2] - p[2]
        L = math.hypot(dx, dy)
        h = math.sqrt(R * R - L * L / 4)
        mx, my = (p[1] + q[1]) / 2, (p[2] + q[2]) / 2
        ux, uy = -dy / L, dx / L
        return (mx + ux * h, my + uy * h), (mx - ux * h, my - uy * h)

    def tip(i, j):
        a, b = inter(centres[i], centres[j])
        return a if math.hypot(*a) > math.hypot(*b) else b

    path = []
    for arc, (i, j, k) in enumerate([(0, 1, 2), (2, 0, 1), (1, 2, 0)]):
        ca, cx, cy = centres[i]
        t1, t2 = tip(i, j), tip(i, k)
        th1 = math.atan2(t1[1] - cy, t1[0] - cx)
        th2 = math.atan2(t2[1] - cy, t2[0] - cx)
        sw = (th2 - th1) % TAU
        if (ca - th1) % TAU < sw:
            sw -= TAU
        for n in range(PER):
            t = n / PER
            th = th1 + sw * t
            path.append({
                "x": cx + R * math.cos(th), "y": cy + R * math.sin(th),
                "nx": math.cos(th), "ny": math.sin(th),
                "arc": arc, "t": t, "u": (arc + t) / 3,
                "z": -math.sin(TAU * (t - 0.5)),
            })
    return path


PATH = knot_path()
M = len(PATH)


def _colour(arc, t):
    a, b, k = PAL[arc], PAL[(arc + 1) % 3], _smooth(0.82, 1, t)
    return {key: tuple(_lerp(a[key][c], b[key][c], k) for c in range(3)) for key in a}


def _rgb(c, m=1.0, alpha=255):
    return tuple(int(min(255, v * m)) for v in c) + (alpha,)


def _pose(time, W, scale, thick=1.0):
    ang, rip_sp, tw = math.pi, 3.0, 1.6  # fixed: one point straight up, like the original mark
    cs, sn, cx = math.cos(ang), math.sin(ang), W / 2
    pts = []
    for p in PATH:
        rnx, rny = p["nx"] * cs - p["ny"] * sn, p["nx"] * sn + p["ny"] * cs
        rip = math.sin(p["u"] * TAU * 9 - time * rip_sp) * scale * 0.009
        x, y = p["x"] * cs - p["y"] * sn, p["x"] * sn + p["y"] * cs
        ph = p["u"] * 3 * math.pi + time * tw
        w = scale * 0.15 * thick * (0.7 + 0.3 * abs(math.cos(ph))) * (0.6 + 0.4 * _smooth(0, 0.12, min(p["t"], 1 - p["t"])))
        pts.append({**p, "rnx": rnx, "rny": rny, "sx": cx + x * scale + rnx * rip,
                    "sy": cx + y * scale + rny * rip, "w": w, "ridge": math.sin(ph)})
    return pts


def render(size=64, time=0.0, ss=4, thick=2.6):
    """Return (knot, glow) RGBA images of the knot at `time`, both `size` px square."""
    from PIL import Image, ImageDraw, ImageFilter

    W = size * ss
    scale = W / 2 / 2.4
    pts = _pose(time, W, scale, thick)

    # Glow: thick soft strokes per arc, blurred.
    glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for a in range(3):
        line = [(pts[(a * PER + n) % M]["sx"], pts[(a * PER + n) % M]["sy"]) for n in range(PER + 1)]
        gd.line(line, fill=_rgb(PAL[a]["outer"], 1, 200), width=int(scale * 0.15 * thick * 2.2), joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(scale * 0.12))

    knot = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    kd = ImageDraw.Draw(knot)

    def zs(i):
        return pts[i]["z"] + pts[(i + 1) % M]["z"]

    def quad(i, f, fill):
        P = [pts[i], pts[(i + 1) % M], pts[(i + 2) % M]]
        poly = []
        for p in P:
            o, hw = f(p)
            poly.append((p["sx"] + p["rnx"] * (o + hw), p["sy"] + p["rny"] * (o + hw)))
        for p in reversed(P):
            o, hw = f(p)
            poly.append((p["sx"] + p["rnx"] * (o - hw), p["sy"] + p["rny"] * (o - hw)))
        kd.polygon(poly, fill=fill)

    layers = [
        lambda c, sh: (_rgb(c["outer"], sh), lambda q: (0, q["w"] * 0.56)),
        lambda c, sh: (_rgb(c["mid"], sh), lambda q: (0, q["w"] * 0.39)),
        lambda c, sh: (_rgb(c["mid"], min(1.15, sh * 1.1)), lambda q: (-q["ridge"] * q["w"] * 0.22, q["w"] * 0.09)),
        lambda c, sh: (_rgb(tuple(_lerp(c["mid"][k] * sh, c["core"][k], 0.25 + 0.65 * sh) for k in range(3))),
                       lambda q: (q["ridge"] * q["w"] * 0.24, q["w"] * 0.12)),
    ]

    under = [i for i in range(M) if zs(i) < 0]
    over = [i for i in range(M) if zs(i) >= 0]

    def paint(idx):
        for layer in layers:
            for i in idx:
                p = pts[(i + 1) % M]
                sh = 0.6 + 0.4 * (zs(i) / 2 + 1) / 2
                fill, f = layer(_colour(p["arc"], p["t"]), sh)
                quad(i, f, fill)

    paint(under)
    for i in over:  # cut a transparent gap so the over-strands visibly cross the under-strands
        quad(i, lambda q: (0, q["w"] * 0.75), (0, 0, 0, 0))
    paint(over)

    return (knot.resize((size, size), Image.LANCZOS),
            glow.resize((size, size), Image.LANCZOS))


def _scale_alpha(img, k):
    r, g, b, a = img.split()
    from PIL import Image
    return Image.merge("RGBA", (r, g, b, a.point(lambda v: int(min(255, v * k)))))


def _dim(img, brightness, saturation=1.0):
    from PIL import Image, ImageEnhance
    r, g, b, a = img.split()
    rgb = Image.merge("RGB", (r, g, b))
    rgb = ImageEnhance.Color(rgb).enhance(saturation)
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    return Image.merge("RGBA", (*rgb.split(), a))


class KnotFrames:
    """Pre-rendered animation frames; image() composes a frame cheaply at runtime."""

    def __init__(self, size=64, n_frames=12):
        from PIL import Image
        self.size = size
        self.n = n_frames
        self.knots, self.glows = [], []
        for f in range(n_frames):
            k, g = render(size, time=f * (TAU / 1.6) / n_frames)  # one twinkle cycle
            self.knots.append(k)
            self.glows.append(g)
        still_k, still_g = self.knots[0], self.glows[0]
        self.idle = _dim(still_k, 0.9, 0.85)
        self.paused = _dim(still_k, 0.6, 0.0)
        self._blank = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        self._still_glow = still_g

    def image(self, state, frame=0, level=0.0):
        from PIL import Image
        if state in ("idle", "ready"):
            return self.idle
        if state in ("paused", "loading"):
            return self.paused
        i = frame % self.n
        if state == "transcribing":
            glow_k = 0.7
        else:  # speaking/recording: glow tracks the voice
            glow_k = 0.35 + 1.4 * max(0.0, min(1.0, level))
        base = Image.alpha_composite(self._blank, _scale_alpha(self.glows[i], glow_k))
        return Image.alpha_composite(base, self.knots[i])


def write_ico(path, png_path=None):
    """Full-colour knot with a soft glow, as a multi-size .ico (and optionally a 256 px PNG)."""
    from PIL import Image
    k, g = render(256)
    img = Image.alpha_composite(Image.alpha_composite(Image.new("RGBA", (256, 256), (0, 0, 0, 0)),
                                                      _scale_alpha(g, 0.8)), k)
    img.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    if png_path:
        img.save(png_path)
    return img

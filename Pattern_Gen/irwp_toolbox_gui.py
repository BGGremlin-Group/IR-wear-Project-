#!/usr/bin/env python3
"""
IRWP-Toolbox (GUI)
A self-contained pattern generator toolbox.

- Seeded RNG for reproducible runs
- Palette mapping
- Multi-layer blending
- Preview (renders 1 design in-app)
- Batch export to PDFs (color & B/W, 2 designs per page)
- Optional combined PDF (1 design per page: top color, bottom B/W)
- Optional PNG set export (color + B/W per design)
- Fixed pattern order mode (controlled testing)
- Extra blend modes: overlay, exclusion (custom pixel ops; NumPy accelerated when available)
- Extra generators: spirals, voronoi, flowfield

Dependencies: pillow, reportlab, (optional) numpy
"""

import os
import io
import math
import time
import random
import datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from PIL import Image, ImageDraw, ImageChops, ImageFont, ImageFilter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

try:
    import numpy as np  # optional
except Exception:
    np = None

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import ImageTk
except Exception:
    ImageTk = None


# ------------------ utilities ------------------

def _clamp255(x: float) -> int:
    return int(max(0, min(255, x)))

def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int,int,int]:
    """HSL (h in degrees, s/l in 0..1) -> RGB 0..255."""
    h = h % 360.0
    c = (1 - abs(2*l - 1)) * s
    hp = h / 60.0
    x = c * (1 - abs((hp % 2) - 1))
    r1 = g1 = b1 = 0.0
    if 0 <= hp < 1:
        r1,g1,b1 = c,x,0
    elif 1 <= hp < 2:
        r1,g1,b1 = x,c,0
    elif 2 <= hp < 3:
        r1,g1,b1 = 0,c,x
    elif 3 <= hp < 4:
        r1,g1,b1 = 0,x,c
    elif 4 <= hp < 5:
        r1,g1,b1 = x,0,c
    else:
        r1,g1,b1 = c,0,x
    m = l - c/2
    return (_clamp255((r1+m)*255), _clamp255((g1+m)*255), _clamp255((b1+m)*255))


PALETTES = [
    "random", "highcontrast", "subtle", "earthtones", "psychedelic", "neon", "thermal"
]

BLEND_MODES = [
    "source-over", "multiply", "screen", "difference", "lighter", "overlay", "exclusion"
]

def pick_color(rng: random.Random, is_color: bool, palette: str, alpha: int = 255) -> Tuple[int,int,int,int]:
    if not is_color:
        g = rng.randrange(256)
        return (g, g, g, alpha)

    p = (palette or "random").lower()
    if p == "highcontrast":
        return (0,0,0,alpha) if rng.random() > 0.5 else (255,255,255,alpha)
    if p == "subtle":
        s = rng.randrange(80, 181)
        return (s, s, s, alpha)
    if p == "earthtones":
        h = 20 + rng.random() * 60
        sat = (30 + rng.random() * 50) / 100.0
        lig = (20 + rng.random() * 45) / 100.0
        r,g,b = hsl_to_rgb(h, sat, lig)
        return (r,g,b,alpha)
    if p == "psychedelic":
        r,g,b = hsl_to_rgb(rng.random() * 360, 1.0, 0.5)
        return (r,g,b,alpha)
    if p == "neon":
        r,g,b = hsl_to_rgb(180 + rng.random() * 180, 1.0, 0.6)
        return (r,g,b,alpha)
    if p == "thermal":
        t = rng.random()
        return (255,0,255,alpha) if t < 0.33 else (255,255,255,alpha) if t < 0.66 else (0,0,255,alpha)

    r,g,b = hsl_to_rgb(rng.random() * 360, 0.8, 0.6)
    return (r,g,b,alpha)


def _overlay_channel(b: "np.ndarray", t: "np.ndarray") -> "np.ndarray":
    # b,t uint8 arrays
    b_f = b.astype(np.float32)
    t_f = t.astype(np.float32)
    mask = b_f < 128.0
    out = np.empty_like(b_f)
    out[mask] = 2.0 * b_f[mask] * t_f[mask] / 255.0
    out[~mask] = 255.0 - 2.0 * (255.0 - b_f[~mask]) * (255.0 - t_f[~mask]) / 255.0
    return np.clip(out, 0, 255).astype(np.uint8)

def _exclusion_channel(b: "np.ndarray", t: "np.ndarray") -> "np.ndarray":
    b_f = b.astype(np.float32)
    t_f = t.astype(np.float32)
    out = b_f + t_f - 2.0 * b_f * t_f / 255.0
    return np.clip(out, 0, 255).astype(np.uint8)

def blend_layer(base: Image.Image, top: Image.Image, mode: str, alpha: float) -> Image.Image:
    """
    Blend 'top' over 'base'. Alpha (0..1) scales top's alpha channel.
    Supports custom overlay/exclusion (NumPy accelerated when available).
    """
    if alpha <= 0:
        return base

    if base.mode != "RGBA":
        base = base.convert("RGBA")
    if top.mode != "RGBA":
        top = top.convert("RGBA")

    if alpha < 1.0:
        a = top.split()[-1].point(lambda p: int(p * alpha))
        top = top.copy()
        top.putalpha(a)

    m = (mode or "source-over").lower()
    if m == "source-over":
        return Image.alpha_composite(base, top)

    # Simple modes via ImageChops on RGB; alpha from top
    if m in ("multiply", "screen", "difference", "lighter"):
        rgbb = base.convert("RGB")
        rgbt = top.convert("RGB")
        if m == "multiply":
            mixed = ImageChops.multiply(rgbb, rgbt)
        elif m == "screen":
            mixed = ImageChops.screen(rgbb, rgbt)
        elif m == "difference":
            mixed = ImageChops.difference(rgbb, rgbt)
        else:
            mixed = ImageChops.lighter(rgbb, rgbt)
        mixed = mixed.convert("RGBA")
        mixed.putalpha(top.split()[-1])
        return Image.alpha_composite(base, mixed)

    if m in ("overlay", "exclusion"):
        # Custom ops; best with NumPy.
        if np is not None:
            b = np.array(base.convert("RGBA"), dtype=np.uint8)
            t = np.array(top.convert("RGBA"), dtype=np.uint8)
            out = b.copy()

            if m == "overlay":
                out[..., 0] = _overlay_channel(b[..., 0], t[..., 0])
                out[..., 1] = _overlay_channel(b[..., 1], t[..., 1])
                out[..., 2] = _overlay_channel(b[..., 2], t[..., 2])
            else:
                out[..., 0] = _exclusion_channel(b[..., 0], t[..., 0])
                out[..., 1] = _exclusion_channel(b[..., 1], t[..., 1])
                out[..., 2] = _exclusion_channel(b[..., 2], t[..., 2])

            # Alpha composite using top alpha
            ta = t[..., 3].astype(np.float32) / 255.0
            ba = b[..., 3].astype(np.float32) / 255.0
            oa = ta + ba * (1.0 - ta)
            oa_safe = np.where(oa <= 1e-6, 1.0, oa)

            for ch in (0,1,2):
                out[..., ch] = np.clip((out[..., ch].astype(np.float32) * ta + b[..., ch].astype(np.float32) * ba * (1.0 - ta)) / oa_safe, 0, 255).astype(np.uint8)
            out[..., 3] = np.clip(oa * 255.0, 0, 255).astype(np.uint8)

            return Image.fromarray(out, mode="RGBA")

        # Fallback (no NumPy): do the op on a smaller working resolution if large
        W, H = base.size
        work = 0.5 if (W * H) > 800_000 else 1.0
        if work != 1.0:
            w2, h2 = int(W * work), int(H * work)
            b_small = base.resize((w2,h2), Image.BILINEAR)
            t_small = top.resize((w2,h2), Image.BILINEAR)
            blended_small = blend_layer(b_small, t_small, m, 1.0)  # recursion hits NumPy case? no; work==1 in small
            # above recursion loops; avoid recursion by manual per-pixel:
            base2 = b_small.convert("RGBA")
            top2 = t_small.convert("RGBA")
            out = _blend_overlay_exclusion_pure(base2, top2, m)
            out = out.resize((W,H), Image.BILINEAR)
            out.putalpha(Image.alpha_composite(base, top).split()[-1])
            return out

        return _blend_overlay_exclusion_pure(base, top, m)

    return Image.alpha_composite(base, top)


def _blend_overlay_exclusion_pure(base: Image.Image, top: Image.Image, mode: str) -> Image.Image:
    """Pure-PIL fallback for overlay/exclusion. Slower; used for small images or downscaled work."""
    b = base.convert("RGBA")
    t = top.convert("RGBA")
    W, H = b.size
    bpx = b.tobytes()
    tpx = t.tobytes()
    out = bytearray(len(bpx))

    def overlay(bc, tc):
        return int((2*bc*tc/255) if bc < 128 else (255 - 2*(255-bc)*(255-tc)/255))

    def exclusion(bc, tc):
        return int(bc + tc - 2*bc*tc/255)

    f = overlay if mode == "overlay" else exclusion

    for i in range(0, len(bpx), 4):
        br, bg, bb, ba = bpx[i], bpx[i+1], bpx[i+2], bpx[i+3]
        tr, tg, tb, ta = tpx[i], tpx[i+1], tpx[i+2], tpx[i+3]
        # apply op
        rr = _clamp255(f(br, tr))
        gg = _clamp255(f(bg, tg))
        bb2 = _clamp255(f(bb, tb))
        # alpha composite with top alpha
        a = ta / 255.0
        out[i]   = _clamp255(rr * a + br * (1-a))
        out[i+1] = _clamp255(gg * a + bg * (1-a))
        out[i+2] = _clamp255(bb2 * a + bb * (1-a))
        out[i+3] = _clamp255(255*(a + (ba/255.0)*(1-a)))
    return Image.frombytes("RGBA", (W,H), bytes(out))


# ------------------ pattern generators ------------------

def pat_lines(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    count = int(60 + comp * 220)
    for _ in range(count):
        d.line(
            (rng.random()*W, rng.random()*H, rng.random()*W, rng.random()*H),
            fill=pick_color(rng, is_color, pal, alpha=255),
            width=max(1, int(1 + rng.random()*(1 + 6*comp)))
        )
    return img

def pat_circles(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img, "RGBA")
    count = int(25 + comp * 95)
    for _ in range(count):
        cx, cy = rng.random()*W, rng.random()*H
        r = 8 + rng.random()*(18 + 120*comp)
        fill = pick_color(rng, is_color, pal, alpha=int(50 + rng.random()*(110 + 70*comp)))
        outline = pick_color(rng, is_color, pal, alpha=255)
        d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=fill, outline=outline, width=1)
    return img

def pat_grid(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    gs = int(10 + comp * 34)
    for i in range(gs):
        for j in range(gs):
            x = (i/(gs-1))*W + (rng.random()*18 - 9)
            y = (j/(gs-1))*H + (rng.random()*18 - 9)
            rr = 2 + rng.random()*(2 + 10*comp)
            d.ellipse((x-rr, y-rr, x+rr, y+rr), fill=pick_color(rng, is_color, pal, 255))
    return img

def pat_moire(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = W/2 + (rng.random()*90 - 45)
    cy = H/2 + (rng.random()*90 - 45)
    step = 3 + (1-comp)*9
    r = 6.0
    while r < min(W,H)/2:
        d.ellipse((cx-r, cy-r, cx+r, cy+r), outline=pick_color(rng, is_color, pal, 255), width=1)
        r += step
    return img

def pat_dazzle(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    count = int(18 + comp*65)
    for _ in range(count):
        rw = int(25 + rng.random()*(40 + 150*comp))
        rh = int(25 + rng.random()*(40 + 150*comp))
        x = int(rng.random()*max(1, W-rw))
        y = int(rng.random()*max(1, H-rh))
        col = (0,0,0,255) if rng.random() > 0.5 else (255,255,255,255)
        d.rectangle((x, y, x+rw, y+rh), fill=col)
    return img

def pat_zebra(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    stripe = int(8 + (1-comp)*28)
    y = 0
    while y < H:
        d.rectangle((0, y, W, y+stripe), fill=(0,0,0,255) if rng.random()>0.5 else (255,255,255,255))
        y += stripe
        d.rectangle((0, y, W, y+stripe), fill=pick_color(rng, is_color, pal, 255))
        y += stripe
    return img

def pat_checker(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    size = int(18 + (1-comp)*46)
    for y in range(0, H, size):
        for x in range(0, W, size):
            gray = 150 if ((x//size + y//size) % 2 == 0) else 95
            d.rectangle((x,y,x+size,y+size), fill=(gray,gray,gray,255))
    # shadow-ish block
    d.rectangle((size*2, size, W-size*2, H-size), fill=(0,0,0,int(40+comp*150)))
    # ellipse pop
    d.ellipse((W/2-90, H-70, W/2+90, H-20), fill=pick_color(rng, is_color, pal, 255))
    return img

def pat_glitchgrid(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    block = int(14 + comp*38)
    for y in range(0, H, block):
        for x in range(0, W, block):
            col = pick_color(rng, is_color, pal, 255)
            a = int(90 + comp*150)
            dx = int((rng.random()-0.5)*block*comp)
            dy = int((rng.random()-0.5)*block*comp)
            d.rectangle((x+dx, y+dy, x+dx+block, y+dy+block), fill=(col[0],col[1],col[2],a))
            hc = pick_color(rng, is_color, "highcontrast", 255)
            d.rectangle((x, y, x+block, y+block), outline=hc, width=1)
    return img

def pat_noise(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    """Fast noise; NumPy accelerated when available."""
    if np is not None:
        seed = rng.randrange(1, 2_000_000_000)
        gen = np.random.default_rng(seed)
        strength = int(18 + comp*90)
        if is_color:
            arr = gen.integers(0, 256, size=(H, W, 3), dtype=np.uint8).astype(np.int16)
            arr = arr + gen.integers(-strength, strength+1, size=(H, W, 3), dtype=np.int16)
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        else:
            g = gen.integers(0, 256, size=(H, W, 1), dtype=np.uint8)
            arr = np.repeat(g, 3, axis=2)
        img = Image.fromarray(arr, mode="RGB").convert("RGBA")
        img.putalpha(255)
        return img

    # fallback: small-resolution noise then upscale
    sw, sh = max(320, W//3), max(240, H//3)
    buf = bytearray(sw*sh*3)
    for i in range(0, len(buf), 3):
        base = rng.randrange(256)
        if is_color:
            buf[i] = (base + rng.randrange(0, 50)) & 255
            buf[i+1] = base
            buf[i+2] = (base + rng.randrange(0, 50)) & 255
        else:
            buf[i] = buf[i+1] = buf[i+2] = base
    img = Image.frombytes("RGB", (sw,sh), bytes(buf)).convert("RGBA")
    img = img.resize((W,H), Image.BICUBIC)
    img.putalpha(255)
    return img

def pat_spirals(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    """Multi-center spiral sweeps using polyline traces."""
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    centers = 1 + int(comp*3)
    for _ in range(centers):
        cx = rng.random()*W
        cy = rng.random()*H
        turns = 3 + int(comp*8)
        pts = []
        max_r = min(W,H) * (0.25 + 0.35*comp) * (0.6 + rng.random()*0.8)
        step = 0.18 + (1-comp)*0.12
        t = 0.0
        while t < turns * 2 * math.pi:
            r = (t / (turns*2*math.pi)) * max_r
            x = cx + r * math.cos(t)
            y = cy + r * math.sin(t)
            pts.append((x,y))
            t += step
        col = pick_color(rng, is_color, pal, alpha=220)
        width = max(1, int(1 + rng.random()*(1+3*comp)))
        # draw as segments to avoid huge polyline cost
        for i in range(len(pts)-1):
            if i % 2 == 0:
                d.line((pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]), fill=col, width=width)
    return img

def pat_flowfield(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    """Particle tracing in a smooth vector field (sin/cos based)."""
    img = Image.new("RGBA", (W,H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    n_particles = int(300 + comp*1200)
    steps = int(14 + comp*34)
    step_len = 1.2 + comp*2.6

    # field parameters are seed driven
    k1 = 0.008 + comp*0.02
    k2 = 0.010 + comp*0.02
    phase1 = rng.random()*math.tau
    phase2 = rng.random()*math.tau

    def vec(x, y):
        ang = math.sin(x*k1 + phase1) + math.cos(y*k2 + phase2)
        ang2 = math.sin((x+y)*k1*0.7 + phase2)
        a = (ang + 0.7*ang2) * math.pi
        return math.cos(a), math.sin(a)

    for _ in range(n_particles):
        x = rng.random()*W
        y = rng.random()*H
        col = pick_color(rng, is_color, pal, alpha=int(80 + 150*comp))
        w = 1
        for _s in range(steps):
            vx, vy = vec(x, y)
            x2 = x + vx*step_len
            y2 = y + vy*step_len
            d.line((x, y, x2, y2), fill=col, width=w)
            x, y = x2, y2
            if x < 0 or x >= W or y < 0 or y >= H:
                break
    return img

def pat_voronoi(rng: random.Random, W:int, H:int, is_color:bool, pal:str, comp:float) -> Image.Image:
    """
    Voronoi-style cell field. NumPy accelerated when available; otherwise uses low-res approximation then upscales.
    """
    n = 12 + int(comp*30)
    # resolution for fallback
    if np is None:
        sw, sh = max(220, W//3), max(160, H//3)
        points = [(rng.random()*sw, rng.random()*sh) for _ in range(n)]
        colors = [pick_color(rng, is_color, pal, alpha=255) for _ in range(n)]
        # brute force nearest at small resolution
        img = Image.new("RGBA", (sw, sh), (0,0,0,0))
        px = img.load()
        for y in range(sh):
            for x in range(sw):
                best_i = 0
                best_d = 1e18
                for i,(pxi, pyi) in enumerate(points):
                    dx = x - pxi
                    dy = y - pyi
                    dd = dx*dx + dy*dy
                    if dd < best_d:
                        best_d = dd
                        best_i = i
                px[x,y] = colors[best_i]
        # edge emphasis (simple)
        img = img.filter(ImageFilter.FIND_EDGES)
        img = img.resize((W,H), Image.BICUBIC)
        img.putalpha(255)
        return img

    # NumPy version at full resolution
    points = np.stack([np.array([rng.random()*W, rng.random()*H]) for _ in range(n)], axis=0)  # (n,2)
    cols = np.array([pick_color(rng, is_color, pal, 255)[:3] for _ in range(n)], dtype=np.uint8)  # (n,3)

    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    # compute squared distances (H,W,n)
    dx = xs[..., None] - points[:, 0][None, None, :]
    dy = ys[..., None] - points[:, 1][None, None, :]
    dist = dx*dx + dy*dy
    idx = np.argmin(dist, axis=2)  # (H,W)
    out = cols[idx]  # (H,W,3)
    img = Image.fromarray(out, mode="RGB").convert("RGBA")

    # edge emphasis: compare to shifted indices
    edge = (idx != np.roll(idx, 1, axis=0)) | (idx != np.roll(idx, 1, axis=1))
    edge = edge.astype(np.uint8) * 255
    edge_img = Image.fromarray(edge, mode="L").filter(ImageFilter.GaussianBlur(radius=1.0))
    # darken edges slightly
    edge_rgba = Image.merge("RGBA", (edge_img, edge_img, edge_img, edge_img.point(lambda p: int(p*0.35))))
    img = ImageChops.subtract(img, edge_rgba)
    img.putalpha(255)
    return img


PATTERNS = {
    "lines": pat_lines,
    "circles": pat_circles,
    "noise": pat_noise,
    "grid": pat_grid,
    "moire": pat_moire,
    "dazzle": pat_dazzle,
    "zebra": pat_zebra,
    "checker": pat_checker,
    "glitchgrid": pat_glitchgrid,
    "spirals": pat_spirals,
    "voronoi": pat_voronoi,
    "flowfield": pat_flowfield,
}


# ------------------ engine ------------------

@dataclass
class EngineConfig:
    width: int = 1024
    height: int = 768
    count: int = 100
    seed: int = 0  # 0 means random seed per run
    layers_min: int = 2
    layers_max: int = 4
    palette_mode: str = "randomize-per-design"  # or fixed palette name
    blend_mode: str = "randomize-per-design"    # or fixed blend name
    opacity: float = 0.78
    complexity: float = 0.78
    fast_mode: bool = True
    jpeg_quality: int = 88
    save_png_set: bool = False
    combined_pdf: bool = False
    fixed_pattern_order: bool = False

class PatternEngine:
    def __init__(self, patterns: Dict[str, callable]):
        self.patterns = patterns
        self.pattern_names = list(patterns.keys())

    def _pick_palette(self, rng: random.Random, palette_mode: str, is_color: bool) -> str:
        if not is_color:
            return "subtle"
        pm = (palette_mode or "random").lower()
        if pm == "randomize-per-design":
            return rng.choice(PALETTES)
        if pm in PALETTES:
            return pm
        return "random"

    def _pick_blend(self, rng: random.Random, blend_mode: str) -> str:
        bm = (blend_mode or "source-over").lower()
        if bm == "randomize-per-design":
            return rng.choice(BLEND_MODES)
        if bm in BLEND_MODES:
            return bm
        return "source-over"

    def _design_seeds(self, base_seed: int, count: int) -> List[int]:
        master = random.Random(base_seed)
        return [master.randrange(1, 2_000_000_000) for _ in range(count)]

    def render_design(self, seed: int, cfg: EngineConfig, is_color: bool, selected_patterns: List[str]) -> Tuple[Image.Image, Dict]:
        rng = random.Random(seed)

        W, H = cfg.width, cfg.height
        scale = 1.0
        if cfg.fast_mode and (np is None) and (W * H > 900_000):
            # helps for large images without NumPy
            scale = 0.5
        if cfg.fast_mode and (W * H > 2_000_000):
            scale = min(scale, 0.5)
        w2, h2 = (int(W*scale), int(H*scale)) if scale != 1.0 else (W, H)

        pal = self._pick_palette(rng, cfg.palette_mode, is_color)
        blend = self._pick_blend(rng, cfg.blend_mode)
        layers = max(cfg.layers_min, min(cfg.layers_max, rng.randint(cfg.layers_min, cfg.layers_max)))
        opacity = float(cfg.opacity)
        comp = float(cfg.complexity)

        # base background
        base = Image.new("RGBA", (w2,h2), (0,0,0,255))

        # subtle base texture
        tex_rng = random.Random(seed ^ 0x1234ABCD)
        base = Image.alpha_composite(base, pat_noise(tex_rng, w2, h2, False, "subtle", min(0.35, comp)))

        # pattern choice
        pats = [p for p in selected_patterns if p in self.patterns]
        if not pats:
            pats = ["lines"]

        if cfg.fixed_pattern_order:
            # deterministic cycle through selected patterns
            start = rng.randrange(len(pats))
            chosen = [pats[(start + i) % len(pats)] for i in range(layers)]
        else:
            chosen = [rng.choice(pats) for _ in range(layers)]

        for idx, name in enumerate(chosen):
            layer_rng = random.Random(seed ^ (idx*0x9E3779B1))
            layer = self.patterns[name](layer_rng, w2, h2, is_color, pal, comp)
            a = max(0.18, opacity * (1 - idx*0.22))
            mode = "source-over" if idx == 0 else blend
            base = blend_layer(base, layer, mode, a)

        # upscale back if needed
        if scale != 1.0:
            base = base.resize((W,H), Image.BILINEAR)

        # alignment marks
        d = ImageDraw.Draw(base)
        pad = int(min(W,H) * 0.03)
        L = int(min(W,H) * 0.06)
        mark = (255,255,255,220)
        lw = max(2, int(min(W,H)/500))
        for (cx,cy) in [(pad,pad),(W-pad,pad),(pad,H-pad),(W-pad,H-pad)]:
            d.line((cx,cy,cx+(L if cx<W/2 else -L),cy), fill=mark, width=lw)
            d.line((cx,cy,cx,cy+(L if cy<H/2 else -L)), fill=mark, width=lw)
        barW = int(min(W,H)*0.25)
        barH = max(8, int(min(W,H)*0.014))
        d.rectangle((W//2-barW//2, H-pad-barH, W//2+barW//2, H-pad), fill=(255,255,255,220))

        meta = {
            "seed": seed,
            "palette": pal,
            "blend": blend,
            "layers": layers,
            "patterns": chosen,
            "is_color": is_color,
            "size": (W,H),
            "scale": scale,
            "np": (np is not None),
        }
        return base, meta

    def export_pdfs(
        self,
        out_dir: str,
        cfg: EngineConfig,
        selected_patterns: List[str],
        progress_cb=None,
        stop_flag=None
    ) -> Dict[str,str]:
        os.makedirs(out_dir, exist_ok=True)

        base_seed = cfg.seed if cfg.seed and cfg.seed > 0 else random.randrange(1, 2_000_000_000)
        seeds = self._design_seeds(base_seed, cfg.count)

        # 75/25 split:
        color_count = int(round(cfg.count * 0.75))
        flags = [True]*color_count + [False]*(cfg.count - color_count)
        # shuffle, but reproducible per run
        master = random.Random(base_seed ^ 0x55AA55AA)
        master.shuffle(flags)

        today = datetime.date.today().strftime("%B %d, %Y")
        title = f"IRWP Pattern Pack ({cfg.count} designs: {color_count} color / {cfg.count-color_count} B&W)"

        color_pdf = os.path.join(out_dir, f"IRWP_color_mixed_{cfg.count}.pdf")
        bw_pdf = os.path.join(out_dir, f"IRWP_bw_mixed_{cfg.count}.pdf")
        combined_pdf = os.path.join(out_dir, f"IRWP_color+bw_mixed_{cfg.count}.pdf") if cfg.combined_pdf else None

        # optional PNG folders
        png_color_dir = os.path.join(out_dir, "png_set", "color")
        png_bw_dir = os.path.join(out_dir, "png_set", "bw")
        if cfg.save_png_set:
            os.makedirs(png_color_dir, exist_ok=True)
            os.makedirs(png_bw_dir, exist_ok=True)

        # PDF layout
        page_w, page_h = A4
        margin = 36
        header_h = 34
        footer_h = 22
        gap = 14
        slot_w = page_w - 2*margin
        slot_h = (page_h - 2*margin - header_h - footer_h - gap) / 2.0

        def header(c):
            c.setFillColorRGB(0,0,0)
            c.rect(0, page_h-header_h, page_w, header_h, fill=1, stroke=0)
            c.setFillColorRGB(1,1,1)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin, page_h-header_h+10, title)
            c.setFont("Helvetica", 9)
            c.drawRightString(page_w-margin, page_h-header_h+11, f"Generated {today} • run seed {base_seed}")

        # 1) mixed color pdf (only color designs)
        c_color = rl_canvas.Canvas(color_pdf, pagesize=A4)
        c_bw = rl_canvas.Canvas(bw_pdf, pagesize=A4)
        c_comb = rl_canvas.Canvas(combined_pdf, pagesize=A4) if combined_pdf else None

        color_indices = [i for i, f in enumerate(flags) if f]
        bw_indices = [i for i, f in enumerate(flags) if not f]

        def draw_two_per_page(c, indices, kind_label: str):
            pages = math.ceil(len(indices)/2) if indices else 1
            for p in range(pages):
                if stop_flag and stop_flag():
                    break
                header(c)
                for pos in range(2):
                    k = p*2 + pos
                    if k >= len(indices):
                        break
                    idx = indices[k]
                    is_color = (kind_label == "COLOR")
                    img, meta = self.render_design(seeds[idx], cfg, is_color=is_color, selected_patterns=selected_patterns)

                    # PNG set
                    if cfg.save_png_set:
                        fn = f"design_{(idx+1):03d}_seed_{meta['seed']}.png"
                        if is_color:
                            img.save(os.path.join(png_color_dir, fn))
                        else:
                            img.convert("L").convert("RGB").save(os.path.join(png_bw_dir, fn))

                    # embed
                    buf = io.BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=int(cfg.jpeg_quality), optimize=True)
                    buf.seek(0)
                    x = margin
                    y = margin + footer_h + (1-pos)*(slot_h + gap)

                    c.setFillColorRGB(1,1,1)
                    c.rect(x-2, y-2, slot_w+4, slot_h+4, fill=1, stroke=0)
                    c.drawImage(ImageReader(buf), x, y, width=slot_w, height=slot_h, preserveAspectRatio=True, anchor='c')

                    c.setFillColorRGB(0,0,0)
                    c.rect(x, y, slot_w, 18, fill=1, stroke=0)
                    c.setFillColorRGB(1,1,1)
                    c.setFont("Helvetica", 8.6)
                    label = f"{kind_label} • design {(idx+1):03d} • seed {meta['seed']} • {', '.join(meta['patterns'])} • blend {meta['blend']} • palette {meta['palette']}"
                    c.drawString(x+6, y+5, label[:160])

                    if progress_cb:
                        progress_cb()

                c.setFillColorRGB(0.25,0.25,0.25)
                c.setFont("Helvetica", 9)
                c.drawCentredString(page_w/2, margin/2, f"Page {p+1} of {pages}")
                c.showPage()

        # color-only and bw-only pdfs
        draw_two_per_page(c_color, color_indices, "COLOR")
        c_color.save()

        draw_two_per_page(c_bw, bw_indices, "B&W")
        c_bw.save()

        # combined: one design per page
        if c_comb:
            pages = len(seeds)
            for idx in range(cfg.count):
                if stop_flag and stop_flag():
                    break
                header(c_comb)

                # top = color, bottom = bw for same design
                img_c, meta_c = self.render_design(seeds[idx], cfg, is_color=True, selected_patterns=selected_patterns)
                img_b, meta_b = self.render_design(seeds[idx], cfg, is_color=False, selected_patterns=selected_patterns)

                # top
                buf = io.BytesIO()
                img_c.convert("RGB").save(buf, format="JPEG", quality=int(cfg.jpeg_quality), optimize=True)
                buf.seek(0)
                x = margin
                y_top = margin + footer_h + slot_h + gap
                c_comb.setFillColorRGB(1,1,1)
                c_comb.rect(x-2, y_top-2, slot_w+4, slot_h+4, fill=1, stroke=0)
                c_comb.drawImage(ImageReader(buf), x, y_top, width=slot_w, height=slot_h, preserveAspectRatio=True, anchor='c')

                # bottom
                buf2 = io.BytesIO()
                img_b.convert("RGB").save(buf2, format="JPEG", quality=int(cfg.jpeg_quality), optimize=True)
                buf2.seek(0)
                y_bot = margin + footer_h
                c_comb.setFillColorRGB(1,1,1)
                c_comb.rect(x-2, y_bot-2, slot_w+4, slot_h+4, fill=1, stroke=0)
                c_comb.drawImage(ImageReader(buf2), x, y_bot, width=slot_w, height=slot_h, preserveAspectRatio=True, anchor='c')

                c_comb.setFillColorRGB(0,0,0)
                c_comb.rect(x, y_bot, slot_w, 18, fill=1, stroke=0)
                c_comb.setFillColorRGB(1,1,1)
                c_comb.setFont("Helvetica", 8.6)
                label = f"design {(idx+1):03d} • seed {seeds[idx]} • {', '.join(meta_c['patterns'])} • blend {meta_c['blend']} • palette {meta_c['palette']}"
                c_comb.drawString(x+6, y_bot+5, label[:160])

                if progress_cb:
                    progress_cb()

                c_comb.setFillColorRGB(0.25,0.25,0.25)
                c_comb.setFont("Helvetica", 9)
                c_comb.drawCentredString(page_w/2, margin/2, f"Page {idx+1} of {pages}")
                c_comb.showPage()
            c_comb.save()

        return {
            "color_pdf": color_pdf,
            "bw_pdf": bw_pdf,
            "combined_pdf": combined_pdf or "",
            "run_seed": str(base_seed),
            "color_count": str(len(color_indices)),
            "bw_count": str(len(bw_indices)),
        }


# ------------------ GUI ------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IRWP-Toolbox — Pattern Generator (GUI)")
        self.geometry("1100x720")
        self.minsize(980, 680)

        self.engine = PatternEngine(PATTERNS)
        self._stop = False
        self._preview_imgs = (None, None)
        self._preview_tk = (None, None)

        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # left controls
        left = ttk.Frame(root)
        left.pack(side="left", fill="y")

        # right preview / log
        right = ttk.Frame(root)
        right.pack(side="right", fill="both", expand=True, padx=(12,0))

        # Output
        out_box = ttk.LabelFrame(left, text="Output", padding=10)
        out_box.pack(fill="x", pady=6)
        self.out_dir = tk.StringVar(value=os.path.join(os.getcwd(), "output"))
        ttk.Entry(out_box, textvariable=self.out_dir, width=36).grid(row=0, column=0, sticky="ew")
        ttk.Button(out_box, text="Browse…", command=self._browse_out).grid(row=0, column=1, padx=6)
        out_box.columnconfigure(0, weight=1)

        # Run settings
        run_box = ttk.LabelFrame(left, text="Run settings", padding=10)
        run_box.pack(fill="x", pady=6)

        self.seed_var = tk.IntVar(value=0)
        self.count_var = tk.IntVar(value=100)
        self.w_var = tk.IntVar(value=1024)
        self.h_var = tk.IntVar(value=768)

        self.layers_min_var = tk.IntVar(value=2)
        self.layers_max_var = tk.IntVar(value=4)
        self.opacity_var = tk.DoubleVar(value=0.78)
        self.comp_var = tk.DoubleVar(value=0.78)

        self.jpegq_var = tk.IntVar(value=88)
        self.fast_var = tk.BooleanVar(value=True)
        self.save_png_var = tk.BooleanVar(value=False)
        self.combined_var = tk.BooleanVar(value=False)
        self.fixed_order_var = tk.BooleanVar(value=False)

        row = 0
        ttk.Label(run_box, text="Seed (0 = random)").grid(row=row, column=0, sticky="w")
        ttk.Entry(run_box, textvariable=self.seed_var, width=10).grid(row=row, column=1, sticky="w")
        row += 1
        ttk.Label(run_box, text="Count").grid(row=row, column=0, sticky="w")
        ttk.Entry(run_box, textvariable=self.count_var, width=10).grid(row=row, column=1, sticky="w")
        row += 1
        ttk.Label(run_box, text="Size (W×H)").grid(row=row, column=0, sticky="w")
        size_row = ttk.Frame(run_box)
        size_row.grid(row=row, column=1, sticky="w")
        ttk.Entry(size_row, textvariable=self.w_var, width=6).pack(side="left")
        ttk.Label(size_row, text="×").pack(side="left", padx=3)
        ttk.Entry(size_row, textvariable=self.h_var, width=6).pack(side="left")
        row += 1

        ttk.Label(run_box, text="Layers (min–max)").grid(row=row, column=0, sticky="w")
        lay_row = ttk.Frame(run_box)
        lay_row.grid(row=row, column=1, sticky="w")
        ttk.Entry(lay_row, textvariable=self.layers_min_var, width=6).pack(side="left")
        ttk.Label(lay_row, text="–").pack(side="left", padx=3)
        ttk.Entry(lay_row, textvariable=self.layers_max_var, width=6).pack(side="left")
        row += 1

        ttk.Label(run_box, text="Opacity (0.1–1.0)").grid(row=row, column=0, sticky="w")
        ttk.Scale(run_box, from_=0.1, to=1.0, variable=self.opacity_var, orient="horizontal").grid(row=row, column=1, sticky="ew")
        row += 1

        ttk.Label(run_box, text="Complexity (0–1)").grid(row=row, column=0, sticky="w")
        ttk.Scale(run_box, from_=0.0, to=1.0, variable=self.comp_var, orient="horizontal").grid(row=row, column=1, sticky="ew")
        row += 1

        ttk.Label(run_box, text="JPEG quality (50–95)").grid(row=row, column=0, sticky="w")
        ttk.Entry(run_box, textvariable=self.jpegq_var, width=10).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Checkbutton(run_box, text="Fast mode (recommended)", variable=self.fast_var).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Checkbutton(run_box, text="Save PNG set (color + B/W)", variable=self.save_png_var).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Checkbutton(run_box, text="Combined PDF (color + B/W per design)", variable=self.combined_var).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Checkbutton(run_box, text="Fixed pattern order (controlled testing)", variable=self.fixed_order_var).grid(row=row, column=0, columnspan=2, sticky="w")

        run_box.columnconfigure(1, weight=1)

        # Palette & blend
        pb_box = ttk.LabelFrame(left, text="Palette & Blend", padding=10)
        pb_box.pack(fill="x", pady=6)

        self.palette_var = tk.StringVar(value="randomize-per-design")
        self.blend_var = tk.StringVar(value="randomize-per-design")

        ttk.Label(pb_box, text="Palette").grid(row=0, column=0, sticky="w")
        pal_combo = ttk.Combobox(pb_box, textvariable=self.palette_var, values=["randomize-per-design"] + PALETTES, width=22, state="readonly")
        pal_combo.grid(row=0, column=1, sticky="w")

        ttk.Label(pb_box, text="Blend mode").grid(row=1, column=0, sticky="w", pady=(8,0))
        blend_combo = ttk.Combobox(pb_box, textvariable=self.blend_var, values=["randomize-per-design"] + BLEND_MODES, width=22, state="readonly")
        blend_combo.grid(row=1, column=1, sticky="w", pady=(8,0))

        # Patterns selection
        pat_box = ttk.LabelFrame(left, text="Pattern generators", padding=10)
        pat_box.pack(fill="both", expand=True, pady=6)

        self.pat_list = tk.Listbox(pat_box, selectmode="extended", height=14)
        for name in sorted(self.engine.pattern_names):
            self.pat_list.insert("end", name)
        self.pat_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(pat_box, orient="vertical", command=self.pat_list.yview)
        sb.pack(side="right", fill="y")
        self.pat_list.configure(yscrollcommand=sb.set)

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(6,0))
        ttk.Button(btn_row, text="Select curated", command=self._select_curated).pack(side="left")
        ttk.Button(btn_row, text="Select all", command=self._select_all).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Clear", command=self._select_none).pack(side="left")

        # Actions
        act = ttk.LabelFrame(left, text="Actions", padding=10)
        act.pack(fill="x", pady=8)

        ttk.Button(act, text="Preview 1 design", command=self.preview_one).pack(fill="x")
        ttk.Button(act, text="Generate PDFs", command=self.generate).pack(fill="x", pady=(8,0))
        ttk.Button(act, text="Stop", command=self.stop).pack(fill="x", pady=(8,0))
        ttk.Button(act, text="Open output folder", command=self.open_output).pack(fill="x", pady=(8,0))

        # Right side: preview area + log
        prev = ttk.LabelFrame(right, text="Preview (Color / B&W)", padding=10)
        prev.pack(fill="both", expand=False)

        self.prev_label_c = ttk.Label(prev, text="(preview color)", anchor="center")
        self.prev_label_b = ttk.Label(prev, text="(preview B&W)", anchor="center")
        self.prev_label_c.grid(row=0, column=0, padx=6, pady=6)
        self.prev_label_b.grid(row=0, column=1, padx=6, pady=6)
        prev.columnconfigure(0, weight=1)
        prev.columnconfigure(1, weight=1)

        info = ttk.LabelFrame(right, text="Run log", padding=10)
        info.pack(fill="both", expand=True, pady=(10,0))
        self.log = tk.Text(info, height=12, wrap="word")
        self.log.pack(fill="both", expand=True)

        self.status = ttk.Label(right, text="Ready.")
        self.status.pack(fill="x", pady=(10,0))

        self.progress = ttk.Progressbar(right, mode="determinate", maximum=1)
        self.progress.pack(fill="x")

        # defaults
        self._select_curated()
        self._log_env()

    def _log(self, s: str):
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.update_idletasks()

    def _log_env(self):
        self._log(f"NumPy: {'available' if np is not None else 'not installed'}")
        self._log(f"ImageTk: {'available' if ImageTk is not None else 'missing (preview may be limited)'}")
        self._log("Tip: enable Fast mode if generation is slow.")

    def _browse_out(self):
        d = filedialog.askdirectory(initialdir=self.out_dir.get() or os.getcwd())
        if d:
            self.out_dir.set(d)

    def _select_all(self):
        self.pat_list.select_set(0, "end")

    def _select_none(self):
        self.pat_list.selection_clear(0, "end")

    def _select_curated(self):
        curated = {"lines","circles","noise","moire","dazzle","checker","glitchgrid","spirals","voronoi","flowfield"}
        self._select_none()
        for i in range(self.pat_list.size()):
            if self.pat_list.get(i) in curated:
                self.pat_list.select_set(i)

    def _cfg(self) -> EngineConfig:
        return EngineConfig(
            width=max(160, int(self.w_var.get())),
            height=max(160, int(self.h_var.get())),
            count=max(1, int(self.count_var.get())),
            seed=int(self.seed_var.get()),
            layers_min=max(1, int(self.layers_min_var.get())),
            layers_max=max(1, int(self.layers_max_var.get())),
            palette_mode=self.palette_var.get(),
            blend_mode=self.blend_var.get(),
            opacity=float(self.opacity_var.get()),
            complexity=float(self.comp_var.get()),
            fast_mode=bool(self.fast_var.get()),
            jpeg_quality=max(50, min(95, int(self.jpegq_var.get()))),
            save_png_set=bool(self.save_png_var.get()),
            combined_pdf=bool(self.combined_var.get()),
            fixed_pattern_order=bool(self.fixed_order_var.get()),
        )

    def _selected_patterns(self) -> List[str]:
        sel = [self.pat_list.get(i) for i in self.pat_list.curselection()]
        return sel if sel else ["lines"]

    def preview_one(self):
        try:
            cfg = self._cfg()
            pats = self._selected_patterns()
            # deterministic preview seed: run seed or random once per click
            run_seed = cfg.seed if cfg.seed and cfg.seed > 0 else random.randrange(1, 2_000_000_000)
            design_seed = (run_seed ^ 0xA5A5A5A5) & 0x7FFFFFFF

            img_c, meta_c = self.engine.render_design(design_seed, cfg, True, pats)
            img_b, meta_b = self.engine.render_design(design_seed, cfg, False, pats)

            self._preview_imgs = (img_c, img_b)
            self._log(f"Preview seed: {design_seed} • patterns: {', '.join(meta_c['patterns'])} • blend: {meta_c['blend']} • palette: {meta_c['palette']}")

            # show in UI
            if ImageTk is None:
                messagebox.showinfo("Preview", "Preview rendered, but ImageTk is unavailable, so it can't be displayed.\nYou can still export PDFs/PNGs.")
                return

            # fit to labels
            max_w = 420
            max_h = 260
            def fit(img):
                w,h = img.size
                s = min(max_w/w, max_h/h)
                if s < 1:
                    return img.resize((int(w*s), int(h*s)), Image.BILINEAR)
                return img

            imc = fit(img_c).convert("RGB")
            imb = fit(img_b).convert("RGB")
            tkc = ImageTk.PhotoImage(imc)
            tkb = ImageTk.PhotoImage(imb)
            self._preview_tk = (tkc, tkb)
            self.prev_label_c.configure(image=tkc, text="")
            self.prev_label_b.configure(image=tkb, text="")
        except Exception as e:
            messagebox.showerror("Preview error", str(e))

    def stop(self):
        self._stop = True
        self.status.configure(text="Stopping…")

    def generate(self):
        self._stop = False
        try:
            cfg = self._cfg()
            pats = self._selected_patterns()
            out_dir = self.out_dir.get().strip() or os.path.join(os.getcwd(), "output")
            os.makedirs(out_dir, exist_ok=True)

            total_pages_color = math.ceil(int(round(cfg.count*0.75))/2)
            total_pages_bw = math.ceil((cfg.count - int(round(cfg.count*0.75)))/2)
            # progress units: one per embedded design; approx = count + optional combined count
            max_units = cfg.count  # color + bw designs total = count
            if cfg.combined_pdf:
                max_units += cfg.count
            self.progress.configure(maximum=max_units, value=0)

            self._log("—" * 60)
            self._log(f"Generating… count={cfg.count} size={cfg.width}x{cfg.height} layers={cfg.layers_min}-{cfg.layers_max}")
            self._log(f"palette={cfg.palette_mode} blend={cfg.blend_mode} fast={cfg.fast_mode} png_set={cfg.save_png_set} combined={cfg.combined_pdf} fixed_order={cfg.fixed_pattern_order}")

            counter = {"n": 0}
            def tick():
                counter["n"] += 1
                self.progress.configure(value=counter["n"])
                self.status.configure(text=f"Generating… {counter['n']}/{max_units}")
                self.update_idletasks()

            def stopped():
                return self._stop

            result = self.engine.export_pdfs(out_dir, cfg, pats, progress_cb=tick, stop_flag=stopped)
            self.status.configure(text="Done.")
            self._log(f"Run seed: {result['run_seed']}")
            self._log(f"Color PDF: {result['color_pdf']}")
            self._log(f"B&W PDF: {result['bw_pdf']}")
            if cfg.combined_pdf:
                self._log(f"Combined PDF: {result['combined_pdf']}")
            if cfg.save_png_set:
                self._log(f"PNG set: {os.path.join(out_dir, 'png_set')}")
        except Exception as e:
            messagebox.showerror("Generation error", str(e))
            self.status.configure(text="Error.")

    def open_output(self):
        p = self.out_dir.get().strip() or os.path.join(os.getcwd(), "output")
        try:
            if os.name == "nt":
                os.startfile(p)  # type: ignore
            elif sys.platform == "darwin":
                os.system(f"open '{p}'")
            else:
                os.system(f"xdg-open '{p}'")
        except Exception:
            messagebox.showinfo("Output folder", f"Output folder:\n{p}")

import sys

def main():
    # Tk themed
    try:
        from tkinter import font as tkfont
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
IRWP-Toolbox (TUI)
Option-driven terminal UI (no CLI flags), suitable for Termux (no root).
NumPy is NOT required.

Features:
- Seeded RNG
- Palette mapping
- Multi-layer blending
- Preview action (saves preview PNGs to output folder)
- Batch export to PDFs (color & B/W, 2 designs per page)
- Optional combined PDF (1 design per page: top color, bottom B/W)
- Optional PNG set export
- Fixed pattern order mode
- Extra blend modes overlay/exclusion (pure-PIL fallback; fast mode recommended)
- Extra generators: spirals, voronoi (approx), flowfield

Dependencies: pillow, reportlab
"""

import os
import io
import math
import time
import random
import datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple

from PIL import Image, ImageDraw, ImageChops, ImageFilter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

import curses


def _clamp255(x: float) -> int:
    return int(max(0, min(255, x)))

def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int,int,int]:
    h = h % 360.0
    c = (1 - abs(2*l - 1)) * s
    hp = h / 60.0
    x = c * (1 - abs((hp % 2) - 1))
    r1 = g1 = b1 = 0.0
    if 0 <= hp < 1: r1,g1,b1 = c,x,0
    elif 1 <= hp < 2: r1,g1,b1 = x,c,0
    elif 2 <= hp < 3: r1,g1,b1 = 0,c,x
    elif 3 <= hp < 4: r1,g1,b1 = 0,x,c
    elif 4 <= hp < 5: r1,g1,b1 = x,0,c
    else: r1,g1,b1 = c,0,x
    m = l - c/2
    return (_clamp255((r1+m)*255), _clamp255((g1+m)*255), _clamp255((b1+m)*255))


PALETTES = ["random","highcontrast","subtle","earthtones","psychedelic","neon","thermal"]
BLEND_MODES = ["source-over","multiply","screen","difference","lighter","overlay","exclusion"]


def pick_color(rng: random.Random, is_color: bool, palette: str, alpha: int = 255) -> Tuple[int,int,int,int]:
    if not is_color:
        g = rng.randrange(256)
        return (g,g,g,alpha)
    p = (palette or "random").lower()
    if p == "highcontrast":
        return (0,0,0,alpha) if rng.random()>0.5 else (255,255,255,alpha)
    if p == "subtle":
        s = rng.randrange(80,181); return (s,s,s,alpha)
    if p == "earthtones":
        h = 20 + rng.random()*60
        sat = (30 + rng.random()*50)/100.0
        lig = (20 + rng.random()*45)/100.0
        r,g,b = hsl_to_rgb(h,sat,lig); return (r,g,b,alpha)
    if p == "psychedelic":
        r,g,b = hsl_to_rgb(rng.random()*360,1.0,0.5); return (r,g,b,alpha)
    if p == "neon":
        r,g,b = hsl_to_rgb(180+rng.random()*180,1.0,0.6); return (r,g,b,alpha)
    if p == "thermal":
        t=rng.random()
        return (255,0,255,alpha) if t<0.33 else (255,255,255,alpha) if t<0.66 else (0,0,255,alpha)
    r,g,b = hsl_to_rgb(rng.random()*360,0.8,0.6); return (r,g,b,alpha)


def _blend_overlay_exclusion_pure(base: Image.Image, top: Image.Image, mode: str) -> Image.Image:
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
        rr = _clamp255(f(br, tr))
        gg = _clamp255(f(bg, tg))
        bb2 = _clamp255(f(bb, tb))
        a = ta / 255.0
        out[i]   = _clamp255(rr * a + br * (1-a))
        out[i+1] = _clamp255(gg * a + bg * (1-a))
        out[i+2] = _clamp255(bb2 * a + bb * (1-a))
        out[i+3] = _clamp255(255*(a + (ba/255.0)*(1-a)))
    return Image.frombytes("RGBA", (W,H), bytes(out))


def blend_layer(base: Image.Image, top: Image.Image, mode: str, alpha: float) -> Image.Image:
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

    if m in ("multiply","screen","difference","lighter"):
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

    if m in ("overlay","exclusion"):
        # For performance, do these at reduced resolution if the image is big.
        W,H = base.size
        work = 0.5 if (W*H) > 800_000 else 1.0
        if work != 1.0:
            w2,h2 = int(W*work), int(H*work)
            b2 = base.resize((w2,h2), Image.BILINEAR)
            t2 = top.resize((w2,h2), Image.BILINEAR)
            out2 = _blend_overlay_exclusion_pure(b2, t2, m)
            out = out2.resize((W,H), Image.BILINEAR)
            out.putalpha(Image.alpha_composite(base, top).split()[-1])
            return out
        return _blend_overlay_exclusion_pure(base, top, m)

    return Image.alpha_composite(base, top)


# ---------------- patterns ----------------

def pat_lines(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    count=int(60+comp*220)
    for _ in range(count):
        d.line((rng.random()*W,rng.random()*H,rng.random()*W,rng.random()*H),
               fill=pick_color(rng,is_color,pal,255),
               width=max(1,int(1+rng.random()*(1+6*comp))))
    return img

def pat_circles(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img,"RGBA")
    count=int(25+comp*95)
    for _ in range(count):
        cx,cy=rng.random()*W,rng.random()*H
        r=8+rng.random()*(18+120*comp)
        fill=pick_color(rng,is_color,pal,alpha=int(50+rng.random()*(110+70*comp)))
        outline=pick_color(rng,is_color,pal,alpha=255)
        d.ellipse((cx-r,cy-r,cx+r,cy+r), fill=fill, outline=outline, width=1)
    return img

def pat_grid(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    gs=int(10+comp*34)
    for i in range(gs):
        for j in range(gs):
            x=(i/(gs-1))*W+(rng.random()*18-9)
            y=(j/(gs-1))*H+(rng.random()*18-9)
            rr=2+rng.random()*(2+10*comp)
            d.ellipse((x-rr,y-rr,x+rr,y+rr), fill=pick_color(rng,is_color,pal,255))
    return img

def pat_moire(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    cx=W/2+(rng.random()*90-45); cy=H/2+(rng.random()*90-45)
    step=3+(1-comp)*9
    r=6.0
    while r<min(W,H)/2:
        d.ellipse((cx-r,cy-r,cx+r,cy+r), outline=pick_color(rng,is_color,pal,255), width=1)
        r+=step
    return img

def pat_dazzle(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    count=int(18+comp*65)
    for _ in range(count):
        rw=int(25+rng.random()*(40+150*comp))
        rh=int(25+rng.random()*(40+150*comp))
        x=int(rng.random()*max(1,W-rw))
        y=int(rng.random()*max(1,H-rh))
        col=(0,0,0,255) if rng.random()>0.5 else (255,255,255,255)
        d.rectangle((x,y,x+rw,y+rh), fill=col)
    return img

def pat_zebra(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    stripe=int(8+(1-comp)*28)
    y=0
    while y<H:
        d.rectangle((0,y,W,y+stripe), fill=(0,0,0,255) if rng.random()>0.5 else (255,255,255,255))
        y+=stripe
        d.rectangle((0,y,W,y+stripe), fill=pick_color(rng,is_color,pal,255))
        y+=stripe
    return img

def pat_checker(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    size=int(18+(1-comp)*46)
    for y in range(0,H,size):
        for x in range(0,W,size):
            gray=150 if ((x//size+y//size)%2==0) else 95
            d.rectangle((x,y,x+size,y+size), fill=(gray,gray,gray,255))
    d.rectangle((size*2,size,W-size*2,H-size), fill=(0,0,0,int(40+comp*150)))
    d.ellipse((W/2-90,H-70,W/2+90,H-20), fill=pick_color(rng,is_color,pal,255))
    return img

def pat_glitchgrid(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    block=int(14+comp*38)
    for y in range(0,H,block):
        for x in range(0,W,block):
            col=pick_color(rng,is_color,pal,255); a=int(90+comp*150)
            dx=int((rng.random()-0.5)*block*comp)
            dy=int((rng.random()-0.5)*block*comp)
            d.rectangle((x+dx,y+dy,x+dx+block,y+dy+block), fill=(col[0],col[1],col[2],a))
            hc=pick_color(rng,is_color,"highcontrast",255)
            d.rectangle((x,y,x+block,y+block), outline=hc, width=1)
    return img

def pat_noise(rng,W,H,is_color,pal,comp):
    # pure python small noise then upscale (fast)
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

def pat_spirals(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    centers=1+int(comp*3)
    for _ in range(centers):
        cx=rng.random()*W; cy=rng.random()*H
        turns=3+int(comp*8)
        max_r=min(W,H)*(0.25+0.35*comp)*(0.6+rng.random()*0.8)
        step=0.18+(1-comp)*0.12
        t=0.0
        pts=[]
        while t<turns*2*math.pi:
            r=(t/(turns*2*math.pi))*max_r
            x=cx+r*math.cos(t); y=cy+r*math.sin(t)
            pts.append((x,y))
            t+=step
        col=pick_color(rng,is_color,pal,alpha=220)
        width=max(1,int(1+rng.random()*(1+3*comp)))
        for i in range(len(pts)-1):
            if i%2==0:
                d.line((pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1]), fill=col, width=width)
    return img

def pat_flowfield(rng,W,H,is_color,pal,comp):
    img=Image.new("RGBA",(W,H),(0,0,0,0)); d=ImageDraw.Draw(img)
    n_particles=int(220+comp*900)
    steps=int(12+comp*28)
    step_len=1.1+comp*2.4
    k1=0.008+comp*0.02; k2=0.010+comp*0.02
    phase1=rng.random()*math.tau; phase2=rng.random()*math.tau

    def vec(x,y):
        ang=math.sin(x*k1+phase1)+math.cos(y*k2+phase2)
        ang2=math.sin((x+y)*k1*0.7+phase2)
        a=(ang+0.7*ang2)*math.pi
        return math.cos(a), math.sin(a)

    for _ in range(n_particles):
        x=rng.random()*W; y=rng.random()*H
        col=pick_color(rng,is_color,pal,alpha=int(70+140*comp))
        for _s in range(steps):
            vx,vy=vec(x,y)
            x2=x+vx*step_len; y2=y+vy*step_len
            d.line((x,y,x2,y2), fill=col, width=1)
            x,y=x2,y2
            if x<0 or x>=W or y<0 or y>=H:
                break
    return img

def pat_voronoi(rng,W,H,is_color,pal,comp):
    # Approx Voronoi: compute on low-res grid then upscale
    n=12+int(comp*30)
    sw, sh = max(220, W//3), max(160, H//3)
    points=[(rng.random()*sw, rng.random()*sh) for _ in range(n)]
    colors=[pick_color(rng,is_color,pal,255) for _ in range(n)]
    img=Image.new("RGBA",(sw,sh),(0,0,0,0))
    px=img.load()
    for y in range(sh):
        for x in range(sw):
            best_i=0; best_d=1e18
            for i,(pxi,pyi) in enumerate(points):
                dx=x-pxi; dy=y-pyi
                dd=dx*dx+dy*dy
                if dd<best_d:
                    best_d=dd; best_i=i
            px[x,y]=colors[best_i]
    # edges
    img=img.filter(ImageFilter.FIND_EDGES)
    img=img.resize((W,H), Image.BICUBIC)
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

@dataclass
class EngineConfig:
    width: int = 1024
    height: int = 768
    count: int = 100
    seed: int = 0
    layers_min: int = 2
    layers_max: int = 4
    palette_mode: str = "randomize-per-design"
    blend_mode: str = "randomize-per-design"
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

    def _pick_palette(self, rng, palette_mode, is_color):
        if not is_color:
            return "subtle"
        pm=(palette_mode or "random").lower()
        if pm=="randomize-per-design":
            return rng.choice(PALETTES)
        return pm if pm in PALETTES else "random"

    def _pick_blend(self, rng, blend_mode):
        bm=(blend_mode or "source-over").lower()
        if bm=="randomize-per-design":
            return rng.choice(BLEND_MODES)
        return bm if bm in BLEND_MODES else "source-over"

    def _design_seeds(self, base_seed, count):
        master=random.Random(base_seed)
        return [master.randrange(1,2_000_000_000) for _ in range(count)]

    def render_design(self, seed:int, cfg:EngineConfig, is_color:bool, selected_patterns:List[str]):
        rng=random.Random(seed)
        W,H=cfg.width,cfg.height
        scale=1.0
        if cfg.fast_mode and (W*H>900_000):
            scale=0.5
        w2,h2=(int(W*scale), int(H*scale)) if scale!=1.0 else (W,H)

        pal=self._pick_palette(rng,cfg.palette_mode,is_color)
        blend=self._pick_blend(rng,cfg.blend_mode)
        layers=max(cfg.layers_min, min(cfg.layers_max, rng.randint(cfg.layers_min,cfg.layers_max)))
        opacity=float(cfg.opacity); comp=float(cfg.complexity)

        base=Image.new("RGBA",(w2,h2),(0,0,0,255))
        tex_rng=random.Random(seed ^ 0x1234ABCD)
        base=Image.alpha_composite(base, pat_noise(tex_rng, w2,h2, False, "subtle", min(0.35, comp)))

        pats=[p for p in selected_patterns if p in self.patterns] or ["lines"]
        if cfg.fixed_pattern_order:
            start=rng.randrange(len(pats))
            chosen=[pats[(start+i)%len(pats)] for i in range(layers)]
        else:
            chosen=[rng.choice(pats) for _ in range(layers)]

        for idx,name in enumerate(chosen):
            layer_rng=random.Random(seed ^ (idx*0x9E3779B1))
            layer=self.patterns[name](layer_rng,w2,h2,is_color,pal,comp)
            a=max(0.18, opacity*(1-idx*0.22))
            mode="source-over" if idx==0 else blend
            base=blend_layer(base, layer, mode, a)

        if scale!=1.0:
            base=base.resize((W,H), Image.BILINEAR)

        # marks
        d=ImageDraw.Draw(base)
        pad=int(min(W,H)*0.03); L=int(min(W,H)*0.06)
        mark=(255,255,255,220); lw=max(2,int(min(W,H)/500))
        for (cx,cy) in [(pad,pad),(W-pad,pad),(pad,H-pad),(W-pad,H-pad)]:
            d.line((cx,cy,cx+(L if cx<W/2 else -L),cy), fill=mark, width=lw)
            d.line((cx,cy,cx,cy+(L if cy<H/2 else -L)), fill=mark, width=lw)
        barW=int(min(W,H)*0.25); barH=max(8,int(min(W,H)*0.014))
        d.rectangle((W//2-barW//2, H-pad-barH, W//2+barW//2, H-pad), fill=(255,255,255,220))

        meta={"seed":seed,"palette":pal,"blend":blend,"layers":layers,"patterns":chosen,"is_color":is_color}
        return base, meta

    def export_pdfs(self, out_dir:str, cfg:EngineConfig, selected_patterns:List[str], progress_cb=None, stop_flag=None):
        os.makedirs(out_dir, exist_ok=True)

        base_seed = cfg.seed if cfg.seed and cfg.seed > 0 else random.randrange(1, 2_000_000_000)
        seeds = self._design_seeds(base_seed, cfg.count)

        color_count = int(round(cfg.count * 0.75))
        flags = [True]*color_count + [False]*(cfg.count-color_count)
        master = random.Random(base_seed ^ 0x55AA55AA)
        master.shuffle(flags)

        today = datetime.date.today().strftime("%B %d, %Y")
        title = f"IRWP Pattern Pack ({cfg.count} designs: {color_count} color / {cfg.count-color_count} B&W)"

        color_pdf = os.path.join(out_dir, f"IRWP_color_mixed_{cfg.count}.pdf")
        bw_pdf = os.path.join(out_dir, f"IRWP_bw_mixed_{cfg.count}.pdf")
        combined_pdf = os.path.join(out_dir, f"IRWP_color+bw_mixed_{cfg.count}.pdf") if cfg.combined_pdf else None

        png_color_dir = os.path.join(out_dir, "png_set", "color")
        png_bw_dir = os.path.join(out_dir, "png_set", "bw")
        if cfg.save_png_set:
            os.makedirs(png_color_dir, exist_ok=True)
            os.makedirs(png_bw_dir, exist_ok=True)

        page_w, page_h = A4
        margin=36; header_h=34; footer_h=22; gap=14
        slot_w=page_w-2*margin
        slot_h=(page_h-2*margin-header_h-footer_h-gap)/2.0

        def header(c):
            c.setFillColorRGB(0,0,0)
            c.rect(0, page_h-header_h, page_w, header_h, fill=1, stroke=0)
            c.setFillColorRGB(1,1,1)
            c.setFont("Helvetica-Bold",12)
            c.drawString(margin, page_h-header_h+10, title)
            c.setFont("Helvetica",9)
            c.drawRightString(page_w-margin, page_h-header_h+11, f"Generated {today} • run seed {base_seed}")

        c_color = rl_canvas.Canvas(color_pdf, pagesize=A4)
        c_bw = rl_canvas.Canvas(bw_pdf, pagesize=A4)
        c_comb = rl_canvas.Canvas(combined_pdf, pagesize=A4) if combined_pdf else None

        color_indices=[i for i,f in enumerate(flags) if f]
        bw_indices=[i for i,f in enumerate(flags) if not f]

        def draw_two_per_page(c, indices, kind_label):
            pages = math.ceil(len(indices)/2) if indices else 1
            for p in range(pages):
                if stop_flag and stop_flag(): break
                header(c)
                for pos in range(2):
                    k=p*2+pos
                    if k>=len(indices): break
                    idx=indices[k]
                    is_color=(kind_label=="COLOR")
                    img, meta = self.render_design(seeds[idx], cfg, is_color, selected_patterns)

                    if cfg.save_png_set:
                        fn=f"design_{(idx+1):03d}_seed_{meta['seed']}.png"
                        if is_color:
                            img.save(os.path.join(png_color_dir, fn))
                        else:
                            img.convert("L").convert("RGB").save(os.path.join(png_bw_dir, fn))

                    buf=io.BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=int(cfg.jpeg_quality), optimize=True)
                    buf.seek(0)
                    x=margin
                    y=margin+footer_h+(1-pos)*(slot_h+gap)
                    c.setFillColorRGB(1,1,1)
                    c.rect(x-2,y-2,slot_w+4,slot_h+4,fill=1,stroke=0)
                    c.drawImage(ImageReader(buf), x, y, width=slot_w, height=slot_h, preserveAspectRatio=True, anchor='c')
                    c.setFillColorRGB(0,0,0)
                    c.rect(x,y,slot_w,18,fill=1,stroke=0)
                    c.setFillColorRGB(1,1,1)
                    c.setFont("Helvetica",8.6)
                    label=f"{kind_label} • design {(idx+1):03d} • seed {meta['seed']} • {', '.join(meta['patterns'])} • blend {meta['blend']} • palette {meta['palette']}"
                    c.drawString(x+6,y+5,label[:160])

                    if progress_cb: progress_cb()
                c.showPage()

        draw_two_per_page(c_color, color_indices, "COLOR")
        c_color.save()

        draw_two_per_page(c_bw, bw_indices, "B&W")
        c_bw.save()

        if c_comb:
            pages = cfg.count
            for idx in range(cfg.count):
                if stop_flag and stop_flag(): break
                header(c_comb)
                img_c,_ = self.render_design(seeds[idx], cfg, True, selected_patterns)
                img_b,_ = self.render_design(seeds[idx], cfg, False, selected_patterns)

                buf=io.BytesIO()
                img_c.convert("RGB").save(buf, format="JPEG", quality=int(cfg.jpeg_quality), optimize=True)
                buf.seek(0)
                x=margin
                y_top=margin+footer_h+slot_h+gap
                c_comb.drawImage(ImageReader(buf), x, y_top, width=slot_w, height=slot_h, preserveAspectRatio=True, anchor='c')

                buf2=io.BytesIO()
                img_b.convert("RGB").save(buf2, format="JPEG", quality=int(cfg.jpeg_quality), optimize=True)
                buf2.seek(0)
                y_bot=margin+footer_h
                c_comb.drawImage(ImageReader(buf2), x, y_bot, width=slot_w, height=slot_h, preserveAspectRatio=True, anchor='c')

                if progress_cb: progress_cb()
                c_comb.showPage()
            c_comb.save()

        return {"color_pdf":color_pdf,"bw_pdf":bw_pdf,"combined_pdf":combined_pdf or "","run_seed":str(base_seed)}


# ---------------- TUI ----------------

class TUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.engine = PatternEngine(PATTERNS)
        self.patterns = sorted(list(PATTERNS.keys()))
        self.selected = set(["lines","circles","noise","spirals","voronoi","flowfield"])
        self.focus = 0
        self.status = "Ready."
        self.out_dir = os.path.join(os.getcwd(), "output")
        self.cfg = EngineConfig()
        self._stop = False

    def run(self):
        curses.curs_set(0)
        self.stdscr.nodelay(False)
        while True:
            self.draw()
            ch = self.stdscr.getch()
            if ch in (ord('q'), 27):
                break
            elif ch in (curses.KEY_UP, ord('k')):
                self.focus = max(0, self.focus-1)
            elif ch in (curses.KEY_DOWN, ord('j')):
                self.focus = min(len(self.patterns)-1, self.focus+1)
            elif ch == ord(' '):
                name = self.patterns[self.focus]
                if name in self.selected:
                    self.selected.remove(name)
                else:
                    self.selected.add(name)
            elif ch in (10, 13):  # Enter
                self.edit_settings()
            elif ch == ord('g'):
                self.generate()
            elif ch == ord('p'):
                self.preview()
            elif ch == ord('s'):
                self._stop = True
                self.status = "Stop requested."
            elif ch == ord('a'):
                self.selected = set(self.patterns)
            elif ch == ord('c'):
                self.selected = set()
            elif ch == ord('r'):
                self.selected = set(["lines","circles","noise","spirals","voronoi","flowfield"])

    def draw(self):
        self.stdscr.erase()
        h,w = self.stdscr.getmaxyx()
        title = "IRWP-Toolbox (TUI) — SPACE toggle pattern • ENTER settings • g generate • p preview • s stop • q quit"
        self.stdscr.addstr(0, 0, title[:w-1], curses.A_BOLD)

        self.stdscr.addstr(2, 0, f"Output: {self.out_dir}"[:w-1])
        self.stdscr.addstr(3, 0, f"Seed:{self.cfg.seed}  Count:{self.cfg.count}  Size:{self.cfg.width}x{self.cfg.height}  Layers:{self.cfg.layers_min}-{self.cfg.layers_max}"[:w-1])
        self.stdscr.addstr(4, 0, f"Palette:{self.cfg.palette_mode}  Blend:{self.cfg.blend_mode}  Fast:{int(self.cfg.fast_mode)}  PNG:{int(self.cfg.save_png_set)}  Combined:{int(self.cfg.combined_pdf)}  FixedOrder:{int(self.cfg.fixed_pattern_order)}"[:w-1])

        self.stdscr.addstr(6, 0, "Patterns (toggle with SPACE):", curses.A_UNDERLINE)
        box_top = 7
        box_h = h - box_top - 4
        for i in range(min(box_h, len(self.patterns))):
            idx = i
            name = self.patterns[idx]
            mark = "[x]" if name in self.selected else "[ ]"
            line = f"{mark} {name}"
            attr = curses.A_REVERSE if idx == self.focus else curses.A_NORMAL
            self.stdscr.addstr(box_top+i, 0, line[:w-1], attr)

        self.stdscr.addstr(h-2, 0, ("Status: " + self.status)[:w-1])
        self.stdscr.refresh()

    def prompt(self, label, current):
        h,w = self.stdscr.getmaxyx()
        curses.echo()
        self.stdscr.addstr(h-1, 0, " "*(w-1))
        self.stdscr.addstr(h-1, 0, f"{label} [{current}]: "[:w-1])
        self.stdscr.refresh()
        s = self.stdscr.getstr(h-1, min(w-2, len(label)+len(str(current))+4)).decode("utf-8").strip()
        curses.noecho()
        return s if s else str(current)

    def edit_settings(self):
        try:
            self.status = "Editing settings…"
            self.draw()

            self.out_dir = self.prompt("Output folder", self.out_dir)
            self.cfg.seed = int(self.prompt("Seed (0 random)", self.cfg.seed))
            self.cfg.count = int(self.prompt("Count", self.cfg.count))
            self.cfg.width = int(self.prompt("Width", self.cfg.width))
            self.cfg.height = int(self.prompt("Height", self.cfg.height))
            self.cfg.layers_min = int(self.prompt("Layers min", self.cfg.layers_min))
            self.cfg.layers_max = int(self.prompt("Layers max", self.cfg.layers_max))
            self.cfg.opacity = float(self.prompt("Opacity 0.1-1.0", self.cfg.opacity))
            self.cfg.complexity = float(self.prompt("Complexity 0-1", self.cfg.complexity))
            self.cfg.jpeg_quality = int(self.prompt("JPEG quality 50-95", self.cfg.jpeg_quality))
            self.cfg.fast_mode = bool(int(self.prompt("Fast mode 1/0", int(self.cfg.fast_mode))))
            self.cfg.save_png_set = bool(int(self.prompt("Save PNG set 1/0", int(self.cfg.save_png_set))))
            self.cfg.combined_pdf = bool(int(self.prompt("Combined PDF 1/0", int(self.cfg.combined_pdf))))
            self.cfg.fixed_pattern_order = bool(int(self.prompt("Fixed pattern order 1/0", int(self.cfg.fixed_pattern_order))))

            # palette/blend pick
            pm = self.prompt("Palette (randomize-per-design or one of: " + ",".join(PALETTES) + ")", self.cfg.palette_mode)
            self.cfg.palette_mode = pm
            bm = self.prompt("Blend (randomize-per-design or one of: " + ",".join(BLEND_MODES) + ")", self.cfg.blend_mode)
            self.cfg.blend_mode = bm

            self.status = "Settings updated."
        except Exception as e:
            self.status = f"Settings error: {e}"

    def preview(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            pats = sorted(list(self.selected)) or ["lines"]
            run_seed = self.cfg.seed if self.cfg.seed and self.cfg.seed > 0 else random.randrange(1, 2_000_000_000)
            design_seed = (run_seed ^ 0xA5A5A5A5) & 0x7FFFFFFF
            img_c,_ = self.engine.render_design(design_seed, self.cfg, True, pats)
            img_b,_ = self.engine.render_design(design_seed, self.cfg, False, pats)
            fp_c = os.path.join(self.out_dir, f"preview_color_seed_{design_seed}.png")
            fp_b = os.path.join(self.out_dir, f"preview_bw_seed_{design_seed}.png")
            img_c.save(fp_c)
            img_b.convert("L").convert("RGB").save(fp_b)
            self.status = f"Preview saved: {os.path.basename(fp_c)}, {os.path.basename(fp_b)}"
        except Exception as e:
            self.status = f"Preview error: {e}"

    def generate(self):
        self._stop = False
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            pats = sorted(list(self.selected)) or ["lines"]
            self.status = "Generating PDFs… (press 's' to request stop)"
            self.draw()

            total_units = self.cfg.count + (self.cfg.count if self.cfg.combined_pdf else 0)
            done = {"n": 0}
            def tick():
                done["n"] += 1
                self.status = f"Generating… {done['n']}/{total_units}"
                self.draw()

            def stopped():
                return self._stop

            res = self.engine.export_pdfs(self.out_dir, self.cfg, pats, progress_cb=tick, stop_flag=stopped)
            self.status = f"Done. Run seed {res['run_seed']} • files in output folder."
        except Exception as e:
            self.status = f"Generation error: {e}"


def main(stdscr):
    tui = TUI(stdscr)
    tui.run()

if __name__ == "__main__":
    curses.wrapper(main)

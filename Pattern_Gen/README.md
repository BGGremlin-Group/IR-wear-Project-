# IRWP-Toolbox — Pattern Generator Toolbox (GUI + TUI)


![IR-Wear Project Banner](https://github.com/BGGremlin-Group/IR-wear-Project-/blob/main/img/IRWP_GEN_BANNER.png


IRWP-Toolbox is a self-contained toolbox that generates **printable pattern designs** using a **seeded RNG** (reproducible), **palette mapping**, **layer blending**, and exports results as **PDFs with embedded images** for printing/sharing.

This bundle includes two programs:

- **GUI (Windows + Debian/Linux)**: `irwp_toolbox_gui.py`  
  - Tkinter UI with **Preview**, batch generation, PDF/PNG export  
  - Uses **NumPy if installed** for faster per-pixel noise and faster overlay/exclusion blending
- **TUI (Termux / Android, no root)**: `irwp_toolbox_tui.py`  
  - Option-driven terminal UI (no CLI flags)  
  - Does **not** require NumPy  
  - Preview saves PNGs to the output folder

---

## New add-ons included

✅ **Preview button / action**  
- GUI: shows a **Color** and **B&W** preview in-app.  
- TUI: saves `preview_color_*.png` and `preview_bw_*.png` into the output folder.

✅ **Save PNG set**  
- Exports all generated designs as PNGs:
  - `output/png_set/color/design_###_seed_XXXX.png`
  - `output/png_set/bw/design_###_seed_XXXX.png`

✅ **More blend modes**  
- Added: `overlay`, `exclusion`  
- Implemented with custom pixel operations. NumPy accelerates these on desktop if installed.

✅ **More generators**  
- Added: `spirals`, `voronoi`, `flowfield`  
- Voronoi uses a fast approximation in the TUI; NumPy accelerates Voronoi in the GUI if installed.

✅ **Fixed pattern order mode**  
- When enabled, the engine cycles through the selected patterns in a deterministic order for controlled testing.

---

## Outputs

By default, the toolbox generates **100 designs** at **1024×768** and produces:

- `IRWP_color_mixed_100.pdf` (color-only designs, 2 per page)  
- `IRWP_bw_mixed_100.pdf` (B&W-only designs, 2 per page)  
- Optional: `IRWP_color+bw_mixed_100.pdf` (1 design per page; top color, bottom B&W)

The default mix is **75% color / 25% B&W** per run.

---

# Quick start

## Desktop (GUI) — Windows + Debian/Linux

### Install
```bash
pip install pillow reportlab numpy
```
> NumPy is optional, but recommended for speed.

### Run
```bash
python irwp_toolbox_gui.py
```

### Use
1. Choose an output folder.
2. Select patterns and options (palette, blend, layers, etc.).
3. Click **Preview 1 design** (optional).
4. Click **Generate PDFs**.

---

## Termux (TUI) — Android (no root)

### Install
```bash
pkg install python
pip install pillow reportlab
```

### Run
```bash
python irwp_toolbox_tui.py
```

### Controls
- **↑/↓** move
- **SPACE** toggle pattern
- **ENTER** edit settings (option prompts)
- **g** generate PDFs
- **p** preview (saves preview PNGs)
- **s** request stop
- **q** quit  
- **a** select all patterns
- **c** clear selection
- **r** reset to curated selection

---

## Notes on performance

- If generation feels slow:
  - Enable **Fast mode**
  - Reduce size (e.g., 800×600)
  - Reduce layers max
  - Reduce count

- On Termux, **Fast mode is strongly recommended** for `overlay/exclusion` and large sizes.

---

## Requirements

- `requirements_gui.txt` (recommended):
  - pillow
  - reportlab
  - numpy (optional but recommended)
- `requirements_tui.txt`:
  - pillow
  - reportlab

---

## License
MIT
These are provided as-is

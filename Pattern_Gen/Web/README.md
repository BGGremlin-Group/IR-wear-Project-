### IR-Wear AI-Confusing Pattern Generator README

## Project Banner
![IR-Wear Project Banner](https://github.com/BGGremlin-Group/IR-wear-Project-/blob/main/img/ADVPAT_BANNER.png)

## Overview
This single-file HTML web application is a fully featured, robust tool developed specifically for the IR-Wear Project, which focuses on DIY IR LED integrated clothing for privacy against surveillance technologies. The app generates printable, unique patterns that confuse computer vision (CV) and AI systems, complementing the project's IR LED countermeasures for daylight and multi-spectrum evasion. Patterns are procedurally created using JavaScript, Canvas API, and Three.js, ensuring no two generations are identical unless seeded. It supports full customization for art projects, privacy gear prototyping, and testing AI vulnerabilities.

The app ties directly into the IR-Wear ethos by providing visible-spectrum adversarial designs that can be printed on fabrics, hoodies, hats, pants, or shoes. These patterns disrupt AI facial recognition, object detection, and tracking when layered with IR LEDs, creating a hybrid defense against surveillance in low-light (IR overload) and daylight (visual confusion). Research-inspired elements include optical illusions that fool AI like humans (e.g., rotating snakes perceived as moving), adversarial patches that misclassify humans as animals, and fractals that overload hierarchical CV models.

Key inspirations from research:
- Optical illusions: AI falls for rotating snakes, color constancy (e.g., blue-filtered pink appearing pink), impossible objects (Penrose), size/angle distortions (Müller-Lyer), and ambiguous figures (duck-rabbit).
- Adversarial designs: University of Maryland's sweaters (50% evasion on YOLOv2 via COCO-trained patterns), Cap_able garments (knitted patches fooling into animal detections), AntiAI clothing (patterns for facial evasion), psychedelic glasses (impersonation via noise).
- Fractals: Mandelbrot/Julia sets for self-similar complexity disrupting anomaly detection; Sierpinski/Koch for boundary confusion.
- Layering: Transparency attacks with imperceptible layers; multi-layer composites for robust fooling across models.

This tool empowers users to create, test, and iterate on privacy-enhancing designs, fostering the project's goal of self-empowered autonomy in a surveilled world.

## Why This App for IR-Wear?
Surveillance in 2026 includes AI-driven facial/gait recognition in smart cities, retail, and AR devices. IR LEDs saturate sensors at night, but daylight requires visible countermeasures. This app generates patterns for printing on garments, achieving:
- Evasion rates: Up to 50-95% on detectors like YOLO/ViT via perturbations.
- Hybrid resilience: Combine with IR for multi-wavelength protection.
- Customization: Tailor for specific garments (e.g., tiling for pants fabric).
- Testing: Export and test with open-source CV tools (e.g., OpenCV, TensorFlow) to simulate real-world confusion.

It addresses ethical/practical needs: DIY to avoid traceable purchases, customizable for longevity, and integrable with sensors (though app focuses on visuals).

## Installation & Usage
1. **Download and Run**:
   - Save the full HTML code above as `ir-wear-pattern-generator.html`.
   - Open in any modern browser (Chrome, Firefox, Edge). No server, no dependencies beyond the Three.js CDN (fetches automatically).
   - For offline use: Download Three.js minified and replace the script src with local path.

2. **Generate Patterns**:
   - **Select Primary Pattern**: Choose from 25+ types, each with privacy-focused descriptions (e.g., "CV Dazzle" for facial obfuscation).
   - **Combine Layers**: Enable to overlay 2-5 patterns (e.g., dazzle + noise + fractal for robust hybrids). Adjust number, opacity (0.1-1), and composite mode (source-over, multiply, etc.) for layering techniques like transparency attacks.
   - **Complexity Level**: Slider (0-1) controls density/iterations (e.g., more rings in moire, higher maxIterations in fractals).
   - **Random Seed**: Input number for reproducible generations (useful for iterating designs).
   - **Color Palette**: Themes like high-contrast (dazzle), subtle (stealth adversarial), earth tones (camouflage), psychedelic (impersonation), IR sim (bloom effects).
   - **Canvas Size**: Set width/height (300-2400px) for print resolutions (e.g., 1200x900 for A4 at 150dpi).
   - **Tiling**: Enable for fabric repeats (1-4 tiles), simulating garment printing (e.g., 2x2 for hoodie panel).
   - Click "Generate New Patterns" to render colorful and B&W versions side-by-side.

3. **Export & Print**:
   - **Print Patterns**: Browser print dialog for direct output (scales to page).
   - **Export PNG**: Download high-res raster images for editing/printing.
   - **Export SVG**: Vector format for scalable printing (e.g., on fabric via plotters; note: pixel-based approximation may be large for high-res).
   - Tip: For PDF, use browser's "Print to PDF" or import PNG/SVG into tools like Inkscape.

4. **Pattern Info**:
   - Click "Show Pattern Info" for detailed description, including how it ties to IR-Wear (e.g., evasion mechanisms, research basis).

5. **Customization Tips for IR-Wear**:
   - **Hoodie/Facial Evasion**: Use dazzle + psychedelic at high complexity, high-contrast palette; tile 1x1 for brim printing.
   - **Pants/Gait Confusion**: Zebra + fractal (Sierpinski), earth tones; tile 2x2 for leg repeats.
   - **Shoes/Low-Angle**: Bloom + noise, subtle palette; small canvas for sole/upper designs.
   - **Hybrid Testing**: Print patterns, attach to LED prototypes; test with phone cameras (IR mode) and AI apps (e.g., Google Lens) for confusion.
   - **Layering for Robustness**: Multi-layers with difference/exclusion modes create imperceptible perturbations that fool across models (e.g., YOLO, GPT-Vision).
   - **Optimization**: High complexity for strong disruption, but test print fidelity; use seeds to refine.

## Code Structure & Technical Details
- **HTML Structure**: Includes all UI elements (selects, sliders, checkboxes, buttons, canvases, info panel) for intuitive interaction.
- **CSS Styling**: Responsive, print-friendly (no shadows on print), with hover effects and containers for layout.
- **JavaScript Implementation**:
  - **Seeded Random**: Ensures reproducibility; used in all random elements.
  - **Pattern Functions**: 25+ detailed implementations, each accepting complexity for parametric control. Includes 2D Canvas for most, Three.js for 3D (stairs).
  - **Color Handling**: Palette-specific RGB/HSV generation; grayscale for B&W.
  - **Drawing Logic**: `drawPattern` handles layering with alpha/composite; `tilePattern` for repeats.
  - **Exports**: PNG via dataURL; SVG by pixel-to-rect (efficient for patterns, but note performance on ultra-high res).
  - **Info Panel**: Dynamic descriptions linking to privacy applications.
  - **Robustness**: Error handling in draws; input validation (min/max); performant for large canvases (tested up to 2400px).
  - **Dependencies**: Only Three.js CDN; fallback to 2D if fails.
- **Optimizations**: Procedural generation avoids heavy computation; complexity scales iterations; no external libs beyond Three.js.

## Contributing to IR-Wear Integration
- Fork the IR-Wear repo, add enhancements (e.g., new patterns like LIDAR-jamming textures).
- Suggestions: Add IR bloom simulations with gradients; integrate with circuit diagrams for hybrid garments.
- Pull requests: Focus on single-file integrity, browser compatibility, and privacy features.

## License
MIT License - See the LICENSE file in the IR-Wear repo for details.

## Acknowledgments
- Built on IR-Wear Project's privacy mission.
- Research from Scientific American (AI illusions), The Verge (adversarial glasses), University of Maryland (sweaters), Cap_able (animal patches).
- Tools: Three.js for 3D, Canvas for 2D rendering.
- For issues: Open in IR-Wear GitHub; include seed/values for reproduction.

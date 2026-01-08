# IR Wear Project

![Project Banner](https://github.com/BGGremlin-Group/IR-wear-Project-/blob/main/img/banner.png)
**By BGGremlin-Group (BGGG)**  
*Creating Unique Tools for Unique Individuals*

## Overview

For the privacy-centric individual navigating an increasingly surveilled world in late 2025, the evolution of IR LED garments represents a proactive, self-empowered strategy to reclaim autonomy over one's digital footprint and physical presence. With surveillance technologies advancing rapidly—think ubiquitous AI-driven facial recognition integrated into smart city infrastructure, retail analytics, and even wearable devices like augmented reality glasses—these garments serve as a countermeasure, not just against night-vision exploitation but as part of a layered defense system.

Why pursue this? Because privacy erosion isn't merely inconvenient; it's a fundamental assault on personal agency, enabling unchecked data commodification by corporations and governments. In an era where biometric tracking can profile your gait, heartbeat patterns via remote laser interferometry, or even vein structures through near-infrared (NIR) transparency in certain fabrics, IR LED setups disrupt the assumption of passive observability.

How does this work at a deeper level? By emitting 940nm infrared light, which saturates camera sensors' photodiodes, creating overexposure artifacts that render algorithmic analysis unreliable—blooming halos, pixel washouts, or complete obfuscation of key features like faces or body contours. This isn't foolproof, but it's adversarial engineering at its core: exploiting the very wavelengths cameras rely on for enhancement, turning their strengths into vulnerabilities.

## Daylight Adaptations

Moving beyond low-light scenarios, daylight presents unique challenges and opportunities for adaptation. Most modern surveillance cameras, especially in well-lit environments like grocery stores or urban streets, engage mechanical IR-cut filters (IRCF) to block infrared wavelengths, prioritizing visible light for color accuracy and reducing noise. This means standalone IR LEDs lose much of their disruptive potency during the day, as the camera's sensor is tuned away from the 700-1100nm range where IR LEDs operate.

Why does this matter? Daylight surveillance often leans on visible-spectrum AI models for tasks like demographic profiling or behavior prediction, making pure IR countermeasures insufficient. However, residual IR sensitivity persists in many systems—cheaper cameras might have imperfect filters, and hybrid day/night models can switch modes dynamically based on ambient light thresholds (e.g., below 10-20 lux).

To adapt, integrate hybrid approaches: embed IR LEDs alongside visible adversarial elements. For instance, incorporate reflective nano-oxide coatings or metamaterials into fabrics, which scatter or absorb specific wavelengths, achieving up to 95% efficiency in blocking thermal IR (8-14μm range) used in advanced detection like drone-mounted FLIR systems.

Why this hybrid? It creates multi-spectrum resilience—IR for low-light overload, reflective for daylight deflection. How to implement? Print or sew optical illusion patterns (e.g., CV Dazzle-inspired asymmetrical designs) onto garments using inks that confuse AI classifiers by mimicking non-human shapes or introducing edge-detection errors. Recent 2025 innovations include "adversarial bomber jackets" with embedded microstructures that warp facial landmarks in visible light, effectively "ghosting" you from recognition algorithms.

Recommendations: Test in controlled environments first—use a smartphone camera app with IR mode to simulate; in daylight, pair with polarized sunglasses or anti-reflective face paints to further scatter light. For maximal privacy, layer with non-tech solutions like wide-brimmed hats or scarves to physically block angles, and use apps like Signal for metadata-minimized communication during outings.

## Ethical and Practical Considerations

On the ethical and practical front, why build this yourself? Commercial anti-surveillance gear exists but often carries traceability risks—purchases could flag you in data brokers' profiles. DIY empowers customization while fostering technical literacy, a key privacy skill in 2025. Legally, these are generally permissible as passive defenses (no active jamming of signals), but avoid deployment in restricted areas like airports where they might trigger security alerts.

Maintenance recommendations: Regularly inspect for LED burnout (lifespan ~50,000 hours, but heat accelerates failure); use rechargeable NiMH AAA/AA batteries to minimize environmental impact, and cycle them every 3-6 months. For longevity, waterproof wiring with silicone sealant against sweat/rain.

Enhance with sensors: add a photoresistor (LDR) to auto-activate LEDs only in low light, conserving power and reducing daytime visibility risks. Why? An LDR detects ambient lux levels (e.g., <50 lux triggers), preventing unnecessary drain. How? Wire it in a voltage divider circuit parallel to the toggle switch.

Broader recommendations: Combine with emerging tech like conductive fabrics that shield electromagnetic emissions, reducing trackability by RF scanners, or NIR-transparent clothing inversions—opt for thick cottons that block unintended transparency under IR illumination. For ultimate privacy, consider optical camouflage inspirations: experimental suits with ECM suites to jam LIDAR, though that's advanced and heat-intensive.

## Circuit and Wiring Details

Diving into granular circuit and wiring details for each garment, let's break it down component-by-component, explaining the "why" (rationale for choice, physics/engineering principles) and "how" (step-by-step assembly). Assume standard tools: soldering iron, multimeter, wire strippers, heat-shrink tubing for insulation, and a breadboard for initial prototyping.

Components per garment:
- 940nm IR LEDs (high-intensity, ~1.3V drop, 20mA forward current—chosen for invisibility to eyes while maxing sensor overload)
- 1/4W resistors (for current limiting to prevent burnout)
- Toggle switch (SPST, for manual control—simple, reliable)
- Battery holder (as specified)
- Optional 555 timer IC (DIP-8 package, for astable pulsing at 1-10Hz to cut power use by 50% via duty cycle, extending runtime and varying disruption for harder AI filtering)
- 2N2222 NPN transistor (as a switch/amplifier for the timer output, handling up to 800mA total—why? LEDs draw collective current beyond timer's 200mA limit)
- 10kΩ resistors and 10µF capacitor for timer config (RC values set frequency via formula f=1.44/( (R1+2R2)C )—adjustable for optimization)
- Flexible 22-24 AWG wire (stranded for bendability in clothing, tinned copper for conductivity)

Why series-parallel topology? Series drops voltage efficiently (matching battery to LED drops), parallel scales brightness without overloading. Safety: Always calculate power dissipation (P=I²R for resistors) to avoid overheating; use multimeter to verify currents (<20mA/LED).

### Hoodie (20 LEDs, 4xAAA ~6V pack)

Why this config? 20 LEDs provide dense facial/upper torso coverage, ideal for head-on camera disruption; 6V allows 4-LED series strings (5.2V total drop, leaving ~0.8V for resistor—prevents undervoltage dimming).

How to build:
1. Prototype on breadboard—insert 555 IC, connect pin 8 (Vcc) and pin 4 (reset) to +6V, pin 1 to GND. Wire 10kΩ between pins 7-6 (R1), another 10kΩ between pins 6-2 (R2), 10µF between pin 2-GND (polarity: + to pin 2). Pin 5 optional 0.01µF bypass. Output pin 3 to 2N2222 base via 1kΩ resistor (current limit). Transistor emitter to GND, collector to LED cathodes.
2. For LED array: Form 5 parallel strings, each 4 LEDs in series (anode to cathode chain). Why? Balances load—each string ~20mA, total 100mA, ~10hr runtime on 1000mAh AAAs. Per string, add 40Ω resistor (from Ohm's: R=(6V-5.2V)/0.02A) to first anode.
3. Solder: Cut wires to length (e.g., 10-20cm between LEDs for hood spacing). Strip ends, tin with solder. Solder resistor to battery + via toggle switch (switch in series for on/off—why? Prevents accidental drain). Connect switch output to all string anodes. Chain LEDs: Solder anode1 to resistor, cathode1 to anode2, etc., last cathode to transistor collector (or direct GND if no pulsing). Bundle parallels with zip ties.
4. Integrate: Poke 1-2mm holes in hood brim/shoulders (5-10cm spacing for 360° coverage—why even? Avoids hot spots). Insert LEDs outward (epoxy secure), route wires inside lining via seams (stitch channels—prevents snags). Hide pack in pocket, switch on zipper for access. Test: Multimeter in series for 100mA draw; camera view for bloom.

### Hat (12 LEDs, 4xAAA ~6V pack)

Why fewer LEDs? Hats focus on head obfuscation, needing less for brim/crown placement; same 6V for efficiency.

How:
1. Breadboard same as hoodie but scale: 3 parallel strings of 4 LEDs (total 60mA, ~17hr runtime—longer due to lower draw). 40Ω per string. Optional pulsing identical.
2. Solder sequence: Battery + to toggle (SPST, rated 1A—why? Margin over 60mA). Toggle out to resistors. Each resistor to string anode1, series chain, last cathode to collector/GND. Use heat-shrink on joints (insulates, waterproofs—critical for headwear sweat).
3. Wiring: Shorter runs (5-15cm) for compactness. Twist pairs (signal/GND) to reduce EMI—why? Prevents interference with nearby devices.
4. Integrate: Space 12 LEDs: 8 on brim (circular for face shield), 4 on crown (upward angles). Thread wires through fabric mesh or glue channels; pack in band lining. Why brim emphasis? Blocks downward cameras like in stores.

### Pants (20 LEDs, 4xAAA ~6V pack)

Why pants? Lower body tracking (gait analysis) is rising in AI surveillance; 20 LEDs cover legs/waist for full silhouette disruption. Same circuit as hoodie (5 strings/4 LEDs, 40Ω, 100mA).

How:
1. Prototype identical, but consider flex: Use silicone-coated wire (bends with movement—prevents breaks).
2. Solder: Extend wires (30-50cm for leg runs). Connect battery (belt-mounted) + to toggle (pocket-accessible), out to resistors. Strings: Parallel anodes post-resistors, series LEDs down seams. Last cathodes converge to collector/GND (bundle in harness—why? Organizes for mobility).
3. Integrate: Distribute: 10 per leg (5 front/back for symmetry), waistband 0 (focus downward). Poke holes in hems/pockets, secure with fabric tape (non-conductive). Route along inseams (natural flex points). Why? Minimizes visibility, maximizes comfort during walking.

### Shoes (10 LEDs per shoe, 2xAA ~3V pack each)

Why individual packs? Independence per foot for balance, mobility; 3V suits 2-LED strings (2.6V drop).

How per shoe:
1. Breadboard: Scale down—no 555 if space-tight (or mini SMD version). 5 parallel strings of 2 LEDs, 20Ω per (R=(3V-2.6V)/0.02A). Total 100mA, ~20hr on 2000mAh AAs. Transistor if pulsing.
2. Solder: Pack + to toggle (mini rocker for sole access), out to resistors. Resistor to anode1, cathode1 to anode2, cathode2 to GND. Short wires (5-10cm) twisted.
3. Integrate: 10 LEDs: 5 upper (laces/sides for upward view), 5 sole edges (ground-level cams). Embed in foam insoles (custom cut—why? Cushions battery bulge). Route via eyelets; seal with rubber cement. Why per-shoe toggle? Selective activation, e.g., one foot for testing.

## Summary and Upgrades

In summary, this setup equips you with a versatile, upgradable privacy arsenal—evolve by adding LDRs (voltage divider: 10kΩ + LDR to ADC pin if microcontroller future-proofing) or Bluetooth for app control. Why verbose? Because true empowerment demands understanding the intricacies, turning you from consumer to creator in the fight for privacy.

## Contributing

**We welcome contributions! Fork the repo, make your changes, and submit a pull request. We currently request help regarding Debugging Code, Flicker Patterns and Micro Controller Optimization, micro controller code. Solutions for Non micro controller versions ate welcome too!**

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

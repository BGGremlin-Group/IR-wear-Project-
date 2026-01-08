## **`user_attacks/`** README

⚠️ CRITICAL SAFETY & FUNCTIONALITY WARNING

This directory contains live attack patterns for IR surveillance system testing. Some patterns are EXPERIMENTAL and have NOT been field-tested. Use at your own risk. We Are Not Your Nanny. We Are Not Responsible For Your Burns, Nor Your Urns.

---

## Structure 

```
user_attacks/
├── README.md
├── agc_lock.json
├── agc_lock_extended.json
├── agc_lock_quick.json
├── alpr_corrupt.json
├── dazzle.json
├── face_dazzle_intense.json
├── flicker.json
├── ptz_jam.json
├── ptz_overflow_slow.json
├── rolling_shutter_slow.json
├── saturation.json
├── sensor_partial.json
├── EXPERIMENTAL-heat_map.json
├── EXPERIMENTAL-people_rapid.json
├── EXPERIMENTAL-people_spoof.json
├── EXPERIMENTAL-queue_manip.json
└── Deadly_Defaults/
    ├── D_Default1_Aggressive_Overdrive.json
    ├── D_Default2_Burnout_Stress_Test.json
    ├── D_Default3_Chaos_Engine.json
    └── D_Default4_Balanced_Endurance.json
```

File Categories

✅ STABLE & VERIFIED PATTERNS (Should Work)
These patterns are based on documented surveillance system vulnerabilities.

Filename	Attack Type	Description	Target Cameras	
`agc_lock.json`	Camera Attack	5-second AGC lock sequence	AXIS, Hikvision, Avigilon	
`agc_lock_extended.json`	Camera Attack	30-second extended saturation	Stubborn AGC circuits	
`agc_lock_quick.json`	Camera Attack	2-second rapid burst	Fast-recovery cameras	
`alpr_corrupt.json`	Data Injection	License plate OCR corruption	AXIS LPR, Hanwha LPR	
`dazzle.json`	Data Injection	Anti-biometric facial dazzle	FR systems (1.5m range)	
`face_dazzle_intense.json`	Data Injection	High-intensity facial dazzle	AI FR systems (2.5m range)	
`flicker.json`	Camera Attack	1kHz rolling shutter flicker	Rolling shutter CMOS	
`ptz_jam.json`	Camera Attack	PTZ tracking buffer overflow	BOSCH, AXIS PTZ	
`ptz_overflow_slow.json`	Camera Attack	Slow pulse PTZ overflow	Low-end PTZ cameras	
`rolling_shutter_slow.json`	Camera Attack	500Hz slow tear	Older CMOS sensors	
`saturation.json`	Camera Attack	Full sensor saturation	All IR-sensitive cameras	
`sensor_partial.json`	Camera Attack	Partial saturation (range)	Long-range effectiveness	

---

⚠️ EXPERIMENTAL PATTERNS (Ideas, Not Actualities)
These are theoretical concepts that have NOT been tested on live surveillance systems. They are included as proof-of-concept ideas but may not function as described.

Filename	Status	Reality Check	
`EXPERIMENTAL-heat_map.json`	⚠️ Untested	Creates false hot zones in analytics - unverified on live systems	
`EXPERIMENTAL-people_rapid.json`	⚠️ Untested	High-speed people injection - timing may not work on real cameras	
`EXPERIMENTAL-people_spoof.json`	⚠️ Untested	Simulates walking person - AI may filter this pattern	
`EXPERIMENTAL-queue_manip.json`	⚠️ Untested	Queue length spoofing - highly dependent on specific algorithm	

Experimental patterns are more "ideas" than actualities. They are inspired by documented system capabilities but lack any field verification. Use them as starting points for your own experiments and development, not as guaranteed-effective attacks.

---

🔴 DEADLY_DEFAULT EXTREME PATTERNS (High Risk)
Located in `Deadly_Defaults/` subfolder. These patterns run all attacks simultaneously until manually stopped, and may cut usage times in half. 

**Plan Accordingly**

Filename	Risk Level	Description	
`D_Default1_Aggressive_Overdrive.json`	🔴 CRITICAL	Maximum intensity, all attacks, flip-flop, thermal warnings	
`D_Default2_Burnout_Stress_Test.json`	🔴 CRITICAL	Designed to reach thermal shutdown in 10-15 minutes	
`D_Default3_Chaos_Engine.json`	🔴 HIGH	Randomized attacks defeat adaptive AI, unpredictable power draw	
`D_Default4_Balanced_Endurance.json`	🟡 HIGH	20-25 minute operation with micro-rests, reduced intensity	

---

Usage Instructions

Loading Patterns

```python
# In Python GUI
pattern_loader.load_pattern("agc_lock")          # Stable
pattern_loader.load_pattern("EXPERIMENTAL-heat_map")  # May not work
pattern_loader.load_pattern("Deadly_Defaults/D_Default1_Aggressive_Overdrive")  # High power
```

Experimental Patterns Reality Check
Why they might fail:
- Heat Map: Analytics software may filter static IR sources after 24+ hours
- People Spoof: AI motion detection requires velocity/acceleration, not just position changes
- Rapid Injection: Frame rate mismatch between your pulses and camera FPS
- Queue Manip: Modern queue AI uses depth sensing, not just blob detection

What to do if they fail during testing:
1. Check camera logs for "anomaly detected" messages
2. Adjust timing to match target camera's FPS (usually 15-30 FPS)
3. Add more jitter to avoid detection as periodic signal
4. Try shorter/longer durations based on camera processing latency

***Always Test In Your Own Systems Before Attempting Real World Obfucation***

---

Safety Warnings

Stable Patterns
- Battery Life: 2-3 hours continuous at 30mA per LED
- Thermal: Keep LED body <50°C, use micro-rests when feasible - *every 5 minutes ideally*
- Range: Most effective within 3 meters (line-of-sight)

Experimental Patterns
- NO GUARANTEES: May not work at all
- Camera Logs: Higher chance of triggering "anomaly detection"
- Wasted Power: Running untested patterns drains battery for no result

Deadly Defaults
- Thermal Shutdown: Will trigger in 10-25 minutes depending on variant
- LED Degradation: Each 30-minute session reduces LED lifespan by 50%
- Battery: Drains in 1-2 hours, unpredictable for Chaos variant
- Emergency Stop: Always keep finger near toggle switch


**OPTIMIZATION CONTRIBUTIONS WELCOME!!**

---

Adding Your Own Patterns
1. Copy a stable pattern as template
2. Modify `sequence` array with your phases
3. Test on your own hardware first
4. Mark as EXPERIMENTAL- until verified
5. Share verified patterns with community

---

Bottom Line: If it doesn't start with `EXPERIMENTAL-`, it should work. If it does, you're in untested territory.

- BGGG - IR wear Project Team

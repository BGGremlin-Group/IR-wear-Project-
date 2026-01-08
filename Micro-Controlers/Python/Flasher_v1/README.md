##IRWP Flasher V1 README

Overview
Multi-platform firmware flashing and IR surveillance testing application for ESP32, Pi Pico, Arduino Nano, and STM32 microcontrollers.

Directory Structure

```
IR-wear-Project/Micro-Cntrollers/Python/Flasher_v1
── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── orchestrator.py
│   └── serial_worker.py
├── core/
│   ├── __init__.py
│   ├── arduino_interface.py
│   └── pattern_loader.py
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   └── validators.py
├── main.py
└── requirements.txt
```

Dependencies
- PyQt6>=6.5.0
- pyserial>=3.5
- Platform flashing tools (esptool, picotool, avrdude, st-flash)

Installation

```bash
cd Micro-Controlers/Python/Flasher_v1
pip install -r requirements.txt
```

Usage
1. Run: `python main.py`
2. Connect microcontroller via USB
3. Click "Auto-Detect & Connect" or select manual port
4. Click "Flash Selected Platform" (first-time setup)
5. Select attack pattern and targets
6. Click "ARM SYSTEM" to begin cycling
7. Click "EMERGENCY STOP" to halt operations

Pattern System
- Built-in patterns: AGC_LOCK, SATURATION, FLICKER
- Custom patterns loaded from `user_attacks/*.json`
- Format: `{"sequence": [{"group": 0-4, "intensity": 0-255, "duration_ms": int}], "repeat": int}`

Firmware Binaries
Place compiled files in `firmware/`:
- ESP32: `esp32_firmware.bin`
- Pi Pico: `pico_firmware.uf2`
- Arduino Nano: `nano_firmware.hex`
- STM32: `stm32_firmware.bin`

Logging
Generates `logs/` folder with:
- `flasher.log` - Firmware flashing operations
- `serial.log` - Serial communication
- `attacks.log` - Attack execution history
- `patterns.log` - Pattern loading events
- `gui.log` - User interface actions

---

Version: Flasher V1

Maintained: BGGremlin Group - IR Wear Project Team

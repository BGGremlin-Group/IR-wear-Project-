### Firmware Setup
# Firmware Binaries

Place pre-compiled firmware files in this directory:

- `esp32_firmware.bin` - ESP32 firmware (use ESP32 DevKit settings)
- `pico_firmware.uf2` - Raspberry Pi Pico firmware
- `nano_firmware.hex` - Arduino Nano firmware
- `stm32_firmware.bin` - STM32 Blue Pill firmware

## Building Firmware

### ESP32
```bash
# Use Arduino IDE or PlatformIO
# Export binary: Sketch -> Export Compiled Binary
# Rename to esp32_firmware.bin
```

Pi Pico

```bash
# Use Arduino IDE with Pico board support
# Export as .uf2 file
# Rename to pico_firmware.uf2
```

Arduino Nano

```bash
# Use Arduino IDE
# Export compiled HEX: Sketch -> Export Compiled Binary
# Rename to nano_firmware.hex
```

Flashing Tools Installation

Linux/macOS

```bash
# ESP32
pip install esptool

# Pi Pico
sudo apt install picotool  # Linux
brew install picotool      # macOS

# Arduino
sudo apt install avrdude   # Linux
brew install avrdude       # macOS
```

Windows
- Install [Python esptool](https://github.com/espressif/esptool)
- Download [picotool.exe](https://github.com/raspberrypi/picotool/releases)
- Install [WinAVR](http://winavr.sourceforge.net/) for avrdude
- Add tools to system PATH or place in `tools/` directory


---

## **Features Implemented**

### ✅ **Complete Functionality**
- Full GUI with all panels (control, monitor, attack)
- Non-blocking serial communication
- Thread-safe attack orchestrator
- Pattern hot-loading
- Multi-platform firmware flashing
- Hardware safety integration
- Real-time status monitoring
- Emergency stop
- Cycle counter with auto-disarm

### ✅ **Firmware Flashing**
- **Auto-detection** of microcontroller platform
- **ESP32**: esptool integration
- **Pi Pico**: UF2 drag-and-drop or picotool
- **Arduino Nano**: avrdude integration
- **STM32**: st-flash support
- Progress tracking and error handling

### ✅ **Error-Free Implementation**
- Thread-safe queue-based communication
- Memory leak prevention (status feed limit)
- Graceful disconnection handling
- Exception isolation between components
- Input validation on all controls
- Automatic port scanning and refresh

### ✅ **Private Testing Optimized**
- No compliance/legal dialogs
- Direct control without authorization gates
- Simple logging (no crypto overhead)
- Fast pattern switching
- Real-time parameter adjustment

---

## **Usage**

1. **Place firmware binaries** in `firmware/` directory
2. **Install requirements**: `pip install -r requirements.txt`
3. **Run**: `python main.py`
4. **Flash firmware**: Select platform and click "Flash"
5. **Auto-connect**: Click "Auto-Detect & Connect"
6. **Configure**: Select targets, pattern, parameters
7. **Engage safety**: Hold safety button
8. **Arm**: Click "ARM SYSTEM"

All platforms supported with automatic detection and flashing.

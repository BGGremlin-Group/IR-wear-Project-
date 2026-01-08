# IRWP Firmware Changelog

## Version 1.5 - 2026
### "Monolithic Power" Release

**Core Philosophy Change:** System NEVER shuts down under any software condition. Only physical power switch controls power state.
All safety systems are informational/warning only.

---

### Added
- **Complete EEPROM Persistence**
  - Pattern configuration autosave on change
  - Platform-agnostic EEPROM handling
  - ESP32: `EEPROM.commit()` support
  - Factory reset command (`FACTORY_RESET`)

- **Bluetooth Command Interface (ESP32 only)**
  - `BluetoothSerial` stack for wireless control
  - Coexists with USB Serial (unified command processor)
  - Broadcast name: "IRWP_v15"

- **MPU6050 Motion Tracking**
  - Full 6-DOF accelerometer/gyroscope integration
  - Motion logging >20G threshold
  - Informational only - never triggers shutdown
  - I2C auto-detection

- **TMP36 Thermal Monitoring**
  - Analog temperature sensor support on A0
  - 5-second sampling interval
  - Overheat warning at 60°C (no shutdown)
  - JSON status reporting

- **Physical Test Button Support**
  - Optional momentary button on pin 13
  - Triggers TESTMODE: 1-second group cycling
  - Active-low with debouncing

- **Attack Pattern Jitter**
  - Per-phase timing randomization (0-100%)
  - Prevents predictability in field
  - Preserves average cycle timing

- **Enhanced Status JSON**
  - Version reporting
  - Thermal state (`temperature_c`, `overheating`)
  - Test mode indicator
  - Platform identification
  - LED power calculation

- **User-Configurable LED Parameters**
  - `LED_COUNT_HAT/HOODIE/PANTS/SHOES` defines
  - Auto-calculated `TOTAL_CURRENT_A`
  - Supports any LED count (not just 40)

- **PING Command**
  - Health check: `PING` → `PONG`

### Changed
- **Safety Model: Informational Only**
  - Safety switch (pin 12) logs warnings but never disables operation
  - All safety conditions removed from critical path
  - System remains functional regardless of sensor state

- **Power Relay Control**
  - Relay activates immediately on LED operation
  - No emergency detachment on ESP32
  - Remains latched during all operation

- **Command Validation**
  - Commands processed regardless of safety state
  - Safety status reported in JSON only

- **Version Numbering**
  - Reset to 1.5 to reflect new "always-on" architecture
  - Monolithic design principle established

### Architecture Notes
- **Monolithic Build**: No modularization, no dynamic allocation
- **PROGMEM Storage**: All patterns in flash (AVR/ESP32/STM32)
- **Unified PWM**: Hardware PWM (ESP32) + software PWM (others)
- **Cross-Platform**: ESP32, Pico, Nano, STM32F1 fully supported

### Hardware Support Matrix
| Platform | PWM | Bluetooth | EEPROM | Motion | Thermal |
|----------|-----|-----------|--------|--------|---------|
| ESP32    | ✅ HW | ✅ Yes | ✅ Emulated | ✅ I2C | ✅ A0 |
| Pico     | ✅ SW | ❌ No | ✅ Emulated | ✅ I2C | ✅ A0 |
| Nano     | ✅ SW | ❌ No | ✅ HW | ✅ I2C | ✅ A0 |
| STM32    | ✅ HW | ❌ No | ✅ Emulated | ✅ I2C | ✅ A0 |

### Removed
- **All Automatic Shutdown Behaviors**
  - Thermal shutdown removed
  - Emergency stop routines removed
  - Safety switch shutdown removed
  - ISR-based emergency handler removed

- **CRITICAL**: System NEVER stops until power switch opened

### Deprecated
- None. All features retained from previous versions.

---

### Firmware File Naming
- **Source**: `irwp_v15_firmware.ino`
- **Releases**: `irwp_v15_[platform]_[date].hex/.bin`

### Build Instructions
- Arduino IDE: Select board, compile, upload
- PlatformIO: `pio run -e [platform]`
- All dependencies: Adafruit MPU6050, ArduinoJson

### Backward Compatibility
- Serial command API unchanged from v1.0
- Pattern library expanded (12 total)
- Status JSON **extended** (additive changes)
- LED counts now configurable (was hard-coded)

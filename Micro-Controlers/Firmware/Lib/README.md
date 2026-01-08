# IRWP - Infrared Wear Project
## Multi-Platform Camera Countermeasure Firmware

### Overview
Complete firmware for a wearable IR LED system designed to disrupt surveillance cameras through sensor saturation and automated flicker patterns.
Supports 40 high-power IR LEDs across four garment zones with hardware safety interlocks.

---

### ✅ Supported Platforms
| Platform | Board Selection | Status |
|----------|----------------|--------|
| **ESP32 DevKit C** | `Tools → Board → ESP32 Dev Module` | Full PWM + WiFi disabled |
| **Raspberry Pi Pico** | `Tools → Board → Raspberry Pi Pico` | Native support |
| **Arduino Nano (ATmega328P)** | `Tools → Board → Arduino Nano` | Limited PWM resolution |
| **STM32F1 (Blue Pill)** | `Tools → Board → Generic STM32F1 series` | RTC support |

---

### 🔧 Hardware Requirements

**Core Components:**
- Microcontroller (ESP32/Pico/Nano/STM32)
- **40x 5mm IR LEDs:**
  - 8x 850nm (Hat, forward-facing)
  - 16x 940nm (Hoodie, surround)
  - 12x 850nm (Pants, low-angle)  
  - 4x 940nm (Shoes, toe caps)
- **LED Driver:** TIP120/TIP122 transistors or MOSFETs (30mA per LED)
- **Sensors:** Adafruit MPU-6050 (motion detection)
- **Safety:** NC momentary switch + emergency stop button

**Power Requirements:**
- **Max Current:** 1.2A @ 12V (14.4W total)
- **Suggested Supply:** 3S LiPo (11.1V) or 12V DC buck converter
- **Relay:** 5V-rated power relay for main LED circuit

---

### 📌 Pinout Mappings

**Universal Pin Assignments:**
| Function | Pin | Hardware |
|----------|-----|----------|
| Hat LEDs | 25 | PWM Channel 1 |
| Hoodie LEDs | 26 | PWM Channel 2 |
| Pants LEDs | 27 | PWM Channel 3 |
| Shoes LEDs | 14 | PWM Channel 4 |
| Safety Switch | 12 | INPUT_PULLUP (NC switch) |
| Emergency Stop | 13 | Interrupt (FALLING) |
| Power Relay | 10 | Active HIGH |
| Status LED | 2 | Blink = Emergency |

**Platform-Specific Notes:**
- **ESP32:** Hardware PWM (38kHz carrier, 8-bit resolution)
- **Pico/Arduino:** `analogWrite()` (software PWM)
- **STM32:** Hardware PWM on timer channels

---

### ⚙️ Build Instructions

#### Arduino IDE Method:
1. Install board packages:
   - ESP32: `Tools → Board → Board Manager → esp32`
   - Pico: `Tools → Board → Board Manager → RP2040`
2. Install Adafruit MPU6050 library
3. Open `IRWP_Firmware.ino`
4. Select correct board
5. Upload

#### PlatformIO (Recommended for multi-platform):
```bash
# Clone repository
git clone [https://github.com/BGGremlin-Group/IR-wear-Project/main/Micro-Controlers/Firmware.git]
cd IR-wear-Project

# Build for specific platform
pio run -e esp32dev
pio run -e pico
pio run -e nanoatmega328
```

---

🎮 Serial Command Interface

Baud Rate: 115200

Command	Response	Description	
`ARM`	`ACK_ARMED`	Enable system (requires safety switch ON)	
`DISARM`	`ACK_DISARMED`	Immediate shutdown	
`START_CYCLE`	`CYCLE_STARTED`	Begin active pattern	
`STOP_CYCLE`	`CYCLE_STOPPED`	Pause cycle (stay armed)	
`LOAD_PATTERN:X`	`PATTERN_LOADED:name`	Load attack pattern (0-11)	
`GET_STATUS`	JSON status	System state report	
`EMERGENCY`	`EMERGENCY_STOPPED`	Hardware halt	

Status JSON Format:

```json
{
  "state": 0,
  "safety": true,
  "armed": false,
  "cycle": 0,
  "platform": "ESP32",
  "emergency": false,
  "led_power_w": 14.4
}
```

---

⚡ Attack Pattern Library

Pre-loaded Patterns (12):
1. AGC_Lock_5_Second - Rapid brightness oscillation
2. Sensor_Saturation_Blast - Continuous full power
3. Rolling_Shutter_Tear - Flicker at camera readout frequency
4. Face_Dazzle_Biometric_Block - Hoodie-focused dazzle
5. People_Count_Injection - Multi-zone spoofing
6. PTZ_Overflow_Jam - Pan-tilt-zoom tracker jamming
7. ALPR_Character_Corrupt - License plate reader attack
8. Heat_Map_Poison_Zone - Thermal camera spoofing
9. Queue_Length_Spoof - Retail analytics disruption
10. Parking_Blind_Spot - Long-duration saturation
11. SelfCheckout_Vision_Block - Checkout counter blocking
12. Inventory_Tracking_Mask - Warehouse system confusion

---

⚠️ CRITICAL SAFETY WARNINGS

⚡ ELECTRICAL SAFETY:
- High-power IR LEDs can cause eye damage at close range
- ALWAYS wear IR-blocker safety glasses during testing
- Verify current limiting resistors (≈150Ω per LED @ 12V)
- Use thermal management - LEDs generate heat at max duty cycle
- Off switch should be accessible at all times

🔥 BURN HAZARD:
- LEDs operate at 30mA (derated from 50mA max)
- Garments can reach 50°C+ during extended use
- Test thermal performance before wearable deployment
- Always insulate and weatherproof integrated circuits

🛑 LEGAL WARNING:
- We are not your nanny 
- User assumes full legal responsibility
- We neither endorse the use nor misuse of our products
---

📊 Technical Specifications

- IR Wavelengths: 850nm (semi-covert), 940nm (covert)
- PWM Frequencies: 38kHz carrier (ESP32), 490Hz (Arduino)
- Sensor Range: MPU6050 ±8g, ±500°/s
- Response Time: <10ms emergency stop
- Memory: Pattern storage in PROGMEM (16KB)
- Boot Time: <500ms to armed state

---

🤝 Contributing

1. Fork repository
2. Create feature branch (`git checkout -b feature/new-pattern`)
3. Test on physical hardware
4. Submit pull request with thermal test data

---

📄 License
MIT License - See LICENSE file

WE'RE NOT YOUR NANNY. USE AT YOUR OWN RISK. HARDWARE MAY BE HAZARDOUS.

---

Firmware Version: 1.0

Last Updated: 2026

Author: [Background Gremlin Group]

Repository: `https://github.com/BGGremlin-Group/IR-wear-Project/main/Micro-Controlers/Firmware`

```

---

### **Critical Additions to Make:**

1. **Add this near the emergency switch:**
```cpp
// Hardware Safety Note: Emergency pin MUST be connected to 
// normally-closed (NC) button that opens on press
```

2. In code, add thermal protection:

```cpp
// TODO: Add TMP36 temp sensor on A0 for thermal shutdown
if (tempC > 60.0) emergencyHandler();
```
## - BGGG - *IR Wear Project Team*

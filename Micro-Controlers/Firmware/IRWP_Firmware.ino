/*
 * irwp_v25_complete_firmware.ino
 * Infrared Wear Project - Complete Technical Reference
 * Platforms: ESP32 DevKit C / Raspberry Pi Pico / Arduino Nano / STM32
 */

#if defined(ESP32)
  #include <esp32-hal-ledc.h>
  #define PLATFORM "ESP32"
  #define PWM_CHANNEL 0
  #define PWM_RESOLUTION 8
  #define EEPROM_SIZE 512
#elif defined(ARDUINO_RASPBERRY_PI_PICO)
  #include <EEPROM.h>
  #define PLATFORM "PICO"
  #define EEPROM_SIZE 512
#elif defined(STM32F1)
  #include <STM32RTC.h>
  #define PLATFORM "STM32"
  #define EEPROM_SIZE 1024
#else
  #include <EEPROM.h>
  #define PLATFORM "ARDUINO"
  #define EEPROM_SIZE 1024
#endif

#include <Wire.h>
#include <Adafruit_MPU6050.h>

// ===== HARDWARE PIN DEFINITIONS =====
#define HAT_PIN    25          // 8x 850nm LEDs (forward-facing)
#define HOODIE_PIN 26          // 16x 940nm LEDs (surround)
#define PANTS_PIN  27          // 12x 850nm LEDs (low-angle)
#define SHOES_PIN  14          // 4x 940nm LEDs (toe caps)
#define SAFETY_PIN 12          // Safety switch input (active LOW)
#define EMERGENCY_PIN 13       // Emergency stop interrupt
#define RELAY_PIN  10          // Power relay control
#define STATUS_LED_PIN 2       // Status indicator

// ===== 5MM LED SPECIFICATIONS =====
#define LED_COUNT_HAT 8
#define LED_COUNT_HOODIE 16
#define LED_COUNT_PANTS 12
#define LED_COUNT_SHOES 4
#define LED_COUNT_TOTAL 40
#define LED_CURRENT_MA 30      // Derated for thermal management
#define LED_FORWARD_VOLTAGE 1.5
#define TOTAL_CURRENT_A ((LED_COUNT_TOTAL * LED_CURRENT_MA) / 1000.0)

// ===== SYSTEM STATE =====
enum SystemState {
  STATE_IDLE = 0,
  STATE_ARMED = 1,
  STATE_CYCLING = 2,
  STATE_EMERGENCY = 99
};

SystemState currentState = STATE_IDLE;
bool safetyEngaged = false;
bool emergencyTriggered = false;

// ===== ATTACK DATA STRUCTURES =====
struct AttackPhase {
  uint8_t ledGroup;      // 0=hat,1=hoodie,2=pants,3=shoes,4=all,5=flicker
  uint16_t durationMs;
  uint8_t intensity;
  uint8_t jitterPercent;
};

struct AttackPattern {
  char name[48];
  uint8_t phaseCount;
  AttackPhase phases[20];
  uint8_t repeatCount;
  bool enabled;
};

// ===== COMPLETE ATTACK PATTERN LIBRARY =====
const AttackPattern PROVEN_ATTACKS[] PROGMEM = {
  {
    "AGC_Lock_5_Second", 9,
    {{4,50,255,0},{4,50,0,0},{4,50,255,0},{4,50,0,0},
     {4,50,255,0},{4,50,0,0},{4,50,255,0},{4,50,0,0},
     {4,5000,255,0}}, 1, true
  },
  {
    "Sensor_Saturation_Blast", 1,
    {{4,60000,255,5}}, 1, true
  },
  {
    "Rolling_Shutter_Tear", 3,
    {{5,100,200,5}}, 10, true
  },
  {
    "Face_Dazzle_Biometric_Block", 1,
    {{1,5000,255,0}}, 6, true
  },
  {
    "People_Count_Injection", 3,
    {{0,200,180,10},{1,300,180,10},{2,250,180,10}}, 2, true
  },
  {
    "PTZ_Overflow_Jam", 4,
    {{0,100,200,5},{1,100,200,5},{2,100,200,5},{3,100,200,5}}, 20, true
  },
  {
    "ALPR_Character_Corrupt", 1,
    {{0,500,220,0}}, 1, true
  },
  {
    "Heat_Map_Poison_Zone", 1,
    {{4,10000,160,15}}, 3, true
  },
  {
    "Queue_Length_Spoof", 1,
    {{1,5000,160,10}}, 2, true
  },
  {
    "Parking_Blind_Spot", 1,
    {{4,30000,255,5}}, 1, true
  },
  {
    "SelfCheckout_Vision_Block", 1,
    {{0,2000,200,0}}, 4, true
  },
  {
    "Inventory_Tracking_Mask", 2,
    {{2,500,180,20},{3,500,180,20}}, 5, true
  }
};

#define PATTERN_COUNT (sizeof(PROVEN_ATTACKS) / sizeof(AttackPattern))

// ===== GLOBAL STATE =====
AttackPattern currentPattern;
uint32_t cycleStartTime = 0;
uint8_t currentPhaseIndex = 0;
uint32_t globalCycleCount = 0;

// ===== SENSOR INTEGRATION =====
Adafruit_MPU6050 mpu;

void setup() {
  Serial.begin(115200);
  Serial.println(ASCII_BANNER);
  
  // Pin configuration
  pinMode(SAFETY_PIN, INPUT_PULLUP);
  pinMode(EMERGENCY_PIN, INPUT_PULLUP);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  attachInterrupt(digitalPinToInterrupt(EMERGENCY_PIN), emergencyISR, FALLING);
  
  pinMode(HAT_PIN, OUTPUT);
  pinMode(HOODIE_PIN, OUTPUT);
  pinMode(PANTS_PIN, OUTPUT);
  pinMode(SHOES_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  
  // Platform-specific initialization
  #ifdef ESP32
    ledcSetup(PWM_CHANNEL, 38000, PWM_RESOLUTION);
    EEPROM.begin(EEPROM_SIZE);
    WiFi.mode(WIFI_OFF);
    btStop();
  #else
    EEPROM.begin(EEPROM_SIZE);
  #endif
  
  // Sensor initialization
  if (mpu.begin()) {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  }
  
  digitalWrite(STATUS_LED_PIN, LOW);
  Serial.println("IRWP v2.5 Initialization Complete");
  Serial.print("Platform: "); Serial.println(PLATFORM);
  Serial.print("Total LEDs: "); Serial.println(LED_COUNT_TOTAL);
  Serial.print("Max Current: "); Serial.print(TOTAL_CURRENT_A); Serial.println("A");
}

void loop() {
  safetyEngaged = (digitalRead(SAFETY_PIN) == LOW);
  
  if (emergencyTriggered || !safetyEngaged) {
    if (currentState != STATE_IDLE) emergencyHandler();
    return;
  }
  
  processSerialCommand();
  processAutonomousCycle();
  updateMotionTracking();
  
  delay(1);
}

void processSerialCommand() {
  if (!Serial.available()) return;
  
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  
  if (cmd == "ARM") {
    currentState = STATE_ARMED;
    Serial.println("ACK_ARMED");
  } else if (cmd == "DISARM") {
    currentState = STATE_IDLE;
    allLEDsOff();
    Serial.println("ACK_DISARMED");
  } else if (cmd == "START_CYCLE") {
    if (currentState == STATE_ARMED) {
      currentState = STATE_CYCLING;
      currentPhaseIndex = 0;
      cycleStartTime = millis();
      Serial.println("CYCLE_STARTED");
    }
  } else if (cmd == "STOP_CYCLE") {
    currentState = STATE_ARMED;
    Serial.println("CYCLE_STOPPED");
  } else if (cmd.startsWith("LOAD_PATTERN:")) {
    uint8_t idx = cmd.substring(13).toInt();
    if (idx < PATTERN_COUNT) {
      memcpy_P(&currentPattern, &PROVEN_ATTACKS[idx], sizeof(AttackPattern));
      Serial.print("PATTERN_LOADED:"); Serial.println(currentPattern.name);
    }
  } else if (cmd == "GET_STATUS") {
    sendStatusJson();
  } else if (cmd == "EMERGENCY") {
    emergencyHandler();
  }
}

void processAutonomousCycle() {
  if (currentState != STATE_CYCLING) return;
  
  unsigned long now = millis();
  if (now - cycleStartTime >= currentPattern.phases[currentPhaseIndex].durationMs) {
    executeCurrentPhase();
    currentPhaseIndex++;
    
    if (currentPhaseIndex >= currentPattern.phaseCount) {
      currentPhaseIndex = 0;
      globalCycleCount++;
      Serial.print("CYCLE_COMPLETE:"); Serial.println(globalCycleCount);
    }
    
    cycleStartTime = now;
  }
}

void executeCurrentPhase() {
  AttackPhase phase = currentPattern.phases[currentPhaseIndex];
  uint32_t jitteredDuration = phase.durationMs * 
    (100 + random(-phase.jitterPercent, phase.jitterPercent)) / 100;
  
  digitalWrite(RELAY_PIN, HIGH);
  setLEDGroup(phase.ledGroup, phase.intensity);
  delay(jitteredDuration);
  
  if (currentPhaseIndex == currentPattern.phaseCount - 1) {
    allLEDsOff();
    digitalWrite(RELAY_PIN, LOW);
  }
}

void setLEDGroup(uint8_t group, uint8_t intensity) {
  switch(group) {
    case 0: setPWM(HAT_PIN, intensity); break;
    case 1: setPWM(HOODIE_PIN, intensity); break;
    case 2: setPWM(PANTS_PIN, intensity); break;
    case 3: setPWM(SHOES_PIN, intensity); break;
    case 4:
      setPWM(HAT_PIN, intensity);
      setPWM(HOODIE_PIN, intensity);
      setPWM(PANTS_PIN, intensity);
      setPWM(SHOES_PIN, intensity);
      break;
    case 5: flickerAll(intensity); break;
  }
}

void setPWM(uint8_t pin, uint8_t intensity) {
  #ifdef ESP32
    ledcAttachPin(pin, PWM_CHANNEL);
    ledcWrite(PWM_CHANNEL, intensity);
  #else
    analogWrite(pin, intensity);
  #endif
}

void flickerAll(uint8_t intensity) {
  for(uint8_t i = 0; i < 60; i++) {
    digitalWrite(HAT_PIN, (i % 2) * intensity);
    digitalWrite(HOODIE_PIN, ((i + 1) % 2) * intensity);
    digitalWrite(PANTS_PIN, ((i + 2) % 2) * intensity);
    digitalWrite(SHOES_PIN, ((i + 3) % 2) * intensity);
    delayMicroseconds(800);
  }
}

void allLEDsOff() {
  digitalWrite(HAT_PIN, LOW);
  digitalWrite(HOODIE_PIN, LOW);
  digitalWrite(PANTS_PIN, LOW);
  digitalWrite(SHOES_PIN, LOW);
  digitalWrite(RELAY_PIN, LOW);
}

void emergencyISR() {
  emergencyTriggered = true;
}

void emergencyHandler() {
  currentState = STATE_EMERGENCY;
  allLEDsOff();
  #ifdef ESP32
    ledcDetachPin(HAT_PIN);
    ledcDetachPin(HOODIE_PIN);
    ledcDetachPin(PANTS_PIN);
    ledcDetachPin(SHOES_PIN);
  #endif
  Serial.println("EMERGENCY_STOPPED");
  digitalWrite(STATUS_LED_PIN, HIGH);
  while(1) {
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    delay(100);
  }
}

void updateMotionTracking() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  float accel = sqrt(a.acceleration.x * a.acceleration.x + 
                     a.acceleration.y * a.acceleration.y + 
                     a.acceleration.z * a.acceleration.z);
  if (accel > 20.0 && currentState == STATE_ARMED) {
    Serial.println("MOTION_DETECTED_HIGH");
  }
}

void sendStatusJson() {
  StaticJsonDocument<256> doc;
  doc["state"] = currentState;
  doc["safety"] = safetyEngaged;
  doc["armed"] = (currentState != STATE_IDLE);
  doc["cycle"] = globalCycleCount;
  doc["platform"] = PLATFORM;
  doc["emergency"] = emergencyTriggered;
  doc["led_power_w"] = TOTAL_CURRENT_A * 12.0;
  serializeJson(doc, Serial);
  Serial.println();
}

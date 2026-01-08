/*
 * IRWP_FirmwareV1.2.ino
 * IR Wear Project v1.2 - Multi-Platform Countermeasure System
 * Supports: ESP32 DevKit C, Raspberry Pi Pico, Arduino Nano, STM32F1
 */

// ===== PLATFORM-SPECIFIC INCLUDES =====
#if defined(ESP32)
  #include <esp32-hal-ledc.h>
  #include <WiFi.h>
  #include <BluetoothSerial.h>
  #define PLATFORM "ESP32"
  #define EEPROM_SIZE 512
#elif defined(ARDUINO_RASPBERRY_PI_PICO)
  #include <EEPROM.h>
  #define PLATFORM "PICO"
  #define EEPROM_SIZE 512
#elif defined(STM32F1xx)
  #include <STM32RTC.h>
  #define PLATFORM "STM32"
  #define EEPROM_SIZE 1024
#else  // Arduino Nano/UNO
  #include <EEPROM.h>
  #define PLATFORM "ARDUINO"
  #define EEPROM_SIZE 1024
#endif

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <ArduinoJson.h>

// ===== PIN DEFINITIONS =====
#define HAT_PIN        25
#define HOODIE_PIN     26
#define PANTS_PIN      27
#define SHOES_PIN      14
#define SAFETY_PIN     12     // NC switch (ACTIVE LOW)
#define EMERGENCY_PIN  13     // NO switch (FALLING edge)
#define RELAY_PIN      10
#define STATUS_LED_PIN 2
#define TEMP_PIN       A0     // TMP36 analog temp sensor

// ===== LED SPECIFICATIONS =====
#define LED_COUNT_HAT      8
#define LED_COUNT_HOODIE  16
#define LED_COUNT_PANTS   12
#define LED_COUNT_SHOES    4
#define LED_COUNT_TOTAL   40
#define LED_CURRENT_MA    50   // Derated from 100mA max
#define TOTAL_CURRENT_A   ((LED_COUNT_TOTAL * LED_CURRENT_MA) / 1000.0)

// ===== SAFETY THRESHOLDS =====
#define OVERHEAT_TEMP_C     60.0
#define MOTION_THRESHOLD_G  20.0

// ===== EEPROM ADDRESSES =====
#define EEPROM_ADDR_TARGET   0
#define EEPROM_ADDR_PATTERN  128

// ===== SYSTEM STATES =====
enum SystemState {
  STATE_IDLE = 0,
  STATE_ARMED = 1,
  STATE_CYCLING = 2,
  STATE_EMERGENCY = 99,
  STATE_OVERHEATED = 98
};

SystemState currentState = STATE_IDLE;
bool safetyEngaged = false;
volatile bool emergencyTriggered = false;

// ===== DATA STRUCTURES =====
struct AttackPhase {
  uint8_t ledGroup;      // 0-3=zones, 4=all, 5=flicker
  uint16_t durationMs;
  uint8_t intensity;     // 0-255
  uint8_t jitterPercent; // 0-100
};

struct AttackPattern {
  char name[48];
  uint8_t phaseCount;
  AttackPhase phases[20];
  uint8_t repeatCount;
  bool enabled;
};

struct TargetStore {
  char name[32];
  uint8_t cameraModels[15];
  bool hasALPR;
  bool hasAnalytics;
  bool isWireless;
};

// ===== ATTACK PATTERN LIBRARY (FLASH) =====
const AttackPattern PROVEN_PATTERNS[] PROGMEM = {
  { "AGC_Lock_5_Second", 9,
    {{4,50,255,0},{4,50,0,0},{4,50,255,0},{4,50,0,0},
     {4,50,255,0},{4,50,0,0},{4,50,255,0},{4,50,0,0},
     {4,5000,255,0}}, 1, true },
  { "Sensor_Saturation_Blast", 1,
    {{4,60000,255,5}}, 1, true },
  { "Rolling_Shutter_Flicker", 1,
    {{5,100,200,5}}, 3, true },
  { "Face_Dazzle_Anti_Biometric", 1,
    {{1,3000,255,0}}, 5, true },
  { "People_Count_Spoof", 3,
    {{0,200,180,10},{1,300,180,10},{2,250,180,10}}, 2, true },
  { "PTZ_Overflow_Jam", 4,
    {{0,100,200,5},{1,100,200,5},{2,100,200,5},{3,100,200,5}}, 20, true },
  { "ALPR_Character_Corrupt", 1,
    {{0,500,220,0}}, 1, true },
  { "Heat_Map_Poison_Zone", 1,
    {{4,10000,160,15}}, 3, true },
  { "Queue_Length_Spoof", 1,
    {{1,5000,160,10}}, 2, true },
  { "Parking_Blind_Spot", 1,
    {{4,30000,255,5}}, 1, true },
  { "SelfCheckout_Vision_Block", 1,
    {{0,2000,200,0}}, 4, true },
  { "Inventory_Tracking_Mask", 2,
    {{2,500,180,20},{3,500,180,20}}, 5, true }
};

#define PATTERN_COUNT (sizeof(PROVEN_PATTERNS) / sizeof(AttackPattern))

// ===== GLOBAL STATE =====
TargetStore currentTarget;
AttackPattern currentPattern;
uint8_t currentPhaseIndex = 0;
uint32_t cycleStartTime = 0;
uint32_t globalCycleCount = 0;
uint32_t lastTempCheck = 0;

// ===== HARDWARE OBJECTS =====
Adafruit_MPU6050 mpu;

#if defined(ESP32)
  BluetoothSerial SerialBT;
  #define PWM_CHANNEL_HAT    0
  #define PWM_CHANNEL_HOODIE 1
  #define PWM_CHANNEL_PANTS  2
  #define PWM_CHANNEL_SHOES  3
#endif

// ===== FORWARD DECLARATIONS =====
void saveConfiguration();
void loadConfiguration();
float readTemperature();
void emergencyHandler();

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(100);
  
  // Pin initialization
  pinMode(SAFETY_PIN, INPUT_PULLUP);
  pinMode(EMERGENCY_PIN, INPUT_PULLUP);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(STATUS_LED_PIN, LOW);
  
  attachInterrupt(digitalPinToInterrupt(EMERGENCY_PIN), emergencyISR, FALLING);
  
  // LED pins
  pinMode(HAT_PIN, OUTPUT);
  pinMode(HOODIE_PIN, OUTPUT);
  pinMode(PANTS_PIN, OUTPUT);
  pinMode(SHOES_PIN, OUTPUT);
  
  // Platform-specific setup
  #ifdef ESP32
    ledcSetup(PWM_CHANNEL_HAT, 38000, 8);
    ledcSetup(PWM_CHANNEL_HOODIE, 38000, 8);
    ledcSetup(PWM_CHANNEL_PANTS, 38000, 8);
    ledcSetup(PWM_CHANNEL_SHOES, 38000, 8);
    EEPROM.begin(EEPROM_SIZE);
    WiFi.mode(WIFI_OFF);
    btStop();
    SerialBT.begin("IRWP_v25");
  #else
    EEPROM.begin(EEPROM_SIZE);
  #endif
  
  // Initialize MPU6050
  if (!mpu.begin()) {
    Serial.println("MPU6050_INIT_FAILED");
  } else {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    Serial.println("MPU6050_INITIALIZED");
  }
  
  // Load saved configuration
  loadConfiguration();
  
  // Status message
  Serial.println("\n=====================================");
  Serial.println("IRWP v1.2 - Initialization Complete");
  Serial.println("=====================================");
  Serial.print("Platform: "); Serial.println(PLATFORM);
  Serial.print("LED Count: "); Serial.println(LED_COUNT_TOTAL);
  Serial.print("Max Current: "); Serial.print(TOTAL_CURRENT_A); Serial.println("A");
  Serial.print("EEPROM Size: "); Serial.println(EEPROM_SIZE);
  Serial.print("Safety: "); Serial.println(safetyEngaged ? "ENGAGED" : "DISENGAGED");
}

// ===== MAIN LOOP =====
void loop() {
  safetyEngaged = (digitalRead(SAFETY_PIN) == LOW);
  
  // Thermal protection (check every 1 second)
  if (millis() - lastTempCheck >= 1000) {
    float temp = readTemperature();
    if (temp > OVERHEAT_TEMP_C) {
      overheating = true;
      emergencyTriggered = true;
      Serial.print("THERMAL_SHUTDOWN:"); Serial.println(temp);
    }
    lastTempCheck = millis();
  }
  
  // Safety monitor
  if (emergencyTriggered || !safetyEngaged) {
    if (currentState != STATE_EMERGENCY && currentState != STATE_OVERHEATED) {
      emergencyHandler();
    }
    return;
  }
  
  // Command processors
  #ifdef ESP32
    if (SerialBT.available()) {
      String btCmd = SerialBT.readStringUntil('\n');
      btCmd.trim();
      processCommand(btCmd);
    }
  #endif
  
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    processCommand(cmd);
  }
  
  // Main processes
  processAutonomousCycle();
  updateMotionTracking();
  
  delay(1);
}

// ===== COMMAND PROCESSING =====
void processCommand(String cmd) {
  if (cmd == "ARM") {
    if (!safetyEngaged) {
      Serial.println("ERROR_SAFETY_NOT_ENGAGED");
      return;
    }
    currentState = STATE_ARMED;
    saveConfiguration();
    Serial.println("ACK_ARMED");
  } 
  else if (cmd == "DISARM") {
    currentState = STATE_IDLE;
    allLEDsOff();
    saveConfiguration();
    Serial.println("ACK_DISARMED");
  } 
  else if (cmd == "START_CYCLE") {
    if (currentState == STATE_ARMED) {
      currentState = STATE_CYCLING;
      currentPhaseIndex = 0;
      cycleStartTime = millis();
      Serial.println("CYCLE_STARTED");
    } else {
      Serial.println("ERROR_NOT_ARMED");
    }
  } 
  else if (cmd == "STOP_CYCLE") {
    if (currentState == STATE_CYCLING) {
      currentState = STATE_ARMED;
      allLEDsOff();
      Serial.println("CYCLE_STOPPED");
    }
  } 
  else if (cmd.startsWith("LOAD_PATTERN:")) {
    uint8_t idx = cmd.substring(13).toInt();
    if (idx < PATTERN_COUNT) {
      memcpy_P(&currentPattern, &PROVEN_PATTERNS[idx], sizeof(AttackPattern));
      saveConfiguration();
      Serial.print("PATTERN_LOADED:"); Serial.println(currentPattern.name);
    } else {
      Serial.println("ERROR_INVALID_PATTERN");
    }
  } 
  else if (cmd.startsWith("SET_TARGET:")) {
    String targetName = cmd.substring(11);
    targetName.toCharArray(currentTarget.name, 32);
    saveConfiguration();
    Serial.print("TARGET_SET:"); Serial.println(currentTarget.name);
  } 
  else if (cmd == "GET_STATUS") {
    sendStatusJson();
  } 
  else if (cmd == "EMERGENCY") {
    emergencyHandler();
  } 
  else if (cmd == "FACTORY_RESET") {
    for (int i = 0; i < EEPROM_SIZE; i++) {
      EEPROM.write(i, 0);
    }
    #ifdef ESP32
      EEPROM.commit();
    #endif
    Serial.println("EEPROM_CLEARED_RESET_REQUIRED");
  }
}

// ===== CYCLE ENGINE =====
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
  
  // Apply timing jitter
  uint32_t jitterRange = (phase.durationMs * phase.jitterPercent) / 100;
  uint32_t jitteredDuration = phase.durationMs + random(-jitterRange, jitterRange);
  
  setLEDGroup(phase.ledGroup, phase.intensity);
  delay(jitteredDuration);
}

void setLEDGroup(uint8_t group, uint8_t intensity) {
  digitalWrite(RELAY_PIN, HIGH); // Enable power relay
  
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
    default: allLEDsOff(); break;
  }
}

void setPWM(uint8_t pin, uint8_t intensity) {
  #ifdef ESP32
    // Map pins to channels
    uint8_t channel;
    if (pin == HAT_PIN) channel = PWM_CHANNEL_HAT;
    else if (pin == HOODIE_PIN) channel = PWM_CHANNEL_HOODIE;
    else if (pin == PANTS_PIN) channel = PWM_CHANNEL_PANTS;
    else if (pin == SHOES_PIN) channel = PWM_CHANNEL_SHOES;
    else return;
    
    ledcAttachPin(pin, channel);
    ledcWrite(channel, intensity);
  #else
    analogWrite(pin, intensity);
  #endif
}

void flickerAll(uint8_t intensity) {
  // 50Hz asymmetric flicker (camera sensor stress)
  for(uint8_t i = 0; i < 60; i++) {
    uint8_t state = (i % 2) ? intensity : 0;
    digitalWrite(HAT_PIN, state);
    digitalWrite(HOODIE_PIN, state);
    digitalWrite(PANTS_PIN, state);
    digitalWrite(SHOES_PIN, state);
    delayMicroseconds(800);
  }
}

void allLEDsOff() {
  digitalWrite(HAT_PIN, LOW);
  digitalWrite(HOODIE_PIN, LOW);
  digitalWrite(PANTS_PIN, LOW);
  digitalWrite(SHOES_PIN, LOW);
  digitalWrite(RELAY_PIN, LOW); // Cut power to LED circuit
}

// ===== SAFETY SYSTEM =====
void emergencyISR() {
  emergencyTriggered = true;
}

void emergencyHandler() {
  // Save configuration before shutdown
  saveConfiguration();
  
  currentState = emergencyTriggered ? STATE_EMERGENCY : STATE_OVERHEATED;
  allLEDsOff();
  
  #ifdef ESP32
    ledcDetachPin(HAT_PIN);
    ledcDetachPin(HOODIE_PIN);
    ledcDetachPin(PANTS_PIN);
    ledcDetachPin(SHOES_PIN);
  #endif
  
  // Log emergency reason
  Serial.print("EMERGENCY_REASON:");
  if (emergencyTriggered) Serial.println("EMERGENCY_SWITCH");
  else if (!safetyEngaged) Serial.println("SAFETY_DISENGAGED");
  else if (overheating) Serial.println("OVERHEATING");
  
  // Halt with blinking status LED
  while(1) {
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    delay(100);
  }
}

// ===== SENSOR SYSTEM =====
void updateMotionTracking() {
  sensors_event_t a, g, temp;
  if (!mpu.getEvent(&a, &g, &temp)) return;
  
  float accel = sqrt(a.acceleration.x * a.acceleration.x + 
                     a.acceleration.y * a.acceleration.y + 
                     a.acceleration.z * a.acceleration.z);
                     
  if (accel > MOTION_THRESHOLD_G && currentState == STATE_ARMED) {
    Serial.print("MOTION_DETECTED:"); Serial.println(accel, 2);
  }
}

float readTemperature() {
  int reading = analogRead(TEMP_PIN);
  float voltage = reading * 5.0 / 1024.0;
  return (voltage - 0.5) * 100.0; // TMP36 conversion
}

// ===== STATUS REPORTING =====
void sendStatusJson() {
  StaticJsonDocument<256> doc;
  doc["state"] = currentState;
  doc["safety"] = safetyEngaged;
  doc["armed"] = (currentState != STATE_IDLE);
  doc["cycle"] = globalCycleCount;
  doc["platform"] = PLATFORM;
  doc["emergency"] = emergencyTriggered;
  doc["temperature_c"] = readTemperature();
  doc["led_power_w"] = TOTAL_CURRENT_A * 12.0;
  serializeJson(doc, Serial);
  Serial.println();
}

// ===== PERSISTENCE =====
void loadConfiguration() {
  EEPROM.get(EEPROM_ADDR_TARGET, currentTarget);
  EEPROM.get(EEPROM_ADDR_PATTERN, currentPattern);
  
  // Validate pattern data
  if (currentPattern.phaseCount == 0 || currentPattern.phaseCount > 20) {
    memcpy_P(&currentPattern, &PROVEN_PATTERNS[0], sizeof(AttackPattern));
  }
}

void saveConfiguration() {
  EEPROM.put(EEPROM_ADDR_TARGET, currentTarget);
  EEPROM.put(EEPROM_ADDR_PATTERN, currentPattern);
  
  #ifdef ESP32
    EEPROM.commit();
  #endif
}

// ASCII banner
const char* ASCII_BANNER = R"(
=====================================
 IRWP v1.2 - Infrared Wear Project
 Wearable Camera Countermeasure System
=====================================
)";

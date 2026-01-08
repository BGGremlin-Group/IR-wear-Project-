/*
 * irwp_v15_firmware.ino
 * IR Wear Project v1.5 - Wearable IR Countermeasure System
 * Monolithic Multi-Platform Firmware (ESP32 / Pico / Nano / STM32)
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

// ===== USER CONFIGURATION ZONE =====
// MODIFY THESE VALUES TO MATCH YOUR HARDWARE
#define LED_COUNT_HAT      8
#define LED_COUNT_HOODIE  16
#define LED_COUNT_PANTS   12
#define LED_COUNT_SHOES    4
#define LED_COUNT_TOTAL   (LED_COUNT_HAT + LED_COUNT_HOODIE + LED_COUNT_PANTS + LED_COUNT_SHOES)
#define LED_CURRENT_MA    50   // mA per LED (thermal derated from 100mA max)
#define TOTAL_CURRENT_A   ((LED_COUNT_TOTAL * LED_CURRENT_MA) / 1000.0)

// ===== HARDWARE PIN DEFINITIONS =====
#define HAT_PIN        25
#define HOODIE_PIN     26
#define PANTS_PIN      27
#define SHOES_PIN      14
#define SAFETY_PIN     12     // Master safety switch (ACTIVE LOW = enabled)
#define TEST_BTN_PIN   13     // Optional test momentary button (ACTIVE LOW)
#define RELAY_PIN      10     // Power relay control
#define STATUS_LED_PIN 2      // Status indicator LED
#define TEMP_PIN       A0     // TMP36 temperature sensor (optional)

// ===== EEPROM STORAGE =====
#define EEPROM_ADDR_PATTERN  0    // Store current pattern
#define EEPROM_ADDR_CONFIG   128  // Store system config

// ===== SYSTEM STATES =====
enum SystemState {
  STATE_IDLE = 0,
  STATE_ARMED = 1,
  STATE_CYCLING = 2,
  STATE_TESTMODE = 3
};

SystemState currentState = STATE_IDLE;
bool safetyEngaged = false;
bool testButtonPressed = false;
bool overheating = false;

// ===== ATTACK STRUCTURES =====
struct AttackPhase {
  uint8_t ledGroup;      // 0=hat,1=hoodie,2=pants,3=shoes,4=all,5=flicker
  uint16_t durationMs;
  uint8_t intensity;     // 0-255 PWM duty
  uint8_t jitterPercent; // 0-100% timing variation
};

struct AttackPattern {
  char name[48];
  uint8_t phaseCount;
  AttackPhase phases[20];
  uint8_t repeatCount;
  bool enabled;
};

// ===== COMPLETE ATTACK PATTERN LIBRARY (FLASH) =====
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
AttackPattern currentPattern;
uint8_t currentPhaseIndex = 0;
uint32_t cycleStartTime = 0;
uint32_t globalCycleCount = 0;
uint32_t lastTempCheck = 0;

// ===== HARDWARE OBJECTS =====
Adafruit_MPU6050 mpu;

#ifdef ESP32
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
void sendStatusJson();

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  delay(100);
  
  // Hardware pin initialization
  pinMode(SAFETY_PIN, INPUT_PULLUP);
  pinMode(TEST_BTN_PIN, INPUT_PULLUP);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  
  // Set initial states
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(STATUS_LED_PIN, HIGH); // Signal power-on
  
  // LED control pins
  pinMode(HAT_PIN, OUTPUT);
  pinMode(HOODIE_PIN, OUTPUT);
  pinMode(PANTS_PIN, OUTPUT);
  pinMode(SHOES_PIN, OUTPUT);
  
  // Platform-specific hardware PWM setup
  #ifdef ESP32
    // Hardware PWM at 38kHz (IR carrier frequency)
    ledcSetup(PWM_CHANNEL_HAT, 38000, 8);
    ledcSetup(PWM_CHANNEL_HOODIE, 38000, 8);
    ledcSetup(PWM_CHANNEL_PANTS, 38000, 8);
    ledcSetup(PWM_CHANNEL_SHOES, 38000, 8);
    EEPROM.begin(EEPROM_SIZE);
    WiFi.mode(WIFI_OFF);
    btStop();
    SerialBT.begin("IRWP_v15"); // Bluetooth command interface
  #else
    EEPROM.begin(EEPROM_SIZE);
  #endif
  
  // Initialize MPU6050 for sensor logging
  if (mpu.begin()) {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    delay(10);
  }
  
  // Load persisted configuration
  loadConfiguration();
  
  // Power-on banner
  Serial.println(F("\n====================================="));
  Serial.println(F("IRWP v1.5 - System Power ON"));
  Serial.println(F("====================================="));
  Serial.print(F("Platform: ")); Serial.println(PLATFORM);
  Serial.print(F("LED Configuration: ")); 
  Serial.print(LED_COUNT_HAT); Serial.print("/");
  Serial.print(LED_COUNT_HOODIE); Serial.print("/");
  Serial.print(LED_COUNT_PANTS); Serial.print("/");
  Serial.print(LED_COUNT_SHOES); Serial.print(" = ");
  Serial.print(LED_COUNT_TOTAL); Serial.println(F(" total"));
  Serial.print(F("Max Current: ")); Serial.print(TOTAL_CURRENT_A, 2); Serial.println(F("A"));
  Serial.print(F("Safety: "));
  Serial.println(digitalRead(SAFETY_PIN) == LOW ? F("ENABLED") : F("DISABLED"));
}

// ===== MAIN LOOP =====
void loop() {
  // Monitor safety switch (informational only, NO SHUTDOWN)
  safetyEngaged = (digitalRead(SAFETY_PIN) == LOW);
  testButtonPressed = (digitalRead(TEST_BTN_PIN) == LOW);
  
  // Thermal monitoring (informational only)
  if (millis() - lastTempCheck >= 5000) { // Check every 5 seconds
    float temp = readTemperature();
    overheating = (temp > 60.0);
    if (overheating) {
      Serial.print(F("WARNING_OVERHEATING:")); Serial.println(temp);
    }
    lastTempCheck = millis();
  }
  
  // Optional test button behavior
  if (testButtonPressed && currentState != STATE_TESTMODE) {
    currentState = STATE_TESTMODE;
    Serial.println(F("TEST_MODE_ENTERED"));
  }
  
  // Multi-interface command processing
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
  
  // Operational state machine
  if (currentState == STATE_TESTMODE) {
    runTestSequence();
  } else {
    processAutonomousCycle();
  }
  
  // Sensor data logging
  updateMotionTracking();
  
  // Status LED heartbeat
  static uint32_t lastBlink = 0;
  if (millis() - lastBlink >= 500) {
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    lastBlink = millis();
  }
  
  delay(1);
}

// ===== COMMAND PROCESSOR =====
void processCommand(String cmd) {
  // Safety state validation
  if (!safetyEngaged && cmd != "GET_STATUS") {
    Serial.println(F("ERROR_SAFETY_DISABLED"));
    return;
  }
  
  if (cmd == "ARM") {
    currentState = STATE_ARMED;
    saveConfiguration();
    Serial.println(F("ACK_ARMED"));
  } 
  else if (cmd == "DISARM") {
    currentState = STATE_IDLE;
    allLEDsOff();
    saveConfiguration();
    Serial.println(F("ACK_DISARMED"));
  } 
  else if (cmd == "START_CYCLE") {
    if (currentState == STATE_ARMED) {
      currentState = STATE_CYCLING;
      currentPhaseIndex = 0;
      cycleStartTime = millis();
      Serial.println(F("CYCLE_STARTED"));
    } else {
      Serial.println(F("ERROR_NOT_ARMED"));
    }
  } 
  else if (cmd == "STOP_CYCLE") {
    if (currentState == STATE_CYCLING || currentState == STATE_TESTMODE) {
      currentState = STATE_ARMED;
      allLEDsOff();
      Serial.println(F("CYCLE_STOPPED"));
    }
  } 
  else if (cmd.startsWith("LOAD_PATTERN:")) {
    uint8_t idx = cmd.substring(13).toInt();
    if (idx < PATTERN_COUNT) {
      memcpy_P(&currentPattern, &PROVEN_PATTERNS[idx], sizeof(AttackPattern));
      saveConfiguration();
      Serial.print(F("PATTERN_LOADED:")); Serial.println(currentPattern.name);
    } else {
      Serial.println(F("ERROR_INVALID_PATTERN"));
    }
  } 
  else if (cmd.startsWith("SET_TARGET:")) {
    String targetName = cmd.substring(11);
    targetName.toCharArray(currentTarget.name, 32);
    saveConfiguration();
    Serial.print(F("TARGET_SET:")); Serial.println(currentTarget.name);
  } 
  else if (cmd == "GET_STATUS") {
    sendStatusJson();
  } 
  else if (cmd == "FACTORY_RESET") {
    // Clear EEPROM
    for (int i = 0; i < EEPROM_SIZE; i++) {
      EEPROM.write(i, 0);
    }
    #ifdef ESP32
      EEPROM.commit();
    #endif
    Serial.println(F("EEPROM_CLEARED"));
    Serial.println(F("REBOOT_REQUIRED"));
  }
  else if (cmd == "PING") {
    Serial.println(F("PONG"));
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
      Serial.print(F("CYCLE_COMPLETE:")); Serial.println(globalCycleCount);
    }
    
    cycleStartTime = now;
  }
}

void executeCurrentPhase() {
  AttackPhase phase = currentPattern.phases[currentPhaseIndex];
  
  // Calculate jittered duration
  uint32_t jitterRange = (phase.durationMs * phase.jitterPercent) / 100;
  uint32_t jitteredDuration = phase.durationMs + random(-jitterRange, jitterRange);
  
  setLEDGroup(phase.ledGroup, phase.intensity);
  delay(jitteredDuration);
}

void runTestSequence() {
  // Test mode: cycles through each LED group for 1 second
  static uint32_t lastTestChange = 0;
  static uint8_t testGroup = 0;
  
  if (millis() - lastTestChange >= 1000) {
    allLEDsOff();
    setLEDGroup(testGroup, 128); // 50% intensity
    Serial.print(F("TEST_ACTIVE_GROUP:")); Serial.println(testGroup);
    testGroup = (testGroup + 1) % 4;
    lastTestChange = millis();
  }
}

void setLEDGroup(uint8_t group, uint8_t intensity) {
  digitalWrite(RELAY_PIN, HIGH);
  
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

// ===== PWM CONTROL =====
void setPWM(uint8_t pin, uint8_t intensity) {
  #ifdef ESP32
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
  // 38kHz flicker pattern for camera sensor stress
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
  digitalWrite(RELAY_PIN, LOW);
}

// ===== SENSOR MONITORING (INFORMATIONAL ONLY) =====
void updateMotionTracking() {
  sensors_event_t a, g, temp;
  if (!mpu.getEvent(&a, &g, &temp)) return;
  
  float accel = sqrt(a.acceleration.x * a.acceleration.x + 
                     a.acceleration.y * a.acceleration.y + 
                     a.acceleration.z * a.acceleration.z);
                     
  if (accel > 20.0) {
    Serial.print(F("MOTION_LOG_ACCEL:")); Serial.println(accel, 2);
  }
}

float readTemperature() {
  int reading = analogRead(TEMP_PIN);
  float voltage = reading * 5.0 / 1024.0;
  return (voltage - 0.5) * 100.0; // TMP36 conversion
}

void sendStatusJson() {
  StaticJsonDocument<256> doc;
  doc["version"] = "1.5";
  doc["state"] = currentState;
  doc["safety"] = safetyEngaged;
  doc["armed"] = (currentState != STATE_IDLE);
  doc["cycle"] = globalCycleCount;
  doc["platform"] = PLATFORM;
  doc["overheating"] = overheating;
  doc["temperature_c"] = readTemperature();
  doc["led_power_w"] = TOTAL_CURRENT_A * 12.0;
  doc["test_mode"] = (currentState == STATE_TESTMODE);
  serializeJson(doc, Serial);
  Serial.println();
}

// ===== PERSISTENCE =====
void loadConfiguration() {
  EEPROM.get(EEPROM_ADDR_PATTERN, currentPattern);
  if (currentPattern.phaseCount == 0 || currentPattern.phaseCount > 20) {
    memcpy_P(&currentPattern, &PROVEN_PATTERNS[0], sizeof(AttackPattern));
  }
}

void saveConfiguration() {
  EEPROM.put(EEPROM_ADDR_PATTERN, currentPattern);
  #ifdef ESP32
    EEPROM.commit();
  #endif
}

/*
 * stm32_firmware.cpp
 * IRWP v2.5 - STM32 Blue Pill Version
 * Compile with PlatformIO or Arduino IDE (STM32 core)
 */

#include <Arduino.h>
#include <EEPROM.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>

// Pin definitions (STM32 Blue Pill)
#define HAT_PIN     PA0   // PWM pin
#define HOODIE_PIN  PA1   // PWM pin
#define PANTS_PIN   PA2   // PWM pin
#define SHOES_PIN   PA3   // PWM pin
#define SAFETY_PIN  PB12
#define EMERGENCY_PIN PB13
#define RELAY_PIN   PB14
#define STATUS_LED_PIN PC13

// LED Specifications
#define LED_COUNT_TOTAL 40
#define LED_CURRENT_MA  30

// System States
enum SystemState {
  STATE_IDLE = 0,
  STATE_ARMED = 1,
  STATE_CYCLING = 2,
  STATE_EMERGENCY = 99
};

SystemState currentState = STATE_IDLE;
bool safetyEngaged = false;
volatile bool emergencyTriggered = false;

// Attack Structures
struct AttackPhase {
  uint8_t ledGroup;
  uint16_t durationMs;
  uint8_t intensity;
};

struct AttackPattern {
  char name[48];
  uint8_t phaseCount;
  AttackPhase phases[20];
  uint8_t repeatCount;
};

// Built-in Patterns
const AttackPattern PROVEN_PATTERNS[] = {
  {
    "AGC_Lock_5_Second", 9,
    {{4,50,255},{4,50,0},{4,50,255},{4,50,0},
     {4,50,255},{4,50,0},{4,50,255},{4,50,0},
     {4,5000,255}}, 1
  },
  {
    "Sensor_Saturation_Blast", 1,
    {{4,5000,255}}, 1
  },
  {
    "Rolling_Shutter_Flicker", 1,
    {{5,100,200}}, 3, true
  }
};

#define PATTERN_COUNT (sizeof(PROVEN_PATTERNS) / sizeof(AttackPattern))

// Target Storage
struct TargetStore {
  char name[32];
  uint8_t cameraModels[15];
  bool hasALPR;
  bool hasAnalytics;
  bool isWireless;
};

TargetStore currentTarget;
AttackPattern currentPattern;
uint8_t currentPhaseIndex = 0;
uint32_t cycleStartTime = 0;
uint32_t globalCycleCount = 0;

// Hardware Interfaces
Adafruit_MPU6050 mpu;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\nIRWP v2.5 STM32 Firmware");
  
  // Safety pins
  pinMode(SAFETY_PIN, INPUT_PULLUP);
  pinMode(EMERGENCY_PIN, INPUT_PULLUP);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  attachInterrupt(digitalPinToInterrupt(EMERGENCY_PIN), emergencyISR, FALLING);
  
  // LED pins (PWM)
  pinMode(HAT_PIN, OUTPUT);
  pinMode(HOODIE_PIN, OUTPUT);
  pinMode(PANTS_PIN, OUTPUT);
  pinMode(SHOES_PIN, OUTPUT);
  pinMode(STATUS_LED_PIN, OUTPUT);
  
  // Initialize MPU6050
  if (mpu.begin()) {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  }
  
  // Load EEPROM
  EEPROM.begin(512);
  EEPROM.get(0, currentTarget);
  EEPROM.get(128, currentPattern);
  
  digitalWrite(STATUS_LED_PIN, LOW);
  Serial.println("STM32 Firmware Initialized");
}

void loop() {
  safetyEngaged = (digitalRead(SAFETY_PIN) == LOW);
  
  if (emergencyTriggered || !safetyEngaged) {
    if (currentState != STATE_IDLE) emergencyHandler();
    return;
  }
  
  processSerialCommand();
  processAutonomousCycle();
  
  delay(1);
}

void processSerialCommand() {
  if (!Serial.available()) return;
  
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  processCommand(cmd);
}

void processCommand(String cmd) {
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
      memcpy(&currentPattern, &PROVEN_PATTERNS[idx], sizeof(AttackPattern));
      Serial.print("PATTERN_LOADED:"); Serial.println(currentPattern.name);
    }
  } else if (cmd.startsWith("SET_GROUP:")) {
    // Parse JSON
    int group_start = cmd.indexOf(':') + 1;
    String json_str = cmd.substring(group_start);
    int g_idx = json_str.indexOf("\"group\":");
    int i_idx = json_str.indexOf("\"intensity\":");
    if (g_idx > 0 && i_idx > 0) {
      int group = json_str.substring(g_idx+8, json_str.indexOf(',', g_idx)).toInt();
      int intensity = json_str.substring(i_idx+11, json_str.indexOf('}', i_idx)).toInt();
      setLEDGroup(group, intensity);
    }
    Serial.println("GROUP_SET");
  } else if (cmd == "EMERGENCY") {
    emergencyHandler();
  } else if (cmd == "GET_STATUS") {
    sendStatusJson();
  } else if (cmd == "IDENTIFY") {
    Serial.println("IRWP_STM32_v2.5");
  } else if (cmd == "ALL_OFF") {
    allLEDsOff();
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
  setLEDGroup(phase.ledGroup, phase.intensity);
}

void setLEDGroup(uint8_t group, uint8_t intensity) {
  digitalWrite(RELAY_PIN, HIGH);
  
  // STM32 PWM (analogWrite)
  switch(group) {
    case 0: analogWrite(HAT_PIN, intensity); break;
    case 1: analogWrite(HOODIE_PIN, intensity); break;
    case 2: analogWrite(PANTS_PIN, intensity); break;
    case 3: analogWrite(SHOES_PIN, intensity); break;
    case 4:
      analogWrite(HAT_PIN, intensity);
      analogWrite(HOODIE_PIN, intensity);
      analogWrite(PANTS_PIN, intensity);
      analogWrite(SHOES_PIN, intensity);
      break;
    case 5:
      flickerAll(intensity);
      break;
  }
}

void flickerAll(uint8_t intensity) {
  for(uint8_t i = 0; i < 50; i++) {
    digitalWrite(HAT_PIN, (i % 2) * intensity);
    digitalWrite(HOODIE_PIN, ((i + 1) % 2) * intensity);
    digitalWrite(PANTS_PIN, ((i + 2) % 2) * intensity);
    digitalWrite(SHOES_PIN, ((i + 3) % 2) * intensity);
    delayMicroseconds(500);
  }
}

void allLEDsOff() {
  digitalWrite(HAT_PIN, LOW);
  digitalWrite(HOODIE_PIN, LOW);
  digitalWrite(PANTS_PIN, LOW);
  digitalWrite(SHOES_PIN, LOW);
  digitalWrite(RELAY_PIN, LOW);
}

void emergencyHandler() {
  emergencyTriggered = true;
  currentState = STATE_EMERGENCY;
  allLEDsOff();
  
  Serial.println("EMERGENCY_STOPPED");
  digitalWrite(STATUS_LED_PIN, HIGH);
  
  // Flash LED indefinitely
  while(1) {
    digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    delay(100);
  }
}

void emergencyISR() {
  emergencyTriggered = true;
}

void sendStatusJson() {
  Serial.print("{\"state\":");
  Serial.print(currentState);
  Serial.print(",\"safety\":");
  Serial.print(safetyEngaged);
  Serial.print(",\"armed\":");
  Serial.print(currentState != STATE_IDLE);
  Serial.print(",\"cycle\":");
  Serial.print(globalCycleCount);
  Serial.print(",\"platform\":\"STM32\"}\n");
}

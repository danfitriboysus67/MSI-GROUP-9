#include <Wire.h>
#include <MPU6050.h>
#include <Servo.h>

MPU6050 mpu;
Servo accessServo;

const int redPin = 3;
const int greenPin = 4;

// State Machine Variables
int currentState = 0; 
// 0 = IDLE (Red ON, Servo at 0)
// 1 = WAITING_FOR_MOTION (Red pulsing, Servo at 0)
// 2 = UNLOCKED (Green ON, Servo at 180 for 5s)

unsigned long lastBlinkTime = 0;
bool blinkState = false;
unsigned long unlockTimer = 0;

void setup() {
  Serial.begin(9600);
  Wire.begin();
  mpu.initialize();
  
  accessServo.attach(9);
  
  pinMode(redPin, OUTPUT);
  pinMode(greenPin, OUTPUT);
  
  // Initial state: Servo at 0, only Red LED on
  accessServo.write(0);
  digitalWrite(redPin, HIGH);
  digitalWrite(greenPin, LOW);
  
  if (!mpu.testConnection()) {
    Serial.println("MPU6050 connection failed!");
    while (1);
  }
}

void loop() {
  // 1. Send motion data to Python
  int ax, ay, az, gx, gy, gz;
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  Serial.print(ax); Serial.print(",");
  Serial.print(ay); Serial.print(","); Serial.println(az);

  // 2. Listen for Serial Commands
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == 'W' && currentState == 0) {
      currentState = 1; // RFID scanned, wait for motion
    } 
    else if (cmd == 'R' && currentState == 1) {
      currentState = 2; // Rotation detected, unlock
      unlockTimer = millis();
      
      accessServo.write(180);
      digitalWrite(redPin, LOW);
      digitalWrite(greenPin, HIGH);
    }
  }

  // 3. State Machine Logic (Non-blocking)
  unsigned long currentMillis = millis();

  if (currentState == 1) {
    // Handle Red LED Pulsing (Toggle every 250ms)
    if (currentMillis - lastBlinkTime >= 250) {
      lastBlinkTime = currentMillis;
      blinkState = !blinkState;
      digitalWrite(redPin, blinkState ? HIGH : LOW);
    }
  } 
  else if (currentState == 2) {
    // 5-Second Hold Timer
    if (currentMillis - unlockTimer >= 5000) {
      currentState = 0; // Return to IDLE
      
      accessServo.write(0);
      digitalWrite(redPin, HIGH);
      digitalWrite(greenPin, LOW);
    }
  }
  
  delay(10); // Small delay to avoid serial buffer overflow
}
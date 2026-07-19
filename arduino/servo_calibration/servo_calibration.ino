/*
  eBALIK — Servo Calibration / Test Sketch
  -----------------------------------------
  Standalone sketch to isolate and recalibrate the door-flap servo,
  independent of the rest of the eBALIK firmware (no RFID, IR, LCD, buzzer).

  Wiring:
    Servo signal -> D6 (SERVO_PIN)
    Servo power  -> EXTERNAL 5V supply (NOT the Arduino 5V pin) if you were
                    seeing resets/brownouts during servo movement.
    Servo GND    -> common ground with Arduino GND.

  Usage (Serial Monitor, 115200 baud, "Newline" line ending):
    Type a number 0-180 and press Enter to move the servo to that angle.
    Type "o" to jump to the currently-defined OPEN angle.
    Type "c" to jump to the currently-defined CLOSED angle.
    Type "s" to run a slow sweep 0->180->0 (useful to watch linkage travel).

  Once you find the correct angles for your physical build, update:
    SERVO_CLOSED_ANGLE / SERVO_OPEN_ANGLE below AND in
    arduino/eBALIK_arduino/eBALIK_arduino.ino
*/

#include <Servo.h>

#define SERVO_PIN 6

// Current best-guess calibration — change these as you test
int SERVO_CLOSED_ANGLE = 10;
int SERVO_OPEN_ANGLE   = 80;

Servo shelfServo;

void setup() {
  Serial.begin(115200);
  delay(200);

  shelfServo.attach(SERVO_PIN);
  shelfServo.write(SERVO_CLOSED_ANGLE);

  Serial.println(F("=== eBALIK Servo Calibration Test ==="));
  Serial.print(F("Booted. Servo set to CLOSED angle = "));
  Serial.println(SERVO_CLOSED_ANGLE);
  Serial.println(F("Commands: [0-180]=go to angle, o=open angle, c=closed angle, s=sweep"));
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() == 0) return;

    if (input.equalsIgnoreCase("o")) {
      moveTo(SERVO_OPEN_ANGLE, "OPEN");
    } else if (input.equalsIgnoreCase("c")) {
      moveTo(SERVO_CLOSED_ANGLE, "CLOSED");
    } else if (input.equalsIgnoreCase("s")) {
      Serial.println(F("Sweeping 0 -> 180 -> 0..."));
      for (int a = 0; a <= 180; a += 5) {
        shelfServo.write(a);
        delay(60);
      }
      for (int a = 180; a >= 0; a -= 5) {
        shelfServo.write(a);
        delay(60);
      }
      Serial.println(F("Sweep done."));
    } else {
      // Try to parse as a plain angle number
      int angle = input.toInt();
      bool isNumeric = true;
      for (unsigned int i = 0; i < input.length(); i++) {
        if (!isDigit(input[i])) { isNumeric = false; break; }
      }
      if (isNumeric && angle >= 0 && angle <= 180) {
        moveTo(angle, "manual");
      } else {
        Serial.println(F("Unrecognized input. Use 0-180, 'o', 'c', or 's'."));
      }
    }
  }
}

void moveTo(int angle, const char* label) {
  shelfServo.write(angle);
  Serial.print(F("-> Moved to "));
  Serial.print(angle);
  Serial.print(F(" deg ("));
  Serial.print(label);
  Serial.println(F(")"));
}

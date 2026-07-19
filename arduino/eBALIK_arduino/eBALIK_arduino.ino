/*
  eBALIK - Book Automated Library Inventory Keeper
  Arduino Uno R3 Firmware

  Hardware:
    - MFRC522 RFID Reader (SPI)
    - SG90 Servo Motor (return slot)
    - 2x IR Obstacle Sensors (Entrance / Full Entry)
    - 16x2 I2C LCD
    - Active Buzzer
    - Green LED (return approved)
    - Red LED (return rejected)

  NOTE: The original design included a third IR sensor (Safety Obstruction
  Detection) that verified the slot was clear before closing. That sensor
  has been removed from this build. In its place, a timed LCD + buzzer
  warning (STATE_CLOSING_WARNING) gives a short heads-up before the servo
  closes. This is a mitigation, not a replacement -- it does not verify
  the slot is actually clear the way the sensor did. Pin 4 (previously
  IR_OBSTRUCTION_PIN) is unused and available if the sensor is added back
  later.

  Communication:
    Talks to the Flask backend over USB Serial (115200 baud) using a
    simple line-based text protocol. See /docs/PROTOCOL.md for the
    full spec -- update it to match the removed OBSTRUCTION messages
    below. Quick reference:

    Arduino -> PC
      RFID,<uid>                 a card was scanned
      STATUS,ENTRANCE_DETECTED   book entering the slot
      STATUS,FULL_ENTRY          book fully inside
      STATUS,SLOT_CLOSED         slot closed safely
      RETURN_SUCCESS,<uid>       full cycle completed
      RETURN_FAILED,<uid>,<reason>
      HELLO,EBALIK,<version>     sent once on boot / on "PING"

    PC -> Arduino
      VALID,<uid>       book accepted, open the slot
      INVALID,<uid>     book rejected, show error
      PING              ask the Arduino to identify itself
      RESET             force the state machine back to IDLE

  Wiring (default pins, change to match your build):
    RC522   SDA(SS)=10  SCK=13  MOSI=11  MISO=12  RST=9
    Servo   signal=6
    IR1 (entrance)     = 2
    IR2 (full entry)   = 3
    (pin 4 unused -- previously obstruction sensor)
    Buzzer             = 5
    Green LED          = 7
    Red LED            = 8
    LCD (I2C)          = SDA A4 / SCL A5, addr 0x27 (16x2)
*/

#include <LiquidCrystal_I2C.h>
#include <MFRC522.h>
#include <SPI.h>
#include <Servo.h>
#include <Wire.h>

// ---------- Pin configuration ----------
#define RFID_SS_PIN 10
#define RFID_RST_PIN 9
#define SERVO_PIN 6
#define IR_ENTRANCE_PIN 2
#define IR_FULL_ENTRY_PIN 3
#define BUZZER_PIN 5
#define LED_GREEN_PIN 7
#define LED_RED_PIN 8

// IR sensors: most obstacle modules pull LOW when they detect something.
// Flip this if your modules are active-HIGH.
#define IR_ACTIVE_STATE LOW

// Servo angles (door flap mechanism -- calibrated 2026-07-18)
// CLOSED = flap shut; OPEN = flap open so book can enter.
// Re-verify with arduino/servo_calibration/servo_calibration.ino if
// the linkage or servo mounting changes.
#define SERVO_CLOSED_ANGLE 10
#define SERVO_OPEN_ANGLE   80

// Timeouts (milliseconds)
const unsigned long RFID_VALIDATION_TIMEOUT =
    5000;                                   // waiting for VALID/INVALID from PC
const unsigned long INSERT_TIMEOUT = 15000; // waiting for book to be inserted
const unsigned long FULL_ENTRY_TIMEOUT =
    8000; // waiting for full entry after entrance detected
const unsigned long CLOSE_WARNING_MS =
    2000; // "closing shortly" warning before slot closes
const unsigned long RFID_DEBOUNCE_MS =
    3000; // ignore same tag for 3s after scan

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Servo returnSlotServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ---------- State machine ----------
enum SystemState {
  STATE_IDLE,
  STATE_AWAITING_VALIDATION,
  STATE_AWAITING_ENTRANCE,
  STATE_AWAIT_FULL_ENTRY,
  STATE_CLOSING_WARNING,
  STATE_CLOSING,
  STATE_ERROR_DISPLAY
};

SystemState currentState = STATE_IDLE;
unsigned long stateEnteredAt = 0;
unsigned long lastScanTime = 0;
String pendingUID = "";
String serialBuffer = "";

// Tracks whether the second warning pulse has fired for the current
// STATE_CLOSING_WARNING cycle, so it only fires once per cycle.
bool closingPulse2Fired = false;

void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();

  pinMode(IR_ENTRANCE_PIN, INPUT);
  pinMode(IR_FULL_ENTRY_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  digitalWrite(LED_GREEN_PIN, LOW);
  digitalWrite(LED_RED_PIN, LOW);

  returnSlotServo.attach(SERVO_PIN);
  returnSlotServo.write(SERVO_CLOSED_ANGLE);

  lcd.init();
  lcd.backlight();

  showIdleScreen();
  sendHello();
}

void loop() {
  readSerialCommands();

  switch (currentState) {
  case STATE_IDLE:
    pollForCard();
    break;

  case STATE_AWAITING_VALIDATION:
    if (millis() - stateEnteredAt > RFID_VALIDATION_TIMEOUT) {
      showError("No response", "Try again");
      blinkRed();
      sendReturnFailed(pendingUID, "PC_TIMEOUT");
      goIdleAfterDelay(1500);
    }
    break;

  case STATE_AWAITING_ENTRANCE:
    if (irTriggered(IR_ENTRANCE_PIN)) {
      Serial.println("STATUS,ENTRANCE_DETECTED");
      returnSlotServo.write(SERVO_OPEN_ANGLE);
      showMessage("Book detected", "Keep pushing...");
      currentState = STATE_AWAIT_FULL_ENTRY;
      stateEnteredAt = millis();
    } else if (millis() - stateEnteredAt > INSERT_TIMEOUT) {
      showError("Timeout", "No book inserted");
      blinkRed();
      sendReturnFailed(pendingUID, "INSERT_TIMEOUT");
      closeSlotAndReset();
    }
    break;

  case STATE_AWAIT_FULL_ENTRY:
    if (irTriggered(IR_FULL_ENTRY_PIN)) {
      Serial.println("STATUS,FULL_ENTRY");
      showMessage("Book received!", "Closing shortly");
      beepClosingPulse();
      closingPulse2Fired = false;
      currentState = STATE_CLOSING_WARNING;
      stateEnteredAt = millis();
    } else if (millis() - stateEnteredAt > FULL_ENTRY_TIMEOUT) {
      showError("Incomplete", "Book not fully in");
      blinkRed();
      sendReturnFailed(pendingUID, "INCOMPLETE_ENTRY");
      closeSlotAndReset();
    }
    break;

  case STATE_CLOSING_WARNING: {
    // Non-blocking: still services serial commands and stays responsive
    // for the full warning window instead of freezing execution.
    unsigned long elapsed = millis() - stateEnteredAt;

    // Second pulse partway through the warning window, fires once.
    if (!closingPulse2Fired && elapsed > (CLOSE_WARNING_MS / 2)) {
      beepClosingPulse();
      closingPulse2Fired = true;
    }

    if (elapsed > CLOSE_WARNING_MS) {
      currentState = STATE_CLOSING;
    }
    break;
  }

  case STATE_CLOSING:
    returnSlotServo.write(SERVO_CLOSED_ANGLE);
    Serial.println("STATUS,SLOT_CLOSED");
    Serial.print("RETURN_SUCCESS,");
    Serial.println(pendingUID);
    blinkGreen();
    beepSuccess();
    showMessage("Return success!", "Thank you.");
    goIdleAfterDelay(2000);
    break;

  case STATE_ERROR_DISPLAY:
    // handled via goIdleAfterDelay() calls
    break;
  }
}

// ---------- Card polling ----------
void pollForCard() {
  if (!rfid.PICC_IsNewCardPresent())
    return;
  if (!rfid.PICC_ReadCardSerial())
    return;

  String uid = uidToString(rfid.uid.uidByte, rfid.uid.size);

  // Debounce: ignore same UID within cooldown period
  if (uid == pendingUID && (millis() - lastScanTime) < RFID_DEBOUNCE_MS) {
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  lastScanTime = millis();
  pendingUID = uid;

  Serial.print("RFID,");
  Serial.println(uid);

  showMessage("Checking book...", uid);
  currentState = STATE_AWAITING_VALIDATION;
  stateEnteredAt = millis();

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

String uidToString(byte *buffer, byte bufferSize) {
  String result = "";
  for (byte i = 0; i < bufferSize; i++) {
    if (buffer[i] < 0x10)
      result += "0";
    result += String(buffer[i], HEX);
  }
  result.toUpperCase();
  return result;
}

// ---------- Serial command handling ----------
void readSerialCommands() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) {
        handleCommand(serialBuffer);
      }
      serialBuffer = "";
    } else if (c != '\r') {
      serialBuffer += c;
    }
  }
}

void handleCommand(String line) {
  // Expected formats: VALID,<uid> | INVALID,<uid> | PING | RESET
  int commaIndex = line.indexOf(',');
  String cmd = commaIndex == -1 ? line : line.substring(0, commaIndex);
  String arg = commaIndex == -1 ? "" : line.substring(commaIndex + 1);
  cmd.toUpperCase();

  if (cmd == "PING") {
    sendHello();
    return;
  }

  if (cmd == "RESET") {
    closeSlotAndReset();
    return;
  }

  if (currentState != STATE_AWAITING_VALIDATION) {
    // ignore validation replies that arrive out of order
    return;
  }

  if (cmd == "VALID") {
    blinkGreen();
    beepApproved();
    showMessage("Book approved", "Insert when ready");
    currentState = STATE_AWAITING_ENTRANCE;
    stateEnteredAt = millis();
  } else if (cmd == "INVALID") {
    // Parse optional reason field (e.g. INVALID,<uid>,UNKNOWN_TAG)
    int secondComma = arg.indexOf(',');
    String reason = secondComma == -1 ? "" : arg.substring(secondComma + 1);
    reason.toUpperCase();
    if (reason == "UNKNOWN_TAG") {
      showError("Tag not", "recognized");
    } else if (reason == "NOT_BORROWED") {
      showError("Book not", "checked out");
    } else if (reason == "MALFORMED_UID") {
      showError("Bad tag", "read");
    } else {
      showError("Invalid book", "Not borrowed");
    }
    blinkRed();
    beepError();
    goIdleAfterDelay(1500);
  }
}

// ---------- Slot control ----------
void openSlotForInsertion() {
  returnSlotServo.write(SERVO_OPEN_ANGLE);
  showMessage("Slot open", "Insert the book");
  currentState = STATE_AWAITING_ENTRANCE;
  stateEnteredAt = millis();
}

void closeSlotAndReset() {
  returnSlotServo.write(SERVO_CLOSED_ANGLE);
  goIdleAfterDelay(500);
}

bool irTriggered(int pin) { return digitalRead(pin) == IR_ACTIVE_STATE; }

// ---------- Non-blocking "go idle after N ms" helper ----------
unsigned long idleDelayUntil = 0;
bool waitingToGoIdle = false;

void goIdleAfterDelay(unsigned long ms) {
  currentState = STATE_ERROR_DISPLAY;
  idleDelayUntil = millis() + ms;
  waitingToGoIdle = true;
  // Busy-wait kept intentionally short and only used for feedback screens;
  // fine here because IR polling loop is not time-critical for these delays.
  while (millis() < idleDelayUntil) {
    readSerialCommands();
  }
  waitingToGoIdle = false;
  showIdleScreen();
  currentState = STATE_IDLE;
  pendingUID = "";
}

void sendReturnFailed(String uid, String reason) {
  Serial.print("RETURN_FAILED,");
  Serial.print(uid);
  Serial.print(",");
  Serial.println(reason);
}

void sendHello() { Serial.println("HELLO,EBALIK,1.0"); }

// ---------- LCD helpers ----------
void showIdleScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("eBALIK Return");
  lcd.setCursor(0, 1);
  lcd.print("Scan your book");
}

void showMessage(String line1, String line2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(line2.substring(0, 16));
}

void showError(String line1, String line2) {
  showMessage(line1, line2);
  beepError();
}

// ---------- Buzzer helpers ----------
// Each cue is deliberately distinct so it's identifiable by ear alone:
//   approved        - single short high chirp
//   success         - two-tone rising sweep
//   error           - single low buzz
//   closing warning - double mid-tone pulse (fires twice during the
//                     2s warning window before the slot closes)

void beepApproved() { tone(BUZZER_PIN, 1800, 100); }

void beepSuccess() {
  tone(BUZZER_PIN, 1500, 120);
  delay(150);
  tone(BUZZER_PIN, 2000, 150);
}

void beepError() { tone(BUZZER_PIN, 400, 300); }

void beepClosingPulse() {
  // Two quick beeps at a mid frequency -- distinct from the single-shot
  // approved chirp and the smooth success sweep. tone() with a duration
  // is non-blocking on its own, but the two beeps here are close enough
  // together that a short blocking gap between them is negligible and
  // keeps the pulse sounding tight rather than spread out.
  tone(BUZZER_PIN, 1200, 80);
  delay(120);
  tone(BUZZER_PIN, 1200, 80);
}

// ---------- LED helpers ----------
void blinkGreen() {
  digitalWrite(LED_GREEN_PIN, HIGH);
  delay(300);
  digitalWrite(LED_GREEN_PIN, LOW);
}

void blinkRed() {
  digitalWrite(LED_RED_PIN, HIGH);
  delay(300);
  digitalWrite(LED_RED_PIN, LOW);
}

/*
  eBALIK - Book Automated Library Inventory Keeper
  Arduino Uno R3 Firmware - WOKWI SIMULATION VERSION

  This is a modified version for Wokwi simulation.
  IR sensors are replaced with pushbuttons for testing.

  Hardware (Wokwi simulation):
    - MFRC522 RFID Reader (SPI)
    - SG90 Servo Motor (return slot)
    - 3x Pushbuttons (Entrance / Full Entry / Safety Obstruction)
    - 16x2 I2C LCD
    - Active Buzzer

  Button mapping:
    btn_entrance   (pin 2) - simulates IR sensor detecting book entering
    btn_fullentry  (pin 3) - simulates IR sensor confirming full entry
    btn_obstruction (pin 4) - simulates IR sensor detecting obstruction

  Communication:
    Talks to the Flask backend over USB Serial (115200 baud) using a
    simple line-based text protocol. See /docs/PROTOCOL.md for the
    full spec. Quick reference:

    Arduino -> PC
      RFID,<uid>                 a card was scanned
      STATUS,ENTRANCE_DETECTED   book entering the slot
      STATUS,FULL_ENTRY          book fully inside
      STATUS,OBSTRUCTION         obstruction seen before close
      STATUS,SLOT_CLOSED         slot closed safely
      RETURN_SUCCESS,<uid>       full cycle completed
      RETURN_FAILED,<uid>,<reason>
      HELLO,EBALIK,<version>     sent once on boot / on "PING"

    PC -> Arduino
      VALID,<uid>       book accepted, open the slot
      INVALID,<uid>     book rejected, show error
      PING              ask the Arduino to identify itself
      RESET             force the state machine back to IDLE

  Wiring (Wokwi simulation):
    RC522   SDA(SS)=10  SCK=13  MOSI=11  MISO=12  RST=9
    Servo   signal=6
    Button 1 (entrance)   = 2  (with pull-down resistor)
    Button 2 (full entry) = 3  (with pull-down resistor)
    Button 3 (obstruction)= 4  (with pull-down resistor)
    Buzzer             = 5
    LCD (I2C)          = SDA A4 / SCL A5, addr 0x27 (16x2)
*/

#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ---------- Pin configuration ----------
#define RFID_SS_PIN   10
#define RFID_RST_PIN  9
#define SERVO_PIN     6
#define IR_ENTRANCE_PIN     2
#define IR_FULL_ENTRY_PIN   3
#define IR_OBSTRUCTION_PIN  4
#define BUZZER_PIN    5

// Wokwi pushbuttons with pull-down resistors are active-HIGH.
// When button is pressed, pin reads HIGH.
// This is OPPOSITE to real IR sensors which are active-LOW.
#define IR_ACTIVE_STATE HIGH

// Servo angles
#define SERVO_CLOSED_ANGLE 0
#define SERVO_OPEN_ANGLE   90

// Timeouts (milliseconds) - shortened for faster simulation testing
const unsigned long RFID_VALIDATION_TIMEOUT = 5000;   // waiting for VALID/INVALID from PC
const unsigned long INSERT_TIMEOUT          = 15000;  // waiting for book to be inserted
const unsigned long FULL_ENTRY_TIMEOUT       = 8000;   // waiting for full entry after entrance detected
const unsigned long OBSTRUCTION_CLEAR_TIMEOUT = 10000; // waiting for hand/object to clear

MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Servo returnSlotServo;
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ---------- State machine ----------
enum SystemState {
  STATE_IDLE,
  STATE_AWAITING_VALIDATION,
  STATE_SLOT_OPEN_AWAIT_ENTRANCE,
  STATE_AWAIT_FULL_ENTRY,
  STATE_AWAIT_OBSTRUCTION_CLEAR,
  STATE_CLOSING,
  STATE_ERROR_DISPLAY
};

SystemState currentState = STATE_IDLE;
unsigned long stateEnteredAt = 0;
String pendingUID = "";
String serialBuffer = "";

void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();

  // Button inputs - using internal pull-down is handled by external resistors in diagram
  pinMode(IR_ENTRANCE_PIN, INPUT);
  pinMode(IR_FULL_ENTRY_PIN, INPUT);
  pinMode(IR_OBSTRUCTION_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  returnSlotServo.attach(SERVO_PIN);
  returnSlotServo.write(SERVO_CLOSED_ANGLE);

  lcd.init();
  lcd.backlight();

  showIdleScreen();
  sendHello();

  Serial.println("[Wokwi] eBALIK simulation ready");
  Serial.println("[Wokwi] Commands:");
  Serial.println("[Wokwi]   SIMULATE_UID,<uid>  - fake an RFID scan (e.g. SIMULATE_UID,04A1B2C3)");
  Serial.println("[Wokwi]   VALID,<uid>         - reply to scan: book accepted");
  Serial.println("[Wokwi]   INVALID,<uid>       - reply to scan: book rejected");
  Serial.println("[Wokwi]   PING                - identify Arduino");
  Serial.println("[Wokwi]   RESET               - force back to IDLE");
  Serial.println("[Wokwi] Buttons simulate IR sensors:");
  Serial.println("[Wokwi]   btn_entrance   -> book entering slot");
  Serial.println("[Wokwi]   btn_fullentry  -> book fully inserted");
  Serial.println("[Wokwi]   btn_obstruction -> hand/object blocking");
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
        sendReturnFailed(pendingUID, "PC_TIMEOUT");
        goIdleAfterDelay(1500);
      }
      break;

    case STATE_SLOT_OPEN_AWAIT_ENTRANCE:
      if (irTriggered(IR_ENTRANCE_PIN)) {
        Serial.println("STATUS,ENTRANCE_DETECTED");
        showMessage("Book detected", "Keep pushing...");
        currentState = STATE_AWAIT_FULL_ENTRY;
        stateEnteredAt = millis();
      } else if (millis() - stateEnteredAt > INSERT_TIMEOUT) {
        showError("Timeout", "No book inserted");
        sendReturnFailed(pendingUID, "INSERT_TIMEOUT");
        closeSlotAndReset();
      }
      break;

    case STATE_AWAIT_FULL_ENTRY:
      if (irTriggered(IR_FULL_ENTRY_PIN)) {
        Serial.println("STATUS,FULL_ENTRY");
        showMessage("Checking slot...", "Please wait");
        currentState = STATE_AWAIT_OBSTRUCTION_CLEAR;
        stateEnteredAt = millis();
      } else if (millis() - stateEnteredAt > FULL_ENTRY_TIMEOUT) {
        showError("Incomplete", "Book not fully in");
        sendReturnFailed(pendingUID, "INCOMPLETE_ENTRY");
        closeSlotAndReset();
      }
      break;

    case STATE_AWAIT_OBSTRUCTION_CLEAR:
      if (irTriggered(IR_OBSTRUCTION_PIN)) {
        // something (hand/object) still blocking the slot
        if (millis() - stateEnteredAt == 0 || (millis() - stateEnteredAt) % 1000 < 20) {
          Serial.println("STATUS,OBSTRUCTION");
          showMessage("Please remove", "hand from slot");
        }
        if (millis() - stateEnteredAt > OBSTRUCTION_CLEAR_TIMEOUT) {
          showError("Cancelled", "Obstruction timeout");
          sendReturnFailed(pendingUID, "OBSTRUCTION_TIMEOUT");
          goIdleAfterDelay(1500); // leave slot open, do not force-close on obstruction
        }
      } else {
        currentState = STATE_CLOSING;
      }
      break;

    case STATE_CLOSING:
      returnSlotServo.write(SERVO_CLOSED_ANGLE);
      Serial.println("STATUS,SLOT_CLOSED");
      Serial.print("RETURN_SUCCESS,");
      Serial.println(pendingUID);
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
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  String uid = uidToString(rfid.uid.uidByte, rfid.uid.size);
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
    if (buffer[i] < 0x10) result += "0";
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

  // Debug command for Wokwi: simulate an RFID scan without the physical reader
  // Usage: SIMULATE_UID,04A1B2C3
  if (cmd == "SIMULATE_UID") {
    if (arg.length() == 0) {
      Serial.println("Usage: SIMULATE_UID,<uid>");
      return;
    }
    String uid = arg;
    uid.toUpperCase();
    pendingUID = uid;

    Serial.print("RFID,");
    Serial.println(uid);

    showMessage("Checking book...", uid);
    currentState = STATE_AWAITING_VALIDATION;
    stateEnteredAt = millis();
    return;
  }

  if (currentState != STATE_AWAITING_VALIDATION) {
    // ignore validation replies that arrive out of order
    return;
  }

  if (cmd == "VALID") {
    openSlotForInsertion();
  } else if (cmd == "INVALID") {
    showError("Invalid book", "Not borrowed");
    beepError();
    goIdleAfterDelay(1500);
  }
}

// ---------- Slot control ----------
void openSlotForInsertion() {
  returnSlotServo.write(SERVO_OPEN_ANGLE);
  showMessage("Slot open", "Insert the book");
  currentState = STATE_SLOT_OPEN_AWAIT_ENTRANCE;
  stateEnteredAt = millis();
}

void closeSlotAndReset() {
  returnSlotServo.write(SERVO_CLOSED_ANGLE);
  goIdleAfterDelay(500);
}

bool irTriggered(int pin) {
  return digitalRead(pin) == IR_ACTIVE_STATE;
}

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

void sendHello() {
  Serial.println("HELLO,EBALIK,1.0");
}

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
void beepSuccess() {
  tone(BUZZER_PIN, 1500, 120);
  delay(150);
  tone(BUZZER_PIN, 2000, 150);
}

void beepError() {
  tone(BUZZER_PIN, 400, 300);
}

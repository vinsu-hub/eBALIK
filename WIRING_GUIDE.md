# eBALIK — Complete Wiring Guide

> **Platform:** Arduino Uno R3 (CH340 clone)
> **Firmware:** `arduino/eBALIK_arduino/eBALIK_arduino.ino`
> **Last updated:** 2026-07-19

This guide covers every physical connection between the Arduino Uno R3 and
all peripherals. Follow it pin-by-pin. Each component section includes the
exact Arduino pin, the component pin, a suggested wire color, and what the
connection does.

---

## 1. Bill of Materials

| # | Component | Qty | Specification | Notes |
|---|-----------|-----|---------------|-------|
| 1 | Arduino Uno R3 | 1 | CH340 USB-serial clone | The main MCU board |
| 2 | RFID Reader (RC522) | 1 | MFRC522, 13.56 MHz, SPI | Comes with header pins |
| 3 | RFID Tags/Cards | 5+ | 13.56 MHz MIFARE | Sticker or card format; one per book |
| 4 | Servo Motor | 1 | SG90, 5V | Controls the return door flap |
| 5 | IR Obstacle Sensor | 2 | HW-204 or similar, 3-pin | Digital output (LOW = detected) |
| 6 | LCD Display | 1 | 16x2, I2C, addr 0x27 | 4-pin I2C version (VCC, GND, SDA, SCL) |
| 7 | Active Buzzer | 1 | 5V, active (tone on HIGH) | Not passive — active buzzers self-oscillate |
| 8 | **Green LED** | 1 | 5mm, standard | Return approved indicator |
| 9 | **Red LED** | 1 | 5mm, standard | Return rejected indicator |
| 10 | **Resistors for LEDs** | 2 | 220 ohm (1/4W) | One per LED, current limiting |
| 11 | USB Cable | 1 | USB-A to USB-B | For Arduino-to-laptop connection |
| 12 | Breadboard | 1 | 830-point (full-size) | Or use perfboard for permanent build |
| 13 | Jumper Wires | 30+ | Male-to-mean dupont wires | Assorted colors recommended |
| 14 | 9V Battery + Clip | 1 | Optional | External power if USB is unstable |

### Wire Color Convention (suggested)

| Color | Use |
|-------|-----|
| **Red** | +5V power (VCC) |
| **Black** | Ground (GND) |
| **Orange** | SPI MOSI (data from Arduino to device) |
| **Yellow** | SPI MISO (data from device to Arduino) |
| **Blue** | SPI SCK (clock) |
| **Purple** | SPI SS / RST (chip select / reset) |
| **Green** | I2C SDA (data) |
| **White** | I2C SCL (clock) |
| **Brown** | Digital signals (IR sensors, buzzer, LEDs, servo) |
| **Pink** | LED-specific signal wires |

---

## 2. Arduino Uno R3 — Full Pin Map

```
                          ARDUINO UNO R3
                       +-----------------+
                       |    USB PORT     |
                       +--------+--------+
                                |
  Analog In                    |  Digital (PWM~)
  +-----------------------+    +-----------------------+
  | A0  (free)            |    | D0  (RX)   [free]    |
  | A1  (free)            |    | D1  (TX)   [free]    |
   | A2  (free)            |    | D2  IR_FULL_ENTRY    |
   | A3  (free)            |    | D3  IR_ENTRANCE      |
  | A4  SDA  [I2C LCD]    |    | D4  (free — was IR_OBSTRUCTION) |
  | A5  SCL  [I2C LCD]    |    | D5  BUZZER           |
  +-----------------------+    | D6  SERVO            |
                               | D7  GREEN LED        |
                               | D8  RED LED          |
                               | D9  RFID RST         |
                               | D10 RFID SS (CS)     |
                               | D11 RFID MOSI        |
                               | D12 RFID MISO        |
                               | D13 RFID SCK         |
                               +-----------------------+
                               | POWER   | ICSP       |
                               | 3.3V 5V |            |
                               | GND GND |            |
                               | VIN     |            |
                               +-----------------+---+
                                                 USB
```

### Pin Assignment Table

| Arduino Pin | Component | Direction | Wire Color | Function |
|-------------|-----------|-----------|------------|----------|
| **D2** | IR Sensor 1 (Entrance) | INPUT | Brown | Detects book entering the slot |
| **D3** | IR Sensor 2 (Full Entry) | INPUT | Brown | Confirms book is fully inserted |
| **D4** | *(free — previously IR Obstruction)* | — | — | Pin unused after safety sensor removal |
| **D5** | Active Buzzer | OUTPUT | Brown | Audible feedback (success/error beeps) |
| **D6** | SG90 Servo | OUTPUT (PWM) | Brown | Opens/closes the door flap |
| **D7** | Green LED (+) | OUTPUT | Pink | Lights up on approved return |
| **D8** | Red LED (+) | OUTPUT | Pink | Lights up on rejected return |
| **D9** | MFRC522 RST | OUTPUT | Purple | Resets the RFID reader |
| **D10** | MFRC522 SDA/SS | OUTPUT | Purple | SPI chip select for RFID reader |
| **D11** | MFRC522 MOSI | OUTPUT | Orange | SPI data: Arduino → RFID reader |
| **D12** | MFRC522 MISO | INPUT | Yellow | SPI data: RFID reader → Arduino |
| **D13** | MFRC522 SCK | OUTPUT | Blue | SPI clock signal |
| **A4** | LCD SDA | Bidirectional | Green | I2C data line to LCD display |
| **A5** | LCD SCL | OUTPUT | White | I2C clock line to LCD display |
| **3.3V** | MFRC522 VCC | POWER | Red | **3.3V ONLY** — do NOT use 5V |
| **5V** | Servo, IR sensors, Buzzer, LCD | POWER | Red | Shared 5V power rail |
| **GND** | ALL components | GROUND | Black | Shared ground rail |

---

## 3. Component Wiring Details

### 3.1 MFRC522 RFID Reader (SPI)

The RC522 communicates over SPI (Serial Peripheral Interface). It has 8 pins.
**WARNING:** The RC522 operates at **3.3V**. Connecting VCC to 5V may damage it.

| RC522 Pin | Arduino Pin | Wire Color | Notes |
|-----------|-------------|------------|-------|
| SDA (SS) | **D10** | Purple | SPI chip select — defined as `RFID_SS_PIN` |
| SCK | **D13** | Blue | SPI clock — hardware SPI, cannot move |
| MOSI | **D11** | Orange | SPI data out — hardware SPI, cannot move |
| MISO | **D12** | Yellow | SPI data in — hardware SPI, cannot move |
| RST | **D9** | Purple | Reset pin — defined as `RFID_RST_PIN` |
| IRQ | *not connected* | — | Not used in this firmware |
| GND | **GND** | Black | Ground |
| VCC | **3.3V** | Red | **3.3V from Arduino** — NOT 5V |

> **Important:** On the Arduino Uno, SPI pins (D11/D12/D13) are fixed to
> specific hardware. You cannot move MOSI/MISO/SCK to other pins. Only SS (D10)
> and RST (D9) can be reassigned, and they are already on non-conflicting pins.

```
RC522 Module (top view, pins facing you):

  +-----------+
  |  RC522    |
  |  MODULE   |
  |           |
  +--+--+--+--+
     |  |  |  |
    SCK SD MOS MISO  (top row)
    RST        IRQ    (bottom row, IRQ NC)
    VCC  GND
```

---

### 3.2 SG90 Servo Motor

The SG90 servo has a 3-pin connector (brown/red/orange on most cables).

| Servo Wire | Arduino Pin | Wire Color | Notes |
|------------|-------------|------------|-------|
| Brown/Black | **GND** | Black | Ground |
| Red | **5V** | Red | Power from Arduino 5V |
| Orange/Yellow | **D6** | Brown | PWM signal — defined as `SERVO_PIN` |

> **Note:** The SG90 draws ~150mA during movement. If the Arduino resets
> when the servo moves, add a 470uF capacitor across the servo power rails.

**Servo Angles (door flap mechanism):**

The servo controls a door flap that opens to accept the book and closes
after insertion. Lower angle = closed, higher angle = open.

- `10°` = CLOSED — door flap shut (default position on boot)
- `80°` = OPEN — door flap open, book can enter

> Re-verify with `arduino/servo_calibration/servo_calibration.ino` if the
> linkage or servo mounting changes. Angles calibrated 2026-07-18.

---

### 3.3 IR Obstacle Sensors (x2)

Each IR sensor is a 3-pin module (VCC, GND, OUT). They output **LOW** when
an obstacle is detected (the default for most Chinese IR obstacle modules).

| Sensor | Arduino Pin | Wire Color | Firmware Constant | Function |
|--------|-------------|------------|-------------------|----------|
| IR1 — Entrance (upper slot) | **D3** | Brown | `IR_ENTRANCE_PIN` | Detects book entering the slot (1s debounce) |
| IR2 — Full Entry (bottom) | **D2** | Brown | `IR_FULL_ENTRY_PIN` | Confirms book reached storage (single trigger) |

> **Removed:** The previous Safety Obstruction sensor (IR3 on D4) has been
> removed. Pin D4 is now free. A timed `STATE_CLOSING_WARNING` (2s, double
> beep) replaces the sensor-verified obstruction clearance — it warns users
> but does not verify clearance.

**Each IR sensor connections:**

| IR Pin | Arduino Pin | Wire Color |
|--------|-------------|------------|
| VCC | **5V** | Red |
| GND | **GND** | Black |
| OUT | **D2 / D3** | Brown |

> **IR Active State:** The firmware defines `IR_ACTIVE_STATE = LOW` (line 66
> of the `.ino`). If your sensors are active-HIGH, change this to `HIGH`.
> Test by checking if the sensor's onboard LED lights when an obstacle is
> detected — if it does, that's the active state.

**Placement (physical):**

```
         RETURN SLOT (top view)
    +----------------------------+
    |                            |
    |  [IR1: Entrance]           |  <-- at the slot opening
    |                            |
    |  [IR2: Full Entry]         |  <-- inside the slot, halfway down
    |                            |
    |  [Servo] ── door flap       |  <-- closing warning (2s, double beep)
    |                            |
    +----------------------------+
```

---

### 3.4 Active Buzzer

The active buzzer produces a tone when HIGH is applied. No `tone()` library
needed for basic beeps, but the firmware uses `tone()` for frequency control.

| Buzzer Pin | Arduino Pin | Wire Color | Notes |
|------------|-------------|------------|-------|
| (+) / VCC | **D5** | Brown | Digital HIGH = buzzer on |
| (-) / GND | **GND** | Black | Ground |

> **Active vs Passive:** This project uses an **active** buzzer. A passive
> buzzer requires `tone()` to produce sound. An active buzzer just needs HIGH/LOW
> but can also use `tone()` for different pitches. The firmware uses `tone()` to
> produce distinct success/error sounds.

**Sound Patterns:**
- **Approved:** Single beep (1800 Hz), 100ms
- **Success:** Two ascending beeps (1500 Hz → 2000 Hz), 120ms + 150ms
- **Closing Warning:** Double mid-tone beep (1200 Hz × 2), 2s warning before slot close
- **Error:** Single low beep (400 Hz), 300ms

---

### 3.5 Green LED (Return Approved)

The green LED lights up when a book is successfully validated for return
(`VALID` received from Flask) or when the return cycle completes
(`RETURN_SUCCESS`).

| LED Pin | Arduino Pin | Wire Color | Notes |
|---------|-------------|------------|-------|
| Anode (+) long leg | **D7** | Pink | Through 220Ω resistor |
| Cathode (-) short leg | **GND** | Black | Direct to ground |

**Wiring:**

```
  Arduino D7 ─────── 220Ω Resistor ──────── Green LED (+) ──── GND
                               (long leg)   (short leg)
```

> **Resistor is mandatory.** Without it, the LED will draw too much current
> and may burn out or damage the Arduino pin. 220Ω gives ~15mA at 5V —
> bright enough to see clearly without stressing the ATmega328P (max 40mA/pin).

**When it blinks:**
- VALID received from Flask (book approved for return)
- RETURN_SUCCESS (full return cycle completed)

---

### 3.6 Red LED (Return Rejected)

The red LED lights up when a book is rejected — unknown tag, not borrowed,
malformed UID, or any flow timeout.

| LED Pin | Arduino Pin | Wire Color | Notes |
|---------|-------------|------------|-------|
| Anode (+) long leg | **D8** | Pink | Through 220Ω resistor |
| Cathode (-) short leg | **GND** | Black | Direct to ground |

**Wiring:**

```
  Arduino D8 ─────── 220Ω Resistor ──────── Red LED (+) ──── GND
                               (long leg)   (short leg)
```

**When it blinks:**
- INVALID received from Flask (UNKNOWN_TAG, NOT_BORROWED, MALFORMED_UID)
- PC_TIMEOUT (Flask didn't respond within 5s)
- INSERT_TIMEOUT (no book inserted within 15s)
- INCOMPLETE_ENTRY (book not fully inserted within 8s)

---

### 3.7 16x2 I2C LCD Display

The LCD uses the I2C bus (only 2 data wires instead of 16). Most modules
have a small potentiometer on the back for contrast adjustment.

| LCD Pin | Arduino Pin | Wire Color | Notes |
|---------|-------------|------------|-------|
| GND | **GND** | Black | Ground |
| VCC | **5V** | Red | Power |
| SDA | **A4** | Green | I2C data — hardware I2C, cannot move |
| SCL | **A5** | White | I2C clock — hardware I2C, cannot move |

> **I2C Address:** The firmware assumes address `0x27`. If your LCD shows
> `0x20`, `0x38`, or another address, change the `LiquidCrystal_I2C lcd(0x27, 16, 2)`
> line in the `.ino` file. Use an I2C scanner sketch to find the address.

**LCD Messages by State:**

| State | Line 1 | Line 2 |
|-------|--------|--------|
| Idle | `eBALIK Return` | `Scan your book` |
| Tag scanned (waiting) | `Checking book...` | `<UID>` |
| VALID → slot open | `Slot open` | `Insert the book` |
| Book detected | `Book detected` | `Keep pushing...` |
| Full entry | `Checking slot...` | `Please wait` |
| Closing warning | `Book received!` | `Closing shortly` |
| Return success | `Return success!` | `Thank you.` |
| Unknown tag | `Tag not` | `recognized` |
| Not borrowed | `Book not` | `checked out` |
| Bad read | `Bad tag` | `read` |
| No response from PC | `No response` | `Try again` |
| No book inserted | `Timeout` | `No book inserted` |
| Incomplete entry | `Incomplete` | `Book not fully in` |

---

## 4. Power Distribution

### 4.1 Power Rails

Use the Arduino's built-in 5V and GND pins to power all peripherals.

```
Arduino 5V ──────> Breadboard (+) rail
                    ├── IR Sensor 1 VCC
                    ├── IR Sensor 2 VCC
                    ├── Servo VCC (red wire)
                    ├── Buzzer VCC
                    └── LCD VCC

Arduino GND ─────> Breadboard (-) rail
                    ├── IR Sensor 1 GND
                    ├── IR Sensor 2 GND
                    ├── Servo GND (brown wire)
                    ├── Buzzer GND
                    ├── LCD GND
                    ├── Green LED cathode
                    └── Red LED cathode

Arduino 3.3V ────> RC522 VCC (ONLY!)
                    └── (do NOT connect to 5V rail)
```

### 4.2 Current Budget

| Component | Typical Current | Peak Current |
|-----------|----------------|--------------|
| MFRC522 | ~13mA | ~30mA (TX) |
| SG90 Servo | ~10mA idle | ~150mA (moving) |
| IR Sensor (each) | ~10mA | ~15mA |
| LCD (I2C, backlight on) | ~20mA | ~40mA |
| Active Buzzer | ~5mA | ~30mA |
| Green LED (220Ω) | ~15mA | ~15mA |
| Red LED (220Ω) | ~15mA | ~15mA |
| **TOTAL** | **~88mA** | **~280mA** |

> The Arduino Uno's USB port supplies up to **500mA**. Total peak draw is
> ~295mA — well within limits. If you add more components later, consider
> using an external 5V power supply.

---

## 5. USB Connection to Laptop

The Arduino Uno R3 (CH340 clone) connects to your laptop via USB-A to USB-B cable.

| Connection | Details |
|------------|---------|
| Cable | USB-A to USB-B |
| Driver | CH340 — install via `TOOLS/install_ch340_driver.bat` |
| Baud Rate | 115200 (defined in firmware and `backend/.env`) |
| Serial Port | Auto-detected by `hw_utils.py` (CH340 VID:PID `1A86:7523`) |
| Flask Config | `SERIAL_PORT=` (empty = auto-detect), `SERIAL_ENABLED=false` |

> **To enable serial communication:** Set `SERIAL_ENABLED=true` in
> `backend/.env` and restart Flask. The SerialBridge will auto-detect the
> CH340 and connect.

---

## 6. Common Mistakes & Troubleshooting

### 6.1 RC522 powered from 5V instead of 3.3V
**Symptom:** RFID reader gets hot, no tags detected, or reads are unreliable.
**Fix:** Move the VCC wire from 5V to the Arduino's **3.3V** pin. The RC522
chip is 3.3V-only.

### 6.2 LCD shows nothing / garbled text
**Symptom:** LCD backlight is on but no text appears.
**Fix:**
1. Check I2C address (try `0x3F` instead of `0x27`)
2. Adjust the contrast potentiometer on the back of the LCD module
3. Verify SDA→A4 and SCL→A5 (swapped = no communication)

### 6.3 IR sensors always triggered / never triggered
**Symptom:** Sensor state doesn't change when obstacle is placed in front.
**Fix:**
1. Check if your sensors are active-LOW or active-HIGH (see `IR_ACTIVE_STATE`)
2. Adjust the sensitivity potentiometer on the IR module
3. Make sure you're connecting to the **OUT** pin, not the **EN** pin

### 6.4 Servo jitters or resets the Arduino
**Symptom:** Arduino resets when servo moves; erratic servo behavior.
**Fix:**
1. Add a **470uF electrolytic capacitor** across the servo power (5V ↔ GND)
2. If still unstable, power the servo from a separate 5V supply (share GND)

### 6.5 LEDs don't light up
**Symptom:** Buzzer works but LEDs are dark.
**Fix:**
1. Check that the 220Ω resistor is in series (not parallel)
2. Verify polarity: long leg (+) goes to Arduino pin, short leg (-) to GND
3. Swap the wires — you may have the LED in backwards

### 6.6 Buzzer is silent
**Symptom:** No sound on VALID/INVALID.
**Fix:**
1. Make sure you have an **active** buzzer (not passive)
2. Check polarity: (+) to D5, (-) to GND
3. Test manually: `digitalWrite(5, HIGH)` in a blank sketch should produce a tone

### 6.7 CH340 not detected by Windows
**Symptom:** No COM port appears in Device Manager.
**Fix:**
1. Run `TOOLS/install_ch340_driver.bat` (self-elevating, installs WCH driver)
2. Check Device Manager for "Ports (COM & LPT)" section
3. If still missing, try a different USB cable (some are charge-only)

---

## 7. Firmware `#define` → Physical Pin Reference

This table maps each `#define` in the `.ino` file to its physical pin and
what it controls.

| Firmware `#define` | Value | Physical Pin | Component |
|--------------------|-------|-------------|-----------|
| `RFID_SS_PIN` | 10 | D10 | MFRC522 SPI chip select |
| `RFID_RST_PIN` | 9 | D9 | MFRC522 reset |
| `SERVO_PIN` | 6 | D6 | SG90 servo signal |
| `IR_ENTRANCE_PIN` | 3 | D3 | IR sensor (entrance, upper slot) |
| `IR_FULL_ENTRY_PIN` | 2 | D2 | IR sensor (full entry, bottom) |
| `IR_OBSTRUCTION_PIN` | 4 | D4 | *(removed — pin now free)* |
| `BUZZER_PIN` | 5 | D5 | Active buzzer |
| `LED_GREEN_PIN` | 7 | D7 | Green LED (approved) |
| `LED_RED_PIN` | 8 | D8 | Red LED (rejected) |
| `IR_ACTIVE_STATE` | LOW | — | IR sensor trigger level |
| `SERVO_CLOSED_ANGLE` | 10 | — | Door flap closed (default on boot) |
| `SERVO_OPEN_ANGLE` | 80 | — | Door flap open (book can enter) |

**SPI Bus (fixed):**

| Signal | Arduino Pin | Cannot Move |
|--------|-------------|-------------|
| SCK | D13 | Yes — hardware SPI |
| MOSI | D11 | Yes — hardware SPI |
| MISO | D12 | Yes — hardware SPI |
| SS | D10 | No — software configurable, but D10 chosen for convention |

**I2C Bus (fixed):**

| Signal | Arduino Pin | Cannot Move |
|--------|-------------|-------------|
| SDA | A4 | Yes — hardware I2C |
| SCL | A5 | Yes — hardware I2C |

---

## 8. Visual Wiring Diagram (ASCII)

```
                        ARDUINO UNO R3
                      +=================+
               USB ==>|                 |
                      |  D13 ──── SCK  ───────────── RC522 SCK
                      |  D12 ──── MISO ───────────── RC522 MISO
                      |  D11 ──── MOSI ───────────── RC522 MOSI
                      |  D10 ──── SS   ───────────── RC522 SDA
                      |  D9  ──── RST  ───────────── RC522 RST
                      |  D8  ───────[220R]──────|>|── GND   (RED LED)
                      |  D7  ───────[220R]──────|>|── GND   (GREEN LED)
                      |  D6  ─────────────────── Servo Signal (orange)
                      |  D5  ─────────────────── Buzzer (+)
                       |  D4  ─────────────────── (free — was IR3 Safety)
                       |  D3  ─────────────────── IR2 OUT (Full Entry)
                       |  D2  ─────────────────── IR1 OUT (Entrance)
                      |                          |
                      |  A4  ─────────────────── LCD SDA
                      |  A5  ─────────────────── LCD SCL
                      |                          |
                      |  3.3V ────────────────── RC522 VCC  (3.3V ONLY!)
                      |  5V   ─────┬──────────── Servo VCC (red)
                       |            ├──────────── IR1 VCC
                       |            ├──────────── IR2 VCC
                       |            ├──────────── Buzzer GND
                      |            └──────────── LCD VCC
                      |  GND  ─────┬──────────── RC522 GND
                      |            ├──────────── Servo GND (brown)
                       |            ├──────────── IR1 GND
                       |            ├──────────── IR2 GND
                       |            ├──────────── Buzzer GND
                      |            ├──────────── LCD GND
                      |            ├──────────── Green LED cathode
                      |            └──────────── Red LED cathode
                      +=================+

  LED Close-up:
  ───────────────
  D7 ──[220Ω]──>| (green, anode+ to pin, cathode- to GND)
  D8 ──[220Ω]──>| (red,    anode+ to pin, cathode- to GND)
```

---

## 9. Physical Placement Diagram (Conceptual)

```
  ┌─────────────────────────────────────────────────┐
  │              eBALIK RETURN BOX                   │
  │                                                  │
  │   ┌──────────────┐                               │
  │   │  LCD (16x2)  │  <-- visible to user          │
  │   └──────────────┘                               │
  │                                                  │
  │   ┌──────────────────────────────┐               │
  │   │      RETURN SLOT             │               │
  │   │                              │               │
  │   │  [IR1] ── entrance           │               │
  │   │  [IR2] ── full entry         │               │
  │   │                              │               │
  │   │  [Servo] ── door flap    │               │
  │   └──────────────────────────────┘               │
  │                                                  │
  │   ┌──────────────────┐   ┌──────────────────┐   │
  │   │  GREEN LED (bulb)│   │  RED LED (bulb)  │   │
  │   └──────────────────┘   └──────────────────┘   │
  │                                                  │
  │   ┌──────────────┐   ┌──────────────────────┐   │
  │   │   BUZZER     │   │  RC522 RFID READER   │   │
  │   └──────────────┘   │  (user taps tag here)│   │
  │                       └──────────────────────┘   │
  │                                                  │
  │   [ Arduino Uno R3 + Breadboard (inside) ]      │
  │   [ USB cable to laptop ]                        │
  └─────────────────────────────────────────────────┘
```

---

## 10. Quick Build Checklist

- [ ] Arduino Uno R3 placed inside the box, USB port accessible
- [ ] RC522 connected via SPI (pins 9, 10, 11, 12, 13) + **3.3V** + GND
- [ ] Servo connected to D6 + 5V + GND; servo linkage attached to door flap
- [ ] IR Sensor (Entrance, upper slot) connected to D3 + 5V + GND
- [ ] IR Sensor (Full Entry, bottom) connected to D2 + 5V + GND
- [ ] D4 left free (previously used for Safety Obstruction sensor — removed)
- [ ] Buzzer connected to D5 + GND
- [ ] Green LED connected to D7 through 220Ω resistor to GND
- [ ] Red LED connected to D8 through 220Ω resistor to GND
- [ ] LCD connected via I2C (A4, A5) + 5V + GND
- [ ] CH340 driver installed (`TOOLS/install_ch340_driver.bat`)
- [ ] Arduino IDE 2.x installed, firmware uploaded
- [ ] USB cable connected, COM port detected
- [ ] `backend/.env` set to `SERIAL_ENABLED=true` for live testing
- [ ] All GND wires share a common ground rail on the breadboard

# eBALIK — Project Current State (2026-07-19)

## What eBALIK Is

RFID-based book return station. A physical return box with a door flap mechanism, 2 IR sensors (upper entrance + bottom compartment), LCD, and buzzer, controlled by an Arduino Uno R3 communicating over USB Serial to a Flask + MySQL web dashboard running on localhost.

**Admin login:** `admin` / `admin123`  
**DB:** MySQL 8.4.9, `ebalik_db`, root password `ebalik123`  
**Arduino:** COM4, firmware v1.2, compiled and uploaded  
**Flask:** `http://localhost:5001`, SerialBridge connected to COM4  
**GitHub:** https://github.com/vinsu-hub/eBALIK  

---

## Current Hardware State

| Component | Pin | Status |
|-----------|-----|--------|
| Arduino Uno R3 (CH340) | — | Connected, firmware uploaded (COM4) |
| MFRC522 RFID Reader | D10-D13, D9 RST | Wired, SPI |
| SG90 Servo (door flap) | D6 | Wired, angles 10°/80° calibrated |
| IR Sensor (Entrance, upper slot) | **D3** | Wired, active LOW, 1s debounce |
| IR Sensor (Full Entry, bottom) | **D2** | Wired, active LOW, single trigger |
| Pin D4 | — | Free (previously Safety Obstruction) |
| Active Buzzer | D5 | **Disconnected** (servo PWM noise coupling) |
| Green LED | D7 | Wired |
| Red LED | D8 | Wired |
| LCD 16x2 I2C | A4/A5, addr 0x27 | Wired |

---

## Current Software State

| Component | Status |
|-----------|--------|
| Flask server | Running on http://localhost:5001 |
| SerialBridge | Connected to COM4, listening for serial |
| MySQL 8.4.9 | Running, eBALIK DB loaded with schema + seed data |
| Admin user | admin / admin123 |
| HW monitor | NOT running (conflicts with SerialBridge for COM4) |

---

## Firmware v1.2 — Key Details

### IR Sensor Pin Mapping (Swapped in Session 6)
| Firmware Define | Arduino Pin | Physical Location | Function |
|----------------|-------------|-------------------|----------|
| `IR_ENTRANCE_PIN` | **D3** | Upper slot entrance | Detects book entering (checked FIRST) |
| `IR_FULL_ENTRY_PIN` | **D2** | Bottom of compartment | Confirms book reached storage (checked SECOND) |

### IR Sensor Behavior
| Sensor | Logic | Debounce |
|--------|-------|----------|
| Entrance (D3) | Must stay LOW **continuously for 1 second** | Filters servo vibration, hand movement |
| Full Entry (D2) | **Single LOW pulse** = book confirmed | No debounce needed (already past entrance) |

### Servo Angles
| Angle | State |
|-------|-------|
| 10° | CLOSED (door flap shut, default on boot) |
| 80° | OPEN (door flap open, book can enter) |

### Complete Return Flow
1. **VALID** received → servo opens gate immediately → `STATE_AWAITING_ENTRANCE`
2. Entrance IR (D3) stays LOW for 1s continuously → `STATUS,ENTRANCE_DETECTED` → `STATE_AWAIT_FULL_ENTRY`
3. Full entry IR (D2) single LOW pulse → `STATUS,FULL_ENTRY` → `STATE_CLOSING_WARNING`
4. 2-second warning (double beep) → `STATE_CLOSING`
5. Servo closes → `RETURN_SUCCESS` → back to `STATE_IDLE`

### Timeouts
| Constant | Value | Timeout Action |
|----------|-------|---------------|
| `RFID_VALIDATION_TIMEOUT` | 5s | `RETURN_FAILED,PC_TIMEOUT` |
| `INSERT_TIMEOUT` | 15s | `RETURN_FAILED,INSERT_TIMEOUT` |
| `FULL_ENTRY_TIMEOUT` | 8s | `RETURN_FAILED,INCOMPLETE_ENTRY` |
| `CLOSE_WARNING_MS` | 2s | Transitions to CLOSING |
| `RFID_DEBOUNCE_MS` | 3s | Ignores same UID within cooldown |

### Serial Debug Output
The firmware prints IR sensor values to serial for debugging:
- `IR_IDLE P3(entr)=HIGH P2(full)=HIGH` — idle state, every 3s
- `IR_DEBUG P3(entr)=LOW P2(full)=HIGH triggered=YES` — entrance state, every 1s
- Labels show actual Arduino pin numbers (P3=entrance, P2=full entry)

### Buzzer Tones
| Event | Frequency | Duration |
|-------|-----------|----------|
| Approved | 1800 Hz | 100ms |
| Success | 1500→2000 Hz sweep | — |
| Error | 400 Hz | 300ms |
| Closing warning | 1200 Hz × 2 | Double beep |

---

## What Does NOT Exist (for reference)

- No HTTPS (local only, not needed)
- No cloud database (MySQL local)
- No multi-user auth (admin-only dashboard)
- No mobile app
- No deployment scripts beyond local laptop setup
- Buzzer currently disconnected (noise coupling from servo PWM)

# eBALIK — Next Session To-Do

## 1. Reconnect Buzzer (Priority)
- Buzzer was disconnected due to servo PWM noise coupling on adjacent pins (D5/D6)
- Options: add decoupling capacitor (100nF ceramic across VCC/GND near buzzer), move buzzer to a different pin, or use `noTone()` to silence between pulses
- Test: upload firmware with buzzer enabled, verify clean operation

## 2. Test Full Return Flow (End-to-End)
- Scan a borrowed book tag → VALID → gate opens → hold at entrance (D3) for 1s → book slides down past D2 → closing warning → gate closes → RETURN_SUCCESS
- Verify dashboard updates live (book status changes from "borrowed" to "available")

## 3. Test Registration Flow via FAB Button
- Click blue RFID scan FAB → Add Book modal opens → scan tag → UID fills input → save book
- Verify book appears in catalog

## 4. Test Reassign Flow
- Scan tag belonging to other book → click reassign → verify UID moved
- Verify original book no longer has that UID

## 5. Test Reconnect Behavior
- Unplug/replug Arduino → verify SerialBridge reconnects automatically
- Verify dashboard badge flips red → green

## 6. Test Debounce
- Hold same tag on reader for >3s → verify only one scan processed

## 7. Demo Prep
- Download Bootstrap/Socket.IO locally if demo venue has no WiFi
- Test all pages: dashboard, books, borrow records, return records, system logs

## 8. Future Improvements (If Time Permits)
- Add safety obstruction sensor back (pin D4 available) for verified clearance
- Add book count sensor to verify storage capacity
- Add LCD custom icons for return status

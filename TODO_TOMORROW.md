# eBALIK — Tomorrow's To-Do

## 1. Upload Arduino firmware
- Install Arduino IDE from https://www.arduino.cc/en/software
- Open `arduino\eBALIK_arduino\eBALIK_arduino.ino`
- Install libraries: **MFRC522**, **LiquidCrystal I2C** (via Sketch → Include Library → Manage Libraries)
- Select board: **Arduino Uno R3**, port: **COM5**
- Click **Upload**

## 2. Test hardware monitor
- Run `python hw_monitor.py`
- PING/HELLO handshake should work now (3.5s boot delay + retry logic applied)
- If still no HELLO → lower `BOOT_DELAY` from 3.5 to 2.5 in `hw_monitor.py` line 52
- If HELLO works → verify live monitor loop and keyboard input (`kbhit()` fix) don't crash

## 3. Enable Arduino in Flask
- Set `SERIAL_ENABLED=true` in `backend\.env`
- Restart Flask: `python backend\run.py` (serving on port 5001)
- Dashboard should show "Connected" badge

# eBALIK — CH340 Driver Integration & Arduino Handshake Plan

**For:** Claude Code implementation
**Context files to reference:** `eBALIK_project_context.md`, `SESSION_NOTES_Ebalik_7-11-26.md`,
`app/serial_reader.py`, `hw_monitor.py`, `sim_terminal.py`, `app/routes/api.py`,
`app/templates/base.html`, `app/static/js/socket_client.js`

---

## 1. Goal

Right now the "Terminal" FAB button spawns `hw_monitor.py` in a new console window
purely as a **diagnostic tool** — it scans ports, tries a PING/HELLO handshake, and
prints raw serial traffic. It does not talk to Flask/MySQL/Socket.IO at all, and it
doesn't distinguish real USB-serial adapters (like the LAFVIN board's CH340G chip)
from unrelated virtual/legacy COM ports (e.g. COM1 "Communications Port", which is
just Windows' built-in modem stub and will never respond to a HELLO).

We want the button to become the actual **dedicated connection window** for bridging
the physical Arduino to the dashboard — not just a diagnostic log — so that:

- It reliably finds the LAFVIN UNO R3 (CH340-based) and ignores decoy ports like COM1.
- A successful handshake visibly updates the dashboard's "Arduino offline/online"
  badge and Live System Log in real time (currently these are separate, disconnected
  processes).
- There's one clear, unambiguous path from "click Terminal" → "Arduino connected and
  driving the dashboard" with no manual COM port typing.

---

## 2. Root Cause of Today's Behavior

`hw_monitor.py`'s port scan (`serial.tools.list_ports.comports()`) currently accepts
any COM port found, including OS-level virtual ports. It needs to filter specifically
for USB-serial adapters, and ideally match the CH340's known VID:PID.

Also, `hw_monitor.py` and the real `SerialBridge` (used when `SERIAL_ENABLED=true`)
are two completely separate implementations that don't share state — meaning even a
successful hw_monitor handshake doesn't inform Flask/Socket.IO/the dashboard badge.

---

## 3. Known Bug — Terminal Window Closes Instantly

**Current behavior:** clicking the Terminal FAB spawns `hw_monitor.py` in a new CMD
window (`CREATE_NEW_CONSOLE`), but the window closes immediately — before the user
can see the port scan, the handshake attempt, or even a failure message.

**Required fix:** the spawned window must **stay open regardless of outcome** —
whether no ports are found, the handshake fails/times out, or it succeeds. It should
only close when the user explicitly closes it (or types `quit`, per the existing
command list). This is true both today (`hw_monitor.py` used standalone) and after
the changes in this plan (handoff to `SerialBridge` in Mode A) — the window is a
persistent diagnostic console, not a one-shot script.

Likely causes to check in `hw_monitor.py` / the `/api/hw-monitor/launch` spawn logic:

- The script may be exiting (reaching end of `main()` / hitting an unhandled
  exception) right after the scan-and-handshake sequence instead of falling through
  into the "Live Monitor" input loop shown in the screenshot (`Type PING to check,
  RESET to reset, ...`). Confirm the code path that runs after a failed handshake
  (`"No HELLO response received... Entering monitor mode anyway"`) actually reaches
  the blocking input loop rather than falling off the end of the function.
- If it's a Windows console flag issue: confirm the process is spawned with
  `subprocess.Popen(..., creationflags=subprocess.CREATE_NEW_CONSOLE)` and **not**
  combined with anything that causes the parent to also terminate the child (e.g. do
  not spawn via a shell one-liner like `cmd /c python hw_monitor.py` without `/k`,
  since `/c` closes the window when the command finishes — use `cmd /k` or spawn the
  `.py` directly via `CREATE_NEW_CONSOLE` without going through `cmd /c`).
- Wrap the entire scan+handshake sequence in `hw_monitor.py`'s `main()` in a
  try/except that, even on an unhandled exception, prints the error and then falls
  into the same input loop (or at minimum an `input("Press Enter to close...")`)
  rather than letting the script exit and the console auto-close.
- Add an explicit test case: unplug all Arduino-like devices, click Terminal FAB,
  confirm the window stays open showing "No devices found — waiting for device to
  be plugged in" (this is described as existing behavior in the session notes, so if
  it's currently closing instead, this is the regression to fix).

This should be fixed **before** implementing the `/api/hw-status` handoff logic in
section 5, since a window that won't stay open can't reliably show handshake results
or hand off to `SerialBridge`.

---

## 4. Recommended Architecture

**Keep two roles, but connect them:**

1. **`hw_monitor.py` (Terminal FAB)** — stays a standalone popup terminal (users like
   seeing raw serial output), but on successful handshake it should:
   - POST connection status to a new Flask endpoint (`/api/hw-status`), including
     which COM port and that HELLO succeeded.
   - Continue as a read-only monitor OR gracefully release the port so the
     `SerialBridge` inside Flask can open it — **decide and implement one of the two
     port-ownership modes below (do not attempt both at once, since only one process
     can hold a COM port).**

   **Mode A (simpler, recommended for defense/demo):** `hw_monitor.py` is diagnostic-only.
   Once it confirms HELLO works, it prints "Handshake confirmed — closing monitor,
   enable SerialBridge to proceed" and exits/releases the port automatically. The user
   (or an automated follow-up call) then flips `SERIAL_ENABLED=true` and Flask's own
   `SerialBridge` opens the same port for the real, production connection driving the
   dashboard.

   **Mode B (more integrated, more complex):** `hw_monitor.py` *is* the running bridge —
   it owns the port permanently and forwards parsed serial events (RFID scans, sensor
   states) directly into MySQL + Socket.IO the same way `sim_terminal.py` already does
   for simulated scans. Flask's separate `SerialBridge` is then unused/disabled.

   → **Implement Mode A first.** It's lower-risk, keeps a single source of truth
   (`SerialBridge` inside Flask), and the terminal window's only job becomes
   "confirm hardware is real and reachable" before handing off.

2. **`SerialBridge` (inside Flask, `app/serial_reader.py`)** — becomes the sole owner
   of the live connection once enabled, and is what actually updates the dashboard.

---

## 5. Implementation Tasks

### 4.1 Shared port-detection module

Create `app/hw_utils.py` (importable by both `hw_monitor.py` and `serial_reader.py`
to avoid duplicating logic):

```python
import serial.tools.list_ports

# CH340 / CH340G common VID:PID (WCH)
CH340_IDS = {("1A86", "7523"), ("1A86", "5523")}

def list_candidate_ports():
    """Return only plausible USB-serial adapters, filtering out virtual/legacy ports."""
    candidates = []
    for port in serial.tools.list_ports.comports():
        # Skip known non-hardware ports
        if port.vid is None or port.pid is None:
            continue  # COM1-style "Communications Port" has no VID/PID — exclude it
        vid_pid = (f"{port.vid:04X}", f"{port.pid:04X}")
        is_ch340 = vid_pid in CH340_IDS or (port.description and "CH340" in port.description.upper())
        candidates.append({
            "device": port.device,
            "description": port.description,
            "vid_pid": vid_pid,
            "is_ch340": is_ch340,
        })
    # Prioritize CH340 matches first
    candidates.sort(key=lambda c: not c["is_ch340"])
    return candidates

def find_arduino_port():
    candidates = list_candidate_ports()
    for c in candidates:
        if c["is_ch340"]:
            return c["device"]
    return None  # No confident match — caller should prompt user
```

**Task:** Replace the raw `serial.tools.list_ports.comports()` scan in `hw_monitor.py`
with `list_candidate_ports()` / `find_arduino_port()` from this shared module. Update
the printed port list so ports with no VID/PID (like COM1) are either hidden or
clearly labeled `(not a USB device — skipped)`.

### 4.2 `hw_monitor.py` changes

**Critical bug to fix first:** the Terminal FAB currently opens a CMD window that
closes instantly, regardless of whether the handshake succeeds, fails, or no device
is found at all. This must never happen — the window is the user's only visibility
into what's going on, so it must stay open and interactive in every outcome
(success, HELLO timeout, no ports found, exception/crash). Treat this as a P0 fix
before any of the other 4.2 changes below.

**Likely causes to check, in order:**
1. **Launch flag mismatch** — if `/api/terminal/launch` or `/api/hw-monitor/launch`
   spawns the process with `cmd /c python hw_monitor.py` (or via `CREATE_NEW_CONSOLE`
   without `/K`), the console window closes the instant the Python process returns —
   success, failure, or crash all end the same way. Change the spawn command to use
   `cmd /k python hw_monitor.py` (note `/K` not `/C`) so the shell stays open after
   the script exits, or equivalently launch with
   `subprocess.Popen(["cmd", "/K", "python", "hw_monitor.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)`.
2. **Unhandled exception on exit** — if `hw_monitor.py` throws (e.g. missing
   `pyserial`, a bad import, or — once 4.2's status-POST is added — a failed
   `requests.post()` call to Flask because the endpoint doesn't exist yet), the
   script exits immediately and, combined with cause #1, the window vanishes with no
   trace. Wrap the main flow in a top-level `try/except Exception`, print the full
   traceback to the console, and fall through to the same "press Enter to exit" wait
   used on all other exit paths (see below) — never let an exception be the reason
   the window disappears silently.
3. **Missing final blocking call** — every exit path in `hw_monitor.py` (handshake
   success, handshake timeout/failure, zero ports found, keyboard interrupt, or
   exception) must end by explicitly waiting on user input before the process
   returns, e.g. `input("\nPress Enter to close this window...")`. Do not rely on the
   console host to keep the window open — make the script itself block.

- On startup, call `find_arduino_port()`. If found, auto-connect as today. If not
  found but other candidate ports exist, list them and let the user pick. If zero
  candidates exist at all, keep current "waiting for device" behavior — this
  waiting behavior already exists per session notes and must be preserved, not
  replaced by the input-on-exit fix above (the two are for different situations:
  "still scanning/waiting for a device" vs "scan finished, window should stay open
  to show the result").
- On successful HELLO handshake, `POST http://localhost:5000/api/hw-status` with
  JSON: `{"connected": true, "port": "COM4", "vid_pid": "1A86:7523"}`.
- On disconnect/exit, POST `{"connected": false}` to the same endpoint so the badge
  reverts to offline.
- Print a clear final line once handshake succeeds:
  `"Handshake confirmed. Enable SERIAL_ENABLED=true and restart Flask (or use the
  dashboard toggle, if implemented) to activate live dashboard integration."`

### 4.3 New Flask endpoint: `/api/hw-status`

In `app/routes/api.py`:
- `POST /api/hw-status` — accepts the JSON payload above, stores last-known state
  (in-memory is fine for a single-demo-laptop deployment), and emits a Socket.IO
  event (`hw_status_update`) with the same payload so connected dashboard clients
  update immediately.
- `GET /api/hw-status` — returns current cached state (useful on dashboard page load
  before any Socket.IO event has fired).

### 4.4 Frontend: badge + Live System Log

In `socket_client.js`:
- Listen for `hw_status_update`. On `connected: true`, switch the topbar/sidebar
  "Arduino offline" badge to "Arduino online (COM4)" with the existing green/red
  status styling already used for device status.
- On `connected: false`, revert to offline styling.
- Push a corresponding entry into the Live System Log panel (`INFO: Arduino
  connected on COM4` / `WARNING: Arduino disconnected`), matching the existing log
  entry format already shown in the dashboard (see `Book returned:` / `Database
  reset` entries in current UI).

### 4.5 `SerialBridge` (`app/serial_reader.py`)

- Import `find_arduino_port()` from `app/hw_utils.py`.
- If `.env`'s `SERIAL_PORT` is unset, empty, or the configured port is no longer
  present in `list_candidate_ports()`, fall back to `find_arduino_port()`
  automatically at startup instead of failing.
- Log a clear warning if no CH340 device is found at all, rather than silently
  failing to connect.
- On successful open, also POST/emit to the same `hw_status_update` path used in
  4.3 so status is consistent whether the connection came from `hw_monitor.py`'s
  handoff or a direct Flask-managed connection.

### 4.6 `.env` cleanup

Once 4.5 is done, `SERIAL_PORT=COM3` in `.env` can be left blank/commented as the
default, since it's now auto-resolved. Keep it as an optional override for cases
where multiple USB-serial devices are plugged in at once and a specific one needs
to be forced.

---

## 6. Testing Checklist (once Arduino hardware arrives)

0. **Window-stays-open regression test** — click the Terminal FAB in each of these
   scenarios and confirm the CMD window remains open and interactive in all of them
   (does not require real hardware, can be tested right now):
   - No Arduino plugged in at all (current known-failing case).
   - A non-CH340 device plugged in (e.g. any other USB-serial adapter, or just COM1
     present with nothing else).
   - Deliberately break something (e.g. temporarily rename `pyserial` import) to
     force an exception, confirm the traceback prints and the window still waits for
     Enter instead of vanishing.
1. Install CH340 driver on the host machine (Device Manager should show
   `USB-SERIAL CH340 (COMx)` under Ports, not under "Other devices").
2. Plug in LAFVIN UNO R3 **before** clicking the Terminal FAB — confirm
   `hw_monitor.py` auto-detects it (not COM1) and completes PING/HELLO.
3. Confirm the dashboard badge flips to "Arduino online" within a second or two of
   handshake success, without refreshing the page.
4. Unplug the Arduino — confirm badge reverts to offline and a log entry appears.
5. Set `SERIAL_ENABLED=true`, restart Flask, confirm `SerialBridge` finds the same
   port automatically with no `.env` COM number set.
6. Confirm `hw_monitor.py` and `SerialBridge` are never both holding the port open
   at the same time (per existing known-issue note in session notes) — Mode A should
   guarantee this by design, but verify with a real port-conflict test (try opening
   both back-to-back and confirm the second gets a clean "port busy" error rather
   than crashing Flask).

---

## 7. Open Decisions for Vince (flag these, don't just assume)

- Confirm whether Mode A (recommended) or Mode B fits the demo flow better — Mode A
  means an extra manual step (enable `SERIAL_ENABLED`) after the terminal confirms
  hardware; Mode B is more "one click" but riskier to get stable before defense.
- Decide whether `hw_monitor.py` should auto-exit after a successful handoff, or
  stay open as a read-only log (recommend: stay open, just stop holding the port).

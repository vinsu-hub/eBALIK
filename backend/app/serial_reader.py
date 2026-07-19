"""
Background thread that owns the USB serial connection to the Arduino.

Responsibilities:
  - Open/maintain the serial port (auto-retries if the Arduino is unplugged).
  - Parse incoming lines per docs/PROTOCOL.md.
  - Validate scanned RFID UIDs against the database and reply VALID/INVALID.
  - On RETURN_SUCCESS, close the borrow record, log the return, update the
    book status, and broadcast a Socket.IO event so the dashboard updates
    live without a page refresh.
  - On RETURN_FAILED, log a WARNING and broadcast it too.

This module is intentionally decoupled from the Flask request cycle: it runs
in its own thread, using `app.app_context()` to talk to the DB safely.
"""

import re
import threading
import time
from weakref import ref as weak_ref

try:
    import serial
except ImportError:  # pyserial not installed yet
    serial = None

from app.extensions import db, socketio
from app.models import Book, BorrowRecord, ReturnRecord, log_event

# Valid RFID UID: 4-byte (8 hex) or 7-byte (14 hex) MIFARE UID
VALID_UID_RE = re.compile(r"^[0-9A-F]{8}$|^[0-9A-F]{14}$")

try:
    from app.hw_utils import find_arduino_port
except ImportError:
    find_arduino_port = None


class SerialBridge:
    def __init__(self, app, port, baud, enabled=True):
        self.app = app
        self.port = port
        self.baud = baud
        self.enabled = enabled
        self.ser = None
        self._stop_event = threading.Event()
        self._thread = None
        self.mode = "idle"
        self._reg_timer = None

    def _emit_hw_status(self, connected):
        socketio.emit("hw_status_update", {
            "connected": connected,
            "port": self.port if connected else "",
            "vid_pid": "",
        })
        socketio.emit("device_status", {"connected": connected})

    def start(self):
        if not self.enabled:
            print("[SerialBridge] Disabled via SERIAL_ENABLED=false. Skipping.")
            return
        if serial is None:
            print("[SerialBridge] pyserial not installed. Run: pip install pyserial")
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self.ser and self.ser.is_open:
            self.ser.close()

    # ------------------------------------------------------------------
    def _on_registration_timeout(self):
        with self.app.app_context():
            socketio.emit("rfid_registration_timeout")
            self.mode = "idle"

    def start_registration_mode(self, timeout=15):
        self.mode = "listening_for_registration"
        self._reg_timer = threading.Timer(timeout, self._on_registration_timeout)
        self._reg_timer.daemon = True
        self._reg_timer.start()

    def cancel_registration_mode(self):
        self.mode = "idle"
        if self._reg_timer and self._reg_timer.is_alive():
            self._reg_timer.cancel()
            self._reg_timer = None

    # ------------------------------------------------------------------
    def _resolve_port(self):
        if not self.port or not self.port.strip():
            resolved = find_arduino_port() if find_arduino_port else None
            if resolved:
                print(f"[SerialBridge] Auto-resolved port: {resolved}")
                self.port = resolved
            else:
                print("[SerialBridge] No port configured and no CH340 device found. Disabling.")
                self.enabled = False
                return False
        return True

    def _connect(self):
        if not self._resolve_port():
            return False
        while not self._stop_event.is_set():
            try:
                self.ser = serial.Serial(self.port, self.baud, timeout=1)
                print(f"[SerialBridge] Connected to {self.port} @ {self.baud} baud")
                time.sleep(2)
                self._emit_hw_status(True)
                return True
            except Exception as exc:
                print(f"[SerialBridge] Could not open {self.port}: {exc}. Retrying in 5s...")
                time.sleep(5)
                # Re-resolve port in case Arduino moved to a different COM port
                self._resolve_port()
        return False

    def _run(self):
        if not self._connect():
            return

        with self.app.app_context():
            while not self._stop_event.is_set():
                try:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    print(f"[Arduino->PC] {line}")
                    self._handle_line(line)
                except (OSError, serial.SerialException) as exc:
                    print(f"[SerialBridge] Serial error: {exc}. Reconnecting...")
                    self._emit_hw_status(False)
                    try:
                        self.ser.close()
                    except Exception:
                        pass
                    if not self._connect():
                        break

    # ------------------------------------------------------------------
    def _send(self, message):
        if self.ser and self.ser.is_open:
            print(f"[PC->Arduino] {message}")
            self.ser.write((message + "\n").encode("utf-8"))

    def _handle_line(self, line):
        parts = line.split(",")
        cmd = parts[0].upper()

        if cmd == "HELLO":
            socketio.emit("device_status", {"connected": True, "raw": line})
            return

        if cmd == "RFID":
            uid = parts[1] if len(parts) > 1 else ""
            if self.mode == "listening_for_registration":
                self.mode = "idle"
                if self._reg_timer and self._reg_timer.is_alive():
                    self._reg_timer.cancel()
                    self._reg_timer = None
                socketio.emit("rfid_registration_scan", {"uid": uid.upper()})
                print(f"[SerialBridge] Registration scan captured: {uid}")
                return
            self._handle_rfid_scan(uid)
            return

        if cmd == "STATUS":
            status = parts[1] if len(parts) > 1 else ""
            socketio.emit("hardware_status", {"status": status})
            return

        if cmd == "RETURN_SUCCESS":
            uid = parts[1] if len(parts) > 1 else ""
            self._handle_return_success(uid)
            return

        if cmd == "RETURN_FAILED":
            uid = parts[1] if len(parts) > 1 else ""
            reason = parts[2] if len(parts) > 2 else "UNKNOWN"
            self._handle_return_failed(uid, reason)
            return

    # ------------------------------------------------------------------
    def _handle_rfid_scan(self, uid):
        uid = uid.strip().upper()
        if not VALID_UID_RE.match(uid):
            log_event("WARNING", "RFID", f"Malformed UID received from reader: {uid}", rfid_uid=uid)
            socketio.emit("scan_result", {"uid": uid, "valid": False, "reason": "MALFORMED_UID"})
            self._send(f"INVALID,{uid},MALFORMED_UID")
            return
        book = Book.query.filter_by(rfid_uid=uid).first()

        if not book:
            log_event("WARNING", "RFID", f"Unknown RFID tag scanned: {uid}", rfid_uid=uid)
            socketio.emit("scan_result", {"uid": uid, "valid": False, "reason": "UNKNOWN_TAG"})
            self._send(f"INVALID,{uid},UNKNOWN_TAG")
            return

        open_borrow = BorrowRecord.query.filter_by(book_id=book.book_id, is_returned=False).first()
        if not open_borrow:
            log_event(
                "WARNING", "RFID",
                f"Book '{book.title}' scanned but has no active borrow record",
                rfid_uid=uid,
            )
            socketio.emit(
                "scan_result",
                {"uid": uid, "valid": False, "reason": "NOT_BORROWED", "title": book.title},
            )
            self._send(f"INVALID,{uid},NOT_BORROWED")
            return

        log_event("INFO", "RFID", f"Book '{book.title}' validated for return", rfid_uid=uid)
        socketio.emit(
            "scan_result",
            {"uid": uid, "valid": True, "title": book.title, "borrower": open_borrow.borrower_name},
        )
        self._send(f"VALID,{uid}")

    def _handle_return_success(self, uid):
        uid = uid.strip().upper()
        book = Book.query.filter_by(rfid_uid=uid).first()
        if not book:
            log_event("ERROR", "RETURN", f"RETURN_SUCCESS for unknown UID {uid}", rfid_uid=uid)
            return

        open_borrow = BorrowRecord.query.filter_by(book_id=book.book_id, is_returned=False).first()

        if open_borrow:
            open_borrow.is_returned = True
            open_borrow.returned_at = db.func.now()

        book.status = "available"

        return_record = ReturnRecord(
            book_id=book.book_id,
            borrow_id=open_borrow.borrow_id if open_borrow else None,
            rfid_uid=uid,
            verified_by_sensors=True,
        )
        db.session.add(return_record)
        db.session.commit()

        log_event("INFO", "RETURN", f"Book '{book.title}' returned successfully", rfid_uid=uid)
        socketio.emit(
            "book_returned",
            {
                "uid": uid,
                "title": book.title,
                "borrower": open_borrow.borrower_name if open_borrow else None,
                "returned_at": str(return_record.returned_at),
            },
        )

    def _handle_return_failed(self, uid, reason):
        uid = uid.strip().upper()
        book = Book.query.filter_by(rfid_uid=uid).first()
        title = book.title if book else uid
        log_event("ERROR", "RETURN", f"Return failed for '{title}': {reason}", rfid_uid=uid)
        socketio.emit("return_failed", {"uid": uid, "title": title, "reason": reason})


_bridge_instance = None


def init_serial_bridge(app):
    """Call once from the app factory to start the background serial thread."""
    global _bridge_instance
    raw_port = app.config.get("SERIAL_PORT", "").strip()
    port = raw_port if raw_port != "COM3" else ""
    _bridge_instance = SerialBridge(
        app=app,
        port=port,
        baud=app.config["SERIAL_BAUD"],
        enabled=app.config["SERIAL_ENABLED"],
    )
    _bridge_instance.start()
    return _bridge_instance


def get_bridge():
    return _bridge_instance

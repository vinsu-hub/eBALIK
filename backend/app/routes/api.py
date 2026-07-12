import os
import re
import subprocess

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from app.extensions import db, socketio
from app.models import Book, BorrowRecord, ReturnRecord, SystemLog, log_event
from app.serial_reader import get_bridge, SerialBridge

# Valid RFID UID: 4-byte (8 hex) or 7-byte (14 hex) MIFARE UID
VALID_UID_RE = re.compile(r"^[0-9A-F]{8}$|^[0-9A-F]{14}$")

api_bp = Blueprint("api", __name__)

_terminal_proc = None
_hw_monitor_proc = None
_hw_status = {"connected": False, "port": "", "vid_pid": ""}


@api_bp.route("/stats")
@login_required
def stats():
    return jsonify(
        {
            "total_books": Book.query.count(),
            "available": Book.query.filter_by(status="available").count(),
            "borrowed": Book.query.filter_by(status="borrowed").count(),
            "returns_today": ReturnRecord.query.count(),  # simplified for demo
        }
    )


@api_bp.route("/logs/recent")
@login_required
def recent_logs():
    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(20).all()
    return jsonify(
        [
            {
                "id": log.log_id,
                "type": log.event_type,
                "source": log.source,
                "message": log.message,
                "rfid_uid": log.rfid_uid,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    )


@api_bp.route("/device/status")
@login_required
def device_status():
    bridge = get_bridge()
    connected = bool(bridge and bridge.ser and bridge.ser.is_open)
    return jsonify({"connected": connected})


@api_bp.route("/hw-status", methods=["GET"])
@login_required
def get_hw_status():
    return jsonify(_hw_status)


@api_bp.route("/hw-status", methods=["POST"])
@login_required
def set_hw_status():
    global _hw_status
    data = request.get_json(silent=True) or {}
    _hw_status = {
        "connected": data.get("connected", False),
        "port": data.get("port", ""),
        "vid_pid": data.get("vid_pid", ""),
    }
    socketio.emit("hw_status_update", _hw_status)
    socketio.emit("device_status", {"connected": _hw_status["connected"]})
    return jsonify(_hw_status)


@api_bp.route("/rfid/start-listen", methods=["POST"])
@login_required
def start_rfid_listen():
    bridge = get_bridge()
    if not bridge or not bridge.ser or not bridge.ser.is_open:
        return jsonify({"error": "Arduino not connected"}), 400
    bridge.start_registration_mode()
    return jsonify({"listening": True})


@api_bp.route("/rfid/cancel-listen", methods=["POST"])
@login_required
def cancel_rfid_listen():
    bridge = get_bridge()
    if bridge:
        bridge.cancel_registration_mode()
    return jsonify({"listening": False})


@api_bp.route("/books/check-uid")
@login_required
def check_rfid_uid():
    uid = request.args.get("uid", "").strip().upper()
    exclude_id = request.args.get("exclude_id", type=int)
    if not uid:
        return jsonify({"exists": False})
    if not VALID_UID_RE.match(uid):
        return jsonify({"exists": False, "error": "Invalid UID format"})
    query = Book.query.filter_by(rfid_uid=uid)
    if exclude_id:
        query = query.filter(Book.book_id != exclude_id)
    book = query.first()
    if book:
        return jsonify({"exists": True, "title": book.title, "book_id": book.book_id})
    return jsonify({"exists": False})


@api_bp.route("/books/reassign-tag", methods=["POST"])
@login_required
def reassign_tag():
    """Move an RFID tag from one book to another in a single transaction."""
    data = request.get_json(silent=True) or {}
    uid = data.get("uid", "").strip().upper()
    new_book_id = data.get("new_book_id", type=int)

    if not uid or not new_book_id:
        return jsonify({"error": "uid and new_book_id are required"}), 400

    if not VALID_UID_RE.match(uid):
        return jsonify({"error": "Invalid UID format"}), 400

    new_book = Book.query.get(new_book_id)
    if not new_book:
        return jsonify({"error": "Target book not found"}), 404

    # Find the old book that currently owns this UID
    old_book = Book.query.filter_by(rfid_uid=uid).first()
    if not old_book:
        return jsonify({"error": "No book found with this UID"}), 404

    if old_book.book_id == new_book_id:
        return jsonify({"error": "Tag is already assigned to this book"}), 400

    # Single transaction: clear old, assign new
    old_book.rfid_uid = None
    new_book.rfid_uid = uid
    db.session.commit()

    log_event(
        "WARNING", "DASHBOARD",
        f"RFID tag {uid} reassigned from '{old_book.title}' to '{new_book.title}'",
        rfid_uid=uid,
    )
    return jsonify({
        "reassigned": True,
        "uid": uid,
        "from_title": old_book.title,
        "to_title": new_book.title,
    })


@api_bp.route("/simulate/scan", methods=["POST"])
@login_required
def simulate_scan():
    """Dev helper: simulate an RFID scan without the physical Arduino attached.
    Handy while building the dashboard before the hardware is wired up.
    Not wired to any UI button by default -- call it directly, e.g. with curl,
    or wire a 'Simulate Scan' button in books.html during development.
    """
    if not current_app.config.get("DEBUG_MODE"):
        return jsonify({"error": "Endpoint disabled outside debug mode"}), 403
    uid = request.json.get("uid", "").strip().upper() if request.is_json else ""
    if not uid:
        return jsonify({"error": "uid is required"}), 400

    bridge = get_bridge()
    if bridge is None:
        return jsonify({"error": "Serial bridge not initialized"}), 500

    if bridge.mode == "listening_for_registration":
        bridge.cancel_registration_mode()
        socketio.emit("rfid_registration_scan", {"uid": uid})
        return jsonify({"status": "registered", "uid": uid})

    bridge._handle_rfid_scan(uid)
    return jsonify({"status": "simulated", "uid": uid})


@api_bp.route("/terminal/launch", methods=["POST"])
@login_required
def launch_terminal():
    global _terminal_proc

    if not current_app.config.get("DEBUG_MODE"):
        return jsonify({"error": "Endpoint disabled outside debug mode"}), 403
    if _terminal_proc is not None and _terminal_proc.poll() is None:
        return jsonify({"launched": False, "error": "Terminal already running", "pid": _terminal_proc.pid})

    sim_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sim_terminal.py")
    if not os.path.exists(sim_path):
        return jsonify({"launched": False, "error": "sim_terminal.py not found"}), 404

    try:
        _terminal_proc = subprocess.Popen(
            ["cmd", "/K", "python", sim_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=os.path.dirname(sim_path),
        )
        return jsonify({"launched": True, "pid": _terminal_proc.pid})
    except Exception as e:
        return jsonify({"launched": False, "error": str(e)}), 500


@api_bp.route("/hw-monitor/launch", methods=["POST"])
@login_required
def launch_hw_monitor():
    global _hw_monitor_proc

    if not current_app.config.get("DEBUG_MODE"):
        return jsonify({"error": "Endpoint disabled outside debug mode"}), 403
    if _hw_monitor_proc is not None and _hw_monitor_proc.poll() is None:
        return jsonify({"launched": False, "error": "Hardware monitor already running", "pid": _hw_monitor_proc.pid})

    hw_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "hw_monitor.py")
    if not os.path.exists(hw_path):
        return jsonify({"launched": False, "error": "hw_monitor.py not found"}), 404

    try:
        _hw_monitor_proc = subprocess.Popen(
            ["cmd", "/K", "python", hw_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=os.path.dirname(hw_path),
        )
        return jsonify({"launched": True, "pid": _hw_monitor_proc.pid})
    except Exception as e:
        return jsonify({"launched": False, "error": str(e)}), 500

"""
eBALIK Interactive Terminal Simulator

A standalone CMD window that acts as a Virtual Arduino.
Type RFID UIDs to simulate book returns, and watch the
dashboard at http://localhost:5000 update in real time.

Usage:
    python sim_terminal.py

Commands:
    <uid>       Simulate scanning a book's RFID tag (e.g. 04A1B2C3)
    list        Show all books and their current status
    borrowed    Show only books that are currently borrowed
    reset       Re-borrow all books (reset for another demo run)
    help        Show available commands
    quit        Exit the simulator

Requires: pip install pymysql python-socketio (auto-installed on first run)
"""

import sys
import time
import textwrap
from datetime import datetime, timedelta

try:
    import pymysql
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymysql"])
    import pymysql

try:
    import socketio as sio_module
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-socketio"])
    import socketio as sio_module


# ─── Configuration ──────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "ebalik_db",
    "charset": "utf8mb4",
}

FLASK_URL = "http://localhost:5000"

# Demo borrower names for the reset command
DEMO_BORROWERS = [
    {"name": "Juan Dela Cruz", "id": "STU-2024-001"},
    {"name": "Maria Santos", "id": "STU-2024-002"},
    {"name": "Pedro Reyes", "id": "STU-2024-003"},
    {"name": "Ana Garcia", "id": "STU-2024-004"},
    {"name": "Jose Lim", "id": "STU-2024-005"},
]

# ─── ANSI Colors (safe for Windows 10+ terminals) ──────────────
import os
os.system("")  # enable ANSI escape codes on Windows

C_RESET   = "\033[0m"
C_BOLD    = "\033[1m"
C_DIM     = "\033[2m"
C_RED     = "\033[91m"
C_GREEN   = "\033[92m"
C_YELLOW  = "\033[93m"
C_BLUE    = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN    = "\033[96m"
C_WHITE   = "\033[97m"
C_GRAY    = "\033[90m"


# ─── Database ───────────────────────────────────────────────────
def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def get_all_books(db):
    with db.cursor() as cur:
        cur.execute("SELECT book_id, rfid_uid, title, author, status FROM books ORDER BY book_id")
        return cur.fetchall()


def get_borrowed_books(db):
    with db.cursor() as cur:
        cur.execute("""
            SELECT b.book_id, b.rfid_uid, b.title, b.author,
                   br.borrow_id, br.borrower_name, br.borrower_id,
                   br.borrow_date, br.due_date
            FROM books b
            JOIN borrow_records br ON b.book_id = br.book_id
            WHERE b.status = 'borrowed' AND br.is_returned = 0
            ORDER BY b.book_id
        """)
        return cur.fetchall()


def get_book_by_uid(db, uid):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM books WHERE rfid_uid = %s", (uid.upper(),))
        return cur.fetchone()


def mark_returned(db, book_id, borrow_id, rfid_uid):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with db.cursor() as cur:
        cur.execute("""
            UPDATE borrow_records SET is_returned = 1, returned_at = %s
            WHERE borrow_id = %s
        """, (now, borrow_id))

        cur.execute("""
            UPDATE books SET status = 'available', updated_at = %s
            WHERE book_id = %s
        """, (now, book_id))

        cur.execute("""
            INSERT INTO return_records (book_id, borrow_id, rfid_uid, returned_at, verified_by_sensors)
            VALUES (%s, %s, %s, %s, 1)
        """, (book_id, borrow_id, rfid_uid, now))

        cur.execute("""
            INSERT INTO system_logs (event_type, source, message, rfid_uid, created_at)
            VALUES ('INFO', 'ARDUINO_SIM', %s, %s, %s)
        """, (f"Book returned: {rfid_uid}", rfid_uid, now))

    db.commit()
    return now


def re_borrow_all(db):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    due = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")

    books = get_all_books(db)
    borrowed_count = 0

    with db.cursor() as cur:
        for i, book in enumerate(books):
            if book["status"] == "borrowed":
                continue

            borrower = DEMO_BORROWERS[i % len(DEMO_BORROWERS)]

            cur.execute("""
                INSERT INTO borrow_records (book_id, borrower_name, borrower_id, borrow_date, due_date, is_returned)
                VALUES (%s, %s, %s, %s, %s, 0)
            """, (book["book_id"], borrower["name"], borrower["id"], now, due))

            cur.execute("""
                UPDATE books SET status = 'borrowed', updated_at = %s
                WHERE book_id = %s
            """, (now, book["book_id"]))

            borrowed_count += 1

        # Clean up old return records so stats reset nicely
        cur.execute("DELETE FROM return_records")
        cur.execute("""
            UPDATE system_logs SET event_type = 'INFO', source = 'SYSTEM',
            message = 'Database reset for demo', rfid_uid = NULL, created_at = %s
        """, (now,))

    db.commit()
    return borrowed_count


# ─── Socket.IO ──────────────────────────────────────────────────
def connect_socketio():
    client = sio_module.Client()
    try:
        client.connect(FLASK_URL)
        return client
    except Exception:
        return None


def emit_event(client, event, data):
    if client and client.connected:
        try:
            client.emit(event, data)
            return True
        except Exception:
            pass
    return False


# ─── Display ────────────────────────────────────────────────────
BANNER = r"""
  +----------------------------------------------------------+
  |                                                          |
  |     ####  ###### #####  ####  #####  ####  #####  #   # |
  |     #   # #        #    #    # #   # #   # #   #  # #   |
  |     ####  ####     #    #    # ##### ####  #####   #    |
  |     #  #  #        #    #    # #     #  #  #       #    |
  |     #   # ######   #     ####  #     #   # #       #    |
  |                                                          |
  |          Book Automated Library Inventory Keeper         |
  |              Interactive Terminal Simulator               |
  |                                                          |
  +----------------------------------------------------------+
"""

HELP_TEXT = """
  Commands:
    <uid>       Scan an RFID tag (e.g. 04A1B2C3)
    list        Show all books and their status
    borrowed    Show currently borrowed books
    reset       Re-borrow all books for another demo
    help        Show this help message
    quit        Exit the simulator
"""


def log_arduino(msg):
    print(f"  {C_BLUE}[Arduino]{C_RESET}  {msg}")


def log_server(msg):
    print(f"  {C_GREEN}[Server]{C_RESET}   {msg}")


def log_dash(msg):
    print(f"  {C_MAGENTA}[Dashboard]{C_RESET} {msg}")


def log_ok(msg):
    print(f"  {C_GREEN}[OK]{C_RESET} {msg}")


def log_warn(msg):
    print(f"  {C_YELLOW}[WARN]{C_RESET} {msg}")


def log_err(msg):
    print(f"  {C_RED}[ERR]{C_RESET} {msg}")


def print_book_row(book, idx=None):
    prefix = f"  {C_CYAN}{idx:2d}{C_RESET}  " if idx is not None else "  "
    status_color = C_GREEN if book["status"] == "available" else C_YELLOW
    status_label = book["status"].upper()
    print(f"{prefix}{book['rfid_uid']}  {status_color}{status_label:<10s}{C_RESET} {book['title']}")


# ─── Core simulation ────────────────────────────────────────────
def simulate_return(db, sio, uid):
    uid = uid.strip().upper()
    book = get_book_by_uid(db, uid)

    print()
    log_arduino(f"RFID,{uid}")

    if not book:
        log_err(f"Unknown tag: {uid}")
        log_dash(f"Invalid tag scanned ({uid})")
        emit_event(sio, "scan_result", {"uid": uid, "valid": False, "reason": "UNKNOWN_TAG"})
        return

    if book["status"] != "borrowed":
        log_warn(f"'{book['title']}' is not borrowed (status: {book['status']})")
        log_dash(f"Scan rejected: not borrowable ({uid})")
        emit_event(sio, "scan_result", {"uid": uid, "valid": False, "reason": "NOT_BORROWED", "title": book["title"]})
        return

    borrowed = get_borrowed_books(db)
    borrow_rec = next((b for b in borrowed if b["rfid_uid"] == uid), None)

    if not borrow_rec:
        log_warn(f"No active borrow record for '{book['title']}'")
        log_dash(f"Scan rejected: no borrow record ({uid})")
        emit_event(sio, "scan_result", {"uid": uid, "valid": False, "reason": "NO_BORROW_RECORD", "title": book["title"]})
        return

    # Step 1: VALID
    time.sleep(0.4)
    log_server(f"VALID,{uid}  -- \"{book['title']}\"")
    emit_event(sio, "scan_result", {
        "uid": uid,
        "valid": True,
        "title": book["title"],
        "borrower": borrow_rec["borrower_name"],
    })

    # Step 2: Sensor sequence
    time.sleep(0.5)
    log_arduino("STATUS,ENTRANCE_DETECTED")
    emit_event(sio, "hardware_status", {"status": "ENTRANCE_DETECTED"})

    time.sleep(0.6)
    log_arduino("STATUS,FULL_ENTRY")
    emit_event(sio, "hardware_status", {"status": "FULL_ENTRY"})

    time.sleep(0.5)
    log_arduino("STATUS,SLOT_CLOSED")
    emit_event(sio, "hardware_status", {"status": "SLOT_CLOSED"})

    # Step 3: RETURN_SUCCESS + DB update
    time.sleep(0.3)
    returned_at = mark_returned(db, book["book_id"], borrow_rec["borrow_id"], uid)
    log_arduino(f"RETURN_SUCCESS,{uid}")

    emit_event(sio, "book_returned", {
        "uid": uid,
        "title": book["title"],
        "borrower": borrow_rec["borrower_name"],
        "returned_at": returned_at,
    })

    log_dash(f"Live update sent -- \"{book['title']}\" returned!")
    print()
    log_ok(f"\"{book['title']}\" returned by {borrow_rec['borrower_name']} at {returned_at}")
    print()


def cmd_list(db):
    books = get_all_books(db)
    borrowed = sum(1 for b in books if b["status"] == "borrowed")
    available = sum(1 for b in books if b["status"] == "available")

    print()
    print(f"  {C_BOLD}All Books{C_RESET}  ({len(books)} total, {C_GREEN}{available} available{C_RESET}, {C_YELLOW}{borrowed} borrowed{C_RESET})")
    print(f"  {'UID':<12s} {'Status':<12s} Title")
    print(f"  {'-'*12} {'-'*12} {'-'*30}")
    for i, book in enumerate(books, 1):
        print_book_row(book, i)
    print()


def cmd_borrowed(db):
    books = get_borrowed_books(db)
    print()
    if not books:
        print(f"  {C_YELLOW}No borrowed books.{C_RESET} Run {C_CYAN}reset{C_RESET} to borrow all books for a demo.")
        print()
        return

    print(f"  {C_BOLD}Borrowed Books{C_RESET}  ({len(books)} can be returned)")
    print(f"  {'UID':<12s} {'Borrower':<20s} Title")
    print(f"  {'-'*12} {'-'*20} {'-'*30}")
    for i, book in enumerate(books, 1):
        print(f"  {C_CYAN}{i:2d}{C_RESET}  {book['rfid_uid']}  {book['borrower_name']:<20s} {book['title']}")
    print()
    print(f"  Type a UID to return a book.")
    print()


def cmd_reset(db):
    count = re_borrow_all(db)
    print()
    log_ok(f"Reset complete. {count} books re-borrowed for demo.")
    print()
    cmd_borrowed(db)


# ─── Main loop ──────────────────────────────────────────────────
def main():
    # Enable ANSI on Windows
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

    print(BANNER)

    # Connect to DB
    try:
        db = get_db()
        print(f"  {C_GREEN}[OK]{C_RESET} Connected to MySQL (ebalik_db)")
    except Exception as e:
        print(f"  {C_RED}[ERR]{C_RESET} Cannot connect to MySQL: {e}")
        print(f"  Make sure MySQL is running on localhost:3306")
        input("\n  Press Enter to exit...")
        sys.exit(1)

    # Connect to Flask Socket.IO
    print(f"  {C_DIM}Connecting to Flask at {FLASK_URL}...{C_RESET}", end="", flush=True)
    sio = connect_socketio()
    if sio:
        print(f"\r  {C_GREEN}[OK]{C_RESET} Connected to Flask dashboard           ")
    else:
        print(f"\r  {C_YELLOW}[WARN]{C_RESET} Flask not reachable -- dashboard won't update live")
        print(f"  {C_DIM}Start Flask first: python run.py{C_RESET}")

    # Show initial state
    cmd_borrowed(db)

    # REPL
    print(f"  {C_DIM}Type a UID to scan, 'help' for commands, 'quit' to exit{C_RESET}")
    print()

    while True:
        try:
            raw = input(f"  {C_CYAN}eBALIK>{C_RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("quit", "exit", "q"):
            print()
            log_ok("Simulator shutting down. Goodbye!")
            break

        elif cmd == "help":
            print(HELP_TEXT)

        elif cmd == "list":
            cmd_list(db)

        elif cmd == "borrowed":
            cmd_borrowed(db)

        elif cmd == "reset":
            cmd_reset(db)

        elif len(raw) >= 4 and all(c in "0123456789abcdefABCDEF" for c in raw):
            # Looks like an RFID UID
            simulate_return(db, sio, raw)

        else:
            print(f"  {C_YELLOW}Unknown command.{C_RESET} Type 'help' for available commands.")

    # Cleanup
    try:
        if sio and sio.connected:
            sio.disconnect()
    except Exception:
        pass
    try:
        db.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()

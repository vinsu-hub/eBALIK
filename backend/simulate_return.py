"""
eBALIK Return Simulator

Simulates the full book return cycle without the physical Arduino.
Connects directly to MySQL and emits Socket.IO events so the
dashboard updates live in real time.

Usage:
    python simulate_return.py                  # interactive mode
    python simulate_return.py --uid 04A1B2C3  # single simulation
    python simulate_return.py --auto           # auto-simulate all borrowed books

Requires: pip install pymysql python-socketio requests
"""

import sys
import time
import argparse
from datetime import datetime

try:
    import pymysql
except ImportError:
    print("Installing pymysql...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymysql"])
    import pymysql

try:
    import socketio
except ImportError:
    print("Installing python-socketio...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-socketio"])
    import socketio

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


# ─── Configuration ──────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "ebalik_db",
    "charset": "utf8mb4",
}

FLASK_URL = "http://localhost:5001"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


# ─── Database helpers ───────────────────────────────────────────
def get_db():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def get_borrowed_books(db):
    with db.cursor() as cur:
        cur.execute("""
            SELECT b.book_id, b.rfid_uid, b.title, b.author,
                   br.borrow_id, br.borrower_name, br.borrower_id, br.borrow_date, br.due_date
            FROM books b
            JOIN borrow_records br ON b.book_id = br.book_id
            WHERE b.status = 'borrowed' AND br.is_returned = 0
            ORDER BY br.borrow_date ASC
        """)
        return cur.fetchall()


def get_all_books(db):
    with db.cursor() as cur:
        cur.execute("SELECT book_id, rfid_uid, title, status FROM books ORDER BY book_id")
        return cur.fetchall()


def mark_returned(db, book_id, borrow_id, rfid_uid):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with db.cursor() as cur:
        # Close the borrow record
        cur.execute("""
            UPDATE borrow_records
            SET is_returned = 1, returned_at = %s
            WHERE borrow_id = %s
        """, (now, borrow_id))

        # Update book status
        cur.execute("""
            UPDATE books SET status = 'available', updated_at = %s
            WHERE book_id = %s
        """, (now, book_id))

        # Create return record
        cur.execute("""
            INSERT INTO return_records (book_id, borrow_id, rfid_uid, returned_at, verified_by_sensors)
            VALUES (%s, %s, %s, %s, 1)
        """, (book_id, borrow_id, rfid_uid, now))

        # Log the event
        cur.execute("""
            INSERT INTO system_logs (event_type, source, message, rfid_uid, created_at)
            VALUES ('INFO', 'SIMULATOR', 'Book returned via simulation', %s, %s)
        """, (rfid_uid, now))

    db.commit()
    return now


# ─── Socket.IO notification ─────────────────────────────────────
def notify_dashboard(title, borrower, rfid_uid, returned_at):
    try:
        sio = socketio.Client()
        sio.connect(FLASK_URL)
        sio.emit("book_returned", {
            "uid": rfid_uid,
            "title": title,
            "borrower": borrower,
            "returned_at": returned_at,
        })
        time.sleep(0.5)
        sio.disconnect()
        return True
    except Exception as e:
        print(f"  [!] Could not notify dashboard via Socket.IO: {e}")
        return False


# ─── HTTP fallback notification ──────────────────────────────────
def notify_via_http(title, borrower, rfid_uid, returned_at):
    try:
        session = requests.Session()
        # Login
        session.post(f"{FLASK_URL}/login", data={
            "username": ADMIN_USER,
            "password": ADMIN_PASS,
        })
        # The dashboard will show the updated data on next page load
        return True
    except Exception as e:
        print(f"  [!] HTTP fallback failed: {e}")
        return False


# ─── Print helpers ──────────────────────────────────────────────
def print_banner():
    print("""
+============================================================+
|           eBALIK Return Simulator v1.0                      |
|   Simulates book returns without physical Arduino hardware  |
+============================================================+
    """)


def print_section(title):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")


def print_book(book, idx=None):
    prefix = f"  [{idx}] " if idx is not None else "  "
    print(f"{prefix}{book['title']}")
    print(f"       RFID: {book['rfid_uid']}  |  Borrower: {book['borrower_name']}")
    print(f"       Borrowed: {book['borrow_date']}  |  Due: {book['due_date']}")


def print_result(book, returned_at, notified):
    status = "LIVE" if notified else "DB ONLY"
    print(f"\n  [OK] RETURN COMPLETE")
    print(f"     Book:    {book['title']}")
    print(f"     UID:     {book['rfid_uid']}")
    print(f"     Time:    {returned_at}")
    print(f"     Status:  [{status}] {'Dashboard updated!' if notified else 'Refresh dashboard to see changes'}")


def print_sim_log(msg):
    print(f"  >> {msg}")


# ─── Main simulation flow ───────────────────────────────────────
def simulate_single(db, book):
    """Simulate the full return cycle for one book."""
    print_section(f"Simulating return: {book['title']}")

    print_sim_log(f"RFID scan detected: {book['rfid_uid']}")
    time.sleep(0.3)

    print_sim_log(f"Validating book in database...")
    print_sim_log(f"  Book found: '{book['title']}'")
    print_sim_log(f"  Borrower: {book['borrower_name']}")
    print_sim_log(f"  Status: borrowed -> VALID")
    time.sleep(0.3)

    print_sim_log(f"Opening return slot (servo -> 80 deg)")
    time.sleep(0.3)

    print_sim_log(f"IR Entrance: book detected")
    time.sleep(0.2)

    print_sim_log(f"IR Full Entry: book fully inserted")
    time.sleep(0.2)

    print_sim_log(f"Closing warning: book received, closing shortly...")
    time.sleep(0.2)

    print_sim_log(f"Closing return slot (servo -> 10 deg)")
    time.sleep(0.2)

    print_sim_log(f"Updating database...")
    returned_at = mark_returned(
        db, book['book_id'], book['borrow_id'], book['rfid_uid']
    )
    print_sim_log(f"  borrow_records.is_returned = 1")
    print_sim_log(f"  books.status = 'available'")
    print_sim_log(f"  return_records: new row added")
    print_sim_log(f"  system_logs: INFO entry added")

    print_sim_log(f"Notifying dashboard via Socket.IO...")
    notified = notify_dashboard(
        book['title'], book['borrower_name'],
        book['rfid_uid'], returned_at
    )

    print_result(book, returned_at, notified)
    return True


def interactive_mode(db):
    """Let user pick which book to return."""
    while True:
        print_section("Borrowed Books (can be returned)")

        borrowed = get_borrowed_books(db)
        if not borrowed:
            print("  No borrowed books left to return!")
            break

        for i, book in enumerate(borrowed, 1):
            print_book(book, i)

        print(f"\n  [0] Exit")
        print(f"  [R] Refresh list")

        choice = input("\n  Select book number to return: ").strip()

        if choice == "0" or choice.lower() == "q":
            print("\n  Goodbye!")
            break
        if choice.lower() == "r":
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(borrowed):
                simulate_single(db, borrowed[idx])
            else:
                print("  Invalid selection.")
        except ValueError:
            print("  Enter a number.")


def auto_mode(db):
    """Return all borrowed books one by one."""
    borrowed = get_borrowed_books(db)
    if not borrowed:
        print("  No borrowed books to return!")
        return

    print(f"  Found {len(borrowed)} borrowed book(s). Simulating all returns...\n")

    for i, book in enumerate(borrowed, 1):
        print(f"\n  -- Return {i}/{len(borrowed)} --")
        simulate_single(db, book)
        time.sleep(1)

    print_section("All returns complete!")
    print("  Open http://localhost:5001 to see the updated dashboard.")


def single_mode(db, uid):
    """Return a specific book by RFID UID."""
    borrowed = get_borrowed_books(db)
    match = next((b for b in borrowed if b['rfid_uid'].upper() == uid.upper()), None)

    if not match:
        print(f"  No borrowed book found with UID: {uid}")
        print("  Available borrowed UIDs:")
        for b in borrowed:
            print(f"    - {b['rfid_uid']} ({b['title']})")
        return

    simulate_single(db, match)


# ─── Entry point ────────────────────────────────────────────────
def main():
    print_banner()

    parser = argparse.ArgumentParser(description="eBALIK Return Simulator")
    parser.add_argument("--uid", help="RFID UID to simulate return for")
    parser.add_argument("--auto", action="store_true", help="Auto-return all borrowed books")
    parser.add_argument("--host", default=DB_CONFIG["host"], help="MySQL host")
    parser.add_argument("--port", type=int, default=DB_CONFIG["port"], help="MySQL port")
    parser.add_argument("--user", default=DB_CONFIG["user"], help="MySQL user")
    parser.add_argument("--password", default=DB_CONFIG["password"], help="MySQL password")
    args = parser.parse_args()

    DB_CONFIG["host"] = args.host
    DB_CONFIG["port"] = args.port
    DB_CONFIG["user"] = args.user
    DB_CONFIG["password"] = args.password

    try:
        db = get_db()
        print("  Connected to MySQL database 'ebalik_db'\n")
    except Exception as e:
        print(f"  ERROR: Could not connect to MySQL: {e}")
        print("  Make sure MySQL is running on localhost:3306")
        sys.exit(1)

    try:
        if args.auto:
            auto_mode(db)
        elif args.uid:
            single_mode(db, args.uid)
        else:
            interactive_mode(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()

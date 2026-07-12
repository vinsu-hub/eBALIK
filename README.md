# eBALIK — Book Automated Library Inventory Keeper

An RFID-based automated book return station: Arduino Uno R3 handles the
physical hardware (RFID reader, servo-controlled slot, IR sensors, LCD,
buzzer), and talks over USB Serial to a local Flask + MySQL web dashboard
that librarians use to manage the catalog and watch returns happen live.

This zip is a **working scaffold**, not a finished product — it's built so
you can open it in Claude Code and keep building from here (wiring it to
your exact pin layout, styling the dashboard further, adding borrower
accounts, etc).

## What's included

```
eBALIK/
├── arduino/eBALIK_arduino/eBALIK_arduino.ino   Arduino firmware
├── backend/                                     Flask + MySQL web app
│   ├── app/
│   │   ├── models.py            SQLAlchemy models (books, borrow, return, logs, users)
│   │   ├── serial_reader.py     Background thread bridging Arduino <-> DB <-> dashboard
│   │   ├── routes/               auth.py, dashboard.py, books.py, api.py
│   │   ├── templates/            Bootstrap 5 dashboard pages
│   │   └── static/               CSS + JS (incl. Socket.IO live updates)
│   ├── schema.sql                Run this first to create the database
│   ├── seed_data.sql             Optional demo data
│   ├── create_admin.py           Creates your first login with a real password hash
│   ├── requirements.txt
│   ├── .env.example              Copy to .env and fill in your values
│   └── run.py                    Entry point
└── docs/PROTOCOL.md              Serial protocol spec (Arduino <-> Flask)
```

## 1. Set up MySQL

```bash
mysql -u root -p < backend/schema.sql
mysql -u root -p < backend/seed_data.sql   # optional demo data
```

## 2. Set up the Flask backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env: set DB_PASSWORD, and SERIAL_PORT to match your Arduino
# (Windows: COM3 / COM4 ... check Device Manager or the Arduino IDE)
# (Linux: /dev/ttyUSB0 or /dev/ttyACM0)
# (macOS: /dev/cu.usbserial-XXXX)

python create_admin.py          # creates your first login
python run.py                   # starts the server on http://localhost:5000
```

If you don't have the Arduino plugged in yet, set `SERIAL_ENABLED=false`
in `.env` so the dashboard still runs without erroring out on the serial
port.

## 3. Upload the Arduino firmware

Open `arduino/eBALIK_arduino/eBALIK_arduino.ino` in the Arduino IDE.

Install these libraries via **Sketch > Include Library > Manage Libraries**:
- `MFRC522` (by GithubCommunity / miguelbalboa)
- `LiquidCrystal I2C` (by Frank de Brabander, or similar)
- `Servo` (usually bundled with the IDE already)

Check the pin definitions at the top of the `.ino` file match your wiring,
then upload to the Arduino Uno R3. Close the Arduino IDE's Serial Monitor
before starting the Flask app — only one program can hold the serial port
at a time.

## 4. Log in

Visit `http://localhost:5000`, log in with the account you created in
`create_admin.py`, and you should see the dashboard. Scan an RFID-tagged
book that has an open borrow record and watch the "Live System Log" and
"Recent Returns" panels update in real time as the Arduino works through
its state machine.

## How the pieces talk to each other

See `docs/PROTOCOL.md` for the full serial message spec. Short version:

1. Arduino scans a tag → sends `RFID,<uid>` over serial.
2. Flask looks up the book, checks it has an open borrow record, replies
   `VALID,<uid>` or `INVALID,<uid>`.
3. Arduino opens the servo, watches its 3 IR sensors (entrance → full
   entry → obstruction-clear), then closes the slot and sends
   `RETURN_SUCCESS,<uid>`.
4. Flask marks the borrow record returned, logs a `return_records` row,
   updates the book's status, and broadcasts the event over Socket.IO so
   the dashboard updates without a refresh.

## Deploying for the demo (local laptop)

Since this is meant to run locally on the demo laptop rather than a public
server:

1. `git clone` this repo onto the laptop.
2. Install MySQL Server on the laptop, run `schema.sql` (+ `seed_data.sql`).
3. Follow steps 2–3 above on that machine, plugging the Arduino into the
   same laptop running Flask.
4. `python run.py` and open `http://localhost:5000` in the browser on that
   laptop for the panel to see.

No internet connection is required at demo time except for loading
Bootstrap/Socket.IO from CDN in `base.html` — if your venue has no wifi,
download those two libraries locally ahead of time and swap the `<link>`/
`<script>` tags in `app/templates/base.html` to point at local files under
`app/static/vendor/`.

## Suggested next steps to build out in Claude Code

- Wire the real pin numbers/I2C address once your circuit is finalized.
- Add a "Users" management page (the `users` table + role field already
  exist in the schema).
- Add password-protected roles (admin vs librarian permissions).
- Add a borrower-facing kiosk view showing only "scan your book" status.
- Add automated tests for `serial_reader.py`'s parsing logic (it's pure
  string parsing + DB calls, easy to unit test with a fake serial port).
- Package the whole thing with a `docker-compose.yml` (Flask + MySQL) if
  you want a one-command local deploy — the Arduino serial port would
  still need to be passed through to the container, which is finicky on
  Windows, so this is optional for a local defense demo.

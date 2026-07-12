# eBALIK: Book Automated Library Inventory Keeper
### An RFID-Based Automated Book Return Station — Project Reference

> This document consolidates the full project specification (from the original
> project identity PDF) into a single Markdown file for use as context when
> working on this codebase in Claude Code.

---

## 1. Project Identity

**System Name:** eBALIK: Book Automated Library Inventory Keeper – An
RFID-Based Automated Book Return Station

**Classification:** Embedded System with Web-Based Library Management
Integration

**Primary Function:** To automate the library book return process by
verifying the successful deposit of RFID-tagged books using multiple sensors
and automatically updating the library inventory database.

### System Objectives

- To automate the verification of returned library books.
- To ensure that books are fully deposited before confirming a successful
  return.
- To prevent false return records through multi-sensor validation.
- To automatically update the library inventory database after successful
  verification.
- To provide users with real-time feedback through an LCD display and buzzer
  notifications.
- To improve the efficiency, accuracy, and security of the book return
  process.

---

## 2. System Architecture

```
Librarian/Student (User)
  → scans RFID-tagged book →
RFID RC522 Reader
  → USB Serial →
Arduino Uno R3
  → USB Serial / HTTP →
Flask Web Application
  → MySQL Database
  → Library Management Dashboard (Admin / Librarian)

Arduino Uno R3 also directly controls:
  - Servo Motor        (Open / Close Return Slot)
  - IR Sensor 1         (Entrance Detection)
  - IR Sensor 2         (Full Entry Detection)
  - IR Sensor 3         (Safety Obstruction Detection)
  - LCD Display         (User Feedback)
  - Buzzer              (Audible Alert)
```

Data/control flow: User → RFID Reader → Arduino → Flask → MySQL → Dashboard.
Hardware control flow: Arduino directly drives the servo, 3 IR sensors, LCD,
and buzzer.

---

## 3. Major Components

| Category | Component | Description / Function |
|---|---|---|
| Embedded Hardware | Arduino Uno R3 | Main microcontroller that controls all hardware components and executes the return process. |
| Embedded Hardware | RFID Reader | Reads the RFID tag attached to each library book. |
| Embedded Hardware | RFID-tagged Book | Provides a unique identification number for every library book. |
| Embedded Hardware | Servo Motor | Opens and closes the return slot automatically. |
| Embedded Hardware | IR Sensor (Entrance Detection) | Detects when a book enters the return slot. |
| Embedded Hardware | IR Sensor (Full Entry Detection) | Confirms that the book has completely entered the return container. |
| Embedded Hardware | IR Sensor (Safety Obstruction Detection) | Detects hands or objects blocking the slot before closing. |
| Embedded Hardware | LCD Display | Displays system instructions, notifications, and transaction status. |
| Embedded Hardware | Buzzer | Provides audible confirmation of successful returns or alerts. |
| Backend Software | Flask Web Application | Processes RFID requests, communicates with Arduino, and manages library transactions. |
| Database | MySQL Database | Stores book information, borrowing records, and return status. |

---

## 4. System Modules

1. **RFID Authentication Module** — Reads the RFID tag and verifies whether
   the scanned book exists in the database and is currently borrowed.
2. **Book Validation Module** — Checks the borrowing status of the scanned
   book before allowing the return process.
3. **Return Slot Control Module** — Controls the servo motor to automatically
   open and close the return slot.
4. **Book Entry Verification Module** — Uses multiple IR sensors to verify
   that the book has entered and fully passed into the return container.
5. **Safety Monitoring Module** — Uses the obstruction sensor to prevent the
   return slot from closing while an object or hand is detected.
6. **Database Management Module** — Updates the return status only after
   successful verification of the deposited book.
7. **User Notification Module** — Displays messages on the LCD and activates
   the buzzer for confirmations and warnings.

---

## 5. Operation Workflow

1. The user scans the RFID tag attached to the book.
2. The Flask application checks the MySQL database to verify that the book
   exists and is currently borrowed.
3. If valid, the Arduino activates the servo motor to open the return slot.
4. The LCD instructs the user to insert the book.
5. The entrance IR sensor detects that the book has been inserted.
6. The full-entry IR sensor confirms that the book has completely entered
   the return container.
7. The safety IR sensor checks whether any obstruction remains before
   allowing the slot to close.
8. If no obstruction is detected, the servo closes the slot.
9. The Flask application updates the MySQL database, marking the book as
   returned.
10. The LCD displays a success message and the buzzer provides audible
    confirmation.
11. If any validation fails (timeout, invalid RFID, incomplete insertion, or
    obstruction), the system cancels the transaction and resets.

### Returning Process (condensed)

1. Scan the RFID-tagged book.
2. Validate the book information in the database.
3. Open the return slot automatically.
4. User inserts the book.
5. Entrance IR sensor detects the book.
6. Full-entry IR sensor confirms complete deposit.
7. Safety IR sensor checks for any obstruction.
8. Close the return slot.
9. Update the database to indicate that the book has been returned.
10. Display a success message on the LCD and sound the buzzer.

---

## 6. Advantages over Traditional Book Return

| Traditional Book Return | Automated Book Return Station |
|---|---|
| Requires manual verification by librarians. | Automatically verifies the returned book. |
| Inventory updates are performed manually. | Inventory is updated automatically in real time. |
| Human error may result in incorrect return records. | Multi-sensor validation reduces errors and false return confirmations. |
| No confirmation that the book was fully deposited. | Dual IR sensors verify complete book insertion before updating records. |
| Staff must physically monitor the return process. | Automated monitoring minimizes staff workload. |
| Users receive little or no immediate feedback. | LCD messages and buzzer provide instant status updates. |
| Return slot may close while obstructed. | Safety sensor prevents accidental closure when an obstruction is detected. |

---

## 7. Electronic Components (Bill of Materials)

| Component | Specification | Quantity | Function |
|---|---|---|---|
| Arduino Uno R3 | ATmega328P, 5V, 16 MHz | 1 | Main microcontroller that controls all hardware components and communicates with the backend. |
| RFID Reader | RC522, 13.56 MHz | 1 | Reads the RFID UID attached to each library book. |
| RFID Tags | 13.56 MHz RFID Sticker/Card | 5–10 | Unique identifier attached to books. |
| Servo Motor | SG90 Micro Servo, 5V | 1 | Opens and closes the return slot. |
| IR Sensor (Entrance Detection) | Infrared Obstacle Sensor, 3.3–5V | 1 | Detects when the book enters the return slot. |
| IR Sensor (Full Entry Detection) | Infrared Obstacle Sensor, 3.3–5V | 1 | Confirms the book has completely entered the return container. |
| IR Sensor (Safety Obstruction Detection) | Infrared Obstacle Sensor, 3.3–5V | 1 | Detects hands or objects blocking the slot before closing. |
| LCD Display | 16×2 LCD with I2C Module | 1 | Displays instructions and system status. |
| Buzzer | Active Buzzer, 5V | 1 | Provides audible alerts and confirmation sounds. |
| Breadboard | 830 Tie-Point | 1 | Used for circuit prototyping. |
| Jumper Wires | Male-to-Male / Male-to-Female | 1 set | Electrical connections between components. |
| USB Cable | USB Type-B | 1 | Connects Arduino to the host computer. |
| Power Supply | 5V DC Adapter or USB Power | 1 | Powers the Arduino and peripheral devices. |

## 8. Structural Materials

| Material | Specification | Quantity |
|---|---|---|
| Corrugated Cardboard | Double-wall cardboard | 2 sheets |
| Foam Board (Optional) | 5 mm thickness | 1 sheet |
| Acrylic Sheet (Optional) | 3 mm clear acrylic | 1 piece |
| Hinges | Small metal hinges | 2 |
| Screws | M3 Assorted | 1 pack |
| Hot Glue Sticks | Standard size | 10 pieces |
| Double-sided Tape | Heavy-duty | 1 roll |
| Cable Ties | 100 mm | 1 pack |
| Paint / Vinyl Sticker | Optional finishing | As needed |

---

## 9. Host Computer Requirements

| Item | Minimum Specification |
|---|---|
| Operating System | Windows 10 (64-bit), Ubuntu 22.04, or macOS 12+ |
| Processor | Intel Core i3 (8th Gen) / AMD Ryzen 3 or higher |
| Memory (RAM) | 8 GB |
| Storage | 20 GB Available SSD/HDD Space |
| USB Port | USB 2.0 or USB 3.0 |
| Internet Connection | Required for installing software packages (optional during operation) |
| Display | 1366 × 768 Resolution |

## 10. Software Environment

| Software | Version | Purpose |
|---|---|---|
| Arduino IDE | 2.x | Programming and uploading code to Arduino Uno. |
| Python | 3.11 or later | Executes the Flask backend application. |
| Flask | 3.x | Backend web framework for processing requests. |
| MySQL Server | 8.x | Stores book records and return transactions. |
| MySQL Workbench | 8.x | Database administration and management. |
| Visual Studio Code | Latest | Source code development. |
| Git | Latest | Version control (optional). |
| Web Browser | Google Chrome / Microsoft Edge | Accesses the library dashboard. |

---

## 11. Database Components (Tables)

| Table | Purpose |
|---|---|
| `books` | Stores book information including RFID UID, title, author, accession number, and availability status. |
| `borrow_records` | Stores borrowing transactions including borrower, borrow date, due date, and return status. |
| `return_records` | Records successful book return transactions with timestamps. |
| `users` | Stores librarian and authorized user accounts. |
| `system_logs` | Logs system activities, errors, and hardware events for monitoring and troubleshooting. |

> The current implementation of this schema lives in `backend/schema.sql`,
> and matches the table purposes above (with added fields such as
> `status` enum on `books`, and `event_type`/`source` on `system_logs` for
> clearer log filtering).

---

## 12. Notes for Implementation (Claude Code context)

- **Serial protocol** between the Arduino and Flask backend is documented in
  `docs/PROTOCOL.md` — this is the contract both sides rely on, so keep it in
  sync if the message format changes.
- **Pin assignments** in `arduino/eBALIK_arduino/eBALIK_arduino.ino` are
  placeholders and should be updated to match the actual wiring/breadboard
  layout once finalized.
- **IR sensor active state** (`LOW` vs `HIGH` on trigger) depends on the exact
  obstacle sensor module used — verify and adjust `IR_ACTIVE_STATE` in the
  firmware accordingly.
- **Dashboard live updates** use Flask-SocketIO so librarians see scan
  results, hardware status (entrance/full-entry/obstruction), and completed
  returns in real time without refreshing the page.
- **Local deployment target:** this is meant to run entirely on the demo
  laptop (Flask + MySQL + Arduino over USB), not a public server, per the
  Host Computer Requirements above.

# eBALIK Serial Protocol

The Arduino and the Flask backend talk over USB Serial at **115200 baud**,
one message per line (`\n` terminated), comma-separated fields.

## Arduino -> PC

| Message                          | Meaning                                              |
|-----------------------------------|-------------------------------------------------------|
| `HELLO,EBALIK,<version>`          | Sent on boot and in reply to `PING`                   |
| `RFID,<uid>`                      | A card was scanned, backend must validate it           |
| `STATUS,ENTRANCE_DETECTED`        | Book is entering the slot                              |
| `STATUS,FULL_ENTRY`               | Book has fully entered the container                   |
| `STATUS,SLOT_CLOSED`              | Slot has closed safely                                 |
| `RETURN_SUCCESS,<uid>`            | Full return cycle completed successfully                |
| `RETURN_FAILED,<uid>,<reason>`    | Cycle aborted. Reasons: `PC_TIMEOUT`, `INSERT_TIMEOUT`, `INCOMPLETE_ENTRY` |

## PC -> Arduino

| Message           | Meaning                                             |
|--------------------|------------------------------------------------------|
| `VALID,<uid>`      | Book exists and is currently borrowed -> open the slot |
| `INVALID,<uid>,<reason>` | Book not found / not borrowed -> reject. Reasons: `UNKNOWN_TAG`, `NOT_BORROWED`, `MALFORMED_UID` |
| `PING`             | Ask Arduino to identify itself                        |
| `RESET`            | Force the state machine back to `IDLE`                |

## Backend responsibilities on `RFID,<uid>`

1. Look up `uid` in `books`.
2. If not found -> reply `INVALID,<uid>,UNKNOWN_TAG`, log to `system_logs`.
3. If found but not currently borrowed (no open `borrow_records` row) ->
   reply `INVALID,<uid>,NOT_BORROWED`, log to `system_logs`.
4. If found and borrowed -> reply `VALID,<uid>`.
5. On `RETURN_SUCCESS,<uid>` -> close the matching `borrow_records` row
   (`is_returned = 1`), insert a row into `return_records`, set
   `books.status = 'available'`, log to `system_logs`, and push a
   `book_returned` event to the dashboard over Socket.IO.
6. On `RETURN_FAILED,<uid>,<reason>` -> log the failure to `system_logs`
   and push a `return_failed` event to the dashboard.

## State machine notes

- The system uses **2 IR sensors** (Entrance, Full-Entry). The previous third
  sensor (Safety Obstruction, pin 4) has been removed. In its place, a timed
  `STATE_CLOSING_WARNING` gives a 2-second LCD message ("Book received! /
  Closing shortly") with a double mid-tone buzzer pulse before the servo
  closes. This is a timed warning, **not** sensor-verified clearance.
- `STATUS,OBSTRUCTION` and `RETURN_FAILED,<uid>,OBSTRUCTION_TIMEOUT` no
  longer exist and will never be sent by the firmware.
- After `STATUS,FULL_ENTRY`, the Arduino enters `CLOSING_WARNING` (2s), then
  immediately transitions to `CLOSING` (sends `RETURN_SUCCESS`). The backend
  sees `STATUS,FULL_ENTRY` followed by `STATUS,SLOT_CLOSED` with ~2s delay.

## Timeout / retry notes

- The Arduino owns all timing for the physical steps (insertion, full entry,
  closing warning). The backend only needs to answer `VALID`/`INVALID`
  quickly (within ~5s) after an `RFID,<uid>` message.
- If the backend or serial link drops mid-cycle, the Arduino will time out on
  its own and return to `IDLE`; no special recovery is required on the PC side
  other than reconnecting the serial port.

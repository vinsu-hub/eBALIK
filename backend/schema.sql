-- eBALIK: Book Automated Library Inventory Keeper
-- MySQL 8.x schema

CREATE DATABASE IF NOT EXISTS ebalik_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE ebalik_db;

-- ---------------------------------------------------------------------
-- users: librarian / admin accounts for the dashboard
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    role          ENUM('admin', 'librarian') NOT NULL DEFAULT 'librarian',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- books: master catalog, one row per physical RFID-tagged copy
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS books (
    book_id           INT AUTO_INCREMENT PRIMARY KEY,
    rfid_uid          VARCHAR(32) UNIQUE,
    title             VARCHAR(255) NOT NULL,
    author            VARCHAR(255),
    accession_number  VARCHAR(50) UNIQUE,
    category          VARCHAR(100),
    status            ENUM('available', 'borrowed', 'lost', 'maintenance')
                       NOT NULL DEFAULT 'available',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE INDEX idx_books_status ON books(status);

-- ---------------------------------------------------------------------
-- borrow_records: one row per borrow transaction
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS borrow_records (
    borrow_id     INT AUTO_INCREMENT PRIMARY KEY,
    book_id       INT NOT NULL,
    borrower_name VARCHAR(150) NOT NULL,
    borrower_id   VARCHAR(50),
    borrow_date   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_date      DATETIME NOT NULL,
    is_returned   TINYINT(1) NOT NULL DEFAULT 0,
    returned_at   DATETIME NULL,
    FOREIGN KEY (book_id) REFERENCES books(book_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_borrow_book_open ON borrow_records(book_id, is_returned);

-- ---------------------------------------------------------------------
-- return_records: audit trail of successful automated returns
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS return_records (
    return_id     INT AUTO_INCREMENT PRIMARY KEY,
    book_id       INT NOT NULL,
    borrow_id     INT NULL,
    rfid_uid      VARCHAR(32) NOT NULL,
    returned_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified_by_sensors TINYINT(1) NOT NULL DEFAULT 1,
    FOREIGN KEY (book_id) REFERENCES books(book_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (borrow_id) REFERENCES borrow_records(borrow_id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- system_logs: hardware events, validation failures, errors
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_logs (
    log_id      INT AUTO_INCREMENT PRIMARY KEY,
    event_type  ENUM('INFO', 'WARNING', 'ERROR') NOT NULL DEFAULT 'INFO',
    source      VARCHAR(50) NOT NULL DEFAULT 'SYSTEM',
    message     VARCHAR(500) NOT NULL,
    rfid_uid    VARCHAR(32) NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE INDEX idx_logs_created ON system_logs(created_at);

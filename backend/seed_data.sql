-- Sample seed data for demo / defense purposes
USE ebalik_db;

-- Default admin account: username "admin", password "admin123"
-- (hash generated with werkzeug.security.generate_password_hash("admin123"))
INSERT INTO users (username, password_hash, full_name, role) VALUES
('admin', 'pbkdf2:sha256:600000$placeholder$replace_me', 'Library Administrator', 'admin')
ON DUPLICATE KEY UPDATE username = username;
-- NOTE: run `python create_admin.py` (see backend/create_admin.py) instead of
-- relying on the placeholder hash above -- it will generate a real hash for you.

INSERT INTO books (rfid_uid, title, author, accession_number, category, status) VALUES
('04A1B2C3', 'Data Structures and Algorithms', 'Robert Lafore', 'ACC-0001', 'Computer Science', 'borrowed'),
('04D4E5F6', 'Operating System Concepts', 'Silberschatz, Galvin, Gagne', 'ACC-0002', 'Computer Science', 'borrowed'),
('04A7B8C9', 'Clean Code', 'Robert C. Martin', 'ACC-0003', 'Computer Science', 'available'),
('04D0E1F2', 'Introduction to Algorithms', 'Cormen, Leiserson, Rivest, Stein', 'ACC-0004', 'Computer Science', 'available'),
('04A3B4C5', 'Database System Concepts', 'Silberschatz, Korth, Sudarshan', 'ACC-0005', 'Computer Science', 'borrowed')
ON DUPLICATE KEY UPDATE title = VALUES(title);

INSERT INTO borrow_records (book_id, borrower_name, borrower_id, borrow_date, due_date, is_returned) VALUES
(1, 'Juan Dela Cruz', '2023-11223', NOW() - INTERVAL 3 DAY, NOW() + INTERVAL 4 DAY, 0),
(2, 'Maria Santos', '2023-33445', NOW() - INTERVAL 5 DAY, NOW() + INTERVAL 2 DAY, 0),
(5, 'Pedro Reyes', '2023-55667', NOW() - INTERVAL 1 DAY, NOW() + INTERVAL 6 DAY, 0);

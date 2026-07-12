from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column("user_id", db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum("admin", "librarian", name="user_role"), default="librarian")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # flask-login expects get_id() to return a string; user_id is our PK
    def get_id(self):
        return str(self.user_id)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Book(db.Model):
    __tablename__ = "books"

    book_id = db.Column(db.Integer, primary_key=True)
    rfid_uid = db.Column(db.String(32), unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    accession_number = db.Column(db.String(50), unique=True)
    category = db.Column(db.String(100))
    status = db.Column(
        db.Enum("available", "borrowed", "lost", "maintenance", name="book_status"),
        default="available",
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    borrow_records = db.relationship("BorrowRecord", backref="book", lazy=True)
    return_records = db.relationship("ReturnRecord", backref="book", lazy=True)

    def current_borrow(self):
        """Return the open (not yet returned) borrow record for this book, if any."""
        return (
            BorrowRecord.query.filter_by(book_id=self.book_id, is_returned=False)
            .order_by(BorrowRecord.borrow_date.desc())
            .first()
        )


class BorrowRecord(db.Model):
    __tablename__ = "borrow_records"

    borrow_id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.book_id"), nullable=False)
    borrower_name = db.Column(db.String(150), nullable=False)
    borrower_id = db.Column(db.String(50))
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    is_returned = db.Column(db.Boolean, default=False)
    returned_at = db.Column(db.DateTime, nullable=True)


class ReturnRecord(db.Model):
    __tablename__ = "return_records"

    return_id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("books.book_id"), nullable=False)
    borrow_id = db.Column(db.Integer, db.ForeignKey("borrow_records.borrow_id"), nullable=True)
    rfid_uid = db.Column(db.String(32), nullable=False)
    returned_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_by_sensors = db.Column(db.Boolean, default=True)


class SystemLog(db.Model):
    __tablename__ = "system_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.Enum("INFO", "WARNING", "ERROR", name="log_event_type"), default="INFO")
    source = db.Column(db.String(50), default="SYSTEM")
    message = db.Column(db.String(500), nullable=False)
    rfid_uid = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def log_event(event_type, source, message, rfid_uid=None):
    """Convenience helper: write a system_logs row and commit."""
    entry = SystemLog(event_type=event_type, source=source, message=message, rfid_uid=rfid_uid)
    db.session.add(entry)
    db.session.commit()
    return entry

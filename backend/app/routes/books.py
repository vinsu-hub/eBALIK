from datetime import datetime, timedelta
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required

from app.extensions import db
from app.models import Book, BorrowRecord, log_event

# Valid RFID UID: 4-byte (8 hex) or 7-byte (14 hex) MIFARE UID
VALID_UID_RE = re.compile(r"^[0-9A-F]{8}$|^[0-9A-F]{14}$")

books_bp = Blueprint("books", __name__, url_prefix="/books")


@books_bp.route("/")
@login_required
def index():
    query = request.args.get("q", "").strip()
    books_query = Book.query
    if query:
        like = f"%{query}%"
        books_query = books_query.filter(
            db.or_(Book.title.ilike(like), Book.author.ilike(like), Book.rfid_uid.ilike(like))
        )
    books = books_query.order_by(Book.title.asc()).all()
    return render_template("books.html", books=books, query=query)


@books_bp.route("/add", methods=["POST"])
@login_required
def add_book():
    rfid_uid = request.form.get("rfid_uid", "").strip().upper()
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    accession_number = request.form.get("accession_number", "").strip()
    category = request.form.get("category", "").strip()

    if not rfid_uid or not title:
        flash("RFID UID and Title are required.", "danger")
        return redirect(url_for("books.index"))

    if not VALID_UID_RE.match(rfid_uid):
        flash(f"'{rfid_uid}' is not a valid RFID UID format (expected 8 or 14 uppercase hex characters).", "danger")
        return redirect(url_for("books.index"))

    if Book.query.filter_by(rfid_uid=rfid_uid).first():
        flash(f"A book with RFID UID {rfid_uid} already exists.", "danger")
        return redirect(url_for("books.index"))

    book = Book(
        rfid_uid=rfid_uid,
        title=title,
        author=author or None,
        accession_number=accession_number or None,
        category=category or None,
        status="available",
    )
    db.session.add(book)
    db.session.commit()
    log_event("INFO", "DASHBOARD", f"Book '{title}' added to catalog", rfid_uid=rfid_uid)
    flash(f"Book '{title}' added.", "success")
    return redirect(url_for("books.index"))


@books_bp.route("/<int:book_id>/edit", methods=["POST"])
@login_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    book.title = request.form.get("title", book.title).strip()
    book.author = request.form.get("author", book.author)
    book.category = request.form.get("category", book.category)
    book.accession_number = request.form.get("accession_number", book.accession_number)
    db.session.commit()
    flash("Book updated.", "success")
    return redirect(url_for("books.index"))


@books_bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    title = book.title
    db.session.delete(book)
    db.session.commit()
    log_event("WARNING", "DASHBOARD", f"Book '{title}' removed from catalog")
    flash(f"Book '{title}' removed.", "warning")
    return redirect(url_for("books.index"))


@books_bp.route("/<int:book_id>/borrow", methods=["POST"])
@login_required
def borrow_book(book_id):
    """Manually record a borrow transaction (e.g. done at the circulation desk,
    separate from the automated RFID return station)."""
    book = Book.query.get_or_404(book_id)

    if book.status != "available":
        flash("This book is not available to borrow.", "danger")
        return redirect(url_for("books.index"))

    borrower_name = request.form.get("borrower_name", "").strip()
    borrower_id = request.form.get("borrower_id", "").strip()
    loan_days = current_app.config["DEFAULT_LOAN_DAYS"]

    if not borrower_name:
        flash("Borrower name is required.", "danger")
        return redirect(url_for("books.index"))

    record = BorrowRecord(
        book_id=book.book_id,
        borrower_name=borrower_name,
        borrower_id=borrower_id or None,
        borrow_date=datetime.utcnow(),
        due_date=datetime.utcnow() + timedelta(days=loan_days),
        is_returned=False,
    )
    book.status = "borrowed"
    db.session.add(record)
    db.session.commit()
    log_event(
        "INFO", "DASHBOARD",
        f"'{book.title}' borrowed by {borrower_name}", rfid_uid=book.rfid_uid,
    )
    flash(f"'{book.title}' marked as borrowed by {borrower_name}.", "success")
    return redirect(url_for("books.index"))

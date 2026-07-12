from flask import Blueprint, render_template
from flask_login import login_required

from app.models import Book, BorrowRecord, ReturnRecord, SystemLog

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    total_books = Book.query.count()
    available_books = Book.query.filter_by(status="available").count()
    borrowed_books = Book.query.filter_by(status="borrowed").count()
    returns_today = ReturnRecord.query.filter(
        ReturnRecord.returned_at >= _today_start()
    ).count()

    recent_returns = (
        ReturnRecord.query.order_by(ReturnRecord.returned_at.desc()).limit(8).all()
    )
    recent_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(10).all()
    overdue = _overdue_borrows()

    return render_template(
        "dashboard.html",
        total_books=total_books,
        available_books=available_books,
        borrowed_books=borrowed_books,
        returns_today=returns_today,
        recent_returns=recent_returns,
        recent_logs=recent_logs,
        overdue=overdue,
    )


@dashboard_bp.route("/logs")
@login_required
def system_logs():
    logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(200).all()
    return render_template("system_logs.html", logs=logs)


@dashboard_bp.route("/records/borrow")
@login_required
def borrow_records():
    records = (
        BorrowRecord.query.order_by(BorrowRecord.borrow_date.desc()).limit(200).all()
    )
    return render_template("borrow_records.html", records=records)


@dashboard_bp.route("/records/return")
@login_required
def return_records():
    records = (
        ReturnRecord.query.order_by(ReturnRecord.returned_at.desc()).limit(200).all()
    )
    return render_template("return_records.html", records=records)


def _today_start():
    from datetime import datetime, time as dtime
    return datetime.combine(datetime.today(), dtime.min)


def _overdue_borrows():
    from datetime import datetime
    return (
        BorrowRecord.query.filter(
            BorrowRecord.is_returned == False,  # noqa: E712
            BorrowRecord.due_date < datetime.utcnow(),
        )
        .order_by(BorrowRecord.due_date.asc())
        .all()
    )

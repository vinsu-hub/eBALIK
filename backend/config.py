import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")

    # MySQL connection (via PyMySQL driver)
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ.get("DB_NAME", "ebalik_db")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Serial connection to the Arduino
    SERIAL_PORT = os.environ.get("SERIAL_PORT", "COM3")  # e.g. /dev/ttyUSB0 on Linux/macOS
    SERIAL_BAUD = int(os.environ.get("SERIAL_BAUD", "115200"))
    SERIAL_ENABLED = os.environ.get("SERIAL_ENABLED", "true").lower() == "true"

    # Default loan period used only if you add a "borrow" feature later
    DEFAULT_LOAN_DAYS = int(os.environ.get("DEFAULT_LOAN_DAYS", "7"))

    # Dev-only endpoints (simulate scan, launch terminal/hw-monitor)
    DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

"""
Entry point for local development / demo deployment.

Usage:
    python run.py

This starts the Flask app together with Socket.IO (needed for the live
dashboard updates) and the background Arduino serial bridge.
"""

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    # debug=False is safer once the serial thread is running, to avoid the
    # reloader spawning a second process that fights over the COM port.
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)

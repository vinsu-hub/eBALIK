from flask import Flask

from config import Config
from app.extensions import db, login_manager, socketio


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    socketio.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.books import books_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Start the Arduino serial bridge in the background (skips gracefully if
    # SERIAL_ENABLED=false or pyserial/the port isn't available yet).
    with app.app_context():
        from app.serial_reader import init_serial_bridge
        init_serial_bridge(app)

    return app

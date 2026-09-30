from flask import Flask

from app.config import Config
from app.extensions import db, migrate, login_manager


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app import models

    from app.auth.routes import auth_bp
    from app.hr.routes import hr_bp
    from app.fleet import fleet_bp

    app.register_blueprint(fleet_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(hr_bp)

    @app.route("/")
    def home():
        return "MatatuHub is running."

    return app
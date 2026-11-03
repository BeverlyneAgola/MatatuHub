from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Flask

from app.config import Config
from app.extensions import db, migrate, login_manager


def format_kenya_time(value):
    """
    Convert a database UTC timestamp to East Africa Time.

    Naive timestamps are treated as UTC because the application
    currently stores timestamps using datetime.utcnow().
    """
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(ZoneInfo("Africa/Nairobi"))


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Register Kenya time conversion for Jinja templates.
    app.jinja_env.filters["kenya_time"] = format_kenya_time

    from app import models

    from app.finance.routes import finance_bp
    from app.auth.routes import auth_bp
    from app.hr.routes import hr_bp
    from app.fleet import fleet_bp
    from app.operations.routes import operations_bp
    from app.operations.schedules.routes import schedules_bp
    from app.driver.routes import driver_bp
    from app.driver_operations.routes import driver_operations_bp
    from app.conductor.routes import conductor_bp
    from app.conductor_operations.routes import conductor_operations_bp
    from app.admin import admin_bp
    from app.admin import routes as admin_routes
    from app.management import management_bp
    from app.public import public_bp
    from app.management import routes as management_routes
    from app.payments.daraja_routes import payments_bp

    app.register_blueprint(fleet_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(driver_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(conductor_bp)
    app.register_blueprint(driver_operations_bp)
    app.register_blueprint(conductor_operations_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(management_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(payments_bp)

    return app
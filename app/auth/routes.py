from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from flask_login import login_user, logout_user, login_required

from app.extensions import db, login_manager
from app.models import User


auth_bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Each role is redirected to an existing page it is permitted to access.
ROLE_DESTINATIONS = {
    "General Manager": "management.dashboard",
    "Deputy General Manager": "management.dashboard",

    "System Administrator": "admin.users",

    "HR Manager": "hr.list_employees",

    "Operations Manager": "operations.list_routes",
    "Operations Officer": "operations.list_routes",

    "Driver": "driver.my_assignment",
    "Conductor": "conductor.my_assignment",

    "Driver Operations Supervisor": "driver_operations.index",
    "Conductor Operations Supervisor": "conductor_operations.index",

    "Finance Manager": "finance.list_payroll",
    "Payroll Officer": "finance.list_payroll",
    "Accountant": "finance.list_claims",
    "Finance Officer": "finance.collections_report",

    "Fleet Manager": "fleet.list_vehicles",
    "Fleet Officer": "fleet.list_vehicles",
    "Inspector": "fleet.list_vehicles",
}


@login_manager.unauthorized_handler
def unauthorized():
    flash("Please log in to access that page.", "login")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    # Avoid showing the login page to someone who is already logged in.
    if request.method == "GET":
        from flask_login import current_user

        if current_user.is_authenticated:
            return redirect(url_for("auth.dashboard_redirect"))

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "login")
            return redirect(url_for("auth.login"))

        if user.account_status != "active":
            flash(
                "This account is inactive. Contact System Administration.",
                "login",
            )
            return redirect(url_for("auth.login"))

        login_user(user)

        user.last_login = datetime.utcnow()
        db.session.commit()

        return redirect(url_for("auth.dashboard_redirect"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():

    logout_user()

    flash("You have been logged out.", "login")
    return redirect(url_for("auth.login"))


@auth_bp.route("/dashboard")
@login_required
def dashboard_redirect():

    employee = getattr(
        getattr(
            __import__("flask_login", fromlist=["current_user"]),
            "current_user",
        ),
        "employee",
        None,
    )

    if employee is None or employee.role is None:
        flash(
            "Your account does not have a valid role. Contact System Administration.",
            "login",
        )
        return redirect(url_for("auth.login"))

    destination = ROLE_DESTINATIONS.get(employee.role.name)

    if destination is None:
        flash(
            "No landing page is configured for your role. Contact System Administration.",
            "login",
        )
        return redirect(url_for("auth.login"))

    return redirect(url_for(destination))


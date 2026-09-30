from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required

from app.extensions import db, login_manager
from app.models import User


auth_bp = Blueprint(
    "auth",
    __name__
)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("Invalid username or password.")
            return redirect(url_for("auth.login"))

        if user.account_status != "active":
            flash("This account is inactive. Contact System Administration.")
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

    return redirect(url_for("auth.login"))


@auth_bp.route("/dashboard")
@login_required
def dashboard_redirect():
    return "MatatuHub login successful."
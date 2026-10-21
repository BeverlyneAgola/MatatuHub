from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required

from app.admin import admin_bp
from app.admin.services import (
    get_all_users,
    update_account_status,
    get_all_roles,
)
from app.auth.decorators import role_required
from app.models import AuditLog


@admin_bp.route("/users")
@login_required
@role_required("System Administrator")
def users():
    users = get_all_users()

    return render_template(
        "admin/users.html",
        users=users
    )


@admin_bp.route("/users/<int:user_id>/status", methods=["POST"])
@login_required
@role_required("System Administrator")
def update_status(user_id):
    new_status = request.form.get("status")

    try:
        user = update_account_status(user_id, new_status)

    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin.users"))

    except Exception:
        flash(
            "Unable to update the user account. Please try again.",
            "error"
        )
        return redirect(url_for("admin.users"))

    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.users"))

    flash(
        f"Account for {user.username} updated successfully.",
        "success"
    )

    return redirect(url_for("admin.users"))




@admin_bp.route("/roles")
@login_required
@role_required("System Administrator")
def roles():
    roles = get_all_roles()

    return render_template(
        "admin/roles.html",
        roles=roles
    )


@admin_bp.route("/audit-log")
@login_required
@role_required("System Administrator")
def audit_log():
    logs = (
        AuditLog.query
        .order_by(AuditLog.timestamp.desc())
        .all()
    )

    return render_template(
        "admin/audit_log.html",
        logs=logs
    )
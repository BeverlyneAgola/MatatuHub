from app.extensions import db
from app.models import User, Role
from app.utils.audit import log_action
from flask_login import current_user

def get_all_users():
    """Retrieve all user accounts with employee information."""

    return (
        User.query
        .join(User.employee)
        .order_by(User.id.asc())
        .all()
    )


def update_account_status(user_id, new_status):
    """Activate or deactivate a user account."""

    if new_status not in ("active", "inactive"):
        raise ValueError("Invalid account status.")

    user = db.session.get(User, user_id)

    if user is None:
        return None

    if (
        user.id == current_user.id
        and new_status == "inactive"
    ):
        raise ValueError(
            "You cannot deactivate your own account."
        )

    if user.account_status == new_status:
        return user

    old_status = user.account_status
    user.account_status = new_status

    try:
        db.session.flush()

        log_action(
            action="User account status changed",
            target_table="users",
            target_id=user.id,
            old_value=old_status,
            new_value=new_status,
            commit=False
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    return user


def get_all_roles():
    """Retrieve all roles with their department information."""

    return Role.query.order_by(Role.name.asc()).all()
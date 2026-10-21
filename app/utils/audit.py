from flask_login import current_user

from app.extensions import db
from app.models import AuditLog


def log_action(
    action,
    target_table,
    target_id,
    old_value=None,
    new_value=None,
    commit=True
):
    entry = AuditLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        target_table=target_table,
        target_id=target_id,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
    )

    db.session.add(entry)

    if commit:
        db.session.commit()
from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*allowed_roles):
    """
    Restrict a route to users whose employee role
    matches one of the allowed roles.
    """

    def decorator(f):

        @wraps(f)
        def wrapped(*args, **kwargs):

            if not current_user.is_authenticated:
                abort(401)

            employee_role = current_user.employee.role.name

            if employee_role not in allowed_roles:
                abort(403)

            return f(*args, **kwargs)

        return wrapped

    return decorator
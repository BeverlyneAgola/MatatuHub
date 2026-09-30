from app.models import Employee


def generate_next_staff_id():
    """Generate the next staff ID in the format STF001, STF002, etc."""

    last_employee = Employee.query.order_by(Employee.id.desc()).first()

    if last_employee is None:
        next_number = 1
    else:
        next_number = last_employee.id + 1

    return f"STF{next_number:03d}"
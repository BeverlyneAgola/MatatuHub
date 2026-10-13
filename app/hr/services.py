from datetime import datetime

from app.extensions import db
from app.models import (
    Complaint,
    Department,
    Employee,
    Role,
    RoleHistory,
    User,
)


def generate_next_staff_id():
    """Generate the next staff ID in the format STF001, STF002, etc."""
    last_employee = Employee.query.order_by(Employee.id.desc()).first()
    next_number = last_employee.id + 1 if last_employee else 1
    return f"STF{next_number:03d}"


def list_employees(department_id=None, role_id=None):
    query = Employee.query
    if department_id:
        query = query.filter_by(department_id=department_id)
    if role_id:
        query = query.filter_by(role_id=role_id)
    return query.order_by(Employee.id).all()


def list_departments():
    return Department.query.order_by(Department.name).all()


def list_roles(department_id=None):
    query = Role.query
    if department_id is not None:
        query = query.filter_by(department_id=department_id)
    return query.order_by(Role.name).all()


def get_employee(employee_id):
    return db.session.get(Employee, employee_id)


def get_employee_profile(employee):
    user = User.query.filter_by(employee_id=employee.id).first()
    role_history = (
        RoleHistory.query
        .filter_by(employee_id=employee.id)
        .order_by(RoleHistory.changed_at.desc())
        .all()
    )
    roles = list_roles()
    return user, role_history, roles


def create_employee(
    department_id,
    role_id,
    national_id,
    first_name,
    last_name,
    username,
    password,
    phone=None,
    email=None,
    kra_pin=None,
):
    department = db.session.get(Department, department_id)
    if department is None:
        raise ValueError("The selected department does not exist.")

    role = db.session.get(Role, role_id)
    if role is None:
        raise ValueError("The selected position does not exist.")
    if role.department_id != department.id:
        raise ValueError(
            "The selected position does not belong to the selected department."
        )

    employee = Employee(
        staff_id=generate_next_staff_id(),
        national_id=national_id,
        first_name=first_name,
        last_name=last_name,
        department_id=department.id,
        role_id=role.id,
        phone=phone,
        email=email,
        kra_pin=kra_pin,
    )
    try:
        db.session.add(employee)
        db.session.flush()

        user = User(employee_id=employee.id, username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return employee


def change_employee_status(employee, new_status):
    if new_status not in {"active", "fired"}:
        raise ValueError("Invalid employee status.")

    old_status = employee.status
    employee.status = new_status
    user = User.query.filter_by(employee_id=employee.id).first()
    if user:
        user.account_status = "inactive" if new_status == "fired" else "active"
    db.session.commit()
    return old_status


def change_employee_role(employee, new_role_id, changed_by):
    new_role = db.session.get(Role, new_role_id)
    if new_role is None:
        raise ValueError("The selected role does not exist.")
    if employee.role_id == new_role.id:
        raise ValueError("Employee already has this role.")

    old_role = db.session.get(Role, employee.role_id)
    history = RoleHistory(
        employee_id=employee.id,
        department_id=old_role.department_id,
        role_id=old_role.id,
        changed_by=changed_by,
    )
    db.session.add(history)
    employee.department_id = new_role.department_id
    employee.role_id = new_role.id
    db.session.commit()
    return old_role.id, new_role


def list_complaints(category=None, status=None):
    query = Complaint.query
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(Complaint.created_at.desc()).all()


def list_active_employees():
    return (
        Employee.query
        .filter_by(status="active")
        .order_by(Employee.first_name)
        .all()
    )


def create_complaint(
    category,
    description,
    filed_by_phone=None,
    filed_by_employee_id=None,
):
    complaint = Complaint(
        category=category,
        description=description,
        filed_by_phone=filed_by_phone,
        filed_by_employee_id=filed_by_employee_id,
    )
    db.session.add(complaint)
    db.session.commit()
    return complaint


def get_complaint(complaint_id):
    return db.session.get(Complaint, complaint_id)


def resolve_complaint(complaint, status, action_taken, resolved_by):
    complaint.status = status
    complaint.action_taken = action_taken
    complaint.resolved_by = resolved_by
    complaint.resolved_at = datetime.utcnow()
    db.session.commit()

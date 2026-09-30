from getpass import getpass

from app import create_app
from app.extensions import db
from app.models import Department, Role, Employee, User

app = create_app()

with app.app_context():

    department = Department.query.filter_by(name="HR").first()
    role = Role.query.filter_by(name="HR Manager").first()

    if not department or not role:
        print("HR department or HR Manager role not found.")
        exit()

    existing_user = User.query.filter_by(username="hrmanager").first()

    if existing_user:
        print("HR Manager account already exists.")
        exit()

    employee = Employee(
        staff_id="STF002",
        national_id="87654321",
        first_name="HR",
        last_name="Manager",
        department_id=department.id,
        role_id=role.id,
    )

    db.session.add(employee)
    db.session.flush()

    user = User(
        employee_id=employee.id,
        username="hrmanager",
    )

    user.set_password(getpass("Enter HR Manager password: "))

    db.session.add(user)
    db.session.commit()

    print("HR Manager account created successfully.")
    print("Username: hrmanager")
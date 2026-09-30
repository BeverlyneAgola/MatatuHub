from getpass import getpass

from app import create_app
from app.extensions import db
from app.models import Department, Role, Employee, User


app = create_app()


with app.app_context():

    # ============================================================
    # DEPARTMENTS
    # ============================================================

    departments_data = [
        "HR",
        "Finance",
        "Fleet",
        "Operations",
        "Driver and Conductor Operations",
        "System Administration",
        "Management",
    ]

    departments = {}

    for name in departments_data:
        department = Department(name=name)
        db.session.add(department)
        departments[name] = department

    db.session.flush()

    # ============================================================
    # ROLES / POSITIONS
    # ============================================================

    roles_by_department = {
        "HR": [
            "HR Manager",
            "HR Officer",
            "HR Assistant",
        ],

        "Finance": [
            "Finance Manager",
            "Accountant",
            "Finance Officer",
            "Payroll Officer",
        ],

        "Fleet": [
            "Fleet Manager",
            "Fleet Officer",
            "Inspector",
        ],

        "Operations": [
            "Operations Manager",
            "Operations Officer",
        ],

        "Driver and Conductor Operations": [
            "Driver Operations Supervisor",
            "Conductor Operations Supervisor",
            "Driver",
            "Conductor",
        ],

        "System Administration": [
            "System Administrator",
        ],

        "Management": [
            "General Manager",
            "Deputy General Manager",
        ],
    }

    roles = {}

    for department_name, role_names in roles_by_department.items():

        department = departments[department_name]

        for role_name in role_names:

            role = Role(
                name=role_name,
                department_id=department.id
            )

            db.session.add(role)
            roles[role_name] = role

    db.session.flush()

    # ============================================================
    # SYSTEM ADMINISTRATOR EMPLOYEE
    # ============================================================

    admin_emp = Employee(
        staff_id="STF001",
        national_id="12345678",
        first_name="System",
        last_name="Admin",
        department_id=departments[
            "System Administration"
        ].id,
        role_id=roles[
            "System Administrator"
        ].id,
    )

    db.session.add(admin_emp)

    db.session.flush()

    # ============================================================
    # SYSTEM ADMINISTRATOR USER ACCOUNT
    # ============================================================

    admin_user = User(
        employee_id=admin_emp.id,
        username="admin"
    )

    admin_user.set_password(
        getpass("Enter admin password: ")
    )

    db.session.add(admin_user)

    db.session.commit()

    print()
    print("==========================================")
    print("MatatuHub seed completed successfully.")
    print("==========================================")
    print()
    print("Departments created:")

    for department in departments.values():
        print(f"- {department.name}")

    print()
    print("Roles created:")

    for department_name, role_names in roles_by_department.items():

        print(f"\n{department_name}:")

        for role_name in role_names:
            print(f"  - {role_name}")

    print()
    print("System administrator:")
    print("Username: admin")
    print("Password: the password you entered")
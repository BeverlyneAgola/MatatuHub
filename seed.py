from getpass import getpass

from app import create_app
from app.extensions import db
from app.models import Department, Role, Employee, User

app	=	create_app()
with	app.app_context():
    
    depts	=	{name:	Department(name=name)	for	name	in
    ["HR",	"Finance",	"Fleet",	"Operations",	"System	Administration",	"Management"]}
    db.session.add_all(depts.values())
    db.session.commit()
    roles	=	{
    "System	Administrator":	Role(name="System	Administrator",	department_id=depts["System	Administration"].id),
    "HR	Manager":	Role(name="HR	Manager",	department_id=depts["HR"].id),
    "Fleet	Manager":	Role(name="Fleet	Manager",	department_id=depts["Fleet"].id),
    "Driver":	Role(name="Driver",	department_id=None),
    "Conductor":	Role(name="Conductor",	department_id=None),
    }
    db.session.add_all(roles.values())
    db.session.commit()
    admin_emp	=	Employee(
    staff_id="STF001",	national_id="12345678",	first_name="System",
    last_name="Admin",	department_id=depts["System	Administration"].id,
    role_id=roles["System	Administrator"].id,
    )
    db.session.add(admin_emp)
    db.session.commit()
    admin_user	=	User(employee_id=admin_emp.id,	username="admin")
    admin_user.set_password(getpass("Enter admin password: "))
    db.session.add(admin_user)
    db.session.commit()
    print("Seed complete. Login with the admin username and the password you entered.")
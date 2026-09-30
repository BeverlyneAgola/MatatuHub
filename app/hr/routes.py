from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)

from flask_login import login_required, current_user

from app.extensions import db
from app.models import (
    Employee,
    Department,
    Role,
    User,
    RoleHistory,
    Complaint,
)

from app.auth.decorators import role_required
from app.utils.audit import log_action
from app.hr.services import generate_next_staff_id


hr_bp = Blueprint(
    "hr",
    __name__,
    url_prefix="/hr"
)


# ============================================================
# EMPLOYEES
# ============================================================

@hr_bp.route("/employees")
@login_required
@role_required("HR Manager")
def list_employees():

    department_id = request.args.get("department_id", type=int)
    role_id = request.args.get("role_id", type=int)

    query = Employee.query

    if department_id:
        query = query.filter_by(department_id=department_id)

    if role_id:
        query = query.filter_by(role_id=role_id)

    employees = query.order_by(Employee.id).all()

    departments = Department.query.order_by(Department.name).all()
    roles = []

    return render_template(
        "hr/list.html",
        employees=employees,
        departments=departments,
        roles=roles,
        selected_department=department_id,
        selected_role=role_id,
    )


@hr_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
@role_required("HR Manager")
def new_employee():

    departments = Department.query.order_by(
        Department.name
    ).all()

    roles = []

    if request.method == "POST":

        try:
            department_id = request.form.get(
                "department_id",
                type=int
            )

            role_id = request.form.get(
                "role_id",
                type=int
            )

            if not department_id or not role_id:
                flash("Please select a department and position.")
                return redirect(
                    url_for("hr.new_employee")
                )

            department = Department.query.get_or_404(
                department_id
            )

            role = Role.query.get_or_404(
                role_id
            )

            # Make sure the selected position
            # actually belongs to the selected department.
            if role.department_id != department.id:
                flash(
                    "The selected position does not belong "
                    "to the selected department."
                )

                return redirect(
                    url_for("hr.new_employee")
                )

            employee = Employee(
                staff_id=generate_next_staff_id(),

                national_id=request.form["national_id"],

                first_name=request.form["first_name"],

                last_name=request.form["last_name"],

                department_id=department.id,

                role_id=role.id,

                phone=request.form.get("phone"),

                email=request.form.get("email"),

                kra_pin=request.form.get("kra_pin"),
            )

            db.session.add(employee)

            db.session.flush()

            user = User(
                employee_id=employee.id,

                username=request.form["username"],
            )

            user.set_password(
                request.form["temp_password"]
            )

            db.session.add(user)

            db.session.commit()

            log_action(
                "Enrolled employee",
                "employees",
                employee.id
            )

            flash(
                f"Employee enrolled successfully. "
                f"Staff ID: {employee.staff_id}"
            )

            return redirect(
                url_for("hr.list_employees")
            )

        except Exception:

            db.session.rollback()

            flash(
                "Employee enrollment failed. "
                "Check that the username and National ID are unique."
            )

    return render_template(
        "hr/new_employee.html",

        departments=departments,

        roles=roles,
    )


@hr_bp.route("/roles/<int:department_id>")
@login_required
@role_required("HR Manager")
def roles_by_department(department_id):

    roles = (
        Role.query
        .filter_by(department_id=department_id)
        .order_by(Role.name)
        .all()
    )

    return [
        {
            "id": role.id,
            "name": role.name
        }
        for role in roles
    ]

@hr_bp.route("/employees/<int:id>")
@login_required
@role_required("HR Manager")
def view_employee(id):

    employee = Employee.query.get_or_404(id)

    user = User.query.filter_by(
        employee_id=employee.id
    ).first()

    role_history = (
        RoleHistory.query
        .filter_by(employee_id=employee.id)
        .order_by(RoleHistory.changed_at.desc())
        .all()
    )

    roles = Role.query.order_by(Role.name).all()

    return render_template(
        "hr/profile.html",
        employee=employee,
        user=user,
        role_history=role_history,
        roles=roles,
    )


@hr_bp.route(
    "/employees/<int:id>/status",
    methods=["POST"]
)
@login_required
@role_required("HR Manager")
def change_status(id):

    employee = Employee.query.get_or_404(id)

    old_status = employee.status
    new_status = request.form["status"]

    if new_status not in ["active", "fired"]:

        flash("Invalid employee status.")

        return redirect(
            url_for("hr.view_employee", id=id)
        )

    employee.status = new_status

    user = User.query.filter_by(
        employee_id=employee.id
    ).first()

    if user:

        if new_status == "fired":
            user.account_status = "inactive"

        elif new_status == "active":
            user.account_status = "active"

    db.session.commit()

    log_action(
        "Changed employee status",
        "employees",
        employee.id,
        old_status,
        new_status,
    )

    flash(
        f"Employee status changed from "
        f"{old_status} to {new_status}."
    )

    return redirect(
        url_for("hr.view_employee", id=id)
    )


@hr_bp.route(
    "/employees/<int:id>/role",
    methods=["POST"]
)
@login_required
@role_required("HR Manager")
def change_role(id):

    employee = Employee.query.get_or_404(id)

    new_role_id = request.form.get(
        "role_id",
        type=int
    )

    if not new_role_id:

        flash("Please select a role.")

        return redirect(
            url_for("hr.view_employee", id=id)
        )

    new_role = Role.query.get_or_404(new_role_id)

    old_role_id = employee.role_id

    if old_role_id == new_role.id:

        flash("Employee already has this role.")

        return redirect(
            url_for("hr.view_employee", id=id)
        )

    history = RoleHistory(
        employee_id=employee.id,
        role_id=old_role_id,
        changed_by=current_user.employee.id,
    )

    db.session.add(history)

    employee.role_id = new_role.id

    db.session.commit()

    log_action(
        "Changed employee role",
        "employees",
        employee.id,
        old_role_id,
        new_role.id,
    )

    flash(
        f"Employee role changed to {new_role.name}."
    )

    return redirect(
        url_for("hr.view_employee", id=id)
    )


# ============================================================
# COMPLAINTS
# ============================================================

@hr_bp.route("/complaints")
@login_required
@role_required("HR Manager")
def list_complaints():

    category = request.args.get("category")
    status = request.args.get("status")

    query = Complaint.query

    if category:
        query = query.filter_by(
            category=category
        )

    if status:
        query = query.filter_by(
            status=status
        )

    complaints = (
        query
        .order_by(Complaint.created_at.desc())
        .all()
    )

    return render_template(
        "hr/complaints.html",
        complaints=complaints,
        selected_category=category,
        selected_status=status,
    )


@hr_bp.route(
    "/complaints/new",
    methods=["GET", "POST"]
)
@login_required
@role_required("HR Manager")
def new_complaint():

    employees = (
        Employee.query
        .filter_by(status="active")
        .order_by(Employee.first_name)
        .all()
    )

    if request.method == "POST":

        complaint = Complaint(
            category=request.form["category"],
            description=request.form["description"],
            filed_by_phone=request.form.get(
                "filed_by_phone"
            ),
            filed_by_employee_id=request.form.get(
                "filed_by_employee_id",
                type=int,
            ),
        )

        db.session.add(complaint)

        db.session.commit()

        log_action(
            "Created complaint",
            "complaints",
            complaint.id,
        )

        flash("Complaint recorded successfully.")

        return redirect(
            url_for("hr.list_complaints")
        )

    return render_template(
        "hr/new_complaint.html",
        employees=employees,
    )


@hr_bp.route(
    "/complaints/<int:id>/resolve",
    methods=["POST"]
)
@login_required
@role_required("HR Manager")
def resolve_complaint(id):

    complaint = Complaint.query.get_or_404(id)

    complaint.status = request.form["status"]

    complaint.action_taken = request.form[
        "action_taken"
    ]

    complaint.resolved_by = current_user.employee.id

    from datetime import datetime

    complaint.resolved_at = datetime.utcnow()

    db.session.commit()

    log_action(
        "Resolved complaint",
        "complaints",
        complaint.id,
        None,
        complaint.status,
    )

    flash("Complaint updated successfully.")

    return redirect(
        url_for("hr.list_complaints")
    )
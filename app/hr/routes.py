from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    current_app,
)

from flask_login import login_required, current_user

from app.auth.decorators import role_required
from app.utils.audit import log_action
from app.hr.services import (
    change_employee_role,
    change_employee_status,
    create_complaint,
    create_employee,
    get_complaint,
    get_employee,
    get_employee_profile,
    list_active_employees,
    list_complaints as fetch_complaints,
    list_departments,
    list_employees as fetch_employees,
    list_roles,
    resolve_complaint as resolve_complaint_service,
)


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

    employees = fetch_employees(department_id, role_id)
    departments = list_departments()
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

    departments = list_departments()

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

            employee = create_employee(
                department_id=department_id,
                role_id=role_id,
                national_id=request.form["national_id"],
                first_name=request.form["first_name"],
                last_name=request.form["last_name"],
                username=request.form["username"],
                password=request.form["temp_password"],
                phone=request.form.get("phone"),
                email=request.form.get("email"),
                kra_pin=request.form.get("kra_pin"),
            )

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

        except ValueError as error:
            flash(str(error))
            return redirect(url_for("hr.new_employee"))
        except Exception:
            current_app.logger.exception("Employee enrollment failed.")
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

    roles = list_roles(department_id)

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

    employee = get_employee(id)
    if employee is None:
        abort(404)
    user, role_history, roles = get_employee_profile(employee)

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

    employee = get_employee(id)
    if employee is None:
        abort(404)
    new_status = request.form["status"]

    try:
        old_status = change_employee_status(employee, new_status)
    except ValueError as error:
        flash(str(error))
        return redirect(
            url_for("hr.view_employee", id=id)
        )

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

    employee = get_employee(id)
    if employee is None:
        abort(404)

    new_role_id = request.form.get(
        "role_id",
        type=int
    )

    if not new_role_id:

        flash("Please select a role.")

        return redirect(
            url_for("hr.view_employee", id=id)
        )

    try:
        old_role_id, new_role = change_employee_role(
            employee,
            new_role_id,
            current_user.employee.id,
        )
    except ValueError as error:
        flash(str(error))
        return redirect(url_for("hr.view_employee", id=id))

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
    complaints = fetch_complaints(category, status)

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

    employees = list_active_employees()

    if request.method == "POST":

        complaint = create_complaint(
            category=request.form["category"],
            description=request.form["description"],
            filed_by_phone=request.form.get("filed_by_phone"),
            filed_by_employee_id=request.form.get(
                "filed_by_employee_id", type=int
            ),
        )

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

    complaint = get_complaint(id)
    if complaint is None:
        abort(404)
    resolve_complaint_service(
        complaint,
        request.form["status"],
        request.form["action_taken"],
        current_user.employee.id,
    )

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
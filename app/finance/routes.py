from flask import (
Blueprint,
abort,
current_app,
render_template,
redirect,
url_for,
request,
flash,
)

from flask_login import login_required, current_user

from app.auth.decorators import role_required
from app.utils.audit import log_action

from app.finance.services import (
approve_claim as approve_claim_service,
create_budget_allocation,
create_payroll,
get_budget_form_data,
get_claim,
get_collections_report,
get_current_employee_id,
get_payroll,
issue_payroll as issue_payroll_service,
list_claims as fetch_claims,
list_employees,
list_payroll as fetch_payroll,
reject_claim as reject_claim_service,
update_budget_allocation,
)

finance_bp = Blueprint(
"finance",
__name__,
url_prefix="/finance",
)

# ============================================================

# FINANCE ROLES AND PERMISSIONS

# ============================================================

FINANCE_ROLES = (
"Finance Manager",
"Accountant",
"Finance Officer",
"Payroll Officer",
)

PAYROLL_VIEW_ROLES = (
"Finance Manager",
"Payroll Officer",
)

PAYROLL_GENERATE_ROLES = (
"Payroll Officer",
)

PAYROLL_APPROVE_ROLES = (
"Finance Manager",
)

CLAIM_REVIEW_ROLES = (
"Finance Manager",
"Accountant",
)

BUDGET_VIEW_ROLES = (
"Finance Manager",
"Accountant",
)

BUDGET_CREATE_ROLES = (
"Accountant",
)

BUDGET_EDIT_ROLES = (
"Finance Manager",
)

# ============================================================

# PAYROLL LISTING AND FILTERING

# ============================================================

@finance_bp.route("/payroll", methods=["GET"])
@login_required
@role_required(*PAYROLL_VIEW_ROLES)
def list_payroll():

    period = request.args.get("period", "").strip()
    role_id = request.args.get("role_id", "").strip()

    selected_role_id = None

    if role_id:
        try:
            selected_role_id = int(role_id)
        except ValueError:
            flash("Invalid role filter.", "error")
            return redirect(url_for("finance.list_payroll"))

    payrolls, roles, deduction_map = fetch_payroll(
        period=period,
        role_id=selected_role_id,
    )

    return render_template(
        "finance/payroll_list.html",
        payrolls=payrolls,
        roles=roles,
        selected_role_id=role_id,
        selected_period=period,
        deduction_map=deduction_map,
    )


# ============================================================

# PAYROLL GENERATION

# ============================================================

@finance_bp.route("/payroll/new", methods=["GET", "POST"])
@login_required
@role_required(*PAYROLL_GENERATE_ROLES)
def new_payroll():

    employees = list_employees()

    if request.method == "POST":

        try:
            payroll = create_payroll(
                employee_id=request.form.get("employee_id"),
                period=request.form.get("period", ""),
                basic_salary=request.form.get("basic_salary"),
                allowance=request.form.get("allowance", "0"),
                deduction_types=request.form.getlist("deduction_type"),
                deduction_amounts=request.form.getlist("deduction_amount"),
                generated_by=get_current_employee_id(
                    current_user.employee
                ),
            )

            log_action(
                "Generated payroll",
                "payroll",
                payroll.id,
            )

            flash(
                f"Draft payroll generated successfully for {payroll.period}.",
                "success",
            )

            return redirect(url_for("finance.list_payroll"))

        except ValueError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Payroll generation failed."
            )
            flash(
                "Payroll generation failed. Check the application logs.",
                "error",
            )

    return render_template(
        "finance/payroll_new.html",
        employees=employees,
    )


# ============================================================

# PAYROLL APPROVAL / ISSUANCE

# ============================================================

@finance_bp.route(
"/payroll/[int:payroll_id](int:payroll_id)/issue",
methods=["POST"],
)
@login_required
@role_required(*PAYROLL_APPROVE_ROLES)
def issue_payroll(payroll_id):


    payroll = get_payroll(payroll_id)

    if payroll is None:
        abort(404)

    try:
        issue_payroll_service(payroll)

        log_action(
            "Approved and issued payroll",
            "payroll",
            payroll.id,
            old_value="draft",
            new_value="issued",
        )

        flash(
            "Payroll approved and issued successfully.",
            "success",
        )

    except ValueError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Payroll approval failed."
        )
        flash(
            "Payroll approval failed. Check the application logs.",
            "error",
        )

    return redirect(url_for("finance.list_payroll"))


# ============================================================

# CLAIM LISTING

# ============================================================

@finance_bp.route("/claims", methods=["GET"])
@login_required
@role_required(*FINANCE_ROLES)
def list_claims():
    status = request.args.get(
        "status",
        "pending",
    ).strip().lower()

    allowed_statuses = {
        "pending",
        "approved",
        "rejected",
        "all",
    }

    if status not in allowed_statuses:
        flash("Invalid claim status filter.", "error")
        status = "pending"

    claims, compensation_map = fetch_claims(status)

    return render_template(
        "finance/claims_list.html",
        claims=claims,
        compensation_map=compensation_map,
        selected_status=status,
    )


# ============================================================

# APPROVE CLAIM

# ============================================================

@finance_bp.route(
"/claims/[int:claim_id](int:claim_id)/approve",
methods=["POST"],
)
@login_required
@role_required(*CLAIM_REVIEW_ROLES)
def approve_claim(claim_id):
    claim = get_claim(claim_id)

    if claim is None:
        abort(404)

    try:
        approve_claim_service(
            claim,
            get_current_employee_id(current_user.employee),
            compensation_amount=request.form.get("amount"),
        )

        log_action(
            "Approved claim",
            "claims",
            claim.id,
        )

        flash("Claim approved successfully.", "success")

    except ValueError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Claim approval failed."
        )
        flash(
            "Claim approval failed. Check the application logs.",
            "error",
        )

    return redirect(url_for("finance.list_claims"))


# ============================================================

# REJECT CLAIM

# ============================================================

@finance_bp.route(
"/claims/[int:claim_id](int:claim_id)/reject",
methods=["POST"],
)
@login_required
@role_required(*CLAIM_REVIEW_ROLES)
def reject_claim(claim_id):

    claim = get_claim(claim_id)

    if claim is None:
        abort(404)

    try:
        reject_claim_service(
            claim,
            get_current_employee_id(current_user.employee),
        )

        log_action(
            "Rejected claim",
            "claims",
            claim.id,
        )

        flash("Claim rejected successfully.", "success")

    except ValueError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Claim rejection failed."
        )
        flash(
            "Claim rejection failed. Check the application logs.",
            "error",
        )

    return redirect(url_for("finance.list_claims"))


# ============================================================

# BUDGET OVERVIEW

# ============================================================

@finance_bp.route("/budget", methods=["GET"])
@login_required
@role_required(*BUDGET_VIEW_ROLES)
def list_budgets():
    departments, allocations = get_budget_form_data()

    return render_template(
        "finance/budget_new.html",
        departments=departments,
        allocations=allocations,
    )


# ============================================================

# CREATE BUDGET ALLOCATION

# ============================================================

@finance_bp.route(
"/budget/new",
methods=["GET", "POST"],
)
@login_required
@role_required(*BUDGET_CREATE_ROLES)
def new_budget():

    departments, allocations = get_budget_form_data()

    if request.method == "POST":

        try:
            allocation = create_budget_allocation(
                department_id=request.form.get("department_id"),
                amount=request.form.get("amount"),
                period=request.form.get("period", ""),
                allocated_by=get_current_employee_id(
                    current_user.employee
                ),
            )

            log_action(
                "Created budget allocation",
                "budget_allocations",
                allocation.id,
            )

            flash(
                "Budget allocation created successfully.",
                "success",
            )

            return redirect(url_for("finance.list_budgets"))

        except ValueError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Budget allocation failed."
            )
            flash(
                "Budget allocation failed. Check the application logs.",
                "error",
            )

    return render_template(
        "finance/budget_create.html",
        departments=departments,
    )


# ============================================================

# EDIT BUDGET ALLOCATION

# ============================================================

@finance_bp.route(
"/budget/[int:allocation_id](int:allocation_id)/edit",
methods=["GET", "POST"],
)
@login_required
@role_required(*BUDGET_EDIT_ROLES)
def edit_budget(allocation_id):
    departments, allocations = get_budget_form_data()

    allocation = next(
        (
            item for item in allocations
            if item.id == allocation_id
        ),
        None,
    )

    if allocation is None:
        abort(404)

    if request.method == "POST":

        old_value = (
            f"Department ID: {allocation.department_id}, "
            f"Period: {allocation.period}, "
            f"Amount: {allocation.amount}"
        )

        try:
            updated_allocation = update_budget_allocation(
                allocation_id=allocation.id,
                department_id=request.form.get("department_id"),
                amount=request.form.get("amount"),
                period=request.form.get("period", ""),
            )

            new_value = (
                f"Department ID: {updated_allocation.department_id}, "
                f"Period: {updated_allocation.period}, "
                f"Amount: {updated_allocation.amount}"
            )

            log_action(
                "Updated budget allocation",
                "budget_allocations",
                allocation.id,
                old_value=old_value,
                new_value=new_value,
            )

            flash(
                "Budget allocation updated successfully.",
                "success",
            )

            return redirect(url_for("finance.list_budgets"))

        except ValueError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Budget allocation update failed."
            )
            flash(
                "Budget allocation update failed. Check the application logs.",
                "error",
            )

    return render_template(
        "finance/budget_edit.html",
        allocation=allocation,
        departments=departments,
    )


# ============================================================

# COLLECTIONS REPORT

# ============================================================

@finance_bp.route("/collections", methods=["GET"])
@login_required
@role_required(*FINANCE_ROLES)
def collections_report():
    report_data = get_collections_report()

    return render_template(
        "finance/collections.html",
        **report_data,
    )


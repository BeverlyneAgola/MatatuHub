from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
)

from flask_login import login_required, current_user

from sqlalchemy import func

from app.extensions import db
from app.auth.decorators import role_required
from app.utils.audit import log_action

from app.models.finance import (
    Payroll,
    PayrollDeduction,
    Claim,
    Compensation,
    BudgetAllocation,
)

from app.models.core import Employee, Department, Role
from app.models.driver_conductor import PaymentLog


finance_bp = Blueprint(
    "finance",
    __name__,
    url_prefix="/finance",
)


# ============================================================
# FINANCE ROLES
# ============================================================

FINANCE_ROLES = (
    "Finance Manager",
    "Accountant",
    "Finance Officer",
    "Payroll Officer",
)

PAYROLL_ROLES = (
    "Finance Manager",
    "Payroll Officer",
)

CLAIM_REVIEW_ROLES = (
    "Finance Manager",
    "Accountant",
)

BUDGET_ROLES = (
    "Finance Manager",
    "Accountant",
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_current_employee_id():
    """
    Return the employee ID associated with the logged-in user.

    A valid Finance action must be associated with an employee.
    """

    employee = current_user.employee

    if employee is None:
        raise ValueError(
            "Your user account is not associated with an employee."
        )

    return employee.id


def parse_money(value, field_name):
    """
    Convert a submitted monetary value to Decimal.

    Reject invalid and negative monetary amounts.
    """

    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(
            f"{field_name} must be a valid monetary amount."
        )

    if not amount.is_finite():
        raise ValueError(
            f"{field_name} must be a finite monetary amount."
        )

    if amount < 0:
        raise ValueError(
            f"{field_name} cannot be negative."
        )

    if amount.as_tuple().exponent < -2:
        raise ValueError(
            f"{field_name} cannot have more than two decimal places."
        )

    return amount


def validate_period(period):
    """
    Validate a payroll or budget period in YYYY-MM format.
    """

    if not re.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])",
        period or "",
    ):
        raise ValueError(
            "Enter the period in YYYY-MM format, for example 2026-10."
        )

    return period


def get_payroll_deductions(payroll_id):
    """
    Retrieve deduction lines associated with a payroll.
    """

    return (
        PayrollDeduction.query
        .filter_by(payroll_id=payroll_id)
        .order_by(PayrollDeduction.id.asc())
        .all()
    )


# ============================================================
# PAYROLL LISTING AND FILTERING
# ============================================================

@finance_bp.route("/payroll", methods=["GET"])
@login_required
@role_required(*FINANCE_ROLES)
def list_payroll():

    query = Payroll.query

    # Filter by payroll period.
    period = request.args.get("period", "").strip()

    if period:
        query = query.filter(
            Payroll.period == period
        )

    # Filter by employee role.
    role_id = request.args.get("role_id", "").strip()

    if role_id:
        try:
            selected_role_id = int(role_id)
        except ValueError:
            flash("Invalid role filter.", "error")
            return redirect(url_for("finance.list_payroll"))

        employee_ids = [
            employee_id
            for (employee_id,) in (
                db.session.query(Employee.id)
                .filter(Employee.role_id == selected_role_id)
                .all()
            )
        ]

        query = query.filter(
            Payroll.employee_id.in_(employee_ids)
        )

    payrolls = (
        query
        .order_by(
            Payroll.period.desc(),
            Payroll.id.desc(),
        )
        .all()
    )

    roles = (
        Role.query
        .join(Department, Role.department_id == Department.id)
        .filter(Department.name == "Finance")
        .order_by(Role.name.asc())
        .all()
    )

    # Prepare deduction lines for display.
    deduction_map = {}

    for payroll in payrolls:
        deduction_map[payroll.id] = get_payroll_deductions(
            payroll.id
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
@role_required(*PAYROLL_ROLES)
def new_payroll():

    employees = (
        Employee.query
        .order_by(
            Employee.first_name.asc(),
            Employee.last_name.asc(),
        )
        .all()
    )

    if request.method == "POST":

        try:
            employee_id = int(
                request.form.get("employee_id", "")
            )

            employee = Employee.query.get_or_404(
                employee_id
            )

            period = validate_period(
                request.form.get("period", "").strip()
            )

            basic_salary = parse_money(
                request.form.get("basic_salary"),
                "Basic salary",
            )

            allowance = parse_money(
                request.form.get("allowance", "0"),
                "Allowance",
            )

            if basic_salary <= 0:
                raise ValueError(
                    "Basic salary must be greater than zero."
                )

            # Prevent multiple payroll records for the same
            # employee and period through this route.
            existing_payroll = Payroll.query.filter_by(
                employee_id=employee.id,
                period=period,
            ).first()

            if existing_payroll:
                raise ValueError(
                    "A payroll already exists for this employee "
                    f"for {period}."
                )

            deduction_types = request.form.getlist(
                "deduction_type"
            )

            deduction_amounts = request.form.getlist(
                "deduction_amount"
            )

            if len(deduction_types) != len(deduction_amounts):
                raise ValueError(
                    "Each deduction type must have a corresponding amount."
                )

            deductions = []
            total_deductions = Decimal("0.00")

            for deduction_type, raw_amount in zip(
                deduction_types,
                deduction_amounts,
            ):

                deduction_type = deduction_type.strip()

                # Ignore completely empty deduction rows.
                if not deduction_type and not raw_amount.strip():
                    continue

                if not deduction_type:
                    raise ValueError(
                        "Select a type for every deduction entered."
                    )

                if not raw_amount.strip():
                    raise ValueError(
                        "Enter an amount for every deduction entered."
                    )

                if len(deduction_type) > 30:
                    raise ValueError(
                        "A deduction type cannot exceed 30 characters."
                    )

                amount = parse_money(
                    raw_amount,
                    f"{deduction_type} deduction",
                )

                if amount <= 0:
                    raise ValueError(
                        "Deduction amounts must be greater than zero."
                    )

                deductions.append(
                    {
                        "type": deduction_type,
                        "amount": amount,
                    }
                )

                total_deductions += amount

            gross_pay = basic_salary + allowance

            if total_deductions > gross_pay:
                raise ValueError(
                    "Total deductions cannot exceed gross pay."
                )

            net_pay = gross_pay - total_deductions

            # Create the draft payroll.
            payroll = Payroll(
                employee_id=employee.id,
                period=period,
                basic_salary=basic_salary,
                allowance=allowance,
                net_pay=net_pay,
                status="draft",
                generated_by=get_current_employee_id(),
            )

            db.session.add(payroll)

            # Assign a payroll ID before creating deduction lines.
            db.session.flush()

            for deduction in deductions:

                db.session.add(
                    PayrollDeduction(
                        payroll_id=payroll.id,
                        type=deduction["type"],
                        amount=deduction["amount"],
                    )
                )

            db.session.commit()

            log_action(
                "Generated payroll",
                "payroll",
                payroll.id,
            )

            flash(
                f"Draft payroll generated successfully for {period}.",
                "success",
            )

            return redirect(
                url_for("finance.list_payroll")
            )

        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")

        except Exception:
            db.session.rollback()

            # Log the technical error in the application logs
            # rather than displaying database details to the user.
            from flask import current_app

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
# ISSUE AND LOCK PAYROLL
# ============================================================

@finance_bp.route(
    "/payroll/<int:payroll_id>/issue",
    methods=["POST"],
)
@login_required
@role_required(*PAYROLL_ROLES)
def issue_payroll(payroll_id):

    payroll = Payroll.query.get_or_404(
        payroll_id
    )

    if payroll.status != "draft":
        flash(
            "Only draft payrolls can be issued.",
            "error",
        )

        return redirect(
            url_for("finance.list_payroll")
        )

    payroll.status = "issued"

    db.session.commit()

    log_action(
        "Issued payroll",
        "payroll",
        payroll.id,
    )

    flash(
        "Payroll issued successfully. It is now locked.",
        "success",
    )

    return redirect(
        url_for("finance.list_payroll")
    )


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

    query = Claim.query

    allowed_statuses = {
        "pending",
        "approved",
        "rejected",
        "all",
    }

    if status not in allowed_statuses:
        flash(
            "Invalid claim status filter.",
            "error",
        )

        status = "pending"

    if status != "all":
        query = query.filter(
            func.lower(Claim.status) == status
        )

    claims = (
        query
        .order_by(Claim.created_at.desc())
        .all()
    )

    # Used to display any existing compensation records.
    compensation_map = {}

    for claim in claims:
        compensation_map[claim.id] = (
            Compensation.query
            .filter_by(claim_id=claim.id)
            .first()
        )

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
    "/claims/<int:claim_id>/approve",
    methods=["POST"],
)
@login_required
@role_required(*CLAIM_REVIEW_ROLES)
def approve_claim(claim_id):

    claim = Claim.query.get_or_404(
        claim_id
    )

    if claim.status != "pending":
        flash(
            "Only pending claims can be approved.",
            "error",
        )

        return redirect(
            url_for("finance.list_claims")
        )

    compensation_amount = None

    if (claim.category or "").strip().lower() == "accident":

        existing_compensation = Compensation.query.filter_by(
            claim_id=claim.id
        ).first()

        if existing_compensation:
            flash(
                "A compensation record already exists for this claim.",
                "error",
            )

            return redirect(
                url_for("finance.list_claims")
            )

        try:
            compensation_amount = parse_money(
                request.form.get(
                    "amount",
                    str(claim.amount_requested or ""),
                ),
                "Compensation amount",
            )

            if compensation_amount <= 0:
                raise ValueError(
                    "Compensation must be greater than zero."
                )

        except ValueError as error:
            flash(str(error), "error")

            return redirect(
                url_for("finance.list_claims")
            )

    try:
        claim.status = "approved"
        claim.reviewed_by = get_current_employee_id()
        claim.reviewed_at = datetime.utcnow()

        if compensation_amount is not None:

            compensation = Compensation(
                claim_id=claim.id,
                amount=compensation_amount,
                approved_by=claim.reviewed_by,
            )

            db.session.add(compensation)

        db.session.commit()

        log_action(
            "Approved claim",
            "claims",
            claim.id,
        )

        flash(
            "Claim approved successfully.",
            "success",
        )

    except Exception:
        db.session.rollback()

        from flask import current_app

        current_app.logger.exception(
            "Claim approval failed."
        )

        flash(
            "Claim approval failed. Check the application logs.",
            "error",
        )

    return redirect(
        url_for("finance.list_claims")
    )


# ============================================================
# REJECT CLAIM
# ============================================================

@finance_bp.route(
    "/claims/<int:claim_id>/reject",
    methods=["POST"],
)
@login_required
@role_required(*CLAIM_REVIEW_ROLES)
def reject_claim(claim_id):

    claim = Claim.query.get_or_404(
        claim_id
    )

    if claim.status != "pending":
        flash(
            "Only pending claims can be rejected.",
            "error",
        )

        return redirect(
            url_for("finance.list_claims")
        )

    claim.status = "rejected"
    claim.reviewed_by = get_current_employee_id()
    claim.reviewed_at = datetime.utcnow()

    db.session.commit()

    log_action(
        "Rejected claim",
        "claims",
        claim.id,
    )

    flash(
        "Claim rejected successfully.",
        "success",
    )

    return redirect(
        url_for("finance.list_claims")
    )


# ============================================================
# BUDGET ALLOCATIONS
# ============================================================

@finance_bp.route(
    "/budget/new",
    methods=["GET", "POST"],
)
@login_required
@role_required(*BUDGET_ROLES)
def new_budget():

    departments = (
        Department.query
        .order_by(Department.name.asc())
        .all()
    )

    allocations = (
        BudgetAllocation.query
        .order_by(
            BudgetAllocation.period.desc(),
            BudgetAllocation.id.desc(),
        )
        .all()
    )

    if request.method == "POST":

        try:
            department_id = int(
                request.form.get("department_id", "")
            )

            department = Department.query.get_or_404(
                department_id
            )

            amount = parse_money(
                request.form.get("amount"),
                "Budget amount",
            )

            period = validate_period(
                request.form.get("period", "").strip()
            )

            if amount <= 0:
                raise ValueError(
                    "Budget amount must be greater than zero."
                )

            allocation = BudgetAllocation(
                department_id=department.id,
                amount=amount,
                period=period,
                allocated_by=get_current_employee_id(),
            )

            db.session.add(allocation)
            db.session.commit()

            log_action(
                "Created budget allocation",
                "budget_allocations",
                allocation.id,
            )

            flash(
                "Budget allocation created successfully.",
                "success",
            )

            return redirect(
                url_for("finance.new_budget")
            )

        except ValueError as error:
            db.session.rollback()
            flash(str(error), "error")

        except Exception:
            db.session.rollback()

            from flask import current_app

            current_app.logger.exception(
                "Budget allocation failed."
            )

            flash(
                "Budget allocation failed. Check the application logs.",
                "error",
            )

    return render_template(
        "finance/budget_new.html",
        departments=departments,
        allocations=allocations,
    )


# ============================================================
# READ-ONLY COLLECTIONS REPORT
# ============================================================

@finance_bp.route(
    "/collections",
    methods=["GET"],
)
@login_required
@role_required(*FINANCE_ROLES)
def collections_report():

    # Finance reads PaymentLog records.
    # This route must not create, update, or delete them.
    payment_logs = (
        PaymentLog.query
        .order_by(PaymentLog.id.desc())
        .all()
    )

    total_records = len(payment_logs)

    total_fares = sum(
        (
            Decimal(str(log.fare_amount or 0))
            for log in payment_logs
        ),
        Decimal("0.00"),
    )

    total_amount_given = sum(
        (
            Decimal(str(log.amount_given or 0))
            for log in payment_logs
        ),
        Decimal("0.00"),
    )

    total_change_given = sum(
        (
            Decimal(str(log.change_given or 0))
            for log in payment_logs
        ),
        Decimal("0.00"),
    )

    status_totals = {}

    for payment in payment_logs:

        status = (
            payment.payment_status or "unknown"
        ).strip().lower()

        status_totals[status] = (
            status_totals.get(status, 0) + 1
        )

    return render_template(
        "finance/collections.html",
        payment_logs=payment_logs,
        total_records=total_records,
        total_fares=total_fares,
        total_amount_given=total_amount_given,
        total_change_given=total_change_given,
        status_totals=status_totals,
    )
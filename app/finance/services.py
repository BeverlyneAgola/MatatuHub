from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from sqlalchemy import func

from app.extensions import db
from app.models.core import Employee, Department, Role
from app.models.driver_conductor import PaymentLog
from app.models.finance import (
    BudgetAllocation,
    Claim,
    Compensation,
    Payroll,
    PayrollDeduction,
)


def get_current_employee_id(employee):
    if employee is None:
        raise ValueError(
            "Your user account is not associated with an employee."
        )
    return employee.id


def parse_money(value, field_name):
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
        raise ValueError(f"{field_name} cannot be negative.")

    if amount.as_tuple().exponent < -2:
        raise ValueError(
            f"{field_name} cannot have more than two decimal places."
        )

    return amount


def validate_period(period):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period or ""):
        raise ValueError(
            "Enter the period in YYYY-MM format, for example 2026-10."
        )

    return period


def list_payroll(period=None, role_id=None):
    query = Payroll.query

    if period:
        query = query.filter(Payroll.period == period)

    if role_id is not None:
        employee_ids = db.session.query(Employee.id).filter(
            Employee.role_id == role_id
        )
        query = query.filter(Payroll.employee_id.in_(employee_ids))

    payrolls = query.order_by(
        Payroll.period.desc(),
        Payroll.id.desc(),
    ).all()

    roles = (
        Role.query
        .join(Department, Role.department_id == Department.id)
        .filter(Department.name == "Finance")
        .order_by(Role.name.asc())
        .all()
    )

    deductions = {
        payroll.id: get_payroll_deductions(payroll.id)
        for payroll in payrolls
    }

    return payrolls, roles, deductions


def get_payroll_deductions(payroll_id):
    return (
        PayrollDeduction.query
        .filter_by(payroll_id=payroll_id)
        .order_by(PayrollDeduction.id.asc())
        .all()
    )


def list_employees():
    return (
        Employee.query
        .filter(Employee.status == "active")
        .order_by(
            Employee.first_name.asc(),
            Employee.last_name.asc(),
        )
        .all()
    )


def create_payroll(
    employee_id,
    period,
    basic_salary,
    allowance,
    deduction_types,
    deduction_amounts,
    generated_by,
):
    try:
        try:
            employee_id = int(employee_id)
        except (ValueError, TypeError):
            raise ValueError("Select a valid employee.")

        employee = db.session.get(Employee, employee_id)

        if employee is None:
            raise ValueError(
                "The selected employee does not exist."
            )

        if (
            not isinstance(employee.status, str)
            or employee.status.strip().lower() != "active"
        ):
            raise ValueError(
                "Only active employees can be included in payroll."
            )

        period = validate_period(period.strip())

        basic_salary = parse_money(
            basic_salary,
            "Basic salary",
        )

        allowance = parse_money(
            allowance,
            "Allowance",
        )

        if basic_salary <= 0:
            raise ValueError(
                "Basic salary must be greater than zero."
            )

        if Payroll.query.filter_by(
            employee_id=employee.id,
            period=period,
        ).first():
            raise ValueError(
                "A payroll already exists for this employee "
                f"for {period}."
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
            deduction_type = (deduction_type or "").strip()
            raw_amount = (raw_amount or "").strip()

            if not deduction_type and not raw_amount:
                continue

            if not deduction_type:
                raise ValueError(
                    "Select a type for every deduction entered."
                )

            if not raw_amount:
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

            deductions.append((deduction_type, amount))
            total_deductions += amount

        gross_pay = basic_salary + allowance

        if total_deductions > gross_pay:
            raise ValueError(
                "Total deductions cannot exceed gross pay."
            )

        payroll = Payroll(
            employee_id=employee.id,
            period=period,
            basic_salary=basic_salary,
            allowance=allowance,
            net_pay=gross_pay - total_deductions,
            status="draft",
            generated_by=generated_by,
        )

        db.session.add(payroll)
        db.session.flush()

        for deduction_type, amount in deductions:
            db.session.add(
                PayrollDeduction(
                    payroll_id=payroll.id,
                    type=deduction_type,
                    amount=amount,
                )
            )

        db.session.commit()

        return payroll

    except Exception:
        db.session.rollback()
        raise


def get_payroll(payroll_id):
    return db.session.get(Payroll, payroll_id)


def issue_payroll(payroll):
    try:
        if payroll.status != "draft":
            raise ValueError(
                "Only draft payrolls can be issued."
            )

        payroll.status = "issued"

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise


def list_claims(status=None):
    query = Claim.query

    if status and status != "all":
        query = query.filter(
            func.lower(Claim.status) == status
        )

    claims = query.order_by(
        Claim.created_at.desc()
    ).all()

    compensation_map = {
        claim.id: Compensation.query.filter_by(
            claim_id=claim.id
        ).first()
        for claim in claims
    }

    return claims, compensation_map


def get_claim(claim_id):
    return db.session.get(Claim, claim_id)


def approve_claim(claim, reviewed_by, compensation_amount=None):
    try:
        if claim.status != "pending":
            raise ValueError(
                "Only pending claims can be approved."
            )

        amount = None

        if (claim.category or "").strip().lower() == "accident":

            if Compensation.query.filter_by(
                claim_id=claim.id
            ).first():
                raise ValueError(
                    "A compensation record already exists for this claim."
                )

            requested_amount = (
                claim.amount_requested
                if compensation_amount is None
                else compensation_amount
            )

            amount = parse_money(
                requested_amount,
                "Compensation amount",
            )

            if amount <= 0:
                raise ValueError(
                    "Compensation must be greater than zero."
                )

        claim.status = "approved"
        claim.reviewed_by = reviewed_by
        claim.reviewed_at = datetime.utcnow()

        if amount is not None:
            db.session.add(
                Compensation(
                    claim_id=claim.id,
                    amount=amount,
                    approved_by=reviewed_by,
                )
            )

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise


def reject_claim(claim, reviewed_by):
    try:
        if claim.status != "pending":
            raise ValueError(
                "Only pending claims can be rejected."
            )

        claim.status = "rejected"
        claim.reviewed_by = reviewed_by
        claim.reviewed_at = datetime.utcnow()

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise


def get_budget_form_data():
    departments = Department.query.order_by(
        Department.name.asc()
    ).all()

    allocations = BudgetAllocation.query.order_by(
        BudgetAllocation.period.desc(),
        BudgetAllocation.id.desc(),
    ).all()

    return departments, allocations


def create_budget_allocation(
    department_id,
    amount,
    period,
    allocated_by,
):
    try:
        try:
            department_id = int(department_id)
        except (ValueError, TypeError):
            raise ValueError(
                "Select a valid department."
            )

        department = db.session.get(
            Department,
            department_id,
        )

        if department is None:
            raise ValueError(
                "The selected department does not exist."
            )

        amount = parse_money(
            amount,
            "Budget amount",
        )

        period = validate_period(period.strip())

        if amount <= 0:
            raise ValueError(
                "Budget amount must be greater than zero."
            )

        allocation = BudgetAllocation(
            department_id=department.id,
            amount=amount,
            period=period,
            allocated_by=allocated_by,
        )

        db.session.add(allocation)
        db.session.commit()

        return allocation

    except Exception:
        db.session.rollback()
        raise

def update_budget_allocation(
    allocation_id,
    department_id,
    amount,
    period,
):
    try:
        try:
            department_id = int(department_id)
        except (ValueError, TypeError):
            raise ValueError(
                "Select a valid department."
            )

        allocation = db.session.get(
            BudgetAllocation,
            allocation_id,
        )

        if allocation is None:
            raise ValueError(
                "Budget allocation not found."
            )

        department = db.session.get(
            Department,
            department_id,
        )

        if department is None:
            raise ValueError(
                "The selected department does not exist."
            )

        amount = parse_money(
            amount,
            "Budget amount",
        )

        period = validate_period(
            period.strip()
        )

        if amount <= 0:
            raise ValueError(
                "Budget amount must be greater than zero."
            )

        allocation.department_id = department.id
        allocation.amount = amount
        allocation.period = period

        db.session.commit()

        return allocation

    except Exception:
        db.session.rollback()
        raise
def get_collections_report():
    payment_logs = PaymentLog.query.order_by(
        PaymentLog.id.desc()
    ).all()

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

    return {
        "payment_logs": payment_logs,
        "total_records": len(payment_logs),
        "total_fares": total_fares,
        "total_amount_given": total_amount_given,
        "total_change_given": total_change_given,
        "status_totals": status_totals,
    }
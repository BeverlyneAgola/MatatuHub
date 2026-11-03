from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from flask_login import login_required, current_user

from app.auth.decorators import role_required
from app.utils.audit import log_action

from app.conductor.services import (
    get_conductor_active_assignment,
    get_conductor_assignment_details,
    get_conductor_payment_logs,
    get_payment_context,
    record_cash_payment,
    create_mpesa_payment,
)

conductor_bp = Blueprint(
    "conductor",
    __name__,
    url_prefix="/conductor",
    template_folder="../templates/conductor",
)


def get_payment_page_context():
    employee_id = current_user.employee.id
    allocation = get_conductor_active_assignment(employee_id)

    if not allocation:
        return None

    vehicle, route = get_conductor_assignment_details(allocation)
    time_band, directions, fares = get_payment_context(route.id)

    return {
        "allocation": allocation,
        "vehicle": vehicle,
        "route": route,
        "time_band": time_band,
        "directions": directions,
        "fares": fares,
    }


@conductor_bp.route("/my-assignment")
@login_required
@role_required("Conductor")
def my_assignment():
    employee_id = current_user.employee.id

    allocation = get_conductor_active_assignment(employee_id)

    vehicle, route = (
        get_conductor_assignment_details(allocation)
        if allocation
        else (None, None)
    )

    payments = get_conductor_payment_logs(employee_id)

    return render_template(
        "conductor/my_assignment.html",
        allocation=allocation,
        vehicle=vehicle,
        route=route,
        payments=payments,
    )


@conductor_bp.route("/payment-log/cash", methods=["GET"])
@login_required
@role_required("Conductor")
def cash_payment():
    context = get_payment_page_context()

    if not context:
        flash("You do not have an active vehicle allocation.", "warning")
        return redirect(url_for("conductor.my_assignment"))

    return render_template(
        "conductor/cash_payment.html",
        **context
    )


@conductor_bp.route("/payment-log/mpesa", methods=["GET"])
@login_required
@role_required("Conductor")
def mpesa_payment():
    context = get_payment_page_context()

    if not context:
        flash("You do not have an active vehicle allocation.", "warning")
        return redirect(url_for("conductor.my_assignment"))

    return render_template(
        "conductor/mpesa_payment.html",
        **context
    )


@conductor_bp.route("/payment-log/cash/record", methods=["POST"])
@login_required
@role_required("Conductor")
def record_cash():
    context = get_payment_page_context()

    if not context:
        flash("You do not have an active vehicle allocation.", "warning")
        return redirect(url_for("conductor.my_assignment"))

    payment, error = record_cash_payment(
        employee_id=current_user.employee.id,
        allocation_id=context["allocation"].id,
        direction=request.form.get("direction"),
        amount_given=request.form.get("amount_given"),
    )

    if error:
        flash(error, "error")
        return redirect(url_for("conductor.cash_payment"))

    log_action(
        "Recorded cash conductor payment",
        "payment_logs",
        payment.id
    )

    flash("Cash payment recorded successfully.", "success")

    return redirect(url_for("conductor.my_assignment"))


@conductor_bp.route("/payment-log/mpesa/request", methods=["POST"])
@login_required
@role_required("Conductor")
def request_mpesa():
    context = get_payment_page_context()

    if not context:
        flash("You do not have an active vehicle allocation.", "warning")
        return redirect(url_for("conductor.my_assignment"))

    if request.form.get("confirm_payment") != "yes":
        flash(
            "Confirm the M-Pesa amount before sending the request.",
            "error",
        )
        return redirect(url_for("conductor.mpesa_payment"))

    payment, error = create_mpesa_payment(
        employee_id=current_user.employee.id,
        allocation_id=context["allocation"].id,
        direction=request.form.get("direction"),
        commuter_phone=request.form.get("commuter_phone"),
    )

    if error:
        flash(error, "error")
        return redirect(url_for("conductor.mpesa_payment"))

    log_action(
        "Initiated M-Pesa STK Push",
        "payment_logs",
        payment.id
    )

    flash(
        "M-Pesa request sent. Ask the commuter to complete "
        "the prompt on their phone.",
        "success",
    )

    return redirect(url_for("conductor.my_assignment"))
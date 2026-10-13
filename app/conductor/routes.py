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
    get_available_directions,
    detect_time_band,
    create_payment_log,
)


conductor_bp = Blueprint(
    "conductor",
    __name__,
    url_prefix="/conductor",
    template_folder="../templates/conductor",
)


# ============================================================
# CONDUCTOR ASSIGNMENT AND PAYMENT HISTORY
# ============================================================

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


# ============================================================
# RECORD COMMUTER PAYMENT
# ============================================================

@conductor_bp.route(
    "/payment-log/new",
    methods=["GET", "POST"]
)
@login_required
@role_required("Conductor")
def new_payment_log():

    employee_id = current_user.employee.id

    allocation = get_conductor_active_assignment(employee_id)

    if not allocation:
        flash("You do not have an active vehicle allocation.")

        return redirect(
            url_for("conductor.my_assignment")
        )

    vehicle, route = get_conductor_assignment_details(allocation)

    time_band = detect_time_band()

    directions = get_available_directions(
        allocation.route_id
    )

    if request.method == "POST":

        direction = request.form.get(
            "direction",
            ""
        ).strip()

        commuter_phone = request.form.get(
            "commuter_phone",
            ""
        ).strip()

        amount_given = request.form.get(
            "amount_given",
            ""
        ).strip()

        if direction not in directions:
            flash(
                "Select a valid fare direction for your assigned route."
            )

            return render_template(
                "conductor/new_payment_log.html",
                allocation=allocation,
                vehicle=vehicle,
                route=route,
                directions=directions,
                time_band=detect_time_band(),
            )

        payment, error = create_payment_log(
            employee_id=employee_id,
            allocation_id=allocation.id,
            direction=direction,
            commuter_phone=commuter_phone,
            amount_given=amount_given,
        )

        if error:
            flash(error)

            return render_template(
                "conductor/new_payment_log.html",
                allocation=allocation,
                vehicle=vehicle,
                route=route,
                directions=directions,
                time_band=detect_time_band(),
            )

        log_action(
            "Created conductor payment log",
            "payment_logs",
            payment.id
        )

        flash(
            "Payment recorded successfully. "
            "Its status is pending confirmation."
        )

        return redirect(
            url_for("conductor.my_assignment")
        )

    return render_template(
        "conductor/new_payment_log.html",
        allocation=allocation,
        vehicle=vehicle,
        route=route,
        directions=directions,
        time_band=time_band,
    )
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

from app.driver.services import (
    get_driver_active_assignment,
    get_driver_assignment_details,
    get_driver_trip_logs,
    create_driver_trip_log,
)


driver_bp = Blueprint(
    "driver",
    __name__,
    url_prefix="/driver",
    template_folder="../templates/driver",
)


# ============================================================
# MY ASSIGNMENT
# ============================================================

@driver_bp.route("/my-assignment")
@login_required
@role_required("Driver")
def my_assignment():

    employee_id = current_user.employee.id

    allocation = get_driver_active_assignment(employee_id)

    vehicle, route = (
        get_driver_assignment_details(allocation)
        if allocation
        else (None, None)
    )

    return render_template(
        "driver/assignment.html",
        allocation=allocation,
        vehicle=vehicle,
        route=route,
    )


# ============================================================
# RECORD A NEW TRIP
# ============================================================

@driver_bp.route("/trip-logs/new", methods=["GET", "POST"])
@login_required
@role_required("Driver")
def new_trip_log():

    employee_id = current_user.employee.id

    allocation = get_driver_active_assignment(employee_id)

    # A driver must have an active allocation before
    # recording a trip.

    if not allocation:

        flash(
            "You cannot record a trip because you do not "
            "currently have an active vehicle allocation.",
            "warning",
        )

        return redirect(
            url_for("driver.my_assignment")
        )

    vehicle, route = get_driver_assignment_details(allocation)

    # PROCESS FORM SUBMISSION

    if request.method == "POST":

        notes = request.form.get(
            "notes",
            ""
        ).strip()

        trip, error = create_driver_trip_log(
            employee_id=employee_id,
            allocation_id=allocation.id,
            notes=notes,
        )

        if error:

            flash(error, "danger")

            return redirect(
                url_for("driver.new_trip_log")
            )

        log_action(
            "Created driver trip log",
            "trip_logs",
            trip.id,
        )

        flash(
            "Trip recorded successfully.",
            "success",
        )

        return redirect(
            url_for("driver.my_trip_logs")
        )

    # DISPLAY THE RECORDING FORM

    return render_template(
        "driver/new_trip_log.html",
        allocation=allocation,
        vehicle=vehicle,
        route=route,
    )


# ============================================================
# MY TRIP HISTORY
# ============================================================

@driver_bp.route("/trip-logs")
@login_required
@role_required("Driver")
def my_trip_logs():

    employee_id = current_user.employee.id

    trip_logs = get_driver_trip_logs(employee_id)

    return render_template(
        "driver/trip_logs.html",
        trip_logs=trip_logs,
    )
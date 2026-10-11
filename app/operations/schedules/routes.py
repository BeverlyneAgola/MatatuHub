from datetime import time

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request
)

from flask_login import login_required, current_user

from app.extensions import db
from app.models import Route, Schedule
from app.auth.decorators import role_required
from app.utils.audit import log_action


schedules_bp = Blueprint(
    "schedules",
    __name__,
    url_prefix="/operations"
)


# ============================================================
# SCHEDULES
# ============================================================

@schedules_bp.route(
    "/routes/<int:route_id>/schedules"
)
@login_required
@role_required(
    "Operations Manager",
    "Operations Officer",
    "General Manager",
    "Deputy General Manager"
)
def list_schedules(route_id):

    route = Route.query.get_or_404(route_id)

    schedules = (
        Schedule.query
        .filter_by(route_id=route.id)
        .order_by(
            Schedule.departure_time.asc()
        )
        .all()
    )

    return render_template(
        "operations/schedules/schedules.html",
        route=route,
        schedules=schedules
    )


@schedules_bp.route(
    "/routes/<int:route_id>/schedules/new",
    methods=["GET", "POST"]
)
@login_required
@role_required(
    "Operations Manager",
    "Operations Officer"
)
def new_schedule(route_id):

    route = Route.query.get_or_404(route_id)

    if request.method == "POST":

        departure_time = request.form.get(
            "departure_time",
            ""
        ).strip()

        if not departure_time:

            flash("Departure time is required.")

            return render_template(
                "operations/schedules/new_schedule.html",
                route=route
            )

        try:

            departure_time = time.fromisoformat(
                departure_time
            )

        except ValueError:

            flash(
                "Departure time must be a valid time."
            )

            return render_template(
                "operations/schedules/new_schedule.html",
                route=route
            )

        schedule = Schedule(
            route_id=route.id,
            departure_time=departure_time,
            created_by=current_user.employee.id
        )

        db.session.add(schedule)
        db.session.commit()

        log_action(
            "Created schedule",
            "schedules",
            schedule.id
        )

        flash("Schedule created successfully.")

        return redirect(
            url_for(
                "schedules.list_schedules",
                route_id=route.id
            )
        )

    return render_template(
        "operations/schedules/new_schedule.html",
        route=route
    )
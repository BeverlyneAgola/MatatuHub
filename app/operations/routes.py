from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app.extensions import db
from app.models import Route, Fare
from app.auth.decorators import role_required
from app.utils.audit import log_action
from app.operations.forms import validate_fare_data
from app.operations.services import create_fare, update_fare


operations_bp = Blueprint(
    "operations",
    __name__,
    url_prefix="/operations"
)


# ============================================================
# ROUTES
# ============================================================

@operations_bp.route("/routes")
@login_required
@role_required("Operations Manager", "Operations Officer")
def list_routes():

    routes = Route.query.order_by(Route.name.asc()).all()

    return render_template(
        "operations/routes.html",
        routes=routes
    )


@operations_bp.route("/routes/new", methods=["GET", "POST"])
@login_required
@role_required("Operations Manager", "Operations Officer")
def new_route():

    if request.method == "POST":

        name = request.form["name"].strip()
        start_point = request.form["start_point"].strip()
        destination = request.form["destination"].strip()

        if not name or not start_point or not destination:
            flash("All route fields are required.")
            return redirect(url_for("operations.new_route"))

        route = Route(
            name=name,
            start_point=start_point,
            destination=destination,
            status="active"
        )

        db.session.add(route)
        db.session.commit()

        log_action(
            "Created route",
            "routes",
            route.id
        )

        flash(f"Route '{route.name}' created successfully.")

        return redirect(url_for("operations.list_routes"))

    return render_template("operations/new_route.html")


@operations_bp.route("/routes/<int:id>")
@login_required
@role_required(
    "Operations Manager",
    "Operations Officer",
    "General Manager",
    "Deputy General Manager"
)
def view_route(id):

    route = Route.query.get_or_404(id)

    return render_template(
        "operations/route_profile.html",
        route=route
    )


# ============================================================
# FARES
# ============================================================

@operations_bp.route("/routes/<int:route_id>/fares")
@login_required
@role_required(
    "Operations Manager",
    "Operations Officer",
    "General Manager",
    "Deputy General Manager"
)
def list_fares(route_id):

    route = Route.query.get_or_404(route_id)

    fares = (
        Fare.query
        .filter_by(route_id=route.id)
        .order_by(
            Fare.direction.asc(),
            Fare.time_band.asc(),
            Fare.effective_from.desc()
        )
        .all()
    )

    return render_template(
        "operations/fares.html",
        route=route,
        fares=fares
    )


@operations_bp.route(
    "/routes/<int:route_id>/fares/new",
    methods=["GET", "POST"]
)
@login_required
@role_required(
    "Operations Manager",
    "Operations Officer"
)
def new_fare(route_id):

    route = Route.query.get_or_404(route_id)

    if request.method == "POST":

        direction = request.form.get(
            "direction",
            ""
        ).strip()

        time_band = request.form.get(
            "time_band",
            ""
        ).strip().lower()

        amount = request.form.get(
            "amount",
            ""
        ).strip()

        effective_from = request.form.get(
            "effective_from",
            ""
        ).strip()

        errors = validate_fare_data(
            direction,
            time_band,
            amount,
            effective_from
        )

        if errors:

            for error in errors:
                flash(error)

            return render_template(
                "operations/new_fare.html",
                route=route
            )

        try:

            amount = Decimal(amount)

            effective_from = date.fromisoformat(
                effective_from
            )

            fare = create_fare(
                route_id=route.id,
                direction=direction,
                time_band=time_band,
                amount=amount,
                effective_from=effective_from
            )

        except (ValueError, InvalidOperation) as error:

            db.session.rollback()

            flash(str(error))

            return render_template(
                "operations/new_fare.html",
                route=route
            )

        log_action(
            "Created fare",
            "fares",
            fare.id
        )

        flash("Fare created successfully.")

        return redirect(
            url_for(
                "operations.list_fares",
                route_id=route.id
            )
        )

    return render_template(
        "operations/new_fare.html",
        route=route
    )


@operations_bp.route(
    "/fares/<int:fare_id>/update",
    methods=["GET", "POST"]
)
@login_required
@role_required(
    "Operations Manager",
    "Operations Officer"
)
def edit_fare(fare_id):

    fare = Fare.query.get_or_404(fare_id)

    route = Route.query.get_or_404(
        fare.route_id
    )

    if request.method == "POST":

        amount = request.form.get(
            "amount",
            ""
        ).strip()

        effective_from = request.form.get(
            "effective_from",
            ""
        ).strip()

        if not amount or not effective_from:

            flash(
                "Amount and effective date are required."
            )

            return render_template(
                "operations/edit_fare.html",
                fare=fare,
                route=route
            )

        try:

            amount = Decimal(amount)

            effective_from = date.fromisoformat(
                effective_from
            )

            if amount <= 0:

                raise ValueError(
                    "Fare amount must be greater than zero."
                )

            new_fare = update_fare(
                fare_id=fare.id,
                amount=amount,
                effective_from=effective_from
            )

        except (ValueError, InvalidOperation) as error:

            db.session.rollback()

            flash(str(error))

            return render_template(
                "operations/edit_fare.html",
                fare=fare,
                route=route
            )

        log_action(
            "Updated fare",
            "fares",
            new_fare.id
        )

        flash("Fare updated successfully.")

        return redirect(
            url_for(
                "operations.list_fares",
                route_id=route.id
            )
        )

    return render_template(
        "operations/edit_fare.html",
        fare=fare,
        route=route
    )
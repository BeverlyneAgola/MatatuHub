from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.fleet.services import (
    close_allocation,
    create_accident,
    create_allocation,
    create_maintenance_record,
    create_vehicle,
    create_vehicle_document,
    fetch_vehicles,
    get_accident_form_data,
    get_allocation,
    get_allocation_form_data,
    get_vehicle,
    get_vehicle_profile,
    list_maintenance_records,
    list_vehicle_documents,
    update_vehicle_status,
)
from app.auth.decorators import role_required
from app.utils.audit import log_action


fleet_bp = Blueprint("fleet", __name__, url_prefix="/fleet")


def parse_optional_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid date.")


def parse_optional_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("Enter a valid date and time.")


@fleet_bp.route("/vehicles")
@login_required
@role_required("Fleet Manager", "Fleet Officer", "Inspector")
def list_vehicles():
    vehicles = fetch_vehicles()

    return render_template(
        "fleet/vehicles.html",
        vehicles=vehicles,
    )


@fleet_bp.route("/vehicles/new", methods=["GET", "POST"])
@login_required
@role_required("Fleet Manager")
def new_vehicle():
    if request.method == "POST":
        reg_no = request.form.get("reg_no", "").strip()

        try:
            vehicle = create_vehicle(
                reg_no=reg_no,
                make=request.form.get("make", "").strip() or None,
                year=request.form.get("year", type=int),
                vehicle_type=request.form.get("type", "").strip() or None,
                ownership=request.form.get("ownership", "").strip() or None,
            )

        except ValueError as error:
            flash(str(error))
            return render_template("fleet/new_vehicle.html"), 400

        log_action(
            "Created vehicle",
            "vehicles",
            vehicle.id,
        )

        flash(f"Vehicle {vehicle.reg_no} added successfully.")

        return redirect(
            url_for("fleet.view_vehicle", id=vehicle.id)
        )

    return render_template("fleet/new_vehicle.html")


@fleet_bp.route("/vehicles/<int:id>")
@login_required
@role_required("Fleet Manager", "Fleet Officer", "Inspector")
def view_vehicle(id):
    vehicle = get_vehicle(id)

    if vehicle is None:
        abort(404)

    profile = get_vehicle_profile(vehicle.id)

    return render_template(
        "fleet/vehicle_profile.html",
        vehicle=vehicle,
        **profile,
        today=date.today(),
    )


@fleet_bp.route("/vehicles/<int:id>/status", methods=["POST"])
@login_required
@role_required("Fleet Manager")
def change_vehicle_status(id):
    vehicle = get_vehicle(id)

    if vehicle is None:
        abort(404)

    new_status = request.form.get("status")
    old_status = vehicle.status

    try:
        old_status = update_vehicle_status(
            vehicle,
            new_status,
        )

    except ValueError as error:
        flash(str(error))
        return redirect(
            url_for("fleet.view_vehicle", id=vehicle.id)
        )

    log_action(
        "Changed vehicle status",
        "vehicles",
        vehicle.id,
        old_status,
        new_status,
    )

    flash(
        f"Vehicle status changed from "
        f"{old_status} to {new_status}."
    )

    return redirect(
        url_for("fleet.view_vehicle", id=vehicle.id)
    )


@fleet_bp.route(
    "/vehicles/<int:id>/documents",
    methods=["GET", "POST"],
)
@login_required
@role_required("Fleet Manager")
def vehicle_documents(id):
    vehicle = get_vehicle(id)

    if vehicle is None:
        abort(404)

    if request.method == "POST":
        try:
            issue_date = parse_optional_date(
                request.form.get("issue_date", "")
            )
            expiry_date = parse_optional_date(
                request.form.get("expiry_date", "")
            )

            document = create_vehicle_document(
                vehicle_id=vehicle.id,
                doc_type=request.form.get("doc_type", ""),
                document_number=(
                    request.form.get("document_number", "").strip()
                    or None
                ),
                issue_date=issue_date,
                expiry_date=expiry_date,
            )

        except ValueError as error:
            flash(str(error))
            return redirect(
                url_for("fleet.vehicle_documents", id=vehicle.id)
            )

        log_action(
            "Added vehicle document",
            "vehicle_documents",
            document.id,
        )

        flash("Vehicle document added successfully.")

        return redirect(
            url_for("fleet.vehicle_documents", id=vehicle.id)
        )

    documents = list_vehicle_documents(vehicle.id)

    return render_template(
        "fleet/documents.html",
        vehicle=vehicle,
        documents=documents,
        today=date.today(),
    )


@fleet_bp.route(
    "/vehicles/<int:id>/maintenance",
    methods=["GET", "POST"],
)
@login_required
@role_required("Fleet Manager")
def vehicle_maintenance(id):
    vehicle = get_vehicle(id)

    if vehicle is None:
        abort(404)

    if request.method == "POST":
        try:
            cost_value = request.form.get("cost", "").strip()

            if cost_value:
                cost = float(cost_value)
            else:
                cost = None

            record_date = parse_optional_date(
                request.form.get("date", "")
            )

            maintenance = create_maintenance_record(
                vehicle_id=vehicle.id,
                created_by=current_user.employee.id,
                description=request.form.get("description", ""),
                cost=cost,
                record_date=record_date or date.today(),
            )

        except (ValueError, TypeError) as error:
            flash(
                str(error) or "Enter a valid maintenance cost."
            )
            return redirect(
                url_for("fleet.vehicle_maintenance", id=vehicle.id)
            )

        log_action(
            "Added maintenance record",
            "maintenance_records",
            maintenance.id,
        )

        flash("Maintenance record added successfully.")

        return redirect(
            url_for("fleet.vehicle_maintenance", id=vehicle.id)
        )

    maintenance_records = list_maintenance_records(vehicle.id)

    return render_template(
        "fleet/maintenance.html",
        vehicle=vehicle,
        maintenance_records=maintenance_records,
    )


@fleet_bp.route("/allocations/new", methods=["GET", "POST"])
@login_required
@role_required("Fleet Manager")
def new_allocation():
    if request.method == "POST":
        driver_id = request.form.get("driver_id", type=int)
        conductor_id = request.form.get("conductor_id", type=int)
        vehicle_id = request.form.get("vehicle_id", type=int)
        route_id = request.form.get("route_id", type=int)

        if not all(
            [driver_id, conductor_id, vehicle_id, route_id]
        ):
            flash(
                "Please select a driver, conductor, vehicle and route."
            )
            return redirect(url_for("fleet.new_allocation"))

        try:
            allocation = create_allocation(
                driver_id=driver_id,
                conductor_id=conductor_id,
                vehicle_id=vehicle_id,
                route_id=route_id,
                created_by=current_user.employee.id,
            )

        except ValueError as error:
            flash(str(error))
            return redirect(url_for("fleet.new_allocation"))

        log_action(
            "Created allocation",
            "allocations",
            allocation.id,
        )

        flash("Vehicle allocation created successfully.")

        return redirect(
            url_for(
                "fleet.view_vehicle",
                id=allocation.vehicle_id,
            )
        )

    form_data = get_allocation_form_data()

    return render_template(
        "fleet/new_allocation.html",
        **form_data,
    )


@fleet_bp.route("/allocations/<int:id>/end", methods=["POST"])
@login_required
@role_required("Fleet Manager")
def end_allocation(id):
    allocation = get_allocation(id)

    if allocation is None:
        abort(404)

    try:
        close_allocation(allocation)

    except ValueError as error:
        flash(str(error))
        return redirect(
            url_for(
                "fleet.view_vehicle",
                id=allocation.vehicle_id,
            )
        )

    log_action(
        "Ended allocation",
        "allocations",
        allocation.id,
    )

    flash("Vehicle allocation ended successfully.")

    return redirect(
        url_for(
            "fleet.view_vehicle",
            id=allocation.vehicle_id,
        )
    )


@fleet_bp.route("/accidents/new", methods=["GET", "POST"])
@login_required
@role_required("Inspector")
def new_accident():
    form_data = get_accident_form_data()

    if request.method == "POST":
        try:
            accident_date = parse_optional_datetime(
                request.form.get("date", "")
            )

            accident = create_accident(
                vehicle_id=request.form.get("vehicle_id", type=int),
                driver_id=(
                    request.form.get("driver_id", type=int) or None
                ),
                reported_by=current_user.employee.id,
                description=request.form.get("description", ""),
                accident_date=accident_date or datetime.utcnow(),
            )

        except ValueError as error:
            flash(str(error))
            return redirect(url_for("fleet.new_accident"))

        log_action(
            "Reported accident",
            "accidents",
            accident.id,
        )

        flash("Accident reported successfully.")

        return redirect(url_for("fleet.new_accident"))

    return render_template(
        "fleet/new_accident.html",
        **form_data,
    )


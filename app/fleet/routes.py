from datetime import datetime, date

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)

from flask_login import login_required, current_user

from app.extensions import db

from app.models import (
    Employee,
    Vehicle,
    VehicleDocument,
    MaintenanceRecord,
    Allocation,
    Accident,
    Route,
)

from app.auth.decorators import role_required
from app.utils.audit import log_action


fleet_bp = Blueprint(
    "fleet",
    __name__,
    url_prefix="/fleet"
)


# ============================================================
# VEHICLES
# ============================================================

@fleet_bp.route("/vehicles")
@login_required
@role_required(
    "Fleet Manager",
    "Fleet Officer",
    "Inspector",
)
def list_vehicles():

    vehicles = (
        Vehicle.query
        .order_by(Vehicle.id)
        .all()
    )

    return render_template(
        "fleet/vehicles.html",
        vehicles=vehicles,
    )


@fleet_bp.route(
    "/vehicles/new",
    methods=["GET", "POST"]
)
@login_required
@role_required("Fleet Manager")
def new_vehicle():

    if request.method == "POST":

        reg_no = request.form["reg_no"].strip()

        existing = Vehicle.query.filter_by(
            reg_no=reg_no
        ).first()

        if existing:

            flash(
                "A vehicle with this registration number "
                "already exists."
            )

            return redirect(
                url_for("fleet.new_vehicle")
            )

        vehicle = Vehicle(
            reg_no=reg_no,
            make=request.form.get("make"),
            year=request.form.get(
                "year",
                type=int
            ),
            type=request.form.get("type"),
            ownership=request.form.get("ownership"),
            status="active",
        )

        db.session.add(vehicle)
        db.session.commit()

        log_action(
            "Created vehicle",
            "vehicles",
            vehicle.id,
        )

        flash(
            f"Vehicle {vehicle.reg_no} added successfully."
        )

        return redirect(
            url_for("fleet.view_vehicle", id=vehicle.id)
        )

    return render_template(
        "fleet/new_vehicle.html"
    )


@fleet_bp.route("/vehicles/<int:id>")
@login_required
@role_required(
    "Fleet Manager",
    "Fleet Officer",
    "Inspector",
)
def view_vehicle(id):

    vehicle = Vehicle.query.get_or_404(id)

    documents = (
        VehicleDocument.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            VehicleDocument.expiry_date
        )
        .all()
    )

    maintenance_records = (
        MaintenanceRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            MaintenanceRecord.date.desc()
        )
        .all()
    )

    allocations = (
        Allocation.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            Allocation.started_at.desc()
        )
        .all()
    )

    accidents = (
        Accident.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            Accident.date.desc()
        )
        .all()
    )

    return render_template(
        "fleet/vehicle_profile.html",
        vehicle=vehicle,
        documents=documents,
        maintenance_records=maintenance_records,
        allocations=allocations,
        accidents=accidents,
        today=date.today(),
    )


@fleet_bp.route(
    "/vehicles/<int:id>/status",
    methods=["POST"]
)
@login_required
@role_required("Fleet Manager")
def change_vehicle_status(id):

    vehicle = Vehicle.query.get_or_404(id)

    old_status = vehicle.status

    new_status = request.form.get("status")

    allowed_statuses = [
        "active",
        "under_maintenance",
        "out_of_service",
        "retired",
    ]

    if new_status not in allowed_statuses:

        flash("Invalid vehicle status.")

        return redirect(
            url_for(
                "fleet.view_vehicle",
                id=vehicle.id
            )
        )

    vehicle.status = new_status

    db.session.commit()

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
        url_for(
            "fleet.view_vehicle",
            id=vehicle.id
        )
    )


# ============================================================
# VEHICLE DOCUMENTS
# ============================================================

@fleet_bp.route(
    "/vehicles/<int:id>/documents",
    methods=["GET", "POST"]
)
@login_required
@role_required("Fleet Manager")
def vehicle_documents(id):

    vehicle = Vehicle.query.get_or_404(id)

    if request.method == "POST":

        document = VehicleDocument(
            vehicle_id=vehicle.id,
            doc_type=request.form["doc_type"],
            document_number=request.form.get(
                "document_number"
            ),
            issue_date=request.form.get(
                "issue_date",
                type=date.fromisoformat
            ) if request.form.get("issue_date") else None,
            expiry_date=request.form.get(
                "expiry_date",
                type=date.fromisoformat
            ) if request.form.get("expiry_date") else None,
        )

        db.session.add(document)
        db.session.commit()

        log_action(
            "Added vehicle document",
            "vehicle_documents",
            document.id,
        )

        flash(
            "Vehicle document added successfully."
        )

        return redirect(
            url_for(
                "fleet.vehicle_documents",
                id=vehicle.id
            )
        )

    documents = (
        VehicleDocument.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            VehicleDocument.expiry_date
        )
        .all()
    )

    return render_template(
        "fleet/documents.html",
        vehicle=vehicle,
        documents=documents,
        today=date.today(),
    )


# ============================================================
# MAINTENANCE
# ============================================================

@fleet_bp.route(
    "/vehicles/<int:id>/maintenance",
    methods=["GET", "POST"]
)
@login_required
@role_required("Fleet Manager")
def vehicle_maintenance(id):

    vehicle = Vehicle.query.get_or_404(id)

    if request.method == "POST":

        maintenance = MaintenanceRecord(
            vehicle_id=vehicle.id,
            created_by=current_user.employee.id,
            description=request.form["description"],
            cost=request.form.get(
                "cost",
                type=float
            ),
            date=request.form.get(
                "date",
                type=date.fromisoformat
            ) if request.form.get("date") else date.today(),
        )

        db.session.add(maintenance)

        db.session.commit()

        log_action(
            "Added maintenance record",
            "maintenance_records",
            maintenance.id,
        )

        flash(
            "Maintenance record added successfully."
        )

        return redirect(
            url_for(
                "fleet.vehicle_maintenance",
                id=vehicle.id
            )
        )

    maintenance_records = (
        MaintenanceRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            MaintenanceRecord.date.desc()
        )
        .all()
    )

    return render_template(
        "fleet/maintenance.html",
        vehicle=vehicle,
        maintenance_records=maintenance_records,
    )


# ============================================================
# ALLOCATIONS
# ============================================================

@fleet_bp.route(
    "/allocations/new",
    methods=["GET", "POST"]
)
@login_required
@role_required("Fleet Manager")
def new_allocation():

    if request.method == "POST":

        driver_id = request.form.get(
            "driver_id",
            type=int
        )

        conductor_id = request.form.get(
            "conductor_id",
            type=int
        )

        vehicle_id = request.form.get(
            "vehicle_id",
            type=int
        )

        route_id = request.form.get(
            "route_id",
            type=int
        )

        if not all([
            driver_id,
            conductor_id,
            vehicle_id,
            route_id,
        ]):

            flash(
                "Please select a driver, conductor, "
                "vehicle and route."
            )

            return redirect(
                url_for("fleet.new_allocation")
            )

        driver = Employee.query.get_or_404(
            driver_id
        )

        conductor = Employee.query.get_or_404(
            conductor_id
        )

        vehicle = Vehicle.query.get_or_404(
            vehicle_id
        )

        route = Route.query.get_or_404(
            route_id
        )

        # ----------------------------------------------------
        # Validate driver role
        # ----------------------------------------------------

        if driver.role.name != "Driver":

            flash(
                "The selected employee is not a Driver."
            )

            return redirect(
                url_for("fleet.new_allocation")
            )

        # ----------------------------------------------------
        # Validate conductor role
        # ----------------------------------------------------

        if conductor.role.name != "Conductor":

            flash(
                "The selected employee is not a Conductor."
            )

            return redirect(
                url_for("fleet.new_allocation")
            )

        # ----------------------------------------------------
        # Only active employees can be allocated
        # ----------------------------------------------------

        if driver.status != "active":

            flash(
                "The selected driver is not active."
            )

            return redirect(
                url_for("fleet.new_allocation")
            )

        if conductor.status != "active":

            flash(
                "The selected conductor is not active."
            )

            return redirect(
                url_for("fleet.new_allocation")
            )

        # ----------------------------------------------------
        # Check active allocation conflicts
        #
        # A driver or vehicle may only have one active
        # allocation at a time.
        # ----------------------------------------------------

        conflict = Allocation.query.filter(
            Allocation.status == "active",
            db.or_(
                Allocation.driver_id == driver.id,
                Allocation.vehicle_id == vehicle.id,
            ),
        ).first()

        if conflict:

            if conflict.driver_id == driver.id:

                flash(
                    "This driver already has an active "
                    "allocation. End it first before "
                    "creating a new one."
                )

            elif conflict.vehicle_id == vehicle.id:

                flash(
                    "This vehicle already has an active "
                    "allocation. End it first before "
                    "creating a new one."
                )

            return redirect(
                url_for("fleet.new_allocation")
            )

        allocation = Allocation(
            driver_id=driver.id,
            conductor_id=conductor.id,
            vehicle_id=vehicle.id,
            route_id=route.id,
            status="active",
            created_by=current_user.employee.id,
        )

        db.session.add(allocation)

        db.session.commit()

        log_action(
            "Created allocation",
            "allocations",
            allocation.id,
        )

        flash(
            "Vehicle allocation created successfully."
        )

        return redirect(
            url_for(
                "fleet.view_vehicle",
                id=vehicle.id
            )
        )

    drivers = (
        Employee.query
        .join(Employee.role)
        .filter(
            Employee.status == "active",
            # Role name is checked below as well.
        )
        .all()
    )

    drivers = [
        employee
        for employee in drivers
        if employee.role.name == "Driver"
    ]

    conductors = (
        Employee.query
        .filter_by(status="active")
        .all()
    )

    conductors = [
        employee
        for employee in conductors
        if employee.role.name == "Conductor"
    ]

    vehicles = (
        Vehicle.query
        .filter(
            Vehicle.status != "retired"
        )
        .order_by(Vehicle.reg_no)
        .all()
    )

    routes = (
        Route.query
        .order_by(Route.name)
        .all()
    )

    return render_template(
        "fleet/new_allocation.html",
        drivers=drivers,
        conductors=conductors,
        vehicles=vehicles,
        routes=routes,
    )


@fleet_bp.route(
    "/allocations/<int:id>/end",
    methods=["POST"]
)
@login_required
@role_required("Fleet Manager")
def end_allocation(id):

    allocation = Allocation.query.get_or_404(id)

    if allocation.status != "active":

        flash(
            "This allocation has already ended."
        )

        return redirect(
            url_for(
                "fleet.view_vehicle",
                id=allocation.vehicle_id
            )
        )

    allocation.status = "ended"
    allocation.ended_at = datetime.utcnow()

    db.session.commit()

    log_action(
        "Ended allocation",
        "allocations",
        allocation.id,
    )

    flash(
        "Vehicle allocation ended successfully."
    )

    return redirect(
        url_for(
            "fleet.view_vehicle",
            id=allocation.vehicle_id
        )
    )


# ============================================================
# ACCIDENTS
# ============================================================

@fleet_bp.route(
    "/accidents/new",
    methods=["GET", "POST"]
)
@login_required
@role_required("Inspector")
def new_accident():

    vehicles = (
        Vehicle.query
        .order_by(Vehicle.reg_no)
        .all()
    )

    drivers = (
        Employee.query
        .filter_by(status="active")
        .all()
    )

    drivers = [
        employee
        for employee in drivers
        if employee.role.name == "Driver"
    ]

    if request.method == "POST":

        accident = Accident(
            vehicle_id=request.form.get(
                "vehicle_id",
                type=int
            ),
            driver_id=request.form.get(
                "driver_id",
                type=int
            ) or None,
            reported_by=current_user.employee.id,
            description=request.form["description"],
            date=request.form.get(
                "date",
                type=datetime.fromisoformat
            ) if request.form.get("date") else datetime.utcnow(),
        )

        db.session.add(accident)

        db.session.commit()

        log_action(
            "Reported accident",
            "accidents",
            accident.id,
        )

        flash(
            "Accident reported successfully."
        )

        return redirect(
            url_for(
                "fleet.new_accident"
            )
        )

    return render_template(
        "fleet/new_accident.html",
        vehicles=vehicles,
        drivers=drivers,
    )


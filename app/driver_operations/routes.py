from flask import Blueprint, render_template, abort
from flask_login import login_required

from app.extensions import db
from app.auth.decorators import role_required

from app.models.core import Employee
from app.models.fleet import Allocation, Vehicle
from app.models.operations import Route
from app.models.driver_conductor import TripLog


driver_operations_bp = Blueprint(
    "driver_operations",
    __name__,
    url_prefix="/driver-operations",
    template_folder="../templates/driver_operations",
)


# ============================================================
# DRIVER OPERATIONS OVERVIEW
# ============================================================

@driver_operations_bp.route("/")
@login_required
@role_required("Driver Operations Supervisor")
def index():

    drivers = (
        Employee.query
        .join(Employee.role)
        .filter(
            Employee.status == "active",
            Employee.role.has(name="Driver"),
        )
        .order_by(Employee.first_name)
        .all()
    )

    active_allocations = (
        Allocation.query
        .filter_by(status="active")
        .count()
    )

    total_trip_logs = TripLog.query.count()

    return render_template(
        "driver_operations/index.html",
        drivers=drivers,
        active_allocations=active_allocations,
        total_trip_logs=total_trip_logs,
    )


# ============================================================
# VIEW DRIVERS AND THEIR ASSIGNMENTS
# ============================================================

@driver_operations_bp.route("/drivers")
@login_required
@role_required("Driver Operations Supervisor")
def list_drivers():

    drivers = (
        Employee.query
        .filter(
            Employee.status == "active",
            Employee.role.has(name="Driver"),
        )
        .order_by(Employee.first_name)
        .all()
    )

    allocations = (
        Allocation.query
        .filter_by(status="active")
        .all()
    )

    allocations_by_driver = {
        allocation.driver_id: allocation
        for allocation in allocations
    }

    vehicles = {
        vehicle.id: vehicle
        for vehicle in Vehicle.query.all()
    }

    routes = {
        route.id: route
        for route in Route.query.all()
    }

    return render_template(
        "driver_operations/drivers.html",
        drivers=drivers,
        allocations_by_driver=allocations_by_driver,
        vehicles=vehicles,
        routes=routes,
    )
# ============================================================
# VIEW ALL DRIVER TRIP LOGS
# ============================================================

@driver_operations_bp.route("/trip-logs")
@login_required
@role_required("Driver Operations Supervisor")
def list_trip_logs():

    trip_logs = (
        TripLog.query
        .order_by(TripLog.start_time.desc())
        .all()
    )

    drivers = {
        employee.id: employee
        for employee in Employee.query.all()
    }

    allocations = {
        allocation.id: allocation
        for allocation in Allocation.query.all()
    }

    vehicles = {
        vehicle.id: vehicle
        for vehicle in Vehicle.query.all()
    }

    routes = {
        route.id: route
        for route in Route.query.all()
    }

    return render_template(
        "driver_operations/trip_logs.html",
        trip_logs=trip_logs,
        drivers=drivers,
        allocations=allocations,
        vehicles=vehicles,
        routes=routes,
    )


# ============================================================
# VIEW ONE TRIP LOG
# ============================================================

@driver_operations_bp.route("/trip-logs/<int:trip_log_id>")
@login_required
@role_required("Driver Operations Supervisor")
def view_trip_log(trip_log_id):

    trip_log = db.session.get(
        TripLog,
        trip_log_id,
    )

    if trip_log is None:
        abort(404)

    driver = db.session.get(
        Employee,
        trip_log.driver_id,
    )

    allocation = db.session.get(
        Allocation,
        trip_log.allocation_id,
    )

    vehicle = None
    route = None

    if allocation:
        vehicle = db.session.get(
            Vehicle,
            allocation.vehicle_id,
        )

        route = db.session.get(
            Route,
            allocation.route_id,
        )

    return render_template(
        "driver_operations/trip_log_profile.html",
        trip_log=trip_log,
        driver=driver,
        allocation=allocation,
        vehicle=vehicle,
        route=route,
    )
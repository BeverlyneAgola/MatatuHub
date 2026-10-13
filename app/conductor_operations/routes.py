from flask import Blueprint, render_template, abort
from flask_login import login_required

from app.extensions import db
from app.auth.decorators import role_required

from app.models.core import Employee
from app.models.fleet import Allocation, Vehicle
from app.models.operations import Route
from app.models.driver_conductor import PaymentLog


conductor_operations_bp = Blueprint(
    "conductor_operations",
    __name__,
    url_prefix="/conductor-operations",
    template_folder="../templates/conductor_operations",
)


# ============================================================
# CONDUCTOR OPERATIONS SUPERVISOR DASHBOARD
# ============================================================

@conductor_operations_bp.route("/")
@login_required
@role_required("Conductor Operations Supervisor")
def index():

    conductors = (
        Employee.query
        .filter(
            Employee.status == "active",
            Employee.role.has(name="Conductor"),
        )
        .order_by(Employee.first_name)
        .all()
    )

    conductor_ids = [conductor.id for conductor in conductors]

    active_allocations = (
        Allocation.query
        .filter(
            Allocation.status == "active",
            Allocation.conductor_id.in_(conductor_ids),
        )
        .count()
    ) if conductor_ids else 0

    total_payment_logs = (
        PaymentLog.query
        .filter(PaymentLog.conductor_id.in_(conductor_ids))
        .count()
    ) if conductor_ids else 0

    pending_payments = (
        PaymentLog.query
        .filter(
            PaymentLog.conductor_id.in_(conductor_ids),
            PaymentLog.payment_status == "pending",
        )
        .count()
    ) if conductor_ids else 0

    return render_template(
        "conductor_operations/index.html",
        conductors=conductors,
        active_allocations=active_allocations,
        total_payment_logs=total_payment_logs,
        pending_payments=pending_payments,
    )


# ============================================================
# VIEW ACTIVE CONDUCTORS
# ============================================================

@conductor_operations_bp.route("/conductors")
@login_required
@role_required("Conductor Operations Supervisor")
def list_conductors():

    conductors = (
        Employee.query
        .filter(
            Employee.status == "active",
            Employee.role.has(name="Conductor"),
        )
        .order_by(Employee.first_name)
        .all()
    )

    conductor_ids = [conductor.id for conductor in conductors]

    allocations = (
        Allocation.query
        .filter(
            Allocation.status == "active",
            Allocation.conductor_id.in_(conductor_ids),
        )
        .all()
    ) if conductor_ids else []

    allocations_by_conductor = {
        allocation.conductor_id: allocation
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
        "conductor_operations/conductors.html",
        conductors=conductors,
        allocations_by_conductor=allocations_by_conductor,
        vehicles=vehicles,
        routes=routes,
    )


# ============================================================
# VIEW PAYMENT LOGS
# ============================================================

@conductor_operations_bp.route("/payment-logs")
@login_required
@role_required("Conductor Operations Supervisor")
def list_payment_logs():

    conductors = (
        Employee.query
        .filter(Employee.role.has(name="Conductor"))
        .all()
    )

    conductor_ids = [conductor.id for conductor in conductors]

    payment_logs = (
        PaymentLog.query
        .filter(PaymentLog.conductor_id.in_(conductor_ids))
        .order_by(PaymentLog.created_at.desc())
        .all()
    ) if conductor_ids else []

    conductors_by_id = {
        conductor.id: conductor
        for conductor in conductors
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
        "conductor_operations/payment_logs.html",
        payment_logs=payment_logs,
        conductors=conductors_by_id,
        allocations=allocations,
        vehicles=vehicles,
        routes=routes,
    )


# ============================================================
# VIEW INDIVIDUAL PAYMENT LOG
# ============================================================

@conductor_operations_bp.route(
    "/payment-logs/<int:payment_log_id>"
)
@login_required
@role_required("Conductor Operations Supervisor")
def view_payment_log(payment_log_id):

    payment_log = db.session.get(
        PaymentLog,
        payment_log_id,
    )

    if payment_log is None:
        abort(404)

    conductor = db.session.get(
        Employee,
        payment_log.conductor_id,
    )

    allocation = db.session.get(
        Allocation,
        payment_log.allocation_id,
    )

    vehicle = db.session.get(
        Vehicle,
        payment_log.vehicle_id,
    )

    route = db.session.get(
        Route,
        payment_log.route_id,
    )

    return render_template(
        "conductor_operations/payment_log_profile.html",
        payment_log=payment_log,
        conductor=conductor,
        allocation=allocation,
        vehicle=vehicle,
        route=route,
    )
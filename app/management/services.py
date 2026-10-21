from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import aliased

from app.extensions import db
from app.models import (
    Employee,
    Vehicle,
    Route,
    Fare,
    Claim,
    Accident,
    Allocation,
    Complaint,
    PaymentLog,
)


# --------------------------------------------------
# MANAGEMENT DASHBOARD STATISTICS
# --------------------------------------------------

def get_dashboard_statistics():
    today = date.today()
    tomorrow = today + timedelta(days=1)

    today_start = datetime.combine(today, time.min)
    tomorrow_start = datetime.combine(tomorrow, time.min)

    total_employees = Employee.query.count()

    active_employees = Employee.query.filter_by(
        status="active"
    ).count()

    fired_employees = Employee.query.filter_by(
        status="fired"
    ).count()

    total_vehicles = Vehicle.query.count()

    active_vehicles = Vehicle.query.filter_by(
        status="active"
    ).count()

    vehicles_under_maintenance = Vehicle.query.filter_by(
        status="under_maintenance"
    ).count()

    vehicles_out_of_service = Vehicle.query.filter_by(
        status="out_of_service"
    ).count()

    retired_vehicles = Vehicle.query.filter_by(
        status="retired"
    ).count()

    total_routes = Route.query.count()

    active_routes = Route.query.filter_by(
        status="active"
    ).count()

    inactive_routes = Route.query.filter_by(
        status="inactive"
    ).count()

    total_claims = Claim.query.count()

    pending_claims = Claim.query.filter_by(
        status="pending"
    ).count()

    approved_claims = Claim.query.filter_by(
        status="approved"
    ).count()

    rejected_claims = Claim.query.filter_by(
        status="rejected"
    ).count()

    total_accidents = Accident.query.count()

    open_accidents = Accident.query.filter_by(
        status="open"
    ).count()

    active_allocations = Allocation.query.filter_by(
        status="active"
    ).count()

    total_complaints = Complaint.query.count()

    unresolved_complaints = Complaint.query.filter_by(
        status="unresolved"
    ).count()

    today_payments = PaymentLog.query.filter(
        PaymentLog.created_at >= today_start,
        PaymentLog.created_at < tomorrow_start
    )

    today_payment_count = today_payments.count()

    confirmed_payments = today_payments.filter_by(
        payment_status="confirmed"
    ).count()

    pending_payments = today_payments.filter_by(
        payment_status="pending"
    ).count()

    failed_payments = today_payments.filter_by(
        payment_status="failed"
    ).count()

    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "fired_employees": fired_employees,

        "total_vehicles": total_vehicles,
        "active_vehicles": active_vehicles,
        "vehicles_under_maintenance": vehicles_under_maintenance,
        "vehicles_out_of_service": vehicles_out_of_service,
        "retired_vehicles": retired_vehicles,

        "total_routes": total_routes,
        "active_routes": active_routes,
        "inactive_routes": inactive_routes,

        "total_claims": total_claims,
        "pending_claims": pending_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,

        "total_accidents": total_accidents,
        "open_accidents": open_accidents,

        "active_allocations": active_allocations,

        "total_complaints": total_complaints,
        "unresolved_complaints": unresolved_complaints,

        "today_payment_count": today_payment_count,
        "confirmed_payments": confirmed_payments,
        "pending_payments": pending_payments,
        "failed_payments": failed_payments,
    }


# --------------------------------------------------
# FLEET AND ALLOCATIONS
# --------------------------------------------------

def get_fleet_overview():
    """
    Returns vehicles and their active allocations, if any.
    Vehicles without active allocations are still included.
    """

    driver = aliased(Employee)
    conductor = aliased(Employee)

    rows = (
        db.session.query(
            Vehicle,
            Allocation,
            Route,
            driver,
            conductor
        )
        .outerjoin(
            Allocation,
            (Allocation.vehicle_id == Vehicle.id)
            & (Allocation.status == "active")
        )
        .outerjoin(
            Route,
            Allocation.route_id == Route.id
        )
        .outerjoin(
            driver,
            Allocation.driver_id == driver.id
        )
        .outerjoin(
            conductor,
            Allocation.conductor_id == conductor.id
        )
        .order_by(Vehicle.reg_no.asc())
        .all()
    )

    return [
        {
            "vehicle": vehicle,
            "allocation": allocation,
            "route": route,
            "driver": assigned_driver,
            "conductor": assigned_conductor,
        }
        for (
            vehicle,
            allocation,
            route,
            assigned_driver,
            assigned_conductor
        ) in rows
    ]


def get_allocation_overview(status=None):
    """
    Returns allocation records.
    Optionally filters by active or ended status.
    """

    driver = aliased(Employee)
    conductor = aliased(Employee)

    query = (
        db.session.query(
            Allocation,
            Vehicle,
            Route,
            driver,
            conductor
        )
        .join(
            Vehicle,
            Allocation.vehicle_id == Vehicle.id
        )
        .join(
            Route,
            Allocation.route_id == Route.id
        )
        .join(
            driver,
            Allocation.driver_id == driver.id
        )
        .join(
            conductor,
            Allocation.conductor_id == conductor.id
        )
    )

    if status in ("active", "ended"):
        query = query.filter(Allocation.status == status)

    rows = query.order_by(
        Allocation.started_at.desc()
    ).all()

    return [
        {
            "allocation": allocation,
            "vehicle": vehicle,
            "route": route,
            "driver": assigned_driver,
            "conductor": assigned_conductor,
        }
        for (
            allocation,
            vehicle,
            route,
            assigned_driver,
            assigned_conductor
        ) in rows
    ]


# --------------------------------------------------
# ROUTES OVERVIEW
# --------------------------------------------------

def get_routes_overview():
    routes = Route.query.order_by(Route.name.asc()).all()

    route_data = []

    for route in routes:
        fares = Fare.query.filter_by(
            route_id=route.id
        ).order_by(
            Fare.effective_from.desc()
        ).all()

        active_allocations = (
            db.session.query(Allocation)
            .filter_by(
                route_id=route.id,
                status="active"
            )
            .count()
        )

        route_data.append({
            "route": route,
            "fares": fares,
            "active_allocations": active_allocations,
        })

    return route_data


# --------------------------------------------------
# OUTSTANDING ISSUES
# --------------------------------------------------

def get_outstanding_issues():
    pending_claims = (
        Claim.query
        .filter_by(status="pending")
        .order_by(Claim.created_at.desc())
        .all()
    )

    open_accidents = (
        Accident.query
        .filter_by(status="open")
        .order_by(Accident.date.desc())
        .all()
    )

    unresolved_complaints = (
        Complaint.query
        .filter_by(status="unresolved")
        .order_by(Complaint.created_at.desc())
        .all()
    )

    return {
        "pending_claims": pending_claims,
        "open_accidents": open_accidents,
        "unresolved_complaints": unresolved_complaints,
    }


# --------------------------------------------------
# WORKFORCE OVERVIEW
# --------------------------------------------------

def get_workforce_overview():
    total_employees = Employee.query.count()

    active_employees = Employee.query.filter_by(
        status="active"
    ).count()

    fired_employees = Employee.query.filter_by(
        status="fired"
    ).count()

    # Group employees by department.
    department_rows = (
        db.session.query(
            Employee.department_id,
            db.func.count(Employee.id)
        )
        .group_by(Employee.department_id)
        .all()
    )

    department_counts = {}

    for department_id, count in department_rows:
        department = db.session.get(
            __import__("app.models", fromlist=["Department"]).Department,
            department_id
        ) if department_id is not None else None

        department_name = (
            department.name if department
            else "Unassigned"
        )

        department_counts[department_name] = count

    # Group employees by role.
    role_rows = (
        db.session.query(
            Employee.role_id,
            db.func.count(Employee.id)
        )
        .group_by(Employee.role_id)
        .all()
    )

    role_counts = {}

    for role_id, count in role_rows:
        role = db.session.get(
            __import__("app.models", fromlist=["Role"]).Role,
            role_id
        ) if role_id is not None else None

        role_name = role.name if role else "Unassigned"

        role_counts[role_name] = count

    # Show driver and conductor allocation assignments.
    driver = aliased(Employee)
    conductor = aliased(Employee)

    allocation_rows = (
        db.session.query(
            Allocation,
            Vehicle,
            Route,
            driver,
            conductor
        )
        .join(
            Vehicle,
            Allocation.vehicle_id == Vehicle.id
        )
        .join(
            Route,
            Allocation.route_id == Route.id
        )
        .join(
            driver,
            Allocation.driver_id == driver.id
        )
        .join(
            conductor,
            Allocation.conductor_id == conductor.id
        )
        .filter(Allocation.status == "active")
        .order_by(Allocation.started_at.desc())
        .all()
    )

    active_assignments = [
        {
            "allocation": allocation,
            "vehicle": vehicle,
            "route": route,
            "driver": assigned_driver,
            "conductor": assigned_conductor,
        }
        for (
            allocation,
            vehicle,
            route,
            assigned_driver,
            assigned_conductor
        ) in allocation_rows
    ]

    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "fired_employees": fired_employees,
        "department_counts": department_counts,
        "role_counts": role_counts,
        "active_assignments": active_assignments,
    }


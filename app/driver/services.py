from datetime import datetime

from app.extensions import db

from app.models.fleet import Allocation, Vehicle
from app.models.operations import Route
from app.models.driver_conductor import TripLog


# ============================================================
# GET DRIVER'S ACTIVE VEHICLE ASSIGNMENT
# ============================================================

def get_driver_active_assignment(employee_id):

    return (
        Allocation.query
        .filter_by(
            driver_id=employee_id,
            status="active",
        )
        .order_by(
            Allocation.started_at.desc()
        )
        .first()
    )


# ============================================================
# GET DRIVER'S TRIP HISTORY
# ============================================================

def get_driver_trip_logs(employee_id):

    return (
        TripLog.query
        .filter_by(
            driver_id=employee_id
        )
        .order_by(
            TripLog.start_time.desc()
        )
        .all()
    )


# ============================================================
# GET VEHICLE AND ROUTE DETAILS
# ============================================================

def get_driver_assignment_details(allocation):

    if allocation is None:
        return None, None

    vehicle = db.session.get(
        Vehicle,
        allocation.vehicle_id,
    )

    route = db.session.get(
        Route,
        allocation.route_id,
    )

    return vehicle, route


# ============================================================
# CREATE DRIVER TRIP LOG
# ============================================================

def create_driver_trip_log(
    employee_id,
    allocation_id,
    notes=None,
):

    # Confirm that this allocation belongs to the driver
    # and is still active.

    allocation = (
        Allocation.query
        .filter_by(
            id=allocation_id,
            driver_id=employee_id,
            status="active",
        )
        .first()
    )

    if allocation is None:

        return (
            None,
            "No matching active vehicle allocation was found.",
        )

    # Create the trip record.

    trip = TripLog(
        allocation_id=allocation.id,
        driver_id=employee_id,
        start_time=datetime.utcnow(),
        notes=(
            notes.strip()
            if notes and notes.strip()
            else None
        ),
    )

    db.session.add(trip)
    db.session.commit()

    return trip, None
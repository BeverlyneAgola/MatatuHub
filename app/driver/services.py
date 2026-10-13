from datetime import datetime

from app.extensions import db
from app.models.fleet import Allocation
from app.models.fleet import Vehicle
from app.models.operations import Route
from app.models.driver_conductor import TripLog


def get_driver_active_assignment(employee_id):
    """Return the driver's active vehicle and route allocation."""

    return (
        Allocation.query
        .filter_by(
            driver_id=employee_id,
            status="active"
        )
        .order_by(Allocation.started_at.desc())
        .first()
    )


def get_driver_trip_logs(employee_id):
    """Return trip logs belonging to the specified driver."""

    return (
        TripLog.query
        .filter_by(driver_id=employee_id)
        .order_by(TripLog.start_time.desc())
        .all()
    )


def get_driver_assignment_details(allocation):
    """Return the vehicle and route attached to an allocation."""
    return (
        db.session.get(Vehicle, allocation.vehicle_id),
        db.session.get(Route, allocation.route_id),
    )


def create_driver_trip_log(employee_id, allocation_id, notes=None):
    """Create a trip log for the driver's own active allocation."""

    allocation = (
        Allocation.query
        .filter_by(
            id=allocation_id,
            driver_id=employee_id,
            status="active"
        )
        .first()
    )

    if allocation is None:
        return None, "No matching active allocation was found."

    trip = TripLog(
        allocation_id=allocation.id,
        driver_id=employee_id,
        start_time=datetime.utcnow(),
        notes=notes.strip() if notes and notes.strip() else None
    )

    db.session.add(trip)
    db.session.commit()

    return trip, None
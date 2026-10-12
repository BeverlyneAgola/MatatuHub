from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from app.extensions import db
from app.models.fleet import Allocation
from app.models.operations import Fare
from app.models.driver_conductor import PaymentLog

def detect_time_band():

    hour = datetime.now().hour

    if 6 <= hour <= 9 or 17 <= hour <= 20:
        return "peak"

    return "off_peak"


def get_conductor_active_assignment(employee_id):

    return (
        Allocation.query
        .filter_by(
            conductor_id=employee_id,
            status="active"
        )
        .order_by(Allocation.started_at.desc())
        .first()
    )


def get_current_fare(route_id, direction, time_band):


    today = date.today()

    return (
        Fare.query
        .filter(
            Fare.route_id == route_id,
            Fare.direction == direction,
            Fare.time_band == time_band,
            Fare.effective_from <= today,
            db.or_(
                Fare.effective_until.is_(None),
                Fare.effective_until >= today
            )
        )
        .order_by(Fare.effective_from.desc(), Fare.id.desc())
        .first()
    )


def get_available_directions(route_id):


    today = date.today()
    time_band = detect_time_band()

    fares = (
        Fare.query
        .filter(
            Fare.route_id == route_id,
            Fare.time_band == time_band,
            Fare.effective_from <= today,
            db.or_(
                Fare.effective_until.is_(None),
                Fare.effective_until >= today
            )
        )
        .order_by(Fare.direction.asc())
        .all()
    )

    return list(dict.fromkeys(fare.direction for fare in fares))


def create_payment_log(
employee_id,
allocation_id,
direction,
commuter_phone,
amount_given
):

    allocation = (
        Allocation.query
        .filter_by(
            id=allocation_id,
            conductor_id=employee_id,
            status="active"
        )
        .first()
    )

    if allocation is None:
        return None, "Your active allocation could not be found."

    direction = direction.strip()
    commuter_phone = commuter_phone.strip()

    if not direction:
        return None, "Please select a fare direction."

    if not commuter_phone:
        return None, "The commuter's phone number is required."

    if len(commuter_phone) > 20:
        return None, "The phone number is too long."

    try:
        amount_given = Decimal(amount_given)

    except (InvalidOperation, TypeError, ValueError):
        return None, "Enter a valid amount received."

    if not amount_given.is_finite() or amount_given <= 0:
        return None, "The amount received must be greater than zero."

    time_band = detect_time_band()

    fare = get_current_fare(
        allocation.route_id,
        direction,
        time_band
    )

    if fare is None:
        return None, (
            f"No current {time_band} fare exists for "
            f"the selected direction."
        )

    fare_amount = Decimal(str(fare.amount))

    if amount_given < fare_amount:
        return None, (
            f"The fare is KSh {fare_amount:.2f}. "
            "The amount received is insufficient."
        )

    change_given = amount_given - fare_amount

    payment = PaymentLog(
        conductor_id=employee_id,
        allocation_id=allocation.id,
        route_id=allocation.route_id,
        vehicle_id=allocation.vehicle_id,
        direction=direction,
        time_band=time_band,
        fare_amount=fare_amount,
        amount_given=amount_given,
        change_given=change_given,
        commuter_phone=commuter_phone,
        payment_status="pending"
    )

    return payment, None


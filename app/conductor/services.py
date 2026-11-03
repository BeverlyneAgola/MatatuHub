from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation

from flask import current_app

from app.extensions import db
from app.models.fleet import Allocation, Vehicle
from app.models.operations import Fare, Route
from app.models.driver_conductor import PaymentLog

from app.payments.daraja_service import (
    DarajaError,
    initiate_stk_push,
    normalize_phone_number,
)


def get_conductor_assignment_details(allocation):
    return (
        db.session.get(Vehicle, allocation.vehicle_id),
        db.session.get(Route, allocation.route_id),
    )


def get_conductor_payment_logs(employee_id):
    return (
        PaymentLog.query
        .filter_by(conductor_id=employee_id)
        .order_by(PaymentLog.created_at.desc())
        .all()
    )


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
        .order_by(
            Fare.effective_from.desc(),
            Fare.id.desc()
        )
        .first()
    )


def get_available_directions(route_id, time_band=None):
    today = date.today()
    time_band = time_band or detect_time_band()

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


def get_payment_context(route_id):
    time_band = detect_time_band()
    directions = get_available_directions(route_id, time_band)

    fares = {}

    for direction in directions:
        fare = get_current_fare(route_id, direction, time_band)

        if fare:
            fares[direction] = Decimal(str(fare.amount))

    return time_band, directions, fares


def _get_valid_allocation(employee_id, allocation_id):
    return (
        Allocation.query
        .filter_by(
            id=allocation_id,
            conductor_id=employee_id,
            status="active"
        )
        .first()
    )


def _get_valid_fare(allocation, direction, time_band):
    direction = (direction or "").strip()

    if not direction:
        return None, "Please select a fare direction."

    fare = get_current_fare(
        allocation.route_id,
        direction,
        time_band
    )

    if fare is None:
        return None, (
            f"No current {time_band} fare exists for "
            "the selected direction."
        )

    try:
        fare_amount = Decimal(str(fare.amount))
    except (InvalidOperation, TypeError, ValueError):
        return None, "The selected fare is invalid."

    if not fare_amount.is_finite() or fare_amount <= 0:
        return None, "The selected fare is invalid."

    return fare_amount, None


def record_cash_payment(
    employee_id,
    allocation_id,
    direction,
    amount_given
):
    allocation = _get_valid_allocation(employee_id, allocation_id)

    if allocation is None:
        return None, "Your active vehicle allocation could not be found."

    direction = (direction or "").strip()
    time_band = detect_time_band()

    fare_amount, error = _get_valid_fare(
        allocation,
        direction,
        time_band
    )

    if error:
        return None, error

    try:
        amount_given = Decimal(str(amount_given))
    except (InvalidOperation, TypeError, ValueError):
        return None, "Enter a valid amount received."

    if not amount_given.is_finite() or amount_given <= 0:
        return None, "The amount received must be greater than zero."

    if amount_given < fare_amount:
        return None, (
            f"The fare is KSh {fare_amount:.2f}. "
            "The amount received is insufficient."
        )

    payment = PaymentLog(
        conductor_id=employee_id,
        allocation_id=allocation.id,
        route_id=allocation.route_id,
        vehicle_id=allocation.vehicle_id,
        direction=direction,
        time_band=time_band,
        fare_amount=fare_amount,
        payment_method="cash",
        amount_given=amount_given,
        change_given=amount_given - fare_amount,
        payment_status="confirmed",
        paid_at=datetime.utcnow()
    )

    try:
        db.session.add(payment)
        db.session.commit()

        return payment, None

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to save cash payment for conductor %s.",
            employee_id
        )

        return None, "The cash payment could not be saved. Please try again."


def _mark_mpesa_payment_failed(payment_id, description):
    """
    Mark an existing M-Pesa payment as failed.

    Never attempts to retrieve a payment without a valid database ID.
    """
    if payment_id is None:
        current_app.logger.error(
            "Cannot update failed M-Pesa transaction: payment ID is missing."
        )
        return

    try:
        failed_payment = db.session.get(PaymentLog, payment_id)

        if failed_payment:
            failed_payment.payment_status = "failed"
            failed_payment.result_description = description
            db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Could not update failed M-Pesa payment %s.",
            payment_id
        )


def create_mpesa_payment(
    employee_id,
    allocation_id,
    direction,
    commuter_phone
):
    allocation = _get_valid_allocation(employee_id, allocation_id)

    if allocation is None:
        return None, "Your active vehicle allocation could not be found."

    direction = (direction or "").strip()
    commuter_phone = (commuter_phone or "").strip()
    time_band = detect_time_band()

    fare_amount, error = _get_valid_fare(
        allocation,
        direction,
        time_band
    )

    if error:
        return None, error

    # Validate the fare and normalize the phone number.
    try:
        if (
            not fare_amount.is_finite()
            or fare_amount <= 0
            or fare_amount != fare_amount.to_integral_value()
        ):
            return None, (
                "The fare must be a positive whole-number KSh amount."
            )

        commuter_phone = normalize_phone_number(commuter_phone)

    except (InvalidOperation, TypeError, ValueError, DarajaError):
        return None, "Enter a valid Kenyan commuter phone number."

    if not commuter_phone:
        return None, "The commuter's phone number is required."

    duplicate_cutoff = datetime.utcnow() - timedelta(minutes=2)

    existing_request = (
        PaymentLog.query
        .filter_by(
            conductor_id=employee_id,
            allocation_id=allocation.id,
            direction=direction,
            time_band=time_band,
            fare_amount=fare_amount,
            commuter_phone=commuter_phone,
            payment_method="mpesa",
            payment_status="pending",
        )
        .filter(
            PaymentLog.created_at >= duplicate_cutoff
        )
        .first()
    )

    if existing_request:
        return None, (
            "A matching M-Pesa request is already being processed. "
            "Please wait for its result before trying again."
        )

    payment = PaymentLog(
        conductor_id=employee_id,
        allocation_id=allocation.id,
        route_id=allocation.route_id,
        vehicle_id=allocation.vehicle_id,
        direction=direction,
        time_band=time_band,
        fare_amount=fare_amount,
        payment_method="mpesa",
        commuter_phone=commuter_phone,
        payment_status="pending"
    )

    payment_id = None

    # First save the transaction so it has a database ID
    # before sending the STK Push.
    try:
        db.session.add(payment)
        db.session.commit()

        payment_id = payment.id

        if payment_id is None:
            raise RuntimeError(
                "The M-Pesa transaction was saved without a payment ID."
            )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Failed to create M-Pesa payment record for conductor %s.",
            employee_id
        )

        return None, (
            "The M-Pesa transaction could not be created. Please try again."
        )

    # Initiate the STK Push.
    try:
        vehicle = db.session.get(Vehicle, allocation.vehicle_id)

        if vehicle is None or not vehicle.reg_no:
            raise DarajaError(
                "The allocated vehicle registration number could not be found."
            )

        account_reference = f"MH-{vehicle.reg_no}"

        response = initiate_stk_push(
            phone_number=commuter_phone,
            amount=int(fare_amount),
            account_reference=account_reference,
            transaction_description="MatatuHub Fare",
        )

        if not isinstance(response, dict):
            raise DarajaError(
                "Daraja returned an invalid response."
            )

        checkout_request_id = response.get("CheckoutRequestID")
        merchant_request_id = response.get("MerchantRequestID")

        if not checkout_request_id or not merchant_request_id:
            raise DarajaError(
                "Daraja did not return the required request identifiers."
            )

        payment.checkout_request_id = checkout_request_id
        payment.merchant_request_id = merchant_request_id
        payment.stk_sent_at = datetime.utcnow()

        db.session.commit()

        return payment, None

    except DarajaError as error:
        db.session.rollback()

        current_app.logger.warning(
            "Daraja STK Push failed for payment %s: %s",
            payment_id,
            error
        )

        _mark_mpesa_payment_failed(
            payment_id,
            str(error)
        )

        return None, (
            "The M-Pesa request could not be sent. Please try again."
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Unexpected error while initiating M-Pesa payment %s.",
            payment_id
        )

        _mark_mpesa_payment_failed(
            payment_id,
            "An unexpected error occurred while initiating STK Push."
        )

        return None, (
            "An unexpected error occurred while initiating M-Pesa."
        )
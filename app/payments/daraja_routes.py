from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.driver_conductor import PaymentLog

from app.payments.daraja_service import normalize_phone_number


payments_bp = Blueprint(
    "payments",
    __name__,
    url_prefix="/payments",
)


def get_callback_metadata(callback_body):
    callback = callback_body.get("Body", {}).get("stkCallback", {})
    metadata = callback.get("CallbackMetadata", {}).get("Item", [])

    return {
        item.get("Name"): item.get("Value")
        for item in metadata
        if item.get("Name")
    }


@payments_bp.route("/mpesa/callback", methods=["POST"])
def mpesa_callback():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "ResultCode": 1,
            "ResultDesc": "Invalid callback payload."
        }), 200

    callback = data.get("Body", {}).get("stkCallback", {})

    checkout_request_id = callback.get("CheckoutRequestID")
    merchant_request_id = callback.get("MerchantRequestID")
    result_code = callback.get("ResultCode")
    result_description = callback.get("ResultDesc", "")

    if not checkout_request_id:
        return jsonify({
            "ResultCode": 1,
            "ResultDesc": "Missing CheckoutRequestID."
        }), 200

    payment = (
        PaymentLog.query
        .filter_by(checkout_request_id=checkout_request_id)
        .with_for_update()
        .first()
    )

    if payment is None:
        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Callback received."
        }), 200

    # Ignore repeated callbacks for an already completed transaction.
    if payment.payment_status in ("confirmed", "failed"):
        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Callback already processed."
        }), 200

    payment.result_code = str(result_code)
    payment.result_description = result_description

    if (
        payment.merchant_request_id
        and merchant_request_id
        and payment.merchant_request_id != merchant_request_id
    ):
        payment.payment_status = "failed"
        payment.result_description = "MerchantRequestID mismatch."

        db.session.commit()

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Callback processed."
        }), 200

    if str(result_code) != "0":
        payment.payment_status = "failed"

        db.session.commit()

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Payment failure recorded."
        }), 200

    metadata = get_callback_metadata(data)

    receipt_number = metadata.get("MpesaReceiptNumber")
    callback_amount = metadata.get("Amount")
    callback_phone = metadata.get("PhoneNumber")

    if not receipt_number or callback_amount is None:
        payment.payment_status = "failed"
        payment.result_description = (
            "Successful callback did not contain the required payment details."
        )

        db.session.commit()

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Callback processed."
        }), 200

    try:
        received_amount = Decimal(str(callback_amount))
    except (InvalidOperation, TypeError, ValueError):
        received_amount = None

    if received_amount is None or received_amount != Decimal(str(payment.fare_amount)):
        payment.payment_status = "failed"
        payment.result_description = (
            "The callback amount did not match the recorded fare."
        )

        db.session.commit()

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Callback processed."
        }), 200

    if callback_phone and payment.commuter_phone:
        try:
            expected_phone = normalize_phone_number(payment.commuter_phone)
            received_phone = normalize_phone_number(str(callback_phone))

            if expected_phone != received_phone:
                payment.payment_status = "failed"
                payment.result_description = (
                    "The callback phone number did not match the payment phone number."
                )

                db.session.commit()

                return jsonify({
                    "ResultCode": 0,
                    "ResultDesc": "Callback processed."
                }), 200

        except ValueError:
            payment.payment_status = "failed"
            payment.result_description = (
                "The callback phone number could not be validated."
            )

            db.session.commit()

            return jsonify({
                "ResultCode": 0,
                "ResultDesc": "Callback processed."
            }), 200

    duplicate_receipt = (
        PaymentLog.query
        .filter(
            PaymentLog.transaction_ref == receipt_number,
            PaymentLog.id != payment.id
        )
        .first()
    )

    if duplicate_receipt:
        payment.payment_status = "failed"
        payment.result_description = (
            "This M-Pesa receipt number is already associated with another payment."
        )

        db.session.commit()

        return jsonify({
            "ResultCode": 0,
            "ResultDesc": "Callback processed."
        }), 200

    payment.transaction_ref = receipt_number
    payment.payment_status = "confirmed"
    payment.paid_at = datetime.utcnow()
    payment.result_description = result_description

    db.session.commit()

    return jsonify({
        "ResultCode": 0,
        "ResultDesc": "Payment successfully processed."
    }), 200


@payments_bp.route("/status/<int:payment_log_id>", methods=["GET"])
@login_required
def payment_status(payment_log_id):
    payment = db.session.get(PaymentLog, payment_log_id)

    if payment is None:
        abort(404)

    role_name = getattr(
        getattr(current_user, "role", None),
        "name",
        None
    )

    if role_name == "Conductor":
        employee = getattr(current_user, "employee", None)

        if employee is None or payment.conductor_id != employee.id:
            abort(403)

    elif role_name != "Conductor Operations Supervisor":
        abort(403)

    return jsonify({
        "payment_id": payment.id,
        "payment_method": payment.payment_method,
        "payment_status": payment.payment_status,
        "fare_amount": str(payment.fare_amount),
        "transaction_ref": payment.transaction_ref,
        "result_description": payment.result_description,
        "paid_at": (
            payment.paid_at.isoformat()
            if payment.paid_at
            else None
        ),
    })
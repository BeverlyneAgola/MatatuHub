from datetime import datetime
from app.extensions import db


class TripLog(db.Model):
    __tablename__ = "trip_logs"

    id = db.Column(db.Integer, primary_key=True)

    allocation_id = db.Column(
        db.Integer,
        db.ForeignKey("allocations.id"),
        nullable=False
    )

    driver_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False
    )

    start_time = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    end_time = db.Column(
        db.DateTime,
        nullable=True
    )

    notes = db.Column(db.Text)


class PaymentLog(db.Model):
    __tablename__ = "payment_logs"

    id = db.Column(db.Integer, primary_key=True)

    # Relationships
    conductor_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False
    )

    allocation_id = db.Column(
        db.Integer,
        db.ForeignKey("allocations.id"),
        nullable=False
    )

    route_id = db.Column(
        db.Integer,
        db.ForeignKey("routes.id"),
        nullable=False
    )

    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False
    )

    # Fare information
    direction = db.Column(
        db.String(50),
        nullable=False
    )

    time_band = db.Column(
        db.String(20),
        nullable=False
    )

    fare_amount = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    # Payment information
    payment_method = db.Column(
        db.String(20),
        nullable=False,
        default="cash"
    )

    amount_given = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    change_given = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    commuter_phone = db.Column(
        db.String(20),
        nullable=True
    )

    # Payment status: pending / confirmed / failed
    payment_status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    # Transaction reference (M-Pesa receipt number)
    transaction_ref = db.Column(
        db.String(50),
        nullable=True
    )

    # Safaricom Daraja STK Push information
    checkout_request_id = db.Column(
        db.String(100),
        unique=True,
        nullable=True
    )

    merchant_request_id = db.Column(
        db.String(100),
        nullable=True
    )

    stk_sent_at = db.Column(
        db.DateTime,
        nullable=True
    )

    paid_at = db.Column(
        db.DateTime,
        nullable=True
    )

    result_code = db.Column(
        db.String(20),
        nullable=True
    )

    result_description = db.Column(
        db.Text,
        nullable=True
    )

    # Record creation timestamp
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
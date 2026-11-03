import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from app.auth.routes import auth_bp, load_user
from app.conductor.routes import conductor_bp
from app.extensions import db, login_manager
from app.models import (
    Allocation,
    AuditLog,
    Department,
    Employee,
    Fare,
    PaymentLog,
    Role,
    Route,
    User,
    Vehicle,
)
from app.payments.daraja_routes import payments_bp
from app.payments.daraja_service import normalize_phone_number


class ConductorPaymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
        cls.app = Flask(__name__, template_folder=str(template_folder))
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY="test-secret",
            TESTING=True,
        )
        db.init_app(cls.app)
        login_manager.user_loader(load_user)
        login_manager.init_app(cls.app)
        cls.app.register_blueprint(auth_bp)
        cls.app.register_blueprint(conductor_bp)
        cls.app.register_blueprint(payments_bp)

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

        self.department = Department(name="Operations")
        db.session.add(self.department)
        db.session.flush()
        self.conductor_role = Role(
            name="Conductor",
            department_id=self.department.id,
        )
        self.driver_role = Role(
            name="Driver",
            department_id=self.department.id,
        )
        db.session.add_all([self.conductor_role, self.driver_role])
        db.session.flush()

        self.conductor, self.user = self.create_employee(
            self.conductor_role,
            "conductor",
        )
        self.driver, _ = self.create_employee(self.driver_role, "driver")
        self.vehicle = Vehicle(reg_no="KAA-001A")
        self.route = Route(
            name="Town route",
            start_point="Town",
            destination="CBD",
            status="active",
        )
        db.session.add_all([self.vehicle, self.route])
        db.session.flush()
        self.allocation = Allocation(
            conductor_id=self.conductor.id,
            driver_id=self.driver.id,
            vehicle_id=self.vehicle.id,
            route_id=self.route.id,
            status="active",
        )
        db.session.add(self.allocation)

        self.fares = {}
        for time_band in ("peak", "off_peak"):
            fare = Fare(
                route_id=self.route.id,
                direction="Towards CBD",
                time_band=time_band,
                amount=Decimal("50.00"),
                effective_from=date.today(),
            )
            db.session.add(fare)
            self.fares[time_band] = fare
        db.session.commit()

        self.client = self.app.test_client()
        self.login_as(self.user)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_employee(self, role, username):
        employee = Employee(
            staff_id=f"STF-{username}",
            national_id=f"NID-{username}",
            first_name=username.title(),
            last_name="Tester",
            department_id=self.department.id,
            role_id=role.id,
        )
        db.session.add(employee)
        db.session.flush()

        user = User(employee_id=employee.id, username=username)
        user.set_password("test-password")
        db.session.add(user)
        db.session.flush()
        return employee, user

    def login_as(self, user):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def current_time_band(self):
        from app.conductor.services import detect_time_band

        return detect_time_band()

    def start_mpesa_payment(self, extra_data=None):
        data = {
            "direction": "Towards CBD",
            "commuter_phone": "0712345678",
            "confirm_payment": "yes",
        }
        data.update(extra_data or {})
        return self.client.post("/conductor/payment-log/mpesa/request", data=data)

    def test_cash_and_mpesa_pages_render_independently_with_sidebar_links(self):
        cash_response = self.client.get("/conductor/payment-log/cash")
        mpesa_response = self.client.get("/conductor/payment-log/mpesa")
        assignment_response = self.client.get("/conductor/my-assignment")

        self.assertEqual(cash_response.status_code, 200)
        self.assertEqual(mpesa_response.status_code, 200)
        self.assertEqual(assignment_response.status_code, 200)
        self.assertIn(
            "My Payment History",
            assignment_response.get_data(as_text=True),
        )
        cash_html = cash_response.get_data(as_text=True)
        mpesa_html = mpesa_response.get_data(as_text=True)
        self.assertIn('action="/conductor/payment-log/cash/record"', cash_html)
        self.assertNotIn('name="commuter_phone"', cash_html)
        self.assertIn('action="/conductor/payment-log/mpesa/request"', mpesa_html)
        self.assertIn('name="commuter_phone"', mpesa_html)
        self.assertIn(
            'value="Towards CBD" data-fare="50.00"',
            mpesa_html,
        )
        self.assertIn("Towards CBD — KSh 50.00", mpesa_html)
        self.assertIn("selectedOptions[0]", mpesa_html)
        self.assertIn("Cash Payments", cash_html)
        self.assertIn("M-Pesa Payments", cash_html)
        self.assertIn("KAA-001A", cash_html)
        self.assertIn("Town - CBD", mpesa_html)

    def test_unauthenticated_users_cannot_access_payment_pages(self):
        unauthenticated = self.app.test_client().get(
            "/conductor/payment-log/cash",
            follow_redirects=False,
        )
        self.assertEqual(unauthenticated.status_code, 302)

    def test_mpesa_page_explains_when_current_time_band_has_no_fare(self):
        db.session.delete(self.fares[self.current_time_band()])
        db.session.commit()

        response = self.client.get("/conductor/payment-log/mpesa")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="mpesa_direction"', html)
        self.assertIn('name="direction"\n                required\n                disabled', html)
        self.assertIn(
            "No current "
            + self.current_time_band().replace("_", " ")
            + " fare is configured",
            html,
        )
        self.assertIn("M-Pesa requests are unavailable", html)
        self.assertNotIn("KSh 70.00", html)

    def test_wrong_role_users_cannot_access_payment_pages(self):
        self.conductor.role = self.driver_role
        db.session.commit()
        forbidden = self.client.get("/conductor/payment-log/mpesa")
        self.assertEqual(forbidden.status_code, 403, forbidden.location)

    def test_cash_exact_fare_is_confirmed_and_uses_database_fare(self):
        response = self.client.post(
            "/conductor/payment-log/cash/record",
            data={
                "direction": "Towards CBD",
                "amount_given": "50",
                "fare_amount": "0.01",
            },
        )

        payment = PaymentLog.query.one()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(payment.payment_method, "cash")
        self.assertEqual(payment.payment_status, "confirmed")
        self.assertEqual(payment.fare_amount, Decimal("50.00"))
        self.assertEqual(payment.amount_given, Decimal("50.00"))
        self.assertEqual(payment.change_given, Decimal("0.00"))
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(AuditLog.query.one().target_id, payment.id)

    def test_cash_excess_payment_calculates_change(self):
        self.client.post(
            "/conductor/payment-log/cash/record",
            data={"direction": "Towards CBD", "amount_given": "75"},
        )
        payment = PaymentLog.query.one()
        self.assertEqual(payment.amount_given, Decimal("75.00"))
        self.assertEqual(payment.change_given, Decimal("25.00"))

    def test_cash_insufficient_amount_is_not_saved(self):
        response = self.client.post(
            "/conductor/payment-log/cash/record",
            data={"direction": "Towards CBD", "amount_given": "49"},
            follow_redirects=True,
        )
        self.assertIn("insufficient", response.get_data(as_text=True).lower())
        self.assertEqual(PaymentLog.query.count(), 0)
        self.assertEqual(AuditLog.query.count(), 0)

    def test_invalid_fare_direction_is_rejected(self):
        response = self.client.post(
            "/conductor/payment-log/cash/record",
            data={"direction": "Not a route direction", "amount_given": "50"},
            follow_redirects=True,
        )
        self.assertIn("No current", response.get_data(as_text=True))
        self.assertEqual(PaymentLog.query.count(), 0)

    @patch("app.conductor.services.initiate_stk_push")
    def test_mpesa_sends_exact_fare_and_stays_pending_until_callback(self, stk_push):
        pending_before_push = []

        def accepted_request(**kwargs):
            pending_before_push.append(PaymentLog.query.one().payment_status)
            self.assertEqual(kwargs["phone_number"], "254712345678")
            self.assertEqual(kwargs["amount"], 50)
            return {
                "CheckoutRequestID": "ws_CO_test",
                "MerchantRequestID": "merchant_test",
            }

        stk_push.side_effect = accepted_request
        response = self.start_mpesa_payment()
        payment = PaymentLog.query.one()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(pending_before_push, ["pending"])
        self.assertEqual(payment.payment_method, "mpesa")
        self.assertEqual(payment.payment_status, "pending")
        self.assertEqual(payment.commuter_phone, "254712345678")
        self.assertEqual(payment.checkout_request_id, "ws_CO_test")
        self.assertEqual(payment.merchant_request_id, "merchant_test")
        self.assertIsNotNone(payment.stk_sent_at)
        self.assertIsNone(payment.paid_at)
        self.assertEqual(AuditLog.query.one().target_id, payment.id)
        stk_push.assert_called_once()

    @patch("app.conductor.services.initiate_stk_push")
    def test_cash_and_mpesa_records_are_distinguishable(self, stk_push):
        self.client.post(
            "/conductor/payment-log/cash/record",
            data={"direction": "Towards CBD", "amount_given": "50"},
        )
        stk_push.return_value = {
            "CheckoutRequestID": "ws_CO_distinct",
            "MerchantRequestID": "merchant_distinct",
        }
        self.start_mpesa_payment()

        payments = PaymentLog.query.order_by(PaymentLog.id).all()
        self.assertEqual(
            [
                (payment.payment_method, payment.payment_status)
                for payment in payments
            ],
            [("cash", "confirmed"), ("mpesa", "pending")],
        )

    @patch("app.conductor.services.initiate_stk_push")
    def test_invalid_phone_and_missing_confirmation_do_not_send_request(self, stk_push):
        self.start_mpesa_payment({"commuter_phone": "not-a-phone"})
        self.assertEqual(PaymentLog.query.count(), 0)

        self.start_mpesa_payment({"commuter_phone": "0712345678", "confirm_payment": ""})
        self.assertEqual(PaymentLog.query.count(), 0)
        stk_push.assert_not_called()

    @patch("app.conductor.services.initiate_stk_push")
    def test_mpesa_rejects_decimal_fare_and_prevents_repeated_request(self, stk_push):
        self.fares[self.current_time_band()].amount = Decimal("50.50")
        db.session.commit()

        self.start_mpesa_payment()
        self.assertEqual(PaymentLog.query.count(), 0)
        stk_push.assert_not_called()

        self.fares[self.current_time_band()].amount = Decimal("50.00")
        db.session.commit()
        stk_push.return_value = {
            "CheckoutRequestID": "ws_CO_repeat",
            "MerchantRequestID": "merchant_repeat",
        }
        self.start_mpesa_payment()
        self.start_mpesa_payment()
        self.assertEqual(PaymentLog.query.count(), 1)
        stk_push.assert_called_once()

    @patch("app.conductor.services.initiate_stk_push")
    def test_mpesa_callback_confirms_matching_successful_payment(self, stk_push):
        stk_push.return_value = {
            "CheckoutRequestID": "ws_CO_success",
            "MerchantRequestID": "merchant_success",
        }
        self.start_mpesa_payment()
        payment = PaymentLog.query.one()

        callback = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": payment.checkout_request_id,
                    "MerchantRequestID": payment.merchant_request_id,
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "MpesaReceiptNumber", "Value": "ABC123"},
                            {"Name": "Amount", "Value": 50},
                            {"Name": "PhoneNumber", "Value": 254712345678},
                        ]
                    },
                }
            }
        }
        response = self.client.post("/payments/mpesa/callback", json=callback)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.payment_status, "confirmed")
        self.assertEqual(payment.transaction_ref, "ABC123")
        self.assertIsNotNone(payment.paid_at)

    @patch("app.conductor.services.initiate_stk_push")
    def test_mpesa_callback_records_failed_payment(self, stk_push):
        stk_push.return_value = {
            "CheckoutRequestID": "ws_CO_failure",
            "MerchantRequestID": "merchant_failure",
        }
        self.start_mpesa_payment()
        payment = PaymentLog.query.one()

        response = self.client.post(
            "/payments/mpesa/callback",
            json={
                "Body": {
                    "stkCallback": {
                        "CheckoutRequestID": payment.checkout_request_id,
                        "MerchantRequestID": payment.merchant_request_id,
                        "ResultCode": 1032,
                        "ResultDesc": "Request cancelled by user.",
                    }
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.payment_status, "failed")
        self.assertIsNone(payment.paid_at)

    def test_conductor_cannot_record_payment_for_another_allocation(self):
        other_conductor, _ = self.create_employee(
            self.conductor_role,
            "other-conductor",
        )
        other_allocation = Allocation(
            conductor_id=other_conductor.id,
            driver_id=self.driver.id,
            vehicle_id=self.vehicle.id,
            route_id=self.route.id,
            status="active",
        )
        db.session.add(other_allocation)
        db.session.commit()

        from app.conductor.services import record_cash_payment

        payment, error = record_cash_payment(
            employee_id=self.conductor.id,
            allocation_id=other_allocation.id,
            direction="Towards CBD",
            amount_given="50",
        )

        self.assertIsNone(payment)
        self.assertIn("allocation", error)
        self.assertEqual(PaymentLog.query.count(), 0)

    def test_phone_normalization_matches_daraja_format(self):
        self.assertEqual(
            normalize_phone_number("0712345678"),
            "254712345678",
        )


if __name__ == "__main__":
    unittest.main()

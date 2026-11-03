import unittest
from datetime import date
from decimal import Decimal

from flask import Flask

from app.admin import admin_bp
from app.admin import routes as admin_routes
from app.admin.services import get_all_roles, get_all_users
from app.auth.routes import load_user
from app.extensions import db, login_manager
from app.models import (
    Allocation,
    AuditLog,
    Claim,
    Compensation,
    Department,
    Employee,
    Fare,
    PaymentLog,
    PayrollDeduction,
    Role,
    RoleHistory,
    Route,
    User,
    Vehicle,
)
from app.finance.services import (
    approve_claim,
    create_budget_allocation,
    create_payroll,
    get_collections_report,
    issue_payroll,
)
from app.fleet.services import (
    change_vehicle_status,
    create_accident,
    create_allocation,
    create_maintenance_record,
    create_vehicle,
    create_vehicle_document,
    end_allocation,
)
from app.hr.services import (
    change_employee_role,
    change_employee_status,
    create_complaint,
    create_employee,
    resolve_complaint,
)
from app.operations.services import create_fare, update_fare


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECRET_KEY="test-secret",
            TESTING=True,
        )
        db.init_app(cls.app)
        login_manager.user_loader(load_user)
        login_manager.init_app(cls.app)
        cls.app.register_blueprint(admin_bp)

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.drop_all()
        db.create_all()

        self.operations = Department(name="Operations")
        self.finance = Department(name="Finance")
        db.session.add_all([self.operations, self.finance])
        db.session.flush()

        self.driver_role = Role(
            name="Driver",
            department_id=self.operations.id,
        )
        self.conductor_role = Role(
            name="Conductor",
            department_id=self.operations.id,
        )
        self.hr_role = Role(
            name="HR Manager",
            department_id=self.operations.id,
        )
        self.inspector_role = Role(
            name="Inspector",
            department_id=self.operations.id,
        )
        self.admin_role = Role(
            name="System Administrator",
            department_id=self.operations.id,
        )
        self.accountant_role = Role(
            name="Accountant",
            department_id=self.finance.id,
        )
        db.session.add_all(
            [
                self.driver_role,
                self.conductor_role,
                self.hr_role,
                self.inspector_role,
                self.admin_role,
                self.accountant_role,
            ]
        )
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def make_employee(self, role, national_id, username):
        return create_employee(
            department_id=role.department_id,
            role_id=role.id,
            national_id=national_id,
            first_name="Test",
            last_name=username.title(),
            username=username,
            password="test-password",
        )

    def make_route(self):
        route = Route(
            name="Town route",
            start_point="Town",
            destination="CBD",
            status="active",
        )
        db.session.add(route)
        db.session.commit()
        return route

    def make_admin_user(self, username="admin-user"):
        employee = self.make_employee(
            self.admin_role,
            f"NID-{username}",
            username,
        )
        return User.query.filter_by(employee_id=employee.id).one()

    def login_as(self, user):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def test_admin_retrieves_all_user_accounts(self):
        admin_user = self.make_admin_user()
        employee = self.make_employee(
            self.driver_role,
            "NID-ADMIN-LIST-DRIVER",
            "listed-driver",
        )
        expected_user = User.query.filter_by(employee_id=employee.id).one()

        self.assertEqual(
            get_all_users(),
            [admin_user, expected_user],
        )

    def test_admin_retrieves_all_system_roles(self):
        self.assertEqual(
            [role.name for role in get_all_roles()],
            [
                "Accountant",
                "Conductor",
                "Driver",
                "HR Manager",
                "Inspector",
                "System Administrator",
            ],
        )

    def test_admin_activates_inactive_account_and_records_audit(self):
        admin_user = self.make_admin_user()
        employee = self.make_employee(
            self.driver_role,
            "NID-ADMIN-ACTIVATE",
            "inactive-driver",
        )
        target = User.query.filter_by(employee_id=employee.id).one()
        target.account_status = "inactive"
        db.session.commit()
        self.login_as(admin_user)

        response = self.client.post(
            f"/admin/users/{target.id}/status",
            data={"status": "active"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(target.account_status, "active")
        audit_entry = AuditLog.query.one()
        self.assertEqual(audit_entry.user_id, admin_user.id)
        self.assertEqual(audit_entry.action, "User account status changed")
        self.assertEqual(audit_entry.target_table, "users")
        self.assertEqual(audit_entry.target_id, target.id)
        self.assertEqual(audit_entry.old_value, "inactive")
        self.assertEqual(audit_entry.new_value, "active")

    def test_admin_deactivates_active_account_and_records_audit(self):
        admin_user = self.make_admin_user()
        employee = self.make_employee(
            self.driver_role,
            "NID-ADMIN-DEACTIVATE",
            "active-driver",
        )
        target = User.query.filter_by(employee_id=employee.id).one()
        self.login_as(admin_user)

        response = self.client.post(
            f"/admin/users/{target.id}/status",
            data={"status": "inactive"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(target.account_status, "inactive")
        audit_entry = AuditLog.query.one()
        self.assertEqual(audit_entry.user_id, admin_user.id)
        self.assertEqual(audit_entry.target_id, target.id)
        self.assertEqual(audit_entry.old_value, "active")
        self.assertEqual(audit_entry.new_value, "inactive")

    def test_admin_rejects_invalid_account_status_without_audit(self):
        admin_user = self.make_admin_user()
        employee = self.make_employee(
            self.driver_role,
            "NID-ADMIN-INVALID-STATUS",
            "status-driver",
        )
        target = User.query.filter_by(employee_id=employee.id).one()
        self.login_as(admin_user)

        response = self.client.post(
            f"/admin/users/{target.id}/status",
            data={"status": "suspended"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(target.account_status, "active")
        self.assertEqual(AuditLog.query.count(), 0)

    def test_admin_handles_nonexistent_user_without_audit(self):
        admin_user = self.make_admin_user()
        self.login_as(admin_user)

        response = self.client.post(
            "/admin/users/9999/status",
            data={"status": "inactive"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditLog.query.count(), 0)

    def test_admin_cannot_deactivate_own_account(self):
        admin_user = self.make_admin_user()
        self.login_as(admin_user)

        response = self.client.post(
            f"/admin/users/{admin_user.id}/status",
            data={"status": "inactive"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(admin_user.account_status, "active")
        self.assertEqual(AuditLog.query.count(), 0)

    def test_non_admin_receives_forbidden_on_admin_routes(self):
        employee = self.make_employee(
            self.hr_role,
            "NID-ADMIN-FORBIDDEN",
            "non-admin-user",
        )
        non_admin = User.query.filter_by(employee_id=employee.id).one()
        self.login_as(non_admin)

        for path in ("/admin/users", "/admin/roles", "/admin/audit-log"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/admin/users/1/status",
            data={"status": "inactive"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AuditLog.query.count(), 0)

    def test_hr_employee_status_and_role_history(self):
        employee = self.make_employee(
            self.driver_role,
            "NID-DRIVER",
            "driver-user",
        )
        user = User.query.filter_by(employee_id=employee.id).one()
        self.assertTrue(user.check_password("test-password"))

        self.assertEqual(
            change_employee_status(employee, "fired"),
            "active",
        )
        self.assertEqual(employee.status, "fired")
        self.assertEqual(user.account_status, "inactive")

        change_employee_status(employee, "active")
        self.assertEqual(user.account_status, "active")

        old_role_id, new_role = change_employee_role(
            employee,
            self.accountant_role.id,
            changed_by=employee.id,
        )
        self.assertEqual(old_role_id, self.driver_role.id)
        self.assertEqual(employee.department_id, self.finance.id)
        self.assertEqual(employee.role_id, self.accountant_role.id)
        history = RoleHistory.query.filter_by(
            employee_id=employee.id
        ).one()
        self.assertEqual(history.role_id, self.driver_role.id)
        self.assertEqual(history.department_id, self.operations.id)

        with self.assertRaisesRegex(ValueError, "already has this role"):
            change_employee_role(
                employee,
                new_role.id,
                changed_by=employee.id,
            )

    def test_hr_employee_rejects_role_from_another_department(self):
        with self.assertRaisesRegex(ValueError, "does not belong"):
            create_employee(
                department_id=self.operations.id,
                role_id=self.accountant_role.id,
                national_id="NID-WRONG-ROLE",
                first_name="Wrong",
                last_name="Role",
                username="wrong-role-user",
                password="test-password",
            )
        self.assertEqual(Employee.query.count(), 0)

    def test_hr_complaint_create_and_resolve(self):
        employee = self.make_employee(
            self.hr_role,
            "NID-HR",
            "hr-user",
        )
        complaint = create_complaint(
            "internal",
            "A test complaint",
            filed_by_employee_id=employee.id,
        )
        resolve_complaint(
            complaint,
            "resolved",
            "Reviewed and addressed",
            employee.id,
        )
        self.assertEqual(complaint.status, "resolved")
        self.assertEqual(complaint.resolved_by, employee.id)
        self.assertIsNotNone(complaint.resolved_at)

    def test_fleet_vehicle_document_maintenance_and_status(self):
        employee = self.make_employee(
            self.hr_role,
            "NID-FLEET",
            "fleet-user",
        )
        vehicle = create_vehicle(
            "KAA-001A",
            make="Test make",
            year=2025,
            vehicle_type="Matatu",
            ownership="owned",
        )
        document = create_vehicle_document(
            vehicle.id,
            "insurance",
            document_number="POLICY-1",
            expiry_date=date(2027, 1, 1),
        )
        maintenance = create_maintenance_record(
            vehicle.id,
            employee.id,
            "Routine service",
            Decimal("250.00"),
        )

        self.assertEqual(change_vehicle_status(vehicle, "under_maintenance"), "active")
        self.assertEqual(vehicle.status, "under_maintenance")
        self.assertEqual(document.vehicle_id, vehicle.id)
        self.assertEqual(maintenance.vehicle_id, vehicle.id)

        with self.assertRaisesRegex(ValueError, "Invalid vehicle status"):
            change_vehicle_status(vehicle, "unknown")

    def test_fleet_allocation_requires_active_driver_and_prevents_conflicts(self):
        driver = self.make_employee(
            self.driver_role,
            "NID-DRIVER-2",
            "driver-two",
        )
        conductor = self.make_employee(
            self.conductor_role,
            "NID-COND-2",
            "conductor-two",
        )
        supervisor = self.make_employee(
            self.hr_role,
            "NID-SUPERVISOR",
            "supervisor",
        )
        vehicle = create_vehicle("KAA-002A")
        route = self.make_route()

        allocation = create_allocation(
            driver.id,
            conductor.id,
            vehicle.id,
            route.id,
            supervisor.id,
        )
        with self.assertRaisesRegex(ValueError, "driver already has"):
            create_allocation(
                driver.id,
                conductor.id,
                vehicle.id,
                route.id,
                supervisor.id,
            )

        end_allocation(allocation)
        self.assertEqual(allocation.status, "ended")
        self.assertIsNotNone(allocation.ended_at)

        with self.assertRaisesRegex(ValueError, "already ended"):
            end_allocation(allocation)

    def test_fleet_allocation_rejects_inactive_employees(self):
        driver = self.make_employee(
            self.driver_role,
            "NID-DRIVER-3",
            "driver-three",
        )
        conductor = self.make_employee(
            self.conductor_role,
            "NID-COND-3",
            "conductor-three",
        )
        supervisor = self.make_employee(
            self.hr_role,
            "NID-SUPERVISOR-2",
            "supervisor-two",
        )
        driver.status = "fired"
        vehicle = create_vehicle("KAA-003A")
        route = self.make_route()
        db.session.commit()

        with self.assertRaisesRegex(ValueError, "driver is not active"):
            create_allocation(
                driver.id,
                conductor.id,
                vehicle.id,
                route.id,
                supervisor.id,
            )

    def test_fleet_accident_creation(self):
        driver = self.make_employee(
            self.driver_role,
            "NID-DRIVER-4",
            "driver-four",
        )
        inspector = self.make_employee(
            self.inspector_role,
            "NID-INSPECTOR",
            "inspector",
        )
        vehicle = create_vehicle("KAA-004A")
        accident = create_accident(
            vehicle.id,
            driver.id,
            inspector.id,
            "Reported test incident",
        )
        self.assertEqual(accident.vehicle_id, vehicle.id)
        self.assertEqual(accident.driver_id, driver.id)
        self.assertEqual(accident.reported_by, inspector.id)

    def test_finance_payroll_calculation_and_issue(self):
        employee = self.make_employee(
            self.hr_role,
            "NID-PAYROLL",
            "payroll-employee",
        )
        payroll = create_payroll(
            employee.id,
            "2026-10",
            "1000.00",
            "150.00",
            ["loan", "sacco"],
            ["100.00", "50.00"],
            employee.id,
        )
        self.assertEqual(payroll.net_pay, Decimal("1000.00"))
        self.assertEqual(
            PayrollDeduction.query.filter_by(payroll_id=payroll.id).count(),
            2,
        )
        issue_payroll(payroll)
        self.assertEqual(payroll.status, "issued")

        with self.assertRaisesRegex(ValueError, "Only draft payrolls"):
            issue_payroll(payroll)

    def test_finance_payroll_rejects_duplicate_and_excess_deductions(self):
        employee = self.make_employee(
            self.hr_role,
            "NID-PAYROLL-2",
            "payroll-employee-two",
        )
        create_payroll(
            employee.id,
            "2026-10",
            "1000.00",
            "0",
            [],
            [],
            employee.id,
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            create_payroll(
                employee.id,
                "2026-10",
                "1000.00",
                "0",
                [],
                [],
                employee.id,
            )

        with self.assertRaisesRegex(ValueError, "cannot exceed gross pay"):
            create_payroll(
                employee.id,
                "2026-11",
                "100.00",
                "0",
                ["loan"],
                ["101.00"],
                employee.id,
            )

    def test_finance_approving_accident_claim_creates_compensation(self):
        reviewer = self.make_employee(
            self.hr_role,
            "NID-REVIEWER",
            "reviewer",
        )
        claim = Claim(
            department="Fleet",
            category="accident",
            description="Accident claim",
            amount_requested=Decimal("300.00"),
            status="pending",
        )
        db.session.add(claim)
        db.session.commit()

        approve_claim(claim, reviewer.id, "250.00")
        self.assertEqual(claim.status, "approved")
        self.assertEqual(claim.reviewed_by, reviewer.id)
        compensation = Compensation.query.filter_by(
            claim_id=claim.id
        ).one()
        self.assertEqual(compensation.amount, Decimal("250.00"))

        with self.assertRaisesRegex(ValueError, "Only pending claims"):
            approve_claim(claim, reviewer.id)

    def test_finance_budget_validation_and_collections_report(self):
        employee = self.make_employee(
            self.hr_role,
            "NID-BUDGET",
            "budget-employee",
        )
        allocation = create_budget_allocation(
            self.finance.id,
            "5000.00",
            "2026-10",
            employee.id,
        )
        self.assertEqual(allocation.period, "2026-10")

        with self.assertRaisesRegex(ValueError, "YYYY-MM format"):
            create_budget_allocation(
                self.finance.id,
                "5000.00",
                "October 2026",
                employee.id,
            )

        conductor = self.make_employee(
            self.conductor_role,
            "NID-COLLECTOR",
            "collection-conductor",
        )
        vehicle = create_vehicle("KAA-005A")
        route = self.make_route()
        trip_allocation = Allocation(
            driver_id=employee.id,
            conductor_id=conductor.id,
            vehicle_id=vehicle.id,
            route_id=route.id,
            status="active",
        )
        db.session.add(trip_allocation)
        db.session.flush()
        db.session.add(
            PaymentLog(
                conductor_id=conductor.id,
                allocation_id=trip_allocation.id,
                route_id=route.id,
                vehicle_id=vehicle.id,
                direction="Towards CBD",
                time_band="peak",
                fare_amount=Decimal("50.00"),
                amount_given=Decimal("60.00"),
                change_given=Decimal("10.00"),
                commuter_phone="0712345678",
                payment_method="mpesa",
                payment_status="pending",
            )
        )
        db.session.add_all(
            [
                PaymentLog(
                    conductor_id=conductor.id,
                    allocation_id=trip_allocation.id,
                    route_id=route.id,
                    vehicle_id=vehicle.id,
                    direction="Towards CBD",
                    time_band="peak",
                    fare_amount=Decimal("30.00"),
                    payment_method="mpesa",
                    payment_status="failed",
                ),
                PaymentLog(
                    conductor_id=conductor.id,
                    allocation_id=trip_allocation.id,
                    route_id=route.id,
                    vehicle_id=vehicle.id,
                    direction="Towards CBD",
                    time_band="peak",
                    fare_amount=Decimal("40.00"),
                    amount_given=Decimal("50.00"),
                    change_given=Decimal("10.00"),
                    payment_method="cash",
                    payment_status="confirmed",
                ),
                PaymentLog(
                    conductor_id=conductor.id,
                    allocation_id=trip_allocation.id,
                    route_id=route.id,
                    vehicle_id=vehicle.id,
                    direction="Towards CBD",
                    time_band="peak",
                    fare_amount=Decimal("20.00"),
                    payment_method="mpesa",
                    payment_status="confirmed",
                ),
            ]
        )
        db.session.commit()

        report = get_collections_report()
        self.assertEqual(report["total_records"], 4)
        self.assertEqual(report["total_fares"], Decimal("60.00"))
        self.assertEqual(report["total_amount_given"], Decimal("50.00"))
        self.assertEqual(report["total_change_given"], Decimal("10.00"))
        self.assertEqual(
            report["status_totals"],
            {"confirmed": 2, "failed": 1, "pending": 1},
        )

    def test_fare_update_preserves_history(self):
        route = self.make_route()
        old_fare = create_fare(
            route.id,
            "Towards CBD",
            "off_peak",
            Decimal("50.00"),
            date(2026, 1, 1),
        )
        new_fare = update_fare(
            old_fare.id,
            Decimal("60.00"),
            date(2026, 2, 1),
        )
        self.assertEqual(old_fare.effective_until, date(2026, 1, 31))
        self.assertEqual(new_fare.effective_from, date(2026, 2, 1))
        self.assertIsNone(new_fare.effective_until)

        with self.assertRaisesRegex(ValueError, "Historical fares"):
            update_fare(
                old_fare.id,
                Decimal("70.00"),
                date(2026, 3, 1),
            )


if __name__ == "__main__":
    unittest.main()

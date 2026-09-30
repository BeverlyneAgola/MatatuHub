from datetime import datetime

from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id"),
        nullable=False
    )

    department = db.relationship("Department")


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)

    staff_id = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    national_id = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    first_name = db.Column(
        db.String(50),
        nullable=False
    )

    last_name = db.Column(
        db.String(50),
        nullable=False
    )

    dob = db.Column(db.Date)

    gender = db.Column(db.String(10))

    phone = db.Column(db.String(20))

    email = db.Column(db.String(100))

    kra_pin = db.Column(db.String(20))

    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id"),
        nullable=False
    )

    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="active"
    )  # active / fired

    driver_license_no = db.Column(
        db.String(30),
        nullable=True
    )  # only used if role = Driver

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    department = db.relationship("Department")

    role = db.relationship("Role")


class RoleHistory(db.Model):
    __tablename__ = "role_history"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=False
    )

    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id"),
        nullable=False
    )

    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id"),
        nullable=False
    )

    changed_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    changed_by = db.Column(
        db.Integer,
        db.ForeignKey("employees.id")
    )

    department = db.relationship("Department")

    role = db.relationship("Role")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        unique=True,
        nullable=False
    )

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    account_status = db.Column(
        db.String(20),
        default="active"
    )  # active / inactive

    last_login = db.Column(db.DateTime)

    employee = db.relationship("Employee")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )

    @property
    def is_active(self):
        return self.account_status == "active"


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    category = db.Column(db.String(20))
    # internal / external

    description = db.Column(
        db.Text,
        nullable=False
    )

    filed_by_phone = db.Column(
        db.String(20)
    )

    filed_by_employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=True
    )

    status = db.Column(
        db.String(20),
        default="unresolved"
    )
    # resolved / unresolved

    action_taken = db.Column(db.Text)

    resolved_by = db.Column(
        db.Integer,
        db.ForeignKey("employees.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    resolved_at = db.Column(
        db.DateTime,
        nullable=True
    )


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    action = db.Column(
        db.String(255),
        nullable=False
    )

    target_table = db.Column(
        db.String(50)
    )

    target_id = db.Column(
        db.Integer
    )

    old_value = db.Column(
        db.String(255)
    )

    new_value = db.Column(
        db.String(255)
    )

    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
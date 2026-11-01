
from datetime import date, datetime

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Accident,
    Allocation,
    Employee,
    MaintenanceRecord,
    Route,
    Vehicle,
    VehicleDocument,
)


VEHICLE_STATUSES = {
    "active",
    "under_maintenance",
    "out_of_service",
    "retired",
}


def fetch_vehicles():
    return Vehicle.query.order_by(Vehicle.reg_no).all()


def list_vehicles():
    return fetch_vehicles()


def get_vehicle(vehicle_id):
    return db.session.get(Vehicle, vehicle_id)


def get_vehicle_profile(vehicle_id):
    return {
        "documents": list_vehicle_documents(vehicle_id),
        "maintenance_records": list_maintenance_records(vehicle_id),
        "allocations": (
            Allocation.query
            .filter_by(vehicle_id=vehicle_id)
            .order_by(Allocation.started_at.desc())
            .all()
        ),
        "accidents": (
            Accident.query
            .filter_by(vehicle_id=vehicle_id)
            .order_by(Accident.date.desc())
            .all()
        ),
    }


def create_vehicle(
    reg_no,
    make=None,
    year=None,
    vehicle_type=None,
    ownership=None,
):
    reg_no = (reg_no or "").strip().upper()

    if not reg_no:
        raise ValueError("Vehicle registration number is required.")

    if Vehicle.query.filter_by(reg_no=reg_no).first():
        raise ValueError(
            "A vehicle with this registration number already exists."
        )

    if year is not None and not 1900 <= year <= 2100:
        raise ValueError("Enter a valid vehicle manufacture year.")

    vehicle = Vehicle(
        reg_no=reg_no,
        make=make,
        year=year,
        type=vehicle_type,
        ownership=ownership,
        status="active",
    )

    db.session.add(vehicle)
    db.session.commit()

    return vehicle


def update_vehicle_status(vehicle, new_status):
    if new_status not in VEHICLE_STATUSES:
        raise ValueError("Invalid vehicle status.")

    if vehicle.status == new_status:
        raise ValueError("The vehicle already has this status.")

    active_allocation = Allocation.query.filter_by(
        vehicle_id=vehicle.id,
        status="active",
    ).first()

    if active_allocation and new_status != "active":
        raise ValueError(
            "End the vehicle's active allocation before changing its status."
        )

    old_status = vehicle.status
    vehicle.status = new_status
    db.session.commit()

    return old_status


def change_vehicle_status(vehicle, new_status):
    return update_vehicle_status(vehicle, new_status)


def list_vehicle_documents(vehicle_id):
    return (
        VehicleDocument.query
        .filter_by(vehicle_id=vehicle_id)
        .order_by(VehicleDocument.expiry_date)
        .all()
    )


def create_vehicle_document(
    vehicle_id,
    doc_type,
    document_number=None,
    issue_date=None,
    expiry_date=None,
):
    if not doc_type or not doc_type.strip():
        raise ValueError("Document type is required.")

    if issue_date and expiry_date and expiry_date < issue_date:
        raise ValueError(
            "The expiry date cannot be earlier than the issue date."
        )

    document = VehicleDocument(
        vehicle_id=vehicle_id,
        doc_type=doc_type.strip(),
        document_number=document_number,
        issue_date=issue_date,
        expiry_date=expiry_date,
    )

    db.session.add(document)
    db.session.commit()

    return document


def list_maintenance_records(vehicle_id):
    return (
        MaintenanceRecord.query
        .filter_by(vehicle_id=vehicle_id)
        .order_by(MaintenanceRecord.date.desc())
        .all()
    )


def create_maintenance_record(
    vehicle_id,
    created_by,
    description,
    cost=None,
    record_date=None,
):
    if not description or not description.strip():
        raise ValueError("Maintenance description is required.")

    if cost is not None and cost < 0:
        raise ValueError("Maintenance cost cannot be negative.")

    maintenance = MaintenanceRecord(
        vehicle_id=vehicle_id,
        created_by=created_by,
        description=description.strip(),
        cost=cost,
        date=record_date or date.today(),
    )

    db.session.add(maintenance)
    db.session.commit()

    return maintenance


def get_allocation_form_data():
    active_employees = (
        Employee.query
        .join(Employee.role)
        .filter(Employee.status == "active")
        .all()
    )

    active_allocations = Allocation.query.filter_by(
        status="active"
    ).all()

    allocated_driver_ids = {
        allocation.driver_id for allocation in active_allocations
    }

    allocated_conductor_ids = {
        allocation.conductor_id for allocation in active_allocations
    }

    allocated_vehicle_ids = {
        allocation.vehicle_id for allocation in active_allocations
    }

    return {
        "drivers": [
            employee
            for employee in active_employees
            if employee.role
            and employee.role.name == "Driver"
            and employee.id not in allocated_driver_ids
        ],
        "conductors": [
            employee
            for employee in active_employees
            if employee.role
            and employee.role.name == "Conductor"
            and employee.id not in allocated_conductor_ids
        ],
        "vehicles": (
            Vehicle.query
            .filter_by(status="active")
            .order_by(Vehicle.reg_no)
            .all()
        ),
        "routes": Route.query.order_by(Route.name).all(),
    }


def create_allocation(
    driver_id,
    conductor_id,
    vehicle_id,
    route_id,
    created_by,
):
    driver = db.session.get(Employee, driver_id)
    conductor = db.session.get(Employee, conductor_id)
    vehicle = db.session.get(Vehicle, vehicle_id)
    route = db.session.get(Route, route_id)

    if any(
        item is None
        for item in (driver, conductor, vehicle, route)
    ):
        raise ValueError(
            "The selected driver, conductor, vehicle or route does not exist."
        )

    if not driver.role or driver.role.name != "Driver":
        raise ValueError("The selected employee is not a Driver.")

    if not conductor.role or conductor.role.name != "Conductor":
        raise ValueError("The selected employee is not a Conductor.")

    if driver.status != "active":
        raise ValueError("The selected driver is not active.")

    if conductor.status != "active":
        raise ValueError("The selected conductor is not active.")

    if vehicle.status != "active":
        raise ValueError(
            "Only active vehicles can be allocated."
        )

    conflict = Allocation.query.filter(
        Allocation.status == "active",
        or_(
            Allocation.driver_id == driver.id,
            Allocation.conductor_id == conductor.id,
            Allocation.vehicle_id == vehicle.id,
        ),
    ).first()

    if conflict:
        if conflict.driver_id == driver.id:
            raise ValueError(
                "This driver already has an active allocation. "
                "End it before creating another."
            )

        if conflict.conductor_id == conductor.id:
            raise ValueError(
                "This conductor already has an active allocation. "
                "End it before creating another."
            )

        raise ValueError(
            "This vehicle already has an active allocation. "
            "End it before creating another."
        )

    allocation = Allocation(
        driver_id=driver.id,
        conductor_id=conductor.id,
        vehicle_id=vehicle.id,
        route_id=route.id,
        status="active",
        created_by=created_by,
    )

    db.session.add(allocation)
    db.session.commit()

    return allocation


def get_allocation(allocation_id):
    return db.session.get(Allocation, allocation_id)


def close_allocation(allocation):
    if allocation.status != "active":
        raise ValueError("This allocation has already ended.")

    allocation.status = "ended"
    allocation.ended_at = datetime.utcnow()

    db.session.commit()


def end_allocation(allocation):
    close_allocation(allocation)


def get_accident_form_data():
    active_employees = (
        Employee.query
        .join(Employee.role)
        .filter(Employee.status == "active")
        .all()
    )

    return {
        "vehicles": (
            Vehicle.query
            .order_by(Vehicle.reg_no)
            .all()
        ),
        "drivers": [
            employee
            for employee in active_employees
            if employee.role and employee.role.name == "Driver"
        ],
    }


def create_accident(
    vehicle_id,
    driver_id,
    reported_by,
    description,
    accident_date=None,
):
    vehicle = db.session.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise ValueError("Select a valid vehicle.")

    if driver_id is not None:
        driver = db.session.get(Employee, driver_id)

        if driver is None or not driver.role or driver.role.name != "Driver":
            raise ValueError("Select a valid driver or leave it blank.")

    if not description or not description.strip():
        raise ValueError("An accident description is required.")

    accident = Accident(
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        reported_by=reported_by,
        description=description.strip(),
        date=accident_date or datetime.utcnow(),
    )

    db.session.add(accident)
    db.session.commit()

    return accident


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


def list_vehicles():
    return Vehicle.query.order_by(Vehicle.id).all()


def get_vehicle(vehicle_id):
    return db.session.get(Vehicle, vehicle_id)


def get_vehicle_profile(vehicle_id):
    return {
        "documents": (
            VehicleDocument.query
            .filter_by(vehicle_id=vehicle_id)
            .order_by(VehicleDocument.expiry_date)
            .all()
        ),
        "maintenance_records": (
            MaintenanceRecord.query
            .filter_by(vehicle_id=vehicle_id)
            .order_by(MaintenanceRecord.date.desc())
            .all()
        ),
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


def create_vehicle(reg_no, make=None, year=None, vehicle_type=None, ownership=None):
    if Vehicle.query.filter_by(reg_no=reg_no).first():
        raise ValueError(
            "A vehicle with this registration number already exists."
        )
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


def change_vehicle_status(vehicle, new_status):
    if new_status not in VEHICLE_STATUSES:
        raise ValueError("Invalid vehicle status.")
    old_status = vehicle.status
    vehicle.status = new_status
    db.session.commit()
    return old_status


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
    document = VehicleDocument(
        vehicle_id=vehicle_id,
        doc_type=doc_type,
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
    maintenance = MaintenanceRecord(
        vehicle_id=vehicle_id,
        created_by=created_by,
        description=description,
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
    return {
        "drivers": [
            employee for employee in active_employees
            if employee.role.name == "Driver"
        ],
        "conductors": [
            employee for employee in active_employees
            if employee.role.name == "Conductor"
        ],
        "vehicles": (
            Vehicle.query
            .filter(Vehicle.status != "retired")
            .order_by(Vehicle.reg_no)
            .all()
        ),
        "routes": Route.query.order_by(Route.name).all(),
    }


def create_allocation(driver_id, conductor_id, vehicle_id, route_id, created_by):
    driver = db.session.get(Employee, driver_id)
    conductor = db.session.get(Employee, conductor_id)
    vehicle = db.session.get(Vehicle, vehicle_id)
    route = db.session.get(Route, route_id)
    if any(item is None for item in (driver, conductor, vehicle, route)):
        raise ValueError("The selected driver, conductor, vehicle or route does not exist.")
    if driver.role.name != "Driver":
        raise ValueError("The selected employee is not a Driver.")
    if conductor.role.name != "Conductor":
        raise ValueError("The selected employee is not a Conductor.")
    if driver.status != "active":
        raise ValueError("The selected driver is not active.")
    if conductor.status != "active":
        raise ValueError("The selected conductor is not active.")

    conflict = Allocation.query.filter(
        Allocation.status == "active",
        or_(
            Allocation.driver_id == driver.id,
            Allocation.vehicle_id == vehicle.id,
        ),
    ).first()
    if conflict:
        if conflict.driver_id == driver.id:
            raise ValueError(
                "This driver already has an active allocation. "
                "End it first before creating a new one."
            )
        raise ValueError(
            "This vehicle already has an active allocation. "
            "End it first before creating a new one."
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


def end_allocation(allocation):
    if allocation.status != "active":
        raise ValueError("This allocation has already ended.")
    allocation.status = "ended"
    allocation.ended_at = datetime.utcnow()
    db.session.commit()


def get_accident_form_data():
    active_employees = Employee.query.filter_by(status="active").all()
    return {
        "vehicles": Vehicle.query.order_by(Vehicle.reg_no).all(),
        "drivers": [
            employee for employee in active_employees
            if employee.role.name == "Driver"
        ],
    }


def create_accident(
    vehicle_id,
    driver_id,
    reported_by,
    description,
    accident_date=None,
):
    accident = Accident(
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        reported_by=reported_by,
        description=description,
        date=accident_date or datetime.utcnow(),
    )
    db.session.add(accident)
    db.session.commit()
    return accident

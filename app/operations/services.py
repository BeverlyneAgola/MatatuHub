from datetime import date, timedelta

from app.extensions import db
from app.models import Fare, Route


def list_routes():
    return Route.query.order_by(Route.name.asc()).all()


def create_route(name, start_point, destination):
    route = Route(
        name=name,
        start_point=start_point,
        destination=destination,
        status="active",
    )
    db.session.add(route)
    db.session.commit()
    return route


def get_route(route_id):
    return db.session.get(Route, route_id)


def get_fare(fare_id):
    return db.session.get(Fare, fare_id)


def list_route_fares(route_id):
    return (
        Fare.query
        .filter_by(route_id=route_id)
        .order_by(
            Fare.direction.asc(),
            Fare.time_band.asc(),
            Fare.effective_from.desc()
        )
        .all()
    )


def get_current_fare(
    route_id,
    direction,
    time_band,
    on_date=None
):
    """
    Return the fare effective on a specific date
    for a route, direction and time band.
    """

    if on_date is None:
        on_date = date.today()

    return (
        Fare.query
        .filter(
            Fare.route_id == route_id,
            Fare.direction == direction,
            Fare.time_band == time_band,
            Fare.effective_from <= on_date,
            (
                (Fare.effective_until.is_(None))
                |
                (Fare.effective_until >= on_date)
            )
        )
        .order_by(
            Fare.effective_from.desc()
        )
        .first()
    )


def create_fare(
    route_id,
    direction,
    time_band,
    amount,
    effective_from
):
    """
    Create a new fare while preserving fare history.

    The new fare must not overlap an existing fare period.
    If it replaces the current fare, the current fare is
    closed one day before the new fare begins.
    """

    existing_fares = (
        Fare.query
        .filter_by(
            route_id=route_id,
            direction=direction,
            time_band=time_band
        )
        .order_by(
            Fare.effective_from.asc()
        )
        .all()
    )

    for fare in existing_fares:

        fare_end = fare.effective_until

        if (
            effective_from >= fare.effective_from
            and (
                fare_end is None
                or effective_from <= fare_end
            )
        ):
            if effective_from == fare.effective_from:
                raise ValueError(
                    "A fare already exists with this effective date."
                )

            if fare_end is None:
                fare.effective_until = (
                    effective_from - timedelta(days=1)
                )

            else:
                raise ValueError(
                    "The new fare date overlaps an existing "
                    "fare history."
                )

    future_fares = [
        fare
        for fare in existing_fares
        if fare.effective_from > effective_from
    ]

    if future_fares:
        next_fare = future_fares[0]

        raise ValueError(
            "The new fare cannot be dated before a future "
            "fare that already exists."
        )

    fare = Fare(
        route_id=route_id,
        direction=direction,
        time_band=time_band,
        amount=amount,
        effective_from=effective_from,
        effective_until=None
    )

    db.session.add(fare)
    db.session.commit()

    return fare


def update_fare(
    fare_id,
    amount,
    effective_from
):
    """
    Update a current fare by creating a new fare record.

    The original fare remains in the database as historical
    information.
    """

    old_fare = db.session.get(
        Fare,
        fare_id
    )

    if not old_fare:
        raise ValueError("Fare not found.")

    if old_fare.effective_until is not None:
        raise ValueError(
            "Historical fares cannot be updated."
        )

    if effective_from <= old_fare.effective_from:
        raise ValueError(
            "The new fare's effective date must be after "
            "the current fare's effective date."
        )

    old_fare.effective_until = (
        effective_from - timedelta(days=1)
    )

    new_fare = Fare(
        route_id=old_fare.route_id,
        direction=old_fare.direction,
        time_band=old_fare.time_band,
        amount=amount,
        effective_from=effective_from,
        effective_until=None
    )

    db.session.add(new_fare)
    db.session.commit()

    return new_fare
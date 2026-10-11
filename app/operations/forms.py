from datetime import date


ALLOWED_TIME_BANDS = {
    "peak",
    "off_peak",
}


def validate_fare_data(
    direction,
    time_band,
    amount,
    effective_from
):
    """
    Validate fare information before it is saved.
    """

    errors = []

    direction = direction.strip()
    time_band = time_band.strip().lower()

    if not direction:
        errors.append("Direction is required.")

    if time_band not in ALLOWED_TIME_BANDS:
        errors.append("Time band must be Peak or Off-Peak.")

    if not amount:
        errors.append("Fare amount is required.")
    else:
        try:
            amount = float(amount)

            if amount <= 0:
                errors.append("Fare amount must be greater than zero.")

        except ValueError:
            errors.append("Fare amount must be a valid number.")

    if not effective_from:
        errors.append("Effective date is required.")
    else:
        try:
            effective_from = date.fromisoformat(effective_from)

        except ValueError:
            errors.append("Effective date must be a valid date.")

    return errors
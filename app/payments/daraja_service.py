
import re
import requests

from requests.auth import HTTPBasicAuth
from flask import current_app


class DarajaError(Exception):
    """Raised when a Daraja API operation fails."""
    pass


def get_daraja_config(key):
    """Retrieve Daraja configuration from Flask config."""

    value = current_app.config.get(key)

    if not value:
        raise DarajaError(
            f"Missing Daraja configuration: {key}"
        )

    return value


def normalize_phone_number(phone_number):
    """
    Convert Kenyan mobile numbers into the
    254XXXXXXXXX format required by Daraja.
    """

    phone = re.sub(r"\D", "", str(phone_number))

    if phone.startswith("0") and len(phone) == 10:
        phone = "254" + phone[1:]

    elif phone.startswith("254") and len(phone) == 12:
        pass

    elif phone.startswith("7") and len(phone) == 9:
        phone = "254" + phone

    elif phone.startswith("1") and len(phone) == 9:
        phone = "254" + phone

    else:
        raise ValueError("Invalid Kenyan phone number.")

    return phone


def get_access_token():
    """Generate a Daraja OAuth access token."""

    consumer_key = get_daraja_config(
        "MPESA_CONSUMER_KEY"
    )

    consumer_secret = get_daraja_config(
        "MPESA_CONSUMER_SECRET"
    )

    oauth_url = get_daraja_config(
        "MPESA_OAUTH_URL"
    )

    try:
        response = requests.get(
            oauth_url,
            auth=HTTPBasicAuth(
                consumer_key,
                consumer_secret
            ),
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        access_token = data.get("access_token")

        if not access_token:
            raise DarajaError(
                "Daraja did not return an access token."
            )

        return access_token

    except requests.RequestException as error:
        current_app.logger.exception(
            "Failed to generate Daraja access token."
        )

        raise DarajaError(
            "Unable to generate Daraja access token."
        ) from error

    except ValueError as error:
        raise DarajaError(
            "Invalid OAuth response from Daraja."
        ) from error


def initiate_stk_push(
    phone_number,
    amount,
    account_reference,
    transaction_description
):
    """
    Initiate an M-Pesa STK Push request.

    Payment confirmation is handled separately
    through the Safaricom callback.
    """

    shortcode = get_daraja_config(
        "MPESA_SHORTCODE"
    )

    password = get_daraja_config(
        "MPESA_PASSWORD"
    )

    timestamp = get_daraja_config(
        "MPESA_TIMESTAMP"
    )

    callback_url = get_daraja_config(
        "MPESA_CALLBACK_URL"
    )

    stk_url = get_daraja_config(
        "MPESA_STK_URL"
    )

    if not timestamp.isdigit() or len(timestamp) != 14:
        raise DarajaError(
            "The configured Daraja timestamp is invalid."
        )

    if not account_reference:
        raise DarajaError(
            "Account reference is required."
        )

    if not transaction_description:
        raise DarajaError(
            "Transaction description is required."
        )

    try:
        phone_number = normalize_phone_number(
            phone_number
        )

    except ValueError as error:
        raise DarajaError(str(error)) from error

    try:
        payment_amount = int(amount)

    except (TypeError, ValueError):
        raise DarajaError(
            "Invalid M-Pesa payment amount."
        )

    if payment_amount <= 0 or payment_amount != amount:
        raise DarajaError(
            "M-Pesa amount must be a positive whole number."
        )

    token = get_access_token()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": payment_amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": str(account_reference),
        "TransactionDesc": str(transaction_description)
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            stk_url,
            json=payload,
            headers=headers,
            timeout=60
        )

        try:
            data = response.json()
        except ValueError:
            data = {}

        if not response.ok:
            error_message = (
                data.get("errorMessage")
                or data.get("ResponseDescription")
                or response.text[:500]
                or "No response details supplied."
            )

            current_app.logger.error(
                "Daraja STK Push HTTP error. "
                "Status: %s. Response: %s",
                response.status_code,
                error_message
            )

            raise DarajaError(
                f"Daraja HTTP {response.status_code}: "
                f"{error_message}"
            )

        if not data:
            raise DarajaError(
                "Invalid response received from Daraja."
            )

        if data.get("ResponseCode") != "0":
            raise DarajaError(
                data.get(
                    "ResponseDescription",
                    "STK Push request was not accepted."
                )
            )

        return data

    except requests.Timeout as error:
        raise DarajaError(
            "Daraja STK Push request timed out."
        ) from error

    except requests.ConnectionError as error:
        raise DarajaError(
            "Could not connect to Safaricom Daraja."
        ) from error

    except requests.RequestException as error:
        current_app.logger.exception(
            "Daraja STK Push request failed."
        )

        raise DarajaError(
            "Unable to complete the Daraja HTTP request."
        ) from error


from flask import Blueprint

management_bp = Blueprint(
    "management",
    __name__,
    url_prefix="/management"
)
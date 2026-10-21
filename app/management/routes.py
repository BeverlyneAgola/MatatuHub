from flask import render_template, request
from flask_login import login_required

from app.management import management_bp
from app.management.services import (
    get_dashboard_statistics,
    get_fleet_overview,
    get_allocation_overview,
    get_routes_overview,
    get_outstanding_issues,
    get_workforce_overview,
)
from app.auth.decorators import role_required


# --------------------------------------------------
# MANAGEMENT DASHBOARD
# --------------------------------------------------

@management_bp.route("/")
@login_required
@role_required("General Manager", "Deputy General Manager")
def dashboard():
    statistics = get_dashboard_statistics()

    return render_template(
        "management/dashboard.html",
        statistics=statistics
    )


# --------------------------------------------------
# FLEET AND ALLOCATIONS
# --------------------------------------------------

@management_bp.route("/fleet-allocations")
@login_required
@role_required("General Manager", "Deputy General Manager")
def fleet_allocations():
    fleet = get_fleet_overview()

    status = request.args.get("status", "all")

    if status not in ("all", "active", "ended"):
        status = "all"

    allocation_status = None if status == "all" else status

    allocations = get_allocation_overview(
        status=allocation_status
    )

    return render_template(
        "management/fleet_allocations.html",
        fleet=fleet,
        allocations=allocations,
        selected_status=status
    )


# --------------------------------------------------
# ROUTES OVERVIEW
# --------------------------------------------------

@management_bp.route("/routes")
@login_required
@role_required("General Manager", "Deputy General Manager")
def routes_overview():
    routes = get_routes_overview()

    return render_template(
        "management/routes_overview.html",
        routes=routes
    )


# --------------------------------------------------
# OUTSTANDING ISSUES
# --------------------------------------------------

@management_bp.route("/outstanding-issues")
@login_required
@role_required("General Manager", "Deputy General Manager")
def outstanding_issues():
    issues = get_outstanding_issues()

    return render_template(
        "management/outstanding_issues.html",
        issues=issues
    )


# --------------------------------------------------
# WORKFORCE OVERVIEW
# --------------------------------------------------

@management_bp.route("/workforce")
@login_required
@role_required("General Manager", "Deputy General Manager")
def workforce_overview():
    workforce = get_workforce_overview()

    return render_template(
        "management/workforce_overview.html",
        workforce=workforce
    )


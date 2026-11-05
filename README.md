# MatatuHub

An operations and business management platform for public transport operators.

MatatuHub brings essential transport-business workflows into a single web application, connecting fleet and route operations with workforce administration, finance, and fare payments. It is designed to help transport operators run their businesses more efficiently and with better visibility.

> Project status: Under active development. Features, setup instructions, and configuration may change.

## Overview

MatatuHub is built for transport operators who need to manage day-to-day business operations in one place. From vehicle records and route planning to payroll, staffing, and digital fare payments, the platform centralizes critical workflows in a single system.

## What MatatuHub supports

- Fleet management — maintain vehicle records, documents, maintenance history, incidents, and assignments.
- Transport operations — manage routes, fares, schedules, and vehicle and crew allocations.
- Driver and conductor operations — support day-to-day field workflows for transport staff.
- Human resources — manage employee records, departments, roles, status changes, and complaints.
- Finance — support payroll, claims, budgets, and collection reporting.
- Fare payments — record payment activity and integrate with Safaricom M-Pesa Daraja workflows.
- Administration and oversight — manage user access and roles, with audit records for selected administrative actions.

## Technology stack

- Backend: Python, Flask
- Database and ORM: SQLAlchemy, Flask-SQLAlchemy
- Migrations: Alembic, Flask-Migrate
- Authentication: Flask-Login
- Forms: Flask-WTF, WTForms
- Templates: Jinja
- Database support:
  - PostgreSQL via `psycopg2-binary`
  - SQLite for local development and tests

## Getting started

### Requirements

- Python 3.10 or later
- pip
- A database supported by SQLAlchemy

### 1. Clone the repository

```bash
git clone https://github.com/BeverlyneAgola/MatatuHub.git
cd MatatuHub
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

On Linux or macOS:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

The application reads configuration from environment variables, and `python-dotenv` loads values from a local `.env` file. Create a `.env` file in the project root:

```dotenv
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///matatuhub.db
```

For PostgreSQL, use a database URL appropriate for your environment, for example:

```dotenv
DATABASE_URL=postgresql://username:password@localhost:5432/matatuhub
```

M-Pesa Daraja settings are read using the following variable names:

```dotenv
KEY=
SECRET=
code=
PASSKEY=
CALLBACK=
PASSWORD=
O_URL=
S_URL=
TIMESTAMP=
```

Set these values only when configuring the Daraja integration. Keep credentials private and do not commit `.env` files or paste secrets into issues or pull requests. The `.env` file is ignored by Git.

### 5. Apply database migrations

```bash
flask --app run.py db upgrade
```

### 6. Start the development server

```bash
python run.py
```

The application will be available at:

```text
http://127.0.0.1:5000
```

`run.py` enables Flask debug mode for local development. Do not use the development server or debug mode in a production deployment.

### 7. Run the app in production

For deployment, use a WSGI server such as Gunicorn:

```bash
gunicorn --bind 0.0.0.0:8000 run:app
```

This loads the Flask app object from `run.py` and starts it for production use.

## Development data

To create the initial departments, roles, and system administrator in a local development database, run:

```bash
python seed.py
```

The script prompts for an administrator password. Use only a database you control; review the seed script before running it, and do not use sample or development credentials in production.

A separate script can create an HR Manager account after the required department and role exist:

```bash
python create_hr_manager.py
```

## Running tests

Run the test suite using Python’s built-in unittest runner:

```bash
python -m unittest discover -s tests
```

## Repository layout

```text
MatatuHub/
├── app/
│   ├── admin/
│   ├── auth/
│   ├── conductor/
│   ├── conductor_operations/
│   ├── driver/
│   ├── driver_operations/
│   ├── finance/
│   ├── fleet/
│   ├── hr/
│   ├── management/
│   ├── models/
│   ├── operations/
│   ├── payments/
│   ├── public/
│   ├── static/
│   └── templates/
├── migrations/
├── tests/
├── create_hr_manager.py
├── requirements.txt
├── run.py
├── seed.py
├── README.md
```

## Configuration and deployment notes

- Set a strong, unique `SECRET_KEY` outside source control.
- Set `DATABASE_URL` to the intended database before applying migrations.
- Configure M-Pesa credentials and a reachable callback URL only in the environment where the integration is being used.
- Use HTTPS and a production-ready WSGI server when deploying.
- Do not expose debug mode or development credentials in a public deployment.

## Contributing

Contributions are welcome. For substantial changes, open an issue first to discuss the proposed approach. When submitting a pull request, include a clear description of the change and the relevant test results.

## License

No license is currently specified in this repository. Unless a license is added, the project’s code is not explicitly released under an open-source license.

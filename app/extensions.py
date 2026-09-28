from flask_sqlalchemy import SQLAlchemy   #importing the library
from flask_migrate import Migrate
from flask_login import LoginManager


db = SQLAlchemy()                          #creating an instance of the SQLAlchemy class
migrate = Migrate()
login_manager = LoginManager()

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
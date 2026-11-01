from flask import render_template

from app.public import public_bp


@public_bp.route("/")
def home():
    return render_template("public/home.html")


@public_bp.route("/about")
def about():
    return render_template("public/about.html")


@public_bp.route("/contact")
def contact():
    return render_template("public/contact.html")
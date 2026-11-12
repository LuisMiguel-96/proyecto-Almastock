import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@auth_bp.route("/", methods=["GET", "POST"])
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.scalar(
            db.select(User).where(func.lower(User.email) == email)
        )
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Bienvenido a AlmaStock.", "success")
            return redirect(url_for("main.dashboard"))
        flash("Correo o contraseña incorrectos.", "danger")
    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not EMAIL_PATTERN.match(email):
            flash("Ingresa un correo electrónico válido.", "warning")
        elif len(password) < 10:
            flash("La contraseña debe tener al menos 10 caracteres.", "warning")
        elif db.session.scalar(
            db.select(User).where(func.lower(User.email) == email)
        ):
            flash("Ya existe una cuenta con ese correo.", "warning")
        else:
            # La primera cuenta se crea como administradora. Las siguientes,
            # mediante registro público, quedan como operarios.
            first_user = db.session.scalar(db.select(User.id).limit(1)) is None
            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role="admin" if first_user else "operario",
            )
            db.session.add(user)
            db.session.commit()
            flash(
                "Cuenta administradora creada." if first_user
                else "Cuenta de operario creada. Ya puedes iniciar sesión.",
                "success",
            )
            return redirect(url_for("auth.login"))
    return render_template("register.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("auth.login"))

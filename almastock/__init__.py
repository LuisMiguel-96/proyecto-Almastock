"""Aplicación AlmaStock: control de inventario."""
from pathlib import Path
import click
from flask import Flask
from sqlalchemy import text, inspect
from .config import Config
from .extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Inicia sesión para acceder a esta sección."
    login_manager.login_message_category = "warning"

    from .auth import auth_bp
    from .routes import main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        # Migración sencilla para instalaciones de Fase 1 que ya tengan users
        # sin columna role. No elimina ni reemplaza registros existentes.
        columns = {column["name"] for column in inspect(db.engine).get_columns("users")}
        if "role" not in columns:
            db.session.execute(
                text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'operario'")
            )
        product_columns = {column["name"] for column in inspect(db.engine).get_columns("products")}
        if "min_stock" not in product_columns:
            db.session.execute(
                text("ALTER TABLE products ADD COLUMN min_stock INTEGER NOT NULL DEFAULT 5")
            )
        movement_columns = {column["name"] for column in inspect(db.engine).get_columns("movements")}
        if "user_id" not in movement_columns:
            db.session.execute(
                text("ALTER TABLE movements ADD COLUMN user_id INTEGER REFERENCES users(id)")
            )
        db.session.commit()

    @app.cli.command("promote-admin")
    @click.argument("email")
    def promote_admin(email):
        """Asigna el rol admin a una cuenta existente."""
        from .models import User
        from sqlalchemy import func, select
        user = db.session.scalar(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )
        if user is None:
            raise click.ClickException("No existe una cuenta con ese correo.")
        user.role = "admin"
        db.session.commit()
        click.echo(f"{user.email} ahora tiene rol administrador.")

    @app.errorhandler(403)
    def forbidden(_error):
        from flask import render_template
        return render_template("403.html"), 403

    return app

from datetime import datetime, date, time
import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response, make_response
from flask_login import login_required, current_user
from sqlalchemy import select, func, update, or_
from sqlalchemy.exc import IntegrityError
from .extensions import db
from .models import Product, Movement, User
from .security import admin_required

main_bp = Blueprint("main", __name__)


def _movement_filters():
    product_term = request.args.get("product", "").strip()[:120]
    movement_type = request.args.get("type", "").strip().lower()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    stmt = select(Movement).join(Product).order_by(Movement.date.desc())
    if product_term:
        stmt = stmt.where(or_(
            Product.name.ilike(f"%{product_term}%"),
            Product.sku.ilike(f"%{product_term}%")
        ))
    if movement_type in {"entrada", "salida"}:
        stmt = stmt.where(Movement.type == movement_type)
    else:
        movement_type = ""
    try:
        if start_date:
            stmt = stmt.where(Movement.date >= datetime.combine(date.fromisoformat(start_date), time.min))
        if end_date:
            stmt = stmt.where(Movement.date <= datetime.combine(date.fromisoformat(end_date), time.max))
    except ValueError:
        start_date, end_date = "", ""
    return stmt, {"product": product_term, "type": movement_type,
                  "start_date": start_date, "end_date": end_date}


@main_bp.route("/dashboard")
@login_required
def dashboard():
    products = db.session.scalars(select(Product).order_by(Product.name)).all()
    total_products = len(products)
    total_units = sum(product.stock for product in products)
    low_stock_products = [p for p in products if p.stock <= p.min_stock]
    recent_movements = db.session.scalars(
        select(Movement).order_by(Movement.date.desc()).limit(8)
    ).all()
    return render_template(
        "dashboard.html", products=products, total_products=total_products,
        total_units=total_units, recent_movements=recent_movements,
        low_stock_products=low_stock_products
    )


@main_bp.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku = request.form.get("sku", "").strip() or None
        category = request.form.get("category", "").strip() or None
        min_stock = request.form.get("min_stock", type=int)
        if not name or len(name) > 120:
            flash("El nombre es obligatorio y no puede superar 120 caracteres.", "warning")
        elif sku and len(sku) > 50:
            flash("El código no puede superar 50 caracteres.", "warning")
        elif category and len(category) > 80:
            flash("La categoría no puede superar 80 caracteres.", "warning")
        elif min_stock is None or min_stock < 0 or min_stock > 2_000_000_000:
            flash("El stock mínimo debe ser un entero igual o mayor que cero.", "warning")
        elif sku and db.session.scalar(
            select(Product).where(func.lower(Product.sku) == sku.lower())
        ):
            flash("Ya existe un producto con ese código.", "warning")
        else:
            try:
                db.session.add(Product(name=name, sku=sku, category=category,
                                       stock=0, min_stock=min_stock))
                db.session.commit()
                flash("Producto creado correctamente.", "success")
                return redirect(url_for("main.products"))
            except IntegrityError:
                db.session.rollback()
                flash("No se pudo guardar: el código del producto ya existe.", "warning")
    product_list = db.session.scalars(select(Product).order_by(Product.name)).all()
    return render_template("products.html", products=product_list)


@main_bp.route("/stock")
@login_required
def stock():
    name = request.args.get("name", "").strip()[:120]
    sku = request.args.get("sku", "").strip()[:50]
    category = request.args.get("category", "").strip()[:80]
    low_only = request.args.get("low") == "1"
    statement = select(Product).order_by(Product.name)
    if name:
        statement = statement.where(Product.name.ilike(f"%{name}%"))
    if sku:
        statement = statement.where(Product.sku.ilike(f"%{sku}%"))
    if category:
        statement = statement.where(Product.category.ilike(f"%{category}%"))
    if low_only:
        statement = statement.where(Product.stock <= Product.min_stock)
    products = db.session.scalars(statement).all()
    return render_template("stock.html", products=products, search_name=name,
                           search_sku=sku, search_category=category, low_only=low_only)


@main_bp.route("/movements")
@login_required
def movements():
    stmt, filters = _movement_filters()
    movement_list = db.session.scalars(stmt.limit(500)).all()
    products = db.session.scalars(select(Product).order_by(Product.name)).all()
    return render_template("movements.html", movements=movement_list,
                           products=products, filters=filters)


@main_bp.route("/movement", methods=["POST"])
@login_required
def create_movement():
    product_id = request.form.get("product_id", type=int)
    quantity = request.form.get("quantity", type=int)
    movement_type = request.form.get("type", "").strip().lower()

    if not product_id or not db.session.get(Product, product_id):
        flash("Selecciona un producto válido.", "warning")
        return redirect(url_for("main.movements"))
    if quantity is None or quantity <= 0 or quantity > 2_000_000_000:
        flash("La cantidad debe ser un entero mayor que cero y válido.", "warning")
        return redirect(url_for("main.movements"))
    if movement_type not in {"entrada", "salida"}:
        flash("Tipo de movimiento no válido.", "warning")
        return redirect(url_for("main.movements"))

    try:
        if movement_type == "entrada":
            result = db.session.execute(
                update(Product).where(Product.id == product_id)
                .values(stock=Product.stock + quantity)
            )
        else:
            result = db.session.execute(
                update(Product).where(Product.id == product_id, Product.stock >= quantity)
                .values(stock=Product.stock - quantity)
            )
            if result.rowcount != 1:
                db.session.rollback()
                flash("No hay existencias suficientes para esa salida.", "danger")
                return redirect(url_for("main.movements"))

        db.session.add(Movement(type=movement_type, quantity=quantity,
                                product_id=product_id, user_id=current_user.id))
        db.session.commit()
        flash("Movimiento registrado correctamente.", "success")
    except Exception:
        db.session.rollback()
        flash("No se pudo registrar el movimiento. No se guardaron cambios.", "danger")
    return redirect(url_for("main.movements"))


@main_bp.route("/reports")
@login_required
def reports():
    stmt, filters = _movement_filters()
    movements = db.session.scalars(stmt.limit(1000)).all()
    products = db.session.scalars(select(Product).order_by(Product.name)).all()
    total_entries = sum(m.quantity for m in movements if m.type == "entrada")
    total_exits = sum(m.quantity for m in movements if m.type == "salida")
    low_stock = [p for p in products if p.stock <= p.min_stock]
    return render_template("reports.html", movements=movements, filters=filters,
                           total_entries=total_entries, total_exits=total_exits,
                           low_stock=low_stock, total_products=len(products),
                           total_units=sum(p.stock for p in products))


@main_bp.route("/reports/export.csv")
@login_required
def export_report_csv():
    stmt, _filters = _movement_filters()
    rows = db.session.scalars(stmt.limit(10000)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Producto", "SKU", "Tipo", "Cantidad", "Fecha", "Usuario"])
    for m in rows:
        writer.writerow([m.id, m.product.name, m.product.sku or "",
                         m.type, m.quantity, m.date.strftime("%Y-%m-%d %H:%M:%S"),
                         m.user.email if m.user else "No disponible"])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=almastock_movimientos.csv"
    return response


@main_bp.route("/reports/export.pdf")
@login_required
def export_report_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        flash("Falta instalar ReportLab. Ejecuta: python -m pip install -r requirements.txt", "warning")
        return redirect(url_for("main.reports"))

    stmt, _filters = _movement_filters()
    rows = db.session.scalars(stmt.limit(1000)).all()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [Paragraph("AlmaStock - Reporte de movimientos", styles["Title"]),
                Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
                Spacer(1, 12)]
    data = [["ID", "Producto", "Código", "Tipo", "Cantidad", "Fecha", "Usuario"]]
    for m in rows:
        data.append([str(m.id), m.product.name[:32], (m.product.sku or "")[:18],
                     m.type.title(), str(m.quantity), m.date.strftime("%d/%m/%Y %H:%M"),
                     (m.user.email if m.user else "N/D")[:28]])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243447")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f5")]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return Response(buffer.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=almastock_movimientos.pdf"})


@main_bp.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        new_role = request.form.get("role", "").strip()
        target = db.session.get(User, user_id) if user_id else None

        if target is None or new_role not in {"admin", "operario"}:
            flash("Usuario o rol no válido.", "warning")
        elif target.id == current_user.id and new_role != "admin":
            flash("No puedes quitarte tu propio rol de administrador.", "warning")
        elif target.is_admin and new_role != "admin":
            admins = db.session.scalar(
                select(func.count()).select_from(User).where(User.role == "admin")
            )
            if admins <= 1:
                flash("Debe existir al menos un administrador.", "warning")
            else:
                target.role = new_role
                db.session.commit()
                flash("Rol actualizado correctamente.", "success")
        else:
            target.role = new_role
            db.session.commit()
            flash("Rol actualizado correctamente.", "success")
        return redirect(url_for("main.users"))

    user_list = db.session.scalars(select(User).order_by(User.email)).all()
    return render_template("users.html", users=user_list)

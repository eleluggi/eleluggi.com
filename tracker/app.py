"""Main application module for the delivery tracker."""
from __future__ import annotations

import csv
import io
import os
from datetime import date
from pathlib import Path

from flask import Flask, Response, flash, g, redirect, render_template, request, url_for
from flask_wtf import CSRFProtect
from sqlalchemy import desc, nullslast

from flask import Blueprint

from .auth import auth_bp
from .forms import (
    DeleteForm,
    DeliveryNoteForm,
    DeliveryPriorityForm,
    DeliverySearchForm,
    DeliveryShipDateForm,
    DeliveryStationForm,
    DeviceLabelForm,
    RevokeDeviceForm,
    ScanForm,
    StationForm,
    UserForm,
)
from .models import Delivery, Event, EventType, Role, Station, User, db, init_db
from .utils import (
    due_badge_class,
    determine_due_status,
    eta_for_station,
    markdown_safe,
    pagination_range,
    priority_badge,
    role_required,
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "tracker.sqlite3"


main_bp = Blueprint("main", __name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.setdefault("SECRET_KEY", os.environ.get("TRACKER_SECRET", "change-me"))
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{DB_PATH}")
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    CSRFProtect(app)
    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    register_cli(app)

    @app.context_processor
    def inject_helpers() -> dict:
        return {
            "markdown_safe": markdown_safe,
            "determine_due_status": determine_due_status,
            "due_badge_class": due_badge_class,
            "priority_badge": priority_badge,
            "eta_for_station": eta_for_station,
        }

    return app


@main_bp.route("/")
@role_required(Role.VIEWER, Role.CONTRIBUTOR, Role.ADMIN)
def index():
    form = ScanForm()
    stations = Station.query.filter_by(is_active=True).order_by(Station.sort_order, Station.name).all()
    return render_template("index.html", form=form, stations=stations)


@main_bp.route("/scan", methods=["POST"])
@role_required(Role.VIEWER, Role.CONTRIBUTOR, Role.ADMIN)
def scan():
    form = ScanForm()
    if form.validate_on_submit():
        number = form.lieferscheinnummer.data.strip().upper()
        delivery = Delivery.query.filter_by(lieferscheinnummer=number).first()
        created = False
        if not delivery:
            delivery = Delivery(lieferscheinnummer=number)
            db.session.add(delivery)
            created = True
        event = Event(
            delivery=delivery,
            actor_username=g.current_user.username,
            type=EventType.SCAN,
        )
        db.session.add(event)
        db.session.commit()
        flash("Lieferschein erfasst" + (" (neu)" if created else ""), "success")
        return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))
    flash("Scan fehlgeschlagen", "danger")
    return redirect(url_for("main.index"))


@main_bp.route("/deliveries")
@role_required(Role.VIEWER, Role.CONTRIBUTOR, Role.ADMIN)
def deliveries_list():
    form = DeliverySearchForm(request.args, meta={"csrf": False})
    stations = Station.query.order_by(Station.sort_order, Station.name).all()
    form.station_id.choices = [(0, "Alle Stationen")] + [(s.id, s.name) for s in stations]

    query = Delivery.query
    if form.query.data:
        like = f"%{form.query.data.strip()}%"
        query = query.filter(Delivery.lieferscheinnummer.ilike(like))
    if form.station_id.data and form.station_id.data != 0:
        query = query.filter(Delivery.current_station_id == form.station_id.data)
    if form.shipping_week.data:
        query = query.filter(Delivery.shipping_week == form.shipping_week.data)
    if form.priority.data is not None and form.priority.data != "":
        query = query.filter(Delivery.priority == form.priority.data)

    query = query.order_by(desc(Delivery.updated_at))

    page = request.args.get("page", default=1, type=int)
    pagination = query.paginate(page=page, per_page=25)

    filters = request.args.to_dict()
    filters.pop("page", None)

    return render_template(
        "deliveries_list.html",
        deliveries=pagination.items,
        pagination=pagination,
        form=form,
        pagination_range=pagination_range,
        filters=filters,
    )


def get_delivery_or_404(delivery_id: int) -> Delivery:
    delivery = Delivery.query.get_or_404(delivery_id)
    return delivery


@main_bp.route("/d/<int:delivery_id>")
@role_required(Role.VIEWER, Role.CONTRIBUTOR, Role.ADMIN)
def delivery_detail(delivery_id: int):
    delivery = get_delivery_or_404(delivery_id)
    station_form = DeliveryStationForm()
    note_form = DeliveryNoteForm()
    ship_form = DeliveryShipDateForm()
    priority_form = DeliveryPriorityForm()

    stations = Station.query.filter_by(is_active=True).order_by(Station.sort_order).all()
    station_form.station_id.choices = [(s.id, s.name) for s in stations]
    if delivery.current_station_id:
        station_form.station_id.data = delivery.current_station_id
    priority_form.priority.data = delivery.priority
    if delivery.ship_date:
        ship_form.ship_date.data = delivery.ship_date

    events = Event.query.filter_by(delivery_id=delivery.id).order_by(Event.created_at.desc()).all()
    eta = eta_for_station(delivery.current_station)
    due_status = determine_due_status(delivery)

    return render_template(
        "delivery_detail.html",
        delivery=delivery,
        events=events,
        station_form=station_form,
        note_form=note_form,
        ship_form=ship_form,
        priority_form=priority_form,
        eta=eta,
        due_status=due_status,
    )


@main_bp.route("/d/<int:delivery_id>/station", methods=["POST"])
@role_required(Role.ADMIN, Role.CONTRIBUTOR)
def set_station(delivery_id: int):
    delivery = get_delivery_or_404(delivery_id)
    form = DeliveryStationForm()
    stations = Station.query.filter_by(is_active=True).order_by(Station.sort_order).all()
    form.station_id.choices = [(s.id, s.name) for s in stations]
    if form.validate_on_submit():
        station = Station.query.get(form.station_id.data)
        if not station:
            flash("Station nicht gefunden", "danger")
        else:
            delivery.current_station = station
            event = Event(
                delivery=delivery,
                actor_username=g.current_user.username,
                type=EventType.SET_STATION,
                station=station,
                new_value=station.name,
            )
            db.session.add_all([delivery, event])
            db.session.commit()
            flash("Station aktualisiert", "success")
    else:
        flash("Station konnte nicht gesetzt werden", "danger")
    return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))


@main_bp.route("/d/<int:delivery_id>/note", methods=["POST"])
@role_required(Role.ADMIN, Role.CONTRIBUTOR)
def add_note(delivery_id: int):
    delivery = get_delivery_or_404(delivery_id)
    form = DeliveryNoteForm()
    if form.validate_on_submit():
        event = Event(
            delivery=delivery,
            actor_username=g.current_user.username,
            type=EventType.NOTE,
            note_text=form.note_text.data.strip(),
        )
        db.session.add(event)
        db.session.commit()
        flash("Notiz gespeichert", "success")
    else:
        flash("Notiz konnte nicht gespeichert werden", "danger")
    return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))


@main_bp.route("/d/<int:delivery_id>/shipdate", methods=["POST"])
@role_required(Role.ADMIN, Role.CONTRIBUTOR)
def set_ship_date(delivery_id: int):
    delivery = get_delivery_or_404(delivery_id)
    form = DeliveryShipDateForm()
    if form.validate_on_submit():
        delivery.set_ship_date(form.ship_date.data)
        event = Event(
            delivery=delivery,
            actor_username=g.current_user.username,
            type=EventType.SET_SHIP_DATE,
            new_value=form.ship_date.data.isoformat() if form.ship_date.data else "gelöscht",
        )
        db.session.add_all([delivery, event])
        db.session.commit()
        flash("Versanddatum gespeichert", "success")
    else:
        flash("Versanddatum ungültig", "danger")
    return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))


@main_bp.route("/d/<int:delivery_id>/priority", methods=["POST"])
@role_required(Role.ADMIN, Role.CONTRIBUTOR)
def set_priority(delivery_id: int):
    delivery = get_delivery_or_404(delivery_id)
    form = DeliveryPriorityForm()
    if form.validate_on_submit():
        delivery.priority = form.priority.data
        event = Event(
            delivery=delivery,
            actor_username=g.current_user.username,
            type=EventType.SET_PRIORITY,
            new_value=str(form.priority.data),
        )
        db.session.add_all([delivery, event])
        db.session.commit()
        flash("Priorität aktualisiert", "success")
    else:
        flash("Priorität ungültig", "danger")
    return redirect(url_for("main.delivery_detail", delivery_id=delivery.id))


@main_bp.route("/shipping")
@role_required(Role.VIEWER, Role.CONTRIBUTOR, Role.ADMIN)
def shipping_board():
    scope = request.args.get("scope", "all")
    today = date.today()
    week = today.isocalendar().week

    query = Delivery.query
    if scope == "overdue":
        query = query.filter(Delivery.ship_date != None, Delivery.ship_date < today)  # noqa: E711
    elif scope == "today":
        query = query.filter(Delivery.ship_date == today)
    elif scope == "week":
        query = query.filter(Delivery.shipping_week == week)
    elif scope == "future":
        query = query.filter(Delivery.ship_date != None, Delivery.ship_date > today)  # noqa: E711

    deliveries = query.order_by(
        desc(Delivery.priority),
        nullslast(Delivery.ship_date.asc()),
        desc(Delivery.updated_at),
    ).all()

    stations = Station.query.filter_by(is_active=True).order_by(Station.sort_order).all()

    return render_template(
        "shipping_board.html",
        deliveries=deliveries,
        scope=scope,
        stations=stations,
        today=today,
    )


@main_bp.route("/export.csv")
@role_required(Role.VIEWER, Role.CONTRIBUTOR, Role.ADMIN)
def export_csv():
    scope = request.args.get("scope", "all")
    today = date.today()
    week = today.isocalendar().week

    query = Delivery.query
    if scope == "overdue":
        query = query.filter(Delivery.ship_date != None, Delivery.ship_date < today)  # noqa: E711
    elif scope == "today":
        query = query.filter(Delivery.ship_date == today)
    elif scope == "week":
        query = query.filter(Delivery.shipping_week == week)

    deliveries = query.order_by(desc(Delivery.priority), Delivery.ship_date, desc(Delivery.updated_at)).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["lieferscheinnummer", "ship_date", "shipping_week", "priority", "station", "updated_at"])
    for d in deliveries:
        writer.writerow(
            [
                d.lieferscheinnummer,
                d.ship_date.isoformat() if d.ship_date else "",
                d.shipping_week or "",
                d.priority,
                d.current_station.name if d.current_station else "",
                d.updated_at.isoformat() if d.updated_at else "",
            ]
        )
    output.seek(0)
    filename = f"export_{scope}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_bp.route("/stations", methods=["GET", "POST"])
@role_required(Role.ADMIN)
def admin_stations():
    form = StationForm()
    delete_form = DeleteForm()
    if form.submit.data and form.validate_on_submit():
        if form.id.data:
            station = Station.query.get_or_404(int(form.id.data))
            station.name = form.name.data.strip()
            station.info_text = form.info_text.data
            station.default_duration_hours = form.default_duration_hours.data
            station.sort_order = form.sort_order.data or 0
            station.is_active = form.is_active.data == "1"
            flash("Station aktualisiert", "success")
        else:
            station = Station(
                name=form.name.data.strip(),
                info_text=form.info_text.data,
                default_duration_hours=form.default_duration_hours.data,
                sort_order=form.sort_order.data or 0,
                is_active=form.is_active.data == "1",
            )
            db.session.add(station)
            flash("Station angelegt", "success")
        db.session.commit()
        return redirect(url_for("admin.admin_stations"))

    if delete_form.delete.data and delete_form.validate_on_submit():
        station = Station.query.get_or_404(int(delete_form.id.data))
        db.session.delete(station)
        db.session.commit()
        flash("Station gelöscht", "info")
        return redirect(url_for("admin.admin_stations"))

    edit_id = request.args.get("edit", type=int)
    if edit_id:
        station = Station.query.get_or_404(edit_id)
        form.id.data = str(station.id)
        form.name.data = station.name
        form.info_text.data = station.info_text
        form.default_duration_hours.data = station.default_duration_hours
        form.sort_order.data = station.sort_order
        form.is_active.data = "1" if station.is_active else "0"

    stations = Station.query.order_by(Station.sort_order, Station.name).all()
    return render_template("admin_stations.html", stations=stations, form=form, delete_form=delete_form)


@admin_bp.route("/users", methods=["GET", "POST"])
@role_required(Role.ADMIN)
def admin_users():
    form = UserForm()
    delete_form = DeleteForm()
    if form.submit.data and form.validate_on_submit():
        username = form.username.data.strip().lower()
        if form.id.data:
            user = User.query.get_or_404(int(form.id.data))
            user.username = username
            user.role = Role(form.role.data)
            flash("Benutzer aktualisiert", "success")
        else:
            if User.query.filter_by(username=username).first():
                flash("Benutzername bereits vergeben", "danger")
            else:
                user = User(username=username, role=Role(form.role.data))
                db.session.add(user)
                flash("Benutzer angelegt", "success")
        db.session.commit()
        return redirect(url_for("admin.admin_users"))

    if delete_form.delete.data and delete_form.validate_on_submit():
        user = User.query.get_or_404(int(delete_form.id.data))
        if user.username == "admin":
            flash("Admin kann nicht gelöscht werden", "warning")
        else:
            db.session.delete(user)
            db.session.commit()
            flash("Benutzer gelöscht", "info")
        return redirect(url_for("admin.admin_users"))

    edit_id = request.args.get("edit", type=int)
    if edit_id:
        user = User.query.get_or_404(edit_id)
        form.id.data = str(user.id)
        form.username.data = user.username
        form.role.data = user.role.value

    users = User.query.order_by(User.username).all()
    return render_template("admin_users.html", users=users, form=form, delete_form=delete_form)


@admin_bp.route("/devices", methods=["GET", "POST"])
@role_required(Role.ADMIN)
def admin_devices():
    label_form = DeviceLabelForm()
    revoke_form = RevokeDeviceForm()

    if label_form.label.data and label_form.validate_on_submit():
        device = Device.query.get_or_404(int(label_form.id.data))
        device.device_label = label_form.device_label.data
        db.session.commit()
        flash("Gerätename aktualisiert", "success")
        return redirect(url_for("admin.admin_devices"))

    if revoke_form.revoke.data and revoke_form.validate_on_submit():
        device = Device.query.get_or_404(int(revoke_form.id.data))
        device.revoke()
        db.session.commit()
        flash("Gerät abgemeldet", "info")
        return redirect(url_for("admin.admin_devices"))

    devices = Device.query.order_by(Device.last_seen.desc()).all()
    return render_template(
        "admin_devices.html",
        devices=devices,
        label_form=label_form,
        revoke_form=revoke_form,
    )


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command():
        """Initialise database and seed demo data."""
        os.makedirs(DB_PATH.parent, exist_ok=True)
        init_db(app)
        click = __import__("click")
        click.echo("Database initialised and seeded.")


app = create_app()

if __name__ == "__main__":
    os.makedirs(DB_PATH.parent, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)

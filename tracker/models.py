"""Database models for the delivery tracker."""
from __future__ import annotations

import enum
import hashlib
from datetime import datetime, date
from typing import Optional

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index


db = SQLAlchemy()


class Role(enum.StrEnum):
    """Roles available for users."""

    ADMIN = "admin"
    CONTRIBUTOR = "contrib"
    VIEWER = "viewer"


class EventType(enum.StrEnum):
    """Event types for delivery timeline."""

    SCAN = "scan"
    SET_STATION = "set_station"
    NOTE = "note"
    SET_SHIP_DATE = "set_ship_date"
    SET_PRIORITY = "set_priority"


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.VIEWER)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    devices = db.relationship("Device", backref="user", lazy=True)
    events = db.relationship("Event", backref="delivery_actor", lazy=True)

    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    def can_contribute(self) -> bool:
        return self.role in {Role.ADMIN, Role.CONTRIBUTOR}


class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    info_text = db.Column(db.Text, nullable=True)
    default_duration_hours = db.Column(db.Integer, nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    deliveries = db.relationship("Delivery", backref="current_station", lazy=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Station {self.name}>"


class Delivery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lieferscheinnummer = db.Column(db.String(120), unique=True, nullable=False, index=True)
    current_station_id = db.Column(db.Integer, db.ForeignKey("station.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    ship_date = db.Column(db.Date, nullable=True)
    shipping_week = db.Column(db.Integer, nullable=True)
    priority = db.Column(db.Integer, nullable=False, default=0)

    events = db.relationship("Event", backref="delivery", lazy=True, order_by="Event.created_at.desc()")

    __table_args__ = (
        Index("ix_delivery_shipping_week", "shipping_week"),
        Index("ix_delivery_ship_date", "ship_date"),
        Index("ix_delivery_priority", "priority"),
        Index("ix_delivery_updated_at", "updated_at"),
    )

    def set_ship_date(self, ship_date_value: Optional[date]) -> None:
        """Set ship date and calculate ISO week."""
        self.ship_date = ship_date_value
        if ship_date_value is None:
            self.shipping_week = None
        else:
            self.shipping_week = ship_date_value.isocalendar().week


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey("delivery.id"), nullable=False)
    actor_username = db.Column(db.String(80), nullable=False)
    type = db.Column(db.Enum(EventType), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey("station.id"), nullable=True)
    note_text = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    station = db.relationship("Station")


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    device_label = db.Column(db.String(120), nullable=True)
    token_hash = db.Column(db.String(128), nullable=False, index=True)
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_revoked = db.Column(db.Boolean, default=False, nullable=False)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def revoke(self) -> None:
        self.is_revoked = True
        db.session.add(self)


def init_db(app) -> None:
    """Initialise the database, seed basic data and create admin user."""
    with app.app_context():
        db.create_all()

        if not User.query.filter_by(username="admin").first():
            admin_user = User(username="admin", role=Role.ADMIN)
            contrib_user = User(username="halle", role=Role.CONTRIBUTOR)
            viewer_user = User(username="buero", role=Role.VIEWER)
            db.session.add_all([admin_user, contrib_user, viewer_user])
            current_app.logger.info("Seeded default users: admin, halle, buero")

        if Station.query.count() == 0:
            stations = [
                Station(name="Eingang", sort_order=10, is_active=True),
                Station(name="Halle A", sort_order=20, is_active=True),
                Station(name="Halle B", sort_order=30, is_active=True),
                Station(name="Pulverbeschichtung", sort_order=40, is_active=True),
                Station(name="Versand", sort_order=50, is_active=True),
                Station(name="Versand abgeschlossen", sort_order=60, is_active=True),
            ]
            db.session.add_all(stations)
            current_app.logger.info("Seeded example stations")

        db.session.commit()


def touch_updated_at(mapper, connection, target) -> None:
    connection.execute(
        Delivery.__table__.update()
        .where(Delivery.id == target.delivery_id)
        .values(updated_at=datetime.utcnow())
    )


# ensure updated_at touches on event creation
from sqlalchemy import event as sa_event  # noqa: E402

sa_event.listen(Event, "after_insert", touch_updated_at)

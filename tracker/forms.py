"""Forms used throughout the tracker application."""
from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import DateField, HiddenField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp

from .models import Role

USERNAME_RE = r"^[A-Za-z0-9_.-]+$"
LIEFERSCHEIN_RE = r"^[A-Za-z0-9_-]{3,120}$"


class LoginForm(FlaskForm):
    username = StringField("Benutzername", validators=[DataRequired(), Length(max=80), Regexp(USERNAME_RE)])
    device_label = StringField("Gerätename", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Anmelden")


class ScanForm(FlaskForm):
    lieferscheinnummer = StringField(
        "Lieferscheinnummer",
        validators=[DataRequired(), Length(min=3, max=120), Regexp(LIEFERSCHEIN_RE)],
        render_kw={"autofocus": True, "data-scan-input": "true"},
    )
    submit = SubmitField("Scannen")


class DeliveryStationForm(FlaskForm):
    station_id = SelectField("Station", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Station setzen")


class DeliveryNoteForm(FlaskForm):
    note_text = TextAreaField("Notiz", validators=[DataRequired(), Length(max=2000)])
    submit = SubmitField("Notiz speichern")


class DeliveryShipDateForm(FlaskForm):
    ship_date = DateField("Versanddatum", validators=[Optional()])
    submit = SubmitField("Speichern")


class DeliveryPriorityForm(FlaskForm):
    priority = IntegerField("Priorität", validators=[DataRequired()])
    submit = SubmitField("Priorität setzen")


class DeliverySearchForm(FlaskForm):
    query = StringField("Suche", validators=[Optional(), Length(max=120)])
    station_id = SelectField("Station", coerce=int, validators=[Optional()], default=0)
    shipping_week = IntegerField("Lieferwoche", validators=[Optional()])
    priority = IntegerField("Priorität", validators=[Optional()])
    submit = SubmitField("Filtern")


class StationForm(FlaskForm):
    id = HiddenField()
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    info_text = TextAreaField("Info", validators=[Optional()])
    default_duration_hours = IntegerField("Standarddauer (h)", validators=[Optional()])
    sort_order = IntegerField("Sortierung", validators=[Optional()])
    is_active = SelectField(
        "Aktiv",
        choices=[("1", "Ja"), ("0", "Nein")],
        default="1",
        validators=[DataRequired()],
    )
    submit = SubmitField("Speichern")


class UserForm(FlaskForm):
    id = HiddenField()
    username = StringField("Benutzername", validators=[DataRequired(), Length(max=80), Regexp(USERNAME_RE)])
    role = SelectField(
        "Rolle",
        choices=[(Role.ADMIN.value, "Admin"), (Role.CONTRIBUTOR.value, "Bearbeiter"), (Role.VIEWER.value, "Viewer")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Speichern")


class DeviceLabelForm(FlaskForm):
    id = HiddenField()
    device_label = StringField("Gerätename", validators=[Optional(), Length(max=120)])
    label = SubmitField("Aktualisieren")


class RevokeDeviceForm(FlaskForm):
    id = HiddenField(validators=[DataRequired()])
    revoke = SubmitField("Revoke")


class DeleteForm(FlaskForm):
    id = HiddenField(validators=[DataRequired()])
    delete = SubmitField("Löschen")

"""Authentication helpers and blueprint for the tracker."""
from __future__ import annotations

import secrets
import time
from datetime import datetime
from typing import Optional

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from .forms import LoginForm
from .models import Device, User, db

AUTH_COOKIE = "device_token"
TOKEN_MAX_AGE = 60 * 60 * 24 * 365  # one year
RATE_LIMIT_WINDOW = 60
MAX_ATTEMPTS_PER_WINDOW = 20

login_attempts: dict[str, list[float]] = {}

auth_bp = Blueprint("auth", __name__)


def record_attempt(ip: str) -> None:
    now = time.time()
    attempts = login_attempts.setdefault(ip, [])
    attempts.append(now)
    # prune old
    login_attempts[ip] = [t for t in attempts if now - t <= RATE_LIMIT_WINDOW]


def allowed_attempt(ip: str) -> bool:
    record_attempt(ip)
    return len(login_attempts.get(ip, [])) <= MAX_ATTEMPTS_PER_WINDOW


def set_login_cookie(response, token: str) -> None:
    secure = current_app.config.get("SESSION_COOKIE_SECURE", False)
    response.set_cookie(
        AUTH_COOKIE,
        token,
        max_age=TOKEN_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=secure,
    )


def clear_login_cookie(response) -> None:
    response.delete_cookie(AUTH_COOKIE)


@auth_bp.before_app_request
def load_user_from_token() -> None:
    token = request.cookies.get(AUTH_COOKIE)
    g.current_user = None
    g.current_device = None
    if not token:
        return
    token_hash = Device.hash_token(token)
    device = Device.query.filter_by(token_hash=token_hash, is_revoked=False).first()
    if not device or not device.user:
        return
    device.last_seen = datetime.utcnow()
    db.session.add(device)
    db.session.commit()
    g.current_user = device.user
    g.current_device = device


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        client_ip = request.remote_addr or "unknown"
        if not allowed_attempt(client_ip):
            flash("Zu viele Login-Versuche. Bitte kurz warten.", "danger")
            return render_template("login.html", form=form)

        user = User.query.filter_by(username=form.username.data.strip().lower()).first()
        if not user:
            flash("Unbekannter Benutzer", "danger")
            return render_template("login.html", form=form)

        token = secrets.token_urlsafe(48)
        device = Device(
            user=user,
            device_label=form.device_label.data or request.user_agent.string[:120],
            token_hash=Device.hash_token(token),
            last_seen=datetime.utcnow(),
        )
        db.session.add(device)
        db.session.commit()
        flash("Erfolgreich angemeldet", "success")
        response = make_response(redirect(url_for("main.index")))
        set_login_cookie(response, token)
        return response
    return render_template("login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(redirect(url_for("auth.login")))
    token = request.cookies.get(AUTH_COOKIE)
    if token:
        token_hash = Device.hash_token(token)
        device = Device.query.filter_by(token_hash=token_hash).first()
        if device:
            device.revoke()
            db.session.commit()
    clear_login_cookie(response)
    flash("Abgemeldet", "info")
    return response


@auth_bp.app_context_processor
def inject_user() -> dict[str, Optional[User]]:
    return {"current_user": getattr(g, "current_user", None)}

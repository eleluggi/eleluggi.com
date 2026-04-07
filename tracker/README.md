# Liefer-Tracker

Industrial dark-theme Flask-Anwendung für das Scannen, Nachverfolgen und Priorisieren von Lieferungen auf einem Raspberry Pi.

## Features

- Benutzer-Login ohne Passwort mit Geräte-Token (HttpOnly Cookie)
- Rollenmodell (`admin`, `contrib`, `viewer`) mit differenzierten Berechtigungen
- Lieferübersicht mit Filter- & Suchfunktionen sowie Prioritäts-Board
- Ereignis-Timeline je Lieferung inkl. Notizen, Station- & Versandänderungen
- Admin-Tools zur Verwaltung von Stationen, Nutzern und registrierten Geräten
- CSV-Export nach Fälligkeitsstatus
- Touchfreundliches, dunkles UI mit gelben Akzenten und akustischem Feedback

## Installation

```bash
sudo apt update && sudo apt install python3-venv git -y
cd /opt
sudo git clone <REPO_URL> liefer-tracker
cd liefer-tracker/tracker
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
flask --app app init-db
```

Standardnutzer nach Initialisierung:

- `admin` (admin)
- `halle` (contrib)
- `buero` (viewer)

Beispielstationen werden automatisch angelegt.

## Entwicklung / Start

```bash
source .venv/bin/activate
flask --app app run --debug
```

Produktionsbetrieb (Gunicorn):

```bash
source /opt/liefer-tracker/tracker/.venv/bin/activate
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

## systemd-Service (Beispiel)

```
[Unit]
Description=Liefer Tracker
After=network.target

[Service]
User=pi
Group=pi
WorkingDirectory=/opt/liefer-tracker/tracker
Environment="FLASK_APP=app"
Environment="TRACKER_SECRET=wechselmich"
ExecStart=/opt/liefer-tracker/tracker/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## Nginx-Proxy Snippet

```
server {
    listen 80;
    server_name tracker.internal;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Backup-Hinweis

Das SQLite-DB-File liegt unter `tracker/data/tracker.sqlite3`. Für ein Backup reicht das Kopieren des gesamten `data/`-Ordners.

## Smoke-Test

1. Anwendung starten und als `halle` anmelden.
2. Drei Lieferscheine scannen: `LS-1001`, `LS-1002`, `LS-1003`.
3. Setze für `LS-1001` das Versanddatum auf heute, für `LS-1002` auf gestern, `LS-1003` auf nächste Woche.
4. Öffne die Versandübersicht (`/shipping`) und prüfe, dass die drei Lieferungen den erwarteten Fälligkeitsstatus anzeigen (Heute, Überfällig, Diese Woche).


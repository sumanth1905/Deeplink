from . import db
from datetime import datetime


class Click(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    click_id = db.Column(db.String(64), unique=True, nullable=False)
    campaign = db.Column(db.String(128))
    source = db.Column(db.String(128))
    play_store_url = db.Column(db.String(512))
    app_store_url = db.Column(db.String(512))
    web_url = db.Column(db.String(512))
    package_name = db.Column(db.String(128))
    ios_bundle_id = db.Column(db.String(128))
    android_scheme = db.Column(db.String(128))
    total_clicks = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ADD THIS RELATIONSHIP ---
    installs = db.relationship('Install', backref='click', lazy=True)
    click_events = db.relationship('ClickEvent', backref='click_details', lazy=True)

class ClickEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    click_id = db.Column(db.String(64), db.ForeignKey('click.click_id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    platform = db.Column(db.String(32))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    language = db.Column(db.String(64))
    screen_width = db.Column(db.Integer)
    screen_height = db.Column(db.Integer)
    device_model = db.Column(db.String(128))
    os_version = db.Column(db.String(64))
    timezone = db.Column(db.String(64))
    referrer = db.Column(db.Text)

class Install(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    install_id = db.Column(db.String(64), unique=True, nullable=False)
    click_id = db.Column(db.String(64), db.ForeignKey('click.click_id'), nullable=True)
    platform = db.Column(db.String(32))
    
    # Existing specific fields
    device_model = db.Column(db.String(128))
    os_version = db.Column(db.String(64))
    language = db.Column(db.String(64))
    timezone = db.Column(db.String(64))
    ip_address = db.Column(db.String(45))
    
    # --- Existing New Fields ---
    advertising_id = db.Column(db.String(64), nullable=True, index=True)
    phone_number = db.Column(db.String(32), nullable=True, index=True)
    
    # --- Add Push Token ---
    push_token = db.Column(db.Text, nullable=True)
    # ------------------------

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

from flask import Blueprint, request, redirect, jsonify, render_template
from .models import db, Click, Install, ClickEvent
import uuid
import string
import random
from datetime import datetime, timedelta
import re
import urllib.parse

main = Blueprint('main', __name__)

def get_os_version(user_agent_string):
    """Parses the Android OS version from a User-Agent string."""
    if not user_agent_string:
        return None
    # Regex to find "Android" followed by a version number (e.g., "Android 13")
    match = re.search(r'android\s([\d\.]+)', user_agent_string.lower())
    if match:
        return match.group(1)
    return None

def get_device_model(user_agent_string):
    """Parses the device model from a User-Agent string (best-effort)."""
    if not user_agent_string:
        return None
    # Regex to find the model string after "Android X.X;"
    match = re.search(r'android\s[\d\.]+;\s([^)]+)', user_agent_string.lower())
    if match:
        # Return the captured group, which is the model string
        return match.group(1).strip()
    return None

def get_client_ip(request):
    """
    Prefer IPv4 from X-Forwarded-For or remote_addr, fallback to IPv6 if no IPv4 found.
    """
    ip_sources = []
    # Get all IPs from X-Forwarded-For if present
    xff = request.headers.get('X-Forwarded-For')
    if xff:
        ip_sources.extend([ip.strip() for ip in xff.split(',')])
    # Always add remote_addr as a fallback
    if request.remote_addr:
        ip_sources.append(request.remote_addr)
    # Regex for IPv4
    ipv4_regex = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    for ip in ip_sources:
        if ipv4_regex.match(ip):
            return ip
    # If no IPv4 found, return the first IP (could be IPv6)
    return ip_sources[0] if ip_sources else None

@main.route('/admin')
def admin_dashboard():
    all_clicks = Click.query.order_by(Click.timestamp.desc()).all()
    return render_template('dashboard.html', clicks=all_clicks)

@main.route('/admin/generate', methods=['POST'])
def admin_generate_link():
    # Generate a unique 4-character click_id
    chars = string.ascii_letters + string.digits
    while True:
        click_id = ''.join(random.choices(chars, k=4))
        if not Click.query.filter_by(click_id=click_id).first():
            break
    
    click = Click(
        click_id=click_id,
        campaign=request.form.get('campaign'),
        source=request.form.get('source'),
        play_store_url=request.form.get('play_store_url'),
        app_store_url=request.form.get('app_store_url'),
        web_url=request.form.get('web_url'),
        total_clicks=0,
        timestamp=datetime.utcnow()
    )
    db.session.add(click)
    db.session.commit()
    return redirect('/admin')

@main.route('/generate_link', methods=['POST'])
def generate_link():
    data = request.json
    campaign = data.get('campaign')
    source = data.get('source')

    # Generate a unique 4-character click_id
    chars = string.ascii_letters + string.digits
    while True:
        click_id = ''.join(random.choices(chars, k=4))
        if not Click.query.filter_by(click_id=click_id).first():
            break

    click = Click(click_id=click_id, campaign=campaign, source=source, total_clicks=0, timestamp=datetime.utcnow())
    db.session.add(click)
    db.session.commit()
    link = f"{request.host_url}{click_id}"
    return jsonify({'link': link, 'click_id': click_id})

@main.route('/<click_id>')
def click_redirect(click_id):
    click = Click.query.filter_by(click_id=click_id).first()
    if not click:
        return " invalid url ", 404

    user_agent = request.headers.get('User-Agent')
    ua = user_agent.lower() if user_agent else ''

    # --- New Hybrid Logic ---
    if 'android' in ua:
        # For Android, collect basic data on the server and redirect immediately.
        # This avoids the browser landing page to maximize referrer survival.
        
        # 1. Log the basic click event on the server.
        click_event = ClickEvent(
            click_id=click_id,
            timestamp=datetime.utcnow(),
            platform='android',
            ip_address=get_client_ip(request),
            user_agent=user_agent
        )
        db.session.add(click_event)
        click.total_clicks += 1
        db.session.commit()

        # 2. Build the simplified referrer URL with only the click_id.
        full_referrer = urllib.parse.quote(f"click_id={click_id}")
        redirect_url = f"{click.play_store_url}&referrer={full_referrer}"

        # 3. Redirect immediately from the server.
        return redirect(redirect_url, code=302)

    elif 'iphone' in ua or 'ipad' in ua:
        # For iOS, we MUST use the landing page to get a fingerprint.
        platform = 'ios'
        redirect_url = click.app_store_url
        return render_template('landing.html', redirect_url=redirect_url)
    
    else:
        # For Web and other platforms, use the landing page.
        platform = 'web'
        redirect_url = click.web_url
        return render_template('landing.html', redirect_url=redirect_url)

@main.route('/api/install', methods=['POST'])
def report_install():
    data = request.json
    click_id = data.get('click_id') # For Android
    install_id = str(uuid.uuid4())
    
    # Create the install record with the new push_token field
    install = Install(
        install_id=install_id, 
        click_id=click_id, 
        device_model=data.get('device_model'),
        os_version=data.get('os_version'),
        language=data.get('language'),
        timezone=data.get('timezone'),
        ip_address=get_client_ip(request),  # <-- updated here
        advertising_id=data.get('advertising_id'),
        push_token=data.get('push_token') # Store push_token
    )
    db.session.add(install)
    db.session.commit()
    return jsonify({'status': 'ok', 'install_id': install_id})

@main.route('/api/deeplink', methods=['POST'])
def get_deeplink():
    data = request.json
    install_id = data.get('install_id')
    install = Install.query.filter_by(install_id=install_id).first()
    if not install:
        return jsonify({'error': 'Invalid install_id'}), 404
    click = Click.query.filter_by(click_id=install.click_id).first()
    payload = {'campaign': click.campaign if click else None}
    return jsonify({'deeplink_payload': payload})

@main.route('/api/match_install', methods=['POST'])
def match_install():
    """
    Probabilistic matching endpoint for iOS with advanced scoring.
    The SDK sends device info, and this endpoint finds the best matching click.
    """
    sdk_data = request.json
    sdk_ip = get_client_ip(request)  # <-- updated here

    # Define a time window for matching (e.g., last 30 minutes)
    match_window_start = datetime.utcnow() - timedelta(minutes=30)

    # Find recent clicks from the same IP that don't have an install yet
    potential_clicks = db.session.query(ClickEvent).outerjoin(Install, ClickEvent.click_id == Install.click_id).filter(
        ClickEvent.ip_address == sdk_ip,
        ClickEvent.timestamp >= match_window_start,
        Install.id == None # Ensure the click hasn't been attributed yet
    ).all()

    if not potential_clicks:
        return jsonify({'status': 'no_match', 'reason': 'No recent clicks from this IP.'}), 404

    # --- Advanced Scoring Logic ---
    best_match = None
    highest_score = -1

    for click in potential_clicks:
        current_score = 0
        
        # Compare OS Version (high weight)
        if sdk_data.get('os_version') and click.os_version and sdk_data.get('os_version') == click.os_version:
            current_score += 3
            
        # Compare Language (medium weight, comparing base language e.g., 'en')
        sdk_lang = sdk_data.get('language', '').split('-')[0]
        click_lang = getattr(click, 'language', '').split('-')[0]
        if sdk_lang and click_lang and sdk_lang == click_lang:
            current_score += 2
            
        # Compare Timezone (medium weight)
        if sdk_data.get('timezone') and click.timezone and sdk_data.get('timezone') == click.timezone:
            current_score += 2
            
        # Compare Device Model (low weight, as it's inferred)
        if sdk_data.get('device_model') and click.device_model and sdk_data.get('device_model') == click.device_model:
            current_score += 1

        # If this click has the highest score so far, it's our new best match
        if current_score > highest_score:
            highest_score = current_score
            best_match = click

    # If no click scored high enough to be considered a match, exit.
    # A score of 0 means no data points matched. We require at least one match.
    if not best_match or highest_score == 0:
        return jsonify({'status': 'no_match', 'reason': 'No click fingerprint matched sufficiently.'}), 404
    # --- End of Scoring Logic ---

    # Create the install record and link it to the matched click
    install_id = str(uuid.uuid4())
    install = Install(
        install_id=install_id,
        click_id=best_match.click_id,
        device_model=sdk_data.get('device_model'),
        os_version=sdk_data.get('os_version'),
        language=sdk_data.get('language'),
        timezone=sdk_data.get('timezone'),
        ip_address=sdk_ip,  # <-- updated here
        advertising_id=sdk_data.get('advertising_id'),
        push_token=sdk_data.get('push_token') # Store push_token
    )
    db.session.add(install)
    db.session.commit()

    return jsonify({
        'status': 'ok', 
        'install_id': install_id, 
        'matched_click_id': best_match.click_id,
        'match_score': highest_score
    })

@main.route('/api/update_user', methods=['POST'])
def update_user():
    """
    Called by the SDK after user logs in or registers.
    Updates the install record with the user's phone number.
    """
    data = request.json
    install_id = data.get('install_id')
    phone_number = data.get('phone_number')

    if not install_id or not phone_number:
        return jsonify({'status': 'error', 'message': 'install_id and phone_number are required'}), 400

    install = Install.query.filter_by(install_id=install_id).first()
    if not install:
        return jsonify({'status': 'error', 'message': 'Invalid install_id'}), 404

    # Update the record with the phone number
    install.phone_number = phone_number
    db.session.commit()

    return jsonify({'status': 'ok', 'message': 'User data updated successfully.'})

@main.route('/<click_id>/collect', methods=['POST'])
def collect_landing_data(click_id):
    data = request.json
    click = Click.query.filter_by(click_id=click_id).first()
    if not click:
        return jsonify({'status': 'error', 'message': 'Invalid click_id'}), 404

    # Log the enriched click event
    click_event = ClickEvent(
        click_id=click_id,
        timestamp=datetime.utcnow(),
        platform=data.get('platform'),
        ip_address=get_client_ip(request),
        user_agent=data.get('user_agent'),
        language=data.get('language'),
        timezone=data.get('timezone'),
        screen_width=data.get('screen_width'),
        screen_height=data.get('screen_height'),
        device_model=data.get('device_model'),
        os_version=data.get('os_version')
    )
    db.session.add(click_event)
    # Increment total_clicks
    click.total_clicks += 1
    db.session.commit()
    return jsonify({'status': 'ok'})
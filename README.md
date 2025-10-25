# Deferred Deep Link System (Flask + MySQL)

## Overview
A Python Flask server for generating, tracking, and matching deferred deep links for mobile attribution.

## Features
- Generate campaign links with unique click IDs
- Log and redirect clicks based on platform
- API for app install/open event reporting
- Deep-link payload retrieval for apps
- MySQL database integration

## Setup
1. Copy `.env.example` to `.env` and fill in your MySQL credentials.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize the database (create tables):
   ```python
   from app import create_app, db
   app = create_app()
   with app.app_context():
       db.create_all()
   ```
4. Run the server:
   ```bash
   python run.py
   ```

## Endpoints
- `POST /generate_link` – Generate a new campaign link
- `GET /click/<click_id>` – Log click and redirect user
- `POST /api/install` – App reports install/open event
- `POST /api/deeplink` – App fetches deep-link payload

## Notes
- Replace placeholder URLs and app IDs in `routes.py` with your actual values.
- Secure your endpoints and use HTTPS in production.

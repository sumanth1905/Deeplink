from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
import urllib.parse

load_dotenv()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    password = urllib.parse.quote_plus(os.getenv('MYSQL_PASSWORD'))
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{password}@{os.getenv('MYSQL_HOST')}/{os.getenv('MYSQL_DB')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app

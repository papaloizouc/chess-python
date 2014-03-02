from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from web import config

api_app = Flask(__name__)
api_app.config.from_object(config)
api_db = SQLAlchemy(api_app)

from redis import Redis
redis = Redis(host='localhost', port=6379, db=0)

from api import application

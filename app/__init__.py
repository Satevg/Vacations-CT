from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager
from werkzeug.debug import DebuggedApplication

app = Flask(__name__)
app.wsgi_app = DebuggedApplication(app.wsgi_app, True)

app.config.from_object('config')
app.debug = True
db = SQLAlchemy(app)

lm = LoginManager()
lm.init_app(app)
lm.login_view = 'login'

from app import views, models

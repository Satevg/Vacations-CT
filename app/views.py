from flask import render_template, flash, redirect, url_for, request, session, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from app import app, db, lm, models
from oauth2client import client
import json


@app.before_request
def before_request():
    g.user = current_user


@lm.user_loader
def load_user(id):
    return models.User.query.get(int(id))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    if g.user is not None and g.user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('oauth2callback'))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/oauth2callback')
def oauth2callback():
    flow = client.flow_from_clientsecrets('client_secrets.json',
                                          scope='https://www.googleapis.com/auth/plus.profile.emails.read',
                                          redirect_uri='http://127.0.0.1:5000/oauth2callback')
    if 'code' not in request.args:
        auth_uri = flow.step1_get_authorize_url()
        return redirect(auth_uri)
    else:
        auth_code = request.args.get('code')
        credentials = json.loads(flow.step2_exchange(auth_code).to_json())
        if credentials:
            email = credentials['id_token']['email']
            if '@core-tech.ru' not in email:
                flash('Registration allowed from core-tech.ru email domain only!')
                return redirect(url_for('index'))
            user = models.User.query.filter_by(email=email).first()
            if not user:
                user = models.User(name='', email=email, role=models.ROLE_USER)
                db.session.add(user)
                db.session.commit()
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')
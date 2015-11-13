from flask import render_template, flash, redirect, url_for, request, session, g, make_response
from flask.ext.login import login_user, logout_user, current_user, login_required
from app import app, db, lm, models
from flask.ext.wtf import Form
from wtforms.ext.sqlalchemy.orm import model_form
from wtforms import validators
from oauth2client import client
from datetime import datetime, date
import json


@app.before_request
def before_request():
    g.user = current_user


@lm.user_loader
def load_user(id):
    return models.User.query.get(int(id))


@app.route('/')
def index():
    if g.user is not None and g.user.is_authenticated:
        return redirect(url_for('dashboard'))
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
    first_day = date(date.today().year, 1, 1)
    vacations_bulk = models.VacationItem.query.filter(models.VacationItem.start >= first_day)
    data = []
    for vacation in vacations_bulk:
        start = datetime.strftime(vacation.start, "%Y-%m-%dT%H:%M:%S")
        end = datetime.strftime(vacation.end, "%Y-%m-%dT%H:%M:%S")
        v = {
            'start': start,
            'end': end,
            'title': vacation.user.email.split('@')[0]
        }
        data.append(v)

    user_vacations = models.VacationItem.query.filter_by(user=current_user).all()
    return render_template('dashboard.html', events=json.dumps(data), u_v=user_vacations)


@app.route('/v_add', methods=['POST'])
@login_required
def add_vacation():
    event_data = request.form['event_data']
    if not event_data:
        return make_response('Wrong Data', 304)
    event_data = json.loads(event_data)
    start = datetime.strptime(event_data['start'], "%Y-%m-%dT%H:%M:%S.%fZ")
    end = datetime.strptime(event_data['end'], "%Y-%m-%dT%H:%M:%S.%fZ")
    v_item = models.VacationItem(description=event_data['title'], approved=False,
                                 start=start, end=end,
                                 user=current_user)
    db.session.add(v_item)
    db.session.commit()
    return 'success', 200


@app.route('/v_delete/<v_id>')
@login_required
def delete_vacation(v_id):
    vacation = models.VacationItem.query.filter_by(user=current_user, id=v_id).first_or_404()
    db.session.delete(vacation)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/v_edit/<v_id>')
@login_required
def edit_vacation(v_id):
    pass
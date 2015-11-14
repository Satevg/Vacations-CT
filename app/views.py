from app import app, db, lm, models
from flask import abort, render_template, flash, redirect, url_for, request, session, g, make_response
from flask.ext.login import login_user, logout_user, current_user, login_required
from oauth2client import client
from datetime import datetime, date, timedelta
import config
import json
import requests


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
    vacations_bulk = models.VacationItem.query.filter(models.VacationItem.start >= first_day).order_by(
        models.VacationItem.approved)
    data = []
    for vacation in vacations_bulk:
        start = datetime.strftime(vacation.start, "%Y-%m-%dT%H:%M:%S")
        end = datetime.strftime(vacation.end + timedelta(days=1), "%Y-%m-%dT%H:%M:%S")
        v = {
            'start': start,
            'end': end,
            'title': vacation.user.email.split('@')[0]
        }
        data.append(v)
    if not current_user.is_superuser():
        user_vacations = models.VacationItem.query.filter_by(user=current_user).order_by(models.VacationItem.approved)
    else:
        user_vacations = vacations_bulk
    return render_template('dashboard.html', events=json.dumps(data), u_v=user_vacations)


@app.route('/v_add', methods=['POST'])
@login_required
def add_vacation():
    event_data = request.form['event_data']
    if not event_data:
        abort(304)
    event_data = json.loads(event_data)
    start = datetime.strptime(event_data['start'], "%Y-%m-%dT%H:%M:%S.%fZ")
    end = datetime.strptime(event_data['end'], "%Y-%m-%dT%H:%M:%S.%fZ") - timedelta(days=1)
    v_item = models.VacationItem(description=event_data['title'], approved=False,
                                 start=start, end=end, user=current_user)
    db.session.add(v_item)
    db.session.commit()
    return 'success', 200


@app.route('/v_delete/<v_id>')
@login_required
def delete_vacation(v_id):
    if not current_user.is_superuser():
        vacation = models.VacationItem.query.filter_by(user=current_user, id=v_id).first_or_404()
    else:
        vacation = models.VacationItem.query.filter_by(id=v_id).first_or_404()
    db.session.delete(vacation)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/v_approve/<v_id>')
@login_required
def approve_vacation(v_id):
    if not current_user.is_superuser():
        abort(401)
    vacation = models.VacationItem.query.filter_by(id=v_id).first_or_404()
    vacation.approved = True
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/<secret>/notify')
def notify(secret):
    if secret != config.NOTIFY_SECRET:
        abort(401)
    unconfirmed_v = models.VacationItem.query.filter_by(approved=False) \
        .filter(models.VacationItem.start >= datetime.today())
    if unconfirmed_v.count() == 0:
        return ''
    send_message = False
    text = 'Vacations update: \n\n'
    for vacation in unconfirmed_v:
        delta = vacation.start - datetime.today()
        if delta.days < 14:
            send_message = True
            text += 'Hey, ' + vacation.user.email.split('@')[0] + '! Your Vacation still not approved (' + \
                    str(delta.days) + ' days remaining). Send this code to Ivan: ' + \
                    vacation.user.email.split('@')[0] + '_' + str(vacation.id) + '\n\n'
        else:
            continue
    if send_message:
        url = "https://api.telegram.org/bot%s/sendMessage" % config.TELEGRAM_BOT_TOKEN
        payload = {
            'chat_id': config.TELEGRAM_TARGET_CHANNEL,
            'text': text
        }
        headers = {'content-type': "application/x-www-form-urlencoded"}
        requests.request("POST", url, data=payload, headers=headers)
    return ''


@app.context_processor
def utility_processor():
    def get_username(email_string):
        return email_string.split('@')[0]

    def count(obj):
        num = True if obj.count() > 0 else False
        return num

    return dict(get_username=get_username, count=count)
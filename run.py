from flask import Flask, render_template, request, send_file
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.security import safe_join
import requests
import json
import time

app = Flask(__name__)
app.config['DEBUG'] = False

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

teams = []
cached_teams = None
last_request = None

with open('teams.txt', 'r') as file:
    if file.read().strip() == "":
        print("No teams specified in teams.txt, defaulting to all teams.")
        teams = None
    else:
        for line in file:
            team = line.strip()
            if team:
                teams.append(team)

def get_team_scores():
    global last_request, cached_teams
    if last_request and cached_teams:
        if (time.time() - last_request) < 60 and len(cached_teams) != 0:
            print("Using cached scores...")
            return cached_teams
    print("Fetching new scores from API...")
    last_request = time.time()
    url = "https://scoreboard.uscyberpatriot.org/api/team/scores.php"
    response = requests.get(url)
    if response.status_code == 200:
        scores = response.json()['data']
        only_relevant_scores = []
        if teams is None or len(teams) == 0:
            only_relevant_scores = scores
        else:
            for score in scores:
                if score['team_number'] in teams:
                    only_relevant_scores.append(score)
        cached_teams = only_relevant_scores
        return only_relevant_scores
    return {}

@app.route('/')
def index():
    host = request.host
    return render_template('index.html', teams=teams, host=host)

@app.route('/assets/<path:path>')
def send_asset(path):
    safe_path = safe_join('assets', path)
    if safe_path is None:
        return "Invalid path", 400
    return send_file(safe_path)

@socketio.on('get_teams')
def handle_get_scores():
    if teams is None or len(teams) == 0:
        emit('teams', [])
    else:
        emit('teams', teams)

@socketio.on('get_scores')
def handle_get_scores():
    global last_request
    scores = get_team_scores()
    emit('scores', scores)
    emit('updated', last_request)

@socketio.on('get_score_update')
def handle_get_score_update(current_scores):
    global last_request
    scores = get_team_scores()
    changed = False
    for score in scores:
        team_id = score['team_number']
        prev = next((s for s in current_scores if s['team_number'] == team_id), None)
        if prev and (score['play_time'] != prev['play_time'] or score['score_time'] != prev['score_time']):
            changed = True
            break
    if changed or len(current_scores) != len(scores):
        emit('scores', scores)
        emit('updated', last_request)
    else:
        emit('no_update', 'Nothing has changed.')
        emit('updated', last_request)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
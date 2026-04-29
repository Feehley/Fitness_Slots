#!/usr/bin/env python3
"""
FIT SPIN — Kiosk Server
Serves the slot machine (/) and admin portal (/admin).
Manages per-column exercise data and WiFi config.
Run as root on port 80 via systemd.
"""
import json, os, csv, io
from flask import Flask, jsonify, request, send_from_directory, abort, Response

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DATA_DIR   = os.path.join(BASE_DIR, 'data')
DATA_FILE  = os.path.join(DATA_DIR, 'exercises.json')
WIFI_FILE  = os.path.join(DATA_DIR, 'wifi.json')

app = Flask(__name__)

# ── DEFAULT EXERCISES (5 columns) ──────────────────────────────────────────────

DEFAULTS = [
    {
        "label": "Warm Up", "color": "#ff3cac",
        "exercises": [
            {"name": "Jumping Jacks",    "emoji": "⚡", "reps": "30 sec",  "image": ""},
            {"name": "High Knees",       "emoji": "🦵", "reps": "30 sec",  "image": ""},
            {"name": "Arm Circles",      "emoji": "🔄", "reps": "20 sec",  "image": ""},
            {"name": "Hip Circles",      "emoji": "🌀", "reps": "20 sec",  "image": ""},
            {"name": "Butt Kicks",       "emoji": "🏃", "reps": "30 sec",  "image": ""},
            {"name": "Leg Swings",       "emoji": "🦿", "reps": "10 each", "image": ""},
        ]
    },
    {
        "label": "Upper Body", "color": "#ff6b35",
        "exercises": [
            {"name": "Push-Ups",       "emoji": "💪", "reps": "20 reps", "image": ""},
            {"name": "Pull-Ups",       "emoji": "🎯", "reps": "8 reps",  "image": ""},
            {"name": "Shoulder Press", "emoji": "🏋️", "reps": "12 reps", "image": ""},
            {"name": "Bicep Curls",    "emoji": "💪", "reps": "15 reps", "image": ""},
            {"name": "Tricep Dips",    "emoji": "👐", "reps": "12 reps", "image": ""},
            {"name": "Chest Fly",      "emoji": "🦅", "reps": "12 reps", "image": ""},
        ]
    },
    {
        "label": "Lower Body", "color": "#00f5d4",
        "exercises": [
            {"name": "Squats",      "emoji": "🦵", "reps": "15 reps", "image": ""},
            {"name": "Lunges",      "emoji": "🏃", "reps": "12 each", "image": ""},
            {"name": "Box Jumps",   "emoji": "📦", "reps": "10 reps", "image": ""},
            {"name": "Deadlifts",   "emoji": "🏋️", "reps": "8 reps",  "image": ""},
            {"name": "Calf Raises", "emoji": "👟", "reps": "25 reps", "image": ""},
            {"name": "Wall Sit",    "emoji": "🧘", "reps": "45 sec",  "image": ""},
        ]
    },
    {
        "label": "Core", "color": "#fee440",
        "exercises": [
            {"name": "Plank",             "emoji": "🧱", "reps": "60 sec",  "image": ""},
            {"name": "Bicycle Crunches",  "emoji": "🚴", "reps": "25 reps", "image": ""},
            {"name": "Mountain Climbers", "emoji": "🏔️", "reps": "20 reps", "image": ""},
            {"name": "Russian Twist",     "emoji": "🌀", "reps": "20 reps", "image": ""},
            {"name": "Leg Raises",        "emoji": "🦵", "reps": "15 reps", "image": ""},
            {"name": "V-Ups",             "emoji": "✌️", "reps": "12 reps", "image": ""},
        ]
    },
    {
        "label": "Cardio", "color": "#9b5de5",
        "exercises": [
            {"name": "Burpees",      "emoji": "🔥", "reps": "10 reps", "image": ""},
            {"name": "Jump Rope",    "emoji": "🪢", "reps": "60 sec",  "image": ""},
            {"name": "Battle Ropes", "emoji": "💥", "reps": "30 sec",  "image": ""},
            {"name": "Sprint",       "emoji": "🏅", "reps": "20 sec",  "image": ""},
            {"name": "Rowing",       "emoji": "🚣", "reps": "2 min",   "image": ""},
            {"name": "Bike Sprint",  "emoji": "🚴", "reps": "60 sec",  "image": ""},
        ]
    },
]

DEFAULT_WIFI = {"ssid": "FITSPIN-ADMIN", "password": "FitSpin2024", "ip": "10.0.0.1"}

# ── DATA HELPERS ───────────────────────────────────────────────────────────────

def load_data():
    try:
        with open(DATA_FILE, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, list) and len(d) == 5:
            return d
    except Exception:
        pass
    return [dict(c) for c in DEFAULTS]

def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_wifi():
    try:
        with open(WIFI_FILE) as f:
            return json.load(f)
    except Exception:
        return dict(DEFAULT_WIFI)

def save_wifi(d):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(WIFI_FILE, 'w') as f:
        json.dump(d, f, indent=2)

def clean_exercise(e, i=None):
    n = str(e.get('name', '')).strip()[:40]
    if not n:
        return None
    return {
        'name':  n,
        'emoji': str(e.get('emoji', '💪')).strip() or '💪',
        'reps':  str(e.get('reps',  '')).strip()[:25],
        'image': str(e.get('image', '')).strip()[:250],
    }

# ── ROUTES ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory(STATIC_DIR, 'admin.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)

# ── EXERCISE API ────────────────────────────────────────────────────────────────

@app.route('/api/exercises')
def get_exercises():
    return jsonify(load_data())

@app.route('/api/column/<int:col>', methods=['POST'])
def update_column(col):
    if not 0 <= col <= 4:
        abort(400)
    data = load_data()
    body = request.get_json(silent=True)
    if not body:
        abort(400)
    if 'label' in body:
        data[col]['label'] = str(body['label'])[:30]
    if 'color' in body:
        c = str(body['color']).strip()
        if c.startswith('#') and len(c) in (4, 7):
            data[col]['color'] = c
    if 'exercises' in body:
        exs = [clean_exercise(e) for e in body.get('exercises', [])]
        data[col]['exercises'] = [e for e in exs if e]
    save_data(data)
    return jsonify({'ok': True})

@app.route('/api/column/<int:col>/upload', methods=['POST'])
def upload_csv(col):
    if not 0 <= col <= 4:
        abort(400)

    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'error': 'No file'}), 400

    try:
        text = f.stream.read().decode('utf-8-sig')
    except Exception:
        return jsonify({'ok': False, 'error': 'Cannot decode file — use UTF-8'}), 400

    reader      = csv.DictReader(io.StringIO(text))
    raw_hdrs    = reader.fieldnames or []
    lc_hdrs     = [h.lower().strip() for h in raw_hdrs]

    def find(*kws):
        for i, h in enumerate(lc_hdrs):
            if any(k in h for k in kws):
                return raw_hdrs[i]
        return None

    nc = find('name', 'exercise', 'workout', 'move')
    ec = find('emoji', 'icon', 'symbol')
    rc = find('rep', 'set', 'dur', 'count', 'time', 'sec', 'min', 'amount')
    ic = find('image', 'img', 'url', 'photo', 'pic', 'src')

    if not nc:
        return jsonify({'ok': False, 'error': 'Need a "name" or "exercise" column'}), 400

    exs = []
    for row in reader:
        n = row.get(nc, '').strip()
        if not n:
            continue
        exs.append({
            'name':  n[:40],
            'emoji': (row.get(ec, '') if ec else '').strip() or '💪',
            'reps':  (row.get(rc, '') if rc else '').strip()[:25],
            'image': (row.get(ic, '') if ic else '').strip()[:250],
        })

    if not exs:
        return jsonify({'ok': False, 'error': 'No exercises found'}), 400

    data = load_data()
    data[col]['exercises'] = exs
    save_data(data)
    return jsonify({'ok': True, 'count': len(exs)})

@app.route('/api/column/<int:col>/download')
def download_csv(col):
    if not 0 <= col <= 4:
        abort(400)
    data  = load_data()
    cd    = data[col]
    buf   = io.StringIO()
    w     = csv.writer(buf)
    w.writerow(['name', 'emoji', 'reps', 'image'])
    for e in cd['exercises']:
        w.writerow([e['name'], e['emoji'], e['reps'], e['image']])
    label = cd['label'].replace(' ', '_')
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=col{col+1}_{label}.csv'}
    )

@app.route('/api/reset', methods=['POST'])
def reset_defaults():
    save_data([dict(c) for c in DEFAULTS])
    return jsonify({'ok': True})

# ── WIFI API ───────────────────────────────────────────────────────────────────

@app.route('/api/wifi')
def get_wifi():
    return jsonify(load_wifi())

@app.route('/api/wifi', methods=['POST'])
def set_wifi():
    body = request.get_json(silent=True)
    if not body:
        abort(400)
    wifi = load_wifi()
    if 'ssid'     in body: wifi['ssid']     = str(body['ssid'])[:32]
    if 'password' in body: wifi['password'] = str(body['password'])[:63]
    save_wifi(wifi)
    # Apply changes to hostapd config and restart
    try:
        _apply_wifi(wifi['ssid'], wifi['password'])
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    return jsonify({'ok': True, 'note': 'WiFi updated — reconnect with new credentials'})

def _apply_wifi(ssid, password):
    """Rewrite /etc/hostapd/hostapd.conf and restart the service."""
    import subprocess
    conf = (
        f"interface=wlan0\ndriver=nl80211\nssid={ssid}\n"
        f"hw_mode=g\nchannel=6\nieee80211n=1\nwmm_enabled=1\n"
        f"macaddr_acl=0\nauth_algs=1\nignore_broadcast_ssid=0\n"
        f"wpa=2\nwpa_passphrase={password}\nwpa_key_mgmt=WPA-PSK\n"
        f"rsn_pairwise=CCMP\n"
    )
    with open('/etc/hostapd/hostapd.conf', 'w') as f:
        f.write(conf)
    subprocess.run(['systemctl', 'restart', 'hostapd'], check=True)

# ── ENTRY ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"FIT SPIN server → http://0.0.0.0:80")
    app.run(host='0.0.0.0', port=80, debug=False, threaded=True)

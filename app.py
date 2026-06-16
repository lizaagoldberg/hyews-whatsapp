from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import json

app = Flask(__name__)

# ── Twilio config ─────────────────────────────────────────────────────────────
TWILIO_SID   = os.environ.get('TWILIO_SID')
TWILIO_TOKEN = os.environ.get('TWILIO_TOKEN')
TWILIO_FROM  = os.environ.get('TWILIO_FROM', 'whatsapp:+14155238886')

# ── Decision tree ─────────────────────────────────────────────────────────────
# Each node: { text, options: {key: (label, next_node)} }
# Terminal nodes have 'outcome' instead of 'options'

TREE = {
    'start': {
        'text': 'Hy-EWS Flood Reporter\n\nAre you interested in reporting your conditions on the ground?\n\n1. Yes\n2. No',
        'options': {'1': ('Yes', 'flooding_now'), 'yes': ('Yes', 'flooding_now'), '2': ('No', 'outcome_clear'), 'no': ('No', 'outcome_clear')}
    },
    'flooding_now': {
        'text': 'Are you experiencing flooding right now?\n\n1. Yes\n2. No',
        'options': {'1': ('Yes', 'water_depth'), 'yes': ('Yes', 'water_depth'), '2': ('No', 'no_flood'), 'no': ('No', 'no_flood')}
    },
    'no_flood': {
        'text': 'Are you in a safe location?\n\n1. Yes, I am safe\n2. Not sure',
        'options': {'1': ('Yes', 'outcome_clear'), 'yes': ('Yes', 'outcome_clear'), '2': ('Not sure', 'water_depth'), 'not sure': ('Not sure', 'water_depth')}
    },
    'water_depth': {
        'text': 'How deep is the water around you?\n\n1. Waist deep or more\n2. Knee deep\n3. Ankle deep\n4. Below ankle',
        'options': {
            '1': ('Waist deep', 'water_rising'), 'waist': ('Waist deep', 'water_rising'),
            '2': ('Knee deep', 'water_rising'), 'knee': ('Knee deep', 'water_rising'),
            '3': ('Ankle deep', 'water_rising'), 'ankle': ('Ankle deep', 'water_rising'),
            '4': ('Below ankle', 'water_rising'), 'below': ('Below ankle', 'water_rising')
        },
        'meta': {'1': {'depthLevel': 4}, '2': {'depthLevel': 3}, '3': {'depthLevel': 2}, '4': {'depthLevel': 1}}
    },
    'water_rising': {
        'text': 'Is the water currently rising?\n\n1. It is rising\n2. It is stable\n3. It is falling',
        'options': {
            '1': ('Rising', 'water_type'), 'rising': ('Rising', 'water_type'),
            '2': ('Stable', 'water_type'), 'stable': ('Stable', 'water_type'),
            '3': ('Falling', 'water_type'), 'falling': ('Falling', 'water_type')
        },
        'meta': {'1': {'rising': 'rising'}, '2': {'rising': 'stable'}, '3': {'rising': 'falling'}}
    },
    'water_type': {
        'text': 'What does the water look like?\n\n1. Fast moving\n2. Slow moving\n3. Still water',
        'options': {
            '1': ('Fast moving', 'advice_fast'), 'fast': ('Fast moving', 'advice_fast'),
            '2': ('Slow moving', 'advice_slow'), 'slow': ('Slow moving', 'advice_slow'),
            '3': ('Still water', 'advice_still'), 'still': ('Still water', 'advice_still')
        }
    },
    'advice_fast': {
        'text': 'SAFETY: Even shallow fast water can knock you down. If you must cross, hold onto a fixed structure and move slowly sideways.\n\nReply anything to continue.',
        'options': {'*': ('OK', 'missing_items')}
    },
    'advice_slow': {
        'text': 'SAFETY: Use a stick to check the ground before each step. Avoid drains and road edges — they may be deeper than they look.\n\nReply anything to continue.',
        'options': {'*': ('OK', 'missing_items')}
    },
    'advice_still': {
        'text': 'SAFETY: Use a stick to check the ground before each step. Avoid drains and road edges — they may be deeper than they look.\n\nReply anything to continue.',
        'options': {'*': ('OK', 'missing_items')}
    },
    'missing_items': {
        'text': 'What are you currently missing? Reply with numbers separated by commas (e.g. "1,3"):\n\n1. Clean water\n2. Food\n3. Toilet\n4. Nothing — I have what I need',
        'options': {'*': ('items', 'shelter_interest')}  # catch-all, parsed separately
    },
    'shelter_interest': {
        'text': 'Are you interested in going to a shelter?\n\n1. Yes\n2. No',
        'options': {
            '1': ('Yes', 'shelter_info'), 'yes': ('Yes', 'shelter_info'),
            '2': ('No', 'photo_prompt'), 'no': ('No', 'photo_prompt')
        }
    },
    'shelter_info': {
        'text': 'Nearest shelters (Dhaka area):\n\n1. Korail Cyclone Shelter — 1.2 km\n2. Mirpur DNCC Shelter — 2.4 km\n3. Badda Govt School — 3.1 km\n\nShare your location in WhatsApp for exact directions.\n\nReply anything to continue.',
        'options': {'*': ('OK', 'photo_prompt')}
    },
    'photo_prompt': {
        'text': 'Would you like to send a photo of the flooding to share with aid agencies?\n\n1. Yes — send your photo now\n2. No, skip',
        'options': {
            '1': ('Yes', 'await_photo'), 'yes': ('Yes', 'await_photo'),
            '2': ('No', 'outcome_main'), 'no': ('No', 'outcome_main'),
            '*photo*': ('photo', 'outcome_main')
        }
    },
    'await_photo': {
        'text': 'Please send your photo now. Or reply "skip" to continue without a photo.',
        'options': {
            'skip': ('skip', 'outcome_main'),
            '*photo*': ('photo', 'outcome_main'),
            '*': ('waiting', 'await_photo')
        }
    },
    'outcome_main': {
        'outcome': True,
        'text': 'Report complete. Your information has been recorded and shared with coordinators. Stay safe.\n\nReply "restart" to submit a new report.'
    },
    'outcome_clear': {
        'outcome': True,
        'text': 'No flooding reported. Stay alert and report again if conditions change.\n\nReply "restart" to submit a new report.'
    }
}

def compute_outcome(session):
    depth = session.get('depthLevel', 1)
    rising = session.get('rising', 'stable')
    if depth >= 4: return 'red'
    if depth == 3 and rising == 'rising': return 'red'
    if depth == 3: return 'orange'
    if depth == 2 and rising == 'rising': return 'orange'
    if depth == 2: return 'yellow'
    if rising == 'rising': return 'yellow'
    return 'green'

# ── In-memory session store ───────────────────────────────────────────────────
# In production, replace with Redis or a database
sessions = {}

def get_session(phone):
    if phone not in sessions:
        sessions[phone] = {'node': 'start', 'answers': [], 'meta': {}}
    return sessions[phone]

def reset_session(phone):
    sessions[phone] = {'node': 'start', 'answers': [], 'meta': {}}
    return sessions[phone]

# ── Google Sheets logging ─────────────────────────────────────────────────────
def log_to_sheet(phone, outcome, answers, session):
    try:
        sheets_url = os.environ.get('SHEETS_URL')
        if not sheets_url:
            return
        import urllib.request
        data = json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'outcome': outcome,
            'language': 'en',
            'answers': ' → '.join(answers),
            'path': 'whatsapp',
            'phone': phone[-4:] + '****'  # partial anonymization
        }).encode()
        req = urllib.request.Request(sheets_url, data=data, headers={'Content-Type': 'text/plain'}, method='POST')
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f'Sheet log error: {e}')

# ── Webhook ───────────────────────────────────────────────────────────────────
@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '').strip().lower()
    num_media = int(request.form.get('NumMedia', 0))
    has_photo = num_media > 0

    resp = MessagingResponse()
    msg = resp.message()

    # Restart
    if body == 'restart':
        session = reset_session(from_number)
        node = TREE['start']
        msg.body(node['text'])
        return str(resp)

    session = get_session(from_number)
    current_node_id = session['node']
    node = TREE[current_node_id]

    # Terminal node — restart prompt
    if node.get('outcome'):
        msg.body('Reply "restart" to submit a new report.')
        return str(resp)

    options = node.get('options', {})

    # Photo handling
    if has_photo and current_node_id in ('photo_prompt', 'await_photo'):
        session['answers'].append('photo_sent')
        next_node_id = 'outcome_main'
        outcome = compute_outcome(session['meta'])
        log_to_sheet(from_number, outcome, session['answers'], session)
        session['node'] = next_node_id
        msg.body(TREE[next_node_id]['text'])
        return str(resp)

    # Missing items node — parse comma-separated numbers
    if current_node_id == 'missing_items':
        items_map = {'1': 'clean water', '2': 'food', '3': 'toilet', '4': 'none'}
        selected = [items_map[x.strip()] for x in body.split(',') if x.strip() in items_map]
        session['answers'].append(', '.join(selected) if selected else body)
        session['node'] = 'shelter_interest'
        msg.body(TREE['shelter_interest']['text'])
        return str(resp)

    # Wildcard catch-all nodes
    if '*' in options and body not in options:
        label, next_node_id = options['*']
        session['answers'].append(body)
    elif body in options:
        label, next_node_id = options[body]
        session['answers'].append(label)
        # Store meta
        if 'meta' in node and body in node['meta']:
            session['meta'].update(node['meta'][body])
    else:
        # Unrecognized input
        msg.body(f"Sorry, I did not understand. {node['text']}")
        return str(resp)

    # Check if next node is terminal
    next_node = TREE[next_node_id]
    if next_node.get('outcome'):
        outcome = compute_outcome(session['meta'])
        log_to_sheet(from_number, outcome, session['answers'], session)
        reset_session(from_number)

    session['node'] = next_node_id
    msg.body(next_node['text'])
    return str(resp)

@app.route('/', methods=['GET'])
def index():
    return 'Hy-EWS WhatsApp Bot is running.'

if __name__ == '__main__':
    app.run(debug=True, port=5000)


# ── IVR routes ────────────────────────────────────────────────────────────────
from ivr import register_ivr_routes
register_ivr_routes(app, sessions, reset_session, get_session, compute_outcome, log_to_sheet)

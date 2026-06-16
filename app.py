from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import os
import json
import urllib.request

app = Flask(__name__)

SHEETS_URL = os.environ.get('SHEETS_URL')

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
        'text': 'Are you in a safe location?\n\n1. Yes\n2. Not sure',
        'options': {'1': ('Yes', 'outcome_clear'), 'yes': ('Yes', 'outcome_clear'), '2': ('Not sure', 'water_depth')}
    },
    'water_depth': {
        'text': 'How deep is the water around you?\n\n1. Waist deep or more\n2. Knee deep\n3. Ankle deep\n4. Below ankle',
        'options': {
            '1': ('Waist deep', 'water_rising'), '2': ('Knee deep', 'water_rising'),
            '3': ('Ankle deep', 'water_rising'), '4': ('Below ankle', 'water_rising')
        },
        'meta': {'1': {'depthLevel': 4}, '2': {'depthLevel': 3}, '3': {'depthLevel': 2}, '4': {'depthLevel': 1}}
    },
    'water_rising': {
        'text': 'Is the water currently rising?\n\n1. Rising\n2. Stable\n3. Falling',
        'options': {'1': ('Rising', 'water_type'), '2': ('Stable', 'water_type'), '3': ('Falling', 'water_type')},
        'meta': {'1': {'rising': 'rising'}, '2': {'rising': 'stable'}, '3': {'rising': 'falling'}}
    },
    'water_type': {
        'text': 'What does the water look like?\n\n1. Fast moving\n2. Slow moving\n3. Still',
        'options': {'1': ('Fast', 'advice_fast'), '2': ('Slow', 'advice_slow'), '3': ('Still', 'advice_still')}
    },
    'advice_fast': {
        'text': 'SAFETY: Even shallow fast water can knock you down. Hold onto a fixed structure and move slowly sideways.\n\nReply anything to continue.',
        'options': {'*': ('OK', 'missing_items')}
    },
    'advice_slow': {
        'text': 'SAFETY: Use a stick to check the ground before each step. Avoid drains and road edges.\n\nReply anything to continue.',
        'options': {'*': ('OK', 'missing_items')}
    },
    'advice_still': {
        'text': 'SAFETY: Use a stick to check the ground before each step. Avoid drains and road edges.\n\nReply anything to continue.',
        'options': {'*': ('OK', 'missing_items')}
    },
    'missing_items': {
        'text': 'What are you missing? Reply numbers separated by commas:\n\n1. Clean water\n2. Food\n3. Toilet\n4. Nothing',
        'options': {'*': ('items', 'shelter_interest')}
    },
    'shelter_interest': {
        'text': 'Are you interested in going to a shelter?\n\n1. Yes\n2. No',
        'options': {'1': ('Yes', 'shelter_info'), 'yes': ('Yes', 'shelter_info'), '2': ('No', 'photo_prompt'), 'no': ('No', 'photo_prompt')}
    },
    'shelter_info': {
        'text': 'Nearest shelters:\n\n1. Korail Cyclone Shelter - 1.2 km\n2. Mirpur DNCC Shelter - 2.4 km\n3. Badda Govt School - 3.1 km\n\nReply anything to continue.',
        'options': {'*': ('OK', 'photo_prompt')}
    },
    'photo_prompt': {
        'text': 'Would you like to send a photo of the flooding?\n\n1. Yes\n2. No',
        'options': {'1': ('Yes', 'await_photo'), 'yes': ('Yes', 'await_photo'), '2': ('No', 'outcome_main'), 'no': ('No', 'outcome_main')}
    },
    'await_photo': {
        'text': 'Please send your photo now, or reply "skip" to finish.',
        'options': {'skip': ('skip', 'outcome_main'), '*': ('waiting', 'await_photo')}
    },
    'outcome_main': {
        'outcome': True,
        'text': 'Report complete. Your information has been recorded. Stay safe.\n\nReply "restart" to submit a new report.'
    },
    'outcome_clear': {
        'outcome': True,
        'text': 'No flooding reported. Stay alert.\n\nReply "restart" to submit a new report.'
    }
}

def compute_outcome(meta):
    depth = meta.get('depthLevel', 1)
    rising = meta.get('rising', 'stable')
    if depth >= 4: return 'red'
    if depth == 3 and rising == 'rising': return 'red'
    if depth == 3: return 'orange'
    if depth == 2 and rising == 'rising': return 'orange'
    if depth == 2: return 'yellow'
    if rising == 'rising': return 'yellow'
    return 'green'

sessions = {}

def get_session(phone):
    if phone not in sessions:
        sessions[phone] = {'node': 'start', 'answers': [], 'meta': {}}
    return sessions[phone]

def reset_session(phone):
    sessions[phone] = {'node': 'start', 'answers': [], 'meta': {}}
    return sessions[phone]

def log_to_sheet(phone, outcome, answers):
    if not SHEETS_URL:
        return
    try:
        data = json.dumps({
            'timestamp': datetime.utcnow().isoformat(),
            'outcome': outcome,
            'language': 'en',
            'answers': ' -> '.join(answers),
            'path': 'whatsapp',
            'phone': '****' + phone[-4:]
        }).encode()
        req = urllib.request.Request(SHEETS_URL, data=data, headers={'Content-Type': 'text/plain'}, method='POST')
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f'Sheet log error: {e}')

@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From', '')
    body = request.form.get('Body', '').strip().lower()
    num_media = int(request.form.get('NumMedia', 0))

    resp = MessagingResponse()
    msg = resp.message()

    if body == 'restart':
        reset_session(from_number)
        msg.body(TREE['start']['text'])
        return str(resp)

    session = get_session(from_number)
    node_id = session['node']
    node = TREE[node_id]

    if node.get('outcome'):
        msg.body('Reply "restart" to submit a new report.')
        return str(resp)

    if num_media > 0 and node_id in ('photo_prompt', 'await_photo'):
        session['answers'].append('photo_sent')
        outcome = compute_outcome(session['meta'])
        log_to_sheet(from_number, outcome, session['answers'])
        reset_session(from_number)
        msg.body(TREE['outcome_main']['text'])
        return str(resp)

    if node_id == 'missing_items':
        items_map = {'1': 'clean water', '2': 'food', '3': 'toilet', '4': 'none'}
        selected = [items_map[x.strip()] for x in body.split(',') if x.strip() in items_map]
        session['answers'].append(', '.join(selected) if selected else body)
        session['node'] = 'shelter_interest'
        msg.body(TREE['shelter_interest']['text'])
        return str(resp)

    options = node.get('options', {})

    if body in options:
        label, next_id = options[body]
        session['answers'].append(label)
        if 'meta' in node and body in node['meta']:
            session['meta'].update(node['meta'][body])
    elif '*' in options:
        label, next_id = options['*']
        session['answers'].append(body)
    else:
        msg.body(f'Please reply with one of the numbered options.\n\n{node["text"]}')
        return str(resp)

    next_node = TREE[next_id]
    if next_node.get('outcome'):
        outcome = compute_outcome(session['meta'])
        log_to_sheet(from_number, outcome, session['answers'])
        reset_session(from_number)

    session['node'] = next_id
    msg.body(next_node['text'])
    return str(resp)

@app.route('/', methods=['GET'])
def index():
    return 'Hy-EWS WhatsApp Bot is running.'

from ivr import register_ivr_routes
register_ivr_routes(app, sessions, reset_session, get_session, compute_outcome, log_to_sheet)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

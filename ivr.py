from flask import request
from twilio.twiml.voice_response import VoiceResponse, Gather

# Bengali and English text for each node
IVR_TREE = {
    'lang_select': {
        'en': 'Welcome to the Hy-EWS flood reporting system. Press 1 for English. Press 2 for Bengali.',
        'bn': 'Welcome to the Hy-EWS flood reporting system. Press 1 for English. Press 2 for Bengali.'
    },
    'start': {
        'en': 'Are you interested in reporting your conditions on the ground and asking questions about flood response? Press 1 for Yes. Press 2 for No.',
        'bn': 'আপনি কি মাঠের পরিস্থিতি রিপোর্ট করতে এবং বন্যা প্রতিক্রিয়া সম্পর্কে প্রশ্ন করতে আগ্রহী? হ্যাঁর জন্য ১ চাপুন। না-র জন্য ২ চাপুন।',
        'options': {'1': 'flooding_now', '2': 'outcome_clear'}
    },
    'flooding_now': {
        'en': 'Are you experiencing flooding right now? Press 1 for Yes. Press 2 for No.',
        'bn': 'আপনি কি এখন বন্যার মুখোমুখি? হ্যাঁর জন্য ১ চাপুন। না-র জন্য ২ চাপুন।',
        'options': {'1': 'water_depth', '2': 'no_flood'}
    },
    'no_flood': {
        'en': 'Are you in a safe location? Press 1 for Yes. Press 2 if you are not sure.',
        'bn': 'আপনি কি নিরাপদ জায়গায় আছেন? হ্যাঁর জন্য ১ চাপুন। নিশ্চিত না হলে ২ চাপুন।',
        'options': {'1': 'outcome_clear', '2': 'water_depth'}
    },
    'water_depth': {
        'en': 'How deep is the water around you? Press 1 for waist deep or more. Press 2 for knee deep. Press 3 for ankle deep. Press 4 for below ankle.',
        'bn': 'আপনার চারপাশে পানি কতটা গভীর? কোমর পর্যন্ত বা বেশির জন্য ১ চাপুন। হাঁটু পর্যন্তের জন্য ২ চাপুন। গোড়ালি পর্যন্তের জন্য ৩ চাপুন। গোড়ালির নিচের জন্য ৪ চাপুন।',
        'options': {'1': 'water_rising', '2': 'water_rising', '3': 'water_rising', '4': 'water_rising'},
        'meta': {'1': {'depthLevel': 4}, '2': {'depthLevel': 3}, '3': {'depthLevel': 2}, '4': {'depthLevel': 1}}
    },
    'water_rising': {
        'en': 'Is the water currently rising? Press 1 if it is rising. Press 2 if it is stable. Press 3 if it is falling.',
        'bn': 'পানি কি এখন বাড়ছে? বাড়ছে হলে ১ চাপুন। স্থির থাকলে ২ চাপুন। কমছে হলে ৩ চাপুন।',
        'options': {'1': 'water_type', '2': 'water_type', '3': 'water_type'},
        'meta': {'1': {'rising': 'rising'}, '2': {'rising': 'stable'}, '3': {'rising': 'falling'}}
    },
    'water_type': {
        'en': 'What does the water look like? Press 1 for fast moving water. Press 2 for slow moving water. Press 3 for still water.',
        'bn': 'পানি দেখতে কেমন? দ্রুত প্রবাহিত পানির জন্য ১ চাপুন। ধীরে প্রবাহিত পানির জন্য ২ চাপুন। স্থির পানির জন্য ৩ চাপুন।',
        'options': {'1': 'advice_fast', '2': 'advice_slow', '3': 'advice_still'}
    },
    'advice_fast': {
        'en': 'Safety advice. Even shallow fast water can knock you down. If you must cross, hold onto a fixed structure and move slowly sideways. Press any key to continue.',
        'bn': 'নিরাপত্তা পরামর্শ। অগভীর দ্রুত পানিও আপনাকে ফেলে দিতে পারে। পার হতে হলে কোনো স্থির কাঠামো ধরে আস্তে আস্তে পাশে সরুন। যেকোনো বোতাম চাপুন।',
        'options': {'*': 'missing_items'}
    },
    'advice_slow': {
        'en': 'Safety advice. Use a stick or pole to check the ground before each step. Move slowly. Avoid drains, ditches, and road edges. Press any key to continue.',
        'bn': 'নিরাপত্তা পরামর্শ। প্রতিটি পদক্ষেপের আগে লাঠি দিয়ে মাটি পরীক্ষা করুন। আস্তে যান। ড্রেন ও রাস্তার কিনারা এড়িয়ে চলুন। যেকোনো বোতাম চাপুন।',
        'options': {'*': 'missing_items'}
    },
    'advice_still': {
        'en': 'Safety advice. Use a stick or pole to check the ground before each step. Move slowly. Avoid drains, ditches, and road edges. Press any key to continue.',
        'bn': 'নিরাপত্তা পরামর্শ। প্রতিটি পদক্ষেপের আগে লাঠি দিয়ে মাটি পরীক্ষা করুন। আস্তে যান। ড্রেন ও রাস্তার কিনারা এড়িয়ে চলুন। যেকোনো বোতাম চাপুন।',
        'options': {'*': 'missing_items'}
    },
    'missing_items': {
        'en': 'What are you currently missing? Press 1 for clean water. Press 2 for food. Press 3 for toilet. Press 4 if you have everything you need.',
        'bn': 'আপনার কাছে এখন কী নেই? বিশুদ্ধ পানির জন্য ১ চাপুন। খাবারের জন্য ২ চাপুন। টয়লেটের জন্য ৩ চাপুন। সব আছে হলে ৪ চাপুন।',
        'options': {'1': 'shelter_interest', '2': 'shelter_interest', '3': 'shelter_interest', '4': 'shelter_interest'},
        'meta': {
            '1': {'missing': 'clean water'}, '2': {'missing': 'food'},
            '3': {'missing': 'toilet'}, '4': {'missing': 'none'}
        }
    },
    'shelter_interest': {
        'en': 'Are you interested in going to a shelter? Press 1 for Yes. Press 2 for No.',
        'bn': 'আপনি কি আশ্রয়কেন্দ্রে যেতে আগ্রহী? হ্যাঁর জন্য ১ চাপুন। না-র জন্য ২ চাপুন।',
        'options': {'1': 'shelter_info', '2': 'outcome_main'}
    },
    'shelter_info': {
        'en': 'The nearest shelters are: Korail Cyclone Shelter, 1 point 2 kilometers away. Mirpur DNCC Shelter, 2 point 4 kilometers away. Badda Government School, 3 point 1 kilometers away. Press any key to finish your report.',
        'bn': 'নিকটস্থ আশ্রয়কেন্দ্রগুলো হলো: করাইল সাইক্লোন শেল্টার, ১ দশমিক ২ কিলোমিটার দূরে। মিরপুর ডিএনসিসি শেল্টার, ২ দশমিক ৪ কিলোমিটার দূরে। বাড্ডা সরকারি বিদ্যালয়, ৩ দশমিক ১ কিলোমিটার দূরে। রিপোর্ট শেষ করতে যেকোনো বোতাম চাপুন।',
        'options': {'*': 'outcome_main'}
    },
    'outcome_main': {
        'en': 'Report complete. Your information has been recorded and will be shared with coordinators. Thank you for reporting. Stay safe. Goodbye.',
        'bn': 'রিপোর্ট সম্পন্ন। আপনার তথ্য রেকর্ড করা হয়েছে এবং সমন্বয়কারীদের সাথে শেয়ার করা হবে। রিপোর্টের জন্য ধন্যবাদ। নিরাপদ থাকুন। বিদায়।',
        'outcome': True
    },
    'outcome_clear': {
        'en': 'No flooding reported. Stay alert and call again if conditions change. Thank you. Goodbye.',
        'bn': 'কোনো বন্যা রিপোর্ট হয়নি। সতর্ক থাকুন এবং পরিস্থিতি পরিবর্তন হলে আবার ফোন করুন। ধন্যবাদ। বিদায়।',
        'outcome': True
    },
    'no_input': {
        'en': 'Sorry, I did not receive any input. Please try again.',
        'bn': 'দুঃখিত, কোনো ইনপুট পাওয়া যায়নি। অনুগ্রহ করে আবার চেষ্টা করুন।'
    }
}

LANG_CODES = {'en': 'en-US', 'bn': 'bn-BD'}

def say(response, text, lang):
    """Add a Say verb with the correct language."""
    response.say(text, language=LANG_CODES.get(lang, 'en-US'), voice='Polly.Joanna' if lang == 'en' else 'Polly.Aditi')

def gather_and_say(text, lang, action, num_digits=1, timeout=8):
    """Create a Gather with Say inside."""
    resp = VoiceResponse()
    gather = Gather(num_digits=num_digits, action=action, timeout=timeout, method='POST')
    gather.say(text, language=LANG_CODES.get(lang, 'en-US'),
               voice='Polly.Joanna' if lang == 'en' else 'Polly.Aditi')
    resp.append(gather)
    # If no input received
    resp.redirect(action + '?no_input=1')
    return str(resp)

def register_ivr_routes(app, sessions, reset_session, get_session, compute_outcome, log_to_sheet):

    @app.route('/ivr/start', methods=['GET', 'POST'])
    def ivr_start():
        """Entry point — language selection."""
        digit = request.form.get('Digits', '')
        from_number = request.form.get('From', request.form.get('Called', 'unknown'))

        if digit == '1':
            lang = 'en'
        elif digit == '2':
            lang = 'bn'
        else:
            # First call — present language choice
            return gather_and_say(
                IVR_TREE['lang_select']['en'],
                'en',
                action='/ivr/start',
                num_digits=1
            )

        session = reset_session(from_number)
        session['lang'] = lang
        session['node'] = 'start'
        node = IVR_TREE['start']
        return gather_and_say(node[lang], lang, action='/ivr/respond', num_digits=1)

    @app.route('/ivr/respond', methods=['POST'])
    def ivr_respond():
        from_number = request.form.get('From', request.form.get('Called', 'unknown'))
        digit = request.form.get('Digits', '').strip()
        no_input = request.args.get('no_input', '')

        session = get_session(from_number)
        lang = session.get('lang', 'en')
        node_id = session.get('node', 'start')
        node = IVR_TREE.get(node_id, IVR_TREE['start'])

        resp = VoiceResponse()

        # No input received
        if no_input or not digit:
            gather = Gather(num_digits=1, action='/ivr/respond', timeout=8, method='POST')
            gather.say(
                ('Sorry, I did not hear your selection. ' if lang == 'en' else 'দুঃখিত, আপনার নির্বাচন শুনতে পাইনি। ') + node[lang],
                language=LANG_CODES.get(lang, 'en-US'),
                voice='Polly.Joanna' if lang == 'en' else 'Polly.Aditi'
            )
            resp.append(gather)
            return str(resp)

        options = node.get('options', {})
        meta = node.get('meta', {})

        # Resolve next node
        if digit in options:
            next_id = options[digit]
        elif '*' in options:
            next_id = options['*']
        else:
            # Invalid key — repeat question
            return gather_and_say(
                ('Invalid selection. ' if lang == 'en' else 'ভুল নির্বাচন। ') + node[lang],
                lang, action='/ivr/respond', num_digits=1
            )

        # Store answer and meta
        session['answers'].append(digit)
        if digit in meta:
            session['meta'].update(meta[digit])

        session['node'] = next_id
        next_node = IVR_TREE.get(next_id)

        if not next_node:
            resp.say('An error occurred. Goodbye.', language='en-US')
            resp.hangup()
            return str(resp)

        # Terminal outcome
        if next_node.get('outcome'):
            outcome = compute_outcome(session['meta'])
            log_to_sheet(from_number, outcome, session['answers'])
            reset_session(from_number)
            say(resp, next_node[lang], lang)
            resp.hangup()
            return str(resp)

        # Next question
        return gather_and_say(next_node[lang], lang, action='/ivr/respond', num_digits=1)

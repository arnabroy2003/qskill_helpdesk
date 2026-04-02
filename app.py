import os
import requests
import httpx
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
from supabase import create_client, Client
from dotenv import load_dotenv

# 🔥 Load env
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'qskill_secret_key'

# 🔥 IMPORTANT FIX → threading mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# =========================
# 🔥 SUPABASE SETUP + DEBUG
# =========================

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print("\n====== ENV DEBUG ======")
print("RAW URL:", repr(url))
print("RAW KEY (partial):", repr(key[:20] if key else None))

# Clean values
if url:
    url = url.strip()
if key:
    key = key.strip()

print("CLEAN URL:", repr(url))

# 🔥 URL test
try:
    test_res = requests.get(url)
    print("URL TEST STATUS:", test_res.status_code)
except Exception as e:
    print("URL TEST FAILED:", str(e))

# 🔥 httpx FIX (VERY IMPORTANT)
try:
    http_client = httpx.Client(http2=False)
    supabase: Client = create_client(url, key, client=http_client)
    print("Supabase client initialized ✅")
except Exception as e:
    print("Supabase init FAILED ❌:", str(e))


ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


# =========================
# -------- ROUTES ---------
# =========================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    try:
        name = request.form.get('name')
        email = request.form.get('email')

        print("\n====== LOGIN DEBUG ======")
        print("LOGIN ATTEMPT:", name, email)

        print("Querying Supabase...")

        user_data = supabase.table('users').select("*").eq("email", email).execute()

        print("Supabase response:", user_data.data)

        if not user_data.data:
            print("User not found → inserting...")
            user_data = supabase.table('users').insert({
                "name": name,
                "email": email
            }).execute()
            print("Insert response:", user_data.data)

        user = user_data.data[0]

        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['role'] = 'student'

        print("Login SUCCESS ✅:", user['email'])

        return redirect(url_for('chat'))

    except Exception as e:
        print("LOGIN ERROR ❌:", str(e))
        return "Login Failed - Check Logs", 500


@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    try:
        history = supabase.table('messages') \
            .select("*") \
            .eq("user_id", session['user_id']) \
            .order("timestamp") \
            .execute()

        return render_template(
            'chat.html',
            history=history.data,
            name=session['user_name'],
            role=session.get('role')
        )

    except Exception as e:
        print("CHAT ERROR:", str(e))
        return "Chat load failed", 500


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['role'] = 'admin'
            return redirect(url_for('admin_panel'))
    return render_template('admin_login.html')


@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    try:
        users = supabase.table('users').select("*, messages(message, timestamp)").execute()
        return render_template('admin.html', users=users.data)

    except Exception as e:
        print("ADMIN ERROR:", str(e))
        return "Admin panel failed", 500


@app.route('/api/messages/<user_id>')
def get_messages(user_id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403

    try:
        response = supabase.table('messages') \
            .select("*") \
            .eq("user_id", user_id) \
            .order("timestamp", desc=False) \
            .execute()

        return jsonify(response.data)

    except Exception as e:
        print("API ERROR:", str(e))
        return jsonify({"error": "Server error"}), 500


# =========================
# 🔥 GLOBAL ERROR HANDLER
# =========================

@app.errorhandler(Exception)
def handle_exception(e):
    print("\n====== GLOBAL ERROR ======")
    print(str(e))
    return "Something broke! Check logs 😑", 500


# =========================
# ------- SOCKET ----------
# =========================

@socketio.on('join')
def on_join(data):
    try:
        room = data['room']
        print("JOIN ROOM:", room)
        join_room(room)
    except Exception as e:
        print("JOIN ERROR:", str(e))


@socketio.on('send_message')
def handle_message(data):
    try:
        room = data['room']
        msg_content = data['message']

        sender = session.get('role', 'student')

        print("NEW MESSAGE:", msg_content)

        supabase.table('messages').insert({
            "user_id": room,
            "sender": sender,
            "message": msg_content
        }).execute()

        emit('receive_message', {
            "message": msg_content,
            "sender": sender,
            "timestamp": "Just now"
        }, to=room)

    except Exception as e:
        print("SOCKET ERROR:", str(e))


# =========================
# -------- RUN ------------
# =========================

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False)
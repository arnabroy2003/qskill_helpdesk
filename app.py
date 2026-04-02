import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
from supabase import create_client, Client
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'qskill_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Supabase Setup
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print("RAW URL:", repr(url))
print("RAW KEY:", repr(key[:20] if key else None))  # full key print korish na 😑

if url:
    url = url.strip()
if key:
    key = key.strip()

print("CLEAN URL:", repr(url))

# 🔥 Test request BEFORE supabase client
try:
    test_res = requests.get(url)
    print("URL TEST STATUS:", test_res.status_code)
except Exception as e:
    print("URL TEST FAILED:", str(e))

supabase: Client = create_client(url, key)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    try:
        name = request.form.get('name')
        email = request.form.get('email')

        print("LOGIN ATTEMPT:", name, email)

        # 🔥 Supabase query debug
        print("Querying Supabase...")

        user_data = supabase.table('users').select("*").eq("email", email).execute()

        print("Supabase response:", user_data.data)

        if not user_data.data:
            print("User not found, inserting...")
            user_data = supabase.table('users').insert({
                "name": name,
                "email": email
            }).execute()
            print("Insert response:", user_data.data)

        user = user_data.data[0]

        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['role'] = 'student'

        print("Login success for:", user['email'])

        return redirect(url_for('chat'))

    except Exception as e:
        print("LOGIN ERROR:", str(e))
        return "Login Failed - Check Logs", 500

@app.route('/chat')
def chat():
    if 'user_id' not in session: return redirect(url_for('index'))
    # Fetch History
    history = supabase.table('messages').select("*").eq("user_id", session['user_id']).order("timestamp").execute()
    return render_template(
    'chat.html',
    history=history.data,
    name=session['user_name'],
    role=session.get('role')
)

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['role'] = 'admin'
            return redirect(url_for('admin_panel'))
    return render_template('admin_login.html')

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin': return redirect(url_for('admin_login'))
    # Get users with their last message
    users = supabase.table('users').select("*, messages(message, timestamp)").execute()
    return render_template('admin.html', users=users.data)

@app.route('/api/messages/<user_id>')
def get_messages(user_id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    # Fetch all messages for this user ordered by time
    response = supabase.table('messages') \
        .select("*") \
        .eq("user_id", user_id) \
        .order("timestamp", desc=False) \
        .execute()
    
    return jsonify(response.data)

@app.errorhandler(Exception)
def handle_exception(e):
    print("GLOBAL ERROR:", str(e))
    return "Something broke! Check logs 😑", 500

# --- SOCKET EVENTS ---

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    msg_content = data['message']
    
    # FIX: Get the role directly from the secure server session
    # If session['role'] isn't set, default to 'student'
    sender = session.get('role', 'student') 
    
    # Save to Supabase
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

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False)
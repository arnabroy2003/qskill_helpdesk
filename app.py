# import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
from supabase import create_client, Client
# from dotenv import load_dotenv

# load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'qskill_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Supabase Setup
# url = os.getenv("SUPABASE_URL")
# key = os.getenv("SUPABASE_KEY")

url = "https://rithbuogcwvjmzqoyrcj.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJpdGhidW9nY3d2am16cW95cmNqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM4MzUxOTUsImV4cCI6MjA4OTQxMTE5NX0.mo-8nz5oT9uFdlJR2GiRUmLWI9crNf5E8JQm3Oz0Kb4"

supabase: Client = create_client(url, key)

# ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
# ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

ADMIN_USERNAME = "tamasa@qskill.in"
ADMIN_PASSWORD = "Tamasa@2005"

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name')
    email = request.form.get('email')
    
    # Fetch or Create User
    user_data = supabase.table('users').select("*").eq("email", email).execute()
    if not user_data.data:
        user_data = supabase.table('users').insert({"name": name, "email": email}).execute()
    
    user = user_data.data[0]
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['role'] = 'student'
    
    return redirect(url_for('chat'))

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
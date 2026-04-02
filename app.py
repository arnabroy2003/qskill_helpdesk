import os
import uuid
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "qskill_secret_key")
socketio = SocketIO(app, cors_allowed_origins="*")

# --- GOOGLE SHEETS SETUP ---

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.getenv("GOOGLE_SHEETS_CREDS_JSON")
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    
    return gspread.authorize(creds)

client = get_gspread_client()
spreadsheet = client.open("help_desk")
sheet_users = spreadsheet.worksheet("users")
sheet_messages = spreadsheet.worksheet("messages")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# --- HELPERS ---

def get_all_records(worksheet):
    return worksheet.get_all_records()

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name')
    email = request.form.get('email')
    
    users = get_all_records(sheet_users)
    user = next((u for u in users if u['email'] == email), None)
    
    if not user:
        user_id = str(uuid.uuid4())[:8]
        sheet_users.append_row([user_id, name, email])
        user = {"id": user_id, "name": name, "email": email}
    
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['role'] = 'student'
    
    return redirect(url_for('chat'))

@app.route('/chat')
def chat():
    if 'user_id' not in session: return redirect(url_for('index'))
    
    all_msgs = get_all_records(sheet_messages)
    history = [m for m in all_msgs if str(m['user_id']) == str(session['user_id'])]
    
    return render_template('chat.html', history=history, name=session['user_name'], role=session.get('role'))

# --- HYBRID MESSAGE ROUTE (Fixed for Vercel) ---

@app.route('/api/send_message', methods=['POST'])
def handle_message_api():
    data = request.json
    room = data.get('room')
    msg_content = data.get('message')
    sender = session.get('role', 'student') 
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Standard HTTP write to Google Sheet
    sheet_messages.append_row([room, sender, msg_content, timestamp])
    
    # 2. Trigger Socket broadcast for real-time UI update
    socketio.emit('receive_message', {
        "message": msg_content,
        "sender": sender,
        "timestamp": "Just now"
    }, to=room)
    
    return jsonify({"status": "success"}), 200

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
    users = get_all_records(sheet_users)
    all_messages = get_all_records(sheet_messages)
    for user in users:
        user_msgs = [m for m in all_messages if str(m['user_id']) == str(user['id'])]
        user['messages'] = user_msgs[-1:] if user_msgs else []
    return render_template('admin.html', users=users)

@app.route('/api/messages/<user_id>')
def get_messages(user_id):
    if session.get('role') != 'admin': return jsonify({"error": "Unauthorized"}), 403
    all_msgs = get_all_records(sheet_messages)
    user_history = [m for m in all_msgs if str(m['user_id']) == str(user_id)]
    return jsonify(user_history)

# --- SOCKET EVENTS ---

@socketio.on('join')
def on_join(data):
    join_room(data['room'])

if __name__ == '__main__':
    socketio.run(app, debug=True)
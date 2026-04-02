import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'qskill_secret_key'

# 🔥 Socket fix
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# =========================
# 🔥 FAKE DATABASE (IN-MEMORY)
# =========================

users_db = []
messages_db = []

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

        print("\n====== LOGIN DEBUG (FAKE DB) ======")
        print("LOGIN ATTEMPT:", name, email)

        # 🔍 find user
        user = next((u for u in users_db if u['email'] == email), None)

        if not user:
            print("User not found → creating...")
            user = {
                "id": str(len(users_db) + 1),
                "name": name,
                "email": email
            }
            users_db.append(user)

        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['role'] = 'student'

        print("Login SUCCESS ✅:", user)

        return redirect(url_for('chat'))

    except Exception as e:
        print("LOGIN ERROR ❌:", str(e))
        return "Login Failed", 500


@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    try:
        user_messages = [m for m in messages_db if m['user_id'] == session['user_id']]

        return render_template(
            'chat.html',
            history=user_messages,
            name=session['user_name'],
            role=session.get('role')
        )

    except Exception as e:
        print("CHAT ERROR:", str(e))
        return "Chat load failed", 500


@app.route('/admin')
def admin_panel():
    return jsonify(users_db)


@app.route('/api/messages/<user_id>')
def get_messages(user_id):
    msgs = [m for m in messages_db if m['user_id'] == user_id]
    return jsonify(msgs)


# =========================
# ------- SOCKET ----------
# =========================

@socketio.on('join')
def on_join(data):
    room = data['room']
    print("JOIN ROOM:", room)
    join_room(room)


@socketio.on('send_message')
def handle_message(data):
    try:
        room = data['room']
        msg_content = data['message']
        sender = session.get('role', 'student')

        print("NEW MESSAGE:", msg_content)

        # 🔥 Save to fake DB
        msg = {
            "user_id": room,
            "sender": sender,
            "message": msg_content,
            "timestamp": "Just now"
        }
        messages_db.append(msg)

        emit('receive_message', msg, to=room)

    except Exception as e:
        print("SOCKET ERROR:", str(e))


# =========================
# -------- RUN ------------
# =========================

if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False)
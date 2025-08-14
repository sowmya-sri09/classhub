import os, json, sqlite3, datetime, random
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from config import DB_PATH

# --- Folders ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
MEME_DIR = os.path.join(STATIC_DIR, "memes")
os.makedirs(MEME_DIR, exist_ok=True)

# --- App ---
app = Flask(__name__)
app.config["SECRET_KEY"] = "classhub_secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# --- DB helper ---
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def nowts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------- PAGES ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/enter", methods=["POST"])
def enter():
    nickname = (request.form.get("nickname") or "").strip() or f"User{random.randint(100,999)}"
    team = (request.form.get("team") or "boys").strip().lower()
    role = (request.form.get("role") or "student").strip().lower()
    conn = db()
    try:
        conn.execute(
            "INSERT INTO users (nickname, team, role, points, joined_at) VALUES (?,?,?,?,?)",
            (nickname, team, role, 0, nowts()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # user already exists
    finally:
        conn.close()
    return redirect(url_for("dashboard", nickname=nickname))

@app.route("/dashboard")
def dashboard():
    nickname = request.args.get("nickname", "")
    conn = db()
    users = conn.execute(
        "SELECT nickname, team, points FROM users ORDER BY points DESC, nickname"
    ).fetchall()
    boys = conn.execute("SELECT COALESCE(SUM(points),0) FROM users WHERE team='boys'").fetchone()[0]
    girls = conn.execute("SELECT COALESCE(SUM(points),0) FROM users WHERE team='girls'").fetchone()[0]
    uploads = conn.execute("SELECT filename, uploader, ts FROM uploads ORDER BY ts DESC LIMIT 10").fetchall()
    conn.close()
    return render_template("dashboard.html", nickname=nickname, users=users, boys=boys, girls=girls, uploads=uploads)

@app.route("/polls")
def polls_page():
    nickname = request.args.get("nickname", "")
    conn = db()
    rows = conn.execute("SELECT id, question, options, votes FROM polls ORDER BY id DESC").fetchall()
    conn.close()
    polls = []
    for r in rows:
        polls.append({
            "id": r["id"],
            "question": r["question"],
            "options": json.loads(r["options"]),
            "votes": json.loads(r["votes"]),
        })
    return render_template("poll.html", nickname=nickname, polls=polls)

@app.route("/games")
def games():
    nickname = request.args.get("nickname", "")
    return render_template("game.html", nickname=nickname)

@app.route("/fake")
def fake():
    return render_template("fake_teacher.html")

# ---------- FEATURES ----------
@app.route("/mark-attendance", methods=["POST"])
def mark_attendance():
    nickname = request.form.get("nickname", "")
    session_name = request.form.get("session", "Lab Period")
    ts = nowts()
    conn = db()
    conn.execute("INSERT INTO attendance (nickname, session_name, timestamp) VALUES (?,?,?)",
                 (nickname, session_name, ts))
    conn.execute("UPDATE users SET points = points + 5 WHERE nickname=?", (nickname,))
    conn.commit()
    conn.close()
    socketio.emit("attendance-marked", {"nickname": nickname, "session": session_name, "ts": ts}, broadcast=True)
    return jsonify(ok=True, ts=ts)

@app.route("/export-attendance")
def export_attendance():
    conn = db()
    rows = conn.execute("SELECT nickname, session_name, timestamp FROM attendance ORDER BY timestamp DESC").fetchall()
    conn.close()
    csv = "nickname,session_name,timestamp\n" + "\n".join([f"{r['nickname']},{r['session_name']},{r['timestamp']}" for r in rows])
    return (csv, 200, {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=attendance.csv"})

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    nickname = request.form.get("nickname", "anon")
    if not f or not f.filename:
        return "No file", 400
    safe_name = f.filename  # (simple for lab use)
    path = os.path.join(MEME_DIR, safe_name)
    f.save(path)
    conn = db()
    conn.execute("INSERT INTO uploads (filename, uploader, ts) VALUES (?,?,?)", (safe_name, nickname, nowts()))
    conn.commit(); conn.close()
    socketio.emit("new-upload", {"filename": safe_name, "uploader": nickname, "ts": nowts()}, broadcast=True)
    return redirect(url_for("dashboard", nickname=nickname))

@app.route("/memes/<filename>")
def serve_meme(filename):
    return send_from_directory(MEME_DIR, filename)

# ---------- POLLS ----------
@app.route("/create-poll", methods=["POST"])
def create_poll():
    q = (request.form.get("question") or "").strip()
    opts = request.form.getlist("options")
    opts = [o for o in opts if o.strip()]
    if not q or len(opts) < 2:
        return redirect(url_for("polls_page"))
    votes = {str(i): 0 for i in range(len(opts))}
    conn = db()
    conn.execute("INSERT INTO polls (question, options, votes) VALUES (?,?,?)",
                 (q, json.dumps(opts), json.dumps(votes)))
    conn.commit(); conn.close()
    socketio.emit("poll-created", {"question": q, "options": opts}, broadcast=True)
    return redirect(url_for("polls_page"))

@app.route("/vote", methods=["POST"])
def vote():
    poll_id = request.form.get("poll_id")
    opt_idx = request.form.get("opt_idx")
    nickname = request.form.get("nickname", "")
    conn = db()
    row = conn.execute("SELECT votes FROM polls WHERE id=?", (poll_id,)).fetchone()
    if not row:
        conn.close(); return jsonify(ok=False), 404
    votes = json.loads(row["votes"])
    votes[opt_idx] = votes.get(opt_idx, 0) + 1
    conn.execute("UPDATE polls SET votes=? WHERE id=?", (json.dumps(votes), poll_id))
    conn.execute("UPDATE users SET points = points + 1 WHERE nickname=?", (nickname,))
    conn.commit(); conn.close()
    socketio.emit("poll-updated", {"poll_id": poll_id, "votes": votes}, broadcast=True)
    return jsonify(ok=True)

# ---------- CHAT + FUN ----------
@socketio.on("join")
def on_join(data):
    room = data.get("room", "main")
    nickname = data.get("nickname", "anon")
    join_room(room)
    emit("status", {"msg": f"{nickname} joined {room}."}, room=room)

@socketio.on("leave")
def on_leave(data):
    room = data.get("room", "main")
    nickname = data.get("nickname", "anon")
    leave_room(room)
    emit("status", {"msg": f"{nickname} left {room}."}, room=room)

@socketio.on("send-msg")
def handle_msg(data):
    room = data.get("room", "main")
    nickname = data.get("nickname", "anon")
    text = data.get("text", "")
    style = data.get("style", "normal")
    emit("new-msg", {"nickname": nickname, "text": text, "style": style, "ts": nowts()}, room=room)

@socketio.on("reaction")
def reaction(data):
    emit("reaction", data, broadcast=True)

@socketio.on("random-teams")
def random_teams(data):
    members = data.get("members", [])
    size = int(data.get("size", 2))
    random.shuffle(members)
    teams = [members[i:i+size] for i in range(0, len(members), size)]
    emit("teams-result", {"teams": teams}, broadcast=True)

# ---------- MINI GAMES ----------
rps_state = {}  # {room: {"moves": {nick: move}, "players": set}}
def rps_winner(m1, m2):
    if m1 == m2: return 0
    win = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    return 1 if win[m1] == m2 else -1

@socketio.on("rps-join")
def rps_join(data):
    room = data.get("room", "rps")
    nickname = data.get("nickname", "anon")
    join_room(room)
    st = rps_state.setdefault(room, {"moves": {}, "players": set()})
    st["players"].add(nickname)
    emit("rps-status", {"msg": f"{nickname} joined {room}. Players: {list(st['players'])}"}, room=room)

@socketio.on("rps-move")
def rps_move(data):
    room = data.get("room", "rps")
    nickname = data.get("nickname", "anon")
    move = data.get("move", "rock")
    st = rps_state.setdefault(room, {"moves": {}, "players": set()})
    st["moves"][nickname] = move
    emit("rps-status", {"msg": f"{nickname} chose {move}."}, room=room)
    if len(st["moves"]) >= 2:
        a, b = list(st["moves"].keys())[:2]
        res = rps_winner(st["moves"][a], st["moves"][b])
        if res == 0:
            emit("rps-result", {"result": "Draw!", "a": a, "b": b}, room=room)
        elif res == 1:
            emit("rps-result", {"result": f"{a} wins!", "a": a, "b": b}, room=room)
            conn = db(); conn.execute("UPDATE users SET points = points + 3 WHERE nickname=?", (a,)); conn.commit(); conn.close()
        else:
            emit("rps-result", {"result": f"{b} wins!", "a": a, "b": b}, room=room)
            conn = db(); conn.execute("UPDATE users SET points = points + 3 WHERE nickname=?", (b,)); conn.commit(); conn.close()
        st["moves"] = {}

ttt_state = {}  # {room: {"board":[...],"turn":"X","players":{"X":nick,"O":nick}}}
def ttt_check(board):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in wins:
        if board[a] and board[a]==board[b]==board[c]: return board[a]
    return "draw" if all(board) else None

@socketio.on("ttt-join")
def ttt_join(data):
    room = data.get("room", "ttt")
    nickname = data.get("nickname", "anon")
    join_room(room)
    st = ttt_state.setdefault(room, {"board": [""]*9, "turn": "X", "players": {}})
    if "X" not in st["players"]:
        st["players"]["X"] = nickname
    elif "O" not in st["players"]:
        st["players"]["O"] = nickname
    emit("ttt-state", {"board": st["board"], "turn": st["turn"], "players": st["players"]}, room=room)

@socketio.on("ttt-move")
def ttt_move(data):
    room = data.get("room", "ttt")
    idx = int(data.get("idx", 0))
    nickname = data.get("nickname", "anon")
    st = ttt_state.setdefault(room, {"board": [""]*9, "turn": "X", "players": {}})
    mark = "X" if st["players"].get("X") == nickname else "O" if st["players"].get("O") == nickname else None
    if mark and st["turn"] == mark and 0 <= idx < 9 and st["board"][idx] == "":
        st["board"][idx] = mark
        st["turn"] = "O" if st["turn"] == "X" else "X"
        result = ttt_check(st["board"])
        if result:
            emit("ttt-state", {"board": st["board"], "turn": st["turn"], "players": st["players"], "winner": result}, room=room)
            if result in ("X","O"):
                wnick = st["players"][result]
                conn = db(); conn.execute("UPDATE users SET points = points + 5 WHERE nickname=?", (wnick,)); conn.commit(); conn.close()
            # reset
            ttt_state[room] = {"board": [""]*9, "turn": "X", "players": {}}
        else:
            emit("ttt-state", {"board": st["board"], "turn": st["turn"], "players": st["players"]}, room=room)

# ---------- STUDY BOT (rule-based demo) ----------
@app.route("/chatbot-query", methods=["POST"])
def chatbot_query():
    q = (request.form.get("q") or "").lower()
    if "attendance" in q:
        return jsonify(answer="Click the Mark Attendance button on dashboard (+5 points). Export CSV available.")
    if "exam" in q:
        return jsonify(answer="Mid-term prep: summary notes + previous papers. Check the dept circular for exact dates.")
    if "tcp" in q or "network" in q:
        return jsonify(answer="Focus: OSI vs TCP/IP layers, subnetting, and HTTP request flow. Try Wireshark once!")
    if "project" in q:
        return jsonify(answer="This app itself: Attendance + Leaderboard + Polls + Games. Add QR code scanning as next step.")
    return jsonify(answer="I'm your study buddy 🤖 — ask me about attendance, exams, networks, or your project.")

# ---------- RUN ----------
if __name__ == "__main__":
    # Auto-create minimal schema if missing (safety net)
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not c.fetchone():
        from schema_init import init; init()
    conn.close()
    print("🚀 ClassHub running on http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000)


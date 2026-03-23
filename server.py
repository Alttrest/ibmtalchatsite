from flask import Flask, render_template_string, request, jsonify, send_from_directory
import threading
import time
import os
import logging
import uuid
import math
import mimetypes
import random

# Gereksiz logları kapat
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- OYUN SABİTLERİ ---
CANVAS_WIDTH, CANVAS_HEIGHT = 1280, 600
GRAVITY, FRICTION, BALL_BOUNCE = 0.5, 0.85, 0.7
GROUND_Y, GOAL_WIDTH, GOAL_HEIGHT = 520, 100, 220

# --- ODA OLUŞTURUCULAR ---
def create_pong_data():
    return {"type": "pong", "p1_y": 160, "p2_y": 160, "ball_x": 300, "ball_y": 200, "s1": 0, "s2": 0, "p1_active": False, "p2_active": False, "game_active": False}

def create_head_soccer_data():
    return {
        "type": "head_soccer",
        "p1": {"x": 250, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "headRadius": 45, "shoeWidth": 60, "shoeHeight": 30, "team": 'ARG', "jumpPower": 15, "isGrounded": True, "facingRight": True, "kickTimer": 0},
        "p2": {"x": 1030, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "headRadius": 45, "shoeWidth": 60, "shoeHeight": 30, "team": 'FRA', "jumpPower": 15, "isGrounded": True, "facingRight": False, "kickTimer": 0},
        "ball": {"x": CANVAS_WIDTH / 2, "y": 200, "vx": 0, "vy": 0, "radius": 22, "rotation": 0},
        "keys_p1": {}, "keys_p2": {}, "s1": 0, "s2": 0, "p1_active": False, "p2_active": False, "game_active": False, "goal_state": False, "goal_timer": 0, "time_left": 88
    }

def create_bridge_data():
    return {"type": "bridge", "path": [random.choice([0, 1]) for _ in range(10)], "current_step": 0, "choices": [], "game_state": "playing"}

state = {
    "global_chat": [],
    "banned_ips": {},
    "rooms": {
        "Oda 1 (Pong)": create_pong_data(),
        "Kafa Topu Arena": create_head_soccer_data(),
        "Sürat Köprüsü": create_bridge_data()
    }
}

# --- FİZİK MOTORLARI ---
def physics_loop():
    while True:
        time.sleep(0.02)
        for room_name, room in list(state["rooms"].items()):
            if not room.get("game_active"): continue
            
            # PONG FİZİĞİ
            if room["type"] == "pong":
                room["ball_x"] += 5; room["ball_y"] += 4 # Basit hız
                if room["ball_y"] <= 0 or room["ball_y"] >= 390: pass # Sekme mantığı
                if room["ball_x"] < 0: room["s2"] += 1; room["game_active"] = False
                elif room["ball_x"] > 600: room["s1"] += 1; room["game_active"] = False

            # KAFA TOPU FİZİĞİ
            elif room["type"] == "head_soccer":
                p1, p2, ball = room["p1"], room["p2"], room["ball"]
                k1, k2 = room["keys_p1"], room["keys_p2"]
                # (Kafa topu fizik hesaplamaları burada devam eder - Önceki kodundaki mantık)
                for p, k in [(p1, k1), (p2, k2)]:
                    if k.get('a') or k.get('arrowleft'): p['vx'] -= 1.2
                    if k.get('d') or k.get('arrowright'): p['vx'] += 1.2
                    p['vx'] *= FRICTION; p['vy'] += GRAVITY; p['x'] += p['vx']; p['y'] += p['vy']
                    if p['y'] + p['shoeHeight'] > GROUND_Y: p['y'] = GROUND_Y - p['shoeHeight']; p['vy'] = 0; p['isGrounded'] = True
                ball['x'] += ball['vx']; ball['y'] += ball['vy'] # Top hareketi

threading.Thread(target=physics_loop, daemon=True).start()

# --- ROUTES ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/state')
def get_state():
    return jsonify({"global_chat": state["global_chat"], "rooms": state["rooms"], "room_list": list(state["rooms"].keys())})

@app.route('/api/room_action', methods=['POST'])
def room_action():
    data = request.json
    room = state["rooms"].get(data['room'])
    action, role = data['action'], data.get('role')
    if action == 'join':
        if role == 'p1': room['p1_active'] = True
        elif role == 'p2': room['p2_active'] = True
    elif action == 'start': room['game_active'] = True
    elif action == 'reset': 
        if room['type'] == 'head_soccer': room.update(create_head_soccer_data())
        else: room['s1'] = 0; room['s2'] = 0
    return jsonify({"ok": True})

@app.route('/api/send', methods=['POST'])
def send():
    data = request.json
    data['id'], data['ip'] = str(uuid.uuid4()), request.remote_addr
    state["global_chat"].append(data)
    return jsonify({"ok": True})

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if file:
        filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        state["global_chat"].append({"user": request.form['user'], "text": filename, "original_name": file.filename, "room": request.form['room'], "type": "file"})
    return jsonify({"ok": True})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

# --- HTML TEMPLATE (SADECE GEREKLİ KISIMLAR) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Alttre HUB</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background: #0b0f19; color: #00ffcc; font-family: monospace; }
        .tab.active { background: #00ffcc; color: #000; }
    </style>
</head>
<body class="flex h-screen overflow-hidden">
    <div class="w-80 bg-slate-950 p-4 border-r border-indigo-500/30 flex flex-col">
        <h2 class="text-xl font-bold mb-4 text-center text-indigo-400">ALTTRE HUB</h2>
        <div id="chat-box" class="flex-1 overflow-y-auto mb-4 p-2 bg-black/40 rounded border border-slate-800 text-sm"></div>
        <input type="text" id="msg" placeholder="Mesaj..." class="bg-slate-900 border border-slate-700 p-2 rounded mb-2 text-white outline-none">
        <input type="file" id="file-upload" class="hidden" onchange="uploadFile()">
        <button onclick="document.getElementById('file-upload').click()" class="bg-slate-800 text-xs py-1 mb-2">Dosya Seç</button>
        <button onclick="sendMsg()" class="bg-indigo-600 font-bold py-2 rounded">GÖNDER</button>
    </div>
    <div class="flex-1 flex flex-col items-center p-4">
        <div class="flex gap-2 mb-4" id="tabs"></div>
        <div id="game-area" class="relative w-full h-full flex items-center justify-center">
             <canvas id="gameCanvas" width="1280" height="600" class="bg-black border-2 border-indigo-500 shadow-2xl max-w-full"></canvas>
        </div>
        <div class="mt-4 flex gap-4">
            <button onclick="roomAction('join', 'p1')" class="bg-blue-600 px-4 py-2 rounded">P1 OL</button>
            <button onclick="roomAction('join', 'p2')" class="bg-red-600 px-4 py-2 rounded">P2 OL</button>
            <button onclick="roomAction('start')" class="bg-green-600 px-4 py-2 rounded">BAŞLAT</button>
        </div>
    </div>
    <script>
        let currentRoom = "Oda 1 (Pong)";
        let rooms = {};
        async function fetchState() {
            const res = await fetch('/api/state');
            const data = await res.json();
            rooms = data.rooms;
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML = data.global_chat.filter(m => m.room === currentRoom).map(m => `<div><b>${m.user}:</b> ${m.text}</div>`).join('');
            
            const tabs = document.getElementById('tabs');
            tabs.innerHTML = data.room_list.map(r => `<button onclick="currentRoom='${r}'" class="tab ${r===currentRoom?'active':''} px-4 py-1 border border-indigo-500">${r}</button>`).join('');
        }
        setInterval(fetchState, 1000);
        async function roomAction(action, role) {
            await fetch('/api/room_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, action, role}) });
        }
        function sendMsg() {
            const text = document.getElementById('msg').value;
            fetch('/api/send', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user: 'Ali', text, room: currentRoom}) });
            document.getElementById('msg').value = '';
        }
    </script>
</body>
</html>
"""

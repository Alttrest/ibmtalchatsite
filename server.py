 from flask import Flask, render_template_string, request, jsonify, send_from_directory

import threading

import time

import os

import logging

import uuid

import math

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


def create_pong_data():

    return {"type": "pong", "p1_y": 160, "p2_y": 160, "ball_x": 300, "ball_y": 200, "s1": 0, "s2": 0, "p1_active": False, "p2_active": False, "game_active": False}


def create_head_soccer_data():

    return {

        "type": "head_soccer",

        "p1": {"x": 250, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "headRadius": 45, "shoeWidth": 60, "shoeHeight": 30, "team": 'ARG', "jumpPower": 15, "isGrounded": True, "facingRight": True, "kickTimer": 0},

        "p2": {"x": 1030, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "headRadius": 45, "shoeWidth": 60, "shoeHeight": 30, "team": 'FRA', "jumpPower": 15, "isGrounded": True, "facingRight": False, "kickTimer": 0},

        "ball": {"x": CANVAS_WIDTH / 2, "y": 200, "vx": 0, "vy": 0, "radius": 22, "rotation": 0},

        "keys_p1": {}, "keys_p2": {}, "s1": 0, "s2": 0, "p1_active": False, "p2_active": False, "game_active": False

    }


def create_bridge_data():

    # 10 adımlı rastgele güvenli yol (0: Sol, 1: Sağ)

    return {"type": "bridge", "path": [random.choice([0, 1]) for _ in range(10)], "current_step": 0, "choices": [], "game_state": "playing", "game_active": True}


state = {

    "global_chat": [],

    "rooms": {

        "Oda 1 (Pong)": create_pong_data(),

        "Kafa Topu Arena": create_head_soccer_data(),

        "Sürat Köprüsü": create_bridge_data()

    }

}


# --- FİZİK MOTORU ---

def physics_loop():

    while True:

        time.sleep(0.02) # 50 FPS

        for room_name, room in list(state["rooms"].items()):

            if not room.get("game_active"): continue

            

            if room["type"] == "head_soccer":

                p1, p2, ball = room["p1"], room["p2"], room["ball"]

                k1, k2 = room["keys_p1"], room["keys_p2"]

                

                if k1.get('a'): p1['vx'] -= 1.2; p1['facingRight'] = False

                if k1.get('d'): p1['vx'] += 1.2; p1['facingRight'] = True

                if k1.get('w') and p1['isGrounded']: p1['vy'] = -p1['jumpPower']; p1['isGrounded'] = False

                

                if k2.get('arrowleft'): p2['vx'] -= 1.2; p2['facingRight'] = False

                if k2.get('arrowright'): p2['vx'] += 1.2; p2['facingRight'] = True

                if k2.get('arrowup') and p2['isGrounded']: p2['vy'] = -p2['jumpPower']; p2['isGrounded'] = False


                for p in [p1, p2]:

                    p['vx'] *= FRICTION; p['vy'] += GRAVITY

                    p['x'] += p['vx']; p['y'] += p['vy']

                    if p['x'] < 0: p['x'] = 0

                    if p['x'] > CANVAS_WIDTH: p['x'] = CANVAS_WIDTH

                    if p['y'] + p['shoeHeight'] > GROUND_Y:

                        p['y'] = GROUND_Y - p['shoeHeight']

                        p['vy'] = 0; p['isGrounded'] = True


                ball['vy'] += GRAVITY

                ball['vx'] *= 0.99; ball['vy'] *= 0.99

                ball['x'] += ball['vx']; ball['y'] += ball['vy']

                if ball['y'] + ball['radius'] > GROUND_Y:

                    ball['y'] = GROUND_Y - ball['radius']

                    ball['vy'] *= -BALL_BOUNCE

                    ball['vx'] *= FRICTION


threading.Thread(target=physics_loop, daemon=True).start()


# --- ROUTES ---

@app.route('/')

def index():

    return render_template_string(HTML_TEMPLATE)


@app.route('/api/state')

def get_state():

    return jsonify({"global_chat": state["global_chat"], "rooms": state["rooms"], "room_list": list(state["rooms"].keys())})


@app.route('/api/keys', methods=['POST'])

def update_keys():

    data = request.json

    room = state["rooms"].get(data['room'])

    if room and room['type'] == 'head_soccer':

        if data.get('role') == 'p1': room['keys_p1'] = data['keys']

        elif data.get('role') == 'p2': room['keys_p2'] = data['keys']

    return jsonify({"ok": True})


@app.route('/api/room_action', methods=['POST'])

def room_action():

    data = request.json

    room = state["rooms"].get(data['room'])

    action = data['action']

    if action == 'join':

        if data.get('role') == 'p1': room['p1_active'] = True

        elif data.get('role') == 'p2': room['p2_active'] = True

    elif action == 'start': room['game_active'] = True

    elif action == 'reset': 

        if room['type'] == 'bridge': room.update(create_bridge_data())

    return jsonify({"ok": True})


@app.route('/api/bridge_action', methods=['POST'])

def bridge_action():

    data = request.json

    room = state["rooms"].get(data['room'])

    if room and room['type'] == 'bridge' and room['game_state'] == 'playing':

        choice = data['choice']

        step = room['current_step']

        room['choices'].append(choice)

        

        if room['path'][step] == choice:

            if step == 9: # 10. adım tamamlandı

                room['game_state'] = 'won'

            else:

                room['current_step'] += 1

        else:

            room['game_state'] = 'lost'

    return jsonify({"ok": True})


@app.route('/api/send', methods=['POST'])

def send():

    state["global_chat"].append(request.json)

    return jsonify({"ok": True})


if __name__ == '__main__':

    port = int(os.environ.get('PORT', 5000))

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


# --- HTML TEMPLATE ---

HTML_TEMPLATE = """

<!DOCTYPE html>

<html>

<head>

    <title>Alttre HUB</title>

    <script src="https://cdn.tailwindcss.com"></script>

    <style>

        body { background: #0b0f19; color: #00ffcc; font-family: monospace; }

        .tab.active { background: #6366f1; color: #fff; }

        

        /* 3D Köprü Stilleri */

        .bridge-perspective { perspective: 1200px; }

        .bridge-platform {

            transform-style: preserve-3d;

            transition: transform 0.8s cubic-bezier(0.25, 0.1, 0.25, 1);

        }

    </style>

</head>

<body class="flex h-screen overflow-hidden select-none text-slate-100">

    

    <div class="w-80 bg-slate-950 p-4 border-r border-indigo-500/30 flex flex-col z-20 relative">

        <h2 class="text-xl font-bold mb-4 text-center text-indigo-400">ALTTRE HUB</h2>

        <div id="chat-box" class="flex-1 overflow-y-auto mb-4 p-2 bg-black/40 rounded border border-slate-800 text-sm"></div>

        <input type="text" id="msg" placeholder="Mesaj..." class="bg-slate-900 border border-slate-700 p-2 rounded mb-2 text-white outline-none">

        <button onclick="sendMsg()" class="bg-indigo-600 font-bold py-2 rounded mb-4">GÖNDER</button>

        

        <div id="soccer-controls" class="flex-col gap-2 flex">

            <button onclick="joinRoom('p1')" id="btn-p1" class="bg-blue-600 px-4 py-2 rounded font-bold">P1 OL (W,A,S,D)</button>

            <button onclick="joinRoom('p2')" id="btn-p2" class="bg-red-600 px-4 py-2 rounded font-bold">P2 OL (Ok Tuşları)</button>

            <button onclick="roomAction('start')" class="bg-green-600 px-4 py-2 rounded font-bold mt-2">OYUNU BAŞLAT</button>

        </div>

    </div>


    <div class="flex-1 flex flex-col items-center p-4 bg-[#0b0f19] relative">

        <div class="flex gap-2 mb-4 w-full justify-center z-20" id="tabs"></div>

        

        <div id="game-area" class="relative w-full h-full flex items-center justify-center overflow-hidden">

             <canvas id="gameCanvas" width="1280" height="600" class="bg-black shadow-2xl rounded-lg border-4 border-slate-800 absolute"></canvas>

             

             <div id="bridge-container" class="absolute inset-0 bridge-perspective hidden flex-col items-center justify-end pb-[15vh]">

                <div id="bridge-hud" class="absolute top-0 left-0 p-6 z-10 w-full pointer-events-none flex justify-between"></div>

                <div id="bridge-world" class="bridge-platform flex flex-col-reverse gap-8" style="transform: rotateX(40deg);"></div>

                <div id="bridge-overlay" class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm z-30 hidden items-center justify-center"></div>

             </div>

        </div>

    </div>


    <script>

        let currentRoom = "Sürat Köprüsü";

        let myRole = null;

        let rooms = {};

        const canvas = document.getElementById('gameCanvas');

        const ctx = canvas.getContext('2d');


        // --- KLAVYE (KAFA TOPU) ---

        let keys = {};

        window.addEventListener('keydown', (e) => { keys[e.key.toLowerCase()] = true; sendKeys(); });

        window.addEventListener('keyup', (e) => { keys[e.key.toLowerCase()] = false; sendKeys(); });

        function sendKeys() {

            if(!myRole || currentRoom !== "Kafa Topu Arena") return;

            fetch('/api/keys', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, role: myRole, keys: keys}) });

        }


        // --- STATE ÇEKME ---

        async function fetchState() {

            try {

                const res = await fetch('/api/state');

                const data = await res.json();

                rooms = data.rooms;

                

                document.getElementById('chat-box').innerHTML = data.global_chat.filter(m => m.room === currentRoom).map(m => `<div><b class="text-indigo-300">${m.user}:</b> ${m.text}</div>`).join('');

                document.getElementById('tabs').innerHTML = data.room_list.map(r => `<button onclick="switchRoom('${r}')" class="tab ${r===currentRoom?'active':''} px-6 py-2 rounded-t-lg font-bold bg-slate-800 text-slate-400 transition-colors">${r}</button>`).join('');

            } catch(e) {}

        }

        setInterval(fetchState, 50);


        function switchRoom(roomName) {

            currentRoom = roomName;

            document.getElementById('soccer-controls').style.display = roomName === "Kafa Topu Arena" ? "flex" : "none";

        }


        // --- KÖPRÜ FİZİĞİ & RENDER (REACT'TEN UYARLAMA) ---

        function sendBridgeAction(choice) {

            fetch('/api/bridge_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, choice}) });

        }


        function renderBridgeUI(room) {

            const world = document.getElementById('bridge-world');

            const hud = document.getElementById('bridge-hud');

            const overlay = document.getElementById('bridge-overlay');

            

            // Kamera Hareketi

            world.style.transform = `rotateX(40deg) translateY(${room.current_step * 160}px) translateZ(${room.current_step * 40}px)`;


            // HUD

            hud.innerHTML = `

                <div>

                    <h1 class="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Sürat Köprüsü</h1>

                    <p class="text-slate-400 font-medium mt-1">Adım: ${Math.min(room.current_step + 1, 10)} / 10</p>

                </div>

            `;


            // Platformlar

            let html = `

                <div class="flex justify-center mb-4">

                    <div class="w-96 h-40 bg-slate-800/80 border border-slate-700 rounded-t-3xl flex items-center justify-center shadow-2xl backdrop-blur-md">

                        <span class="text-slate-500 font-bold tracking-widest uppercase text-xl">Başlangıç</span>

                    </div>

                </div>

            `;


            for(let i=0; i<10; i++) {

                html += `<div class="flex gap-8 justify-center">`;

                [0, 1].forEach(side => {

                    const isCurrent = i === room.current_step && room.game_state === 'playing';

                    const isPast = i < room.current_step || (i === room.current_step && room.game_state !== 'playing');

                    const wasChosen = isPast && room.choices[i] === side;

                    const isSafe = room.path[i] === side;

                    

                    let cls = "relative w-40 h-32 rounded-2xl transition-all duration-500 flex items-center justify-center ";

                    

                    if (isCurrent) {

                        cls += "bg-indigo-500/20 border-2 border-indigo-400 hover:bg-indigo-500/30 cursor-pointer shadow-[0_0_30px_rgba(99,102,241,0.5)]";

                    } else if (isPast) {

                        if (wasChosen && isSafe) cls += "bg-emerald-500/30 border-2 border-emerald-400 shadow-[0_0_30px_rgba(16,185,129,0.4)]";

                        else if (wasChosen && !isSafe) cls += "opacity-0 translate-y-20"; // Kırıldı

                        else cls += "bg-white/5 border border-white/10 opacity-40";

                    } else {

                        cls += "bg-white/10 border border-white/20 backdrop-blur-md";

                    }


                    const clickAttr = isCurrent ? `onclick="sendBridgeAction(${side})"` : "";

                    html += `<div ${clickAttr} class="${cls}">

                                ${wasChosen && isSafe ? '<div class="w-14 h-14 bg-emerald-400 rounded-full shadow-[0_0_30px_rgba(52,211,153,1)]"></div>' : ''}

                             </div>`;

                });

                html += `</div>`;

            }


            html += `

                <div class="flex justify-center mt-4">

                    <div class="w-96 h-40 bg-emerald-900/80 border border-emerald-800 rounded-b-3xl flex items-center justify-center shadow-2xl backdrop-blur-md">

                        <span class="text-emerald-500 font-bold tracking-widest uppercase text-xl">Bitiş</span>

                    </div>

                </div>

            `;

            world.innerHTML = html;


            // Oyun Sonu Ekranı

            if (room.game_state !== 'playing') {

                overlay.style.display = 'flex';

                overlay.innerHTML = `

                    <div class="bg-slate-900 border border-slate-800 p-8 rounded-3xl shadow-2xl flex flex-col items-center max-w-sm pointer-events-auto">

                        <h2 class="text-3xl font-bold text-white mb-2">${room.game_state === 'won' ? '🏆 Başardın!' : '💀 Düştün!'}</h2>

                        <p class="text-slate-400 mb-8">${room.game_state === 'won' ? 'Köprüyü güvenle geçtin.' : 'Yanlış camı seçtin.'}</p>

                        <button onclick="roomAction('reset')" class="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl font-semibold w-full">Tekrar Oyna</button>

                    </div>

                `;

            } else {

                overlay.style.display = 'none';

            }

        }


        // --- ANA RENDER DÖNGÜSÜ ---

        function render() {

            const room = rooms[currentRoom];

            const bridgeContainer = document.getElementById('bridge-container');

            

            if (currentRoom === "Sürat Köprüsü") {

                canvas.style.display = 'none';

                bridgeContainer.style.display = 'flex';

                if(room) renderBridgeUI(room);

            } else {

                canvas.style.display = 'block';

                bridgeContainer.style.display = 'none';

                

                ctx.clearRect(0, 0, canvas.width, canvas.height);

                if (room && room.type === "head_soccer") {

                    // Kafa topu çizim mantığı (Zemin, oyuncular, top)

                    ctx.fillStyle = '#228B22'; ctx.fillRect(0, 520, canvas.width, 80);

                    if(room.p1) { ctx.fillStyle = '#3b82f6'; ctx.beginPath(); ctx.arc(room.p1.x, room.p1.y, room.p1.headRadius, 0, Math.PI*2); ctx.fill(); }

                    if(room.p2) { ctx.fillStyle = '#ef4444'; ctx.beginPath(); ctx.arc(room.p2.x, room.p2.y, room.p2.headRadius, 0, Math.PI*2); ctx.fill(); }

                    if(room.ball) { ctx.fillStyle = 'white'; ctx.beginPath(); ctx.arc(room.ball.x, room.ball.y, room.ball.radius, 0, Math.PI*2); ctx.fill(); }

                }

            }

            requestAnimationFrame(render);

        }

        render();


        // --- GENEL AKSİYONLAR ---

        async function joinRoom(role) {

            myRole = role;

            document.getElementById('btn-' + role).innerText += " (SEÇİLDİ)";

            await fetch('/api/room_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, action: 'join', role}) });

        }

        async function roomAction(action) {

            await fetch('/api/room_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, action}) });

        }

        function sendMsg() {

            const text = document.getElementById('msg').value;

            if(!text) return;

            fetch('/api/send', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user: myRole ? myRole.toUpperCase() : 'Oyuncu', text, room: currentRoom}) });

            document.getElementById('msg').value = '';

        }

        

        switchRoom(currentRoom);

    </script>

</body>

</html

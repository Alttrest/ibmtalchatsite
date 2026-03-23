from flask import Flask, render_template_string, request, jsonify, send_from_directory
import threading
import time
import os
import logging
import uuid
import math
import mimetypes

# Terminal spamını sustur
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- OYUN SABİTLERİ (Python Fizik Motoru İçin) ---
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 600
GRAVITY = 0.5
FRICTION = 0.85
BALL_BOUNCE = 0.7
GROUND_Y = 520
GOAL_WIDTH = 100
GOAL_HEIGHT = 220

def create_base_room():
    return {
        "p1": {"x": 250, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "headRadius": 45, "shoeWidth": 60, "shoeHeight": 30, "team": 'ARG', "jumpPower": 15, "isGrounded": True, "facingRight": True, "kickTimer": 0},
        "p2": {"x": 1030, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "headRadius": 45, "shoeWidth": 60, "shoeHeight": 30, "team": 'FRA', "jumpPower": 15, "isGrounded": True, "facingRight": False, "kickTimer": 0},
        "ball": {"x": CANVAS_WIDTH / 2, "y": 200, "vx": 0, "vy": 0, "radius": 22, "rotation": 0},
        "keys_p1": {}, "keys_p2": {}, "s1": 0, "s2": 0,
        "p1_active": False, "p2_active": False, "game_active": False, 
        "goal_state": False, "goal_timer": 0, "time_left": 88
    }

# --- VERİTABANI ---
state = {
    "global_chat": [], 
    "rooms": {
        "Oda 1": create_base_room(),
        "Oda 2": create_base_room(),
        "Oda 3": create_base_room()
    }
}

def reset_positions(room):
    room["p1"].update({"x": 250, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "isGrounded": True, "facingRight": True, "kickTimer": 0})
    room["p2"].update({"x": 1030, "y": GROUND_Y - 60, "vx": 0, "vy": 0, "isGrounded": True, "facingRight": False, "kickTimer": 0})
    room["ball"].update({"x": CANVAS_WIDTH / 2, "y": 200, "vx": 0, "vy": 0})

# --- KAFA TOPU FİZİK MOTORU (SUNUCU TARAFLI) ---
def physics_loop():
    while True:
        time.sleep(0.02) # Saniyede 50 Kare Hesaplama
        for room_name, room in state["rooms"].items():
            
            # Gol sevinci beklemesi
            if room["goal_state"]:
                if time.time() > room["goal_timer"]:
                    reset_positions(room)
                    room["goal_state"] = False
                    room["game_active"] = True
                continue

            if not room["game_active"]: continue

            p1, p2, ball = room["p1"], room["p2"], room["ball"]
            k1, k2 = room["keys_p1"], room["keys_p2"]

            # --- OYUNCU 1 HAREKET ---
            if k1.get('a'): p1['vx'] -= 1.2; p1['facingRight'] = False
            if k1.get('d'): p1['vx'] += 1.2; p1['facingRight'] = True
            if k1.get('w') and p1['isGrounded']: p1['vy'] = -p1['jumpPower']; p1['isGrounded'] = False
            if (k1.get('v') or k1.get('b')) and p1['kickTimer'] == 0: p1['kickTimer'] = 15

            # --- OYUNCU 2 HAREKET ---
            if k2.get('arrowleft'): p2['vx'] -= 1.2; p2['facingRight'] = False
            if k2.get('arrowright'): p2['vx'] += 1.2; p2['facingRight'] = True
            if k2.get('arrowup') and p2['isGrounded']: p2['vy'] = -p2['jumpPower']; p2['isGrounded'] = False
            if (k2.get('k') or k2.get('l')) and p2['kickTimer'] == 0: p2['kickTimer'] = 15

            # --- OYUNCULAR ARASI ÇARPIŞMA ---
            pdx, pdy = p2['x'] - p1['x'], p2['y'] - p1['y']
            pDist = math.sqrt(pdx*pdx + pdy*pdy)
            pMinDist = p1['headRadius'] + p2['headRadius']

            if 0 < pDist < pMinDist:
                overlap = pMinDist - pDist
                angle = math.atan2(pdy, pdx)
                pushX = math.cos(angle) * (overlap / 2)
                pushY = math.sin(angle) * (overlap / 2)
                p1['x'] -= pushX; p1['y'] -= pushY
                p2['x'] += pushX; p2['y'] += pushY
                vxDiff = p1['vx'] - p2['vx']
                p1['vx'] -= vxDiff * 0.3; p2['vx'] += vxDiff * 0.3

            # --- OYUNCU FİZİKLERİ ---
            for p in [p1, p2]:
                p['vx'] *= FRICTION; p['vy'] += GRAVITY
                p['x'] += p['vx']; p['y'] += p['vy']
                if p['kickTimer'] > 0: p['kickTimer'] -= 1

                if p['x'] - p['headRadius'] < 0: p['x'] = p['headRadius']; p['vx'] = 0
                if p['x'] + p['headRadius'] > CANVAS_WIDTH: p['x'] = CANVAS_WIDTH - p['headRadius']; p['vx'] = 0
                if p['y'] + p['shoeHeight'] > GROUND_Y: p['y'] = GROUND_Y - p['shoeHeight']; p['vy'] = 0; p['isGrounded'] = True

                # Oyuncunun kalenin üstüne çıkması
                if p['x'] < GOAL_WIDTH and p['y'] > GROUND_Y - GOAL_HEIGHT:
                    if p['vy'] > 0 and p['y'] < GROUND_Y - GOAL_HEIGHT + 20: p['y'] = GROUND_Y - GOAL_HEIGHT; p['vy'] = 0; p['isGrounded'] = True
                    else: p['x'] = GOAL_WIDTH + p['headRadius']; p['vx'] = 0
                if p['x'] > CANVAS_WIDTH - GOAL_WIDTH and p['y'] > GROUND_Y - GOAL_HEIGHT:
                    if p['vy'] > 0 and p['y'] < GROUND_Y - GOAL_HEIGHT + 20: p['y'] = GROUND_Y - GOAL_HEIGHT; p['vy'] = 0; p['isGrounded'] = True
                    else: p['x'] = CANVAS_WIDTH - GOAL_WIDTH - p['headRadius']; p['vx'] = 0

            # --- TOP FİZİKLERİ ---
            ball['vy'] += GRAVITY
            ball['vx'] *= 0.99; ball['vy'] *= 0.99
            ball['x'] += ball['vx']; ball['y'] += ball['vy']
            ball['rotation'] += ball['vx'] * 0.05

            if ball['y'] + ball['radius'] > GROUND_Y: ball['y'] = GROUND_Y - ball['radius']; ball['vy'] *= -BALL_BOUNCE; ball['vx'] *= FRICTION
            if ball['y'] - ball['radius'] < 0: ball['y'] = ball['radius']; ball['vy'] *= -BALL_BOUNCE
            if ball['x'] - ball['radius'] < 0: ball['x'] = ball['radius']; ball['vx'] *= -BALL_BOUNCE
            if ball['x'] + ball['radius'] > CANVAS_WIDTH: ball['x'] = CANVAS_WIDTH - ball['radius']; ball['vx'] *= -BALL_BOUNCE

            # Top Direk Çarpışmaları
            if ball['x'] < GOAL_WIDTH and GROUND_Y - GOAL_HEIGHT < ball['y'] < GROUND_Y - GOAL_HEIGHT + 15: ball['vy'] *= -BALL_BOUNCE; ball['y'] = GROUND_Y - GOAL_HEIGHT - ball['radius']
            if ball['x'] > CANVAS_WIDTH - GOAL_WIDTH and GROUND_Y - GOAL_HEIGHT < ball['y'] < GROUND_Y - GOAL_HEIGHT + 15: ball['vy'] *= -BALL_BOUNCE; ball['y'] = GROUND_Y - GOAL_HEIGHT - ball['radius']

            # --- GOL KONTROLÜ ---
            if ball['y'] > GROUND_Y - GOAL_HEIGHT + 15:
                if ball['x'] - ball['radius'] < GOAL_WIDTH - 15:
                    room['s2'] += 1; room['game_active'] = False; room['goal_state'] = True; room['goal_timer'] = time.time() + 3
                elif ball['x'] + ball['radius'] > CANVAS_WIDTH - GOAL_WIDTH + 15:
                    room['s1'] += 1; room['game_active'] = False; room['goal_state'] = True; room['goal_timer'] = time.time() + 3

            # --- TOP - OYUNCU ÇARPIŞMASI ---
            for p in [p1, p2]:
                dx, dy = ball['x'] - p['x'], ball['y'] - (p['y'] - 20)
                distance = math.sqrt(dx*dx + dy*dy)
                minDist = ball['radius'] + p['headRadius']

                if 0 < distance < minDist: # Kafa vuruşu
                    angle = math.atan2(dy, dx)
                    ball['x'], ball['y'] = p['x'] + math.cos(angle) * minDist, (p['y'] - 20) + math.sin(angle) * minDist
                    ball['vx'] += (ball['x'] - p['x']) * 0.2 + p['vx'] * 0.5
                    ball['vy'] += (ball['y'] - (p['y'] - 20)) * 0.2 + p['vy'] * 0.5

                shoeX, shoeY = p['x'] + (15 if p['facingRight'] else -15), p['y'] + 20
                shoeDx, shoeDy = ball['x'] - shoeX, ball['y'] - shoeY
                shoeDist = math.sqrt(shoeDx*shoeDx + shoeDy*shoeDy)
                kickReach = 45 if p['kickTimer'] > 0 else 30

                if shoeDist < ball['radius'] + kickReach: # Ayak vuruşu
                    if p['kickTimer'] > 0:
                        ball['vx'] = 16 if p['facingRight'] else -16
                        ball['vy'] = -14; p['kickTimer'] = 0
                    else:
                        angle = math.atan2(shoeDy, shoeDx)
                        ball['vx'] += math.cos(angle) * 2 + p['vx'] * 0.5
                        ball['vy'] += math.sin(angle) * 2 + p['vy'] * 0.5

threading.Thread(target=physics_loop, daemon=True).start()

# --- ZAMANLAYICI MOTORU ---
def timer_loop():
    while True:
        time.sleep(1)
        for room in state["rooms"].values():
            if room["game_active"] and room["time_left"] > 0:
                room["time_left"] -= 1
threading.Thread(target=timer_loop, daemon=True).start()

# --- HTML / JS ARAYÜZÜ (MODERN TASARIM) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Modern Kafa Topu Multiplayer</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        body { margin: 0; overflow: hidden; background: #000; font-family: sans-serif; user-select: none; }
        .chat-scroll::-webkit-scrollbar { width: 6px; }
        .chat-scroll::-webkit-scrollbar-thumb { background: #4f46e5; border-radius: 10px; }
    </style>
</head>
<body class="flex h-screen w-screen text-slate-100">

    <div class="w-80 bg-slate-950 border-r border-indigo-500/30 flex flex-col p-4 z-20 shadow-2xl">
        <h2 class="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400 mb-4 text-center">ALTTRE HUB</h2>
        
        <select id="chat-mode" class="w-full bg-slate-900 border border-slate-700 text-white rounded p-2 mb-4 outline-none focus:border-indigo-500" onchange="changeRoom(this.value)">
            <option value="Oda 1">Oda 1</option>
            <option value="Oda 2">Oda 2</option>
            <option value="Oda 3">Oda 3</option>
        </select>

        <div id="chat-box" class="flex-1 overflow-y-auto chat-scroll flex flex-col gap-2 p-2 bg-slate-900/50 rounded border border-slate-800 mb-4"></div>
        
        <div class="flex flex-col gap-2">
            <input type="text" id="username" placeholder="Kullanıcı Adı" class="bg-slate-900 border border-slate-700 rounded p-2 text-sm text-white outline-none focus:border-indigo-500">
            <input type="text" id="msg" placeholder="Mesaj yaz..." class="bg-slate-900 border border-slate-700 rounded p-2 text-sm text-white outline-none focus:border-indigo-500" onkeypress="if(event.key==='Enter') sendData()">
            <label class="bg-slate-800 hover:bg-slate-700 text-center text-xs p-2 rounded cursor-pointer transition border border-slate-600 text-indigo-300">
                📁 Dosya / Medya Seç
                <input type="file" id="file-upload" class="hidden" onchange="sendData()">
            </label>
            <button onclick="sendData()" class="bg-indigo-600 hover:bg-indigo-500 font-bold py-2 rounded transition shadow-[0_0_15px_rgba(79,70,229,0.4)]">GÖNDER</button>
        </div>
    </div>

    <div class="flex-1 flex flex-col relative bg-[#1a1a1a]">
        
        <div class="absolute top-0 left-0 w-full p-4 flex justify-between items-start z-10 pointer-events-none">
            <button onclick="roomAction('reset')" class="pointer-events-auto bg-blue-600 border-4 border-white rounded-xl p-2 shadow-lg hover:scale-105 transition-transform"><i data-lucide="refresh-cw" class="text-white w-6 h-6"></i></button>
            <div class="flex flex-col items-center mt-2">
                <div class="flex items-stretch h-16 shadow-2xl drop-shadow-2xl">
                    <div class="bg-gray-200 text-black font-black text-3xl px-8 flex items-center justify-center border-y-4 border-l-4 border-black" style="clip-path: polygon(0 0, 100% 0, 85% 100%, 15% 100%); width: 140px;">P1</div>
                    <div class="bg-cyan-500 w-12 border-y-4 border-black" style="clip-path: polygon(0 0, 100% 0, 60% 100%, -40% 100%); margin-left: -20px;"></div>
                    <div class="bg-white text-black font-black text-4xl px-6 flex items-center justify-center border-4 border-black z-10" style="min-width: 120px; margin-left: -15px; margin-right: -15px;" id="score-board">0-0</div>
                    <div class="bg-red-500 w-12 border-y-4 border-black" style="clip-path: polygon(40% 0, 140% 0, 100% 100%, 0 100%); margin-right: -20px;"></div>
                    <div class="bg-gray-200 text-black font-black text-3xl px-8 flex items-center justify-center border-y-4 border-r-4 border-black" style="clip-path: polygon(15% 0, 100% 0, 85% 100%, 0 100%); width: 140px;">P2</div>
                </div>
                <div class="bg-green-600 border-x-4 border-b-4 border-black text-white font-black text-xl px-8 py-1 flex items-center gap-2 shadow-lg" style="clip-path: polygon(10% 0, 90% 0, 100% 100%, 0 100%); margin-top: -4px;">
                    <span class="text-sm">🕒</span> <span id="time-left">88</span>
                </div>
            </div>
            <button onclick="toggleMute()" id="mute-btn" class="pointer-events-auto bg-blue-600 border-4 border-white rounded-xl p-2 shadow-lg hover:scale-105 transition-transform"><i data-lucide="volume-2" class="text-white w-6 h-6"></i></button>
        </div>

        <div class="flex-1 flex items-center justify-center overflow-hidden">
            <canvas id="gameCanvas" width="1280" height="600" class="max-w-full max-h-full shadow-2xl rounded-lg" style="aspect-ratio: 1280/600;"></canvas>
        </div>

        <div class="h-[140px] bg-[#3e2723] border-t-8 border-[#271815] relative flex justify-between px-16 items-center shrink-0">
            <div class="flex items-center gap-8 z-10 w-1/3">
                <button onclick="roomAction('join', 'p1')" class="text-white font-black text-4xl drop-shadow-md hover:text-cyan-400 transition">P1 OL</button>
                <div class="flex flex-col items-center gap-2">
                    <span class="text-white font-bold text-sm tracking-widest">HAREKET</span>
                    <div class="flex flex-col items-center gap-1">
                        <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">W</div>
                        <div class="flex gap-1">
                            <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">A</div>
                            <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">S</div>
                            <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">D</div>
                        </div>
                    </div>
                </div>
                <div class="flex flex-col items-center gap-2">
                    <span class="text-orange-400 font-black text-sm italic">ŞUT 🔥</span>
                    <div class="flex gap-1 mt-2">
                        <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">V</div>
                        <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">B</div>
                    </div>
                </div>
            </div>
            
            <div class="z-10 flex flex-col items-center gap-2">
                <button onclick="roomAction('start')" class="bg-yellow-500 text-black font-black px-6 py-2 rounded hover:bg-yellow-400 shadow-lg">BAŞLAT / DEVAM</button>
                <button onclick="roomAction('exit')" class="text-rose-400 text-sm font-bold hover:text-white">Çıkış Yap</button>
                <p id="game-status" class="text-white text-xs font-bold bg-black/50 px-3 py-1 rounded">İzleyici Modu</p>
            </div>

            <div class="flex items-center justify-end gap-8 z-10 w-1/3">
                <div class="flex flex-col items-center gap-2">
                    <span class="text-orange-400 font-black text-sm italic">ŞUT 🔥</span>
                    <div class="flex gap-1 mt-2">
                        <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">K</div>
                        <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">L</div>
                    </div>
                </div>
                <div class="flex flex-col items-center gap-2">
                    <span class="text-white font-bold text-sm tracking-widest">HAREKET</span>
                    <div class="flex flex-col items-center gap-1">
                        <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">↑</div>
                        <div class="flex gap-1">
                            <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">←</div>
                            <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">↓</div>
                            <div class="bg-gray-300 text-black font-black w-8 h-8 flex items-center justify-center rounded border-b-4 border-gray-500">→</div>
                        </div>
                    </div>
                </div>
                <button onclick="roomAction('join', 'p2')" class="text-white font-black text-4xl drop-shadow-md hover:text-rose-400 transition">P2 OL</button>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();
        const CANVAS_W = 1280, CANVAS_H = 600, GROUND_Y = 520, GOAL_W = 100, GOAL_H = 220;
        let currentRoom = "Oda 1";
        let myRole = null;
        let serverData = null;
        let isMuted = false;
        let localBallHistory = [];
        let audioCtx = null;

        const canvas = document.getElementById("gameCanvas");
        const ctx = canvas.getContext("2d");

        // SES SİSTEMİ
        function playSound(type) {
            if (isMuted) return;
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain); gain.connect(audioCtx.destination);
            const now = audioCtx.currentTime;

            if (type === 'jump') {
                osc.type = 'sine'; osc.frequency.setValueAtTime(300, now); osc.frequency.exponentialRampToValueAtTime(600, now + 0.15);
                gain.gain.setValueAtTime(0.2, now); gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);
                osc.start(now); osc.stop(now + 0.15);
            } else if (type === 'kick') {
                osc.type = 'triangle'; osc.frequency.setValueAtTime(150, now); osc.frequency.exponentialRampToValueAtTime(40, now + 0.1);
                gain.gain.setValueAtTime(0.4, now); gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
                osc.start(now); osc.stop(now + 0.1);
            } else if (type === 'bounce') {
                osc.type = 'square'; osc.frequency.setValueAtTime(100, now); osc.frequency.exponentialRampToValueAtTime(50, now + 0.1);
                gain.gain.setValueAtTime(0.1, now); gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
                osc.start(now); osc.stop(now + 0.1);
            }
        }

        function toggleMute() { isMuted = !isMuted; }

        function changeRoom(room) { currentRoom = room; myRole = null; }

        async function roomAction(action, role) {
            if (action === 'join') myRole = role;
            if (action === 'exit') myRole = null;
            await fetch('/api/room_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, action, role: myRole}) });
            if(!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }

        // KLAVYE GÖNDERİMİ
        window.addEventListener("keydown", e => {
            if(!myRole || document.activeElement.id === 'msg') return;
            fetch('/api/key', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, player: myRole, key: e.key.toLowerCase(), state: true}) });
        });
        window.addEventListener("keyup", e => {
            if(!myRole || document.activeElement.id === 'msg') return;
            fetch('/api/key', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({room: currentRoom, player: myRole, key: e.key.toLowerCase(), state: false}) });
        });

        // DOSYA VE SOHBET GÖNDERİMİ
        async function sendData() {
            const user = document.getElementById('username').value || "Anonim";
            const text = document.getElementById('msg').value;
            const fileInput = document.getElementById('file-upload');

            if(fileInput.files.length > 0) {
                const formData = new FormData();
                formData.append("file", fileInput.files[0]); formData.append("user", user); formData.append("room", currentRoom);
                await fetch('/api/upload_file', { method: 'POST', body: formData });
                fileInput.value = ""; 
            } else if (text) {
                await fetch('/api/send', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user, text, room: currentRoom, type: 'text'}) });
                document.getElementById('msg').value = '';
            }
        }

        // AĞ SENKRONİZASYONU
        let prevBallVy = 0;
        let prevP1Vy = 0, prevP2Vy = 0;
        
        async function fetchState() {
            const res = await fetch('/api/state');
            const data = await res.json();
            serverData = data.rooms[currentRoom];
            
            document.getElementById("score-board").innerText = `${serverData.s1}-${serverData.s2}`;
            document.getElementById("time-left").innerText = serverData.time_left;

            let status = "İzleyici Modu";
            if(serverData.p1_active && serverData.p2_active) status = serverData.game_active ? "Oyun Aktif" : "Bekleniyor...";
            else status = "Oyuncu Bekleniyor...";
            if(myRole) status = `[${myRole.toUpperCase()}] ` + status;
            document.getElementById("game-status").innerText = status;

            // Chat Güncelleme
            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML = data.global_chat.filter(m => m.room === currentRoom).map(m => {
                let content = m.text;
                if(m.type === 'image') content = `<img src="/uploads/${m.text}" class="max-w-full rounded mt-1">`;
                else if(m.type === 'video') content = `<video controls src="/uploads/${m.text}" class="max-w-full rounded mt-1"></video>`;
                else if(m.type === 'file') content = `📁 <a href="/uploads/${m.text}" download="${m.original_name}" class="text-yellow-400 font-bold hover:underline">${m.original_name} İndir</a>`;
                return `<div class="bg-slate-800 p-2 rounded text-sm"><b class="text-indigo-400">${m.user}:</b><br>${content}</div>`;
            }).join('');

            // Ses Efektleri Tetikleyicisi (Local tahmini)
            if(serverData.game_active) {
                if(Math.abs(serverData.ball.vy - prevBallVy) > 5) playSound('bounce');
                if(serverData.p1.vy < -10 && prevP1Vy >= 0) playSound('jump');
                if(serverData.p2.vy < -10 && prevP2Vy >= 0) playSound('jump');
                
                prevBallVy = serverData.ball.vy;
                prevP1Vy = serverData.p1.vy;
                prevP2Vy = serverData.p2.vy;
            }

            // Top İzi Güncellemesi
            localBallHistory.unshift({x: serverData.ball.x, y: serverData.ball.y});
            if (localBallHistory.length > 10) localBallHistory.pop();
        }
        setInterval(fetchState, 30);

        // ÇİZİM MOTORU (React'tan Vanilya JS'ye Çevrildi)
        function drawBackground() {
            const skyGrad = ctx.createLinearGradient(0, 0, 0, 300);
            skyGrad.addColorStop(0, '#0a0a2a'); skyGrad.addColorStop(1, '#1a1a3a');
            ctx.fillStyle = skyGrad; ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

            ctx.fillStyle = 'white';
            for(let i=0; i<50; i++) {
                const x = Math.sin(i * 123) * CANVAS_W; const y = Math.cos(i * 321) * 200;
                ctx.globalAlpha = Math.abs(Math.sin(Date.now() / 1000 + i));
                ctx.fillRect(Math.abs(x), Math.abs(y), 2, 2);
            }
            ctx.globalAlpha = 1;

            ctx.fillStyle = '#2d3748';
            ctx.beginPath(); ctx.moveTo(0, 200); ctx.lineTo(CANVAS_W, 200); ctx.lineTo(CANVAS_W, 400); ctx.lineTo(0, 400); ctx.fill();

            ctx.fillStyle = '#1a202c';
            for(let i=0; i<CANVAS_W; i+=20) {
                for(let j=220; j<380; j+=15) {
                    if(Math.random() > 0.3) { ctx.fillStyle = Math.random() > 0.5 ? '#4a5568' : '#2b6cb0'; ctx.fillRect(i + Math.random()*10, j, 4, 4); }
                }
            }

            ctx.fillStyle = '#171923'; ctx.fillRect(0, 380, CANVAS_W, 40);
            const fieldGrad = ctx.createLinearGradient(0, 420, 0, CANVAS_H);
            fieldGrad.addColorStop(0, '#00c853'); fieldGrad.addColorStop(1, '#00e676');
            ctx.fillStyle = fieldGrad; ctx.fillRect(0, 420, CANVAS_W, CANVAS_H - 420);

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)'; ctx.lineWidth = 4;
            ctx.beginPath(); ctx.moveTo(CANVAS_W / 2, 420); ctx.lineTo(CANVAS_W / 2, CANVAS_H); ctx.stroke();
            ctx.beginPath(); ctx.ellipse(CANVAS_W / 2, 510, 120, 40, 0, 0, Math.PI * 2); ctx.stroke();

            ctx.fillStyle = '#3e2723'; ctx.fillRect(0, GROUND_Y, CANVAS_W, CANVAS_H - GROUND_Y);
            ctx.fillStyle = '#ffffff'; ctx.fillRect(0, GROUND_Y, CANVAS_W, 6);
        }

        function drawGoals() {
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)'; ctx.lineWidth = 1.5;
            ctx.beginPath();
            for(let i=0; i<=GOAL_W; i+=15) { ctx.moveTo(i, GROUND_Y); ctx.lineTo(i, GROUND_Y - GOAL_H); }
            for(let i=0; i<=GOAL_H; i+=15) { ctx.moveTo(0, GROUND_Y - i); ctx.lineTo(GOAL_W, GROUND_Y - i); }
            ctx.stroke();
            ctx.beginPath();
            for(let i=0; i<=GOAL_W; i+=15) { ctx.moveTo(CANVAS_W - i, GROUND_Y); ctx.lineTo(CANVAS_W - i, GROUND_Y - GOAL_H); }
            for(let i=0; i<=GOAL_H; i+=15) { ctx.moveTo(CANVAS_W, GROUND_Y - i); ctx.lineTo(CANVAS_W - GOAL_W, GROUND_Y - i); }
            ctx.stroke();

            const drawPost = (x, y, w, h) => {
                ctx.fillStyle = 'white'; ctx.fillRect(x, y, w, h);
                ctx.fillStyle = '#e53e3e'; for(let i=0; i<h; i+=30) ctx.fillRect(x, y + i, w, 15);
                ctx.strokeStyle = '#2d3748'; ctx.lineWidth = 2; ctx.strokeRect(x, y, w, h);
            };
            drawPost(GOAL_W - 15, GROUND_Y - GOAL_H, 15, GOAL_H); drawPost(0, GROUND_Y - GOAL_H, GOAL_W, 15);
            drawPost(CANVAS_W - GOAL_W, GROUND_Y - GOAL_H, 15, GOAL_H); drawPost(CANVAS_W - GOAL_W, GROUND_Y - GOAL_H, GOAL_W, 15);
        }

        function drawPlayer(p) {
            ctx.save(); ctx.translate(p.x, p.y); if (!p.facingRight) ctx.scale(-1, 1);
            const kickOffset = p.kickTimer > 0 ? 25 : 0; const shoeX = -10 + kickOffset, shoeY = 15;
            
            ctx.fillStyle = '#e2e8f0'; ctx.beginPath(); ctx.roundRect(shoeX, shoeY, p.shoeWidth, p.shoeHeight, 15); ctx.fill();
            ctx.strokeStyle = '#1a202c'; ctx.lineWidth = 2; ctx.stroke();

            ctx.save(); ctx.beginPath(); ctx.roundRect(shoeX + 15, shoeY + 5, 30, 15, 2); ctx.clip();
            if (p.team === 'ARG') {
                ctx.fillStyle = '#75AADB'; ctx.fillRect(shoeX + 15, shoeY + 5, 30, 5);
                ctx.fillStyle = '#FFFFFF'; ctx.fillRect(shoeX + 15, shoeY + 10, 30, 5);
                ctx.fillStyle = '#75AADB'; ctx.fillRect(shoeX + 15, shoeY + 15, 30, 5);
            } else {
                ctx.fillStyle = '#002395'; ctx.fillRect(shoeX + 15, shoeY + 5, 10, 15);
                ctx.fillStyle = '#FFFFFF'; ctx.fillRect(shoeX + 25, shoeY + 5, 10, 15);
                ctx.fillStyle = '#ED2939'; ctx.fillRect(shoeX + 35, shoeY + 5, 10, 15);
            }
            ctx.restore();

            const headY = -25;
            ctx.fillStyle = p.team === 'ARG' ? '#fcd5ce' : '#8d5524'; 
            ctx.beginPath(); ctx.ellipse(0, headY, p.headRadius, p.headRadius * 1.1, 0, 0, Math.PI * 2); ctx.fill(); ctx.stroke();

            ctx.fillStyle = p.team === 'ARG' ? '#5c3a21' : '#1a1a1a';
            ctx.beginPath();
            if (p.team === 'ARG') { ctx.arc(0, headY - 10, p.headRadius + 2, Math.PI, 0); ctx.lineTo(p.headRadius, headY); ctx.lineTo(-p.headRadius, headY); } 
            else { ctx.arc(0, headY - 15, p.headRadius, Math.PI, 0); }
            ctx.fill();

            ctx.fillStyle = 'white';
            ctx.beginPath(); ctx.arc(15, headY - 5, 8, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
            ctx.beginPath(); ctx.arc(35, headY - 5, 8, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
            ctx.fillStyle = 'black';
            ctx.beginPath(); ctx.arc(18, headY - 5, 3, 0, Math.PI * 2); ctx.fill();
            ctx.beginPath(); ctx.arc(38, headY - 5, 3, 0, Math.PI * 2); ctx.fill();

            ctx.lineWidth = 2; ctx.beginPath();
            if (p.kickTimer > 0) { ctx.arc(25, headY + 20, 8, 0, Math.PI * 2); ctx.fillStyle = '#7f1d1d'; ctx.fill(); } 
            else { ctx.arc(25, headY + 15, 10, 0, Math.PI); }
            ctx.stroke();
            ctx.restore();
        }

        function drawBall(ball) {
            localBallHistory.forEach((pos, index) => {
                const alpha = 1 - (index / localBallHistory.length);
                ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.4})`;
                ctx.beginPath(); ctx.arc(pos.x, pos.y, ball.radius * (1 - index * 0.05), 0, Math.PI * 2); ctx.fill();
            });

            ctx.save(); ctx.translate(ball.x, ball.y); ctx.rotate(ball.rotation);
            ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(0, 0, ball.radius, 0, Math.PI * 2); ctx.fill();
            
            const grad = ctx.createRadialGradient(-5, -5, 2, 0, 0, ball.radius);
            grad.addColorStop(0, 'rgba(255,255,255,0.9)'); grad.addColorStop(1, 'rgba(0,0,0,0.4)');
            ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(0, 0, ball.radius, 0, Math.PI * 2); ctx.fill();

            ctx.strokeStyle = '#1e3a8a'; ctx.lineWidth = 3; ctx.beginPath();
            ctx.moveTo(-10, -10); ctx.lineTo(10, -10); ctx.lineTo(15, 5); ctx.lineTo(0, 15); ctx.lineTo(-15, 5); ctx.closePath(); ctx.stroke();
            ctx.restore();
        }

        function draw() {
            if (!serverData) { requestAnimationFrame(draw); return; }
            ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);
            
            drawBackground();
            drawGoals();
            drawPlayer(serverData.p1);
            drawPlayer(serverData.p2);
            drawBall(serverData.ball);

            if (serverData.goal_state) {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.5)'; ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
                ctx.font = '900 80px "Arial Black", sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                ctx.fillStyle = '#fbbf24'; ctx.strokeStyle = 'black'; ctx.lineWidth = 8;
                ctx.strokeText('GOL!', CANVAS_W / 2, CANVAS_H / 2); ctx.fillText('GOL!', CANVAS_W / 2, CANVAS_H / 2);
            }
            requestAnimationFrame(draw);
        }
        draw();
    </script>
</body>
</html>
"""

# --- API YÖNLENDİRMELERİ ---
@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/uploads/<filename>')
def uploaded_file(filename): return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/state')
def get_state(): return jsonify(state)

@app.route('/api/key', methods=['POST'])
def handle_key():
    data = request.json
    room = state["rooms"][data['room']]
    if data['player'] == 'p1': room['keys_p1'][data['key']] = data['state']
    elif data['player'] == 'p2': room['keys_p2'][data['key']] = data['state']
    return jsonify({"ok": True})

@app.route('/api/room_action', methods=['POST'])
def room_action():
    data = request.json
    room = state["rooms"][data['room']]
    action, role = data['action'], data.get('role')

    if action == 'join':
        if role == 'p1': room['p1_active'] = True
        elif role == 'p2': room['p2_active'] = True
    elif action == 'start':
        if room['p1_active'] and room['p2_active']: room['game_active'] = True
    elif action == 'reset':
        reset_positions(room)
        room['s1'] = 0; room['s2'] = 0; room['time_left'] = 88; room['game_active'] = False
    elif action == 'exit':
        if role == 'p1': room['p1_active'] = False
        elif role == 'p2': room['p2_active'] = False
        room['game_active'] = False
    return jsonify({"ok": True})

@app.route('/api/send', methods=['POST'])
def send():
    data = request.json
    data['id'], data['ip'] = str(uuid.uuid4()), request.remote_addr
    state["global_chat"].append(data)
    if len(state["global_chat"]) > 100: state["global_chat"].pop(0)
    return jsonify({"ok": True})

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        filename = str(uuid.uuid4()) + ext
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        
        mime_type, _ = mimetypes.guess_type(filename)
        msg_type = "file"
        if mime_type:
            if mime_type.startswith('image'): msg_type = "image"
            elif mime_type.startswith('video'): msg_type = "video"
                
        state["global_chat"].append({"id": str(uuid.uuid4()), "ip": request.remote_addr, "user": request.form['user'], "text": filename, "original_name": file.filename, "room": request.form['room'], "type": msg_type})
    return jsonify({"ok": True})

if __name__ == '__main__':
    print("🚀 MODERN KAFA TOPU SUNUCUSU BAŞLADI!")
    print("👉 Oyuncular için adres: http://192.168.1.X:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
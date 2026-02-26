"""
MANPADS WebSocket Server - Fast Mode
Read file and broadcast, with envData injection
"""
import asyncio
import websockets
import http.server
import socketserver
import os
import threading
import json
import subprocess

PORT_HTTP = 8080
PORT_WS = 8765

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BUILD_DIR = os.path.join(PROJECT_DIR, "build", "Release")
JSON_PATH = os.path.join(BUILD_DIR, "tracking_data.json")

clients = set()
last_content = ""
last_enriched = ""

# Load scenes.json for environmentData injection
# Pre-build injection snippets for each scene to avoid per-frame JSON parsing
scenes_env = {}
scenes_inject_snippet = {}
try:
    with open(os.path.join(PROJECT_DIR, 'scenes.json'), 'r', encoding='utf-8') as f:
        scenes_cfg = json.load(f)
    for i, s in enumerate(scenes_cfg.get('scenes', []), 1):
        env = s.get('environmentData', '')
        scenes_env[i] = env
        # Pre-build the string snippet: ,"envData":"..."
        scenes_inject_snippet[i] = ',"envData":"' + env + '"'
    print(f"[Scenes] Loaded {len(scenes_env)} scene(s) from scenes.json")
except Exception as e:
    print(f"[Scenes] Warning: Could not load scenes.json: {e}")

def inject_env_data_fast(raw_json):
    """Fast envData injection using string manipulation instead of JSON parse/stringify"""
    try:
        # Find "scene":N to get scene id
        idx = raw_json.find('"scene":')
        if idx == -1:
            return raw_json
        num_start = idx + 8
        num_end = num_start
        while num_end < len(raw_json) and raw_json[num_end].isdigit():
            num_end += 1
        scene_id = int(raw_json[num_start:num_end])

        if scene_id in scenes_inject_snippet and '"envData"' not in raw_json:
            # Insert snippet before the last }
            last_brace = raw_json.rfind('}')
            return raw_json[:last_brace] + scenes_inject_snippet[scene_id] + '}'
    except:
        pass
    return raw_json

def send_key_to_tracker(key):
    """Uses PowerShell to send a keystroke to the C++ console window."""
    def _run():
        cmd = f"powershell -noprofile -command \"$w=New-Object -ComObject WScript.Shell; if($w.AppActivate('MANPADS_Tracker_Window')){{$w.SendKeys('{key}')}}\""
        subprocess.run(cmd, shell=True)
    threading.Thread(target=_run, daemon=True).start()

async def broadcast_loop():
    """Read file and broadcast on change"""
    global last_content, last_enriched

    while True:
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                content = f.read()

            if content and content != last_content and clients:
                last_content = content
                last_enriched = inject_env_data_fast(content)
                await asyncio.gather(
                    *[c.send(last_enriched) for c in clients.copy()],
                    return_exceptions=True
                )
        except:
            pass

        await asyncio.sleep(0.001)  # 1ms polling

async def ws_handler(websocket):
    """WebSocket handler"""
    clients.add(websocket)
    print(f"[+] Client connected ({len(clients)} total)")
    try:
        if last_enriched:
            await websocket.send(last_enriched)
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get('type') == 'keypress':
                    send_key_to_tracker(data.get('key'))
            except:
                pass
    except:
        pass
    finally:
        clients.discard(websocket)
        print(f"[-] Client disconnected ({len(clients)} total)")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SCRIPT_DIR, **kw)
    def do_GET(self):
        if self.path.split('?')[0] in ['/', '/index.html']:
            self.path = '/viewer_ws.html'
        return super().do_GET()
    def log_message(self, *a):
        pass

def run_http():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', PORT_HTTP), Handler) as s:
        s.serve_forever()

async def main():
    threading.Thread(target=run_http, daemon=True).start()
    print("="*50)
    print("MANPADS WebSocket Server (Fast Mode)")
    print("="*50)
    print(f"  HTTP: http://localhost:{PORT_HTTP}")
    print(f"  WS:   ws://localhost:{PORT_WS}")
    print("="*50)

    async with websockets.serve(ws_handler, "0.0.0.0", PORT_WS):
        await asyncio.gather(asyncio.Future(), broadcast_loop())

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")

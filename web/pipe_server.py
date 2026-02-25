"""
FIM92 Pipe WebSocket Server
Read C++ output from stdin, broadcast to WebSocket
Zero file I/O!

Usage: TrackingMinimalDemo.exe --json | python pipe_server.py
"""
import asyncio
import websockets
import http.server
import socketserver
import sys
import os
import threading
import json
import subprocess

PORT_HTTP = 8080
PORT_WS = 8765

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
clients = set()
latest_data = None

# Load scenes.json for environmentData injection
scenes_env = {}
try:
    with open(os.path.join(PROJECT_DIR, 'scenes.json'), 'r', encoding='utf-8') as f:
        scenes_cfg = json.load(f)
    for i, s in enumerate(scenes_cfg.get('scenes', []), 1):
        scenes_env[i] = s.get('environmentData', '')
    print(f"[Scenes] Loaded {len(scenes_env)} scene(s) from scenes.json")
except Exception as e:
    print(f"[Scenes] Warning: Could not load scenes.json: {e}")

def send_key_to_tracker(key):
    """
    Uses PowerShell to send a keystroke to the C++ console window.
    Requires the window title to be 'FIM92_Tracker_Window'.
    """
    def _run():
        # 使用 PowerShell 發送按鍵 (確保修復 cscript /C 錯誤)
        cmd = f"powershell -noprofile -command \"$w=New-Object -ComObject WScript.Shell; if($w.AppActivate('FIM92_Tracker_Window')){{$w.SendKeys('{key}')}}\""
        subprocess.run(cmd, shell=True)
    
    # 在獨立執行緒中執行，避免卡住 WebSocket 廣播迴圈
    threading.Thread(target=_run, daemon=True).start()

async def broadcast(data):
    if clients:
        await asyncio.gather(
            *[c.send(data) for c in clients.copy()],
            return_exceptions=True
        )

def inject_env_data(raw_json):
    """Inject environmentData from scenes.json into tracker JSON"""
    try:
        data = json.loads(raw_json)
        scene_id = data.get('scene')
        if scene_id and scene_id in scenes_env and 'envData' not in data:
            data['envData'] = scenes_env[scene_id]
            return json.dumps(data, separators=(',', ':'))
    except:
        pass
    return raw_json

def stdin_reader(loop):
    """Read stdin using OS-level unbuffered read for maximum throughput"""
    global latest_data
    fd = sys.stdin.buffer.fileno()
    remainder = b""
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        remainder += chunk
        while b"\n" in remainder:
            line_bytes, remainder = remainder.split(b"\n", 1)
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if line.startswith('{') and line.endswith('}'):
                line = inject_env_data(line)
                latest_data = line
                asyncio.run_coroutine_threadsafe(broadcast(line), loop)

async def ws_handler(websocket):
    """WebSocket handler - new API (websockets 10+)"""
    clients.add(websocket)
    print(f"[+] Client ({len(clients)})")
    try:
        if latest_data:
            await websocket.send(latest_data)
        async for message in websocket:
            # Handle incoming commands from Web
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
        print(f"[-] Client ({len(clients)})")

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
    loop = asyncio.get_event_loop()

    # HTTP server
    threading.Thread(target=run_http, daemon=True).start()

    # Stdin reader
    threading.Thread(target=stdin_reader, args=(loop,), daemon=True).start()

    print("="*50)
    print("FIM92 Pipe WebSocket Server")
    print("="*50)
    print(f"  HTTP: http://localhost:{PORT_HTTP}")
    print(f"  WS:   ws://localhost:{PORT_WS}")
    print("  Waiting for stdin...")
    print("="*50)

    async with websockets.serve(ws_handler, "0.0.0.0", PORT_WS):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")

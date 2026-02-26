"""
MANPADS Pipe WebSocket Server
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
new_data_event = None  # asyncio.Event, set from stdin_reader thread

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
    Requires the window title to be 'MANPADS_Tracker_Window'.
    """
    def _run():
        # 使用 PowerShell 發送按鍵 (確保修復 cscript /C 錯誤)
        cmd = f"powershell -noprofile -command \"$w=New-Object -ComObject WScript.Shell; if($w.AppActivate('MANPADS_Tracker_Window')){{$w.SendKeys('{key}')}}\""
        subprocess.run(cmd, shell=True)
    
    # 在獨立執行緒中執行，避免卡住 WebSocket 廣播迴圈
    threading.Thread(target=_run, daemon=True).start()

def inject_env_data(raw_json):
    """Inject environmentData using fast string operation (no json.loads/dumps)"""
    try:
        # Quick extract scene id: find "scene":N
        idx = raw_json.find('"scene":')
        if idx == -1 or 'envData' in raw_json:
            return raw_json
        num_start = idx + 8
        num_end = num_start
        while num_end < len(raw_json) and raw_json[num_end].isdigit():
            num_end += 1
        scene_id = int(raw_json[num_start:num_end])
        env = scenes_env.get(scene_id)
        if env:
            # Insert envData before closing }
            return raw_json[:-1] + ',"envData":"' + env + '"}'
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
        # Process all complete lines, keep only the last valid JSON
        last_valid = None
        while b"\n" in remainder:
            line_bytes, remainder = remainder.split(b"\n", 1)
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if line.startswith('{') and line.endswith('}'):
                last_valid = line
        # Only signal once per os.read() chunk with the latest data
        if last_valid:
            latest_data = inject_env_data(last_valid)
            loop.call_soon_threadsafe(new_data_event.set)

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

async def broadcast_loop():
    """Broadcast latest data whenever stdin_reader signals new data"""
    while True:
        await new_data_event.wait()
        new_data_event.clear()
        data = latest_data
        if data and clients:
            await asyncio.gather(
                *[c.send(data) for c in clients.copy()],
                return_exceptions=True
            )

async def main():
    global new_data_event
    loop = asyncio.get_event_loop()
    new_data_event = asyncio.Event()

    # HTTP server
    threading.Thread(target=run_http, daemon=True).start()

    # Stdin reader
    threading.Thread(target=stdin_reader, args=(loop,), daemon=True).start()

    print("="*50)
    print("MANPADS Pipe WebSocket Server")
    print("="*50)
    print(f"  HTTP: http://localhost:{PORT_HTTP}")
    print(f"  WS:   ws://localhost:{PORT_WS}")
    print("  Waiting for stdin...")
    print("="*50)

    # Start broadcast loop
    asyncio.create_task(broadcast_loop())

    async with websockets.serve(ws_handler, "0.0.0.0", PORT_WS):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")

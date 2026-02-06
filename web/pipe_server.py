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

PORT_HTTP = 8080
PORT_WS = 8765

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
clients = set()
latest_data = None

async def broadcast(data):
    if clients:
        await asyncio.gather(
            *[c.send(data) for c in clients.copy()],
            return_exceptions=True
        )

def stdin_reader(loop):
    """Read stdin in a separate thread"""
    global latest_data
    for line in sys.stdin:
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            latest_data = line
            asyncio.run_coroutine_threadsafe(broadcast(line), loop)

async def ws_handler(websocket):
    """WebSocket handler - new API (websockets 10+)"""
    clients.add(websocket)
    print(f"[+] Client ({len(clients)})")
    try:
        if latest_data:
            await websocket.send(latest_data)
        async for _ in websocket:
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

    async with websockets.serve(ws_handler, "localhost", PORT_WS):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")

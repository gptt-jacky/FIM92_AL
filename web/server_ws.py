"""
FIM92 WebSocket Server - Fast Mode
Read file and broadcast, no cache
"""
import asyncio
import websockets
import http.server
import socketserver
import os
import threading

PORT_HTTP = 8080
PORT_WS = 8765

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
BUILD_DIR = os.path.join(PROJECT_DIR, "build", "Release")
JSON_PATH = os.path.join(BUILD_DIR, "tracking_data.json")

clients = set()
last_content = ""

async def broadcast_loop():
    """Read and broadcast without any checks"""
    global last_content

    while True:
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                content = f.read()

            # Only broadcast if content changed
            if content != last_content and clients:
                last_content = content
                await asyncio.gather(
                    *[c.send(content) for c in clients.copy()],
                    return_exceptions=True
                )
        except:
            pass

        await asyncio.sleep(0.001)  # 1ms = 1000Hz

async def ws_handler(websocket):
    """WebSocket handler - new API (websockets 10+)"""
    clients.add(websocket)
    print(f"[+] Client connected ({len(clients)} total)")
    try:
        if last_content:
            await websocket.send(last_content)
        async for _ in websocket:
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
    print("FIM92 WebSocket Server (Fast Mode)")
    print("="*50)
    print(f"  HTTP: http://localhost:{PORT_HTTP}")
    print(f"  WS:   ws://localhost:{PORT_WS}")
    print("="*50)

    async with websockets.serve(ws_handler, "localhost", PORT_WS):
        await asyncio.gather(asyncio.Future(), broadcast_loop())

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")

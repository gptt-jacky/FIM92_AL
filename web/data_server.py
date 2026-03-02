"""
MANPADS Data Server — High-speed stdin to WebSocket forwarder
For software team integration. No HTTP server, no web viewer.

Usage:
  TrackingMinimalDemo.exe --json scenes.json | python data_server.py
  TrackingMinimalDemo.exe --json scenes.json | python data_server.py --host 192.168.1.100 --port 8765
"""
import asyncio
import websockets
import sys
import time
import threading
import re
import argparse
import json
import subprocess
from datetime import datetime

# ============================================================
# WebSocket Server Settings (defaults, can override via args)
# ============================================================
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765

clients = set()
latest_data = None
loop_ref = None
data_event = None  # asyncio.Event for signaling new data

# Stats
tx_count = 0
rx_count = 0
tx_fps = 0
rx_fps = 0

# Tag = Type directly (A/B/C/D set in AntilatencyService)
VALID_TAGS = {"A", "B", "C", "D"}

# IO7 state tracking: {"A": "0", "B": "1", ...}
io7_state = {}

# Pre-compile regex for fast extraction from C++ JSON
_tracker_re = re.compile(
    r'\{"id":(\d+),'
    r'"tag":"([^"]*)",'
    r'"type":"([^"]*)",'
    r'"number":"[^"]*",'
    r'"px":([^,]+),'
    r'"py":([^,]+),'
    r'"pz":([^,]+),'
    r'"rx":([^,]+),'
    r'"ry":([^,]+),'
    r'"rz":([^,]+),'
    r'"rw":([^,]+),'
    r'"stability":\d+,'
    r'"io":"([^"]*)"'
    r'\}'
)


def send_key_to_tracker(key):
    """
    Uses PowerShell to send a keystroke to the C++ console window.
    Requires the window title to be 'MANPADS_DataServer' (set by RunDataServer.bat).
    """
    def _run():
        try:
            ps_cmd = (
                "$w=New-Object -ComObject WScript.Shell; "
                f"if($w.AppActivate('MANPADS_DataServer')){{$w.SendKeys('{key}')}}"
            )
            subprocess.run(
                ["powershell", "-noprofile", "-command", ps_cmd],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            sys.stderr.write(f"\n[SendKey Error] {e}\n")
    threading.Thread(target=_run, daemon=True).start()


def transform_fast(line):
    """Fast string-level transform via regex, no json.loads/json.dumps."""
    global io7_state
    matches = _tracker_re.findall(line)
    if not matches and '"trackers":[]' not in line:
        return None

    parts = []
    for m in matches:
        tid, tag, ttype, px, py, pz, rx, ry, rz, rw, io = m
        if not tag:
            tag = ttype if ttype in VALID_TAGS else "?" + tid
        # Track IO7 state (io[6]) per tag
        if len(io) > 6 and tag in VALID_TAGS:
            io7_state[tag] = io[6]
        parts.append(
            f'{{"tag":"{tag}","px":{px},"py":{py},"pz":{pz},'
            f'"rx":{rx},"ry":{ry},"rz":{rz},"rw":{rw},"io":"{io}"}}'
        )

    return '{"trackers":[' + ",".join(parts) + "]}"


def stdin_reader():
    """Read C++ JSON from stdin using raw OS-level read to bypass Python buffering."""
    global latest_data, rx_count
    import os
    fd = sys.stdin.buffer.fileno()
    remainder = b""
    while True:
        chunk = os.read(fd, 65536)  # unbuffered OS read, up to 64KB at once
        if not chunk:
            break
        remainder += chunk
        while b"\n" in remainder:
            line_bytes, remainder = remainder.split(b"\n", 1)
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line.startswith("{"):
                continue
        transformed = transform_fast(line)
        if transformed:
            latest_data = transformed
            rx_count += 1
            # Signal the async broadcast loop (no sleep, instant wakeup)
            if loop_ref and data_event:
                loop_ref.call_soon_threadsafe(data_event.set)


async def broadcast_loop():
    """Broadcast latest data to all clients, triggered by event signal."""
    global tx_count
    while True:
        await data_event.wait()
        data_event.clear()

        current = latest_data
        if current and clients:
            tx_count += 1
            await asyncio.gather(
                *[c.send(current) for c in clients.copy()],
                return_exceptions=True
            )


async def ws_handler(websocket):
    """WebSocket handler"""
    clients.add(websocket)
    remote = websocket.remote_address
    addr = f"{remote[0]}:{remote[1]}"
    print(f"[+] Client connected: {addr} (total: {len(clients)})")
    try:
        if latest_data:
            await websocket.send(latest_data)
        async for message in websocket:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"  [{ts}] {addr} >> {message}")
            try:
                data = json.loads(message)
                io7_cmd = data.get("io7", "")
                if io7_cmd in ("A1", "A0", "B1", "B0"):
                    tag = io7_cmd[0]      # "A" or "B"
                    desired = io7_cmd[1]  # "1" or "0"
                    current = io7_state.get(tag, "0")
                    if current != desired:
                        send_key_to_tracker(tag.lower())
            except Exception:
                pass
    except Exception:
        pass
    finally:
        clients.discard(websocket)
        print(f"[-] Client disconnected: {addr} (total: {len(clients)})")


def stats_reporter():
    """Print TX/RX rate every second"""
    global tx_count, rx_count, tx_fps, rx_fps
    while True:
        time.sleep(1.0)
        tx_fps = tx_count
        rx_fps = rx_count
        tx_count = 0
        rx_count = 0
        n = len(clients)
        status = f"\r  [RX] {rx_fps}/sec  [TX] {tx_fps}/sec  |  Clients: {n}    "
        sys.stderr.write(status)
        sys.stderr.flush()


async def main(host, port):
    global loop_ref, data_event

    loop_ref = asyncio.get_event_loop()
    data_event = asyncio.Event()

    # Start stdin reader thread
    threading.Thread(target=stdin_reader, daemon=True).start()

    # Start stats reporter thread
    threading.Thread(target=stats_reporter, daemon=True).start()

    # Start broadcast loop
    asyncio.ensure_future(broadcast_loop())

    print("=" * 50)
    print("MANPADS Data Server (for Software Team)")
    print("=" * 50)
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  URI:  ws://{host}:{port}")
    print("  Waiting for tracking data from stdin...")
    print("=" * 50)

    async with websockets.serve(ws_handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MANPADS Data Server")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Bind address (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"WebSocket port (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        print("\nStopped.")

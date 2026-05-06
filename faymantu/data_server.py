# MANPADS Data Server — High-speed stdin to WebSocket forwarder
# 最後更新: 2026/05/06
"""
For software team integration. No HTTP server, no web viewer.
IO control via Named Pipe (MANPADS_IO).

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

# Tag = Type directly (A/B/C/D/E/F set in AntilatencyService)
VALID_TAGS = {"A", "B", "C", "D", "E", "F"}

# IO7 state tracking: {"A": "0", "B": "1", ...}
io7_state = {}

# IO8 state tracking (Tag B only): {"B": "0"}
io8_state = {}

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


PIPE_NAME = r'\\.\pipe\MANPADS_IO'
_pipe_handle = None
_pipe_lock = threading.Lock()

# Windows API via ctypes for Named Pipe access
import ctypes
from ctypes import wintypes
_kernel32 = ctypes.windll.kernel32
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p
]
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


def _get_pipe():
    """Get or open the Named Pipe connection to C++ via Windows API."""
    global _pipe_handle
    if _pipe_handle is not None:
        return _pipe_handle
    handle = _kernel32.CreateFileW(
        PIPE_NAME,
        GENERIC_WRITE,
        0, None,
        OPEN_EXISTING,
        0, None
    )
    if handle == INVALID_HANDLE_VALUE:
        err = _kernel32.GetLastError()
        sys.stderr.write(f"\n[Pipe] Cannot connect (error={err})\n")
        return None
    _pipe_handle = handle
    print(f"[Pipe] Connected to {PIPE_NAME}")
    return _pipe_handle


def send_io_command(cmd_json):
    """Send IO command to C++ via Named Pipe. cmd_json e.g. '{"io7":"A1"}'"""
    global _pipe_handle
    with _pipe_lock:
        pipe = _get_pipe()
        if pipe is None:
            return
        data = (cmd_json + '\n').encode('utf-8')
        written = wintypes.DWORD(0)
        ok = _kernel32.WriteFile(
            pipe, data, len(data),
            ctypes.byref(written), None
        )
        if not ok:
            err = _kernel32.GetLastError()
            sys.stderr.write(f"\n[Pipe] Write error (error={err})\n")
            _kernel32.CloseHandle(pipe)
            _pipe_handle = None


def transform_fast(line):
    """Fast string-level transform via regex, no json.loads/json.dumps."""
    global io7_state, io8_state
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
        # Track IO8 state (io[7]) for Tag B
        if len(io) > 7 and tag == "B":
            io8_state[tag] = io[7]
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
                if io7_cmd in ("A1", "A0"):
                    send_io_command(f'{{"io7":"{io7_cmd}"}}')
                ioa3_cmd = data.get("ioa3", "")
                if ioa3_cmd in ("A0", "A1", "A2"):
                    send_io_command(f'{{"ioa3":"{ioa3_cmd}"}}')
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

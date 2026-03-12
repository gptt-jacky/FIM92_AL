"""
MANPADS WebSocket Client — verify raw JSON data from data_server.py

Usage:
  python ws_client.py
  python ws_client.py --url ws://192.168.1.100:8765
"""
import asyncio
import websockets
import sys
import os
import time
import argparse
import threading
import json
import msvcrt

CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

io7_state = {"A": False, "B": False}
io8_state = {"B": False}
ws_ref = None
loop_ref = None


def keyboard_reader():
    """Read keyboard input: A/B toggle IO7, C toggle IO8 (Tag B)."""
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            try:
                key = ch.decode().upper()
            except Exception:
                continue
            if key in ("A", "B") and ws_ref and loop_ref:
                io7_state[key] = not io7_state[key]
                val = "1" if io7_state[key] else "0"
                cmd = json.dumps({"io7": f"{key}{val}"})
                asyncio.run_coroutine_threadsafe(ws_ref.send(cmd), loop_ref)
            elif key == "C" and ws_ref and loop_ref:
                io8_state["B"] = not io8_state["B"]
                val = "1" if io8_state["B"] else "0"
                cmd = json.dumps({"io8": f"B{val}"})
                asyncio.run_coroutine_threadsafe(ws_ref.send(cmd), loop_ref)
        time.sleep(0.05)


async def main(url):
    global ws_ref, loop_ref

    if sys.platform == "win32":
        os.system("")

    loop_ref = asyncio.get_running_loop()

    print(f"Connecting to {url} ...")
    frame_count = 0
    fps = 0
    fps_counter = 0
    fps_time = time.time()

    async with websockets.connect(url) as ws:
        ws_ref = ws
        print("Connected!\n")

        # Start keyboard reader thread
        threading.Thread(target=keyboard_reader, daemon=True).start()

        async for message in ws:
            frame_count += 1
            fps_counter += 1
            now = time.time()
            if now - fps_time >= 1.0:
                fps = int(fps_counter / (now - fps_time))
                fps_counter = 0
                fps_time = now

            # Throttle display
            if frame_count % 25 != 0:
                continue

            io7a = "ON" if io7_state["A"] else "OFF"
            io7b = "ON" if io7_state["B"] else "OFF"
            io8b = "ON" if io8_state["B"] else "OFF"
            header = f"  RX: {fps} msg/sec  |  Frame: #{frame_count}  |  Size: {len(message)} bytes"
            output = (
                CLEAR_SCREEN
                + "=" * 70 + "\n"
                + "  MANPADS WebSocket Client\n"
                + "=" * 70 + "\n"
                + header + "\n"
                + "-" * 70 + "\n\n"
                + message + "\n\n"
                + "-" * 70 + "\n"
                + f"  [A] IO7-A: {io7a}  [B] IO7-B: {io7b}  [C] IO8-B: {io8b}  |  Ctrl+C to quit\n"
            )
            sys.stdout.write(output)
            sys.stdout.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MANPADS WebSocket Client")
    parser.add_argument("--url", default="ws://localhost:8765",
                        help="WebSocket URL (default: ws://localhost:8765)")
    args = parser.parse_args()

    print(HIDE_CURSOR, end="", flush=True)
    try:
        asyncio.run(main(args.url))
    except KeyboardInterrupt:
        print(f"\n{SHOW_CURSOR}Disconnected.")
    except Exception as e:
        print(f"\n{SHOW_CURSOR}Error: {e}")

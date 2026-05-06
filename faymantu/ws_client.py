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

io7_state = {"A": False}
ioa3_level = {"A": 0}  # 0=off, 1=中震動, 2=強震動
ws_ref = None
loop_ref = None


def keyboard_reader():
    """Read keyboard input: A toggle IO7-A, G cycle IOA3-A (off/中震動/強震動)."""
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            try:
                key = ch.decode().upper()
            except Exception:
                continue
            if key == "A" and ws_ref and loop_ref:
                io7_state["A"] = not io7_state["A"]
                val = "1" if io7_state["A"] else "0"
                cmd = json.dumps({"io7": f"A{val}"})
                asyncio.run_coroutine_threadsafe(ws_ref.send(cmd), loop_ref)
            elif key == "G" and ws_ref and loop_ref:
                ioa3_level["A"] = (ioa3_level["A"] + 1) % 3
                lvl = ioa3_level["A"]
                cmd = json.dumps({"ioa3": f"A{lvl}"})
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
            ioa3_labels = ["OFF", "中震動", "強震動"]
            ioa3a = ioa3_labels[ioa3_level["A"]]
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
                + f"  [A] 允許後座力: {io7a}  [G] IOA3震動: {ioa3a}  |  Ctrl+C to quit\n"
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

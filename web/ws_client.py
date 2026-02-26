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

CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


async def main(url):
    if sys.platform == "win32":
        os.system("")

    print(f"Connecting to {url} ...")
    frame_count = 0
    fps = 0
    fps_counter = 0
    fps_time = time.time()

    async with websockets.connect(url) as ws:
        print("Connected!\n")
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
                + "  Ctrl+C to quit\n"
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

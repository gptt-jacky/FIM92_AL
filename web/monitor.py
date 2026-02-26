"""
MANPADS Console Monitor — 原地刷新顯示所有 Tracker + IO 狀態
從 stdin 讀取 C++ JSON 輸出，解析後以清晰的多行格式顯示

Usage: TrackingMinimalDemo.exe --json scenes.json | python monitor.py
"""
import sys
import os
import json
import time

# ANSI escape codes
CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
DIM = "\033[2m"

# Tag = Type directly (A/B/C/D)
TAG_INFO = {
    "A": ("A", "刺針"),
    "B": ("B", "頭盔"),
    "C": ("C", "望遠鏡"),
    "D": ("D", "對講機"),
}

IO_LABELS = ["IO1", "IO2", "IOA3", "IOA4", "IO5", "IO6", "IO7*", "IO8"]


def format_io_detail(io_inputs, io7out):
    """Format IO from the global io object (array of 0/1 + io7out bool)"""
    bits = ""
    for i, val in enumerate(io_inputs):
        bits += str(val)
    # Insert IO7 output between IO6 and IO8
    bits = bits[:6] + ("1" if io7out else "0") + bits[6:]
    return bits


def format_io_bar(io_str):
    """Format IO bits as a visual bar with labels"""
    parts = []
    for i, ch in enumerate(io_str):
        label = IO_LABELS[i]
        if ch == "1":
            parts.append(f"{GREEN}{label}=H{RESET}")
        else:
            parts.append(f"{DIM}{label}=L{RESET}")
    return "  ".join(parts)


def render(data, frame_count, fps):
    """Render the full display"""
    lines = []
    scene = data.get("scene", "?")
    scene_name = data.get("sceneName", "?")
    trackers = data.get("trackers", [])
    io_global = data.get("io", {})

    lines.append(f"{BOLD}{'=' * 70}{RESET}")
    lines.append(f"{BOLD}  MANPADS Tracking Monitor{RESET}    Scene: [{scene}] {scene_name}    FPS: {fps}")
    lines.append(f"{BOLD}{'=' * 70}{RESET}")

    # ---- Trackers ----
    if not trackers:
        lines.append(f"  {DIM}No trackers connected{RESET}")
    else:
        for t in trackers:
            tid = t.get("id", "?")
            ttype = t.get("type", "")
            tag = t.get("tag", ttype if ttype in TAG_INFO else "?")
            tag_info = TAG_INFO.get(tag)
            device_name = tag_info[1] if tag_info else ttype
            stability = t.get("stability", 0)
            io_bits = t.get("io", "--------")

            # Stability color
            if stability >= 6:
                s_color = GREEN
                s_label = "Tracking"
            elif stability >= 3:
                s_color = YELLOW
                s_label = "Inertial"
            else:
                s_color = RED
                s_label = "Init"

            lines.append("")
            lines.append(f"  {BOLD}{CYAN}[{tag}]{RESET} {device_name}  (T{tid}, type={ttype})  {s_color}S:{stability} {s_label}{RESET}")
            lines.append(f"      Pos: ({t.get('px', 0):+9.4f}, {t.get('py', 0):+9.4f}, {t.get('pz', 0):+9.4f})")
            lines.append(f"      Rot: ({t.get('rx', 0):+9.4f}, {t.get('ry', 0):+9.4f}, {t.get('rz', 0):+9.4f}, {t.get('rw', 0):+9.4f})")
            lines.append(f"      IO:  {io_bits}   {format_io_bar(io_bits)}")

    # ---- Global IO summary ----
    lines.append("")
    lines.append(f"  {BOLD}{'─' * 66}{RESET}")

    if io_global.get("connected"):
        io_type = io_global.get("type", "")
        io_inputs = io_global.get("inputs", [])
        io7out = io_global.get("io7out", False)
        if io_inputs:
            global_bits = format_io_detail(io_inputs, io7out)
            lines.append(f"  Global IO [{io_type}]: {global_bits}   {format_io_bar(global_bits)}")
        else:
            lines.append(f"  Global IO [{io_type}]: connected (no data)")
    else:
        lines.append(f"  {DIM}Global IO: not connected{RESET}")

    hw_count = sum(1 for t in trackers if t.get("io", "00000000") != "00000000")
    total = len(trackers)
    lines.append(f"  HW Ext Modules with signal: {hw_count}/{total}")

    lines.append("")
    lines.append(f"  {DIM}Frame #{frame_count}  |  [O] Toggle IO7  [1-9] Scene  [Q] Quit{RESET}")

    return "\n".join(lines)


def main():
    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("")

    sys.stderr.write(f"{HIDE_CURSOR}")
    sys.stderr.flush()

    frame_count = 0
    fps = 0
    fps_counter = 0
    fps_time = time.time()

    try:
        import os as _os
        fd = sys.stdin.buffer.fileno()
        remainder = b""
        data = None
        while True:
            chunk = _os.read(fd, 65536)
            if not chunk:
                break
            remainder += chunk
            while b"\n" in remainder:
                line_bytes, remainder = remainder.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not (line.startswith("{") and line.endswith("}")):
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                frame_count += 1
                fps_counter += 1
                now = time.time()
                elapsed = now - fps_time
                if elapsed >= 1.0:
                    fps = int(fps_counter / elapsed)
                    fps_counter = 0
                    fps_time = now

                # Throttle display to ~30 fps for readability
                if frame_count % 16 != 0:
                    continue

                output = render(data, frame_count, fps)
                sys.stderr.write(CLEAR_SCREEN + output + "\n")
                sys.stderr.flush()

    except KeyboardInterrupt:
        pass
    finally:
        sys.stderr.write(f"{SHOW_CURSOR}\n")
        sys.stderr.flush()


if __name__ == "__main__":
    main()

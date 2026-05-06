"""
MANPADS Console Monitor — 原地刷新顯示所有 Tracker + IO 狀態
從 stdin 讀取 C++ JSON 輸出，解析後以清晰的多行格式顯示

Usage: TrackingMinimalDemo.exe --json scenes.json | python monitor.py
"""
# 最後更新: 2026/05/06
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

# Tag = Type directly (A/B/C/D/E/F/G)
TAG_INFO = {
    "A": ("A", "刺針"),
    "B": ("B", "主射手頭盔震動器"),
    "C": ("C", "望遠鏡"),
    "D": ("D", "對講機"),
    "E": ("E", "副射手頭盔"),
    "F": ("F", "主射手頭盔定位"),
    "G": ("G", "測試裝置"),
}

# 8-bit labels (Tags B/C/D/E/F)
IO_LABELS_8 = ["IO1", "IO2", "IOA3", "IOA4", "IO5", "IO6", "IO7*", "IO8"]
# Tag A: IOA3=震動器輸出, IOA4=天線/BCU/保險 analog decode
IO_LABELS_A = ["IO1", "IO2", "IOA3*", "IOA4(A)", "IO5", "IO6", "IO7*", "IO8"]
# Tag G diagnostic: IOA3=PWM output, IOA4=analog input
IO_LABELS_G = ["IO1", "IO2", "IOA3*", "IOA4(A)", "IO5", "IO6", "IO7*", "IO8"]
# 10-bit labels (legacy, unused)
IO_LABELS_10 = ["IO1", "IO2", "BCU", "保險", "天線", "IO5", "IO6", "IO7*", "IO8*", "IOA4*"]
# Tag A IOA4: 天線/BCU/保險 voltage ladder decode
IOA4_LEVELS_A = {
    "0": "無",
    "1": "BCU",
    "2": "保險",
    "3": "天線",
    "4": "BCU+保險",
    "5": "BCU+天線",
    "6": "保險+天線",
    "7": "BCU+保險+天線",
}
# Tag G IOA4: generic A/B/C voltage ladder decode
IOA4_LEVELS_G = {
    "0": "無",
    "1": "A",
    "2": "B",
    "3": "A+B",
    "4": "C",
    "5": "A+C",
    "6": "B+C",
    "7": "A+B+C",
}



def format_io_bar(io_str, labels=None, tag=None):
    """Format IO bits as a visual bar with labels. Tag A/G share IOA3*/IOA4(A) but use different text."""
    if labels is None:
        labels = IO_LABELS_8 if len(io_str) <= 8 else IO_LABELS_10
    ioa4_levels = IOA4_LEVELS_A if tag == "A" else IOA4_LEVELS_G
    parts = []
    for i, ch in enumerate(io_str):
        if i >= len(labels):
            break
        label = labels[i]
        if label == "IOA3*":
            if tag == "A":
                if ch == "1":
                    parts.append(f"{GREEN}{label}=中震動{RESET}")
                elif ch == "2":
                    parts.append(f"{YELLOW}{label}=強震動{RESET}")
                else:
                    parts.append(f"{DIM}{label}=OFF{RESET}")
            else:
                if ch == "1":
                    parts.append(f"{GREEN}{label}=小PWM{RESET}")
                elif ch == "2":
                    parts.append(f"{YELLOW}{label}=全輸出{RESET}")
                else:
                    parts.append(f"{DIM}{label}=OFF{RESET}")
        elif label == "IOA4(A)":
            value = ioa4_levels.get(ch, ch)
            if ch == "0":
                parts.append(f"{DIM}{label}=0/無{RESET}")
            else:
                parts.append(f"{YELLOW}{label}={ch}/{value}{RESET}")
        elif label == "IOA4*":
            if ch == "1":
                parts.append(f"{GREEN}{label}=小震動{RESET}")
            elif ch == "2":
                parts.append(f"{YELLOW}{label}=大震動{RESET}")
            else:
                parts.append(f"{DIM}{label}=OFF{RESET}")
        else:
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
    analog = data.get("analog", {})

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
            if tag == "A" and len(io_bits) == 8:
                labels = IO_LABELS_A
            elif tag == "G" and len(io_bits) == 8:
                labels = IO_LABELS_G
            else:
                labels = None
            lines.append(f"      IO:  {io_bits}   {format_io_bar(io_bits, labels, tag=tag)}")
            analog_info = analog.get(tag, {})
            if "ioa4" in analog_info:
                norm = analog_info.get("ioa4", 0.0)
                lines.append(f"      IOA4: {YELLOW}{norm:.3f}{RESET}")

    lines.append("")
    lines.append(f"  {BOLD}{'─' * 66}{RESET}")

    if analog:
        for tag, values in analog.items():
            norm = values.get("ioa4", 0.0)
            lines.append(f"  Analog [{tag}]: IOA4={norm:.3f}")

    hw_count = sum(1 for t in trackers if t.get("io", "00000000") != "00000000")
    total = len(trackers)
    lines.append(f"  HW Ext Modules with signal: {hw_count}/{total}")

    lines.append("")
    lines.append(f"  {DIM}Frame #{frame_count}  |  [A] IO7允許後座力  [G] IOA3震動(off/中/強)  [O] 全部IO7  [1-9] Scene  [Q] Quit{RESET}")

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

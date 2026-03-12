# MANPADS 軟體組操作手冊

本文件說明如何從 MANPADS 追蹤系統取得即時 6DOF 追蹤資料（位置、旋轉、IO 狀態）。

---

## 本資料夾內容

```
faymantu/
├── SOFTWARE_GUIDE.md         ← 本文件（操作手冊）
├── RunDataServer.bat         ← 啟動 WebSocket 模式（雙擊執行）
├── RunMonitor.bat            ← 啟動 IO 訊號監控（雙擊執行）
├── RunWSClient.bat           ← WebSocket 連線測試工具（雙擊執行）
├── data_server.py            ← WebSocket 伺服器程式（自動被 BAT 呼叫）
├── monitor.py                ← IO 訊號監控程式（自動被 BAT 呼叫）
└── ws_client.py              ← 連線測試工具程式（自動被 BAT 呼叫）
```

---

## 環境需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Windows 10/11 (64-bit) |
| AntilatencyService | 4.5.0 Windows 版，[下載頁面](https://developers.antilatency.com/Software/AntilatencyService_en.html)（用於確認硬體連線狀態、更改 Tag 屬性） |
| Python | 3.8 以上，已加入系統 PATH |
| Python 套件 | `pip install websockets` |

---

# WebSocket 模式（推薦）

## Step 1：啟動 Server

### 1-1. 雙擊 `RunDataServer.bat`

會開啟一個黑色 Console 視窗，畫面如下：

```
=== MANPADS Data Server (for Software Team) ===

[Local IP Addresses]
   10.20.32.104
   192.168.1.100

  0.0.0.0 = Accept all connections (default)

Server Host [0.0.0.0]: _
```

畫面上方會自動列出本機所有 IP 位址，供 Client 端連線使用。

### 1-2. 設定 Host

| 操作 | 效果 |
|------|------|
| **直接按 Enter**（推薦） | 使用預設 `0.0.0.0`，接受任何 IP 連線 |
| 輸入畫面上列出的 IP（如 `192.168.1.100`） | 僅綁定該網卡 |
| 輸入 `127.0.0.1` | 僅允許本機連線（測試用） |

### 1-3. 設定 Port

```
Server Port [8765]: _
```

| 操作 | 效果 |
|------|------|
| **直接按 Enter**（推薦） | 使用預設 `8765` |
| 輸入其他數字 | 使用自訂 Port（需確保防火牆允許） |

### 1-4. Server 啟動完成

出現以下畫面表示已開始運行：

```
[Host] 0.0.0.0
[Port] 8765
[URI]  ws://0.0.0.0:8765

Starting...

==================================================
MANPADS Data Server (for Software Team)
==================================================
  Host: 0.0.0.0
  Port: 8765
  URI:  ws://0.0.0.0:8765
  Waiting for tracking data from stdin...
==================================================
  [RX] 128/sec  [TX] 128/sec  |  Clients: 0
```

### 1-5. Console 狀態列說明

底部會持續顯示即時狀態（每秒刷新）：

```
  [RX] 128/sec  [TX] 128/sec  |  Clients: 2
```

| 指標 | 說明 |
|------|------|
| **RX** | 從追蹤程式接收到的資料速率 |
| **TX** | 推送給 WebSocket Client 的速率 |
| **Clients** | 目前連線中的 Client 數量 |

當有 Client 連線或斷線時，也會顯示：

```
[+] Client connected: 192.168.1.50:54321 (total: 1)
[-] Client disconnected: 192.168.1.50:54321 (total: 0)
```

> **重要**：Server 執行期間請勿關閉此 Console 視窗，關閉即停止服務。

---

## Step 2：Client 連線

### 連線位址

```
ws://<Server 的 IP>:<Port>
```

**範例**：若 Server 畫面顯示 IP 為 `192.168.1.100`，Port 為預設 `8765`：

```
ws://192.168.1.100:8765
```

若 Server 和 Client 在同一台電腦：

```
ws://localhost:8765
```

### 連線行為

- 連上後**自動開始接收資料**，不需發送任何請求或握手指令
- Server 會以 **~128 msg/sec** 的速率持續推送 JSON
- 多個 Client 可同時連線，所有 Client 接收到相同資料

---

## Step 3：測試連線（RunWSClient.bat）

在 Client 端電腦上雙擊 `RunWSClient.bat`，可以快速驗證連線是否正常：

```
=== MANPADS WebSocket Client ===

[Local IP Addresses]
   10.20.32.50

  Enter Server IP to connect (localhost = same machine)

Server Host [localhost]: 192.168.1.100
Server Port [8765]: 8765
```

輸入 Server 的 IP 後，會顯示即時收到的原始 JSON 和接收速率：

```
======================================================================
  MANPADS WebSocket Client
======================================================================
  RX: 128 msg/sec  |  Frame: #3200  |  Size: 198 bytes
----------------------------------------------------------------------

{"trackers":[{"tag":"A","px":1.256012,"py":1.680032,"pz":0.000145,"rx":-0.710743,"ry":0.008621,"rz":-0.014023,"rw":0.703312,"io":"00000000"}]}

----------------------------------------------------------------------
  [A] IO7-A: OFF  [B] IO7-B: OFF  [C] IO8-B: OFF  |  Ctrl+C to quit
```

**測試工具快捷鍵：**

| 按鍵 | 功能 |
|------|------|
| `A` | 切換 Tag A（刺針）的 IO7 輸出（後座力） |
| `B` | 切換 Tag B（主射手頭盔震動器）的 IO7 輸出（小震動） |
| `C` | 切換 Tag B（主射手頭盔震動器）的 IO8 輸出（大震動） |
| `Ctrl+C` | 結束程式 |

> 確認 RX 速率約為 128 msg/sec 且能看到 JSON 資料，表示連線正常。

---

## IO 訊號監控（RunMonitor.bat）

雙擊 `RunMonitor.bat`，可在 Console 即時監看所有裝置的追蹤狀態與 IO 腳位訊號。適合硬體接線測試、IO 訊號驗證。

啟動後畫面（原地刷新）：

```
======================================================================
  MANPADS Tracking Monitor    Scene: [1] FIM92    FPS: 128
======================================================================

  [A] 刺針  (T1, type=A)  S:2 Tracking
      Pos: (  +1.2560,   +1.6800,   +0.0001)
      Rot: (  -0.7107,   +0.0086,   -0.0140,   +0.7033)
      IO:  00110100   IO1=L  IO2=L  IOA3=H  IOA4=H  IO5=L  IO6=H  IO7*=L  IO8=L

  [B] 主射手頭盔震動器  (T2, type=B)  S:0 Init
      Pos: (  +0.0000,   +0.0000,   +0.0000)
      Rot: (  +0.0000,   +0.0000,   +0.0000,   +1.0000)
      IO:  00000000   IO1=L  IO2=L  IOA3=L  IOA4=L  IO5=L  IO6=L  IO7*=L  IO8=L

  ──────────────────────────────────────────────────────────────────
  Global IO [A]: 00110100   IO1=L  IO2=L  IOA3=H  IOA4=H  IO5=L  IO6=H  IO7*=L  IO8=L

  Frame #1600  |  [A] IO7-A  [B] IO7-B  [O] IO7-All  [1-9] Scene  [Q] Quit
```

**顯示內容：**

| 區域 | 說明 |
|------|------|
| 標題列 | 場景名稱、資料接收速率 (FPS) |
| 各裝置區塊 | Tag、位置、旋轉、IO 8-bit 狀態（`H`=有訊號、`L`=無訊號） |
| Global IO | 第一組 HW Extension 的 IO 摘要 |

> 此工具僅顯示，不提供 WebSocket 連線。若需連線資料請用 `RunDataServer.bat`。

---

## 資料格式

每一筆 WebSocket message 是一行 JSON 字串：

```
{"trackers":[{"tag":"A","px":1.256012,"py":1.680032,"pz":0.000145,"rx":-0.710743,"ry":0.008621,"rz":-0.014023,"rw":0.703312,"io":"00000000"},{"tag":"B","px":0.000000,"py":0.000000,"pz":0.000000,"rx":0.000000,"ry":0.000000,"rz":0.000000,"rw":1.000000,"io":"00000000"}]}
```

格式化後：

```json
{
  "trackers": [
    {
      "tag": "A",
      "px": 1.256012,
      "py": 1.680032,
      "pz": 0.000145,
      "rx": -0.710743,
      "ry": 0.008621,
      "rz": -0.014023,
      "rw": 0.703312,
      "io": "00000000"
    }
  ]
}
```

### 欄位摘要

| 欄位 | 型別 | 說明 |
|------|------|------|
| `tag` | string | 裝置代號：`"A"`=刺針、`"B"`=主射手頭盔震動器、`"C"`=望遠鏡、`"D"`=對講機、`"E"`=副射手頭盔、`"F"`=主射手頭盔定位 |
| `px`, `py`, `pz` | float | 位置（公尺），右手座標系，**Y 軸朝上** |
| `rx`, `ry`, `rz`, `rw` | float | 旋轉四元數 (x, y, z, w) |
| `io` | string | 8 字元 IO 狀態字串（每字元 `"0"` 或 `"1"`） |

> **注意**：Tag B（主射手頭盔震動器）和 Tag D（對講機）為 **IO-only 裝置**，不提供位置追蹤。其 `px/py/pz` 固定為 0，`rw` 固定為 1，僅 `io` 欄位有效。Tag E（副射手頭盔）和 Tag F（主射手頭盔定位）為 **Alt-only 裝置**，提供位置追蹤但無 IO（`io` 固定為 `"00000000"`）。

### trackers 陣列

- 裝置數量 **0 ~ 6 個**，連線時自動出現，斷線時自動消失
- 陣列順序不固定，**請用 `tag` 欄位識別裝置**

```python
# ✓ 正確：用 tag 找裝置
for t in data["trackers"]:
    if t["tag"] == "A":
        stinger_pos = (t["px"], t["py"], t["pz"])

# ✗ 避免：用索引假設順序
stinger = data["trackers"][0]  # 不保證是 Tag A
```

---

## IO 字串怎麼讀

`"io"` 為固定 **8 字元**字串，每字元 `"0"` 或 `"1"`，代表一個 IO 腳位：

| 位置 | 腳位 | 方向 | `"1"` 的意義 |
|------|------|------|-------------|
| `[0]` | IO1 | 輸入 | 有訊號 |
| `[1]` | IO2 | 輸入 | 有訊號 |
| `[2]` | IOA3 | 輸入 | 有訊號 |
| `[3]` | IOA4 | 輸入 | 有訊號 |
| `[4]` | IO5 | 輸入 | 有訊號 |
| `[5]` | IO6 | 輸入 | 有訊號 |
| `[6]` | **IO7** | **輸出** | ON (High) |
| `[7]` | IO8 | 輸入 | 有訊號 |

**Tag A（刺針）IO 訊號定義：**

| 位置 | 訊號名稱 |
|------|----------|
| `[0]` IO1 | IFF 開關 |
| `[1]` IO2 | 鎖定鍵 |
| `[2]` IOA3 | BCU |
| `[3]` IOA4 | 保險 |
| `[4]` IO5 | 瞄準模組 |
| `[5]` IO6 | 板機 |
| `[6]` IO7 | 後座力（輸出，由 Server 控制） |
| `[7]` IO8 | 後座力準備 |

**Tag B（主射手頭盔震動器，IO-only）IO 訊號定義：**

| 位置 | 訊號名稱 |
|------|----------|
| `[6]` IO7 | 小震動（輸出，由 Server 控制） |
| `[7]` IO8 | 大震動（輸出，由 Server 控制） |

> Tag B 為 IO-only（無位置追蹤），大震動需 IO7 + IO8 同時 ON。

**Tag E（副射手頭盔）：** Alt-only，無 IO。`io` 固定為 `"00000000"`。

**Tag F（主射手頭盔定位）：** Alt-only，無 IO。`io` 固定為 `"00000000"`。

**Tag C（望遠鏡）IO 訊號定義：**

| 位置 | 訊號名稱 |
|------|----------|
| `[0]` IO1 | 縮小鍵 |
| `[1]` IO2 | 放大鍵 |

**Tag D（對講機）IO 訊號定義：**

| 位置 | 訊號名稱 |
|------|----------|
| `[0]` IO1 | 通話鍵 |

### 讀取範例

```python
io = tracker["io"]  # 例如 "00110100"

iff     = io[0]  # IO1  - IFF 開關
lock    = io[1]  # IO2  - 鎖定鍵
bcu     = io[2]  # IOA3 - BCU
safety  = io[3]  # IOA4 - 保險
aim     = io[4]  # IO5  - 瞄準模組
trigger = io[5]  # IO6  - 板機
io7_out = io[6]  # IO7  - 後座力（輸出）
io8     = io[7]  # IO8  - 後座力準備

if trigger == "1":
    print("板機已按下！")
```

```csharp
string io = tracker.GetProperty("io").GetString();  // "00110100"

bool iff     = io[0] == '1';  // IO1  - IFF 開關
bool lockKey = io[1] == '1';  // IO2  - 鎖定鍵
bool bcu     = io[2] == '1';  // IOA3 - BCU
bool safety  = io[3] == '1';  // IOA4 - 保險
bool aim     = io[4] == '1';  // IO5  - 瞄準模組
bool trigger = io[5] == '1';  // IO6  - 板機
bool io7Out  = io[6] == '1';  // IO7  - 後座力（輸出）
bool io8     = io[7] == '1';  // IO8  - 後座力準備
```

---

## IO 控制指令（Client → Server）

Client 可透過 WebSocket 發送 JSON 指令，控制特定裝置的 IO 輸出腳位。

### IO7 控制

```json
{"io7": "<Tag><State>"}
```

| 指令 | 語義 |
|------|------|
| `{"io7":"A1"}` | Tag A（刺針）IO7 → ON（後座力） |
| `{"io7":"A0"}` | Tag A（刺針）IO7 → OFF |
| `{"io7":"B1"}` | Tag B（主射手頭盔震動器）IO7 → ON（小震動） |
| `{"io7":"B0"}` | Tag B（主射手頭盔震動器）IO7 → OFF |

### IO8 控制（僅 Tag B）

```json
{"io8": "<Tag><State>"}
```

| 指令 | 語義 |
|------|------|
| `{"io8":"B1"}` | Tag B（主射手頭盔震動器）IO8 → ON（大震動） |
| `{"io8":"B0"}` | Tag B（主射手頭盔震動器）IO8 → OFF |

> 大震動效果需 IO7 + IO8 同時 ON。

### 注意事項

- IO7 控制：僅 Tag A（刺針）和 Tag B（主射手頭盔震動器）支援
- IO8 控制：僅 Tag B（主射手頭盔震動器）支援
- 若已是目標狀態，指令不會重複翻轉（set-to-state 語義）
- 建議發送後仍讀取回傳 JSON 的 `io[6]`（IO7）確認實際狀態

---

## 連線範例

### Python

```python
import asyncio
import websockets
import json

WS_URL = "ws://192.168.1.100:8765"  # ← 改為 Server 的內網 IP

async def main():
    async with websockets.connect(WS_URL) as ws:
        print(f"已連線到 {WS_URL}")
        async for message in ws:
            data = json.loads(message)

            for t in data["trackers"]:
                print(f"[{t['tag']}] "
                      f"位置=({t['px']:.3f}, {t['py']:.3f}, {t['pz']:.3f}) "
                      f"IO={t['io']}")

asyncio.run(main())
```

### C#

```csharp
using System;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;

// ← 改為 Server 的內網 IP
string wsUrl = "ws://192.168.1.100:8765";

var ws = new ClientWebSocket();
await ws.ConnectAsync(new Uri(wsUrl), CancellationToken.None);
Console.WriteLine($"已連線到 {wsUrl}");

var buffer = new byte[4096];
while (ws.State == WebSocketState.Open)
{
    var result = await ws.ReceiveAsync(buffer, CancellationToken.None);
    var json = Encoding.UTF8.GetString(buffer, 0, result.Count);
    var doc = JsonDocument.Parse(json);

    foreach (var tracker in doc.RootElement.GetProperty("trackers").EnumerateArray())
    {
        string tag = tracker.GetProperty("tag").GetString();
        double px = tracker.GetProperty("px").GetDouble();
        double py = tracker.GetProperty("py").GetDouble();
        double pz = tracker.GetProperty("pz").GetDouble();
        string io = tracker.GetProperty("io").GetString();

        Console.WriteLine($"[{tag}] 位置=({px:F3}, {py:F3}, {pz:F3}) IO={io}");
    }
}
```

### JavaScript (Node.js)

```javascript
const WebSocket = require('ws');

// ← 改為 Server 的內網 IP
const ws = new WebSocket('ws://192.168.1.100:8765');

ws.on('open', () => console.log('已連線'));

ws.on('message', (raw) => {
    const data = JSON.parse(raw);
    data.trackers.forEach(t => {
        console.log(`[${t.tag}] `
            + `位置=(${t.px.toFixed(3)}, ${t.py.toFixed(3)}, ${t.pz.toFixed(3)}) `
            + `IO=${t.io}`);
    });
});
```

### JavaScript (瀏覽器)

```javascript
// ← 改為 Server 的內網 IP
const ws = new WebSocket('ws://192.168.1.100:8765');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    data.trackers.forEach(t => {
        console.log(`[${t.tag}] px=${t.px} py=${t.py} pz=${t.pz} io=${t.io}`);
    });
};

// 發送 IO7 控制指令
function setIO7(tag, state) {
    ws.send(JSON.stringify({ io7: tag + state }));  // 例如 "A1"
}
```

---

# 防火牆設定

跨電腦使用 WebSocket 時，需確保 Server 端防火牆允許 TCP Port 入站連線。

以**系統管理員**身份在 Server 端開啟 PowerShell，執行：

```powershell
netsh advfirewall firewall add rule name="MANPADS DataServer" dir=in action=allow protocol=tcp localport=8765
```

---

# 常見問題

### Q：連上 WebSocket 但收到 `{"trackers":[]}`？

表示目前無追蹤裝置連線。確認 Antilatency 硬體已 USB 接上且在 AntilatencyService 中可見。

### Q：RX 顯示 0/sec？

C++ 追蹤程式可能未啟動或未連接到硬體。檢查 Console 是否有錯誤訊息。

### Q：跨電腦連線失敗？

1. 確認兩台電腦在同一網段（例如都是 `192.168.1.x`）
2. 確認 Server 端防火牆已開放 Port 8765
3. 嘗試用 `ping <server-ip>` 確認網路連通
4. 確認 Server 的 Host 設定為 `0.0.0.0`（而非 `127.0.0.1`）

### Q：如何停止程式？

關閉 `RunDataServer.bat` 的 Console 視窗即可。

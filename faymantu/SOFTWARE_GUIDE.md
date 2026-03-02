# MANPADS 軟體組操作手冊

本文件說明如何從 MANPADS 追蹤系統取得即時 6DOF 追蹤資料（位置、旋轉、IO 狀態）。

> **資料格式完整定義**請見 [COMM_SPEC.md](COMM_SPEC.md)。

---

## 本資料夾內容

```
faymantu/
├── COMM_SPEC.md              ← 通訊規格書（欄位定義、IO 定義）
├── SOFTWARE_GUIDE.md         ← 本文件（操作手冊）
├── RunDataServer.bat         ← 啟動 WebSocket 模式（雙擊執行）
├── RunLocalFile.bat          ← 啟動本地檔案模式（雙擊執行）
├── RunWSClient.bat           ← WebSocket 連線測試工具（雙擊執行）
├── data_server.py            ← WebSocket 伺服器程式（自動被 BAT 呼叫）
└── ws_client.py              ← 連線測試工具程式（自動被 BAT 呼叫）
```

---

## 環境需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Windows 10/11 (64-bit) |
| Python | 3.8 以上，已加入系統 PATH |
| Python 套件 | `pip install websockets` |
| 硬體 | Antilatency Alt Tracker + Extension Module（USB 連接至追蹤主機） |
| 編譯產物 | `build/Release/TrackingMinimalDemo.exe`（需先編譯或從 Release 下載） |

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
  [A] IO7-A: OFF  [B] IO7-B: OFF  |  Ctrl+C to quit
```

**測試工具快捷鍵：**

| 按鍵 | 功能 |
|------|------|
| `A` | 切換 Tag A（刺針）的 IO7 輸出 |
| `B` | 切換 Tag B（頭盔）的 IO7 輸出 |
| `Ctrl+C` | 結束程式 |

> 確認 RX 速率約為 128 msg/sec 且能看到 JSON 資料，表示連線正常。

---

## 資料格式

每一筆 WebSocket message 是一行 JSON 字串：

```
{"trackers":[{"tag":"A","px":1.256012,"py":1.680032,"pz":0.000145,"rx":-0.710743,"ry":0.008621,"rz":-0.014023,"rw":0.703312,"io":"00000000"},{"tag":"B","px":0.500123,"py":1.500045,"pz":0.100012,"rx":-0.697612,"ry":0.008834,"rz":-0.010012,"rw":0.710023,"io":"00100000"}]}
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
| `tag` | string | 裝置代號：`"A"`=刺針、`"B"`=頭盔、`"C"`=望遠鏡、`"D"`=對講機 |
| `px`, `py`, `pz` | float | 位置（公尺），右手座標系，**Y 軸朝上** |
| `rx`, `ry`, `rz`, `rw` | float | 旋轉四元數 (x, y, z, w) |
| `io` | string | 8 字元 IO 狀態字串（每字元 `"0"` 或 `"1"`） |

> 完整欄位定義（型別、範圍、精度）請見 [COMM_SPEC.md §5](COMM_SPEC.md#5-欄位定義)。

### trackers 陣列

- 裝置數量 **0 ~ 4 個**，連線時自動出現，斷線時自動消失
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
| `[7]` IO8 | （未定義） |

> 完整 IO 定義（含 Tag B/C/D、Active Low 說明、解讀範例）請見 [COMM_SPEC.md §6](COMM_SPEC.md#6-io-定義)。

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
io8     = io[7]  # IO8  - 未定義

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
bool io8     = io[7] == '1';  // IO8  - 未定義
```

---

## IO7 控制指令（Client → Server）

Client 可透過 WebSocket 發送 JSON 指令，控制特定裝置的 IO7 輸出腳位（例如觸發後座力模擬）。

### 指令格式

```json
{"io7": "<Tag><State>"}
```

| 指令 | 語義 |
|------|------|
| `{"io7":"A1"}` | Tag A（刺針）IO7 → ON |
| `{"io7":"A0"}` | Tag A（刺針）IO7 → OFF |
| `{"io7":"B1"}` | Tag B（頭盔）IO7 → ON |
| `{"io7":"B0"}` | Tag B（頭盔）IO7 → OFF |

### 注意事項

- 僅 Tag A（刺針）和 Tag B（頭盔）支援 IO7 控制
- 若 IO7 已是目標狀態，指令不會重複翻轉（Server 內部比對 `io[6]` 後決定是否動作）
- 建議發送後仍讀取回傳 JSON 的 `io[6]` 確認實際狀態

> 完整控制指令規格請見 [COMM_SPEC.md §8](COMM_SPEC.md#8-控制指令client--server)。

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

# 本地檔案模式（RunLocalFile.bat）

> 適用於追蹤主機和軟體組程式在**同一台電腦**上執行。跨電腦請用 WebSocket 模式。

雙擊 `RunLocalFile.bat`，軟體組程式定時讀取以下檔案即可取得追蹤資料：

```
build/Release/tracking_data.json
```

本地檔案使用 C++ 完整 JSON 格式（比 WebSocket 多出 `scene`、`stability` 等欄位）。格式定義請見 [COMM_SPEC.md §4.2](COMM_SPEC.md#42-本地檔案-json-格式)。

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

### Q：兩種模式可以同時使用嗎？

**不行**。`RunDataServer.bat`（WebSocket）和 `RunLocalFile.bat`（檔案）都會啟動 C++ 追蹤程式，同一時間只能執行一個。

### Q：如何停止程式？

- WebSocket 模式：關閉 `RunDataServer.bat` 的 Console 視窗
- 本地檔案模式：在 Console 視窗按 `Q` 鍵退出

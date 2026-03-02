# MANPADS 軟體組資料介面使用指南

本文件說明如何從 MANPADS 追蹤系統取得即時 6DOF 追蹤資料（位置、旋轉、IO 狀態）。

提供兩種取得資料的方式：

| 方式 | 啟動腳本 | 適用場景 |
|------|----------|----------|
| **方式一：WebSocket**（推薦） | `RunDataServer.bat` | 跨電腦 / 同電腦均可，即時推送 |
| **方式二：本地檔案** | `RunLocalFile.bat` | 同一台電腦，直接讀檔 |

> **注意**：兩種方式**無法同時使用**，同一時間只能啟動其中一個。

---

## 本資料夾內容

```
faymantu/
├── RunDataServer.bat     ← 啟動 WebSocket 模式（雙擊執行）
├── RunLocalFile.bat      ← 啟動本地檔案模式（雙擊執行）
├── RunWSClient.bat       ← WebSocket 連線測試工具（雙擊執行）
├── data_server.py        ← WebSocket 伺服器程式（自動被 BAT 呼叫）
├── ws_client.py          ← 連線測試工具程式（自動被 BAT 呼叫）
└── SOFTWARE_GUIDE.md     ← 本文件
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

# 方式一：WebSocket 模式（推薦）

## 整體架構

```
┌───────────────────────────────────────────────────────────┐
│                  追蹤主機（Server 端）                      │
│                                                           │
│  Antilatency 追蹤硬體 (USB)                                │
│       ↓                                                   │
│  TrackingMinimalDemo.exe (C++ 追蹤程式)                    │
│       ↓ stdout pipe (500Hz JSON)                          │
│  data_server.py (Python WebSocket Server)                 │
│       ↓ WebSocket 推送 (~128 msg/sec)                     │
│       ↓ ws://<host>:<port>                                │
└───────┬───────────────────────────────────────────────────┘
        │ 有線網路 (Ethernet) / WiFi / 同一台電腦
┌───────┴───────────────────────────────────────────────────┐
│                  軟體組電腦（Client 端）                     │
│                                                           │
│  你的應用程式 → WebSocket Client                            │
│       連線到 ws://<server-ip>:<port>                       │
│       連上後自動接收資料，不需發送任何指令                     │
└───────────────────────────────────────────────────────────┘
```

---

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
| **RX** | 從 C++ 追蹤程式接收到的原始資料速率（正常應為 ~128/sec） |
| **TX** | 實際推送給所有 WebSocket Client 的速率 |
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

Server 啟動後，Client 使用以下位址連線：

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

## WebSocket 通訊規格

| 項目 | 規格 |
|------|------|
| 協定 | WebSocket (RFC 6455) |
| 連線位址 | `ws://<server-ip>:<port>`（預設 port `8765`） |
| Frame 類型 | Text frame |
| 資料方向 | Server → Client：推送追蹤資料；Client → Server：IO7 控制指令 |
| 推送頻率 | ~128 msg/sec |
| 編碼 | UTF-8 |
| 最大同時 Client | 無硬性限制（建議 < 10） |

---

## 資料格式（WebSocket 模式）

### 你收到的原始字串

每一筆 WebSocket message 是一行 JSON 字串（無換行、無空格）：

```
{"trackers":[{"tag":"A","px":1.256012,"py":1.680032,"pz":0.000145,"rx":-0.710743,"ry":0.008621,"rz":-0.014023,"rw":0.703312,"io":"00000000"},{"tag":"B","px":0.500123,"py":1.500045,"pz":0.100012,"rx":-0.697612,"ry":0.008834,"rz":-0.010012,"rw":0.710023,"io":"00100000"}]}
```

### 格式化後（方便閱讀）

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
    },
    {
      "tag": "B",
      "px": 0.500123,
      "py": 1.500045,
      "pz": 0.100012,
      "rx": -0.697612,
      "ry": 0.008834,
      "rz": -0.010012,
      "rw": 0.710023,
      "io": "00100000"
    }
  ]
}
```

### 欄位定義

| 欄位 | 型別 | 單位 | 說明 |
|------|------|------|------|
| `tag` | string | — | 裝置代號（`"A"` / `"B"` / `"C"` / `"D"`，見 Tag 對照表） |
| `px` | float | 公尺 (m) | X 軸位置（左右） |
| `py` | float | 公尺 (m) | Y 軸位置（上下 / 高度），**Y 軸朝上** |
| `pz` | float | 公尺 (m) | Z 軸位置（前後） |
| `rx` | float | — | 旋轉四元數 X 分量 |
| `ry` | float | — | 旋轉四元數 Y 分量 |
| `rz` | float | — | 旋轉四元數 Z 分量 |
| `rw` | float | — | 旋轉四元數 W 分量 |
| `io` | string | — | 8 字元 IO 狀態字串（見 IO 說明） |

> **座標系**：右手座標系，Y 軸朝上。`py` 值即為裝置離地高度。

> **四元數**：格式為 (x, y, z, w)。可轉換為 Euler 角度：Yaw（偏航/左右轉）、Pitch（俯仰/上下看）、Roll（翻滾/歪頭）。

### Tag 對照表

| Tag | 裝置名稱 | 說明 |
|-----|----------|------|
| `"A"` | 刺針 | 飛彈發射器 |
| `"B"` | 頭盔 | 射手頭盔 |
| `"C"` | 望遠鏡 | 觀測望遠鏡 |
| `"D"` | 對講機 | 通訊裝置 |

### trackers 陣列說明

- `trackers` 是一個陣列，**裝置數量不固定**（0 ~ 4 個）
- 裝置連線時自動出現在陣列中，斷線時自動消失
- 陣列中的順序不固定，請用 `tag` 欄位識別裝置
- 建議寫法：用 `tag` 找到目標裝置，而非用陣列索引

```python
# ✓ 正確：用 tag 找裝置
for t in data["trackers"]:
    if t["tag"] == "A":
        stinger_pos = (t["px"], t["py"], t["pz"])

# ✗ 避免：用索引假設順序
stinger = data["trackers"][0]  # 不保證是 Tag A
```

### 各種情況下收到的 JSON

| 情況 | 收到的 JSON |
|------|-------------|
| 無裝置連線 | `{"trackers":[]}` |
| 僅刺針連線 | `{"trackers":[{"tag":"A","px":...,"io":"00000000"}]}` |
| 刺針+頭盔 | `{"trackers":[{"tag":"A",...},{"tag":"B",...}]}` |
| 4 台全連 | `{"trackers":[{"tag":"A",...},{"tag":"B",...},{"tag":"C",...},{"tag":"D",...}]}` |

---

## IO 8-bit 字串詳細說明

`"io"` 欄位為固定 **8 字元**字串，每個字元為 `"0"` 或 `"1"`，代表一個 IO 腳位的狀態。

### IO 腳位對照表

| 字元位置 | 腳位名稱 | 方向 | `"0"` 的意義 | `"1"` 的意義 |
|----------|----------|------|-------------|-------------|
| `[0]` | IO1 | **輸入** | 無訊號 (High) | 有訊號 (Low) |
| `[1]` | IO2 | **輸入** | 無訊號 | 有訊號 |
| `[2]` | IOA3 | **輸入** | 無訊號 | 有訊號 |
| `[3]` | IOA4 | **輸入** | 無訊號 | 有訊號 |
| `[4]` | IO5 | **輸入** | 無訊號 | 有訊號 |
| `[5]` | IO6 | **輸入** | 無訊號 | 有訊號 |
| `[6]` | **IO7** | **輸出** | OFF (Low) | ON (High) |
| `[7]` | IO8 | **輸入** | 無訊號 | 有訊號 |

> **輸入腳位**使用 Active Low 邏輯：硬體接地 (Low) = `"1"`（觸發），懸空 (High) = `"0"`（未觸發）。

> 若裝置無對應 IO 模組，`io` 值固定為 `"00000000"`。

### Tag A（刺針）IO 腳位定義

| 字元位置 | 腳位 | 訊號名稱 | 說明 |
|----------|------|----------|------|
| `[0]` | IO1 | IFF 開關 | `"1"` = ON |
| `[1]` | IO2 | 鎖定鍵 | `"1"` = ON |
| `[2]` | IOA3 | BCU | `"1"` = ON |
| `[3]` | IOA4 | 保險 | `"1"` = ON |
| `[4]` | IO5 | 瞄準模組 | `"1"` = ON |
| `[5]` | IO6 | 板機 | `"1"` = ON |
| `[6]` | **IO7** | **後座力** | 由 Server 控制輸出 |
| `[7]` | IO8 | （未定義） | |

**範例**：`"00110100"` 表示 BCU=ON、保險=ON、瞄準模組=ON，其餘 OFF。

### 讀取 IO 的程式範例

```python
io = tracker["io"]  # 例如 "00110100"

iff     = io[0]  # IO1  - IFF 開關
lock    = io[1]  # IO2  - 鎖定鍵
bcu     = io[2]  # IOA3 - BCU
safety  = io[3]  # IOA4 - 保險
aim     = io[4]  # IO5  - 瞄準模組
trigger = io[5]  # IO6  - 板機
io7_out = io[6]  # IO7  - 後座力（輸出，由系統控制）
io8     = io[7]  # IO8  - 未定義

# 判斷板機是否觸發
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

| 指令 | 說明 |
|------|------|
| `{"io7":"A1"}` | Tag A（刺針）IO7 → High (ON) |
| `{"io7":"A0"}` | Tag A（刺針）IO7 → Low (OFF) |
| `{"io7":"B1"}` | Tag B（頭盔）IO7 → High (ON) |
| `{"io7":"B0"}` | Tag B（頭盔）IO7 → Low (OFF) |

### 注意事項

- IO7 在硬體端為 **toggle** 機制：每次指令會切換一次狀態
- **建議**：發送指令後，讀取回傳 JSON 的 `io[6]` 確認實際狀態
- 僅 Tag A（刺針）和 Tag B（頭盔）支援 IO7 控制

### 使用範例（Python）

```python
import asyncio, websockets, json

async def fire_recoil():
    async with websockets.connect("ws://192.168.1.100:8765") as ws:
        # 開啟刺針後座力
        await ws.send(json.dumps({"io7": "A1"}))

        # 等待並確認狀態
        msg = await ws.recv()
        data = json.loads(msg)
        for t in data["trackers"]:
            if t["tag"] == "A":
                io7_actual = t["io"][6]
                print(f"Tag A IO7 = {'ON' if io7_actual == '1' else 'OFF'}")

        # 關閉刺針後座力
        await ws.send(json.dumps({"io7": "A0"}))

asyncio.run(fire_recoil())
```

---

## 連線範例（完整程式碼）

### Python — 持續接收追蹤資料

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

            if not data["trackers"]:
                print("無裝置連線")
                continue

            for t in data["trackers"]:
                print(f"[{t['tag']}] "
                      f"位置=({t['px']:.3f}, {t['py']:.3f}, {t['pz']:.3f}) "
                      f"IO={t['io']}")

asyncio.run(main())
```

### C# — 持續接收追蹤資料

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

    var trackers = doc.RootElement.GetProperty("trackers");
    if (trackers.GetArrayLength() == 0)
    {
        Console.WriteLine("無裝置連線");
        continue;
    }

    foreach (var tracker in trackers.EnumerateArray())
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

    if (data.trackers.length === 0) {
        console.log('無裝置連線');
        return;
    }

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

# 方式二：本地檔案模式（RunLocalFile.bat）

若不使用 WebSocket，可改用本地檔案模式：C++ 程式直接將追蹤資料寫入 JSON 檔案，軟體組程式定時讀取此檔案。

> **適用場景**：追蹤主機和軟體組程式在**同一台電腦**上執行。跨電腦請用方式一（WebSocket）。

## 啟動方式

雙擊 `RunLocalFile.bat`，會開啟一個 Console 視窗：

```
=== MANPADS Local File Mode ===

  Tracking data will be written to:
  build\Release\tracking_data.json

  Software team can poll-read this file for real-time data.
  Press [Q] in the tracker window to quit.
```

C++ 程式啟動後，Console 會顯示追蹤資料文字（供觀察用），同時持續將 JSON 寫入檔案。

## 資料檔案位置

從專案根目錄算起：

```
build/Release/tracking_data.json
```

完整路徑範例：

```
C:\Users\<使用者>\<專案路徑>\FIM92_C++\build\Release\tracking_data.json
```

## 讀取方式

軟體組程式以固定間隔（建議 **5~10ms**）讀取 `tracking_data.json` 的完整檔案內容。

### 為什麼不會讀到壞資料？

C++ 使用 **Atomic Write**：
1. 先寫入 `tracking_data.json.tmp`（暫存檔）
2. 再用 `rename` 原子替換 `tracking_data.json`

`rename` 在作業系統層級是原子操作，所以讀取端**永遠不會讀到寫到一半的檔案**。

### 讀取範例（Python）

```python
import json
import time

FILE_PATH = r"C:\...\FIM92_C++\build\Release\tracking_data.json"  # ← 改為實際路徑

while True:
    try:
        with open(FILE_PATH, "r") as f:
            data = json.load(f)

        for t in data["trackers"]:
            print(f"[{t['tag']}] px={t['px']:.3f} py={t['py']:.3f} pz={t['pz']:.3f}")

    except (json.JSONDecodeError, FileNotFoundError):
        pass  # 檔案尚未建立或剛好在寫入中（極罕見）

    time.sleep(0.01)  # 10ms = 100 次/秒
```

### 讀取範例（C#）

```csharp
using System.Text.Json;

string filePath = @"C:\...\FIM92_C++\build\Release\tracking_data.json";

while (true)
{
    try
    {
        string json = File.ReadAllText(filePath);
        var doc = JsonDocument.Parse(json);

        foreach (var tracker in doc.RootElement.GetProperty("trackers").EnumerateArray())
        {
            string tag = tracker.GetProperty("tag").GetString();
            double px = tracker.GetProperty("px").GetDouble();
            double py = tracker.GetProperty("py").GetDouble();
            double pz = tracker.GetProperty("pz").GetDouble();
            Console.WriteLine($"[{tag}] px={px:F3} py={py:F3} pz={pz:F3}");
        }
    }
    catch { }

    Thread.Sleep(10);  // 10ms
}
```

## 本地檔案的 JSON 格式

本地檔案模式使用 C++ 的**完整 JSON 格式**，比 WebSocket 模式多了幾個欄位：

```json
{
  "scene": 1,
  "sceneName": "FV_10bars",
  "trackers": [
    {
      "id": 1,
      "tag": "A",
      "type": "A",
      "number": "1",
      "px": 1.256012,
      "py": 1.680032,
      "pz": 0.000145,
      "rx": -0.710743,
      "ry": 0.008621,
      "rz": -0.014023,
      "rw": 0.703312,
      "stability": 2,
      "io": "00000000"
    }
  ],
  "io": {
    "connected": true,
    "type": "A",
    "inputs": [0, 0, 0, 1, 0, 0, 0],
    "io7out": false
  }
}
```

### 與 WebSocket 格式的差異

| 欄位 | WebSocket 模式 | 本地檔案模式 | 說明 |
|------|---------------|-------------|------|
| `scene` | ✗ 無 | ✓ 有 | 當前場景編號 (1-based) |
| `sceneName` | ✗ 無 | ✓ 有 | 場景名稱 |
| `trackers[].id` | ✗ 無 | ✓ 有 | Tracker 流水號 |
| `trackers[].tag` | ✓ 有 | ✓ 有 | 裝置代號（A/B/C/D） |
| `trackers[].type` | ✗ 無 | ✓ 有 | 裝置 Type 屬性 |
| `trackers[].number` | ✗ 無 | ✓ 有 | 裝置 Number 屬性 |
| `trackers[].px~rw` | ✓ 有 | ✓ 有 | 位置與旋轉 |
| `trackers[].stability` | ✗ 無 | ✓ 有 | 追蹤穩定度（見下方說明） |
| `trackers[].io` | ✓ 有 | ✓ 有 | 8-bit IO 字串 |
| `io` (全域) | ✗ 無 | ✓ 有 | 第一組 IO 模組的狀態（向下相容） |

> **建議**：即使使用本地檔案模式，也以 `tag` 欄位識別裝置、以 `trackers[].io` 讀取 IO 狀態，這樣兩種模式的程式邏輯可以共用。

### 追蹤穩定度 (stability)

| 值 | 名稱 | 說明 | 資料可用性 |
|----|------|------|-----------|
| 0 | InertialDataInitialization | IMU 初始化中 | 位置/旋轉均不可用 |
| 1 | Tracking3Dof | 僅 IMU 旋轉 | **旋轉可用，位置不可用** |
| **2** | **Tracking6Dof** | **光學定位 + IMU** | **位置 + 旋轉均可用** |
| 3 | TrackingBlind6Dof | 暫時遮擋 | 位置靠慣性預測 |

> **重要**：`stability < 2` 時，`px/py/pz` 位置資料不準確。**必須在立柱場地中達到 `stability=2` 後，位置資料才可信賴。**

---

## 防火牆設定（跨電腦使用 WebSocket 時）

若 Server 和 Client 在不同電腦上，需確保 Server 端防火牆允許 WebSocket Port 的 **TCP 入站**連線。

### Windows 防火牆（在 Server 端執行）

以系統管理員身份開啟 PowerShell，執行：

```powershell
netsh advfirewall firewall add rule name="MANPADS DataServer" dir=in action=allow protocol=tcp localport=8765
```

---

## 效能規格

| 指標 | 數值 |
|------|------|
| C++ 追蹤迴圈 | 500Hz（每 2ms 輪詢一次） |
| WebSocket 推送速率 | ~128 msg/sec |
| 本地檔案寫入速率 | ~500 次/sec |
| 每筆 JSON 大小 | ~150-400 bytes（取決於連線裝置數量） |
| 延遲（本機 WebSocket） | < 10ms |
| 延遲（區域網路 WebSocket） | < 15ms |

> **128 msg/sec 說明**：C++ 以 500Hz 產生資料，經 Windows pipe 傳輸到 Python 後受限於 Windows kernel pipe buffer，實際到達 Python 的速率約為 128 msg/sec。此速率足以滿足即時追蹤需求。

---

## 常見問題

### Q：連上 WebSocket 但收到 `{"trackers":[]}`？

A：表示目前無追蹤裝置連線。確認 Antilatency 硬體已 USB 接上且在 AntilatencyService 中可見。

### Q：RX 顯示 0/sec？

A：C++ 追蹤程式可能未啟動或未連接到硬體。檢查 Console 是否有錯誤訊息。

### Q：跨電腦連線失敗？

A：
1. 確認兩台電腦在同一網段（例如都是 `192.168.1.x`）
2. 確認 Server 端防火牆已開放 port 8765
3. 嘗試用 `ping <server-ip>` 確認網路連通
4. 確認 Server 的 Host 設定為 `0.0.0.0`（而非 `127.0.0.1`）

### Q：兩種模式可以同時使用嗎？

A：**不行**。`RunDataServer.bat`（WebSocket）和 `RunLocalFile.bat`（檔案）都會啟動 C++ 追蹤程式，同時間只能執行一個。

### Q：如何停止程式？

A：
- WebSocket 模式：關閉 `RunDataServer.bat` 的 Console 視窗
- 本地檔案模式：在 Console 視窗按 `Q` 鍵退出

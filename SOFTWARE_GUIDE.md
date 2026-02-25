# FIM92 軟體組資料介面使用指南

## 環境需求

- **Python 3.8+**（已安裝在系統 PATH 中）
- **websockets** 套件：`pip install websockets`
- Antilatency 追蹤硬體已連接並校正完成（接在 Server 端電腦上）

---

## 架構圖

```
                    ┌─────────────────────────────────────────┐
                    │         Server 端（追蹤主機）             │
                    │                                         │
                    │  Antilatency HW                         │
                    │       ↓                                 │
                    │  TrackingMinimalDemo.exe (C++)           │
                    │       ↓ stdout pipe                     │
                    │  data_server.py (Python WebSocket)      │
                    │       ↓ ws://<host>:<port>              │
                    └───────┬─────────────────────────────────┘
                            │ WiFi / LAN
                    ┌───────┴─────────────────────────────────┐
                    │         Client 端（軟體組電腦）            │
                    │                                         │
                    │  Your App → WebSocket Client             │
                    │       connect to ws://<server-ip>:<port> │
                    └─────────────────────────────────────────┘
```

---

## Server 端操作（追蹤主機）

### 啟動方式

雙擊 `RunDataServer.bat`，會詢問網路設定：

```
=== FIM92 Data Server (for Software Team) ===

Server Host [0.0.0.0]: _
Server Port [8765]: _
```

- **Host**: 直接按 Enter 使用預設 `0.0.0.0`（接受所有 IP 連線）
- **Port**: 直接按 Enter 使用預設 `8765`

| Host 設定 | 效果 |
|-----------|------|
| `0.0.0.0` | 接受來自任何 IP 的連線（LAN 使用） |
| `127.0.0.1` | 僅允許本機連線 |
| `192.168.1.100` | 僅綁定特定網卡 IP |

### 運行狀態

啟動後 Console 會持續顯示即時收發速率：

```
  [RX] 487/sec  [TX] 485/sec  |  Clients: 2
```

| 指標 | 說明 |
|------|------|
| RX | 從 C++ 追蹤程式收到的原始資料速率 |
| TX | 實際送給 WebSocket clients 的速率 |
| Clients | 目前連線中的 client 數量 |

---

## Client 端操作（軟體組電腦）

### 測試工具

可用 `RunWSClient.bat` 快速測試連線：

```
=== FIM92 WebSocket Client ===

Server Host [localhost]: 192.168.1.100
Server Port [8765]: 8765
```

輸入 Server 的內網 IP 即可連線，會顯示即時收到的原始 JSON 和接收速率。

### 用自己的程式連線

使用任何支援 WebSocket 的語言連線到 `ws://<server-ip>:<port>`。
連上後自動開始接收資料，不需送任何指令。

---

## WebSocket 規格

| 項目 | 規格 |
|------|------|
| 協定 | WebSocket (RFC 6455) |
| 位址 | `ws://<server-ip>:<port>`（預設 port 8765） |
| Frame 類型 | Text frame |
| 方向 | Server → Client 單向推送 |
| 更新頻率 | ~500 msg/sec |
| 編碼 | UTF-8 |

---

## 資料格式

### 軟體組收到的原始字串

每一筆 WebSocket message 就是一行 JSON 字串（無換行）：

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

### 欄位說明

| 欄位 | 型別 | 說明 |
|------|------|------|
| `tag` | string | 裝置代號（見下表） |
| `px`, `py`, `pz` | float | 位置（單位：公尺） |
| `rx`, `ry`, `rz`, `rw` | float | 旋轉（四元數） |
| `io` | string | 8 字元 IO 狀態字串（見下方說明） |

### Tag 對照表

| Tag | 裝置 |
|-----|------|
| `A` | 刺針 Stinger |
| `B` | 頭盔 Helmet |
| `C` | 望遠鏡 Binoculars |

### IO 8-bit 字串格式

`"io"` 欄位為固定 **8 字元**的字串，每個字元（`"0"` 或 `"1"`）代表一個 IO 腳位。

| 字元位置 | 腳位 | 方向 | 說明 |
|----------|------|------|------|
| `[0]` | IO1 | 輸入 | |
| `[1]` | IO2 | 輸入 | |
| `[2]` | IOA3 | 輸入 | 類比腳位 |
| `[3]` | IOA4 | 輸入 | 類比腳位 |
| `[4]` | IO5 | 輸入 | |
| `[5]` | IO6 | 輸入 | |
| `[6]` | IO7 | **輸出** | 由系統控制 |
| `[7]` | IO8 | 輸入 | |

- `"0"` = Low（無訊號）
- `"1"` = High（有訊號）
- 若該裝置無對應 IO 模組 → `"00000000"`

**範例**: `"00100000"` → IOA3 有訊號，其餘皆無。

### 特殊情況

| 情況 | 收到的 JSON |
|------|-------------|
| 無裝置連線 | `{"trackers":[]}` |
| 1 台裝置 | `{"trackers":[{"tag":"A",...}]}` |
| 3 台裝置 | `{"trackers":[{"tag":"A",...},{"tag":"B",...},{"tag":"C",...}]}` |
| 裝置無 IO 模組 | 該裝置的 `"io"` 為 `"00000000"` |

---

## 連線範例

### Python

```python
import asyncio
import websockets
import json

WS_URL = "ws://192.168.1.100:8765"  # 改為 Server 的內網 IP

async def main():
    async with websockets.connect(WS_URL) as ws:
        async for message in ws:
            data = json.loads(message)
            for t in data["trackers"]:
                print(f"[{t['tag']}] "
                      f"pos=({t['px']:.3f}, {t['py']:.3f}, {t['pz']:.3f}) "
                      f"io={t['io']}")

asyncio.run(main())
```

### C#

```csharp
using System;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;

string wsUrl = "ws://192.168.1.100:8765";  // 改為 Server 的內網 IP

var ws = new ClientWebSocket();
await ws.ConnectAsync(new Uri(wsUrl), CancellationToken.None);

var buffer = new byte[4096];
while (ws.State == WebSocketState.Open)
{
    var result = await ws.ReceiveAsync(buffer, CancellationToken.None);
    var json = Encoding.UTF8.GetString(buffer, 0, result.Count);
    var doc = JsonDocument.Parse(json);
    foreach (var tracker in doc.RootElement.GetProperty("trackers").EnumerateArray())
    {
        Console.WriteLine($"[{tracker.GetProperty("tag")}] " +
            $"px={tracker.GetProperty("px")} " +
            $"py={tracker.GetProperty("py")} " +
            $"pz={tracker.GetProperty("pz")} " +
            $"io={tracker.GetProperty("io")}");
    }
}
```

### JavaScript (Node.js)

```javascript
const WebSocket = require('ws');
const ws = new WebSocket('ws://192.168.1.100:8765');  // 改為 Server 的內網 IP

ws.on('message', (raw) => {
    const data = JSON.parse(raw);
    data.trackers.forEach(t => {
        console.log(`[${t.tag}] `
            + `pos=(${t.px.toFixed(3)}, ${t.py.toFixed(3)}, ${t.pz.toFixed(3)}) `
            + `io=${t.io}`);
    });
});
```

### JavaScript (Browser)

```javascript
const ws = new WebSocket('ws://192.168.1.100:8765');  // 改為 Server 的內網 IP

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    data.trackers.forEach(t => {
        console.log(`[${t.tag}] px=${t.px} py=${t.py} pz=${t.pz} io=${t.io}`);
    });
};
```

---

## 防火牆設定

跨機器使用時，需確保 Server 端防火牆允許 WebSocket port（預設 8765）的 **TCP 入站**連線。

### Windows 防火牆

```powershell
netsh advfirewall firewall add rule name="FIM92 DataServer" dir=in action=allow protocol=tcp localport=8765
```

---

## 效能規格

| 指標 | 數值 |
|------|------|
| C++ 追蹤迴圈 | 500Hz（2ms interval） |
| WebSocket 推送速率 | ~128 msg/sec |
| 每筆 JSON 大小 | ~150-400 bytes（取決於裝置數量） |
| 延遲（本機） | < 10ms |
| 最大同時 Client 數 | 無硬性限制（建議 < 10） |

> **128 msg/sec 說明：** C++ 以 500Hz 產生資料，經 Windows pipe 傳輸到 Python 後受限於 Windows 系統層級的 pipe buffering，實際到達 Python 的速率約為 128 msg/sec。此速率足以滿足即時追蹤的應用需求。

---

## 注意事項

- 裝置未連接時，`trackers` 陣列為空 `[]`
- 每個 Tracker 的 IO 是獨立的，透過硬體 Type 屬性自動配對
- Server 端需保持 `RunDataServer.bat` 視窗開啟
- 多個 Client 可同時連線接收相同資料

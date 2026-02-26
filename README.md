# FIM92 Antilatency Tracking System

Antilatency Alt 6-DOF Tracking + HW IO C++ 應用程式，搭配 Web 3D 即時視覺化介面。

---

## 快速開始

1. 安裝 Python 套件：`pip install websockets`
2. 執行 `RunWithPipe.bat`（推薦）
3. 瀏覽器開啟 `http://localhost:8080`

> 從原始碼編譯請見 [編譯說明](#編譯)。已編譯版本請至 [Releases](https://github.com/gptt-jacky/FIM92_AL/releases)。

---

## 功能

- **6-DOF 追蹤**：位置 (X,Y,Z) + 旋轉 (Quaternion)，500 Hz 輸出
- **多場景切換**：`scenes.json` 定義多場景，按 `[1]`-`[9]` 即時切換
- **多 Tracker**：自動偵測所有 Alt 設備，同時追蹤（最多 9 個）
- **Type 識別**：透過 AntilatencyService 設定裝置 Type（Stinger / Binoculars 等）
- **Number 識別**：透過 AntilatencyService 設定裝置 Number，用於區分同類型裝置
- **HW IO**：7 路 Input + 1 路 Output (IO7)，支援多組 Extension Module（per-tracker IO）
- **Web 控制**：網頁端按鈕可直接控制 C++ 程式（切換場景、IO7 開關）
- **Web 3D 視覺化**：Three.js 即時渲染，XYZ 軸箭頭顯示追蹤器朝向
- **環境燈柱顯示**：自動解碼 environmentData，在 3D 場景中顯示 Antilatency 燈柱位置
- **軸向修正**：AXIS FIX 按鈕 + 模型方向滑桿，即時調整並自動保存
- **跨電腦連線**：區域網路內其他電腦可直接用瀏覽器連線觀看

---

## 系統架構總覽

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         啟動方式與資料流                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  RunTracking.bat (純 C++)                                               │
│  ┌──────────────────────────┐                                           │
│  │ TrackingMinimalDemo.exe  │─── Console 文字輸出                       │
│  │ (無 --json)              │─── build/Release/tracking_data.json       │
│  └──────────────────────────┘    (每 ~2ms 原子覆寫，軟體組可讀取此檔案)  │
│                                                                         │
│  RunWithPipe.bat (推薦)                                                  │
│  ┌──────────────────────────┐   stdout    ┌─────────────────┐           │
│  │ TrackingMinimalDemo.exe  │────pipe────►│ pipe_server.py  │           │
│  │ (--json 模式)            │             │ HTTP :8080      │           │
│  └──────────────────────────┘             │ WS   :8765      │──► 瀏覽器 │
│                                           └─────────────────┘           │
│  RunDataServer.bat (軟體組專用)                                          │
│  ┌──────────────────────────┐   stdout    ┌─────────────────┐           │
│  │ TrackingMinimalDemo.exe  │────pipe────►│ data_server.py  │           │
│  │ (--json 模式)            │             │ WS 0.0.0.0:8765 │──► 軟體組 │
│  └──────────────────────────┘             │ (精簡 JSON)     │    程式   │
│                                           └─────────────────┘           │
│  RunMonitor.bat (IO 監控)                                               │
│  ┌──────────────────────────┐   stdout    ┌─────────────────┐           │
│  │ TrackingMinimalDemo.exe  │────pipe────►│ monitor.py      │           │
│  │ (--json 模式)            │             │ (原地刷新顯示)   │           │
│  └──────────────────────────┘             └─────────────────┘           │
│                                                                         │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                         硬體層                                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐              │
│  │ Alt Tracker #1 │  │ Alt Tracker #2 │  │ Alt Tracker #3 │              │
│  │ Type: Stinger  │  │ Type: Helmet   │  │ Type:Binoculars│              │
│  │ Tag: A         │  │ Tag: B         │  │ Tag: C         │              │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘              │
│          │                   │                   │                       │
│  ┌───────┴────────┐  ┌──────┴─────────┐  ┌──────┴─────────┐            │
│  │ Extension [A]  │  │ Extension [B]  │  │ Extension [C]  │            │
│  │ 7 Input+IO7 Out│  │ 7 Input+IO7 Out│  │ 7 Input+IO7 Out│            │
│  └────────────────┘  └────────────────┘  └────────────────┘            │
│                         USB / Device Network                            │
│                      Antilatency SDK 4.5.0                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 通訊模式

| 模式 | 啟動 | Data/s | 延遲 | 說明 |
|------|------|--------|------|------|
| **Pipe 3D** (推薦) | `RunWithPipe.bat` | ~128 | ~2ms | C++ → pipe → pipe_server.py → WebSocket + HTTP |
| **DataServer** (軟體組) | `RunDataServer.bat` | ~128 | ~2ms | C++ → pipe → data_server.py → WebSocket (精簡 JSON) |
| **Monitor** (IO 監控) | `RunMonitor.bat` | ~128 | ~2ms | C++ → pipe → monitor.py → Console 原地刷新 |
| 純 C++ | `RunTracking.bat` | 500 (檔案) | ~2ms | C++ 直接寫入 `tracking_data.json` + Console 顯示 |

> Pipe 模式零檔案 I/O，效能遠優於 WS 檔案模式。~128 msg/sec 為 Windows pipe kernel buffer 的實際上限。

---

## 軟體整合指南（給軟體組）

### 方式一：WebSocket 精簡介面（RunDataServer.bat，**推薦**）

專為軟體組設計的精簡 WebSocket 資料流。詳細說明見 **[SOFTWARE_GUIDE.md](SOFTWARE_GUIDE.md)**。

```
啟動：RunDataServer.bat（互動式設定 Host / Port）
連線：ws://<server-ip>:8765
```

軟體組收到的精簡 JSON：
```json
{"trackers":[{"tag":"A","px":1.256,"py":1.680,"pz":0.000,"rx":-0.710,"ry":0.008,"rz":-0.014,"rw":0.703,"io":"00000000"}]}
```

- 支援跨機器 LAN 連線（預設綁定 0.0.0.0）
- 驗證工具：`RunWSClient.bat`（互動式輸入 Server IP）
- ~128 msg/sec 推送速率

### 方式二：WebSocket 完整資料（RunWithPipe.bat）

執行 `RunWithPipe.bat` 後，連接 `ws://localhost:8765` 即可收到完整 JSON（含 scene、stability 等欄位）。附帶 HTTP 伺服器及 3D 網頁視覺化。

### JSON 資料格式

C++ 輸出的完整 JSON（Pipe 3D / WebSocket / RunTracking 模式）：

```json
{
    "scene": 1,
    "sceneName": "AL_TEST_3.5M",
    "trackers": [
        {
            "id": 1,
            "type": "Stinger",
            "number": "1",
            "tag": "A",
            "px": 0.123456,
            "py": 1.678901,
            "pz": -0.045678,
            "rx": -0.630000,
            "ry": 0.010000,
            "rz": -0.320000,
            "rw": 0.710000,
            "stability": 2,
            "io": "00000000"
        }
    ],
    "io": {
        "connected": true,
        "type": "AC50",
        "inputs": [0, 0, 0, 1, 0, 0, 0],
        "io7out": false
    }
}
```

> - 每個 tracker 物件內含 `"tag"` 和 `"io"` 欄位（per-tracker IO，透過 Type 屬性配對 HW Extension Module）
> - 全域 `"io":{...}` 保留向下相容（使用第一組 HW Extension 資料）
> - 使用 Pipe/WebSocket 模式時，Python server 會自動注入 `envData` 欄位供前端解碼燈柱

軟體組收到的精簡 JSON（DataServer 模式）只保留必要欄位，詳見 [SOFTWARE_GUIDE.md](SOFTWARE_GUIDE.md)。

### 欄位定義

| 欄位 | 型別 | 說明 |
|------|------|------|
| `scene` | int | 當前場景編號 (1-based) |
| `sceneName` | string | 場景名稱 |
| `trackers[]` | array | 所有連接的 Alt Tracker（可能 0 ~ 多個） |
| `trackers[].id` | int | Tracker 流水號（程式啟動後遞增分配） |
| `trackers[].type` | string | 裝置 Type（在 AntilatencyService 設定，例如 `"Stinger"`，未設定則為空字串） |
| `trackers[].number` | string | 裝置 Number（在 AntilatencyService 設定，未設定則為空字串） |
| `trackers[].tag` | string | 裝置代號（A=Stinger, B=Helmet, C=Binoculars，未知類型為空） |
| `trackers[].px/py/pz` | float | **位置**，單位：公尺 (m)，右手座標系，Y 軸朝上 |
| `trackers[].rx/ry/rz/rw` | float | **旋轉**，四元數 (Quaternion)，格式 (x, y, z, w) |
| `trackers[].stability` | int | 追蹤穩定度（見下表） |
| `trackers[].io` | string | 8 字元 IO 狀態（per-tracker，透過 Type 配對 HW Extension Module） |
| `io.connected` | bool | Extension Module 是否已連接 |
| `io.type` | string | 模組型號（例如 `"AC50"`） |
| `io.inputs[]` | int[7] | 7 路 Input 狀態 (0 或 1)，順序：IO1, IO2, IOA3, IOA4, IO5, IO6, IO8 |
| `io.io7out` | bool | IO7 Output 當前狀態 (true=High/ON, false=Low/OFF) |

### 追蹤穩定度 (Stability)

| 值 | 名稱 | 說明 | 資料可用性 |
|----|------|------|-----------|
| 0 | InertialDataInitialization | IMU 正在初始化 | 位置/旋轉均不可用 |
| 1 | Tracking3Dof | 僅 IMU 旋轉追蹤 | **旋轉可用，位置不可用** |
| **2** | **Tracking6Dof** | **立柱光學定位 + IMU** | **位置 + 旋轉均可用** |
| 3 | TrackingBlind6Dof | 暫時遮擋，靠慣性預測 | 位置靠預測，短時間內可用 |

> **重要**：`stability=1`（3DOF）時位置資料不會真正移動，**必須架設立柱達到 `stability=2`（6DOF）後，位置資料才準確可用**。

### IO 腳位邏輯

Input 使用 **Active Low**：Low（接地）= 1（觸發），High（懸空）= 0（未觸發）。

| 索引 | 腳位 | 方向 | 說明 |
|------|------|------|------|
| 0 | IO1 | Input | Low=1, High=0 |
| 1 | IO2 | Input | Low=1, High=0 |
| 2 | IOA3 | Input | Low=1, High=0 |
| 3 | IOA4 | Input | Low=1, High=0 |
| 4 | IO5 | Input | Low=1, High=0 |
| 5 | IO6 | Input | Low=1, High=0 |
| 6 | IO8 | Input | Low=1, High=0 |
| - | IO7 | **Output** | `io7out` 欄位控制 |

### WebSocket 反向控制

Web 端（或任何 WebSocket client）可以發送 JSON 訊息控制 C++ 程式：

```json
{"type": "keypress", "key": "2"}
```

| key | 功能 |
|-----|------|
| `"1"` ~ `"9"` | 切換場景 |
| `"O"` | 切換 IO7 Output ON/OFF |

---

## 跨電腦使用

兩台電腦用**有線乙太網 (Ethernet)** 連接，追蹤主機執行 Pipe 模式：

```
追蹤主機 (192.168.1.100)              顯示端電腦
┌─────────────────────┐              ┌─────────────────────────────┐
│ RunWithPipe.bat     │◄─ Ethernet ─►│ 瀏覽器開啟:                 │
│ WS on 0.0.0.0:8765  │              │ http://192.168.1.100:8080   │
│ HTTP on 0.0.0.0:8080│              └─────────────────────────────┘
└─────────────────────┘
```

也可以用 URL 參數指定主機：`http://localhost:8080?host=192.168.1.100`

---

## 場景設定 (scenes.json)

```json
{
    "scenes": [
        {
            "name": "場景名稱",
            "environmentData": "AntilatencyAltEnvironmentPillars~...",
            "placementData": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        }
    ]
}
```

- `environmentData` 從 AntilatencyService → Export Environment 取得
- `placementData` 可省略，預設為原點 (`"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"`)
- 新增場景後，Web 3D 會自動顯示對應燈柱位置
- 按 `[1]`-`[9]` 切換場景，`[L]` 列出所有場景

### 目前場景設定

| 按鍵 | 場景名稱 | 說明 |
|------|----------|------|
| `1` | AL_TEST_3.5M | 3.5 公尺測試場地 (預設) |
| `2` | AL_TEST_3M | 3 公尺測試場地 |

### 快速管理工具 (UpdateScene.bat)

無需手動編輯 JSON，使用內建工具快速新增或更新場景：

1. 執行 `UpdateScene.bat`
2. 選擇 `[2] Add / Update a scene`
3. 貼上 Antilatency Environment URL

---

## Web 3D 介面

### 控制項

| 位置 | 功能 |
|------|------|
| **Topbar** SCENE 1/2/3 | **切換場景** (直接控制 C++ 端) |
| **Topbar** AXIS FIX | Y+180(前後)、-P(上下)、-Y(左右)、-R(翻滾) 修正追蹤軸向 |
| **右側** Model Orientation | X/Y/Z 滑桿調整模型初始方向，Save 保存到瀏覽器 |
| **右側** Tracker 面板 | 位置、四元數、Euler 角度、穩定度 |
| **右側** IO Pins | 7 路 Input 狀態 + **IO7 Output 開關** (直接控制 C++ 端) |

### 3D 場景元素

| 元素 | 說明 |
|------|------|
| XYZ 軸箭頭 | 紅(X)、綠(Y)、藍(Z) 三色箭頭顯示追蹤器朝向 |
| 環境燈柱 | 自動解碼 environmentData，彩色柱體 (A=粉紅, B=青藍, C=橘色) |
| 地板格線 | 6x6m 灰色地板 + 30x30 格線 |
| IR Marker | 紅色球體標示燈柱上的紅外線標記位置 |

### 技術特點

| 項目 | 說明 |
|------|------|
| 渲染引擎 | Three.js (ES Module + import maps) |
| 相機控制 | OrbitControls（滑鼠旋轉/縮放/平移） |
| 平滑演算法 | 指數平滑 + 速度預測，幀率無關 |
| 資料持久化 | localStorage 保存模型方向與軸向修正設定 |
| FPS 顯示 | 即時顯示渲染幀率與資料更新率 |

---

## 檔案結構

```text
FIM92_C++/
├── LICENSE                       # MIT 授權
├── README.md                     # 專案說明 (本文件)
├── DEVLOG.md                     # 詳細開發紀錄
├── SOFTWARE_GUIDE.md             # 軟體組資料介面使用指南
├── DEV_DISCUSSION.md             # 開發討論紀錄
├── requirements.txt              # Python 套件依賴 (websockets)
├── .gitignore                    # Git 忽略清單
├── scenes.json                   # 場景設定檔
│
├── RunWithPipe.bat               # 啟動器：Pipe 3D 模式 (推薦)
├── RunDataServer.bat             # 啟動器：軟體組 WebSocket (精簡 JSON)
├── RunMonitor.bat                # 啟動器：Console IO 監控 (原地刷新)
├── RunWSClient.bat               # 啟動器：WebSocket Client 連線測試
├── RunTracking.bat               # 啟動器：僅 C++ 追蹤 (無 Web UI)
├── UpdateScene.bat               # 場景管理工具
│
├── TrackingMinimalDemoCpp.cpp    # C++ 核心程式
│                                 #   多場景 + 多 Tracker + 多組 HW IO + JSON 輸出
├── CMakeLists.txt                # CMake 編譯設定 (C++17)
├── update_scene.py               # 場景管理 Python 腳本
│
├── web/
│   ├── viewer_ws.html            # 3D 視覺化頁面 (Three.js + WebSocket)
│   ├── pipe_server.py            # Pipe WebSocket 伺服器 (stdin → WS + HTTP)
│   ├── data_server.py            # 軟體組 WebSocket 伺服器 (stdin → 精簡 JSON WS)
│   ├── monitor.py                # Console 監控 (stdin → 原地刷新顯示)
│   ├── ws_client.py              # WebSocket Client 連線驗證工具
│   └── server_ws.py              # 檔案監聽 WebSocket 伺服器 (備用，需搭配 RunTracking.bat)
│
├── AntilatencySdk/               # Antilatency SDK 4.5.0 (Rev.367)
│   ├── Api/                      # C++ Header Files (31 個)
│   └── Bin/                      # 預編譯二進位檔 (Windows/Linux)
│
└── build/                        # 編譯輸出
    └── Release/
        ├── TrackingMinimalDemo.exe   # 編譯產物
        ├── tracking_data.json        # 即時追蹤資料 (RunTracking.bat 模式)
        └── *.dll                     # Antilatency SDK DLLs (自動複製)
```

---

## 各檔案詳細說明

### TrackingMinimalDemoCpp.cpp（C++ 核心程式）

主程式，負責所有追蹤邏輯與硬體通訊。支援多組 Tracker + 多組 HW Extension Module（per-tracker IO）。

**主要元件：**

| 元件 | 說明 |
|------|------|
| `SceneConfig` 結構 | 場景設定：name、environmentData、placementData |
| `TrackerInstance` 結構 | 追蹤器實例：node、cotask、id、type、number |
| `HWExtInstance` 結構 | HW Extension 實例：node、cotask、type、inputPins、outputPinIO7 |
| JSON 解析器 | 自製 JSON 解析（無第三方依賴），解析 scenes.json |
| `getNodeType()` | 讀取裝置 Type 屬性 |
| `getNodeNumber()` | 讀取裝置 Number 屬性 |
| `getAllIdleTrackingNodes()` | 找出所有閒置的 Alt Tracking 節點 |
| `getAllIdleExtensionNodes()` | 找出所有閒置的 HW Extension 節點 |
| `typeToTag()` | Type → Tag 映射（Stinger→A, Helmet→B, Binoculars→C） |
| `getKeyPress()` | 非阻塞鍵盤輸入（Windows `_kbhit()`/`_getch()`） |
| `switchScene()` | 場景切換：停止追蹤→建新 Environment→重新掃描 |
| `main()` | 主函式：參數解析、SDK 載入、主迴圈 |

**主迴圈流程（500 Hz）：**

1. 讀取鍵盤輸入（L/1-9/O/Q）
2. 檢查 Device Network 更新 (`getUpdateId()`)
3. 清理已斷線的 Tracker（`isTaskFinished()`）
4. 偵測並啟動新的閒置 Alt Tracker
5. 偵測並啟動所有閒置 Extension Module（每組 7 Input + IO7 Output，透過 Type 配對 Tracker）
6. 讀取所有 Tracker 的追蹤狀態（`getExtrapolatedState()`）
7. 讀取各 Tracker 配對的 IO 腳位狀態（per-tracker IO）
8. 輸出：Console 文字 + JSON 檔案（標準模式）或 stdout JSON（--json 模式）

**關鍵技術：**

- **Atomic File Write**：先寫 `.tmp` 再 `rename`，避免讀取端讀到不完整 JSON
- **外推預測**：`getExtrapolatedState(placement, 0.005f)` 預測 5ms 後的位置
- **跨平台**：Windows（DLL）/ Linux（SO，支援 x86_64/aarch64/armv7l）

### web/pipe_server.py（Pipe WebSocket 伺服器，140 行）

零檔案 I/O 的高效能伺服器，讀取 C++ 的 stdout 並透過 WebSocket 廣播。

**架構：**

```
C++ --json stdout → pipe → stdin_reader thread → asyncio broadcast → WebSocket clients
                                                                      ↑
                                                            HTTP :8080 serves viewer_ws.html
```

**主要元件：**

| 元件 | 說明 |
|------|------|
| `stdin_reader()` | 獨立線程讀取 stdin，驗證 JSON 格式，注入 envData |
| `inject_env_data()` | 從 scenes.json 載入 environmentData 並注入到 JSON 資料 |
| `ws_handler()` | WebSocket 連線管理，支援接收控制指令 |
| `send_key_to_tracker()` | 透過 PowerShell 發送按鍵到 C++ 視窗（Windows 限定） |
| `Handler` | HTTP 伺服器，`/` 和 `/index.html` 導向 viewer_ws.html |

### web/data_server.py（軟體組 WebSocket 伺服器）

專為軟體組設計的精簡 WebSocket 資料轉發器，無 HTTP server、無 3D 視覺化。

**架構：**

```
C++ --json stdout → pipe → os.read() unbuffered → regex 精簡化 → WebSocket broadcast
```

**主要元件：**

| 元件 | 說明 |
|------|------|
| `stdin_reader()` | OS 層級 unbuffered read（`os.read(fd, 65536)`），避免 Python stdin buffering |
| `transform_json()` | Pre-compiled regex 提取 tracker 欄位，轉換為精簡 JSON |
| `stats_reporter()` | 即時顯示 `[RX] xxx/sec [TX] xxx/sec \| Clients: n` |
| `asyncio.Event` | 信號機制取代 sleep，避免 Windows 15.6ms 計時器限制 |

**特點：**
- 可配置 Host/Port（`--host` / `--port` 參數）
- 預設綁定 `0.0.0.0`（支援跨機器 LAN 連線）
- ~128 msg/sec 推送速率

### web/monitor.py（Console IO 監控）

讀取 C++ JSON 並以 ANSI escape codes 原地刷新顯示，方便觀察多組 Tracker 的 IO 狀態。

**主要特點：**
- 每個 Tracker 獨立顯示：Tag、位置、旋轉、IO 8-bit 狀態
- IO 各腳位標籤（IO1~IO8）+ 高亮顯示 active 狀態
- ~30fps 顯示刷新，FPS 計數器顯示資料接收速率
- 使用 stderr 輸出（stdout 保留給 pipe）

### web/ws_client.py（WebSocket 連線驗證工具）

連線到 data_server.py 或 pipe_server.py，顯示原始 JSON 和接收速率。

**主要特點：**
- 顯示軟體組實際收到的原始 JSON 字串
- 即時 RX 速率（msg/sec）、frame count、message size
- 可配置連線 URL（`--url` 參數）
- ~20fps 顯示刷新

### web/viewer_ws.html（3D 視覺化介面，755 行）

基於 Three.js 的即時 3D 追蹤視覺化頁面。

**頁面結構：**

| 區域 | 說明 |
|------|------|
| CSS (L7-167) | 深色主題、Grid 佈局、響應式控制元件 |
| Topbar | 狀態指示燈、WS 連線狀態、場景切換按鈕、AXIS FIX 按鈕、FPS/Data Rate |
| 3D Viewport | Three.js 場景：地板、格線、座標軸、Tracker 模型、燈柱 |
| Right Panel | Model Orientation 滑桿、Tracker 資料卡片、IO 面板 |
| JavaScript | WebSocket 連線、JSON 解析、Three.js 更新、localStorage 持久化 |

**平滑演算法：**

```javascript
// 指數平滑：物件平滑追蹤目標
const smoothFactor = 1 - Math.pow(1 - SMOOTHING, deltaTime);
obj.group.position.lerp(predictedPos, smoothFactor);

// 速度預測：外推位置減少延遲感
predictedPos.addScaledVector(velocity, timeSinceData * PREDICTION_FACTOR);
```

### update_scene.py（場景管理工具，151 行）

互動式 CLI 工具，用於管理 `scenes.json` 中的場景設定。

| 功能 | 說明 |
|------|------|
| List scenes | 列出所有已設定的場景 |
| Add / Update | 從 Antilatency Environment URL 自動解析並新增/更新場景 |
| Delete | 依編號刪除場景 |
| 自動備份 | 儲存前自動建立 `.bak` 備份 |

### CMakeLists.txt（編譯設定，28 行）

| 設定 | 說明 |
|------|------|
| C++ 標準 | C++17（filesystem、structured bindings） |
| SDK 整合 | `AntilatencySdk/Api/` include path |
| 跨平台 | Windows DLL / Linux SO（自動偵測架構） |
| Post-Build | 自動複製 SDK 動態函式庫到執行檔目錄 |

### 啟動腳本

| 腳本 | 說明 |
|------|------|
| `RunWithPipe.bat` | 推薦方案：C++ → pipe_server.py → WebSocket + HTTP 3D 視覺化 |
| `RunDataServer.bat` | 軟體組方案：C++ → data_server.py → 精簡 JSON WebSocket（互動式 Host/Port） |
| `RunMonitor.bat` | IO 監控：C++ → monitor.py → Console 原地刷新（多組 IO 狀態） |
| `RunWSClient.bat` | 連線測試：WebSocket Client（互動式輸入 Server IP/Port） |
| `RunTracking.bat` | 純 C++ 模式：Console 顯示 + tracking_data.json 輸出 |
| `UpdateScene.bat` | 啟動 update_scene.py 互動式場景管理 |

---

## 編譯

```bash
# Windows
cmake -B build -A x64
cmake --build build --config Release

# Linux
cmake -B build && cmake --build build
```

### 環境需求

- Windows 10/11 (64-bit) 或 Linux (x86_64 / aarch64 / armv7l)
- C++17 (MSVC 2019+)、CMake 3.10+
- Python 3.x + `pip install websockets`
- Antilatency Alt Tracker + Extension Module (USB)

---

## 鍵盤操作

| 按鍵 | 功能 |
|------|------|
| `1`-`9` | 切換場景 |
| `L` | 列出場景 |
| `O` | 切換 IO7 Output |
| `Q` | 退出程式 |

---

## Antilatency SDK

本專案使用 **Antilatency SDK 4.5.0** (Rev.367)，包含以下核心元件：

| 函式庫 | 版本 | 用途 |
|--------|------|------|
| AntilatencyDeviceNetwork | v9.2.0 | USB 裝置列舉與通訊 |
| AntilatencyAltTracking | v6.1.0 | 6-DOF 位置/旋轉追蹤 |
| AntilatencyAltEnvironmentSelector | v1.0.4 | 環境設定載入 |
| AntilatencyHardwareExtensionInterface | v3.1.0 | I/O 腳位控制 |

### 支援的環境類型

| 類型 | 說明 |
|------|------|
| Pillars | 直立式發光柱陣列（目前使用） |
| Rectangle | 矩形邊界標記 |
| HorizontalGrid | 地面/牆面格線 |
| Sides | 側牆標記 |
| Arbitrary2D | 自訂 2D 排列 |

---

## 6DOF 資料說明

```
6DOF = 3 軸平移 + 3 軸旋轉

平移 P(x, y, z):              旋轉 R(qx, qy, qz, qw):
  x = 左右移動 (公尺)           四元數表示 3 軸旋轉
  y = 上下移動 / 高度 (公尺)     可轉換為 Euler 角度:
  z = 前後移動 (公尺)             Yaw   (偏航/左右轉)
                                  Pitch (俯仰/上下看)
                                  Roll  (翻滾/歪頭)
```

### 硬體更新率

| 元件 | 內部更新率 | 說明 |
|------|-----------|------|
| Alt Tracker IMU | 2000 Hz | 加速度計 + 陀螺儀融合 |
| 光學追蹤 | 依標記可見度 | 紅外線標記定位 |
| IO Extension Module | 200 Hz | Pin 狀態每 5ms 更新一次 |
| C++ 主迴圈 | 500 Hz | 每 2ms 輪詢一次 |

---

## 授權

MIT License

---

> - 詳細開發歷程、技術細節、效能分析請見 [DEVLOG.md](DEVLOG.md)
> - 軟體組資料介面使用指南請見 [SOFTWARE_GUIDE.md](SOFTWARE_GUIDE.md)
> - 開發討論紀錄請見 [DEV_DISCUSSION.md](DEV_DISCUSSION.md)

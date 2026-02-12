# FIM92 開發紀錄 (Development Log)

本文件為 FIM92 Antilatency Tracking System 的完整開發記錄，包含所有階段的技術細節與變更歷程。

---

## 系統架構

```
┌─────────────────────────────────────────────────────┐
│                    Main Application                 │
│                TrackingMinimalDemoCpp.cpp            │
│                      (676 行)                       │
├──────────┬──────────┬──────────┬────────────────────┤
│ Scene    │ Multi-   │ HW IO    │ Keyboard           │
│ Manager  │ Tracker  │ Manager  │ Input              │
│          │ Manager  │          │                    │
├──────────┴──────────┴──────────┴────────────────────┤
│              Antilatency SDK 4.5.0 (Rev.367)        │
├──────────┬──────────┬──────────┬────────────────────┤
│ Device   │ Alt      │ Env      │ HW Extension       │
│ Network  │ Tracking │ Selector │ Interface          │
│ v9.2.0   │ v6.1.0   │ v1.0.4   │ v3.1.0             │
└──────────┴──────────┴──────────┴────────────────────┘
           ↕ USB / Device Network
┌──────────────────────────────────────────────────────┐
│          Antilatency Hardware Devices                │
│  ┌───────────────┐ ┌───────────────┐ ┌─────────────┐ │
│  │ Alt #1        │ │ Alt #2        │ │ Extension   │ │
│  │ Type:Stinger  │ │ Type:Binocul. │ │ Type:AC50   │ │
│  │ Number:1      │ │ Number:2      │ │ 7In + 1Out  │ │
│  └───────────────┘ └───────────────┘ └─────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 完整資料流架構

```
┌────────────────────────────────────────────────────────────────────────┐
│                          三種通訊模式                                  │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Mode 1: Pipe (推薦, ~64 Data/s, ~2ms 延遲)                           │
│  ┌──────────────┐  stdout   ┌───────────────┐  WS    ┌──────────────┐ │
│  │ C++ --json   │───pipe───►│pipe_server.py │──8765─►│viewer_ws.html│ │
│  │ (500Hz JSON) │           │HTTP :8080     │        │ Three.js 3D  │ │
│  └──────────────┘           └───────┬───────┘        └──────┬───────┘ │
│                                     │ envData 注入           │ keypress │
│                                     │ from scenes.json       │ 反向控制 │
│                                     └────────────────────────┘         │
│                                                                        │
│  Mode 2: WebSocket File (備用, ~20-28 Data/s, ~15-50ms 延遲)          │
│  ┌──────────────┐  file     ┌───────────────┐  WS    ┌──────────────┐ │
│  │ C++ 標準模式 │──write───►│server_ws.py   │──8765─►│viewer_ws.html│ │
│  │ (500Hz 寫檔) │           │1ms polling    │        │ Three.js 3D  │ │
│  └──────────────┘           │HTTP :8080     │        └──────────────┘ │
│       │                     └───────────────┘                          │
│       └── tracking_data.json (atomic write: .tmp → rename)             │
│                                                                        │
│  Mode 3: Pure C++ (無 Web UI, 500Hz 檔案 + Console)                   │
│  ┌──────────────┐                                                      │
│  │ C++ 標準模式 │─── Console 文字輸出 (160 字寬，\r 覆寫)             │
│  │              │─── tracking_data.json (供軟體組讀取)                 │
│  └──────────────┘                                                      │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1：基礎追蹤 Demo (初始版本)

**目標**：實現單一 Alt Tracker + 單一 HW IO 的最小可行程式

### 1.1 SDK 載入

- 載入 4 個 SDK 動態函式庫：
  - `AntilatencyDeviceNetwork` — USB 裝置列舉與通訊
  - `AntilatencyAltTracking` — 6-DOF 追蹤
  - `AntilatencyAltEnvironmentSelector` — 環境設定載入
  - `AntilatencyHardwareExtensionInterface` — I/O 控制
- 跨平台路徑：Windows 直接載 DLL 名稱，Linux 需組合完整 `.so` 路徑

### 1.2 基本流程

- 透過命令列參數傳入 Environment Data 和 Placement Data
- `getIdleTrackingNode()` 取得第一個閒置的 Tracking Node
- `getIdleExtensionNode()` 取得第一個閒置的 Extension Node
- 主迴圈 60 FPS 輪詢裝置狀態，輸出 `P(x,y,z) R(qx,qy,qz,qw) S:stage IO:pinStates`
- 單一場景、單一 Tracker 的設計

### 1.3 限制

- 只能透過命令列傳入一組 Environment，無法在執行中切換場景
- 只追蹤第一個找到的閒置 Alt Node，無法同時使用多個 Tracker

---

## Phase 2：多場景 + 多 Alt 重構

**目標**：支援多場景切換與多 Alt 同時追蹤

### 2.1 資料結構設計

```cpp
// 場景設定結構 (TrackingMinimalDemoCpp.cpp L26-30)
struct SceneConfig {
    std::string name;            // 場景名稱
    std::string environmentData; // Antilatency 環境序列化資料
    std::string placementData;   // 座標系轉換資料
};

// 追蹤器實例結構 (L35-41)
struct TrackerInstance {
    Antilatency::DeviceNetwork::NodeHandle node; // 裝置節點
    Antilatency::Alt::Tracking::ITrackingCotask cotask; // 追蹤任務
    int id;            // 追蹤器編號
    std::string type;   // 裝置類型 (從 AntilatencyService 設定)
    std::string number; // 裝置編號 (從 AntilatencyService 設定)
};
```

### 2.2 JSON 設定檔 (`scenes.json`)

- 新增簡易 JSON 解析器 (`extractJsonValue`, `parseSceneConfigs`)（L53-116）
- 不依賴第三方 JSON 函式庫，減少外部依賴
- 支援 `scenes` 陣列，每個元素包含 `name`, `environmentData`, `placementData`
- `trimQuotes()` 處理引號，`extractJsonValue()` 提取鍵值對
- `parseSceneConfigs()` 掃描 JSON 陣列中的所有 `{}` 物件

### 2.3 多場景切換

- `switchScene()` 函式（L200-232）：
  1. 停止所有追蹤 Cotask（`t.cotask = nullptr`）
  2. 清除 tracker 列表（`trackers.clear()`）
  3. 建立新 Environment（`environmentSelectorLibrary.createEnvironment()`）
  4. 更新 Placement（`altTrackingLibrary.createPlacement()`）
  5. 重置 `prevUpdateId = 0` 觸發裝置重新掃描
- 鍵盤快捷鍵 `[1]`-`[9]` 即時切換場景
- 向下相容：仍支援 `exe <envData> <placementData>` 單場景模式（L278-284）

### 2.4 多 Alt Tracker

- `getIdleTrackingNode()` → `getAllIdleTrackingNodes()`（L143-155）— 回傳**所有**閒置節點
- 使用 `std::vector<TrackerInstance>` 管理多個追蹤器（L377）
- 自動偵測新連接的 Alt 設備，分配遞增編號（`nextTrackerId++`）
- 已斷線的 Tracker 自動從列表移除（L451-456，`isTaskFinished()` 檢查）
- 防重複：收集 `usedNodes`，跳過已在追蹤中的節點（L458-472）

### 2.5 鍵盤控制 (Windows)

- `getKeyPress()` 使用 `_kbhit()` / `_getch()` 非阻塞讀取（L188-195）
- `[1]`-`[9]`：切換場景
- `[L]`：列出所有場景
- `[O]`：切換 IO7 Output
- `[Q]`：退出程式

### 2.6 輸出格式更新

- 增加場景指示器 `[S1]`
- 每個 Tracker 以 `T1:`, `T2:` 前綴區分
- 行寬從 130 擴展到 160 以容納多 Tracker 資料（L646）
- 使用 `\r` 覆寫同一行，避免 Console 不斷捲動

---

## Phase 3：Type 裝置類型識別

**目標**：透過 Antilatency 的 Type 屬性識別各個硬體裝置的用途（例如區分「刺針飛彈」與「望遠鏡」）

**背景**：
Antilatency 裝置可以在 AntilatencyService 軟體中設定 Type 屬性，寫入硬體記憶體。程式端可透過 `network.nodeGetStringProperty(node, "Type")` 讀取。

### 3.1 Type 設定流程 (硬體端)

1. 執行 **AntilatencyService**
2. 進入 **Device Network** 分頁
3. 找到目標裝置節點
4. 設定 **Type** 名稱（例如 `Stinger`、`Binoculars`、`ExBoard`、`AC50`）
5. Type 寫入硬體記憶體，換電腦也會保留

### 3.2 程式端實作

```cpp
// 讀取裝置 Type (返回空字串表示未設定) (L121-127)
static std::string getNodeType(
    Antilatency::DeviceNetwork::INetwork network,
    Antilatency::DeviceNetwork::NodeHandle node)
{
    try {
        return network.nodeGetStringProperty(node, "Type");
    } catch (...) {
        return "";
    }
}
```

### 3.3 變更內容

- `TrackerInstance` 新增 `type` 和 `number` 欄位，儲存追蹤器的 Type 和 Number
- 新增 `getNodeType()` 和 `getNodeNumber()` 輔助函式，安全地讀取屬性（未設定時回傳空字串）
- Alt Tracker 連接時讀取並記錄 Type 和 Number（L480-481）
- Extension Module 連接時讀取並記錄 Type（L517）
- 連接訊息顯示：`Alt Tracker #1 Number:1 [Stinger] connected!`
- 即時輸出加入 Type 標示：`T1[Stinger]:P(...)` 和 `IO[AC50]:10101010`

### 3.4 應用範例

| 裝置 | Type | 程式中的顯示 |
|------|------|-------------|
| 刺針飛彈上的 Alt Tracker | `Stinger` | `T1[Stinger]:P(...) R(...) S:2` |
| 望遠鏡上的 Alt Tracker | `Binoculars` | `T2[Binoculars]:P(...) R(...) S:2` |
| IO 擴充板 | `AC50` | `IO[AC50]:10101010 IO7out:OFF` |
| 未設定 Type 的裝置 | (空) | `T3:P(...) R(...) S:2` |

---

## Phase 4：Web 視覺化效能優化

**目標**：解決 3D 視覺化介面的卡頓問題，實現流暢的動態追蹤顯示

**問題分析**：
原本的實作有多個效能瓶頸：

1. **檔案讀寫競爭**：C++ 直接寫入 `tracking_data.json`，Python server 同時讀取時可能讀到不完整的 JSON
2. **插值方式不當**：使用 frame-based lerp，物體會「衝→停→衝→停」
3. **Server 效能**：Python 單線程 HTTP server，每次請求都從磁碟讀取
4. **像素比過高**：高 DPI 螢幕渲染負擔過重

### 4.1 C++ 端：原子檔案寫入

```cpp
// 先寫臨時檔，再原子重命名 (L650-661)
std::ofstream jsonFile("tracking_data.json.tmp");
jsonFile << js.str();
jsonFile.close();
try {
    std::filesystem::rename("tracking_data.json.tmp", "tracking_data.json");
} catch (...) {
    // Fallback: copy + delete
    std::filesystem::copy_file("tracking_data.json.tmp", "tracking_data.json",
        std::filesystem::copy_options::overwrite_existing);
    std::filesystem::remove("tracking_data.json.tmp");
}
```

### 4.2 Python Server：多線程處理

```python
# pipe_server.py: 獨立 stdin 讀取線程 + asyncio WebSocket 廣播
threading.Thread(target=stdin_reader, args=(loop,), daemon=True).start()

# server_ws.py: 1ms 非同步輪詢 + WebSocket 廣播
await asyncio.sleep(0.001)  # 1ms polling
```

### 4.3 Web 端：指數平滑 + 速度預測

```javascript
// 指數平滑：物件平滑追蹤目標 (viewer_ws.html)
const smoothFactor = 1 - Math.pow(1 - SMOOTHING, deltaTime);
obj.group.position.lerp(predictedPos, smoothFactor);

// 速度預測：外推位置減少延遲感
predictedPos.copy(targetPos);
predictedPos.addScaledVector(velocity, timeSinceData * PREDICTION_FACTOR);
```

### 4.4 渲染優化

```javascript
// 限制像素比，避免高 DPI 螢幕過度渲染
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
// 啟用高效能模式
new THREE.WebGLRenderer({ powerPreference: 'high-performance' });
```

### 4.5 最終效能數據

| 項目 | 數值 |
|------|------|
| C++ 輪詢/寫入頻率 | **500 Hz (2ms)** |
| Web 輪詢頻率 (HTTP) | ~66 Hz (15ms) |
| WebSocket 推送頻率 | ~500 Hz (即時) |
| 3D 渲染 FPS | 60-180 Hz (自動) |
| 平滑因子 | 0.6-0.7 |
| 外推時間 | 0.005f (5ms) |

**成效**：
- 3D 物體移動從「跳躍式」變成「持續滑動」
- IO 板機反應延遲 < 10ms
- 可達 Antilatency 標榜的 2ms 低延遲追蹤

---

## Phase 5：軸向修正 + 環境燈柱視覺化

**目標**：提供即時軸向調整工具，並在 3D 場景中顯示 Antilatency 燈柱位置

### 5.1 3D 模型改為 XYZ 軸箭頭

- 移除原本的 URS 設備模型，改為三色軸箭頭 (X=紅 0xff3333, Y=綠 0x33ff33, Z=藍 0x3333ff)
- 與場景底部的世界座標軸顏色一致，讓開發者直覺理解追蹤器朝向
- 原點白色球體標示追蹤器位置

### 5.2 模型方向調整面板 (Model Orientation)

- 右側面板新增 X/Y/Z 三軸滑桿（-180° ~ 180°）
- 拖拉即時預覽，調整追蹤器軸箭頭的初始方向
- **Save** 按鈕存到 localStorage，下次開啟自動載入
- **Reset** 按鈕恢復預設值

### 5.3 追蹤軸向修正按鈕 (AXIS FIX)

Topbar 新增 4 個切換按鈕，修正追蹤資料的旋轉對應：

| 按鈕 | 功能 | 適用問題 |
|------|------|---------|
| **Y+180** | Yaw +180° | 前後顛倒 |
| **-P** | 反轉 Pitch | 上下反向 |
| **-Y** | 反轉 Yaw | 左右反向 |
| **-R** | 反轉 Roll | 翻滾反向 |

- 按鈕狀態自動存到 localStorage
- 模型方向（滑桿）和追蹤修正（按鈕）是獨立的兩層修正

### 5.4 環境燈柱自動解碼與顯示

- `pipe_server.py` 啟動時讀取 `scenes.json`，將 `environmentData` 注入 WebSocket 資料流
- 前端自動解碼 `AntilatencyAltEnvironmentPillars` 二進位格式（Base64URL → IEEE 754 float）
- 3D 場景中顯示燈柱：彩色柱體（A=粉紅, B=青藍, C=橘色）+ 紅色 IR marker 球體
- **任何新增的場景**只要在 `scenes.json` 中加入 environmentData，前端會自動解析並顯示對應燈柱

---

## Phase 6：體驗優化與工具完善

**目標**：優化視覺體驗、支援跨裝置協作，並簡化場景管理流程。

### 6.1 3D 場景視覺優化

- **地板材質變更**：背景保持黑色 (0x1a1a1a)，地板改為實體灰色平面 (0x555555)，格線改為淺灰色 (主線 0xaaaaaa, 副線 0x777777)。
- **視覺對比提升**：灰色地板更能襯托出彩色軸箭頭與燈柱，減少視覺疲勞。

### 6.2 跨電腦通訊支援

- **WebSocket 綁定調整**：Server 綁定 IP 改為 `0.0.0.0`（pipe_server.py L132、server_ws.py L135），允許區域網路內其他電腦連線。
- **前端參數支援**：`viewer_ws.html` 支援 URL 參數 `?host=IP`，例如 `http://localhost:8080?host=192.168.1.100`。
- **應用場景**：一台電腦負責跑 C++ 追蹤 (連接 Tracker)，另一台輕薄筆電或平板透過瀏覽器監看 3D 畫面。

### 6.3 場景管理工具 (UpdateScene)

- **新增 `UpdateScene.bat` 與 `update_scene.py`**（151 行）
- 提供互動式選單：
  1. List scenes (列出目前場景)
  2. Add / Update a scene (新增或更新場景)
  3. Remove a scene (刪除場景)
  4. Exit
- **自動化流程**：
  - 使用者只需貼上 Antilatency Environment URL
  - `urllib.parse` 自動解析 `data` 和 `name` 參數
  - 同名場景自動更新，新名稱自動新增
  - 儲存前自動建立 `.bak` 備份
  - 無需手動編輯 JSON 檔案避免格式錯誤

---

## Phase 7：雙向通訊與 Web 控制

**目標**：實現從 Web UI 反向控制 C++ 主程式，提供更整合的操作體驗。

### 7.1 Web-to-C++ 控制流

```
┌──────────────┐   WebSocket   ┌────────────────┐  PowerShell  ┌───────────┐
│ Web UI       │   {type:      │ pipe_server.py │  SendKeys    │ C++ App   │
│ (viewer.html)│──"keypress"──►│                ├──────────────►│ (Console) │
└──────────────┘   key:"2"}    └────────────────┘              └───────────┘
```

**實作細節**：

1. **前端觸發**：使用者在 `viewer_ws.html` 點擊按鈕（如切換場景、開關 IO7）
2. **WebSocket 訊息**：JavaScript 發送 `{"type": "keypress", "key": "2"}` 給 Python
3. **Python 伺服器解析**：`pipe_server.py` 的 `ws_handler()` 接收並解析 JSON（L86-93）
4. **發送按鍵**：`send_key_to_tracker()` 透過 PowerShell `WScript.Shell.SendKeys()` 送到 C++ 視窗
   - 需要 C++ 視窗標題為 `FIM92_Tracker_Window`（由 `.bat` 的 `title` 命令設定）
   - 在獨立 daemon 線程執行，避免阻塞 WebSocket 迴圈
5. **C++ 接收**：主迴圈的 `getKeyPress()` 讀取到按鍵，執行對應動作

### 7.2 支援的控制指令

| Web UI 按鈕 | WebSocket 訊息 | C++ 動作 |
|------------|---------------|----------|
| SCENE 1/2/3 | `{"type":"keypress","key":"1"}` | `switchScene()` 切換場景 |
| IO7 Toggle | `{"type":"keypress","key":"O"}` | 切換 IO7 Output 狀態 |

**成效**：
- 使用者無需在 C++ 主控台和網頁之間切換，所有主要操作都可以在 Web 介面完成
- 實現了從顯示端到控制端的完整閉環

---

## Phase 8：Number 裝置編號識別

**目標**：支援透過 Antilatency 的 Number 屬性區分同類型的多個裝置

**背景**：
當有多個相同 Type 的 Alt Tracker（例如 2 個 Stinger）時，僅靠 Type 無法區分。Number 屬性提供額外的識別維度。

### 8.1 程式端實作

```cpp
// 讀取裝置 Number (L132-138)
static std::string getNodeNumber(
    Antilatency::DeviceNetwork::INetwork network,
    Antilatency::DeviceNetwork::NodeHandle node)
{
    try {
        return network.nodeGetStringProperty(node, "Number");
    } catch (...) {
        return "";
    }
}
```

### 8.2 變更內容

- `TrackerInstance` 新增 `number` 欄位（L40）
- 新增 `getNodeNumber()` 輔助函式（L132-138）
- Alt Tracker 連接時讀取並記錄 Number（L481）
- Console 輸出：有 Number 時顯示 `#1[Stinger]:P(...)`，無 Number 時顯示 `T1[Stinger]:P(...)`（L554-558）
- JSON 輸出新增 `number` 欄位（L610）

### 8.3 設定方法

與 Type 相同，在 AntilatencyService → Device Network 中設定：
1. 找到目標裝置節點
2. 設定 **Number**（例如 `1`、`2`）
3. Number 寫入硬體記憶體，換電腦也會保留

---

## Phase 9：Pipe 模式實作（零檔案 I/O）

**目標**：消除檔案 I/O 瓶頸，實現最低延遲的資料傳輸

### 9.1 --json 命令列參數

C++ 程式新增 `--json` (或 `-j`) 參數支援（L257-265）：

```bash
# 標準模式：Console 輸出 + 檔案寫入
TrackingMinimalDemo.exe "scenes.json"

# JSON 模式：僅 stdout 輸出 JSON (供 pipe 使用)
TrackingMinimalDemo.exe --json "scenes.json"
```

JSON 模式下的行為差異：
- `std::cout.setf(std::ios::unitbuf)` 禁用輸出緩衝（L298）
- 不輸出任何除錯訊息到 stdout（改用 stderr）
- 每 2ms 輸出一行完整 JSON 到 stdout（L642）
- 不寫入 `tracking_data.json` 檔案

### 9.2 pipe_server.py 架構

```python
# 三個並行元件：
1. stdin_reader thread  — 讀取 C++ stdout（每行一筆 JSON）
2. asyncio WebSocket    — 廣播到所有連線的瀏覽器
3. HTTP server thread   — 提供 viewer_ws.html 靜態檔案
```

**關鍵實作**：

```python
# stdin 讀取線程 (pipe_server.py L69-77)
def stdin_reader(loop):
    global latest_data
    for line in sys.stdin:
        line = line.strip()
        if line.startswith('{') and line.endswith('}'):
            line = inject_env_data(line)
            latest_data = line
            asyncio.run_coroutine_threadsafe(broadcast(line), loop)
```

### 9.3 RunWithPipe.bat 流程

```batch
title FIM92_Tracker_Window          # 設定視窗標題（PowerShell SendKeys 需要）
chcp 65001                          # UTF-8 編碼
cd /d "%~dp0build\Release"          # 切換到 build 目錄
copy /Y scenes.json                 # 複製最新 scenes.json
start "" "http://localhost:8080"    # 開啟瀏覽器
TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0web\pipe_server.py"
```

### 9.4 效能對比

| 項目 | Pipe 模式 | WS 檔案模式 |
|------|----------|------------|
| 資料傳輸方式 | stdout → pipe → stdin | 寫檔 → 讀檔 |
| 資料更新率 | **~64 Data/s** | ~20-28 Data/s |
| 延遲 | **~2ms** | ~15-50ms |
| 檔案 I/O | **無** | 每幀讀寫一次 |
| 穩定性 | 非常穩定 | 可能讀到不完整 JSON |

---

## 兩種通訊模式效能比較

### 為什麼 WS 檔案模式較慢？

1. **Windows NTFS 時間戳精度**：Windows 檔案修改時間精度約 15ms，限制了檔案變化偵測頻率
2. **檔案 I/O 開銷**：每次都要開檔 → 讀取 → 關檔，比記憶體管道慢得多
3. **讀寫競爭**：C++ 寫入和 Python 讀取可能同時發生，導致讀到不完整資料
4. **字串比對**：每次都要比對整個 JSON 字串是否變化

### server_ws.py 的優化策略

```python
# 1. 預建注入字串片段，避免每幀 JSON parse/stringify
scenes_inject_snippet[i] = ',"envData":"' + env + '"'

# 2. 字串操作注入，比 json.loads/json.dumps 快 10 倍以上
def inject_env_data_fast(raw_json):
    last_brace = raw_json.rfind('}')
    return raw_json[:last_brace] + scenes_inject_snippet[scene_id] + '}'

# 3. 字串比對偵測變化（不解析 JSON）
if content and content != last_content and clients:
```

### 結論

**Pipe 模式是唯一推薦的正式使用方案**。WS 檔案模式僅作為 Pipe 不可用時的備用方案。

---

## 跨電腦通訊方案

### 方案一：Pipe + WebSocket over LAN (目前已實作，推薦)

```
追蹤主機 (192.168.1.100)                    顯示端電腦
┌──────────────────────────┐                ┌─────────────────────┐
│ C++ --json | pipe_server │◄── 有線網路 ──►│ 瀏覽器開啟:         │
│ WebSocket on 0.0.0.0:8765│  (Ethernet)    │ http://192.168.1.100│
│ HTTP on 0.0.0.0:8080     │                │ :8080               │
└──────────────────────────┘                └─────────────────────┘
```

- 最簡單，不需要額外開發
- 另一台電腦只需要瀏覽器
- 延遲 = Pipe 延遲 + 網路延遲 (區域網通常 < 1ms)
- 用有線乙太網 (Ethernet) 連接最穩定

### 方案二：TCP Socket (未來可選)

如果 WebSocket 不夠用，可以考慮用 raw TCP socket 直接傳輸 JSON：
- 更低的通訊開銷（無 HTTP 握手）
- 需要自行實作接收端程式
- 適合嵌入式裝置或自定義軟體

### 方案三：UDP 廣播 (未來可選)

最低延遲但無傳輸保證：
- 適合即時性要求極高但允許偶爾丟包的場景
- 可以一對多廣播
- 需要自行實作發送/接收端

---

## 輸出格式

### Console 輸出格式

有 Number 時：
```
[S<場景編號>] #<Number>[<Type>]:P(x,y,z) R(qx,qy,qz,qw) S:<穩定度>  IO[<Type>]:<7位元> IO7out:<ON/OFF>
```

無 Number 時：
```
[S<場景編號>] T<ID>[<Type>]:P(x,y,z) R(qx,qy,qz,qw) S:<穩定度>  IO[<Type>]:<7位元> IO7out:<ON/OFF>
```

### 實際測試範例

```
[S1] T1:P(-0.0000, 1.6800, 0.0000) R(-0.6286, 0.0094,-0.3238, 0.7071) S:1  IO[AC50]:0001000 IO7out:OFF
```

#### 逐欄解析

| 欄位 | 值 | 意義 |
|------|-----|------|
| `[S1]` | 場景 1 | 目前使用 AL_TEST_3.5M 場景 |
| `T1:` | Tracker #1 | Alt Tracker（未設定 Type，若有設定會顯示如 `T1[Stinger]:`） |
| `P(-0.0000, 1.6800, 0.0000)` | X=0m, Y=1.68m, Z=0m | 位置座標（Y 軸 = 高度），單位：公尺 |
| `R(-0.6286, 0.0094, -0.3238, 0.7071)` | 四元數 (qx, qy, qz, qw) | 裝置目前的朝向/旋轉 |
| `S:1` | 3DOF | 只有旋轉追蹤，沒有位置追蹤（因為沒有立柱） |
| `IO[AC50]` | Type = AC50 | IO 擴充板，Type 已從硬體讀取成功 |
| `0001000` | IOA4 = 1，其餘 = 0 | 第 4 腳 (IOA4) 被觸發，其餘放開 |
| `IO7out:OFF` | IO7 輸出關閉 | Output 腳位為 Low |

### JSON 輸出格式

```json
{
    "scene": 1,
    "sceneName": "AL_TEST_3.5M",
    "trackers": [
        {
            "id": 1,
            "type": "Stinger",
            "number": "1",
            "px": 0.123456, "py": 1.678901, "pz": -0.045678,
            "rx": -0.628600, "ry": 0.009400, "rz": -0.323800, "rw": 0.707100,
            "stability": 2
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

> **注意**：使用 Pipe/WebSocket 模式時，Python server 會自動從 `scenes.json` 注入 `envData` 欄位，C++ 原始 JSON 輸出不包含此欄位。

---

## IO 腳位說明

### Input 腳位 (7 個)

使用 Active Low 邏輯：

| 腳位 | 索引 | 方向 | Low (按下) | High (放開) |
|------|------|------|-----------|-------------|
| IO1  | 0    | Input | 1         | 0           |
| IO2  | 1    | Input | 1         | 0           |
| IOA3 | 2    | Input | 1         | 0           |
| IOA4 | 3    | Input | 1         | 0           |
| IO5  | 4    | Input | 1         | 0           |
| IO6  | 5    | Input | 1         | 0           |
| IO8  | 6    | Input | 1         | 0           |

### Output 腳位 (1 個)

| 腳位 | 方向 | 控制方式 | High (ON) | Low (OFF) |
|------|------|---------|----------|------------|
| IO7  | **Output** | 按鍵 `[O]` 或 Web 按鈕切換 | 輸出高電位 | 輸出低電位 (預設) |

- 啟動時 IO7 預設為 **Low (OFF)**（L383）
- 使用 `hwCotask.createOutputPin()` 建立（L512-514）
- 使用 `outputPin.setState()` 切換狀態（L425-427）
- 可用於控制繼電器、LED、蜂鳴器等外部裝置

### 腳位定義（C++ 原始碼）

```cpp
// Input pins 定義 (L389-397)
const Antilatency::HardwareExtensionInterface::Interop::Pins inputPinDefs[] = {
    Pins::IO1, Pins::IO2, Pins::IOA3, Pins::IOA4,
    Pins::IO5, Pins::IO6, Pins::IO8
};

// Output pin: IO7 (L512-514)
outputPinIO7 = hwCotask.createOutputPin(
    Pins::IO7,
    PinState::Low);  // 初始狀態：Low
```

---

## 追蹤穩定度 (Stability Stage) 詳細說明

| 階段 | S 值 | 名稱 | 說明 | 資料可用性 |
|------|------|------|------|-----------|
| 初始化 | `S:0` | InertialDataInitialization | IMU 正在初始化 | 位置/旋轉均不可用 |
| 3DOF | `S:1` | Tracking3Dof | 僅 IMU 旋轉追蹤 | **旋轉可用，位置不可用** |
| **6DOF** | **`S:2`** | **Tracking6Dof** | **立柱光學定位 + IMU** | **位置 + 旋轉均可用** |
| 盲區 6DOF | `S:3` | TrackingBlind6Dof | 暫時遮擋，靠慣性預測 | 位置靠預測，短時間內可用 |

**重要**：`S:1`（3DOF）時 `P(x,y,z)` 位置資料不會真正移動，**必須架設立柱達到 `S:2`（6DOF）後，位置資料才準確可用**。

---

## 6DOF 資料說明

本系統提供完整的 **6 自由度 (6DOF)** 追蹤：

```
6DOF = 3 軸平移 + 3 軸旋轉

平移 P(x, y, z):              旋轉 R(qx, qy, qz, qw):
  x = 左右移動 (公尺)           四元數表示 3 軸旋轉
  y = 上下移動 / 高度 (公尺)     可轉換為 Euler 角度:
  z = 前後移動 (公尺)             Yaw   (偏航/左右轉)
                                  Pitch (俯仰/上下看)
                                  Roll  (翻滾/歪頭)
```

> **關於 "9 軸"**：9 軸是指 IMU 感測器的硬體規格（3 軸加速度計 + 3 軸陀螺儀 + 3 軸磁力計），
> 但最終輸出仍然是 6DOF（3 平移 + 3 旋轉），這已經是空間中的全部自由度。

---

## 輸出資料頻率

### Antilatency 硬體能力

| 元件 | 內部更新率 | 說明 |
|------|-----------|------|
| **Alt Tracker IMU** | 2000 Hz | 加速度計 + 陀螺儀融合 |
| **光學追蹤** | 依標記可見度 | 紅外線標記定位 |
| **IO Extension Module** | 200 Hz | Pin 狀態每 5ms 更新一次 |

### 程式設定頻率

| 環節 | 頻率 | 說明 |
|------|------|------|
| **C++ 主迴圈** | **500 Hz** | 每 2ms 輪詢一次 (`sleep_for(2ms)`) (L665) |
| **外推時間** | 5ms | `getExtrapolatedState(placement, 0.005f)` (L553) |
| **Pipe 資料率** | ~64 Hz | stdout → pipe → WebSocket |
| **WS 檔案資料率** | ~20-28 Hz | 受 NTFS 時間戳精度限制 |
| **3D 渲染** | 60-180 Hz | 依螢幕刷新率，配合平滑插值 |

### 外推時間 (Extrapolation) 說明

```cpp
// SDK 函式：取得外推後的追蹤狀態
getExtrapolatedState(placement, deltaTime)
//                             ↑ 向前預測多少秒

// 0.03f = 30ms → 預測太遠，物體會「衝過頭」再拉回來
// 0.005f = 5ms → 幾乎即時，減少預測誤差 (目前設定)
```

### 如何調整輪詢頻率？

修改 `TrackingMinimalDemoCpp.cpp` 第 665 行的 sleep 時間：

```cpp
// 目前設定：500 Hz (高速追蹤)
std::this_thread::sleep_for(std::chrono::milliseconds(2));

// 200 Hz (平衡)
std::this_thread::sleep_for(std::chrono::milliseconds(5));

// 100 Hz (省 CPU)
std::this_thread::sleep_for(std::chrono::milliseconds(10));

// 60 Hz (配合 60fps 螢幕)
std::this_thread::sleep_for(std::chrono::milliseconds(16));
```

修改後需重新編譯：`cmake --build build --config Release`

---

## Web 3D 視覺化介面

### viewer_ws.html 結構 (755 行)

| 區段 | 行數 | 說明 |
|------|------|------|
| CSS | L7-167 | 深色主題 (1a1a1a)、Grid 佈局、Topbar 48px、右面板 320px |
| HTML 結構 | L168-280 | Topbar + Viewport + Right Panel |
| JavaScript (Three.js) | L280+ | 場景初始化、WebSocket、資料更新、渲染迴圈 |

### 3D 場景設定

| 項目 | 設定值 |
|------|--------|
| 相機 FOV | 50° |
| 相機位置 | (3, 2.5, 3) |
| 地板大小 | 6x6m |
| 格線 | 30x30 subdivisions |
| 座標軸 | X=紅, Y=綠, Z=藍 |
| 光源 | Ambient light |
| 像素比限制 | `Math.min(devicePixelRatio, 2)` |

### 平滑化演算法

```
┌─────────────────────────────────────────────────────────────┐
│                    資料流與平滑化流程                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  C++ (500Hz)     WebSocket/Pipe (即時)    Render (60-180Hz) │
│  ┌─────────┐         ┌─────────┐          ┌─────────────┐   │
│  │ 追蹤資料 │ ──JSON──▶│ 目標位置 │ ──平滑──▶│ 3D 物件位置 │   │
│  └─────────┘         │ 目標旋轉 │          │ (視覺呈現)  │   │
│                      │ 速度向量 │          └─────────────┘   │
│                      └─────────┘                            │
│                           │                                 │
│                           ▼                                 │
│                   ┌───────────────┐                         │
│                   │ 指數平滑插值  │                         │
│                   └───────────────┘                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**核心演算法參數**：

| 參數 | 值 | 說明 |
|------|-----|------|
| `SMOOTHING` | 0.6-0.7 | 指數平滑因子，越高反應越快 |
| 渲染迴圈 | requestAnimationFrame | 自動匹配螢幕刷新率 |
| deltaTime 正規化 | `clock.getDelta()` | 確保不同幀率下動作速度一致 |

---

## 場景設定詳細說明

### scenes.json 格式

```json
{
    "scenes": [
        {
            "name": "場景名稱",
            "environmentData": "AntilatencyAltEnvironmentPillars~...",
            "placementData": "AAAAAA..."
        }
    ]
}
```

### 目前場地設定

| 按鍵 | 場地名稱 | 說明 |
|------|----------|------|
| `1` | AL_TEST_3.5M | 3.5 公尺測試場地 (預設) |
| `2` | AL_TEST_3M | 3 公尺測試場地 |

### 欄位說明

| 欄位 | 必填 | 說明 |
|------|------|------|
| `name` | 否 | 場景顯示名稱，未填則自動編號 (L109) |
| `environmentData` | 是 | Antilatency 環境序列化字串 |
| `placementData` | 否 | Placement 轉換資料，未填則使用預設值 (L110) |

### 如何取得 Environment Data

**方法一：從 AntilatencyService 軟體匯出**

1. 開啟 **AntilatencyService** 軟體
2. 設定好場景的標記點 (Pillars / Rectangle / Grid 等)
3. 點擊 **Export Environment** → 複製序列化字串
4. 貼到 `scenes.json` 的 `environmentData` 欄位

**方法二：從 Antilatency 環境 URL 提取**

URL 格式：
```
http://www.antilatency.com/antilatencyservice/environment?data=<環境資料>&name=<名稱>
```

使用 `UpdateScene.bat` 自動解析，或手動提取 `data=` 後到 `&name=` 前的字串。

### 支援的環境類型

| 類型 | 說明 | 適用場景 |
|------|------|----------|
| Pillars | 直立式發光柱陣列 | 大型空間、VR 場域 |
| Rectangle | 矩形邊界標記 | 小型桌面追蹤 |
| HorizontalGrid | 地面/牆面格線 | 工業定位 |
| Sides | 側牆標記 | 走廊式空間 |
| Arbitrary2D | 自訂 2D 排列 | 非規則空間 |

---

## 多場景切換設計

### 運作流程

```
使用者按下 [2] (鍵盤或 Web UI)
    │
    ▼
switchScene(1, ...) (L200-232)
    │
    ├── 停止所有追蹤 Cotask
    │   for (auto& t : trackers) t.cotask = nullptr;
    │   trackers.clear();
    │
    ├── 建立新 Environment
    │   environmentSelectorLibrary.createEnvironment(scene.environmentData)
    │
    ├── 更新 Placement
    │   altTrackingLibrary.createPlacement(scene.placementData)
    │
    └── 重置 prevUpdateId = 0
        (觸發主迴圈重新掃描裝置，自動連接所有 Tracker)
```

### 切換時序

```
時間 ──────────────────────────────────────────────►

場景1 運行中          切換          場景2 運行中
┌─────────────┐    ┌──────────┐    ┌─────────────┐
│ T1 tracking │    │ 停止所有  │    │ T1 tracking │
│ T2 tracking │──► │ Cotask   │──► │ T2 tracking │
│ IO reading  │    │ 建新 Env │     │ IO reading  │
└─────────────┘    │ 重新掃描  │    └─────────────┘
                   └──────────┘
                   使用者按 [2]
```

### 注意事項

- 切換場景時會**暫時中斷所有追蹤**，因為不同場景的標記配置不同
- 切換後 Alt Tracker 需要重新定位，Stability 會從 InertialDataInitialization 重新開始
- 若新場景的 Environment Data 無效，`switchScene()` 回傳 false，保持在當前場景
- 不同場地可以混用不同環境類型

---

## 多 Alt Tracker 設計

### 原始設計 vs 新設計

```
原始 (單 Tracker):                新設計 (多 Tracker):
┌─────────────────┐              ┌─────────────────────────┐
│ getIdleTracking │              │ getAllIdleTrackingNodes  │
│ Node()          │──→ 1 node    │ ()                      │──→ N nodes
└─────────────────┘              └─────────────────────────┘
         │                                  │
         ▼                                  ▼
┌─────────────────┐              ┌─────────────────────────┐
│ altTrackingCo-  │              │ for each idle node:     │
│ task (single)   │              │   trackers.push_back()  │
└─────────────────┘              │ → vector<TrackerInst>   │
                                 └─────────────────────────┘
```

### 自動管理流程

1. **偵測**：每次 `network.getUpdateId()` 變化時（L447），掃描所有支援的節點
2. **清理**：移除已斷線 (`isTaskFinished()`) 的 Tracker 實例（L451-456）
3. **過濾**：跳過已在使用中的節點，避免重複啟動（L458-472）
4. **啟動**：為每個新的閒置節點建立 `TrackerInstance`，分配遞增 ID + 讀取 Type/Number（L474-493）
5. **輸出**：以 `T1[Type]:`, `T2[Type]:` 或 `#1[Type]:` 前綴區分各 Tracker 的資料

### 範例輸出 (2 個 Alt Tracker + IO)

```
[S1] #1[Stinger]:P( 1.2345, 0.5678, 2.1111) R( 0.0000, 0.0000, 0.7071, 0.7071) S:2  #2[Binoculars]:P(-0.3210, 0.8888, 1.5000) R( 0.1000, 0.2000, 0.3000, 0.9000) S:2  IO[AC50]:1010100 IO7out:OFF
```

---

## 執行流程圖

```
START
  │
  ├── 解析命令列參數 (L251-288)
  │   ├── --json flag → jsonMode = true
  │   ├── 1 個參數 → 讀取 scenes.json (parseSceneConfigs)
  │   └── 2 個參數 → 舊模式 (單場景)
  │
  ├── 載入 4 個 SDK 函式庫 (L302-340)
  │   ├── AntilatencyDeviceNetwork
  │   ├── AntilatencyAltTracking
  │   ├── AntilatencyAltEnvironmentSelector
  │   └── AntilatencyHardwareExtensionInterface
  │
  ├── 建立 Device Network (USB Filter) (L342-349)
  │
  ├── 初始化第一個場景的 Environment + Placement (L352-360)
  │
  ├── 建立 Cotask Constructors (L362-373)
  │
  ├── 初始化狀態變數 (L376-398)
  │   ├── prevUpdateId = 0
  │   ├── trackers = empty vector
  │   ├── nextTrackerId = 1
  │   ├── inputPinDefs[7] = {IO1, IO2, IOA3, IOA4, IO5, IO6, IO8}
  │   └── io7State = false (OFF)
  │
  └── MAIN LOOP (500 Hz) (L405-666)
      │
      ├── [鍵盤輸入] (L407-443)
      │   ├── Q → 退出
      │   ├── L → 列出場景
      │   ├── O → 切換 IO7 Output
      │   └── 1-9 → switchScene()
      │
      ├── [裝置更新] (L445-530)
      │   ├── getUpdateId() 變化時：
      │   ├── 清理已斷線 Tracker (erase + remove_if)
      │   ├── getAllIdleTrackingNodes() → 啟動新 Tracker
      │   │   └── getNodeType() + getNodeNumber() → 讀取屬性
      │   └── getIdleExtensionNode() → 啟動 HW IO
      │       └── 建立 7 Input + IO7 Output
      │
      ├── [讀取資料] (L532-591)
      │   ├── 各 Tracker: getExtrapolatedState(placement, 0.005f)
      │   └── IO: inputPins[i].getState()
      │
      ├── [建構 JSON] (L593-638)
      │   └── scene, sceneName, trackers[], io{}
      │
      └── [輸出] (L640-662)
          ├── jsonMode → stdout JSON (一行一筆)
          └── 標準模式 → Console \r 覆寫 + atomic file write
```

---

## API 參考

### 主要函式

| 函式 | 位置 | 說明 |
|------|------|------|
| `trimQuotes(s)` | L53-58 | 移除字串前後引號 |
| `extractJsonValue(json, key)` | L60-76 | 從 JSON 字串中提取指定 key 的值 |
| `parseSceneConfigs(filename)` | L78-116 | 解析 scenes.json，回傳 `vector<SceneConfig>` |
| `getNodeType(network, node)` | L121-127 | 讀取裝置 Type 屬性 |
| `getNodeNumber(network, node)` | L132-138 | 讀取裝置 Number 屬性 |
| `getAllIdleTrackingNodes(network, constructor)` | L143-155 | 取得所有閒置的 Alt Tracking 節點 |
| `getIdleExtensionNode(network, constructor)` | L157-168 | 取得第一個閒置的 HW Extension 節點 |
| `getKeyPress()` | L188-195 | 非阻塞鍵盤輸入 (Windows only) |
| `switchScene(index, scenes, ...)` | L200-232 | 切換到指定場景 |
| `printUsage(progName)` | L237-246 | 印出使用說明 |

### 核心結構

| 結構 | 欄位 | 說明 |
|------|------|------|
| `SceneConfig` | name, environmentData, placementData | 場景設定 |
| `TrackerInstance` | node, cotask, id, type, number | 追蹤器實例 |
| `Alt::Tracking::State` | pose, stability, localAngularVelocity | 追蹤狀態 |
| `Math::floatP3Q` | position (float3), rotation (floatQ) | 位姿資料 |

### Python Server API

**pipe_server.py：**

| 函式/類別 | 說明 |
|----------|------|
| `inject_env_data(raw_json)` | JSON parse/stringify 注入 envData |
| `stdin_reader(loop)` | stdin 讀取線程 |
| `broadcast(data)` | WebSocket 廣播到所有客戶端 |
| `ws_handler(websocket)` | WebSocket 連線處理（新 API，websockets 10+） |
| `send_key_to_tracker(key)` | PowerShell 發送按鍵到 C++ 視窗 |
| `Handler` | HTTP 伺服器，`/` → viewer_ws.html |

**server_ws.py：**

| 函式/類別 | 說明 |
|----------|------|
| `inject_env_data_fast(raw_json)` | 字串操作快速注入 envData |
| `broadcast_loop()` | 1ms 輪詢 tracking_data.json + WebSocket 廣播 |
| `ws_handler(websocket)` | WebSocket 連線處理 |

**update_scene.py：**

| 函式 | 說明 |
|------|------|
| `load_scenes()` | 載入 scenes.json |
| `save_scenes(config)` | 儲存 scenes.json（含 .bak 備份） |
| `list_scenes(config)` | 列出所有場景 |
| `add_update_scene(config)` | 從 URL 新增/更新場景 |
| `delete_scene(config)` | 刪除場景 |
| `main_menu()` | 互動式 CLI 選單 |

---

## 檔案統計

| 類別 | 檔案數 | 程式碼行數 | 大小 |
|------|--------|----------|------|
| C++ 原始碼 | 1 | 676 行 | 28 KB |
| Python 腳本 | 3 | 434 行 | 17 KB |
| HTML/Web | 1 | 755 行 | 34 KB |
| Batch 腳本 | 5 | ~50 行 | 2 KB |
| CMake 設定 | 1 | 28 行 | 1 KB |
| 文件 | 2 | ~1900 行 | ~80 KB |
| SDK Headers | 31 | - | - |
| SDK Binaries | 8+ 架構 | - | ~104 MB |
| **專案總計** | **~50+ 檔案** | **~1943 行自寫程式碼** | **~110 MB** |

---

## 環境需求

- **OS**: Windows 10/11 (64-bit) 或 Linux (x86_64, aarch64, armv7l)
- **編譯器**: C++17 相容 (MSVC 2019+, GCC 7+, Clang 5+)
- **CMake**: 3.10+
- **Python**: 3.x + `pip install websockets`
- **硬體**: Antilatency Alt Tracker + Extension Module (USB 連線)
- **瀏覽器**: Chrome / Edge / Firefox（需支援 ES Module + import maps）

---

## 編譯與執行

> **注意**：從 GitHub 下載原始碼後，必須先執行以下編譯步驟產生執行檔。

### Windows

```bash
# 編譯
cmake -B build -A x64
cmake --build build --config Release

# 執行 (推薦)
RunWithPipe.bat

# 或手動
cd build\Release
TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "..\..\web\pipe_server.py"
```

### Linux

```bash
cmake -B build
cmake --build build
cd build
./TrackingMinimalDemo "../scenes.json"
```

---

## 為什麼使用本地有線連接？

- **延遲最低**：USB 直連，可達 Antilatency 標榜的 **2ms 低延遲**
- **頻寬充足**：本地傳輸速度遠超網路
- **穩定性高**：無封包遺失、無網路抖動
- **資料完整**：不需要壓縮、不需要協議轉換

> 注意：若改為無線傳輸 (WiFi/4G)，會引入 10-100ms+ 的額外延遲，且受網路品質影響。本地有線方案是追蹤應用的最佳選擇。

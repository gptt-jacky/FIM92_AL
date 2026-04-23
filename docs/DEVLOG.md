# MANPADS 開發紀錄 (Development Log)

本文件為 MANPADS Antilatency Tracking System 的完整開發記錄，包含所有階段的技術細節與變更歷程。

---

## 系統架構

```
┌─────────────────────────────────────────────────────┐
│                    Main Application                 │
│           src/TrackingMinimalDemoCpp.cpp             │
│                      (788 行)                       │
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
│  Mode 2: Local File (軟體組本地, 500Hz 檔案)                          │
│  ┌──────────────┐                                                      │
│  │ C++ 標準模式 │─── tracking_data.json (atomic write: .tmp → rename) │
│  │ (500Hz 寫檔) │    軟體組 poll-read 此檔案                           │
│  └──────────────┘    啟動：faymantu/RunLocalFile.bat                   │
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
- `[A]`：切換 Tag A IO7 Output
- `[B]`：切換 Tag B IO7 Output
- `[O]`：切換所有 IO7 Output
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

- **WebSocket 綁定調整**：Server 綁定 IP 改為 `0.0.0.0`（pipe_server.py L132），允許區域網路內其他電腦連線。
- **前端參數支援**：`viewer_ws.html` 支援 URL 參數 `?host=IP`，例如 `http://localhost:8080?host=192.168.1.100`。
- **應用場景**：一台電腦負責跑 C++ 追蹤 (連接 Tracker)，另一台輕薄筆電或平板透過瀏覽器監看 3D 畫面。

### 6.3 場景管理工具 (UpdateScene)

- **新增 `scripts/UpdateScene.bat` 與 `scripts/update_scene.py`**（151 行）
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
   - 需要 C++ 視窗標題為 `MANPADS_Tracker_Window`（由 `.bat` 的 `title` 命令設定）
   - 在獨立 daemon 線程執行，避免阻塞 WebSocket 迴圈
5. **C++ 接收**：主迴圈的 `getKeyPress()` 讀取到按鍵，執行對應動作

### 7.2 支援的控制指令

| Web UI 按鈕 / Client 指令 | WebSocket 訊息 | C++ 動作 |
|---------------------------|---------------|----------|
| SCENE 1/2/3 | `{"type":"keypress","key":"1"}` | `switchScene()` 切換場景 |
| IO7 Toggle All | `{"type":"keypress","key":"O"}` | 切換所有 IO7 Output 狀態 |
| IO7 Tag A | `{"io7":"A1"}` | Tag A IO7 → High (toggle) |
| IO7 Tag B | `{"io7":"B1"}` | Tag B IO7 → High (toggle) |

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

### 9.3 scripts/RunWithPipe.bat 流程

```batch
title MANPADS_Tracker_Window          # 設定視窗標題（PowerShell SendKeys 需要）
chcp 65001                          # UTF-8 編碼
cd /d "%~dp0..\build\Release"      # 切換到 build 目錄
copy /Y "%~dp0..\scenes.json"      # 複製最新 scenes.json
start "" "http://localhost:8080"    # 開啟瀏覽器
TrackingMinimalDemo.exe --json "..\..\scenes.json" | python "%~dp0..\web\pipe_server.py"
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
| `[S1]` | 場景 1 | 目前使用 FV_10bars 場景 |
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
    "sceneName": "FV_10bars",
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
| `1` | FV_10bars | 費曼圖 10 燈柱場地 (HorizontalGrid) |

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
      ├── [鍵盤輸入] (L407-470)
      │   ├── Q → 退出
      │   ├── L → 列出場景
      │   ├── A → 切換 Tag A IO7 Output
      │   ├── B → 切換 Tag B IO7 Output
      │   ├── O → 切換所有 IO7 Output
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

**scripts/update_scene.py：**

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
| C++ 原始碼 | 1 | 788 行 | 32 KB |
| Python 腳本 | 4 | ~500 行 | 20 KB |
| HTML/Web | 1 | 755 行 | 34 KB |
| Batch 腳本 | 8 | ~80 行 | 3 KB |
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
scripts\RunWithPipe.bat

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

## Phase 10：多組 HW Extension + 軟體組資料介面 (2026-02-25)

**目標**：支援多組 HW Extension Module（每個 Tracker 各一組 IO），並提供軟體組精簡 WebSocket JSON 介面。

### 10.1 多組 HW Extension 支援

**問題**：原始架構只支援一組 HW Extension Module，但實際硬體有多組（A/B/C 各一組），每組 IO 模組需對應各自的 Tracker。

**新增結構體**：

```cpp
// Per-HW-Extension instance (L44-51)
struct HWExtInstance {
    Antilatency::DeviceNetwork::NodeHandle node;
    Antilatency::HardwareExtensionInterface::ICotask cotask;
    std::string type;
    std::vector<Antilatency::HardwareExtensionInterface::IInputPin> inputPins;
    Antilatency::HardwareExtensionInterface::IOutputPin outputPinIO7;
    bool io7State = false;
};
```

**配對機制**：透過 Antilatency Type 屬性匹配 Tracker 與 HW Extension

```cpp
// 主迴圈中建立 type -> HWExtInstance 映射 (L594-599)
std::map<std::string, HWExtInstance*> hwByType;
for (auto& hw : hwExtensions) {
    if (hw.cotask != nullptr && !hw.cotask.isTaskFinished() && !hw.type.empty()) {
        hwByType[hw.type] = &hw;
    }
}
```

**Tag 映射**：

```cpp
// Type = Tag directly (A/B/C/D set in AntilatencyService)
static std::string typeToTag(const std::string& type) {
    if (type == "A" || type == "B" || type == "C" || type == "D") return type;
    return "";
}
```

| Tag | 裝置 | Type 屬性 |
|-----|------|-----------|
| A | 刺針 | "A" |
| B | 頭盔 | "B" |
| C | 望遠鏡 | "C" |
| D | 對講機 | "D" |

**IO 8-bit 字串格式**：`IO1, IO2, IOA3, IOA4, IO5, IO6, IO7(輸出), IO8`

- 前 6 位：輸入腳位
- 第 7 位：IO7 輸出狀態
- 第 8 位：IO8 輸入
- 無對應 IO 模組時回傳 `"00000000"`

**JSON 向下相容**：

- 新增 per-tracker `"tag"` 和 `"io"` 欄位
- 保留全域 `"io":{...}` 欄位（第一組 HW Extension 的資料）
- 現有 viewer_ws.html 不受影響

### 10.2 軟體組資料介面

**架構**：

```
C++ --json stdout → pipe → data_server.py → WebSocket → 軟體組程式
                           (regex transform)   (0.0.0.0:8765)
```

**`web/data_server.py`** — 精簡版 WebSocket 轉發器：

- 從 stdin 讀取 C++ 完整 JSON
- 用 pre-compiled regex 提取欄位（不用 json.loads/json.dumps）
- 轉換為軟體組格式：`{"trackers":[{"tag":"A","px":...,"io":"00000000"}]}`
- WebSocket 廣播，支援可配置 Host/Port
- 無 HTTP server（軟體組不需要網頁）

**軟體組收到的 JSON**：

```json
{"trackers":[{"tag":"A","px":1.256012,"py":1.680032,"pz":0.000145,"rx":-0.710743,"ry":0.008621,"rz":-0.014023,"rw":0.703312,"io":"00000000"}]}
```

### 10.3 Console Monitor (`web/monitor.py`)

原地刷新的 console 監控工具，取代原本 `\r` 單行覆寫：

- 每個 Tracker 分行顯示 Tag、Position、Rotation、IO
- IO 每個 bit 有腳位名稱標示，有訊號的用綠色高亮
- 即時 FPS 顯示
- 用 ANSI escape codes 實現畫面清屏重繪

### 10.4 WebSocket Client (`web/ws_client.py`)

連線驗證工具：

- 連線到 data_server.py 的 WebSocket
- 顯示原始 JSON（軟體組實際收到的格式）
- 即時顯示接收速率 (msg/sec)
- 啟動時互動式輸入 Server Host/Port

### 10.5 Pipe 效能優化

**問題**：C++ 以 500Hz 輸出，但 Python 端只收到 ~64 msg/sec。

**根因分析（三層 buffering）**：

| 層級 | 問題 | 解法 |
|------|------|------|
| C stdio | Windows pipe 模式下 stdout 預設 4KB full buffering | `setvbuf(stdout, NULL, _IONBF, 0)` |
| C++ stream | `std::cout` 預設不即時 flush | `std::cout.setf(std::ios::unitbuf)` |
| Python stdin | `for line in sys.stdin` 使用 read-ahead buffering | `os.read(fd, 65536)` OS 層級 unbuffered read |

**Windows asyncio.sleep 陷阱**：Windows 預設計時器解析度 15.625ms，`asyncio.sleep(0.001)` 實際等待 ~15.6ms（=64Hz）。改用 `asyncio.Event` 信號機制。

**優化結果**：

| 版本 | RX 速率 |
|------|---------|
| 原始（`for line in sys.stdin`） | ~64 msg/sec |
| + `os.read()` + `asyncio.Event` | ~128 msg/sec |
| + C++ `setvbuf` unbuffered | ~128 msg/sec |

128 msg/sec 的剩餘瓶頸為 Windows kernel pipe buffer，無法從 user-space 消除。

### 10.6 網路設定

- Server 預設綁定 `0.0.0.0`（接受 LAN 連線）
- BAT 啟動時互動式詢問 Host/Port
- 已驗證跨機器 WiFi 連線可用
- SOFTWARE_GUIDE.md 包含防火牆設定指令

### 10.7 新增 / 修改的檔案

| 檔案 | 動作 | 說明 |
|------|------|------|
| `src/TrackingMinimalDemoCpp.cpp` | 修改 | 多組 HWExtInstance、typeToTag()、per-tracker IO、setvbuf |
| `web/data_server.py` | 新建 | 軟體組 WebSocket 轉發器 |
| `web/monitor.py` | 新建 | 原地刷新 console 監控器 |
| `web/ws_client.py` | 新建 | WebSocket 連線驗證工具 |
| `web/pipe_server.py` | 修改 | os.read() unbuffered stdin |
| `scripts/RunDataServer.bat` | 新建 | 軟體組啟動器 |
| `scripts/RunMonitor.bat` | 新建 | Console 監控器啟動器 |
| `scripts/RunWSClient.bat` | 新建 | WebSocket client 啟動器 |
| `docs/SOFTWARE_GUIDE.md` | 新建 | 軟體組使用指南 |
| `docs/DEV_DISCUSSION.md` | 新建 | 開發討論紀錄 |

---

## Phase 11：IO7 Per-device 控制 (2026-02-26)

**目標**：支援透過鍵盤或 WebSocket 指令，獨立控制各裝置（Tag A / Tag B）的 IO7 輸出。

### 11.1 C++ 端 — Per-device IO7 Toggle

原本只有 `O` 鍵統一切換所有 IO7，現新增 `A`/`B` 鍵分別控制：

```cpp
// TrackingMinimalDemoCpp.cpp — 'A' 鍵 toggle Tag A IO7
} else if (key == 'a' || key == 'A') {
    for (auto& hw : hwExtensions) {
        if (hw.type == "A" && hw.cotask != nullptr && !hw.cotask.isTaskFinished()) {
            hw.io7State = !hw.io7State;
            hw.outputPinIO7.setState(hw.io7State
                ? PinState::High : PinState::Low);
            break;
        }
    }
}
```

**鍵盤操作更新：**

| 按鍵 | 功能 |
|------|------|
| `A` | 切換 Tag A（刺針）IO7 Output |
| `B` | 切換 Tag B（頭盔）IO7 Output |
| `O` | 切換所有 IO7 Output（保留向下相容） |

### 11.2 WebSocket IO7 控制協議

新增 `{"io7":"..."}` JSON 指令格式，供 Client 端控制特定裝置 IO7：

| 指令 | 說明 |
|------|------|
| `{"io7":"A1"}` / `{"io7":"A0"}` | Tag A IO7 → High / Low |
| `{"io7":"B1"}` / `{"io7":"B0"}` | Tag B IO7 → High / Low |

**實作方式：** Python server 收到指令後，提取 Tag 字母（`A` 或 `B`），透過 PowerShell `SendKeys` 發送對應按鍵到 C++ 視窗。

### 11.3 data_server.py — 雙向通訊

原本為 send-only WebSocket handler，現新增接收端處理：

```python
async for message in websocket:
    data = json.loads(message)
    io7_cmd = data.get("io7", "")
    if io7_cmd in ("A1", "A0", "B1", "B0"):
        send_key_to_tracker(io7_cmd[0].lower())
```

- 新增 `send_key_to_tracker()` 函式（與 pipe_server.py 相同機制）
- 新增 client message 日誌（含時間戳與來源 IP）
- 需 BAT 設定視窗標題為 `MANPADS_DataServer`

### 11.4 pipe_server.py — io7 協議擴充

在原有 keypress 協議之外，新增 io7 協議支援：

```python
io7_cmd = data.get("io7", "")
if io7_cmd in ("A1", "A0", "B1", "B0"):
    send_key_to_tracker(io7_cmd[0].lower())
```

### 11.5 ws_client.py — 鍵盤互動

WebSocket 連線驗證工具新增鍵盤互動功能：

- 獨立 `keyboard_reader` 線程（`msvcrt.kbhit()` + `msvcrt.getch()`）
- 按 `A` / `B` 鍵 toggle 對應裝置的 IO7
- 透過 `asyncio.run_coroutine_threadsafe()` 跨線程發送 WebSocket 訊息
- 底部狀態列顯示 IO7 狀態：`[A] IO7-A: ON  [B] IO7-B: OFF`

### 11.6 monitor.py — 提示文字更新

底部快捷鍵提示從 `[O] Toggle IO7` 更新為 `[A] IO7-A  [B] IO7-B  [O] IO7-All`。

### 11.7 修改的檔案

| 檔案 | 動作 | 說明 |
|------|------|------|
| `src/TrackingMinimalDemoCpp.cpp` | 修改 | 新增 A/B 鍵 per-device IO7 toggle |
| `web/data_server.py` | 修改 | 雙向通訊 + io7 指令 + send_key_to_tracker() |
| `web/pipe_server.py` | 修改 | 新增 io7 協議支援 |
| `web/ws_client.py` | 修改 | 鍵盤 A/B toggle + IO7 狀態顯示 |
| `web/monitor.py` | 修改 | 底部快捷鍵提示更新 |
| `docs/SOFTWARE_GUIDE.md` | 修改 | 新增 IO7 控制指令章節 |

---

## Phase 12：IO-only 架構 + Tag B IO8 輸出 (2026-03-03)

**目標**：為 Tag B（頭盔）新增 IO8 輸出控制（大震動），並確立 Tag B/D 為 IO-only 裝置（不需要 Alt Tracker 定位）。

### 12.1 各 Tag IO 定義

| Tag | 裝置 | 用途概述 |
|-----|------|----------|
| A（刺針） | IO1=IFF開關, IO2=鎖定鍵, IOA3=BCU, IOA4=保險, IO5=瞄準模組, IO6=板機, **IO7=後座力(輸出)**, IO8=後座力準備 |
| B（頭盔） | **IO7=小震動(輸出)**, **IO8=大震動(輸出)** |
| C（望遠鏡） | IO1=縮小鍵, IO2=放大鍵 |
| D（對講機） | IO1=通話鍵 |

### 12.2 IO-only 架構（重要硬體發現）

**問題**：Tag B 需要 IO7（小震動）+ IO8（大震動）兩個 Output pin。最初嘗試在 Tag B 裝置上同時執行 Alt Tracker cotask + HW Extension cotask（含 2 個 `createOutputPin`），結果 **Alt Tracker 完全無法啟動**（LED 不亮綠燈、收不到追蹤資料）。

**測試過程**：

| 嘗試 | 配置 | 結果 |
|------|------|------|
| 1 | 7 input + IO7 output + IO8 output + Alt Tracker | ❌ Alt 不啟動 |
| 2 | IO7 + IO8 output 加 try-catch fallback + Alt Tracker | ❌ 無 exception 但 Alt 仍不啟動 |
| 3 | 改用 IO6 + IO7 兩個 output + Alt Tracker | ❌ 同樣失敗 |
| 4 | 減少總 pin 數到 7 個（5 input + 2 output）+ Alt Tracker | ❌ 仍然失敗 |

**根因分析**：

在同一個實體 USB 裝置上，**Alt Tracker cotask** 會佔用大量硬體資源（IMU、LED 通訊等）。當 HW Extension cotask 同時呼叫 **2 次 `createOutputPin`**，總資源需求超過裝置可同時分配的上限，導致 Alt Tracker 無法啟動。

- 1 output + Alt Tracker → ✅ 正常
- 2 output + Alt Tracker → ❌ 衝突
- 2 output + 無 Alt Tracker → ✅ 正常

> 官方 Antilatency Demo 示範了 PWM + Output（2 個輸出型 pin），但該 Demo **沒有同時執行 Alt Tracker cotask**。
> 硬體本身支援 8 個 pin 全部設為 Output，但 **Alt Tracker 和 HW Extension 共用裝置時，只能有 1 個 Output pin**。

**解決方案**：

Tag B（頭盔）和 Tag D（對講機）實際上不需要 6DOF 定位，只需要 IO 控制。因此將這兩個裝置設為 **IO-only**，不啟動 Alt Tracker cotask：

```cpp
// 跳過 Type B 和 D 的 Alt Tracker 啟動
std::string nodeType = getNodeType(network, node);
if (nodeType == "B" || nodeType == "D") continue;
```

| Tag | Alt Tracker | HW Extension | Pin 配置 |
|-----|:-----------:|:------------:|----------|
| A（刺針） | ✅ | ✅ | 7 input + IO7 output |
| B（頭盔） | ❌ IO-only | ✅ | 6 input + IO7 output + IO8 output |
| C（望遠鏡） | ✅ | ✅ | 7 input + IO7 output |
| D（對講機） | ❌ IO-only | ✅ | 7 input + IO7 output |

### 12.3 C++ 端修改

**HWExtInstance 結構體新增 IO8 欄位：**

```cpp
struct HWExtInstance {
    // ... 原有欄位 ...
    Antilatency::HardwareExtensionInterface::IOutputPin outputPinIO8;  // Tag B only
    bool io8State = false;
    bool hasIO8Output = false;  // true only for Tag B
};
```

**Tag B Pin 配置（IO-only，無 Alt Tracker 衝突）：**

```cpp
if (hw.type == "B") {
    for (int i = 0; i < 6; i++) {  // IO1~IO6: 6 input
        hw.inputPins.push_back(cotask.createInputPin(inputPinDefs[i]));
    }
    hw.outputPinIO7 = cotask.createOutputPin(Pins::IO7, PinState::Low);  // 小震動
    hw.outputPinIO8 = cotask.createOutputPin(Pins::IO8, PinState::Low);  // 大震動
    hw.hasIO8Output = true;
}
```

**鍵盤操作更新：**

| 按鍵 | 功能 |
|------|------|
| `A` | 切換 Tag A（刺針）IO7 Output（後座力） |
| `B` | 切換 Tag B（頭盔）IO7 Output（小震動） |
| `C` | 切換 Tag B（頭盔）IO8 Output（大震動） |
| `O` | 切換所有 IO7 Output |

**JSON 輸出**：IO-only 裝置（B/D）加入 trackers 陣列，位置為 0，IO 正常輸出。

### 12.4 WebSocket IO8 控制協議

新增 `{"io8":"B1"}` / `{"io8":"B0"}` 指令：

| 指令 | 目標 | 說明 |
|------|------|------|
| `{"io8":"B1"}` | Tag B IO8 | 大震動 ON（需 IO7 同時 ON） |
| `{"io8":"B0"}` | Tag B IO8 | 大震動 OFF |

**震動邏輯**：
- IO7=ON, IO8=OFF → 小震動
- IO7=ON, IO8=ON → 大震動（兩者必須同時 ON）
- IO7=OFF, IO8=ON → 無效果

**Python Server**：data_server.py、pipe_server.py 均新增 io8 指令處理。

### 12.5 修改的檔案

| 檔案 | 動作 | 說明 |
|------|------|------|
| `src/TrackingMinimalDemoCpp.cpp` | 修改 | IO-only 架構、IO8 output、C 鍵、JSON 輸出 |
| `web/data_server.py` | 修改 | io8 控制指令處理 |
| `web/pipe_server.py` | 修改 | io8 控制指令處理 |
| `web/ws_client.py` | 修改 | C 鍵 toggle IO8、狀態顯示 |
| `faymantu/data_server.py` | 修改 | io8 控制指令處理 |
| `faymantu/ws_client.py` | 修改 | C 鍵 toggle IO8、狀態顯示 |
| `faymantu/COMM_SPEC.md` | 修改 | IO8 指令、IO 定義、IO-only 裝置說明 |
| `faymantu/SOFTWARE_GUIDE.md` | 修改 | IO8 控制、Tag B/C/D IO 定義 |
| `docs/DEVLOG.md` | 修改 | Phase 12 記錄 |
| `docs/DEV_DISCUSSION.md` | 修改 | 硬體發現紀錄 |

---

## Phase 13：IO 控制改用 Named Pipe 雙向通訊（待實作）(2026-03-11)

**目標**：消除 IO 控制對鍵盤視窗 focus 和英文輸入法的依賴。

### 13.1 現有問題

目前 data_server.py 收到軟體組 WebSocket IO 指令（如 `{"io7":"A1"}`）後，透過 **PowerShell `SendKeys`** 將按鍵發送到 C++ console 視窗。此機制有三個限制：

| 限制 | 原因 |
|------|------|
| C++ 視窗不能最小化 | `AppActivate` + `SendKeys` 需視窗可被激活 |
| 系統輸入法必須切英文 | `SendKeys` 送出的字元會被中文輸入法攔截，`_getch()` 收不到 |
| 延遲較高 | 每次指令需啟動 PowerShell subprocess |

### 13.2 計畫方案：Named Pipe 雙向通訊

```
軟體組 → WebSocket → data_server.py → Named Pipe → C++ 主迴圈 → outputPin.setState()
```

**C++ 端改動**：
- 主迴圈新增 named pipe listener（non-blocking），接收 IO 指令字串（如 `"A1"`, `"B0"`, `"CB1"`）
- 收到指令直接呼叫 `outputPinIO7.setState()` / `outputPinIO8.setState()`
- 保留鍵盤控制作為 fallback（調試用）

**Python 端改動**：
- `send_key_to_tracker()` 改為寫 named pipe
- 移除 PowerShell `SendKeys` 依賴

**預期效果**：
- 不依賴視窗 focus → 視窗可最小化甚至隱藏
- 不依賴輸入法 → 中英文皆可
- 延遲更低 → 省掉 PowerShell 啟動時間
- 架構更乾淨 → 直接 IPC，不經過鍵盤模擬

**狀態**：待實作

---

## 為什麼使用本地有線連接？

- **延遲最低**：USB 直連，可達 Antilatency 標榜的 **2ms 低延遲**
- **頻寬充足**：本地傳輸速度遠超網路
- **穩定性高**：無封包遺失、無網路抖動
- **資料完整**：不需要壓縮、不需要協議轉換

> 注意：若改為無線傳輸 (WiFi/4G)，會引入 10-100ms+ 的額外延遲，且受網路品質影響。本地有線方案是追蹤應用的最佳選擇。

---

## Phase 12: Named Pipe 雙向 IO 控制 (2026-03-12)

### 問題

data_server.py 收到軟體組 WebSocket IO 指令後，透過 PowerShell `SendKeys` 模擬鍵盤輸入轉發到 C++ console 視窗。此方案有三個限制：

1. C++ console 視窗不能最小化（SendKeys 需要視窗 focus）
2. 系統輸入法必須切英文（否則 `_getch()` 收不到正確字元）
3. 依賴 PowerShell 啟動，延遲較高

### 解法

C++ 在 `--json` 模式下新增 Named Pipe listener thread（`\\.\pipe\MANPADS_IO`），Python data_server.py 直接透過 Named Pipe 寫入 JSON 指令，C++ 收到後直接呼叫 `outputPin.setState()`。

### 改動檔案

| 檔案 | 改動 |
|------|------|
| `src/TrackingMinimalDemoCpp.cpp` | 新增 Named Pipe listener（僅 `--json` 模式），收到 `{"io7":"A1"}` / `{"io8":"B1"}` 直接控制 IO |
| `web/data_server.py` | `send_key_to_tracker()` → `send_io_command()`，改為寫 Named Pipe |
| `faymantu/data_server.py` | 同步更新 |

### 技術細節

- Pipe name: `\\.\pipe\MANPADS_IO`
- 指令格式：沿用 WebSocket JSON（`{"io7":"A1"}`），一行一筆
- C++ 端用 `std::mutex` 保護 command queue，主迴圈每輪消費
- C++ 非 `--json` 模式的鍵盤控制完全不受影響
- 軟體組 WebSocket 介面零變動（格式、指令完全相同）

### 實測踩坑紀錄

| 問題 | 根因 | 修法 |
|------|------|------|
| Python `open()` 開 pipe 報 `No such file or directory` | Python `open()` 對 Named Pipe 支援不穩定 | 改用 `ctypes.windll.kernel32.CreateFileW` Windows API |
| `CreateFileW` 成功但 `WriteFile` 報 error 6 (INVALID_HANDLE) | 64-bit Windows 上 ctypes 預設把 handle 截斷為 32-bit int | 設定 `_kernel32.CreateFileW.restype = wintypes.HANDLE` |
| Pipe 連線成功但 C++ 收不到指令（無 `[Pipe] IO7` 輸出） | `json.dumps()` 產生 `"io7": "B1"`（冒號後有空格），C++ parser 搜尋 `"io7":"` 不匹配 | Python 改用 f-string 直接組 compact JSON |
| Release 資料夾的 exe 是舊版 | `MANPADS_Release_V1.1/build/Release/` 的 exe 未更新 | 手動複製新編譯的 exe |

### 效果

- C++ 視窗可最小化在背景執行
- 不再依賴輸入法狀態
- 省掉 PowerShell 啟動開銷，延遲更低
- Release 版本更新至 V1.1

---

## Phase 12：自製 ALPCB + 無線 IO 驗證 (2026-03-17)

**目標**：驗證自製 PCB（ALPCB）取代官方 Socket 用於 IO-only 裝置（Tag B / Tag D），並確認無線模式可行性。

### 背景

Tag B（主射手頭盔震動器）和 Tag D（對講機）為純 IO 裝置，不需要 Alt Tracker 定位功能。基於成本與客製化考量，改用自製 PCB（代號 **ALPCB**）取代官方 Socket。

ALPCB 基於 Antilatency **Socket Reference Design**（nRF52840 模組），具備：
- USB Type-C 連接
- Antilatency Hardware Extension Interface（IO 腳位控制）
- 2.4GHz 無線功能（Antilatency Radio Protocol）

裝置在 AntilatencyService 中的名稱：`ACHA0Socket_ReferenceDesign_RUA`

### 問題：BAT 啟動後 C++ 偵測不到 ALPCB

**現象**：
- AntilatencyService Device Network 中能看到 ALPCB 的 node
- 但 C++ 程式（`TrackingMinimalDemo.exe`）執行後沒有印出 `Extension Module connected`
- 官方 URS（Socket）正常偵測

**調查過程**：

1. 排除 USB device filter 問題 — 分析 SDK source `AllUsbDevices` 常數（VID=0x3237, PID mask=0xF000），確認涵蓋 ALPCB 的 USB 識別碼
2. 排除 HW Extension Interface 不支援 — ALPCB 基於 Reference Design，韌體原生支援
3. 排除 AntilatencyService 佔用 — 關閉 AS 後問題依舊

**根因**：

ALPCB 在 AntilatencyService 中的 **Type 屬性設定錯誤**。C++ 程式依賴 Type 屬性（必須為 `"B"` 或 `"D"`）來配對裝置與 IO pin 配置。Type 不匹配時，裝置雖然被 Device Network 發現，但不會被正確初始化。

**修法**：在 AntilatencyService → Device Network 中，將 ALPCB 的 Type 分別設為 `B` 和 `D`（大寫單字元）。

### 無線模式驗證

確認 ALPCB 支援無線模式（先前在 Unity 專案中已長期使用）：

```
有線模式:
  PC ──USB── ALPCB [B]
  PC ──USB── ALPCB [D]

無線模式:
  PC ──USB── URS (Access Point 模式)
                  ╲ 2.4GHz Antilatency Radio Protocol
              ALPCB [B] (Client 模式, 外部供電)
              ALPCB [D] (Client 模式, 外部供電)
```

- URS 作為 Access Point 透過 USB 連接 PC
- ALPCB 作為 Client 透過 2.4GHz 無線連接 URS
- SDK Device Network 對無線裝置的呈現方式與 USB 裝置一致（透明）
- **HW Extension Interface IO（輸入 + 輸出）在無線模式下正常運作**
- C++ 程式碼**無需任何修改**即可支援無線模式

### 結論

| 項目 | 結果 |
|------|------|
| ALPCB 有線 IO | ✅ 正常（Type 設對即可） |
| ALPCB 無線 IO | ✅ 正常（URS Access Point + ALPCB Client） |
| C++ 程式碼改動 | 無需改動 |
| 根因 | AntilatencyService 中 Type 屬性設定錯誤 |

---

## Phase 14：專案入口文件治理 (2026-04-21)

**目標**：補齊缺少的專案級入口文件，讓人類與代理在開始工作前有一致的上下文入口與讀取順序。

### 14.1 新增文件

| 檔案 | 用途 |
|------|------|
| `docs/MEMORY.md` | 記錄穩定事實、硬體限制、跨模組相依與維護記憶 |
| `docs/AGENTS.md` | 定義代理/自動化修改 repo 時的工作規則與升級條件 |
| `docs/INDEX.md` | 依任務類型索引應讀文件，避免一開始展開整個 repo |

### 14.2 調整原則

- 入口文件只保留高信號、低耦合內容
- `README.md` 保持對外與整體導覽角色
- `docs/MEMORY.md` 保存穩定事實，不記錄一次性討論
- `docs/DEVLOG.md` 持續保存歷史決策與踩坑紀錄
- `docs/INDEX.md` 明確規定先讀入口文件，再按任務深入模組

### 14.3 效果

- 降低不同代理或不同回合讀取上下文時的偏差
- 降低一開始過度展開所有文件的成本
- 讓後續文件維護責任更清楚

---

## Phase 15：web/ 與 faymantu/ 整合 + Release V1.2 (2026-04-23)

**目標**：消除 `web/` 與 `faymantu/` 之間的重複 Python 檔案，統一以 `faymantu/` 作為唯一來源；同步更新 Release 封裝至 V1.2。

### 15.1 問題背景

`web/` 與 `faymantu/` 重複維護三支 Python 工具：

| 重複檔案 | web/ | faymantu/ | MANPADS_Release/ |
|---------|------|-----------|-----------------|
| `data_server.py` | ✅ | ✅ | ✅ |
| `monitor.py` | ✅ | ✅ | ✅ |
| `ws_client.py` | ✅ | ✅ | ✅ |

每次修改都需手動同步三處，容易造成版本不一致（`git status` 中大量 `M` 都是同步遺漏的結果）。

### 15.2 決策

以 `faymantu/` 為唯一來源，理由：
- `faymantu/` 是對外交付的資料夾，本來就是「最終版本」
- `web/` 只有 `pipe_server.py` 和 `viewer_ws.html` 是真正 web viewer 專用，其餘不該在此重複

### 15.3 變更清單

| 操作 | 對象 |
|------|------|
| 刪除 | `web/data_server.py` |
| 刪除 | `web/monitor.py` |
| 刪除 | `web/ws_client.py` |
| 修改 | `scripts/RunMonitor.bat`：`web\monitor.py` → `faymantu\monitor.py` |
| 重命名 | `MANPADS_Release_V1.1/` → `MANPADS_Release_V1.2/` |
| 同步 | `faymantu/` 全部檔案 → `MANPADS_Release_V1.2/faymantu/` |

### 15.4 整合後目錄職責

```
web/                            ← 3D viewer 專用
  pipe_server.py                ← stdin → WebSocket + HTTP 伺服器
  viewer_ws.html                ← Three.js 3D 視覺化頁面

faymantu/                       ← 共用工具 + 費曼圖交付（唯一來源）
  data_server.py                ← WebSocket 精簡 JSON 伺服器
  monitor.py                    ← Console IO 監控
  ws_client.py                  ← WebSocket 連線驗證
  SOFTWARE_GUIDE.md             ← 軟體組操作手冊
  RunDataServer/Monitor/WSClient.bat
```

### 15.5 data_server.py rx_count 計數說明

在 `stdin_reader()` 中，`transform_fast(line)` 與 `rx_count += 1` 被放在內層 while 迴圈**外面**，每次 `os.read()` chunk 只執行一次（取 chunk 中最後一行做處理）：

```python
while b"\n" in remainder:      # 內層 loop：掃完 chunk 所有行
    line_bytes, remainder = ...
    line = ...
    if not line.startswith("{"):
        continue
# 只處理最後一行，rx_count 計的是 chunk 數
transformed = transform_fast(line)
if transformed:
    rx_count += 1
```

**行為**：`rx_fps` 顯示的是 `os.read()` chunk 數，通常高於實際 JSON 行數。這是**預期行為**——偏高的數字對監控有用，不需修改。

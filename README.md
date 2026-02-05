# FIM92 Antilatency Tracking System

Antilatency Alt Tracking + Hardware Extension Interface (HW IO) C++ 應用程式，支援**多場景切換**、**多 Alt Tracker 同時追蹤**與 **Type 裝置類型識別**。

---

## 目錄

1. [專案概述](#專案概述)
2. [系統架構](#系統架構)
3. [開發歷程](#開發歷程)
4. [檔案結構](#檔案結構)
5. [環境需求](#環境需求)
6. [編譯與執行](#編譯與執行)
7. [場景設定 (scenes.json)](#場景設定)
8. [多場景切換設計](#多場景切換設計)
9. [多 Alt Tracker 設計](#多-alt-tracker-設計)
10. [Type 裝置類型識別](#type-裝置類型識別)
11. [IO 腳位說明](#io-腳位說明)
12. [輸出格式](#輸出格式)
13. [Web 3D 視覺化介面](#web-3d-視覺化介面)
14. [架構圖](#架構圖)
15. [API 參考](#api-參考)

---

## 快速開始 (給使用者)

如果您不想編譯程式碼，請直接至 [Releases](https://github.com/gptt-jacky/FIM92_AL/releases) 頁面下載最新版本的壓縮檔，解壓縮後執行 `RunWithWebViewer.bat` 即可。

## 專案概述

本專案基於 Antilatency SDK 4.5.0，實現：
- **6-DOF 動作追蹤**：透過 Antilatency Alt Tracker 取得位置 (X, Y, Z) 與旋轉 (Quaternion)
- **8 通道數位 IO 輸入**：透過 Hardware Extension Interface 讀取 8 個腳位狀態
- **多場景 (Environment) 切換**：透過 JSON 設定檔定義多個場景，執行時用鍵盤數字鍵即時切換
- **多 Alt Tracker 同時運行**：自動偵測所有已連接的 Alt 設備，同時啟動追蹤
- **Type 裝置類型識別**：透過 `nodeGetStringProperty(node, "Type")` 讀取裝置 Type，區分刺針/望遠鏡/IO 擴充板等

---

## 系統架構

```
┌─────────────────────────────────────────────────────┐
│                    Main Application                 │
├──────────┬──────────┬──────────┬────────────────────┤
│ Scene    │ Multi-   │ HW IO    │ Keyboard           │
│ Manager  │ Tracker  │ Manager  │ Input              │
│          │ Manager  │          │                    │
├──────────┴──────────┴──────────┴────────────────────┤
│              Antilatency SDK 4.5.0                  │
├──────────┬──────────┬──────────┬────────────────────┤
│ Device   │ Alt      │ Env      │ HW Extension       │
│ Network  │ Tracking │ Selector │ Interface          │
└──────────┴──────────┴──────────┴────────────────────┘
           ↕ USB / Device Network
┌──────────────────────────────────────────────────────┐
│          Antilatency Hardware Devices                │
│  ┌───────────────┐ ┌───────────────┐ ┌─────────────┐ │
│  │ Alt #1        │ │ Alt #2        │ │ Extension   │ │
│  │ Type:Stinger  │ │ Type:Binocul. │ │ Type:ExBoard│ │
│  └───────────────┘ └───────────────┘ └─────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 開發歷程

### Phase 1：基礎追蹤 Demo (初始版本)

**目標**：實現單一 Alt Tracker + 單一 HW IO 的最小可行程式

- 載入 4 個 SDK 動態函式庫 (DeviceNetwork, AltTracking, EnvironmentSelector, HardwareExtensionInterface)
- 透過命令列參數傳入 Environment Data 和 Placement Data
- `getIdleTrackingNode()` 取得第一個閒置的 Tracking Node
- `getIdleExtensionNode()` 取得第一個閒置的 Extension Node
- 主迴圈 60 FPS 輪詢裝置狀態，輸出 P(x,y,z) R(qx,qy,qz,qw) S:stage IO:pinStates
- 單一場景、單一 Tracker 的設計

**限制**：
- 只能透過命令列傳入一組 Environment，無法在執行中切換場景
- 只追蹤第一個找到的閒置 Alt Node，無法同時使用多個 Tracker

### Phase 2：多場景 + 多 Alt 重構

**目標**：支援多場景切換與多 Alt 同時追蹤

**變更重點**：

#### 2.1 資料結構設計

```cpp
// 場景設定結構
struct SceneConfig {
    std::string name;            // 場景名稱
    std::string environmentData; // Antilatency 環境序列化資料
    std::string placementData;   // 座標系轉換資料
};

// 追蹤器實例結構 (支援多個 Alt)
struct TrackerInstance {
    Antilatency::DeviceNetwork::NodeHandle node; // 裝置節點
    Antilatency::Alt::Tracking::ITrackingCotask cotask; // 追蹤任務
    int id;          // 追蹤器編號
    std::string type; // 裝置類型 (從 AntilatencyService 設定)
};
```

#### 2.2 JSON 設定檔 (`scenes.json`)

- 新增簡易 JSON 解析器 (`extractJsonValue`, `parseSceneConfigs`)
- 不依賴第三方 JSON 函式庫，減少外部依賴
- 支援 `scenes` 陣列，每個元素包含 `name`, `environmentData`, `placementData`

#### 2.3 多場景切換

- `switchScene()` 函式：停止所有追蹤 Cotask → 建立新 Environment → 重新啟動追蹤
- 鍵盤快捷鍵 `[1]`-`[9]` 即時切換場景
- 切換時重置 `prevUpdateId` 觸發裝置重新掃描
- 向下相容：仍支援 `exe <envData> <placementData>` 單場景模式

#### 2.4 多 Alt Tracker

- `getIdleTrackingNode()` → `getAllIdleTrackingNodes()` — 回傳**所有**閒置節點
- 使用 `std::vector<TrackerInstance>` 管理多個追蹤器
- 自動偵測新連接的 Alt 設備，分配遞增編號
- 已斷線的 Tracker 自動從列表移除 (`isTaskFinished()` 檢查)

#### 2.5 鍵盤控制 (Windows)

- `getKeyPress()` 使用 `_kbhit()` / `_getch()` 非阻塞讀取
- `[1]`-`[9]`：切換場景
- `[L]`：列出所有場景
- `[Q]`：退出程式

#### 2.6 輸出格式更新

- 增加場景指示器 `[S1]`
- 每個 Tracker 以 `T1:`, `T2:` 前綴區分
- 行寬從 130 擴展到 160 以容納多 Tracker 資料

### Phase 3：Type 裝置類型識別

**目標**：透過 Antilatency 的 Type 屬性識別各個硬體裝置的用途（例如區分「刺針飛彈」與「望遠鏡」）

*(詳見下方 [Type 裝置類型識別](#type-裝置類型識別) 章節)*

### Phase 4：Web 視覺化效能優化

**目標**：解決 3D 視覺化介面的卡頓問題，實現流暢的 60fps 動態追蹤顯示

**問題分析**：
原本的實作有兩個效能瓶頸：

1. **檔案讀寫競爭**：C++ 直接寫入 `tracking_data.json`，Python server 同時讀取時可能讀到不完整的 JSON，導致解析失敗
2. **插值方式不當**：使用 frame-based lerp (`position.lerp(target, 0.25)`)，在高 FPS 下物體會快速接近目標後「停住」等待下一筆資料，造成「衝→停→衝→停」的卡頓感

**解決方案**：

#### 4.1 C++ 端：原子檔案寫入

```cpp
// 之前：直接寫入 (寫入中被讀取 = JSON 損壞)
std::ofstream jsonFile("tracking_data.json");
jsonFile << js.str();

// 之後：先寫臨時檔，再原子重命名
std::ofstream jsonFile("tracking_data.json.tmp");
jsonFile << js.str();
jsonFile.close();
std::filesystem::rename("tracking_data.json.tmp", "tracking_data.json");
```

#### 4.2 Web 端：時間基準插值 (Time-based Interpolation)

```javascript
// 之前：frame-based lerp (高 FPS 下會卡頓)
obj.group.position.lerp(obj.targetPos, 0.25);

// 之後：time-based interpolation (任何 FPS 都平滑)
const elapsed = now - obj.lastUpdateTime;
const t = Math.min(elapsed / DATA_INTERVAL, 1.2);
obj.group.position.lerpVectors(obj.prevPos, obj.targetPos, t);
```

**時間基準插值原理**：
- 收到新資料時，記錄「前一個位置」和「時間戳」
- 每個 render frame 計算經過時間佔預期間隔的比例 (0~1)
- 物體從前一個位置**勻速滑動**到目標位置
- 不管渲染 60fps 或 200fps，動作都很平滑

#### 4.3 提升資料輪詢頻率

| 項目 | 之前 | 之後 |
|------|------|------|
| C++ 寫入頻率 | 60 Hz (16ms) | 60 Hz (16ms) |
| Web 輪詢頻率 | 30 Hz (33ms) | **60 Hz (16ms)** |
| 插值間隔 | 33ms | **16ms** |

**成效**：3D 物體移動從「跳躍式」變成「持續滑動」，延遲感大幅降低

**背景**：
Antilatency 裝置可以在 AntilatencyService 軟體中設定 Type 屬性，寫入硬體記憶體。程式端可透過 `network.nodeGetStringProperty(node, "Type")` 讀取。

#### 3.1 Type 設定流程 (硬體端)

1. 執行 **AntilatencyService**
2. 進入 **Device Network** 分頁
3. 找到目標裝置節點
4. 設定 **Type** 名稱（例如 `Stinger`、`Binoculars`、`ExBoard`）
5. Type 寫入硬體記憶體，換電腦也會保留

#### 3.2 程式端實作

```cpp
// 讀取裝置 Type (返回空字串表示未設定)
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

#### 3.3 變更內容

- `TrackerInstance` 新增 `type` 欄位，儲存追蹤器的 Type
- 新增 `getNodeType()` 輔助函式，安全地讀取 Type（未設定時回傳空字串）
- Alt Tracker 連接時讀取並記錄 Type，連接訊息顯示 `Alt Tracker #1 [Stinger] connected!`
- HW Extension 連接時讀取並記錄 Type，連接訊息顯示 `Extension Module [ExBoard] connected!`
- 即時輸出加入 Type 標示：`T1[Stinger]:P(...)` 和 `IO[ExBoard]:10101010`

#### 3.4 應用範例

在 AntilatencyService 中設定好 Type 後，程式會自動識別：

| 裝置 | Type | 程式中的顯示 |
|------|------|-------------|
| 刺針飛彈上的 Alt Tracker | `Stinger` | `T1[Stinger]:P(...) R(...) S:2` |
| 望遠鏡上的 Alt Tracker | `Binoculars` | `T2[Binoculars]:P(...) R(...) S:2` |
| IO 擴充板 | `ExBoard` | `IO[ExBoard]:10101010` |
| 未設定 Type 的裝置 | (空) | `T3:P(...) R(...) S:2` |

---

## 檔案結構

```
FIM92_C++/
├── TrackingMinimalDemoCpp.cpp    # 主程式 (多場景 + 多Alt + Type識別)
├── CMakeLists.txt                # CMake 編譯設定
├── scenes.json                   # 場景設定檔 (JSON)
├── RunTracking.bat               # Windows 快速執行腳本 (多場景模式)
├── RunTracking_legacy.bat        # Windows 快速執行腳本 (舊模式，單場景)
├── RunWithWebViewer.bat          # 同時啟動 Tracker + Web 3D 視覺化介面
├── README.md                     # 本文件
├── web/                          # Web 3D 視覺化介面
│   ├── viewer.html               # 3D 追蹤視覺化頁面 (Three.js)
│   └── server.py                 # 本地 HTTP 伺服器
├── AntilatencySdk/               # Antilatency SDK 4.5.0
│   ├── Api/                      # C++ Header Files (30 個)
│   │   ├── Antilatency.Alt.Tracking.h
│   │   ├── Antilatency.Alt.Environment.Selector.h
│   │   ├── Antilatency.Alt.Environment.Pillars.h
│   │   ├── Antilatency.Alt.Environment.Rectangle.h
│   │   ├── Antilatency.Alt.Environment.HorizontalGrid.h
│   │   ├── Antilatency.Alt.Environment.Sides.h
│   │   ├── Antilatency.Alt.Environment.Arbitrary2D.h
│   │   ├── Antilatency.Alt.Environment.AdditionalMarkers.h
│   │   ├── Antilatency.DeviceNetwork.h
│   │   ├── Antilatency.HardwareExtensionInterface.h
│   │   ├── Antilatency.HardwareExtensionInterface.Interop.h
│   │   └── ... (其他)
│   └── Bin/                      # 預編譯二進位檔
│       ├── WindowsDesktop/x64/   # Windows 64-bit DLLs
│       ├── WindowsDesktop/x86/   # Windows 32-bit DLLs
│       └── Linux/                # Linux .so 檔案
└── build/                        # CMake 編譯輸出
```

---

## 環境需求

- **OS**: Windows 10/11 (64-bit) 或 Linux (x86_64, aarch64, armv7l)
- **編譯器**: C++17 相容 (MSVC 2019+, GCC 7+, Clang 5+)
- **CMake**: 3.10+
- **硬體**: Antilatency Alt Tracker + Extension Module (USB 連線)

---

## 編譯與執行

> **注意**：從 GitHub 下載原始碼後，必須先執行以下編譯步驟產生執行檔，`RunWithWebViewer.bat` 才能正常運作。

### Windows

```bash
# 建立 build 目錄並編譯
cmake -B build -A x64
cmake --build build --config Release

# 方法一：使用設定檔 (推薦)
cd build/Release
TrackingMinimalDemo.exe "../../scenes.json"

# 方法二：使用 RunTracking.bat
RunTracking.bat

# 方法三：舊模式 (單一場景)
TrackingMinimalDemo.exe "<environmentData>" "<placementData>"
```

### Linux

```bash
cmake -B build
cmake --build build
cd build
./TrackingMinimalDemo "../scenes.json"
```

---

## 場景設定

`scenes.json` 格式：

```json
{
    "scenes": [
        {
            "name": "場景名稱",
            "environmentData": "AntilatencyAltEnvironmentPillars~...",
            "placementData": "AAAAAA..."
        },
        {
            "name": "另一個場景",
            "environmentData": "AntilatencyAltEnvironmentRectangle~...",
            "placementData": "AAAAAA..."
        }
    ]
}
```

### 欄位說明

| 欄位 | 必填 | 說明 |
|------|------|------|
| `name` | 否 | 場景顯示名稱，未填則自動編號 |
| `environmentData` | 是 | Antilatency 環境序列化字串，從 AntilatencyService 匯出 |
| `placementData` | 否 | Placement 轉換資料，未填則使用預設值 (原點) |

### 如何取得 Environment Data

1. 開啟 **AntilatencyService** 軟體
2. 設定好場景的標記點 (Pillars / Rectangle / Grid 等)
3. 點擊 **Export Environment** → 複製序列化字串
4. 貼到 `scenes.json` 的 `environmentData` 欄位

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

### 如何更改場地 / 切換場景

**步驟一：準備各場地的 Environment Data**

每個物理場地都有不同的標記配置，需要各自匯出：

1. 在場地 A 架設好 Antilatency 標記 (Pillars/Rectangle 等)
2. 開啟 **AntilatencyService** → 校正場地 A → **Export Environment** → 複製字串
3. 到場地 B 重複上述步驟，取得場地 B 的 Environment Data
4. 以此類推

**步驟二：寫入 `scenes.json`**

```json
{
    "scenes": [
        {
            "name": "TrainingRoom_A",
            "environmentData": "AntilatencyAltEnvironmentPillars~<場地A的資料>",
            "placementData": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        },
        {
            "name": "TrainingRoom_B",
            "environmentData": "AntilatencyAltEnvironmentPillars~<場地B的資料>",
            "placementData": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        },
        {
            "name": "Outdoor_Field",
            "environmentData": "AntilatencyAltEnvironmentRectangle~<戶外場地資料>",
            "placementData": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        }
    ]
}
```

**步驟三：執行時即時切換**

```
程式啟動後：
  按 [1] → 切到 TrainingRoom_A
  按 [2] → 切到 TrainingRoom_B
  按 [3] → 切到 Outdoor_Field
  按 [L] → 列出所有場景，標示目前使用中的場景
```

### 運作流程

```
使用者按下 [2]
    │
    ▼
switchScene(1, ...)
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

### 注意事項

- 切換場景時會**暫時中斷所有追蹤**，因為不同場景的標記配置不同
- 切換後 Alt Tracker 需要重新定位，Stability 會從 InertialDataInitialization 重新開始
- 若新場景的 Environment Data 無效，會保持在當前場景
- 不同場地可以混用不同環境類型（場地 A 用 Pillars、場地 B 用 Rectangle）

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

1. **偵測**：每次 `network.getUpdateId()` 變化時，掃描所有支援的節點
2. **清理**：移除已斷線 (`isTaskFinished()`) 的 Tracker 實例
3. **過濾**：跳過已在使用中的節點 (避免重複啟動)
4. **啟動**：為每個新的閒置節點建立 `TrackerInstance`，分配遞增 ID + 讀取 Type
5. **輸出**：以 `T1[Type]:`, `T2[Type]:` 前綴區分各 Tracker 的資料

### 範例輸出 (2 個 Alt Tracker + IO，含 Type)

```
[S1] T1[Stinger]:P( 1.2345, 0.5678, 2.1111) R( 0.0000, 0.0000, 0.7071, 0.7071) S:2  T2[Binoculars]:P(-0.3210, 0.8888, 1.5000) R( 0.1000, 0.2000, 0.3000, 0.9000) S:2  IO[ExBoard]:10101010
```

---

## Type 裝置類型識別

### 什麼是 Type？

Antilatency 每個硬體節點都可以設定一個自訂的 Type 屬性。程式端透過 `network.nodeGetStringProperty(node, "Type")` 即可讀取，用來區分不同用途的裝置。

### 設定方法

1. 開啟 **AntilatencyService**
2. 進入 **Device Network** 分頁
3. 找到目標裝置節點
4. 設定 **Type** 名稱，例如：
   - `Stinger` — 刺針飛彈上的 Alt Tracker
   - `Binoculars` — 望遠鏡上的 Alt Tracker
   - `ExBoard` — IO 擴充板

### 程式行為

| 事件 | 有 Type | 無 Type |
|------|---------|---------|
| Alt Tracker 連接 | `Alt Tracker #1 [Stinger] connected!` | `Alt Tracker #1 connected!` |
| Extension 連接 | `Extension Module [ExBoard] connected!` | `Extension Module connected!` |
| 即時輸出 | `T1[Stinger]:P(...)` | `T1:P(...)` |
| IO 輸出 | `IO[ExBoard]:10101010` | `IO:10101010` |

### 用途

- **區分多個追蹤器**：同時接 2 個以上 Alt 時，靠 Type 知道哪個是刺針、哪個是望遠鏡
- **識別 IO 擴充板**：當有多個擴充板時，靠 Type 區分用途
- **記錄與除錯**：輸出日誌中可明確看到是哪個裝置的資料

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
| IO7  | **Output** | 按鍵 `[O]` 切換 | 輸出高電位 | 輸出低電位 (預設) |

- 啟動時 IO7 預設為 **Low (OFF)**
- 按 `[O]` 鍵可即時切換 ON/OFF
- 可用於控制繼電器、LED、蜂鳴器等外部裝置
- 程式碼中使用 `hwCotask.createOutputPin()` 和 `outputPin.setState()` 控制

---

## 輸出格式

```
[S<場景編號>] T<ID>[<Type>]:P(x,y,z) R(qx,qy,qz,qw) S:<穩定度>  IO[<Type>]:<7位元> IO7out:<ON/OFF>
```

### 實際測試範例

以下為未裝立柱時的實測輸出（IO7 改為 Output 前）：

```
[S1] T1:P(-0.0000, 1.6800, 0.0000) R(-0.6286, 0.0094,-0.3238, 0.7071) S:1  IO[AC50]:00010000
```

IO7 改為 Output 後的輸出格式：

```
[S1] T1:P(-0.0000, 1.6800, 0.0000) R(-0.6286, 0.0094,-0.3238, 0.7071) S:1  IO[AC50]:0001000 IO7out:OFF
```

#### 逐欄解析

| 欄位 | 值 | 意義 |
|------|-----|------|
| `[S1]` | 場景 1 | 目前使用 AL_TEST_2M 場景 |
| `T1:` | Tracker #1 | Alt Tracker（未設定 Type，若有設定會顯示如 `T1[Stinger]:`） |
| `P(-0.0000, 1.6800, 0.0000)` | X=0m, Y=1.68m, Z=0m | 位置座標（Y 軸 = 高度），單位：公尺 |
| `R(-0.6286, 0.0094, -0.3238, 0.7071)` | 四元數 (qx, qy, qz, qw) | 裝置目前的朝向/旋轉 |
| `S:1` | 3DOF | 只有旋轉追蹤，沒有位置追蹤（因為沒有立柱） |
| `IO[AC50]` | Type = AC50 | IO 擴充板，Type 已從硬體讀取成功 |
| `00010000` | IOA4 = 1，其餘 = 0 | 第 4 腳 (IOA4) 被觸發，其餘放開 |

#### IO 腳位對照 (`00010000`)

```
IO1=0  IO2=0  IOA3=0  IOA4=1  IO5=0  IO6=0  IO7=0  IO8=0
                        ↑
                     此腳位被觸發 (Active Low)
```

### 追蹤穩定度 (Stability Stage) 詳細說明

| 階段 | S 值 | 名稱 | 說明 | 資料可用性 |
|------|------|------|------|-----------|
| 初始化 | `S:0` | InertialDataInitialization | IMU 正在初始化 | 位置/旋轉均不可用 |
| 3DOF | `S:1` | Tracking3Dof | 僅 IMU 旋轉追蹤 | **旋轉可用，位置不可用** |
| **6DOF** | **`S:2`** | **Tracking6Dof** | **立柱光學定位 + IMU** | **位置 + 旋轉均可用** |
| 盲區 6DOF | `S:3` | TrackingBlind6Dof | 暫時遮擋，靠慣性預測 | 位置靠預測，短時間內可用 |

**重要**：`S:1`（3DOF）時 `P(x,y,z)` 位置資料不會真正移動，**必須架設立柱達到 `S:2`（6DOF）後，位置資料才準確可用**。

### 6DOF 資料說明

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

### 給網站使用的注意事項

| 項目 | 說明 |
|------|------|
| 資料完整性 | `P` + `R` + `S` 包含完整的空間定位資訊，足夠做定位應用 |
| 穩定度要求 | 必須達到 **S:2 (6DOF)** 才能取得準確的位置資料 |
| 更新頻率 | C++ 60 Hz 寫入 + Web 60 Hz 輪詢 + 時間插值平滑化 |
| 座標系 | 右手座標系，Y 軸朝上 |
| 目前格式 | Console 文字輸出，後續可改為 JSON over WebSocket 供網站即時讀取 |

### 欄位快速參考

| 欄位 | 說明 | 範例 |
|------|------|------|
| `[S1]` | 當前場景編號 | S1 = 第一個場景 |
| `T1[Stinger]:` | 追蹤器 ID + Type | T1 = 第一個 Alt，Type = Stinger |
| `T2:` | 追蹤器 ID (未設定 Type) | T2 = 第二個 Alt，無 Type |
| `P(x,y,z)` | 位置 (公尺) | P(-0.0000, 1.6800, 0.0000) |
| `R(qx,qy,qz,qw)` | 旋轉 (四元數) | R(-0.6286, 0.0094, -0.3238, 0.7071) |
| `S:N` | 穩定度階段 | S:2 = 6DOF (位置+旋轉可用) |
| `IO[AC50]:XXXXXXX` | 7 個 Input 腳位 + Type | IO[AC50]:0001000 |
| `IO7out:OFF` | IO7 Output 狀態 | OFF=High(關), ON=Low(開) |

---

## Web 3D 視覺化介面

本專案包含一個即時 3D 視覺化網頁，可在瀏覽器中顯示追蹤資料。

### 功能

- **3D 物件顯示**：使用 Three.js 即時渲染追蹤器的位置與旋轉
- **時間插值平滑化**：採用 time-based interpolation，確保任何螢幕更新率下都能流暢顯示
- **Position 顯示**：X, Y, Z 座標 (公尺)
- **Rotation 顯示**：Quaternion (x, y, z, w) + 自動換算 Euler 角度 (Pitch, Yaw, Roll)
- **Stability 狀態**：S:0~S:3 進度條與文字顯示
- **IO 腳位面板**：8 個腳位即時狀態 (7 input + IO7 output)
- **多 Tracker 支援**：每個 Tracker 以不同顏色顯示
- **OrbitControls**：可用滑鼠旋轉/縮放/平移 3D 視角

### 使用方式

**方法一：一鍵啟動 (推薦)**

```bat
RunWithWebViewer.bat
```

同時啟動 Tracker 程式 + Web Server，自動開啟瀏覽器。

**方法二：手動啟動**

1. 先啟動 Tracker 程式（會產生 `tracking_data.json`）：
   ```bat
   RunTracking.bat
   ```

2. 另開 terminal 啟動 Web Server：
   ```bat
   cd web
   python server.py
   ```

3. 開啟瀏覽器到 `http://localhost:8080`

### 資料流

```
TrackingMinimalDemo.exe
    │
    ├── Console 輸出 (即時文字)
    └── tracking_data.json (每 16ms 原子寫入)
            │
            └── web/server.py (HTTP Server, port 8080)
                    │
                    └── web/viewer.html (Three.js 3D 渲染)
                            │
                            └── 瀏覽器 fetch 每 16ms 讀取 + 時間插值
```

### JSON 資料格式 (tracking_data.json)

```json
{
    "scene": 1,
    "sceneName": "AL_TEST_2M",
    "trackers": [
        {
            "id": 1,
            "type": "Tag",
            "px": 0.1234, "py": 1.6800, "pz": -0.0456,
            "rx": -0.6286, "ry": 0.0094, "rz": -0.3238, "rw": 0.7071,
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

### 環境需求

- Python 3.x (用於本地 HTTP Server)
- 現代瀏覽器 (Chrome, Edge, Firefox — 需支援 ES Module + import maps)

---

## 架構圖

### 執行流程

```
START
  │
  ├── 解析命令列參數
  │   ├── 1 個參數 → 讀取 scenes.json
  │   └── 2 個參數 → 舊模式 (單場景)
  │
  ├── 載入 4 個 SDK 函式庫
  │   ├── AntilatencyDeviceNetwork
  │   ├── AntilatencyAltTracking
  │   ├── AntilatencyAltEnvironmentSelector
  │   └── AntilatencyHardwareExtensionInterface
  │
  ├── 建立 Device Network (USB Filter)
  │
  ├── 初始化第一個場景的 Environment + Placement
  │
  ├── 建立 Cotask Constructors
  │
  └── MAIN LOOP (60 FPS)
      │
      ├── [鍵盤輸入]
      │   ├── 1-9 → switchScene()
      │   ├── L   → 列出場景
      │   └── Q   → 退出
      │
      ├── [裝置更新]
      │   ├── 清理已斷線 Tracker
      │   ├── getAllIdleTrackingNodes() → 啟動新 Tracker
      │   │   └── getNodeType() → 讀取 Type (Stinger/Binoculars/...)
      │   └── getIdleExtensionNode() → 啟動 HW IO
      │       └── getNodeType() → 讀取 Type (ExBoard/...)
      │
      └── [資料輸出]
          ├── [S<n>] 場景指示器
          ├── T<id>[<type>]:P() R() S: 各 Tracker 資料 (含 Type)
          └── IO[<type>]:<pins> 腳位狀態 (含 Type)
```

### 場景切換時序

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

---

## API 參考

### 主要函式

| 函式 | 說明 |
|------|------|
| `parseSceneConfigs(filename)` | 解析 JSON 設定檔，回傳 `vector<SceneConfig>` |
| `getAllIdleTrackingNodes(network, constructor)` | 取得所有閒置的 Alt Tracking 節點 |
| `getIdleExtensionNode(network, constructor)` | 取得第一個閒置的 HW Extension 節點 |
| `getNodeType(network, node)` | 讀取裝置 Type 屬性 (從 AntilatencyService 設定) |
| `switchScene(index, scenes, ...)` | 切換到指定場景 |
| `getKeyPress()` | 非阻塞鍵盤輸入 (Windows only) |

### 核心結構

| 結構 | 欄位 | 說明 |
|------|------|------|
| `SceneConfig` | name, environmentData, placementData | 場景設定 |
| `TrackerInstance` | node, cotask, id, type | 追蹤器實例 (含 Type 類型) |
| `Alt::Tracking::State` | pose, stability, localAngularVelocity | 追蹤狀態 |
| `Math::floatP3Q` | position (float3), rotation (floatQ) | 位姿資料 |

---

## 執行時鍵盤操作

| 按鍵 | 功能 |
|------|------|
| `1`-`9` | 切換到對應編號的場景 |
| `L` | 列出所有可用場景及當前場景 |
| `O` | 切換 IO7 Output (ON/OFF) |
| `Q` | 退出程式 |

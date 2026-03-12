# MANPADS 軟體組資料介面 — 開發討論紀錄

## 需求背景

軟體組需要從 Antilatency 追蹤系統取得即時資料（位置 / 旋轉 / IO 狀態），用於自行開發的應用程式。他們不需要 3D 網頁視覺化（viewer），只需要一個乾淨的 WebSocket JSON 資料流。

## 討論過程

### 1. 輸出格式精簡化

原始 C++ JSON 輸出包含 `scene`、`sceneName`、`id`、`type`、`number`、`stability` 等完整欄位。軟體組只需要最精簡的資訊。

**最終格式：**
```json
{"trackers":[{"tag":"A","px":...,"py":...,"pz":...,"rx":...,"ry":...,"rz":...,"rw":...,"io":"00000000"}]}
```

### 2. Tag 映射確認

經討論確認四組裝置的代號，Type 屬性直接設為 Tag 字母：

| Tag | 裝置 | Antilatency Type 屬性 |
|-----|------|----------------------|
| A | 刺針 | "A" |
| B | 頭盔 | "B" |
| C | 望遠鏡 | "C" |
| D | 對講機 | "D" |

Type 直接作為 Tag，寫在 C++ `typeToTag()` 函式和 Python `VALID_TAGS` / `TAG_INFO` 中。

### 3. IO per-tracker 架構決策

**問題：** 原始架構只支援一組 HW Extension Module（IO 模組），但實際硬體有多組（A/B/C/D 各一組），每組 IO 模組對應各自的 Tracker。

**方案選擇：**
- ~~方案 A: `nodeGetParent()` parent node 匹配~~ — 過於依賴硬體拓撲
- **方案 B: Type 屬性匹配** ✓ — 透過 Antilatency 服務設定的 Type 字串配對

**實作：**
- C++ 側：`std::vector<HWExtInstance>` 取代單一 `hwCotask`
- 每個 tracker 透過 `type` 欄位找到對應的 `HWExtInstance`
- `std::map<std::string, HWExtInstance*> hwByType` 用於快速查找

### 4. IO 8-bit 字串格式

**位置順序：** IO1, IO2, IOA3, IOA4, IO5, IO6, IO7(輸出), IO8

- 前 6 位為輸入腳位讀取值
- 第 7 位為 IO7 輸出狀態
- 第 8 位為 IO8 輸入讀取值
- `0` = Low（無訊號），`1` = High（有訊號）
- 無對應 IO 模組時回傳 `"00000000"`

### 5. 向下相容設計

C++ JSON 輸出同時保留：
- **新欄位：** 每個 tracker 物件內的 `"io":"00000000"` 和 `"tag":"A"`
- **舊欄位：** 全域的 `"io":{"connected":true,"inputs":[...],"io7out":false}`

確保現有的 3D 網頁 viewer（`viewer_ws.html`）不受影響。

### 6. 架構分離

| 角色 | 檔案 | 用途 |
|------|------|------|
| C++ 主程式 | `src/TrackingMinimalDemoCpp.cpp` | 追蹤 + IO 讀取，輸出完整 JSON |
| 軟體組 Server | `web/data_server.py` | stdin → 精簡 JSON → WebSocket（無 HTTP） |
| 網頁版 Server | `web/pipe_server.py` | stdin → 完整 JSON → WebSocket + HTTP |
| Console Monitor | `web/monitor.py` | stdin → 原地刷新 console 顯示 |
| WebSocket Client | `web/ws_client.py` | 連線驗證工具，顯示原始 JSON |
| 軟體組 BAT | `faymantu/RunDataServer.bat` | 啟動 C++ → data_server.py pipe |
| 軟體組本地 BAT | `faymantu/RunLocalFile.bat` | 啟動 C++（無 pipe），寫入 tracking_data.json |
| 網頁版 BAT | `scripts/RunWithPipe.bat` | 啟動 C++ → pipe_server.py pipe |
| 監控 BAT | `scripts/RunMonitor.bat` | 啟動 C++ → monitor.py pipe |
| 驗證 BAT | `faymantu/RunWSClient.bat` | WebSocket client 連線測試 |

### 7. Pipe 效能優化

**問題：** C++ 以 500Hz 輸出 JSON，但 Python 端只收到 ~64 msg/sec。

**根因分析（三層 buffering）：**

| 層級 | 問題 | 解法 |
|------|------|------|
| C stdio | Windows pipe 模式下 stdout 預設 4KB full buffering | `setvbuf(stdout, NULL, _IONBF, 0)` |
| C++ stream | `std::cout` 預設不即時 flush | `std::cout.setf(std::ios::unitbuf)` |
| Python stdin | `for line in sys.stdin` 和 `readline()` 使用 read-ahead buffering | `os.read(fd, 65536)` OS 層級 unbuffered read |

**優化結果：**

| 版本 | 速度 |
|------|------|
| 原始（`for line in sys.stdin`） | ~64 msg/sec |
| + `os.read()` unbuffered | ~128 msg/sec |
| + C++ `setvbuf` unbuffered | ~128 msg/sec |

**128 msg/sec 的剩餘瓶頸：** Windows pipe 本身的 kernel-level buffering，無法從 user-space 完全消除。128 msg/sec 足以滿足軟體組的即時需求。

**Windows asyncio.sleep 陷阱：** Windows 預設計時器解析度為 15.625ms，`asyncio.sleep(0.001)` 實際等待 ~15.6ms（=64Hz）。改用 `asyncio.Event` 信號機制避免此問題。

### 8. 網路設定

- Server 預設綁定 `0.0.0.0`（接受任何 IP 連線），支援跨機器 LAN 使用
- BAT 啟動時互動式詢問 Host / Port，直接 Enter 用預設值
- Client 端啟動時輸入 Server IP 即可連線

### 9. IO7 Per-device 控制

**需求：** 軟體組需要能透過 WebSocket 指令獨立控制各裝置（Tag A / Tag B）的 IO7 輸出，而非只能統一開關。

**C++ 端實作：**
- 原有 `O` 鍵統一切換所有 HW Extension 的 IO7
- 新增 `A`/`B` 鍵，透過 `hw.type` 匹配找到對應的 HWExtInstance，獨立 toggle 其 `io7State`
- 每個 HWExtInstance 有自己的 `io7State` 布林值，互不影響

**WebSocket 協議設計：**
- 新增 `{"io7":"A1"}` / `{"io7":"B0"}` 格式（與原有 `{"type":"keypress","key":"O"}` 並存）
- 格式：`io7` 值 = Tag 字母 + 目標狀態（`1`=High, `0`=Low）
- Python server 收到後提取 Tag 字母，轉為小寫按鍵送給 C++

**實作方式選擇：**
- ~~方案 A: Python 直接透過 serial/USB 控制 IO~~ — 不可行，IO 由 C++ SDK 管理
- **方案 B: PowerShell SendKeys 模擬鍵盤** ✓ — 與現有場景切換機制一致，實作成本最低

**雙向通訊擴展：**
- `data_server.py` 從 send-only 升級為雙向（接收 client message + 日誌記錄）
- `pipe_server.py` 新增 io7 協議（與現有 keypress 協議並行）
- `ws_client.py` 新增鍵盤互動（A/B 鍵 toggle）作為測試工具

**注意事項：**
- IO7 在 C++ 端為 toggle 機制（每次按鍵翻轉一次），指令中的 `1`/`0` 僅作為語義區分
- 建議 client 端搭配回傳 `io` 欄位確認實際狀態
- 僅 Tag A（刺針）和 Tag B（頭盔）支援 IO7 控制

### 10. IO-only 架構 + IO8 Output (Tag B 大震動)

**需求：** Tag B（頭盔）需要兩個 Output pin — IO7（小震動）和 IO8（大震動），可同時啟動達成大震動效果。

**硬體衝突發現：**

在同一裝置上同時跑 Alt Tracker cotask + HW Extension cotask（含 2 個 `createOutputPin`），Alt Tracker 完全無法啟動。經過 4 輪測試：

| 嘗試 | 結果 |
|------|------|
| 8 pin (7in + IO7 out + IO8 out) + Alt Tracker | ❌ |
| IO8 output 加 try-catch + Alt Tracker | ❌（無 exception 但 Alt 不動） |
| 改用 IO6 + IO7 output + Alt Tracker | ❌ |
| 7 pin (5in + IO7 + IO8 out) + Alt Tracker | ❌ |

**結論：** Antilatency 裝置在 Alt Tracker cotask 運行時，HW Extension 只能有 **1 個 Output pin**。2 個 Output pin 的資源需求會與 Alt Tracker 衝突。官方 Demo 展示的 PWM + Output 組合也是在**不跑 Alt Tracker** 的情境下。

**解法：** Tag B（頭盔）和 Tag D（對講機）不需要 6DOF 定位，只需 IO。改為 **IO-only** 架構 — 不啟動 Alt Tracker cotask：

```cpp
if (nodeType == "B" || nodeType == "D") continue;  // 跳過 Alt Tracker
```

這樣 Tag B 就能安全使用 2 個 Output pin（IO7 + IO8），與 Alt Tracker 零衝突。

**WebSocket 新增指令：** `{"io8":"B1"}` / `{"io8":"B0"}`，Python server 與 C++ 均已支援。

**IO-only JSON 格式：** B/D 裝置在 trackers 陣列中，位置為 0 (`px=0, py=0, pz=0, rw=1`)，IO 正常輸出。

### 11. IO-only 裝置的 JSON 格式調整

由於 Tag B/D 不跑 Alt Tracker，JSON 輸出已簡化：

- 移除全域 `"io":{...}` 欄位（原本用於向下相容 viewer）
- 移除 `id`、`type`、`number`、`stability` 欄位
- WebSocket 格式統一為：`{"trackers":[{"tag":"A","px":...,"rw":...,"io":"..."}]}`
- IO-only 裝置範例：`{"tag":"B","px":0,"py":0,"pz":0,"rx":0,"ry":0,"rz":0,"rw":1,"io":"00000000"}`

### 12. IO7 語義變更 — 從「直接觸發」改為「保險授權」

**變更日期：** 2026-03-09

**原本邏輯：** 軟體端判定可射擊 → 送 `{"io7":"A1"}` → 直接觸發後座力

**新邏輯：**
- 軟體端判定可射擊 → 送 `{"io7":"A1"}` **開保險**（授權硬體端可觸發）
- 軟體端判定不可射擊 / 故障 → 送 `{"io7":"A0"}` **關保險**（禁止觸發）
- IO7=1 期間，後座力觸發權交由硬體端本地判定

**硬體端觸發三條件（全部成立才觸發）：**
1. IO7 = 1（軟體允許）
2. IO8 = 1（後座力機構已就位）
3. IO6 + IO2 同時持續按壓 ≥ 1 秒（板機 + 鎖定鍵）

**IO8 回報機制：**
- 觸發後 IO8 物理自動歸 0（機構動作）
- 機構復位完成後 IO8 自動回 1（約 10 秒）
- 軟體端只需讀取 WebSocket JSON 中 `io[7]` 即可得知狀態

**設計原則：**
- 所有場景邏輯與故障判定由軟體端處理
- 硬體端不需區分故障類型，只看 IO7 這一個開關
- 軟體端任何時刻可立即送 `{"io7":"A0"}`，不需等硬體回報
- 頭盔震動器（Tag B）維持軟體直接控制，不受此變更影響

### 13. IO 控制改用 Named Pipe（取代 PowerShell SendKeys）

**變更日期：** 2026-03-12

**問題：** data_server.py 收到 WebSocket IO 指令後，透過 PowerShell `SendKeys` 模擬鍵盤輸入送給 C++。限制：C++ 視窗不能最小化、輸入法必須切英文、PowerShell 啟動延遲。

**解法：** C++ 在 `--json` 模式下開 Named Pipe（`\\.\pipe\MANPADS_IO`），Python 直接寫入 JSON 指令。

**C++ 端：**
- 新增 `namedPipeListener()` 函式，獨立 thread 持續監聽
- `PipeIOCommand` 結構 + `g_pipeCommands` queue（mutex 保護）
- 主迴圈每輪消費 queue，直接呼叫 `setState()`
- 非 `--json` 模式完全不受影響（鍵盤控制保留）

**Python 端：**
- `send_key_to_tracker()` 整個移除（含 `import subprocess`）
- 新增 `send_io_command(cmd_json)` — 開啟 Named Pipe 寫入 JSON + `\n`
- 指令格式不變：`{"io7":"A1"}`、`{"io8":"B1"}`
- 不再需要 toggle 比對邏輯（C++ 端為 set-to-state）

**影響範圍：** 僅 data_server.py（RunDataServer.bat 路徑）。pipe_server.py、viewer、monitor、ws_client 全部不動。軟體組 WebSocket 介面零變動。

## 日期

- 初始討論：2026-02-25
- 實作完成：2026-02-25
- 效能優化：2026-02-25
- IO7 per-device 控制：2026-02-26
- IO-only 架構 + IO8 output：2026-03-03
- IO7 語義變更（保險授權）：2026-03-09
- IO 控制改用 Named Pipe：2026-03-12

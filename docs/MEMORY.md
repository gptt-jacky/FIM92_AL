# Project Memory

Last updated: 2026-04-30

## Tag A / Tag G IO Mode (2026-05-06)

Tag A（刺針）與 Tag G（測試）現在共用相同的 C++ HW setup 路徑，8-bit io 字串格式相同：
`IO1, IO2, IOA3(0/1/2), IOA4(0-7), IO5, IO6, IO7(out), IO8`

**Tag A IOA4 decode（天線/BCU/保險）**：`0=無, 1=BCU, 2=保險, 3=天線, 4=BCU+保險, 5=BCU+天線, 6=保險+天線, 7=BCU+保險+天線`
**Tag G IOA4 decode（A/B/C 按鈕）**：`0=none, 1=A, 2=B, 3=A+B, 4=C, 5=A+C, 6=B+C, 7=A+B+C`
值 3/4 對調是因為 Tag A 電阻網路設計不同（天線電壓低於 BCU+保險組合）。

IOA3 levels（Tag A / G 共用）：0=off, 1=中震動 55% duty, 2=強震動 100% duty
WebSocket 控制指令：`{"ioa3":"A0"}` / `{"ioa3":"A1"}` / `{"ioa3":"A2"}`

Tag B（頭盔震動器）：停用，保留 code 空殼，io 固定 "00000000"。

## IOA3 Analog Decode Rule (2026-04-30)

- When IOA3 is used as the A/B/C button ladder, decode by floor threshold, not midpoint.
- Examples: 0.62V = A/BCU; 1.30V = A+B.
- Ranges: `<0.54V` none, `0.54-0.88V` A/BCU, `0.88-1.25V` B/保險, `1.25-1.56V` A+B, `1.56-1.83V` C/天線, `1.83-2.00V` A+C, `2.00-2.19V` B+C, `>=2.19V` A+B+C.

## Purpose

`docs/MEMORY.md` 記錄本專案的長期穩定事實、已確認的技術限制、跨檔案相依與維護時要先記住的背景。
這份文件不記錄一次性對話，也不放暫時性的待辦。

## Canonical Context

本專案的主要上下文來源依序為：

1. `README.md`：對外與整體操作說明
2. `docs/MEMORY.md`：穩定事實、限制、維護記憶
3. `docs/DEVLOG.md`：歷史決策、演進脈絡、已踩過的坑
4. `docs/CLAUDE.md`：協作與修改規範
5. `docs/AGENTS.md`：代理/自動化工作時的執行規則
6. `docs/INDEX.md`：工作流程索引，決定何時讀哪份文件

若上述文件彼此衝突，優先順序如下：

1. `README.md`
2. `docs/MEMORY.md`
3. `docs/DEVLOG.md`
4. `docs/CLAUDE.md`
5. `docs/AGENTS.md`
6. `docs/INDEX.md`

## Stable Architecture Facts

- 核心主程式是 `src/TrackingMinimalDemoCpp.cpp`。
- 主要執行環境是 Windows。
- 建構系統為 CMake，C++ 標準為 C++17。
- Python 工具分為兩類：`faymantu/`（共用工具，唯一來源）與 `web/`（3D viewer 專用）。
  - `faymantu/`：`data_server.py`、`monitor.py`、`ws_client.py`、BAT 腳本、`SOFTWARE_GUIDE.md`
  - `web/`：僅保留 `pipe_server.py` 和 `viewer_ws.html`
- Web 視覺化入口是 `web/viewer_ws.html`。
- 場景設定來源是根目錄 `scenes.json`。
- 第三方 SDK 位於 `AntilatencySdk/`，視為唯讀。
- `build/` 與 `MANPADS_Release_V1.2/` 為輸出/封裝產物區，非主要開發來源。

## Data Flow That Must Not Be Broken Lightly

- C++ 主程式會產出 JSON。
- `web/pipe_server.py`、`faymantu/data_server.py`、`faymantu/monitor.py` 與前端/軟體組工具都依賴該輸出。
- 任何 JSON 欄位名稱、結構、語義變更，都必須連帶檢查：
  - `web/pipe_server.py`
  - `web/viewer_ws.html`
  - `faymantu/data_server.py`
  - `faymantu/monitor.py`
  - `faymantu/ws_client.py`
  - `docs/Websocket_刺針感測器通訊系統.md`
  - `faymantu/SOFTWARE_GUIDE.md`

## Hardware Constraints Already Confirmed

- Tag B、Tag D 為 IO-only 裝置，不跑 Alt Tracker。
- Tag E、Tag F 為 Alt-only 裝置，不掛 HW Extension。
- Alt Tracker + HW Extension 同裝置：IO7+IO8 雙 output 已實測可行（Tag G 驗證）。
- `createPwmPin` 確定會讓同裝置的 Alt Tracker cotask 立即 finish（沉默失敗）。根因待確認（可能是 nRF52840 PWM timer 與 Alt tracking DMA 衝突）。
- `createAnalogPin` 是否衝突：**未確認**（Diag 3 待測試）。
- Tag B 需要 IO7 與 IO8 雙輸出，因此採 IO-only 架構。
- Type 屬性必須在 AntilatencyService 正確設定，否則配對流程會失敗。
- `Antilatency Support/` 保存提交給官方的 C++ SDK 4.5.0 support ticket，聚焦 Alt Tracking cotask + HW Extension cotask + 2 output pins 衝突問題；因後續實測 IO7+IO8 正常，暫不送出。

## IOA3/IOA4 實作狀態（2026-05-06 已完成）

- IOA3 → PWM output（震動器）：Tag A 和 Tag G 均採用。duty 0%=off, 55%=中震動, 100%=強震動
- IOA4 → analog input（電阻分壓梯 decode）：Tag A 和 Tag G 均採用，但 decode 表不同（見上方）
- 8-bit io 字串格式：Tag A/G 均為 `IO1, IO2, IOA3(0/1/2), IOA4(0-7), IO5, IO6, IO7*, IO8`
- `analog.<tag>.ioa4` 欄位保留原始 SDK 電壓讀值（0–3.3V），不歸一化
- `decodeAnalogABCLevel` 門檻值（floor threshold）：0.54/0.88/1.25/1.56/1.83/2.00/2.19V

## Operational Expectations

- 預設先讀入口文件，再決定是否深入特定模組。
- 修改前先說明需求理解、修改範圍、風險與驗證方式。
- 未經明確同意，不直接 commit、不 push。
- 完成修改後先驗證，再更新 `README.md`、`docs/DEVLOG.md`、`docs/MEMORY.md`。

## High-Risk Areas

- `src/TrackingMinimalDemoCpp.cpp`：核心追蹤、IO、JSON 輸出集中點。
- `faymantu/data_server.py`：與外部客戶端介面最直接。
- `web/viewer_ws.html`：Web 3D 顯示與控制協議入口。
- `scripts/*.bat`：實際啟動流程，容易因路徑/編碼/參數改動而失效。

## What To Update When

- 若系統穩定事實、硬體限制、上下文優先序改變，更新 `docs/MEMORY.md`。
- 若使用方式、目錄結構、對外說明改變，更新 `README.md`。
- 若是歷史決策、重要變更或踩坑紀錄，更新 `docs/DEVLOG.md`。
- 若新增工作流程、模板或技能入口，更新 `docs/INDEX.md`。

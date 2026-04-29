# Project Memory

Last updated: 2026-04-23

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
  - `docs/COMM_SPEC.md`
  - `docs/COMM_SPEC_V10.md`
  - `faymantu/SOFTWARE_GUIDE.md`

## Hardware Constraints Already Confirmed

- Tag B、Tag D 為 IO-only 裝置，不跑 Alt Tracker。
- Tag E、Tag F 為 Alt-only 裝置，不掛 HW Extension。
- Alt Tracker 與 HW Extension 共用同一實體裝置時，最多只能安全使用 1 個 output pin。
- Tag B 需要 IO7 與 IO8 雙輸出，因此採 IO-only 架構。
- Type 屬性必須在 AntilatencyService 正確設定，否則配對流程會失敗。
- `Antilatency Support/` 保存提交給官方的 C++ SDK 4.5.0 support ticket、Service Desk 表單欄位輔助文件與最小復現，聚焦同一 physical Socket 上 Alt Tracking cotask + HW Extension cotask + 2 output pins 的衝突，並詢問未來 3 output pins + Alt Tracking 的官方上限與建議架構。

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

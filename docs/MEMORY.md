# Project Memory

Last updated: 2026-04-30

## Current Tag G Diagnostic State (2026-04-30)

- Tag G outputs: IOA3 PWM and IO7 digital.
- Tag G IOA3 levels: 0=off, 1=small PWM at 55% duty, 2=full output at 100% duty.
- Tag G analog input: IOA4, exposed in JSON as `analog.G.ioa4` and `analog.G.ioa4v`.
- Tag G digital inputs: IO1, IO2, IO5, IO6, IO8.
- Tag G `trackers[].io` diagnostic layout: `IO1, IO2, IOA3(0/1/2), IOA4(0-7), IO5, IO6, IO7(out), IO8`.
- Tag G IOA4 uses one character for the A/B/C analog decode: `0=none, 1=A, 2=B, 3=A+B, 4=C, 5=A+C, 6=B+C, 7=A+B+C`.
- `scripts/RunMonitor.bat` can exit immediately if any old code path reads Tag G as a seven-input module. The fix is to use the guarded Tag G IO mapping everywhere before JSON is emitted.

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
  - `docs/COMM_SPEC.md`
  - `docs/COMM_SPEC_V10.md`
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

## IOA3/IOA4 類比重設計（2026-04-30 硬體會議決策，尚未完整實作）

**原始方向：IOA3 → analog input（電阻分壓梯，讀三顆按鈕）**

- 三顆按鈕（BCU、保險、天線）各自並聯接地電阻，IOA3 讀組合電壓
- SDK：`createAnalogPin(IOA3, refreshMs)`, `getValue()` 回傳 0.0–1.0（= 0–3.3V）
- 8 種狀態（7 電壓段 + 0V），誤差容許 ±6%，取中點門檻解碼
- IO 字串從 8-bit 擴展到 10-bit：BCU/保險/天線各佔一位

**原始方向：IOA4 → PWM output（輸出至 Pico2W 控制震動馬達）**

- duty=0%=off, duty=55%≈1.8V=小震動, duty=91%≈3.0V=大震動
- SDK：`createPwmPin(IOA4, freqHz)`, `setDuty(float)`
- **已知衝突**：`createPwmPin` 與 Alt Tracker 同裝置衝突 → 解決方案待定

**10-bit IO 字串格式（Tag G/A）**：
```
位置  0   1   2    3    4    5   6    7     8     9
腳位 IO1 IO2 BCU 保險 天線 IO5 IO6 IO7* IO8* IOA4*
```
IOA4* 儲存 `'0'`/`'1'`/`'2'`（非 H/L）

**實作狀態**：
- Struct 欄位、decodeIOA3()、10-bit path、monitor.py → 已完成但未套用到正式 Tag A
- Tag G 最新測試配置（2026-04-30）：IOA3 + IO7 為 output；IOA4 為 analog input 並在 monitor 顯示即時電壓；IO1/IO2/IO5/IO6/IO8 為 input
- 鍵盤：`[G]` 控制 Tag G IOA3 output，`[H]` 控制 Tag G IO7 output
- IOA4 PWM 方案暫停，先改為 analog input 診斷是否與 Alt Tracker 共存

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

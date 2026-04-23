# Project Index

## Purpose

`docs/INDEX.md` 是本專案的工作流程索引。
先讀入口文件，再依任務類型讀必要文件；不要一開始展開所有文件。

## Default Entry Sequence

所有任務預設先讀：

1. `README.md`
2. `docs/MEMORY.md`
3. `docs/DEVLOG.md`
4. `docs/CLAUDE.md`
5. `docs/AGENTS.md`
6. `docs/INDEX.md`

## Task Routing

### 1. 需求理解 / 專案導覽

讀：

- `README.md`
- `docs/MEMORY.md`
- `docs/DEVLOG.md`
- `docs/architecture.mmd`

### 2. C++ 追蹤核心 / IO / 場景切換

讀：

- `src/TrackingMinimalDemoCpp.cpp`
- `README.md`
- `docs/MEMORY.md`
- `docs/DEVLOG.md`
- `docs/COMM_SPEC.md`
- `docs/COMM_SPEC_V10.md`

重點：

- JSON 輸出格式
- Type/Tag/Number 配對
- IO-only / Alt-only 限制

### 3. WebSocket / Python Server / Monitor

讀：

- `web/pipe_server.py`
- `web/data_server.py`
- `web/monitor.py`
- `web/ws_client.py`
- `README.md`
- `docs/MEMORY.md`
- `docs/DEVLOG.md`

若是軟體組交付介面，再加讀：

- `faymantu/data_server.py`
- `faymantu/monitor.py`
- `faymantu/ws_client.py`
- `faymantu/SOFTWARE_GUIDE.md`

### 4. Web 3D Viewer / 前端控制

讀：

- `web/viewer_ws.html`
- `web/pipe_server.py`
- `README.md`
- `docs/DEVLOG.md`
- `docs/architecture.mmd`

### 5. 場景資料 / 環境設定

讀：

- `scenes.json`
- `scripts/update_scene.py`
- `scripts/UpdateScene.bat`
- `README.md`
- `docs/DEVLOG.md`

### 6. 啟動流程 / 執行腳本

讀：

- `scripts/RunWithPipe.bat`
- `scripts/RunTracking.bat`
- `scripts/RunMonitor.bat`
- `faymantu/RunDataServer.bat`
- `faymantu/RunMonitor.bat`
- `faymantu/RunWSClient.bat`
- `README.md`

### 7. 通訊規格 / 外部整合

讀：

- `docs/COMM_SPEC.md`
- `docs/COMM_SPEC_V10.md`
- `faymantu/SOFTWARE_GUIDE.md`
- `README.md`
- `docs/MEMORY.md`

## Skills / Templates Policy

目前 repo 內沒有獨立的專案級 `skills/` 或 `templates/` 目錄。

因此規則是：

- 先依本索引讀取對應文件與程式檔。
- 若未來新增專案內 skill 或 template：
  - 只在任務明確涉及該流程時再讀
  - 不要在任務開始時一次展開全部 skill/template
  - 新增後需同步更新 `docs/INDEX.md`

## Output Checklist

開始實作前應先提供：

- 需求理解
- 修改範圍
- 風險
- 驗證方式

完成後應提供：

- 驗證結果
- 已更新的文件
- `git diff` 摘要
- commit message 草案

## Maintenance Rule

當以下任一項變更時，必須回來更新 `docs/INDEX.md`：

- 新增工作流程
- 新增對外協議文件
- 新增 project-local skill/template
- 主要入口文件或讀取順序調整

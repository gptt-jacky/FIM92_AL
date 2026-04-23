# Agents Guide

## Purpose

`docs/AGENTS.md` 定義人類或代理在本 repo 內工作的最低共同規則。
它不是功能文件，而是執行文件。

## Read Order

開始任何工作前，至少先讀：

1. `README.md`
2. `docs/MEMORY.md`
3. `docs/DEVLOG.md`
4. `docs/CLAUDE.md`
5. `docs/AGENTS.md`
6. `docs/INDEX.md`

若任務有明確模組範圍，再補讀對應檔案，不要一開始就展開整個 repo。

## Scope Rules

- 主要開發來源：
  - `src/`
  - `web/`
  - `faymantu/`
  - `scripts/`
  - `docs/`
  - `README.md`
  - `scenes.json`
- 非主要開發來源：
  - `AntilatencySdk/`：第三方 SDK，預設不改
  - `build/`：編譯輸出，不直接編修
  - `MANPADS_Release_V1.1/`：封裝/釋出版內容，除非任務明確要求，否則不優先修改

## Execution Rules

- 先理解，再修改。
- 若需求不完整，只問最少且必要的問題。
- 沒有使用者確認，不做超出當前任務的順手重構。
- 修改要盡量小而完整，避免半套變更。
- 不以「編譯通過」取代「行為正確」。

## Change Rules

- 變更 JSON 輸出前，先視為跨模組變更。
- 變更 IO 控制邏輯前，先確認是否影響 Tag A/B/C/D 的既有語義。
- 變更 WebSocket 協議前，先確認是否影響 `web/` 與 `faymantu/` 兩套 client/server。
- 變更啟動腳本前，先確認工作目錄、編碼、路徑相對位置是否仍成立。

## Verification Rules

- 文件變更：至少檢查連結、路徑、流程描述與現況一致。
- Python 變更：至少檢查語法與主要啟動路徑。
- C++ 變更：至少檢查建構可行性與受影響模組；若牽涉硬體/IO，需明確標示哪些部分無法在本機完全驗證。
- 協議變更：列出受影響的 producer/consumer。

## Documentation Rules

完成實作後，視變更性質同步更新：

- `README.md`：使用方式、檔案入口、對外行為
- `docs/DEVLOG.md`：決策、演進、踩坑
- `docs/MEMORY.md`：穩定事實或新限制

## Git Rules

- 未經使用者同意，不 commit。
- 未經使用者同意，不 push。
- 提供 `git diff` 摘要與 commit message 草案即可。

## Escalation Triggers

以下情況先停下來確認：

- 要改 JSON 格式或 WebSocket 協議
- 要改硬體配對規則、Type/Tag 語義或 IO 腳位定義
- 要同時改 `web/` 與 `faymantu/` 的對外行為
- 要碰 `AntilatencySdk/`、`build/` 或 release 封裝內容
- 發現文件與程式實作互相矛盾，且無法從上下文判斷哪個是最新

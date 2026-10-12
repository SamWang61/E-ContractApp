# Contributing／貢獻規範

## Language／語言

Project documentation and user-facing API descriptions must include Traditional Chinese and English sections.／專案文件與對外 API 說明必須包含繁體中文與英文段落。

## Changes／變更

Keep runtime code under `full/functions` and `full/web`; keep design and API explanations under `docs`; keep tests under `tests`.／執行程式放在 `full/functions` 與 `full/web`，設計與 API 說明放在 `docs`，測試放在 `tests`。

Before opening a pull request, run `pytest -q` and check that no secret or local environment file is included.／建立 Pull Request 前請執行 `pytest -q`，並確認沒有密鑰或本機環境檔被提交。

## Commit messages／提交訊息

Use imperative English with an optional bilingual scope, for example: `Implement signing invitation workflow／實作簽署邀請流程`.／採用祈使句英文，可附雙語範圍。

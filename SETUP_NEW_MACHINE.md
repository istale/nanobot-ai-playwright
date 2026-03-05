# SETUP_NEW_MACHINE.md

## Nanobot + Gemini Web (Playwright, non-API) 跨機重建指南

> 目標：在新電腦完整重建可用環境，包含 CLI 對話、Gemini 網頁操作、以及 `<tool_call>` 工具調用流程。

---

## 0) 前置需求

- Linux/macOS（建議有圖形環境）
- `python3` 可用
- `git` 可用
- 網路可連到 Gemini 網頁

---

## 1) 取得專案 + 建立虛擬環境

```bash
git clone <YOUR_GITHUB_REPO_URL> nanobot-ai-playwright
cd nanobot-ai-playwright

python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install -U pip
python3 -m pip install -e . playwright
python3 -m playwright install chromium
```

---

## 2) 建立 nanobot 設定檔

```bash
mkdir -p ~/.nanobot
cat > ~/.nanobot/config.json <<'JSON'
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "gemini_web/default",
      "provider": "auto",
      "max_tokens": 8192,
      "temperature": 0.1,
      "max_tool_iterations": 40,
      "memory_window": 100
    }
  },
  "providers": {
    "gemini_web": {
      "api_key": "",
      "api_base": null,
      "extra_headers": null
    }
  },
  "channels": {},
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790,
    "heartbeat": {
      "enabled": true,
      "interval_s": 1800
    }
  },
  "tools": {
    "web": {
      "proxy": null,
      "search": {
        "api_key": "",
        "max_results": 5
      }
    },
    "exec": {
      "timeout": 60,
      "path_append": ""
    },
    "restrict_to_workspace": false,
    "mcp_servers": {}
  }
}
JSON
```

---

## 3) 啟動 CLI

```bash
cd /path/to/nanobot-ai-playwright
source .venv/bin/activate
python3 -m nanobot agent
```

---

## 4) 首次登入 Gemini（必要）

- 第一次啟動會開 Chromium。
- 在瀏覽器完成 Google/Gemini 登入。
- 登入狀態保存在：`~/.nanobot/profiles/gemini-web`
- 這個 profile 不會隨 GitHub 傳遞，新機必須重登。

---

## 5) 最小驗收清單

1. `python3 -m nanobot agent` 可啟動。
2. 輸入：`請回覆：HELLO_OK`，確認有回覆。
3. 再輸入第二句，確認 Chromium 不關閉、可持續對話。
4. 工具測試：
   - 輸入：`請建立 workspace 下的 test-dir`
   - 預期：Gemini 輸出 `<tool_call>...</tool_call>`，nanobot 執行工具後回報完成。
5. 檢查 `outputs/` 有回覆落檔（若流程有落檔）。

---

## 6) 重要提醒（我們討論過）

1. 目前是「Gemini 網頁自動化」不是 Gemini API。
2. 工具調用靠文字協議：

```xml
<tool_call>{"name":"...","arguments":{...}}</tool_call>
```

3. 優先用相對路徑，避免硬寫絕對路徑。
4. 若出現 `SingletonLock`，代表 profile 被舊 Chromium 占用，需先關閉舊實例。

---

## 7) 常見問題

### Q1: `python: command not found`
請改用：
```bash
python3 -m nanobot agent
```

### Q2: `ModuleNotFoundError: No module named 'playwright'`
```bash
source .venv/bin/activate
python3 -m pip install -e . playwright
python3 -m playwright install chromium
```

### Q3: `ProcessSingleton / SingletonLock` 錯誤
```bash
pkill -f "/home/istale/.cache/ms-playwright/chromium-1208/chrome-linux/chrome.*gemini-web" || true
rm -f ~/.nanobot/profiles/gemini-web/SingletonLock ~/.nanobot/profiles/gemini-web/SingletonCookie ~/.nanobot/profiles/gemini-web/SingletonSocket
```

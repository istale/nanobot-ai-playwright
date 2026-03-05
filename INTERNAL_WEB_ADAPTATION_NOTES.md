# INTERNAL_WEB_ADAPTATION_NOTES.md

在不改現有檔名（沿用 `gemini_web`）前提下，改接內部開發網頁模型時，請修改以下檔案與位置。

---

## 1) `nanobot/tools/gemini_web_mvp.py`（主要改這裡）

### 必改位置

1. `GEMINI_URL = "https://gemini.google.com/app"`
   - 改成你的內部開發網頁 URL。

2. `_run_on_page(...)` 裡的 `input_selectors`
   - 改成內網輸入框 selector 清單。

3. 送出操作（目前為 `await prompt_box.press("Enter")`）
   - 如果內網需要按送出按鈕，改成 click submit selector。

4. `response_count_before` / `_response_count()` 內的 selector（目前是 Gemini 的）
   - 改成內網「回覆訊息區塊」的 selector。

5. `response_selectors`（抓最後一則回答）
   - 改成內網可穩定擷取回答原文的 selector。

6. `stop_sel` 完成判定（目前是 Gemini 的 stop 按鈕）
   - 改成內網的「生成中/完成」判定元素（例如 loading 消失、停止按鈕消失等）。

---

## 2) `nanobot/providers/gemini_web_provider.py`

### 可能要改的位置

1. `_build_prompt(...)`
   - 若內網模型不吃目前 `[SYSTEM INSTRUCTION]` 包裝格式，改為內網較穩定的 prompt 格式。
   - 若你需要工具調用，保留 `<tool_call>{"name":"...","arguments":{...}}</tool_call>` 規則提示。

2. `TOOL_CALL_PATTERN` 與 `_extract_tool_calls(...)`
   - 若內網模型輸出的工具格式不同，調整 regex 與 JSON 解析邏輯。

3. `chat(...)`
   - 目前使用 `run_once(... keep_browser_open=True)` 以保留同一瀏覽器 session 多輪對話。
   - 通常建議保留。

---

## 3) `nanobot/cli/commands.py`

在不改 provider 名稱（仍叫 `gemini_web`）前提下，通常不用改。

- 只需確認 `_make_provider()` 仍會走 `gemini_web` 分支。

---

## 4) `nanobot/providers/registry.py`

在不改名稱前提下通常不用改。

- 確認 `gemini_web` provider spec 保留即可。

---

## 5) `nanobot/config/schema.py`

在不改名稱前提下通常不用改。

- 保持 config 使用：`"model": "gemini_web/default"`

---

## 內網頁面請至少提供這些元素資訊（方便改 selector）

1. 輸入框 element/selector
2. 送出按鈕 element/selector（或確認 Enter 可送）
3. 回覆區塊 element/selector（可抓最後一則）
4. 完成狀態 element/selector（例如 loading、stop、done 標誌）

提供這四類後，就能快速把 `gemini_web_mvp.py` 改成對應內網版本。
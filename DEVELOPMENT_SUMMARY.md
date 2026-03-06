# DEVELOPMENT_SUMMARY.md

## 專案背景
本專案從原始 nanobot 程式碼出發，實作「以 Playwright 一般網頁模式操作 Gemini（非 API）」的可用 MVP，並逐步調整為可在內網環境落地的精簡版本。

---

## 討論重點與決策脈絡

1. **第一階段目標（MVP）**
   - 啟動獨立瀏覽器
   - 進入 Gemini 網頁送出單一 prompt
   - 等待回覆完成
   - 擷取完整原文並落地 txt

2. **第二階段（整合到 nanobot 模型配置）**
   - 從「獨立 CLI 指令」升級成可設為 `agents.defaults.model` 的 provider 路徑
   - 模型設定改為 `gemini_web/default`

3. **第三階段（多輪互動可用性）**
   - 修正每輪關閉瀏覽器問題
   - 修正每輪刷新導致對話重置問題
   - 改善回答尚未完成就提早擷取的問題

4. **第四階段（工具調用）**
   - 不使用原生 API function calling，改採文字協議
   - 定義 `<tool_call>{"name":"...","arguments":{...}}</tool_call>`
   - provider 解析後轉成 nanobot 的 ToolCallRequest 交由工具層執行

5. **第五階段（內網部署考量）**
   - 保留既有檔名（不新增 provider 名稱）
   - 提供最小檔案清單與外部 config 模板
   - 進一步做 `gemini_web-only` 精簡模式，降低依賴

---

## 已實作功能

### A. Playwright 網頁模式（非 API）
- 新增 `nanobot/tools/gemini_web_mvp.py`
- 支援：
  - 網頁開啟
  - prompt 輸入送出
  - 回覆完成判定
  - 回覆原文擷取
  - txt 落檔

### B. nanobot provider 整合
- 新增 `nanobot/providers/gemini_web_provider.py`
- 可透過 model 設定 `gemini_web/default` 走網頁 provider
- provider 已接入 agent loop，回覆可回到 CLI

### C. 多輪對話與穩定性補強
- 保持瀏覽器 session，不再每輪關閉
- 避免每輪 `goto` 導致刷新重開對話
- 回覆擷取改為較穩定判定（避免半截答案）
- 增加 debug screenshot（失敗時可定位 UI 變動）
- 快取上次成功輸入 selector，降低後續輪次等待時間

### D. 文字協議工具調用
- system/prompt 中定義 `<tool_call>...</tool_call>` 規範
- provider 端解析 XML 包裹 JSON
- 轉換為 `ToolCallRequest`，交由 nanobot 既有工具執行
- 工具結果回填後可續回覆

### E. 內網精簡版（gemini_web-only）
- `_make_provider()` 限制為僅支援 `gemini_web`
- 移除 runtime 對其他 provider 的必要匯入依賴
- 目標：降低跨環境搬遷成本

---

## 文件與運維產物

1. `SETUP_NEW_MACHINE.md`
   - 跨機重建 SOP
   - 安裝與驗收流程
   - 常見錯誤排除

2. `INTERNAL_WEB_ADAPTATION_NOTES.md`
   - 接內網模型網頁時需改的檔案與程式碼位置
   - selector 與完成判定調整指引

3. `MINIMAL_FILELIST.txt`
   - 最小可運行檔案清單
   - 包含外部 `~/.nanobot/config.json` 模板內容

4. Git 追蹤標記
   - 已建立可回溯 tag：`internal-web-mvp-stable-20260305`

---

## 目前狀態
- 專案可用於：CLI ↔ Playwright ↔ Web 模型 的多輪互動流程
- 已具備文字協議型工具調用能力
- 已提供內網移植所需的最小文件與檔案清單

---

## 下一步建議
1. 針對目標內網頁面替換 selector 與完成判定規則（以實際 HTML 為準）。
2. 增加 tool_call 協議的錯誤容錯（格式錯誤回退策略）。
3. 若後續穩定，補一套自動化 smoke tests（單輪、多輪、tool_call）。
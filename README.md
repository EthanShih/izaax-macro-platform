# 總經分析模組 (v1.0.0)
*(Macroeconomic Analysis Framework, Automated FRED Data Pipeline & Interactive Dashboard)*

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-Gemini%203.6%20Flash-blueviolet)](https://aistudio.google.com/)

本專案依據經典總體經濟分析框架（景氣循環四階段：復甦期、成長期、榮景期、衰退期），建構了完整的數據自動化下載、本地時序資料庫維護、每日 Gemini AI 實時宏觀診斷，以及現代化互動視覺化儀表板。

---

## 📌 核心功能 (v1.0.0 正式版)

1. **AI 實時總經深度診斷代理程式 (`gemini_macro_agent.py`)**：
   - 每日自動讀取 23 項核心指標數據（最新值、MoM 月增率、YoY 年增率），打包為標準宏觀 Prompt。
   - 直接調用最新 **Google Gemini 3.6 Flash** REST API 進行全維度宏觀推論，輸出嚴格符合 JSON Schema 的專業分析報告。
   - 具備雙軌容錯：若未設定金鑰或連線異常，自動啟動內建確定性規則庫作為保底備援，確保系統永不中斷。

2. **前端三大功能分頁 (`docs/index.html` / GitHub Pages)**：
   - **分頁 1：📋 最新總經深度診斷**
     - **即時景氣循環定位**：動態判定階段名稱、核心判定依據、AI 引擎識別與時間戳記。
     - **四大核心體質卡片**：勞動市場、通膨受控、公債殖利率利差、終端消費。
     - **五大維度交叉比對分析 (Cross-Indicator Validation)**：跳脫單一指標雜訊，從供需、傳導鏈、資本支出、房市製造、貨幣流動性全面驗證。
     - **未來三大情境推論 (Forward Scenarios)**：基準軟著陸 (60%)、下行硬著陸 (25%)、通膨停滯 (15%) 與對應最佳資產反應。
     - **關鍵追蹤指標與門檻清單**：客觀設定初領失業金、核心 PCE 等敏感門檻與應對邏輯，支援 FRED 官方圖表外跳連結。
     - **全部 23 項總經指標數值總覽表**：支援分類篩選。
   - **分頁 2：🕰️ 歷史時空回顧**
     - 自由選擇歷史任一基準日或載入 9 大經典歷史情境（次貸風暴、雷曼破產、無限QE、40年通膨大頂、矽谷銀行倒掛等）。
     - 嚴格時空切片（剔除未來數據污染），動態重演當時公佈數據、動態景氣循環定位。
     - **重點指標歷史變化簡圖 (Sparklines Gallery)**：展示基準日前 8 期之走勢簡圖，即刻辨識加速、見頂或觸底。
   - **分頁 3：📈 指標互動走勢圖**
     - 支援滑鼠放大、縮小、平移。
     - 雙 Y 軸配置（解決大數值與小比例指標之刻度壓縮問題）。
     - 動態計算與切換：原始數據、指數基期=100、YoY 年成長率、MoM/QoQ 月季成長率。
     - 全局字體多階縮放 (A- / 100% / A+)。

3. **自動化 CI/CD 排程 (`.github/workflows/daily_update.yml`)**：
   - 每日台灣時間早上 09:00 (UTC 01:00) 自動執行 FRED 數據增量更新、呼叫 Gemini 產製最新報告、重新編譯並自動 Push 發布至 GitHub Pages。
   - 支援 GitHub Actions 手動一鍵觸發 (`workflow_dispatch`)。

```text
macro-platform/
│
├── macro_framework.md        # 總經理論與指標架構文件
├── batch_download_agent.py   # 歷史原始數據批次下載腳本
├── update_daemon_agent.py    # 定期增量更新背景常駐程式
├── macro_dashboard.py        # Streamlit + Plotly 前端儀表板
├── macro_data.db             # 本地 SQLite 時序資料庫 (內含 23 項指標數據)
├── requirements.txt          # Python 依賴套件清單
├── docs/                     # GitHub Pages 靜態網站目錄
│   ├── index.html            # 靜態互動儀表板
│   └── data.js               # 預編譯指標數據庫
└── README.md                 # 專案說明文件
```

---

## 🚀 快速開始

### 1. 安裝環境依賴

```bash
pip install -r requirements.txt
```

### 2. 資料下載與維護 (可選，專案已自帶最新數據庫)

- **重新下載全部歷史數據**：
  ```bash
  python batch_download_agent.py
  ```
- **啟動背景增量更新排程**：
  ```bash
  python update_daemon_agent.py
  ```

### 3. 啟動視覺化儀表板

- **本地 Streamlit 執行**：
  ```bash
  streamlit run macro_dashboard.py
  ```
- **線上 GitHub Pages 瀏覽**：
  直接開啟 GitHub Pages 部署網址即可。

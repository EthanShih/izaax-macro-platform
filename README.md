# 總經分析模組
*(Macroeconomic Analysis Framework, Automated FRED Data Pipeline & Interactive Dashboard)*

本專案依據經典總經分析框架（景氣循環四階段：復甦期、成長期、榮景期、衰退期），建構了完整的數據自動化下載、本地時序資料庫維護、以及現代化互動視覺化儀表板。

---

## 📌 核心功能

1. **總經分析模組框架 (`macro_framework.md`)**：
   - 詳細記錄四階段景氣循環特徵與定量判斷標準。
   - 彙整 23 項核心美國總經指標（就業、消費、通膨、製造、房地產、利率與公債利差）之出處與規律發布日程。

2. **自動化資料工程管道 (FRED Data Pipeline)**：
   - `batch_download_agent.py`：批次爬取自 2000 年以來的長天期歷史原始數據，儲存於 SQLite (`macro_data.db`)。
   - `update_daemon_agent.py`：常駐背景代理程式，每日自動追蹤最新發布數據並執行增量更新。

3. **前端視覺化與總經診斷儀表板 (`macro_dashboard.py` / GitHub Pages)**：
   - **分頁 1：📊 指標互動走勢圖**
     - 支援滑鼠放大、縮小、平移。
     - 雙 Y 軸配置（解決大數值與小比例指標之刻度壓縮問題）。
     - 動態計算與切換：原始數據、指數基期=100、YoY 年成長率、MoM/QoQ 月季成長率（針對比例型數據自動切換為差值計算）。
     - 時間區間自由篩選與重點數據發布行事曆。
   - **分頁 2：📋 最新數據與總經診斷**
     - **景氣循環定位儀表**：依據初領失業金、失業率、倒掛解讀、通膨等多維度動態判定目前循環階段。
     - **宏觀現況深度剖析**、**三大核心風險提示** 與 **資產配置策略建議**。
     - **23 項指標最新數據總覽表**（含最新值、MoM 變化、YoY 年增/差值，支援分類篩選）。

---

## 📂 專案架構

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

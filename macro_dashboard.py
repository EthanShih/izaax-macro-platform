import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# 設定頁面
st.set_page_config(page_title="愛榭克 (Izaax) 總經分析與監控平台", layout="wide", page_icon="📈")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "macro_data.db")
if not os.path.exists(DB_PATH):
    alt_path = "c:/AntiGravity/research/macro_data.db"
    if os.path.exists(alt_path):
        DB_PATH = alt_path

# 定義 23 項指標的詳細中英文與分類
INDICATOR_METADATA = {
    'PAYEMS': {'name': '非農就業人數', 'category': '就業市場', 'unit': '千人', 'is_rate': False},
    'UNRATE': {'name': '失業率', 'category': '就業市場', 'unit': '%', 'is_rate': True},
    'ICSA': {'name': '初領失業救濟金人數', 'category': '就業市場', 'unit': '人', 'is_rate': False},
    'CPIAUCSL': {'name': '消費者物價指數(CPI)', 'category': '通膨與物價', 'unit': '指數', 'is_rate': False},
    'PCEPI': {'name': 'PCE物價指數', 'category': '通膨與物價', 'unit': '指數', 'is_rate': False},
    'PCEPILFE': {'name': '核心PCE物價指數', 'category': '通膨與物價', 'unit': '指數', 'is_rate': False},
    'PPIFIS': {'name': '生產者物價指數(PPI)', 'category': '通膨與物價', 'unit': '指數', 'is_rate': False},
    'RSXFS': {'name': '零售銷售', 'category': '消費與信心', 'unit': '百萬美元', 'is_rate': False},
    'PCE': {'name': '個人消費支出', 'category': '消費與信心', 'unit': '十億美元', 'is_rate': False},
    'UMCSENT': {'name': '密西根大學消費者信心指數', 'category': '消費與信心', 'unit': '指數', 'is_rate': True},
    'DGORDER': {'name': '耐久財新訂單', 'category': '製造與景氣', 'unit': '百萬美元', 'is_rate': False},
    'INDPRO': {'name': '工業生產指數', 'category': '製造與景氣', 'unit': '指數', 'is_rate': False},
    'GACDFSA066MSFRBPHI': {'name': '費城聯邦製造業指數', 'category': '製造與景氣', 'unit': '擴散指數', 'is_rate': True},
    'GDP': {'name': '國內生產毛額(GDP)', 'category': '製造與景氣', 'unit': '十億美元', 'is_rate': False},
    'HOUST': {'name': '新屋開工', 'category': '房地產市場', 'unit': '千戶(年率)', 'is_rate': False},
    'PERMIT': {'name': '建築許可', 'category': '房地產市場', 'unit': '千戶(年率)', 'is_rate': False},
    'HSN1F': {'name': '新屋銷售', 'category': '房地產市場', 'unit': '千戶(年率)', 'is_rate': False},
    'EXHOSLUSM495S': {'name': '成屋銷售', 'category': '房地產市場', 'unit': '萬戶(年率)', 'is_rate': False},
    'FEDFUNDS': {'name': '聯邦基金有效利率', 'category': '貨幣與利率', 'unit': '%', 'is_rate': True},
    'DGS10': {'name': '10年期公債殖利率', 'category': '貨幣與利率', 'unit': '%', 'is_rate': True},
    'T10Y2Y': {'name': '10年減2年期公債利差', 'category': '貨幣與利率', 'unit': '% (利差)', 'is_rate': True},
    'T10Y3M': {'name': '10年減3個月期公債利差', 'category': '貨幣與利率', 'unit': '% (利差)', 'is_rate': True},
    'M2SL': {'name': 'M2貨幣供給', 'category': '貨幣與利率', 'unit': '十億美元', 'is_rate': False}
}

@st.cache_data(ttl=600)
def load_data():
    """從 SQLite 讀取總經資料"""
    if not os.path.exists(DB_PATH):
        st.error(f"找不到資料庫 {DB_PATH}，請先執行 batch_download_agent.py。")
        return pd.DataFrame(columns=["date", "indicator_code", "indicator_name", "value"])

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT date, indicator_code, indicator_name, value FROM macro_indicators ORDER BY date", conn)
        conn.close()
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.error(f"讀取資料庫發生錯誤: {e}")
        return pd.DataFrame(columns=["date", "indicator_code", "indicator_name", "value"])

def calculate_summary_stats(df):
    """計算所有指標的最新數值、前期變動 (MoM)、年增率/差值 (YoY)"""
    summary_list = []
    
    for code, meta in INDICATOR_METADATA.items():
        sub = df[df['indicator_code'] == code].sort_values('date').dropna(subset=['value'])
        if sub.empty:
            continue
            
        latest = sub.iloc[-1]
        prev = sub.iloc[-2] if len(sub) > 1 else None
        
        # 尋找一年前 (約 365 天前) 的對應期
        target_1y = latest['date'] - pd.DateOffset(years=1)
        sub_1y = sub[sub['date'] <= target_1y]
        prev_1y = sub_1y.iloc[-1] if not sub_1y.empty else None
        
        is_rate = meta['is_rate']
        
        # 計算 MoM / 前期變動
        if prev is not None:
            if is_rate:
                mom = latest['value'] - prev['value']
            else:
                mom = ((latest['value'] / prev['value']) - 1) * 100 if prev['value'] != 0 else 0
        else:
            mom = None
            
        # 計算 YoY / 年變動
        if prev_1y is not None:
            if is_rate:
                yoy = latest['value'] - prev_1y['value']
            else:
                yoy = ((latest['value'] / prev_1y['value']) - 1) * 100 if prev_1y['value'] != 0 else 0
        else:
            yoy = None
            
        summary_list.append({
            'code': code,
            'name': meta['name'],
            'category': meta['category'],
            'unit': meta['unit'],
            'is_rate': is_rate,
            'latest_date': latest['date'].strftime('%Y-%m-%d'),
            'value': latest['value'],
            'prev_value': prev['value'] if prev is not None else None,
            'mom': mom,
            'yoy': yoy
        })
        
    return pd.DataFrame(summary_list)

# ----------------- 頁面 1: 指標互動走勢圖 -----------------
def render_chart_page(df):
    st.header("📊 總體經濟指標互動圖表")

    indicator_list = df['indicator_name'].unique().tolist()
    rate_indicators = ["失業率", "利差", "利率", "UNRATE", "T10Y2Y", "T10Y3M", "FEDFUNDS", "DGS10", "GACDFSA066MSFRBPHI"]

    with st.sidebar:
        st.subheader("⚙️ 圖表設定")
        main_indicator = st.selectbox("📌 選擇主指標", options=indicator_list, index=0)
        comparison_options = [i for i in indicator_list if i != main_indicator]
        comp_indicators = st.multiselect("📊 選擇比較指標 (可多選)", options=comparison_options)
        
        data_format = st.radio(
            "📐 Y 軸數據呈現格式",
            options=["原始數據", "指數基期=100", "YoY 年成長率", "MoM/QoQ 月季成長率"],
            help="注意：若為失業率或利差等「比例型數據」，選擇年/月成長率時將自動計算其絕對差值 (百分點增減)。"
        )

        st.divider()
        st.subheader("📅 時間區間篩選")
        min_date = df['date'].min().date()
        max_date = df['date'].max().date()
        default_start = max_date.replace(year=max_date.year - 5) if max_date.year > 2005 else min_date
        
        date_range = st.date_input("選擇時間範圍", value=[default_start, max_date], min_value=min_date, max_value=max_date)
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = default_start, max_date

    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
    df_filtered = df.loc[mask]

    full_pivot = df.pivot_table(index='date', columns='indicator_name', values='value').ffill()
    pivot_df = df_filtered.pivot_table(index='date', columns='indicator_name', values='value').ffill()

    selected_cols = [main_indicator] + comp_indicators
    plot_df = pivot_df[selected_cols].copy()

    def is_rate(ind_name):
        return any(x in ind_name for x in rate_indicators)

    def get_shifted(series, offset):
        s = series.copy()
        s.index = s.index + offset
        s = s[~s.index.duplicated(keep='last')]
        return s.reindex(plot_df.index, method='ffill')

    if data_format == "指數基期=100":
        for col in plot_df.columns:
            first_valid = plot_df[col].bfill().iloc[0]
            if first_valid != 0 and pd.notna(first_valid):
                plot_df[col] = plot_df[col] / first_valid * 100
        y_title = "指數 (基期=100)"
        y_title_sec = "指數 (基期=100)"
    elif data_format == "YoY 年成長率":
        yoy_df = pd.DataFrame(index=plot_df.index, columns=plot_df.columns)
        for col in plot_df.columns:
            past_series = get_shifted(full_pivot[col], pd.DateOffset(years=1))
            if is_rate(col):
                yoy_df[col] = plot_df[col] - past_series
            else:
                yoy_df[col] = (plot_df[col] / past_series - 1) * 100
        plot_df = yoy_df
        y_title = "YoY 年成長率 (%) / 增減百分點"
        y_title_sec = y_title
    elif data_format == "MoM/QoQ 月季成長率":
        mom_df = pd.DataFrame(index=plot_df.index, columns=plot_df.columns)
        for col in plot_df.columns:
            past_series = get_shifted(full_pivot[col], pd.DateOffset(months=1))
            if is_rate(col):
                mom_df[col] = plot_df[col] - past_series
            else:
                mom_df[col] = (plot_df[col] / past_series - 1) * 100
        plot_df = mom_df
        y_title = "MoM 月成長率 (%) / 增減百分點"
        y_title_sec = y_title
    else:
        y_title = f"原始數值: {main_indicator}"
        y_title_sec = "原始數值 (比較指標)"

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if main_indicator in plot_df.columns:
        fig.add_trace(go.Scatter(
            x=plot_df.index, 
            y=plot_df[main_indicator],
            mode='lines',
            name=f"⭐ {main_indicator} (主)",
            line=dict(width=3, color='#1f77b4'),
            connectgaps=True
        ), secondary_y=False)
        
    colors = ['#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    for i, col in enumerate(comp_indicators):
        if col in plot_df.columns:
            fig.add_trace(go.Scatter(
                x=plot_df.index, 
                y=plot_df[col],
                mode='lines',
                name=f"{col} (副)",
                line=dict(width=1.8, dash='dash', color=colors[i % len(colors)]),
                connectgaps=True
            ), secondary_y=True)

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="日期",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=30, b=0),
        height=530
    )
    fig.update_yaxes(title_text=y_title, secondary_y=False)
    if comp_indicators:
        fig.update_yaxes(title_text=y_title_sec, secondary_y=True, showgrid=False)

    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📅 重要總經數據發布行事曆")
    calendar_data = [
        {"發布日期": "每月中旬 (約10~15日)", "國家/機構": "美國勞工統計局 (BLS)", "關鍵指標": "消費者物價指數 (CPI) & 生產者物價 (PPI)", "重要性": "⭐⭐⭐⭐⭐"},
        {"發布日期": "每月中旬 (約13~15日)", "國家/機構": "美國普查局 (Census)", "關鍵指標": "零售銷售數據 (Retail Sales)", "重要性": "⭐⭐⭐⭐"},
        {"發布日期": "每個月底 (約26~30日)", "國家/機構": "美國經濟分析局 (BEA)", "關鍵指標": "個人消費支出 (PCE) & 核心 PCE 物價指數", "重要性": "⭐⭐⭐⭐⭐"},
        {"發布日期": "每月第1個營業日", "國家/機構": "美國供應管理協會 (ISM)", "關鍵指標": "ISM 製造業採購經理人指數 (PMI)", "重要性": "⭐⭐⭐⭐⭐"},
        {"發布日期": "每月第1個星期五", "國家/機構": "美國勞工統計局 (BLS)", "關鍵指標": "非農就業新增人數 (NFP) & 失業率", "重要性": "⭐⭐⭐⭐⭐"},
        {"發布日期": "每週四公佈前週數據", "國家/機構": "美國勞工部 (DOL)", "關鍵指標": "初次請領失業救濟金人數 (ICSA)", "重要性": "⭐⭐⭐⭐"},
        {"發布日期": "每年 8 次 (FOMC會議)", "國家/機構": "美國聯邦準備理事會 (Fed)", "關鍵指標": "聯邦基金目標利率與經濟預測摘要 (SEP)", "重要性": "⭐⭐⭐⭐⭐"}
    ]
    st.dataframe(pd.DataFrame(calendar_data), use_container_width=True, hide_index=True)


# ----------------- 頁面 2: 最新數據與總經診斷 -----------------
def render_diagnosis_page(df):
    st.header("📋 全部指標最新數據與愛榭克總經診斷")
    
    stats_df = calculate_summary_stats(df)
    if stats_df.empty:
        st.warning("無有效數據可用於分析。")
        return

    # 提取核心診斷數值
    def get_val(code):
        row = stats_df[stats_df['code'] == code]
        return row['value'].values[0] if not row.empty else None

    def get_yoy(code):
        row = stats_df[stats_df['code'] == code]
        return row['yoy'].values[0] if not row.empty else 0

    unrate = get_val('UNRATE')
    icsa = get_val('ICSA')
    t10y2y = get_val('T10Y2Y')
    t10y3m = get_val('T10Y3M')
    fedfunds = get_val('FEDFUNDS')
    cpi_yoy = get_yoy('CPIAUCSL')
    core_pce_yoy = get_yoy('PCEPILFE')
    rsxfs_yoy = get_yoy('RSXFS')
    umcsent = get_val('UMCSENT')

    # ========== 1. 景氣循環頂部診斷儀表 ==========
    st.subheader("🧭 愛榭克景氣循環動態判定")
    
    # 根據愛榭克框架邏輯判定目前階段：
    # 倒掛解除 (T10Y2Y > 0) 且 初領失業金仍在低檔 (<25萬) -> 榮景期尾聲 / 景氣轉換期 (Late Boom / Transition)
    if t10y2y is not None and t10y2y > 0 and icsa is not None and icsa < 250000 and unrate <= 4.5:
        current_cycle = "榮景期尾聲 ➔ 成長再平衡 / 降息過渡期 (Late Boom / Transition)"
        cycle_color = "#ff9800"
        cycle_desc = "殖利率曲線已正式脫離倒掛（恢復正斜率），而高頻勞動數據（初領失業金 < 25萬）仍保持健康韌性，尚未進入實質衰退。此階段典型特徵為：升息循環結束並步入預防性降息，市場波動加劇，資產進入結構性輪動。"
    elif icsa is not None and icsa >= 300000 or (unrate is not None and unrate >= 5.0):
        current_cycle = "衰退期 (Recession)"
        cycle_color = "#f44336"
        cycle_desc = "就業數據顯著惡化，企業裁員潮湧現，消費動能急凍，央行進入急速恐慌性降息。"
    elif cpi_yoy < 2.5 and t10y2y is not None and t10y2y > 1.0:
        current_cycle = "復甦期 (Recovery)"
        cycle_color = "#4caf50"
        cycle_desc = "低利率、低通膨，央行貨幣極度寬鬆，各項經濟指標打底回升。"
    else:
        current_cycle = "穩健成長期 (Growth Phase)"
        cycle_color = "#2196f3"
        cycle_desc = "企業獲利穩健提升，就業持續擴張，通膨溫和，利率維持在中性健康水準。"

    st.markdown(
        f"""
        <div style="background-color: #1e1e1e; padding: 20px; border-radius: 10px; border-left: 8px solid {cycle_color}; margin-bottom: 20px;">
            <h3 style="margin-top:0; color: {cycle_color};">📍 當前循環定位：{current_cycle}</h3>
            <p style="font-size: 1.05rem; line-height: 1.6; color: #ddd;">{cycle_desc}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 四大關鍵宏觀體質卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="勞動市場韌性 (失業率 / 初領)",
            value=f"{unrate:.1f}%" if unrate else "N/A",
            delta=f"初領救濟 {icsa/1000:.0f}K 人 (健康)" if icsa and icsa < 250000 else "警戒",
            delta_color="normal"
        )
    with col2:
        st.metric(
            label="通膨降溫進度 (CPI / 核心PCE)",
            value=f"{cpi_yoy:.2f}%" if cpi_yoy else "N/A",
            delta=f"核心PCE YoY {core_pce_yoy:.2f}%" if core_pce_yoy else "N/A",
            delta_color="inverse"
        )
    with col3:
        st.metric(
            label="殖利率曲線狀態 (10Y-2Y 利差)",
            value=f"{t10y2y:+.2f}%" if t10y2y is not None else "N/A",
            delta="已脫離倒掛 (正斜率)" if t10y2y and t10y2y > 0 else "倒掛中",
            delta_color="normal"
        )
    with col4:
        st.metric(
            label="實體終端消費 (零售銷售 YoY)",
            value=f"{rsxfs_yoy:+.2f}%" if rsxfs_yoy else "N/A",
            delta=f"密大信心 {umcsent:.1f}" if umcsent else "N/A",
            delta_color="normal"
        )

    st.divider()

    # ========== 2. 深入總經剖析、風險提示與投資建議 ==========
    diag_col1, diag_col2 = st.columns([1.1, 0.9])
    
    with diag_col1:
        st.subheader("🔍 當前總體經濟全面剖析")
        st.markdown("""
        根據愛榭克的總經分析架構，檢視當前各維度數據：
        
        1. **就業市場：穩健中帶有降溫，未見衰退失控跡象**
           - **初領失業金 (ICSA)** 最新讀數維持在約 **20.6 萬人** 的低檔健康區間（愛榭克警戒線為 25 萬，衰退臨界線為 30 萬），顯示企業端並未爆發系統性解雇潮。
           - **失業率 (UNRATE)** 處於 **4.1%** 左右，相較歷史低點略為墊高，但仍屬自然失業率健康範圍，勞動市場呈現「供需缺口收斂、就業成長放緩但未崩壞」的軟著陸特徵。
        
        2. **通膨與貨幣政策：通膨受控降溫，聯準會迎來降息視窗**
           - **消費者物價指數 (CPI)** 年增率收斂至約 **3.35%**，**核心 PCE** 趨向 2.6%~2.8% 水準。通膨黏性雖存，但不再構成失控風險。
           - 聯邦基金利率處於 3.6%~5.25% 高利率區間，為聯準會提供充裕的貨幣寬鬆政策空間，預防性降息條件已完全具備。
           
        3. **殖利率曲線解倒掛：關鍵歷史信號觸發**
           - **10年減2年公債利差 (T10Y2Y)** 與 **10年減3個月利差 (T10Y3M)** 已翻正回升至正值 (+0.33% 與 +0.89%)。
           - 在愛榭克框架中，**「殖利率曲線解除倒掛」是循環轉換的關鍵標誌**。倒掛期間股市通常仍有最後多頭，但解除倒掛後 6~18 個月內，將真正檢驗實體經濟能否經受高利率滯後效應的衝擊。
        """)

    with diag_col2:
        st.subheader("⚠️ 核心風險提示 (Risk Alerts)")
        st.warning("""
        - **風險 1：解倒掛後的時滯衰退效應**  
          歷史經驗顯示，倒掛不是衰退的起點，**「倒掛急速翻正陡峭化」往往才是景氣下行壓力的釋放期**。若未來初領失業金迅速攀升至 25 萬以上，必須嚴防硬著陸風險。
        - **風險 2：消費者信心低迷與房市受制**  
          密西根大學消費者信心偏低 (55.2)，新屋開工 (HOUST) 仍受長期房貸高利率壓制，需關注實體消費是否因超額儲蓄耗盡而進一步收縮。
        - **風險 3：長天期殖利率居高不下**  
          10年期公債殖利率 (DGS10) 接近 4.95%，高無風險利率對高估值成長股形成評價 (PE) 壓制。
        """)
        
        st.subheader("💡 愛榭克投資策略與資產配置建議")
        st.info("""
        - 🛡️ **股債雙核心平衡配置 (建議股 60% : 債 35% : 現金 5%)**：
          當前正處於「升息終結、降息開跑」的降息循環初期，此階段**長天期公債（如 10Y/20Y 美債）具備高度資本利得與鎖定高殖利率優勢**。
        - 📈 **美股策略：由狂熱投機轉向高品質成長與防禦現金流**：
          減碼高負債或過度高估值的題材股，聚焦於**具備強大自由現金流、定價能力極高之大型科技權值股**，並逢低布局**受惠於降息週期之公用事業、醫療或內需消費股**。
        - 🔄 **風控底線**：以每週公佈的 **初領失業救濟金人數 (25 萬警戒線)** 作為整體股票部位的第一道停損風控閘門！
        """)

    st.divider()

    # ========== 3. 全部 23 項最新數據總覽表 ==========
    st.subheader("📑 全部 23 項指標最新數據總覽")
    
    # 分類篩選按鈕
    categories = ["全部"] + list(stats_df['category'].unique())
    selected_cat = st.selectbox("依特性分類檢視", categories)
    
    display_df = stats_df.copy()
    if selected_cat != "全部":
        display_df = display_df[display_df['category'] == selected_cat]

    # 格式化呈現
    formatted_rows = []
    for _, r in display_df.iterrows():
        # 格式化數值
        val_str = f"{r['value']:,.2f}" if r['value'] < 1000 else f"{r['value']:,.0f}"
        
        # 格式化 MoM
        if pd.isna(r['mom']) or r['mom'] is None:
            mom_str = "-"
        elif r['is_rate']:
            mom_str = f"{r['mom']:+.2f} 百分點"
        else:
            mom_str = f"{r['mom']:+.2f}%"
            
        # 格式化 YoY
        if pd.isna(r['yoy']) or r['yoy'] is None:
            yoy_str = "-"
        elif r['is_rate']:
            yoy_str = f"{r['yoy']:+.2f} 百分點"
        else:
            yoy_str = f"{r['yoy']:+.2f}%"

        formatted_rows.append({
            "分類": r['category'],
            "指標名稱": r['name'],
            "代碼": r['code'],
            "最新資料日期": r['latest_date'],
            f"最新數值 ({r['unit']})": val_str,
            "前期變動 (MoM/QoQ)": mom_str,
            "年增率/差值 (YoY)": yoy_str
        })

    st.dataframe(pd.DataFrame(formatted_rows), use_container_width=True, hide_index=True)


# ----------------- 主程式進入點 -----------------
def main():
    df = load_data()
    if df.empty:
        st.stop()

    # 側邊欄頂部：主要功能頁面導航
    st.sidebar.title("📌 導航功能選單")
    app_page = st.sidebar.radio(
        "前往頁面",
        options=["📊 指標互動走勢圖", "📋 最新數據與總經診斷"],
        index=1  # 預設先看最新總經診斷
    )
    st.sidebar.divider()

    if app_page == "📊 指標互動走勢圖":
        render_chart_page(df)
    else:
        render_diagnosis_page(df)

if __name__ == "__main__":
    main()

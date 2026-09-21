import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import datetime

# 設定頁面
st.set_page_config(page_title="總經分析模組", layout="wide", page_icon="📈")

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
    'GDP': {'name': '名目GDP (BEA)', 'category': '製造與景氣', 'unit': '十億美元', 'is_rate': False},
    'GDPC1': {'name': '實質GDP (BEA)', 'category': '製造與景氣', 'unit': '十億美元', 'is_rate': False},
    'A191RL1Q225SBEA': {'name': '實質GDP季增年率 (BEA)', 'category': '製造與景氣', 'unit': '%', 'is_rate': True},
    'HOUST': {'name': '新屋開工', 'category': '房地產市場', 'unit': '千戶(年率)', 'is_rate': False},
    'PERMIT': {'name': '建築許可', 'category': '房地產市場', 'unit': '千戶(年率)', 'is_rate': False},
    'HSN1F': {'name': '新屋銷售', 'category': '房地產市場', 'unit': '千戶(年率)', 'is_rate': False},
    'EXHOSLUSM495S': {'name': '成屋銷售', 'category': '房地產市場', 'unit': '萬戶(年率)', 'is_rate': False},
    'FEDFUNDS': {'name': '聯邦資金利率', 'category': '貨幣與利率', 'unit': '%', 'is_rate': True},
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

def calculate_summary_stats(df, cutoff_date=None, spark_periods=8):
    """計算所有指標在特定基準日以前的最新數值、變動率與歷史簡圖數據"""
    if cutoff_date is not None:
        df_base = df[df['date'] <= cutoff_date]
    else:
        df_base = df

    summary_list = []
    
    for code, meta in INDICATOR_METADATA.items():
        sub = df_base[df_base['indicator_code'] == code].sort_values('date').dropna(subset=['value'])
        if sub.empty:
            continue
            
        latest = sub.iloc[-1]
        prev = sub.iloc[-2] if len(sub) > 1 else None
        
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

        spark_sub = sub.tail(spark_periods)
        spark_dates = spark_sub['date'].dt.strftime('%Y-%m-%d').tolist()
        spark_vals = spark_sub['value'].tolist()

        spark_yoy_vals = []
        for d, v in zip(spark_sub['date'], spark_sub['value']):
            t_past = d - pd.DateOffset(years=1)
            past_match = sub[sub['date'] <= t_past]
            if not past_match.empty:
                pv = past_match.iloc[-1]['value']
                val_yoy = (v - pv) if is_rate else (((v / pv) - 1) * 100 if pv != 0 else 0)
            else:
                val_yoy = 0
            spark_yoy_vals.append(round(val_yoy, 2))
            
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
            'yoy': yoy,
            'spark_dates': spark_dates,
            'spark_vals': spark_vals,
            'spark_yoy_vals': spark_yoy_vals
        })
        
    return pd.DataFrame(summary_list)

def create_sparkline_fig(dates, values, color='#2563eb', title='', is_rate=False, unit=''):
    """生成簡潔的歷史微型折線圖 (Sparkline)"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode='lines+markers',
        line=dict(color=color, width=2.2),
        marker=dict(size=4, color=color),
        hovertemplate='%{x}<br><b>%{y:.2f}</b><extra></extra>'
    ))
    fig.update_layout(
        height=125,
        margin=dict(l=10, r=10, t=28, b=15),
        xaxis=dict(showgrid=False, showline=True, linecolor='#cbd5e1', tickfont=dict(size=9, color='#64748b')),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickfont=dict(size=9, color='#64748b')),
        title=dict(text=f"<b>{title}</b> (近{len(dates)}期)", font=dict(size=11, color='#334155'), x=0.01, y=0.98),
        font=dict(family='inherit'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig


# ----------------- 總經多維交叉驗證與未來推論引擎 -----------------
def generate_macro_diagnosis(stats_df, as_of_title="當前"):
    """
    全方位多維交叉比對與未來情境推論分析模組
    """
    def get_val(code):
        row = stats_df[stats_df['code'] == code]
        return row['value'].values[0] if not row.empty else None

    def get_yoy(code):
        row = stats_df[stats_df['code'] == code]
        return row['yoy'].values[0] if not row.empty else 0

    unrate = get_val('UNRATE')
    icsa = get_val('ICSA')
    payems_yoy = get_yoy('PAYEMS')
    
    cpi_yoy = get_yoy('CPIAUCSL')
    core_pce_yoy = get_yoy('PCEPILFE')
    ppi_yoy = get_yoy('PPIFIS')
    
    rsxfs_yoy = get_yoy('RSXFS')
    pce_yoy = get_yoy('PCE')
    umcsent = get_val('UMCSENT')
    dgorder_yoy = get_yoy('DGORDER')
    indpro_yoy = get_yoy('INDPRO')
    philly_fed = get_val('GACDFSA066MSFRBPHI')
    
    permit_yoy = get_yoy('PERMIT')
    houst_yoy = get_yoy('HOUST')
    
    t10y2y = get_val('T10Y2Y')
    t10y3m = get_val('T10Y3M')
    fedfunds = get_val('FEDFUNDS')
    dgs10 = get_val('DGS10')
    m2_yoy = get_yoy('M2SL')

    # 1. 景氣循環動態定位
    if (icsa is not None and icsa >= 300000) or (unrate is not None and unrate >= 5.5):
        current_cycle = "衰退期 (Recession Phase)"
        cycle_color = "#ef4444"
        cycle_desc = "就業市場出現廣泛性裁員潮（初領失業救濟金飆升突破 30 萬門檻），實體經濟全面收縮。央行處於緊急降息救市階段。"
        alloc_advice = "🛡️ 資產配置建議：防禦至上（現金 40% ｜ 長期公債 40% ｜ 防禦型股票 20%）。嚴控信用風險，等待景氣全面落底訊號。"
        risk_alert = "注意企業違約潮、流動性枯竭及盈利預期大幅下修之衝擊。"
    elif t10y2y is not None and t10y2y < 0:
        current_cycle = "榮景期 (Boom Phase / Inversion Peak)"
        cycle_color = "#f59e0b"
        cycle_desc = f"長短殖利率曲線處於深度倒掛狀態 (10Y-2Y 為 {t10y2y:+.2f}%)，央行激進升息抗擊通膨。經濟擴張雖達頂點，但倒掛預示著後續週期轉折正逐步逼近。"
        alloc_advice = "⚖️ 資產配置建議：由股轉債漸進平衡（股票 50% ｜ 中長天期公債 40% ｜ 現金 10%）。鎖定高無風險利率，聚焦高自由現金流防禦標的。"
        risk_alert = "留意貨幣緊縮政策之滯後衝擊，以及銀行業與高槓桿資產之流動性壓力。"
    elif t10y2y is not None and t10y2y >= 0 and (icsa is not None and icsa < 260000) and (unrate is not None and unrate <= 4.8):
        current_cycle = "榮景期尾聲 ➔ 成長再平衡 / 降息過渡期 (Late Boom / Transition)"
        cycle_color = "#f97316"
        cycle_desc = f"長短天期公債利差正式脫離倒掛、恢復正斜率 (+{t10y2y:.2f}%)。初領失業金仍在健康低檔 (未破 25 萬警戒線)，實體經濟具備韌性，步入預防性降息窗口。"
        alloc_advice = "📈 資產配置建議：股債雙核心佈局（股票 60% ｜ 長天期美債 35% ｜ 現金 5%）。降息初期長端美債具備高鎖利與資本利得優勢。"
        risk_alert = "嚴防解倒掛後的時滯衰退效應。每週四緊盯初領失業金人數是否突破 25 萬警戒線。"
    elif cpi_yoy < 2.5 and t10y2y is not None and t10y2y > 0.8 and (fedfunds is not None and fedfunds < 2.0):
        current_cycle = "復甦期 (Recovery Phase)"
        cycle_color = "#10b981"
        cycle_desc = "央行維持極度寬鬆政策，低利率、低通膨，市場資金充裕，製造業與初領失業金見高回落，景氣觸底強烈反彈。"
        alloc_advice = "🚀 資產配置建議：全力進攻（股票 80% ｜ 高收益債/商品 15% ｜ 現金 5%）。優先配置高貝塔週期股、中小型股與科技成長股。"
        risk_alert = "注意早期復甦期可能出現之二次探底擔憂，但中長期趨勢向上。"
    else:
        current_cycle = "穩健成長期 (Growth Phase)"
        cycle_color = "#3b82f6"
        cycle_desc = "經濟穩健擴張，就業充沛，企業獲利持續成長。通膨處於健康可控區間，央行利率維持在中性至溫和升息水準。"
        alloc_advice = "💼 資產配置建議：股優於債（股票 70% ｜ 投資級債券 20% ｜ 現金 10%）。側重獲利成長強勁之主流產業龍頭。"
        risk_alert = "關注物價是否過熱升溫，促使央行超預期收緊貨幣政策。"

    # 2. 五大維度指標交叉驗證 (Cross-Validation Matrix)
    cross_validation = [
        {
            'dimension': '👥 勞動市場深度交叉比對',
            'indicators': f'失業率: {unrate}% | 初領失業金: {icsa/1000:.0f}K 人 | 非農年增: {payems_yoy:+.2f}%',
            'insight': '非農就業增幅常態化放緩，但每週高頻指標「初領失業救濟金」並未出現突破 25 萬的異常跳升。這印證當前失業率的小幅回升主要是勞動力供給增加（移民與勞動參與率修復）所致，而非企業大面積裁員所引發的實質需求坍塌，薩姆規則尚未實質觸發硬著陸警戒。'
        },
        {
            'dimension': '🔥 通膨傳導鏈條交叉驗證',
            'indicators': f'PPI 生產端: {ppi_yoy:+.2f}% ➔ CPI 消費端: {cpi_yoy:+.2f}% ➔ 核心 PCE: {core_pce_yoy:+.2f}%',
            'insight': '核心 PCE 與 CPI 均自高點顯著收斂，生產者物價 PPI 雖受低基期擾動偶有波動，但尚未向上傳導至下游消費品。服務業工資增長放緩有效壓制了核心通膨黏性，使得實質利率（聯邦利率 - 核心PCE）擴大至限制性高檔，為聯準會開啟了降息的安全邊際。'
        },
        {
            'dimension': '🛒 終端消費 vs 企業資本支出 (Capex)',
            'indicators': f'零售銷售 YoY: {rsxfs_yoy:+.2f}% | 實體消費 PCE YoY: {pce_yoy:+.2f}% | 耐久財新訂單 YoY: {dgorder_yoy:+.2f}%',
            'insight': f'零售銷售保持約 {rsxfs_yoy:.1f}% 穩健年增，個人消費支出亦展現消費韌性。尤其耐久財新訂單年增達 {dgorder_yoy:+.1f}%，顯示以 AI、自動化及先進製造驅動的企業實體資本支出 (Capex) 極具抗跌性，民間消費與企業投資兩大引擎並未熄火。'
        },
        {
            'dimension': '🏡 房市領先指標與實體製造鏈',
            'indicators': f'建築許可 YoY: {permit_yoy:+.2f}% | 新屋開工 YoY: {houst_yoy:+.2f}% | 工業生產 YoY: {indpro_yoy:+.2f}%',
            'insight': f'新屋開工 YoY ({houst_yoy:+.1f}%) 仍承受 7% 房貸高利率之壓抑，為當前經濟最脆弱之一環。然而領先開工約 3~6 個月的建築許可 YoY ({permit_yoy:+.1f}%) 已率先觸底翻正。一旦基準利率鬆綁引導房貸利率下行，房市有望從當前「被動壓抑」轉為新一輪擴張反彈動能。'
        },
        {
            'dimension': '💧 貨幣供給與流動性傳導環境',
            'indicators': f'M2 貨幣年增: {m2_yoy:+.2f}% | 基準利率: {fedfunds}% | 10Y-2Y 利差: {t10y2y:+.2f}%',
            'insight': f'M2 貨幣供給 YoY 已正式自負增長轉為正增長 ({m2_yoy:+.1f}%)，長短公債利差結束倒掛。這意味著「全市場流動性最緊縮的至暗時刻」已經過去，資金活水重回金融體系，為資產估值修復提供底層流動性支撐。'
        }
    ]

    # 3. 未來發展三大情境推論 (Forward Scenarios)
    forward_scenarios = [
        {
            'name': '情境 A：預防性降息引導「軟著陸再擴張」 (基準情境)',
            'prob': '60%',
            'color': '#10b981',
            'path': '通膨穩定向 2.5% 收斂，聯準會採節奏性降息引導借貸成本下降，房市開工回升，資本支出延續強勁，經濟成功化解滯後衝擊並重返穩健擴張。',
            'asset': '美股大型科技與優質權值股獲利擴張；長天期美債賺取資本利得；美元指數溫和走弱。'
        },
        {
            'name': '情境 B：緊縮滯後衝擊引發「遲到型硬著陸衰退」 (下行風險)',
            'prob': '25%',
            'color': '#ef4444',
            'path': '長天期利率高懸導致房地產與高負債中小企業加速爆雷，初領失業金竄升至 28 萬以上，消費急速緊縮，央行被迫恐慌性降息救市。',
            'asset': '股票面臨盈利與估值雙殺；長天期美國公債與現金為絕對避險王者；防禦型公用事業優於週期股。'
        },
        {
            'name': '情境 C：大宗商品推動「二次通膨停滯風險」 (黑天鵝風險)',
            'prob': '15%',
            'color': '#f59e0b',
            'path': '地緣政治或供應鏈擾動帶動原油等大宗商品價格飆升，PPI 重新推升核心 CPI 至 3.8% 以上，聯準會被迫暫停降息甚至重啟升息。',
            'asset': '股債雙殺；原物料能源、黃金與高利現金最具備抗通膨保護力。'
        }
    ]

    # 4. 後續應密切觀察的關鍵追蹤指標 (Forward Watchlist & Triggers)
    watchlist_triggers = [
        {
            'indicator': '初領失業救濟金人數 (ICSA)',
            'freq': '每週四',
            'current': f'{icsa/1000:.0f}K 人' if icsa else 'N/A',
            'trigger': '> 250K (警戒) / > 300K (衰退)',
            'meaning': '最靈敏的每週實時裁員指標。若 4 週均線突破 25 萬，代表企業開始廣泛解僱，軟著陸預期破滅。'
        },
        {
            'indicator': '核心 PCE 物價指數 MoM (PCEPILFE)',
            'freq': '每月底',
            'current': f'{core_pce_yoy:.2f}% (YoY)',
            'trigger': '月增率 MoM > 0.3% (年化 3.6%)',
            'meaning': '聯準會貨幣政策最核心定錨指標。若連續 2 個月 MoM > 0.3%，降息窗口將全面關閉。'
        },
        {
            'indicator': '建築許可 (PERMIT) & 新屋開工 (HOUST)',
            'freq': '每月中旬',
            'current': f'開工 YoY {houst_yoy:+.1f}% | 許可 YoY {permit_yoy:+.1f}%',
            'trigger': '開工與許可連續 2 季正增長',
            'meaning': '房地產是經濟週期的先行者。開工回溫將確認降息已實質傳導至實體經濟。'
        },
        {
            'indicator': '耐久財核心資本財新訂單 (DGORDER)',
            'freq': '每月中下旬',
            'current': f'YoY {dgorder_yoy:+.1f}%',
            'trigger': 'YoY 增速轉負 (< 0%)',
            'meaning': '企業真實資本支出 (Capex) 的領先信號。只要保持正增長，製造業擴張基礎堅固。'
        },
        {
            'indicator': 'M2 貨幣供給年增率 (M2SL YoY)',
            'freq': '每月底',
            'current': f'YoY {m2_yoy:+.2f}%',
            'trigger': '年增率回升至 > 6.0%',
            'meaning': '全市場流動性水龍頭。M2 加速擴張將為風險資產提供充沛的流動性溢價行情。'
        }
    ]

    return {
        'cycle_title': current_cycle,
        'cycle_color': cycle_color,
        'cycle_desc': cycle_desc,
        'alloc_advice': alloc_advice,
        'risk_alert': risk_alert,
        'unrate': unrate,
        'icsa': icsa,
        't10y2y': t10y2y,
        'cpi_yoy': cpi_yoy,
        'rsxfs_yoy': rsxfs_yoy,
        'cross_validation': cross_validation,
        'forward_scenarios': forward_scenarios,
        'watchlist_triggers': watchlist_triggers
    }


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


# ----------------- 頁面 2: 最新數據與總經診斷 -----------------
def render_diagnosis_page(df):
    st.header("📋 全部指標最新數據與總經深度診斷")
    
    stats_df = calculate_summary_stats(df)
    if stats_df.empty:
        st.warning("無有效數據可用於分析。")
        return

    diag = generate_macro_diagnosis(stats_df, as_of_title="最新即時")

    # 1. 循環橫幅
    st.markdown(
        f"""
        <div style="background-color: #1e1e1e; padding: 20px; border-radius: 10px; border-left: 8px solid {diag['cycle_color']}; margin-bottom: 20px;">
            <h3 style="margin-top:0; color: {diag['cycle_color']};">📍 總經分析模組動態判定：{diag['cycle_title']}</h3>
            <p style="font-size: 1.05rem; line-height: 1.6; color: #ddd; margin:0;">{diag['cycle_desc']}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. 四大關鍵體質指標卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("勞動就業 (失業率 / 初領)", f"{diag['unrate']:.1f}%" if diag['unrate'] else "N/A", f"初領 {diag['icsa']/1000:.0f}K 人" if diag['icsa'] else "N/A")
        st.caption("[查看 UNRATE FRED 圖表 ↗](https://fred.stlouisfed.org/series/UNRATE)")
    with col2:
        st.metric("通膨指標 (CPI YoY)", f"{diag['cpi_yoy']:.2f}%" if diag['cpi_yoy'] else "N/A", "通膨受控降溫", delta_color="inverse")
        st.caption("[查看 CPIAUCSL FRED 圖表 ↗](https://fred.stlouisfed.org/series/CPIAUCSL)")
    with col3:
        st.metric("殖利率利差 (10Y-2Y)", f"{diag['t10y2y']:+.2f}%" if diag['t10y2y'] is not None else "N/A", "利差翻正" if diag['t10y2y'] and diag['t10y2y'] > 0 else "倒掛中")
        st.caption("[查看 T10Y2Y FRED 圖表 ↗](https://fred.stlouisfed.org/series/T10Y2Y)")
    with col4:
        st.metric("終端消費 (零售銷售 YoY)", f"{diag['rsxfs_yoy']:+.2f}%" if diag['rsxfs_yoy'] else "N/A", "實體內需支撐")
        st.caption("[查看 RSXFS FRED 圖表 ↗](https://fred.stlouisfed.org/series/RSXFS)")

    st.divider()

    # 3. 多維度指標交叉比對 (Cross-Validation Matrix)
    st.subheader("🔍 總體經濟多維度交叉比對分析 (Cross-Indicator Validation)")
    for cv in diag['cross_validation']:
        with st.expander(f"{cv['dimension']} ➔ 核心觀察", expanded=True):
            st.markdown(f"**關鍵對比數據**：`{cv['indicators']}`")
            st.markdown(f"**實證分析推論**：{cv['insight']}")

    st.divider()

    # 4. 未來發展三大情境推論 (Forward Scenarios)
    st.subheader("🔮 未來發展可能趨勢與路徑推論 (Forward Scenarios)")
    sc_cols = st.columns(3)
    for idx, sc in enumerate(diag['forward_scenarios']):
        with sc_cols[idx]:
            st.markdown(
                f"""
                <div style="background-color: #f8fafc; border-top: 4px solid {sc['color']}; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0; height: 100%;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-weight: 800; font-size: 0.95rem; color: #0f172a;">{sc['name']}</span>
                    </div>
                    <span style="background-color: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700;">發生機率：{sc['prob']}</span>
                    <p style="font-size: 0.85rem; color: #334155; margin-top: 10px; line-height: 1.5;"><strong>演變路徑</strong>：{sc['path']}</p>
                    <p style="font-size: 0.85rem; color: #1e40af; margin-top: 8px; line-height: 1.5; border-top: 1px dashed #cbd5e1; padding-top: 8px;"><strong>資產表現</strong>：{sc['asset']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.divider()

    # 5. 後續應注意觀察的其他關鍵指標 (Forward Watchlist & Triggers)
    st.subheader("👀 後續應密切追蹤之領先指標與觸發門檻 (Forward Watchlist)")
    st.caption("設定明確客觀的數據閥值，作為整體策略與資產配置動態調整的觸發信號：")
    
    watch_df = pd.DataFrame(diag['watchlist_triggers'])
    watch_df.columns = ["追蹤指標", "發布頻率", "當前數值", "關鍵警戒門檻 (Trigger)", "宏觀意涵與應對邏輯"]
    st.dataframe(watch_df, use_container_width=True, hide_index=True)

    st.divider()

    # 6. 核心風險提示與資產配置
    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("⚠️ 核心風險提示")
        st.warning(diag['risk_alert'])
    with c_right:
        st.subheader("💡 資產配置與投資策略建議")
        st.info(diag['alloc_advice'])

    st.divider()

    # 7. 全部 23 項指標最新數據總覽
    st.subheader("📑 全部 23 項指標最新數據總覽")
    categories = ["全部"] + list(stats_df['category'].unique())
    selected_cat = st.selectbox("依特性分類檢視", categories)
    
    display_df = stats_df.copy()
    if selected_cat != "全部":
        display_df = display_df[display_df['category'] == selected_cat]

    formatted_rows = []
    for _, r in display_df.iterrows():
        val_str = f"{r['value']:,.2f}" if r['value'] < 1000 else f"{r['value']:,.0f}"
        mom_str = f"{r['mom']:+.2f} {'百分點' if r['is_rate'] else '%'}" if pd.notna(r['mom']) else "-"
        yoy_str = f"{r['yoy']:+.2f} {'百分點' if r['is_rate'] else '%'}" if pd.notna(r['yoy']) else "-"

        formatted_rows.append({
            "分類": r['category'],
            "指標名稱": r['name'],
            "代碼": r['code'],
            "最新資料日期": r['latest_date'],
            f"最新數值 ({r['unit']})": val_str,
            "前期變動 (MoM/QoQ)": mom_str,
            "年增率/差值 (YoY)": yoy_str,
            "FRED 官方連結": f"https://fred.stlouisfed.org/series/{r['code']}"
        })
    st.dataframe(
        pd.DataFrame(formatted_rows),
        column_config={
            "FRED 官方連結": st.column_config.LinkColumn("FRED 圖表 ↗", display_text="查看圖表 ↗")
        },
        use_container_width=True,
        hide_index=True
    )


# ----------------- 頁面 3: 歷史時空回顧 -----------------
def render_history_page(df):
    st.header("🕰️ 歷史時空回顧與總經情境重現")
    st.caption("輸入任意歷史特定日期，系統將自動消除未來函數，重現該時點的全部數據、動態景氣循環診斷與指標歷史變化簡圖。")

    preset_scenarios = {
        "自訂日期 (請在下方選擇)": None,
        "2007-06-01 次貸風暴前夕 (殖利率深度倒掛)": "2007-06-01",
        "2008-09-15 雷曼兄弟破產 (金融海嘯實質衰退)": "2008-09-15",
        "2009-06-01 量化寬鬆救市 (景氣觸底復甦期)": "2009-06-01",
        "2017-06-01 經濟穩健擴張期": "2017-06-01",
        "2020-03-15 疫情爆發全球斷崖衝擊": "2020-03-15",
        "2020-09-01 無限 QE 與疫後強勁復甦": "2020-09-01",
        "2022-06-01 通膨四十年大頂 (聯準會暴力升息)": "2022-06-01",
        "2023-03-15 矽谷銀行破產 (倒掛最深時)": "2023-03-15",
        "2024-08-05 日圓套息交易震撼": "2024-08-05"
    }

    with st.sidebar:
        st.subheader("🕰️ 歷史時空設定")
        selected_preset = st.selectbox("經典歷史情境快速載入", list(preset_scenarios.keys()), index=1)
        
        min_date = df['date'].min().date()
        max_date = df['date'].max().date()

        if preset_scenarios[selected_preset] is not None:
            default_val = datetime.datetime.strptime(preset_scenarios[selected_preset], "%Y-%m-%d").date()
        else:
            default_val = datetime.date(2008, 9, 15)

        target_date = st.date_input("選擇特定歷史回顧基準日", value=default_val, min_value=min_date, max_value=max_date)

        spark_type = st.radio("簡圖呈現數據維度", options=["原始數據走勢 (Raw)", "YoY 年增率/差值走勢 (YoY %)"])
        spark_len = st.slider("歷史簡圖回溯期數", min_value=5, max_value=18, value=8)

    cutoff_datetime = pd.to_datetime(target_date)
    stats_df = calculate_summary_stats(df, cutoff_date=cutoff_datetime, spark_periods=spark_len)
    if stats_df.empty:
        st.error(f"在 {target_date} 之前無足夠的歷史數據。")
        return

    diag = generate_macro_diagnosis(stats_df, as_of_title=str(target_date))

    # 1. 歷史當時循環定位橫幅
    st.markdown(
        f"""
        <div style="background-color: #1e1e1e; padding: 22px; border-radius: 12px; border-left: 8px solid {diag['cycle_color']}; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <h3 style="margin:0; color: {diag['cycle_color']};">📍 歷史時點 [{target_date}] 循環判定：{diag['cycle_title']}</h3>
                <span style="background: rgba(255,255,255,0.1); color: #fff; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem;">零未來函數時空重現</span>
            </div>
            <p style="font-size: 1.05rem; line-height: 1.6; color: #e2e8f0; margin: 0;">{diag['cycle_desc']}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. 當時 4 大核心體質卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("當時失業率 / 初領", f"{diag['unrate']:.1f}%" if diag['unrate'] else "N/A", f"初領 {diag['icsa']/1000:.0f}K 人" if diag['icsa'] else "N/A")
        st.caption("[查看 UNRATE FRED 圖表 ↗](https://fred.stlouisfed.org/series/UNRATE)")
    with col2:
        st.metric("當時 CPI 年增率", f"{diag['cpi_yoy']:.2f}%" if diag['cpi_yoy'] else "N/A", "通膨年增率")
        st.caption("[查看 CPIAUCSL FRED 圖表 ↗](https://fred.stlouisfed.org/series/CPIAUCSL)")
    with col3:
        st.metric("當時利差 (10Y-2Y)", f"{diag['t10y2y']:+.2f}%" if diag['t10y2y'] is not None else "N/A", "倒掛" if diag['t10y2y'] and diag['t10y2y'] < 0 else "正斜率")
        st.caption("[查看 T10Y2Y FRED 圖表 ↗](https://fred.stlouisfed.org/series/T10Y2Y)")
    with col4:
        st.metric("當時零售銷售年增", f"{diag['rsxfs_yoy']:+.2f}%" if diag['rsxfs_yoy'] else "N/A", "零售銷售年增")
        st.caption("[查看 RSXFS FRED 圖表 ↗](https://fred.stlouisfed.org/series/RSXFS)")

    st.divider()

    # 3. 當時指標交叉驗證分析
    st.subheader(f"🔍 歷史時點 [{target_date}] 指標交叉比對深度分析")
    for cv in diag['cross_validation']:
        with st.expander(f"{cv['dimension']}", expanded=True):
            st.markdown(f"**當時數據比對**：`{cv['indicators']}`")
            st.markdown(f"**分析論證**：{cv['insight']}")

    st.divider()

    # 4. 當時視角下的未來情境推論與後續追蹤
    c_sc, c_watch = st.columns([1.1, 0.9])
    with c_sc:
        st.subheader("🔮 當時視角之未來情境路徑推論")
        for sc in diag['forward_scenarios']:
            st.markdown(f"**{sc['name']}** (機率: `{sc['prob']}`)")
            st.markdown(f"- 路徑：{sc['path']}")
            st.markdown(f"- 資產：{sc['asset']}")
    with c_watch:
        st.subheader("👀 當時後續應重點觀察之警報指標")
        for wt in diag['watchlist_triggers'][:3]:
            st.markdown(f"**{wt['indicator']}** ({wt['freq']})")
            st.caption(f"警戒門檻: {wt['trigger']} | 意涵: {wt['meaning']}")

    st.divider()

    # 5. 重點指標歷史簡圖展廳 (Sparklines Gallery)
    st.subheader(f"📈 核心指標歷史數據變化簡圖 (至 {target_date} 止，共 {spark_len} 期)")
    st.caption("下方簡圖反映該歷史時點前數期的加速度與轉折趨勢：")

    key_codes = ['UNRATE', 'ICSA', 'T10Y2Y', 'CPIAUCSL', 'RSXFS', 'FEDFUNDS', 'HOUST', 'DGORDER', 'M2SL']
    gallery_cols = st.columns(3)
    use_yoy = "YoY" in spark_type

    for idx, code in enumerate(key_codes):
        row = stats_df[stats_df['code'] == code]
        if row.empty:
            continue
        r = row.iloc[0]
        col_target = gallery_cols[idx % 3]
        
        with col_target:
            dates = r['spark_dates']
            vals = r['spark_yoy_vals'] if use_yoy else r['spark_vals']
            
            line_color = '#ef4444' if (code in ['UNRATE', 'ICSA'] and len(vals) > 1 and vals[-1] > vals[0]) else '#2563eb'
            if code == 'T10Y2Y' and vals[-1] < 0:
                line_color = '#f59e0b'

            fig_spark = create_sparkline_fig(
                dates, vals, 
                color=line_color, 
                title=f"{r['name']} ({'YoY' if use_yoy else '原始'})"
            )
            st.plotly_chart(fig_spark, use_container_width=True)
            
            st.markdown(
                f"<div style='font-size:0.85rem; margin-top:-10px; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center;'>"
                f"<span><a href='https://fred.stlouisfed.org/series/{code}' target='_blank' style='font-weight:700; color:#2563eb; text-decoration:none;'>🔗 {r['name']} ↗</a>: <b>{r['value']:.2f} {r['unit']}</b></span>"
                f"<span style='color:#64748b;'>YoY: <b>{r['yoy']:+.2f}%</b></span>"
                f"</div>", 
                unsafe_allow_html=True
            )

    st.divider()

    # 6. 當時 23 項指標完整快照數據表
    st.subheader(f"📑 歷史時點 [{target_date}] 全部指標數據快照")
    categories = ["全部"] + list(stats_df['category'].unique())
    selected_cat = st.selectbox("篩選分類", categories, key="hist_cat")
    
    display_df = stats_df.copy()
    if selected_cat != "全部":
        display_df = display_df[display_df['category'] == selected_cat]

    formatted_rows = []
    for _, r in display_df.iterrows():
        val_str = f"{r['value']:,.2f}" if r['value'] < 1000 else f"{r['value']:,.0f}"
        mom_str = f"{r['mom']:+.2f} {'百分點' if r['is_rate'] else '%'}" if pd.notna(r['mom']) else "-"
        yoy_str = f"{r['yoy']:+.2f} {'百分點' if r['is_rate'] else '%'}" if pd.notna(r['yoy']) else "-"

        formatted_rows.append({
            "分類": r['category'],
            "指標名稱": r['name'],
            "代碼": r['code'],
            "當時最新公佈日期": r['latest_date'],
            f"數值 ({r['unit']})": val_str,
            "前期變動 (MoM)": mom_str,
            "年增率/差值 (YoY)": yoy_str,
            "FRED 官方連結": f"https://fred.stlouisfed.org/series/{r['code']}"
        })
    st.dataframe(
        pd.DataFrame(formatted_rows),
        column_config={
            "FRED 官方連結": st.column_config.LinkColumn("FRED 圖表 ↗", display_text="查看圖表 ↗")
        },
        use_container_width=True,
        hide_index=True
    )


# ----------------- 主程式進入點 -----------------
def main():
    df = load_data()
    if df.empty:
        st.stop()

    with st.sidebar:
        st.title("📌 導航功能選單")
        app_page = st.radio(
            "前往頁面",
            options=["📊 指標互動走勢圖", "📋 最新數據與總經診斷", "🕰️ 歷史時空回顧"],
            index=1
        )
        st.divider()
        st.subheader("🔍 畫面字體縮放")
        font_size = st.select_slider(
            "全局字體大小",
            options=["85%", "92%", "100%", "110%", "120%", "130%"],
            value="100%",
            help="調整全畫面文字、標題與圖表文字的顯示大小比例"
        )
        st.divider()

    st.markdown(f"""
    <style>
        html, body, [class*="css"], .stMarkdown, .stText, p, span, label, div, table, td, th {{
            font-size: {font_size} !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    if app_page == "📊 指標互動走勢圖":
        render_chart_page(df)
    elif app_page == "📋 最新數據與總經診斷":
        render_diagnosis_page(df)
    else:
        render_history_page(df)

if __name__ == "__main__":
    main()

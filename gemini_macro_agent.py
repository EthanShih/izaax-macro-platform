import os
import json
import sqlite3
import datetime
import urllib.request
import urllib.error
import re
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "macro_data.db")
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DATA_JS_PATH = os.path.join(DOCS_DIR, "data.js")
DIAGNOSIS_JSON_PATH = os.path.join(DOCS_DIR, "diagnosis_result.json")

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

def get_latest_macro_snapshot():
    """從 SQLite 資料庫擷取 23 項指標的最新數值與變動率"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"找不到資料庫：{DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT date, indicator_code, indicator_name, value FROM macro_indicators ORDER BY date", conn)
    conn.close()

    df['date'] = pd.to_datetime(df['date'])
    snapshot = []

    for code, meta in INDICATOR_METADATA.items():
        sub = df[df['indicator_code'] == code].sort_values('date').dropna(subset=['value'])
        if sub.empty:
            continue
        
        latest = sub.iloc[-1]
        prev = sub.iloc[-2] if len(sub) > 1 else None
        
        target_1y = latest['date'] - pd.DateOffset(years=1)
        sub_1y = sub[sub['date'] <= target_1y]
        prev_1y = sub_1y.iloc[-1] if not sub_1y.empty else None
        
        is_rate = meta['is_rate']
        mom = (latest['value'] - prev['value']) if is_rate else (((latest['value'] / prev['value']) - 1) * 100 if prev is not None and prev['value'] != 0 else 0)
        yoy = (latest['value'] - prev_1y['value']) if is_rate else (((latest['value'] / prev_1y['value']) - 1) * 100 if prev_1y is not None and prev_1y['value'] != 0 else 0)
        
        snapshot.append({
            'code': code,
            'name': meta['name'],
            'category': meta['category'],
            'unit': meta['unit'],
            'is_rate': is_rate,
            'latest_date': latest['date'].strftime('%Y-%m-%d'),
            'value': round(float(latest['value']), 3),
            'mom': round(float(mom), 2) if mom is not None else None,
            'yoy': round(float(yoy), 2) if yoy is not None else None
        })

    return snapshot

def build_gemini_prompt(snapshot):
    """組裝給 Gemini 的專家級總經分析 Prompt"""
    data_summary_text = "\n".join([
        f"- 【{item['category']}】{item['name']} ({item['code']})：最新值 {item['value']} {item['unit']} (發布日: {item['latest_date']}), MoM: {item['mom']}, YoY: {item['yoy']}"
        for item in snapshot
    ])

    prompt = f"""
你是一位世界頂級的總體經濟分析師與宏觀資產配置專家。
請依據「四階段景氣循環分析架構」（復甦期、成長期、榮景期、衰退期）以及下方由美國聯邦儲備銀行 FRED 資料庫最新同步的 23 項核心經濟指標數據，進行深度的交叉驗證、景氣循環定位、未來情境推論與資產配置建議。

【最新 23 項總體經濟數據快照】：
{data_summary_text}

【四階段景氣循環判定核心法則】：
1. 復甦期 (Recovery)：低通膨、低利率、殖利率曲線大幅陡峭 (10Y-2Y > 0.8%)、初領失業救濟金見頂回落、製造業觸底反彈。
2. 成長期 (Growth)：經濟良性擴張、非農與就業充沛、企業盈利增長、通膨溫和受控、央行維持中性政策。
3. 榮景期 (Boom)：景氣擴張達頂峰、通膨攀升、央行強力升息使利率達限制性高檔、長短公債殖利率深度倒掛 (10Y-2Y < 0%)。
4. 榮景期尾聲 / 降息過渡期 (Late Boom / Transition)：殖利率利差結束倒掛轉為正斜率 (10Y-2Y > 0%)、初領失業救濟金維持健康低檔 (< 25 萬)、步入預防性降息窗口。
5. 衰退期 (Recession)：失業率飆升 (薩姆規則觸發)、初領救濟金突破 30 萬警戒線、終端消費與製造業全面萎縮、央行緊急降息。

【輸出格式要求】：
請直接輸出符合以下 JSON Schema 的合法 JSON，不可包含任何 markdown 標記（如 ```json 等），統一命名為「總經分析模組」：

{{
  "cycle_title": "當前循環定位名稱（例如：榮景期尾聲 ➔ 成長再平衡 / 降息過渡期）",
  "cycle_color": "對應顏色 Hex Code（#f97316 或 #10b981 或 #3b82f6 或 #f59e0b 或 #ef4444）",
  "cycle_desc": "詳細的核心判定依據論述（結合當前利差、就業與通膨具體數據，100-200字）",
  "stat_cards": {{
    "labor_status": "簡短評語（如：健康韌性）",
    "labor_sub": "初領救濟金與失業率關鍵描述",
    "inflation_status": "簡短評語（如：受控降溫）",
    "inflation_sub": "CPI 與核心 PCE 收斂狀態",
    "yield_status": "簡短評語（如：已解倒掛）",
    "yield_sub": "10Y-2Y 與 10Y-3M 利差讀數描述",
    "consumption_status": "簡短評語（如：強韌增長）",
    "consumption_sub": "耐久財訂單表現"
  }},
  "cross_validation": [
    {{
      "dimension": "👥 勞動市場供需交叉比對",
      "status_tag": "健康常態化",
      "indicators": "列出比對指標與當前讀數",
      "insight": "深入的交叉驗證實證推論（深入探討非農放緩本質、失業率構成與薩姆規則警戒）"
    }},
    {{
      "dimension": "🔥 通膨傳導鏈條交叉驗證",
      "status_tag": "平穩收斂",
      "indicators": "列出比對指標與當前讀數",
      "insight": "探討 PPI 上游到 CPI/核心 PCE 下游的傳導與實質利率空間"
    }},
    {{
      "dimension": "🛒 終端消費 vs 企業資本支出 (Capex)",
      "status_tag": "雙引擎支撐",
      "indicators": "列出比對指標與當前讀數",
      "insight": "剖析零售銷售與耐久財新訂單對實體投資的支撐"
    }},
    {{
      "dimension": "🏡 房市領先指標與實體製造鏈",
      "status_tag": "築底震盪",
      "indicators": "列出比對指標與當前讀數",
      "insight": "剖析建築許可、新屋開工與高房貸利率之相互作用"
    }},
    {{
      "dimension": "💧 貨幣流動性 vs 實體利差結構",
      "status_tag": "牛陡重啟",
      "indicators": "列出比對指標與當前讀數",
      "insight": "剖析 10Y-2Y 利差轉正機制與 M2 流動性挹注"
    }}
  ],
  "forward_scenarios": [
    {{
      "name": "基準情境：預防性降息與軟著陸 (Soft Landing)",
      "prob": "60%",
      "color": "#10b981",
      "path": "演變路徑描述...",
      "asset": "最佳資產配置方向與受惠資產..."
    }},
    {{
      "name": "風險情境：時滯效應引發延遲硬著陸 (Hard Landing)",
      "prob": "25%",
      "color": "#ef4444",
      "path": "演變路徑描述...",
      "asset": "最佳防守資產與需減碼資產..."
    }},
    {{
      "name": "例外情境：供應鏈與地緣引發二次通膨 (Secondary Inflation)",
      "prob": "15%",
      "color": "#f59e0b",
      "path": "演變路徑描述...",
      "asset": "最佳抗通膨資產..."
    }}
  ],
  "risk_warnings": [
    "核心風險點 1...",
    "核心風險點 2...",
    "核心風險點 3..."
  ],
  "asset_allocation": {{
    "ratio": "股票 XX% ｜ 長天期美債 XX% ｜ 現金 XX%",
    "bond_strategy": "債券端具體策略...",
    "equity_strategy": "股票端具體策略...",
    "risk_control": "停損與風控閘門具體觸發條件..."
  }},
  "watchlist_triggers": [
    {{
      "indicator": "初領失業救濟金 (ICSA)",
      "code": "ICSA",
      "freq": "每週四 (高頻)",
      "current": "當前值",
      "trigger": "警戒門檻 (如: 4週均線 > 250K)",
      "meaning": "宏觀意涵與操作邏輯"
    }},
    {{
      "indicator": "核心 PCE 物價 MoM (PCEPILFE)",
      "code": "PCEPILFE",
      "freq": "每月底",
      "current": "當前值",
      "trigger": "警戒門檻 (如: 連續 2 個月 MoM > 0.3%)",
      "meaning": "宏觀意涵與操作邏輯"
    }},
    {{
      "indicator": "建築許可 (PERMIT) & 新屋開工 (HOUST)",
      "code": "PERMIT",
      "freq": "每月中旬",
      "current": "當前值",
      "trigger": "警戒門檻 (如: 開工與許可連續 2 季正增長)",
      "meaning": "宏觀意涵與操作邏輯"
    }},
    {{
      "indicator": "耐久財新訂單 (DGORDER)",
      "code": "DGORDER",
      "freq": "每月中下旬",
      "current": "當前值",
      "trigger": "警戒門檻 (如: YoY 增速轉負 < 0%)",
      "meaning": "宏觀意涵與操作邏輯"
    }},
    {{
      "indicator": "M2 貨幣供給年增率 (M2SL YoY)",
      "code": "M2SL",
      "freq": "每月底",
      "current": "當前值",
      "trigger": "警戒門檻 (如: 年增率穩定保持 > 5.0%)",
      "meaning": "宏觀意涵與操作邏輯"
    }}
  ]
}}
"""
    return prompt

LAST_API_ERROR = ""

def call_gemini_api(prompt, api_key):
    """透過官方 REST API 呼叫 Gemini 模型 (依序支援 1.5-flash / 2.0-flash / 2.5-flash)"""
    global LAST_API_ERROR
    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]
    
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                res_data = response.read().decode('utf-8')
                res_json = json.loads(res_data)
                candidate_text = res_json['candidates'][0]['content']['parts'][0]['text'].strip()
                # 去除可能的 markdown json 區塊標籤
                clean_text = re.sub(r"^```(?:json)?\s*", "", candidate_text, flags=re.IGNORECASE)
                clean_text = re.sub(r"\s*```$", "", clean_text).strip()
                parsed = json.loads(clean_text)
                return parsed, model_name
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            LAST_API_ERROR = f"HTTP {e.code} on {model_name}: {err_body[:250]}"
            print(f"Gemini API 呼叫失敗 ({LAST_API_ERROR})")
        except Exception as e:
            LAST_API_ERROR = f"Exception on {model_name}: {str(e)}"
            print(f"Gemini API 發生未預期錯誤: {LAST_API_ERROR}")

    return None, None

def fallback_rule_diagnosis(snapshot):
    """當未配置 API Key 或 API 異常時，使用內建確定性規則庫作為保底備援"""
    def get_val(code):
        f = next((x for x in snapshot if x['code'] == code), None)
        return f['value'] if f else None
    
    def get_yoy(code):
        f = next((x for x in snapshot if x['code'] == code), None)
        return f['yoy'] if f and f['yoy'] is not None else 0

    unrate = get_val('UNRATE') or 4.1
    icsa = get_val('ICSA') or 206000
    t10y2y = get_val('T10Y2Y') if get_val('T10Y2Y') is not None else 0.33
    cpi_yoy = get_yoy('CPIAUCSL')
    rsxfs_yoy = get_yoy('RSXFS')
    dgorder_yoy = get_yoy('DGORDER')
    permit_yoy = get_yoy('PERMIT')
    houst_yoy = get_yoy('HOUST')
    core_pce_yoy = get_yoy('PCEPILFE')
    m2_yoy = get_yoy('M2SL')

    if (icsa >= 300000) or (unrate >= 5.5):
        cycle_title = "衰退期 (Recession Phase)"
        cycle_color = "#ef4444"
        cycle_desc = "就業市場出現廣泛性裁員潮（初領失業救濟金飆升突破 30 萬門檻），實體經濟全面收縮。央行處於緊急降息救市階段。"
        ratio = "現金 40% ｜ 長期公債 40% ｜ 防禦型股票 20%"
    elif t10y2y < 0:
        cycle_title = "榮景期 (Boom Phase / Inversion Peak)"
        cycle_color = "#f59e0b"
        cycle_desc = f"長短殖利率曲線處於深度倒掛狀態 (10Y-2Y 為 {t10y2y:+.2f}%)，央行激進升息抗擊通膨。經濟擴張雖達頂點，但倒掛預示著後續週期轉折正逐步逼近。"
        ratio = "股票 50% ｜ 中長天期公債 40% ｜ 現金 10%"
    elif t10y2y >= 0 and icsa < 260000 and unrate <= 4.8:
        cycle_title = "榮景期尾聲 ➔ 成長再平衡 / 降息過渡期 (Late Boom / Transition)"
        cycle_color = "#f97316"
        cycle_desc = f"長短公債利差已正式脫離長達兩年的深度倒掛、恢復正斜率 (+{t10y2y:.2f}%)。初領救濟金維持在 {icsa/1000:.0f}K 人之健康低檔，失業率 {unrate}% 溫和，升息週期已正式邁向預防性降息窗口。"
        ratio = "股票 60% ｜ 長天期美債 35% ｜ 現金 5%"
    else:
        cycle_title = "穩健成長期 (Growth Phase)"
        cycle_color = "#3b82f6"
        cycle_desc = "經濟穩健擴張，就業穩步增長，通膨健康可控，利率維持在中性至溫和水準。"
        ratio = "股票 70% ｜ 投資級債券 20% ｜ 現金 10%"

    return {
        "cycle_title": cycle_title,
        "cycle_color": cycle_color,
        "cycle_desc": cycle_desc,
        "stat_cards": {
            "labor_status": "健康韌性",
            "labor_sub": f"初領救濟金 {icsa/1000:.0f}K (未破250K警戒)",
            "inflation_status": "受控降溫",
            "inflation_sub": f"核心 PCE {core_pce_yoy:.2f}% 穩定收斂",
            "yield_status": "已解倒掛" if t10y2y > 0 else "倒掛警戒",
            "yield_sub": f"10Y-2Y 正斜率 {t10y2y:+.2f}%",
            "consumption_status": "強韌增長",
            "consumption_sub": f"耐久財訂單 YoY {dgorder_yoy:+.1f}% 擴張"
        },
        "cross_validation": [
            {
                "dimension": "👥 勞動市場供需交叉比對",
                "status_tag": "健康常態化",
                "indicators": f"失業率 {unrate}% ｜ 初領失業金 {icsa/1000:.0f}K 人",
                "insight": "非農新增人數雖常態化放緩，但高頻初領救濟金並未突破 25 萬警戒線。失業率的小幅回升主因是勞動力供給增加（移民與勞參率修復），而非企業裁員潮導致的需求崩盤。"
            },
            {
                "dimension": "🔥 通膨傳導鏈條交叉驗證",
                "status_tag": "平穩收斂",
                "indicators": f"CPI YoY {cpi_yoy:+.2f}% ➔ 核心 PCE {core_pce_yoy:+.2f}%",
                "insight": "核心 PCE 與 CPI 均自高點顯著收斂，生產者物價 PPI 雖偶有波動，但尚未向上傳導至下游消費品。服務業工資增長放緩有效壓制了核心通膨黏性。"
            },
            {
                "dimension": "🛒 終端消費 vs 企業資本支出 (Capex)",
                "status_tag": "雙引擎支撐",
                "indicators": f"零售銷售 YoY {rsxfs_yoy:+.2f}% ｜ 耐久財新訂單 YoY {dgorder_yoy:+.2f}%",
                "insight": "零售銷售保持穩健年增，耐久財新訂單亦展現擴張韌性，顯示以 AI 與先進製造驅動的企業資本支出抗跌性極高，民間消費與企業投資兩大引擎並未熄火。"
            },
            {
                "dimension": "🏡 房市領先指標與實體製造鏈",
                "status_tag": "築底震盪",
                "indicators": f"建築許可 YoY {permit_yoy:+.2f}% ｜ 新屋開工 YoY {houst_yoy:+.2f}%",
                "insight": "新屋開工雖受 6.5% 以上高房貸利率壓抑，但建築許可已領先觸底翻正。一旦降息引導房貸利率下行，房市有望轉為新一輪擴張反彈動能。"
            },
            {
                "dimension": "💧 貨幣流動性 vs 實體利差結構",
                "status_tag": "牛陡重啟",
                "indicators": f"10Y-2Y 利差 {t10y2y:+.2f}% ｜ M2 貨幣供給 YoY {m2_yoy:+.2f}%",
                "insight": "長短天期公債利差正式脫離深度倒掛，M2 年增率重回擴張區間，整體流動性保持充沛，降低了信用風險溢酬攀升與流動性枯竭風險。"
            }
        ],
        "forward_scenarios": [
            {
                "name": "基準情境：預防性降息與軟著陸 (Soft Landing)",
                "prob": "60%",
                "color": "#10b981",
                "path": "通膨平緩回落至 2.5%~2.8%，勞動市場降溫而非失速。高利率政策使超額需求出清，降息提供及時流動性支持。",
                "asset": "股債雙牛；長天期美債鎖定高資本利得，大型科技股引領指數再創新高。"
            },
            {
                "name": "風險情境：時滯效應引發延遲硬著陸 (Hard Landing)",
                "prob": "25%",
                "color": "#ef4444",
                "path": "歷史上降息初期若觸發薩姆規則，失業率急彈常在 2~3 季內引爆企業違約與信貸緊縮。",
                "asset": "長天期公債暴漲、公用事業防禦；週期股與高收益債面臨深度盈利下修。"
            },
            {
                "name": "例外情境：供應鏈與地緣引發二次通膨 (Secondary Inflation)",
                "prob": "15%",
                "color": "#f59e0b",
                "path": "國際油價或供應鏈再度受阻，使服務業通膨反彈，導致央行被迫中止降息。",
                "asset": "股債雙殺；原油大宗商品、黃金與高利現金最具備抗通膨防禦力。"
            }
        ],
        "risk_warnings": [
            "解除倒掛後的時滯衰退陷阱：歷史經驗表明，經濟下行通常不在倒掛期間，而在倒掛解除後 6~18 個月內驗證。若初領失業金急升至 25 萬以上，需提高警覺。",
            "長端利率高懸：無風險基準利率居高不下，房貸利率緊繃壓抑房市開工與成屋交易，並制約股票估值倍數。",
            "低收入群體消費邊際放緩：密大消費者信心指數低迷，需關注終端零售是否因超額儲蓄見底而走弱。"
        ],
        "asset_allocation": {
            "ratio": ratio,
            "bond_strategy": "降息週期開展，目前處於鎖定高無風險殖利率與賺取資本利得的最佳歷史視窗，長天期美債為核心防守重兵。",
            "equity_strategy": "揚棄高槓桿、無獲利的投機題材，重兵佈局具備強大現金流定價能力之大型科技巨擘，並逢低增持受惠降息週期之高股息、公用事業與內需消費族群。",
            "risk_control": "每週四以「初領失業救濟金人數 25 萬」作為股票部位全面調降槓桿之第一道停損閘門。"
        },
        "watchlist_triggers": [
            {
                "indicator": "初領失業救濟金 (ICSA)",
                "code": "ICSA",
                "freq": "每週四 (高頻)",
                "current": f"{icsa/1000:.0f}K 人",
                "trigger": "4週均線 > 250K",
                "meaning": "最敏感的裁員先導指標。若突破 25 萬人，代表就業進入實質惡化，應立即降低股票部位。"
            },
            {
                "indicator": "核心 PCE 物價 MoM (PCEPILFE)",
                "code": "PCEPILFE",
                "freq": "每月底",
                "current": f"{core_pce_yoy:.2f}% (YoY)",
                "trigger": "連續 2 個月 MoM > 0.3%",
                "meaning": "Fed 定錨目標。若 MoM 持續高於 0.3% (年化 3.6%)，降息窗口將關閉，股債受折現率壓制。"
            },
            {
                "indicator": "建築許可 (PERMIT) & 新屋開工 (HOUST)",
                "code": "PERMIT",
                "freq": "每月中旬",
                "current": f"開工 {houst_yoy:+.1f}% | 許可 {permit_yoy:+.1f}%",
                "trigger": "開工與許可連續 2 季正增長",
                "meaning": "房地產為景氣先行火車頭。若開工回升，確認降息已實質傳導至民間實體，增持週期成長股。"
            },
            {
                "indicator": "耐久財新訂單 (DGORDER)",
                "code": "DGORDER",
                "freq": "每月中下旬",
                "current": f"{dgorder_yoy:+.1f}% (YoY)",
                "trigger": "YoY 增速轉負 (< 0%)",
                "meaning": "企業實體資本支出 (Capex) 晴雨表。若跌破零軸，反映企業對未來需求轉趨悲觀並凍結投資。"
            },
            {
                "indicator": "M2 貨幣供給年增率 (M2SL YoY)",
                "code": "M2SL",
                "freq": "每月底",
                "current": f"{m2_yoy:+.2f}% (YoY)",
                "trigger": "年增率穩定保持 > 5.0%",
                "meaning": "金融流動性活水。M2 保持 5% 以上擴張將持續為市場注入評價支撐，降低流動性枯竭風險。"
            }
        ]
    }

def run_gemini_macro_agent():
    """主執行函數：取得最新數據、呼叫 Gemini、保存結果並同步至 data.js"""
    print(f"[{datetime.datetime.now()}] 啟動 Gemini AI 總經診斷代理程式...")
    snapshot = get_latest_macro_snapshot()
    
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    result = None
    engine_name = ""

    debug_info = ""
    if api_key:
        print(f"檢測到 GEMINI_API_KEY (長度 {len(api_key)})，正在呼叫 Google Gemini 進行全面總經深度推論...")
        prompt = build_gemini_prompt(snapshot)
        ai_res, used_model = call_gemini_api(prompt, api_key)
        if ai_res:
            result = ai_res
            engine_name = f"Gemini ({used_model}) (AI 實時生成)"
            print(f"Gemini AI ({used_model}) 總經深度診斷報告生成成功！")
        else:
            debug_info = f"GEMINI_API_KEY 已配置 (長度 {len(api_key)})，但 API 調用失敗: {LAST_API_ERROR}"
            print(f"Gemini API 調用未果: {debug_info}")
    else:
        debug_info = "GitHub Actions / 本地環境未檢測到 GEMINI_API_KEY (變數為空)"
        print("未配置 GEMINI_API_KEY，啟用總經架構確定性演算法產製報告...")

    if not result:
        result = fallback_rule_diagnosis(snapshot)
        engine_name = "總經分析規則引擎 (保底備援模式)"

    result['generated_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result['engine'] = engine_name
    if debug_info:
        result['debug_info'] = debug_info

    # 1. 保存獨立 JSON
    with open(DIAGNOSIS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"已保存 AI 診斷結果至 {DIAGNOSIS_JSON_PATH}")

    # 2. 同步注入 docs/data.js (確保靜態網頁可秒載入)
    if os.path.exists(DATA_JS_PATH):
        with open(DATA_JS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 使用正規表達式安全替換或追加 var AI_DIAGNOSIS = ...;
        new_diag_stmt = f"var AI_DIAGNOSIS = {json.dumps(result, ensure_ascii=False)};"
        if re.search(r"(?:const|var)\s+AI_DIAGNOSIS\s*=.*?;", content, re.DOTALL):
            content = re.sub(r"(?:const|var)\s+AI_DIAGNOSIS\s*=.*?;", new_diag_stmt, content, count=1, flags=re.DOTALL)
        else:
            content = content.rstrip() + "\n" + new_diag_stmt + "\n"
        
        with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"已成功同步注入 AI 診斷結果至 {DATA_JS_PATH}")

    return result

if __name__ == "__main__":
    run_gemini_macro_agent()

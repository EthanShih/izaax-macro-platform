import sqlite3
import pandas as pd
import json
import os

BASE_DIR = r"C:\AntiGravity\izaax-macro-platform"
DOCS_DIR = os.path.join(BASE_DIR, "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "macro_data.db")

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

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT date, indicator_code, indicator_name, value FROM macro_indicators ORDER BY date", conn)
conn.close()

df['date'] = pd.to_datetime(df['date'])

# 計算統計數據
summary_list = []
timeseries_dict = {}

for code, meta in INDICATOR_METADATA.items():
    sub = df[df['indicator_code'] == code].sort_values('date').dropna(subset=['value'])
    if sub.empty:
        continue
    
    # 時間序列資料 (保留 2000 年後)
    sub_filtered = sub[sub['date'] >= '2000-01-01']
    timeseries_dict[code] = {
        'name': meta['name'],
        'category': meta['category'],
        'unit': meta['unit'],
        'is_rate': meta['is_rate'],
        'dates': sub_filtered['date'].dt.strftime('%Y-%m-%d').tolist(),
        'values': sub_filtered['value'].round(3).tolist()
    }
    
    latest = sub.iloc[-1]
    prev = sub.iloc[-2] if len(sub) > 1 else None
    target_1y = latest['date'] - pd.DateOffset(years=1)
    sub_1y = sub[sub['date'] <= target_1y]
    prev_1y = sub_1y.iloc[-1] if not sub_1y.empty else None
    
    is_rate = meta['is_rate']
    mom = (latest['value'] - prev['value']) if is_rate else (((latest['value'] / prev['value']) - 1) * 100 if prev is not None and prev['value'] != 0 else 0)
    yoy = (latest['value'] - prev_1y['value']) if is_rate else (((latest['value'] / prev_1y['value']) - 1) * 100 if prev_1y is not None and prev_1y['value'] != 0 else 0)

    summary_list.append({
        'code': code,
        'name': meta['name'],
        'category': meta['category'],
        'unit': meta['unit'],
        'is_rate': is_rate,
        'latest_date': latest['date'].strftime('%Y-%m-%d'),
        'value': round(float(latest['value']), 3),
        'prev_value': round(float(prev['value']), 3) if prev is not None else None,
        'mom': round(float(mom), 2) if mom is not None else None,
        'yoy': round(float(yoy), 2) if yoy is not None else None
    })

# 輸出 data.js
data_js_path = os.path.join(DOCS_DIR, "data.js")
with open(data_js_path, "w", encoding="utf-8") as f:
    f.write("// 自動生成的總經數據資料庫\n")
    f.write("const MACRO_DATA = " + json.dumps(timeseries_dict, ensure_ascii=False) + ";\n")
    f.write("const LATEST_SUMMARY = " + json.dumps(summary_list, ensure_ascii=False) + ";\n")

print(f"成功生成 {data_js_path}")

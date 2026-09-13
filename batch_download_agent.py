import sqlite3
import pandas as pd
import pandas_datareader.data as web
import datetime

# 總經指標代碼對應表 (愛榭克總經框架常用指標)
INDICATORS = {
    'PAYEMS': '非農就業人數',
    'UNRATE': '失業率',
    'ICSA': '初領失業救濟金人數',
    'CPIAUCSL': '消費者物價指數(CPI)',
    'PCEPI': 'PCE物價指數',
    'PCEPILFE': '核心PCE物價指數',
    'PPIFIS': '生產者物價指數(PPI)',
    'RSXFS': '零售銷售',
    'PCE': '個人消費支出',
    'UMCSENT': '密西根大學消費者信心指數',
    'DGORDER': '耐久財新訂單',
    'INDPRO': '工業生產指數',
    'GACDFSA066MSFRBPHI': '費城聯邦製造業指數',
    'HOUST': '新屋開工',
    'PERMIT': '建築許可',
    'HSN1F': '新屋銷售',
    'EXHOSLUSM495S': '成屋銷售',
    'FEDFUNDS': '聯邦基金利率',
    'DGS10': '10年期公債殖利率',
    'T10Y2Y': '10年減2年期公債殖利率差',
    'T10Y3M': '10年減3個月期公債殖利率差',
    'GDP': '國內生產毛額(GDP)',
    'M2SL': 'M2貨幣供給'
}

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'macro_data.db')

def create_table(conn):
    """建立資料表與 Schema"""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS macro_indicators (
            date TEXT,
            indicator_code TEXT,
            indicator_name TEXT,
            value REAL,
            PRIMARY KEY (date, indicator_code)
        )
    ''')
    conn.commit()

def batch_download(start_date, end_date):
    """批次下載並寫入資料庫"""
    try:
        conn = sqlite3.connect(DB_PATH)
        create_table(conn)
        cursor = conn.cursor()
        
        for code, name in INDICATORS.items():
            print(f"正在下載 {name} ({code})...")
            try:
                # 透過 pandas_datareader 從 FRED 獲取歷史資料
                df = web.DataReader(code, 'fred', start_date, end_date)
                
                if df.empty:
                    print(f"警告: {code} 資料為空。")
                    continue
                    
                # 重新整理 DataFrame 以符合 schema 需求
                df = df.reset_index()
                df = df.rename(columns={'DATE': 'date', code: 'value'})
                df['date'] = df['date'].dt.strftime('%Y-%m-%d')
                
                # 排除缺失值
                df = df.dropna(subset=['value'])
                
                # 準備寫入資料
                records = [
                    (row['date'], code, name, row['value'])
                    for _, row in df.iterrows()
                ]
                
                # 使用 INSERT OR REPLACE 避免重複寫入報錯或違反 PRIMARY KEY 約束
                cursor.executemany('''
                    INSERT OR REPLACE INTO macro_indicators (date, indicator_code, indicator_name, value)
                    VALUES (?, ?, ?, ?)
                ''', records)
                conn.commit()
                
                print(f"成功寫入 {name} ({code}) 共 {len(records)} 筆資料。")
            except Exception as e:
                print(f"下載或寫入 {code} 時發生錯誤: {e}")
                
    except sqlite3.Error as e:
        print(f"資料庫連線錯誤: {e}")
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("資料庫連線已關閉。")

if __name__ == "__main__":
    # 設定下載的歷史資料範圍，這裡預設從 2000 年開始
    start = datetime.datetime(2000, 1, 1)
    end = datetime.datetime.now()
    batch_download(start, end)

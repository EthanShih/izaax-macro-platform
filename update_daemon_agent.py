import sqlite3
import pandas as pd
import pandas_datareader.data as web
import datetime
import time

# 總經指標代碼對應表
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
    'FEDFUNDS': '聯邦資金利率',
    'DGS10': '10年期公債殖利率',
    'T10Y2Y': '10年減2年期公債殖利率差',
    'T10Y3M': '10年減3個月期公債殖利率差',
    'GDP': '名目GDP (BEA)',
    'GDPC1': '實質GDP (BEA)',
    'A191RL1Q225SBEA': '實質GDP季增年率 (BEA)',
    'M2SL': 'M2貨幣供給'
}

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'macro_data.db')

def get_latest_date(conn, code):
    """獲取資料庫中該指標的最後一筆資料日期"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT MAX(date) FROM macro_indicators WHERE indicator_code = ?
    ''', (code,))
    result = cursor.fetchone()
    if result and result[0]:
        return datetime.datetime.strptime(result[0], '%Y-%m-%d')
    return None

def incremental_update():
    """對各指標進行增量更新"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        end_date = datetime.datetime.now()
        
        for code, name in INDICATORS.items():
            latest_date = get_latest_date(conn, code)
            
            if not latest_date:
                print(f"{name} ({code}) 尚無資料，請先執行 batch_download_agent.py。")
                continue
            
            # 從最後一筆資料的隔天開始下載
            start_date = latest_date + datetime.timedelta(days=1)
            
            if start_date > end_date:
                print(f"{name} ({code}) 已經是最新狀態，無需更新。")
                continue
                
            print(f"正在更新 {name} ({code})，從 {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}...")
            try:
                # 透過 pandas_datareader 從 FRED 獲取新資料
                df = web.DataReader(code, 'fred', start_date, end_date)
                
                if df.empty:
                    print(f"{code} 沒有新資料。")
                    continue
                    
                df = df.reset_index()
                df = df.rename(columns={'DATE': 'date', code: 'value'})
                df['date'] = df['date'].dt.strftime('%Y-%m-%d')
                df = df.dropna(subset=['value'])
                
                if df.empty:
                    print(f"{code} 沒有新資料 (排除空值後)。")
                    continue
                
                records = [
                    (row['date'], code, name, row['value'])
                    for _, row in df.iterrows()
                ]
                
                cursor.executemany('''
                    INSERT OR REPLACE INTO macro_indicators (date, indicator_code, indicator_name, value)
                    VALUES (?, ?, ?, ?)
                ''', records)
                conn.commit()
                
                print(f"成功更新 {name} ({code}) 共 {len(records)} 筆新資料。")
            except Exception as e:
                print(f"更新 {code} 時發生錯誤: {e}")
                
    except sqlite3.Error as e:
        print(f"資料庫連線錯誤: {e}")
    except Exception as e:
        print(f"發生未預期的錯誤: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    # 以 Daemon 模式執行，每天定期更新一次
    while True:
        print(f"\n--- 開始執行增量更新 ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
        incremental_update()
        print("更新完成，等待下次執行 (24 小時後)...\n")
        # 暫停 24 小時 (86400 秒)
        time.sleep(86400)

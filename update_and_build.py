import datetime
import subprocess
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print(f"[{datetime.datetime.now()}] 啟動每日自動更新排程...")

# 1. 執行增量資料下載
from update_daemon_agent import incremental_update
incremental_update()

# 2. 重新編譯產出基礎資料 docs/data.js
build_script = os.path.join(BASE_DIR, "build_site.py")
subprocess.run(["python", build_script], check=True)

# 3. 呼叫 Gemini AI 產生全新總經深度診斷報告 (具備保底引擎備援)
from gemini_macro_agent import run_gemini_macro_agent
run_gemini_macro_agent()

print(f"[{datetime.datetime.now()}] 更新與網站重新構建完成！")

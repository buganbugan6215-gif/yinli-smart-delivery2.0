@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "YL_STAFF_PASSWORD=123456"
echo 正在启动生鲜农产品智慧配送平台...
start "" cmd /c "for /l %%i in (1,1,30) do (powershell -NoProfile -Command \"try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://localhost:8501/).StatusCode -eq 200 } catch { $false }\" | findstr /c:True >nul && (start http://localhost:8501/ & exit) || timeout /t 1 /nobreak >nul) & echo 网站启动超时，请查看此窗口中的错误信息。"
python -m streamlit run app.py --server.headless true --server.port 8501
pause

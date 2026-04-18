@echo off
chcp 65001 >nul
echo ========================================
echo   AIOps 多智能体根因分析系统
echo   一键启动脚本 (Web界面)
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo [1/3] 检查依赖...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo 发现缺少依赖，正在安装...
    pip install -r requirements.txt
)

echo [2/3] 依赖检查完成
echo.

echo [3/3] 启动 Web 界面...
echo.
echo 浏览器将自动打开: http://localhost:8501
echo 关闭终端窗口可停止服务
echo.

streamlit run app.py

pause
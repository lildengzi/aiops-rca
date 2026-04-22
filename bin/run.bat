@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ========================================
echo   AIOps 多智能体根因分析系统
echo   一键启动脚本 (Web界面)
echo ========================================
echo.

:: 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查并创建必要目录
if not exist "logs\" mkdir logs
if not exist "reports\" mkdir reports
if not exist "models\" mkdir models

echo [1/4] 检查依赖...
pip show streamlit langchain langgraph faiss-cpu >nul 2>&1
if errorlevel 1 (
    echo 发现缺少依赖，正在安装完整依赖包...
    pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接或手动执行 pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo [2/4] 初始化知识库...
if not exist "knowledge_base\faiss_index" (
    echo 首次运行，正在构建 RAG 知识库索引...
    python build_knowledge_base.py >nul 2>&1
    if errorlevel 1 (
        echo [警告] 知识库构建失败，将使用降级模式运行
    ) else (
        echo 知识库构建完成
    )
)

echo [3/4] 检查环境配置...
if not exist ".env" (
    echo [提示] 未找到 .env 配置文件，将使用默认配置运行离线演示模式
    echo [提示] 如需使用完整 LLM 功能，请复制 .env.example 为 .env 并配置 API Key
    echo.
)

echo [4/4] 启动 Web 界面...
echo.
echo 浏览器将自动打开: http://localhost:8501
echo 按 Ctrl+C 可停止服务
echo.

streamlit run app.py --server.headless=false --browser.gatherUsageStats=false

echo.
echo 服务已停止
pause
@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

cd /d "%~dp0.."

echo ========================================
echo   AIOps 多智能体根因分析系统
echo   一键启动脚本 ^(Web 界面^)
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
if not exist "think_log\" mkdir think_log
if not exist "feedback\" mkdir feedback

echo [1/5] 检查依赖...
pip show streamlit langchain langgraph faiss-cpu pandas numpy faster-whisper pytesseract opencv-python-headless >nul 2>&1
if errorlevel 1 (
    echo 发现缺少依赖，正在安装 requirements.txt ...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接或手动执行 python -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

echo [2/5] 检查 OCR 环境...
where tesseract >nul 2>&1
if errorlevel 1 (
    echo [警告] 未检测到 Tesseract 可执行程序，图片文字识别功能可能不可用。
    echo [提示] 如需启用 OCR，请安装 Tesseract OCR 并确保 tesseract 已加入 PATH。
) else (
    echo 已检测到 Tesseract OCR
)

echo [3/5] 初始化知识库...
if not exist "knowledge_base\faiss_index" (
    echo 首次运行，正在构建 RAG 知识库索引...
    python build_knowledge_base.py >nul 2>&1
    if errorlevel 1 (
        echo [警告] 知识库构建失败，将使用降级模式运行
    ) else (
        echo 知识库构建完成
    )
) else (
    echo 已存在知识库索引，跳过构建
)

echo [4/5] 检查环境配置...
if not exist ".env" (
    echo [提示] 未找到 .env 配置文件。
    echo [提示] Web 界面仍可启动，但完整多智能体分析需要配置 LLM API Key。
    echo [提示] 如需使用完整功能，请复制 .env.example 为 .env 并填写配置。
    echo.
)

echo [5/5] 启动 Web 界面...
echo.
echo 浏览器将自动打开: http://localhost:8501
echo 如需停止服务，请关闭当前窗口或结束对应的 streamlit 进程
echo.

python -m streamlit run app.py --server.headless=false --browser.gatherUsageStats=false

echo.
echo 服务已停止
pause
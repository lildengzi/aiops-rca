@echo off
chcp 65001 >nul

echo ========================================
echo   AIOps 多智能体根因分析系统
echo   离线演示模式 (无需 API Key)
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo [1/3] 检查基础依赖...
pip show pandas numpy >nul 2>&1
if errorlevel 1 (
    echo 安装基础依赖...
    pip install pandas numpy
)

echo [2/3] 准备演示数据...
if not exist "data\" (
    echo [错误] 未找到测试数据目录
    pause
    exit /b 1
)

echo [3/3] 启动离线演示...
echo.
echo 正在运行 CPU 故障场景离线分析...
echo.

python demo_offline.py

echo.
echo 演示完成
pause

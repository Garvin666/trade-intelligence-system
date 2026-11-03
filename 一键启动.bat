@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================================
echo   Cross-Border Product Selection Demo - One-Click Start
echo   Backend + Native Desktop Window + React Frontend (/app)
echo ==========================================================

set "ROOT=%~dp0"
set "PYTHON_CMD="
set "PYTHON_FLAGS="
set "DEMO_MODE=-Desktop"
set "EXTRA_ARGS="
if "%DEMO_OPEN_BROWSER%"=="1" set "DEMO_MODE="
if /i "%~1"=="/browser" set "DEMO_MODE="
if /i "%~1"=="/port" (
    set "DEMO_MODE="
    set "EXTRA_ARGS=-Port %~2"
)
set "DEMO_LOGIN_URL=/agent/login.html?v=20260822-starfield-v2"

if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%ROOT%.venv\Scripts\python.exe"
    goto python_ok
)

set "PYTHON_CMD=python"
python --version >nul 2>nul
if not errorlevel 1 goto python_ok

set "PYTHON_CMD=py"
set "PYTHON_FLAGS=-3"
py -3 --version >nul 2>nul
if errorlevel 1 goto python_failed

:python_ok
"%PYTHON_CMD%" %PYTHON_FLAGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 goto deps
if /i "%PYTHON_CMD%"=="python" (
    set "PYTHON_CMD=py"
    set "PYTHON_FLAGS=-3"
    goto python_ok
)
goto python_failed

:create_venv
echo Creating local virtual environment (.venv) ...
"%PYTHON_CMD%" %PYTHON_FLAGS% -m venv "%ROOT%.venv"
if errorlevel 1 goto venv_failed
set "PYTHON_CMD=%ROOT%.venv\Scripts\python.exe"
set "PYTHON_FLAGS="

:deps
echo [1/2] Checking dependencies ...
"%PYTHON_CMD%" %PYTHON_FLAGS% -c "import importlib.util as u; raise SystemExit(0 if all(u.find_spec(m) for m in ('fastapi','uvicorn')) else 1)" >nul 2>nul
if not errorlevel 1 goto start
if not exist "%ROOT%.venv\Scripts\python.exe" goto create_venv
echo Installing requirements (first run may take a few minutes)...
set "PIP_COMMON=--disable-pip-version-check --timeout 20 --retries 1"
set "PIP_FALLBACK_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple"
if defined DEMO_PIP_INDEX_URL set "PIP_FALLBACK_INDEX=%DEMO_PIP_INDEX_URL%"
set "REQUIREMENTS_FILE=%ROOT%requirements.lock"
if not exist "%REQUIREMENTS_FILE%" set "REQUIREMENTS_FILE=%ROOT%requirements.txt"
"%PYTHON_CMD%" %PYTHON_FLAGS% -m pip install --upgrade pip %PIP_COMMON% >nul 2>nul
if errorlevel 1 (
    echo [WARN] Default pip source failed. Retrying without the system proxy...
    "%PYTHON_CMD%" %PYTHON_FLAGS% -m pip install --upgrade pip --index-url "%PIP_FALLBACK_INDEX%" --proxy= %PIP_COMMON%
    if errorlevel 1 goto deps_failed
)
"%PYTHON_CMD%" %PYTHON_FLAGS% -m pip install -r "%REQUIREMENTS_FILE%" %PIP_COMMON%
if errorlevel 1 (
    echo [WARN] Default pip source failed. Retrying without the system proxy...
    "%PYTHON_CMD%" %PYTHON_FLAGS% -m pip install -r "%REQUIREMENTS_FILE%" --index-url "%PIP_FALLBACK_INDEX%" --proxy= %PIP_COMMON%
    if errorlevel 1 goto deps_failed
)
echo Dependencies ready.

:start
if "%DEMO_MODE%"=="-Desktop" (
    echo [2/2] Starting backend and opening the native desktop window ...
) else (
    echo [2/2] Starting backend and opening the login page in your browser ...
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%start_complete_demo.ps1" %DEMO_MODE% %EXTRA_ARGS%
if errorlevel 1 goto start_failed
goto end

:python_failed
echo [ERROR] Python 3.10+ not found. Please install Python first.
pause
exit /b 1

:venv_failed
echo [ERROR] Failed to create local virtual environment (.venv).
pause
exit /b 1

:deps_failed
echo [ERROR] Dependency install failed. Check network and retry.
pause
exit /b 1

:start_failed
echo [ERROR] Backend failed to start. See messages above.
pause

:end
endlocal

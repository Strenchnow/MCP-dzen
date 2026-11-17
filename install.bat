@echo off
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

echo [1/5] Checking Python installation...
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found in PATH. Install Python 3.10+ and retry.
    exit /b 1
)

echo [2/5] Creating virtual environment in "%ROOT_DIR%\.venv"...
if not exist "%ROOT_DIR%\.venv\Scripts\python.exe" (
    python -m venv "%ROOT_DIR%\.venv"
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        exit /b 1
    )
)

echo [3/5] Upgrading pip and installing dependencies...
"%ROOT_DIR%\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

"%ROOT_DIR%\.venv\Scripts\pip.exe" install "mcp[cli]" playwright
if errorlevel 1 exit /b 1

echo [4/5] Installing Playwright Chromium browser...
"%ROOT_DIR%\.venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1

echo [5/5] Generating mcp_config_snippet.json...
"%ROOT_DIR%\.venv\Scripts\python.exe" -c "import json, pathlib; root = pathlib.Path(r'%ROOT_DIR%'); cfg = {'mcpServers': {'dzen-mcp': {'command': str(root / '.venv' / 'Scripts' / 'python.exe'), 'args': [str(root / 'server.py')]}}}; out = root / 'mcp_config_snippet.json'; text = json.dumps(cfg, indent=2, ensure_ascii=False); out.write_text(text + '\n', encoding='utf-8'); print('\n=== Copy this into your mcp_config.json ===\n' + text + '\n==========================================\nSaved to: ' + str(out))"
if errorlevel 1 exit /b 1

echo Done! Add the JSON above to your MCP config and click Refresh.
endlocal

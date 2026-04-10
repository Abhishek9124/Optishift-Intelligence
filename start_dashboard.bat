@echo off
REM ==============================================
REM Leave Management Dashboard - Startup Script
REM ==============================================

echo.
echo ========================================
echo   Leave Management - Executive Dashboard
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo WARNING: Virtual environment not found
    echo Please activate it with: .venv\Scripts\activate.bat
)

REM Check if Flask is installed
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Flask is not installed
    echo Install with: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Display startup information
echo Checking dependencies...
python -c "import flask, plotly, pandas; print('✓ Flask ' + flask.__version__); print('✓ Plotly ' + plotly.__version__); print('✓ Pandas ' + pandas.__version__)"

echo.
echo ========================================
echo Starting Flask Application...
echo ========================================
echo.
echo  📊 Dashboard will be available at:
echo     http://localhost:5000
echo.
echo  Press Ctrl+C to stop the server
echo.

REM Start Flask
python web_dashboard.py

pause

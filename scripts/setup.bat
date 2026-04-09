@echo off
echo === VAT Reports Generator Setup ===

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed. Please install Python 3.13+.
    exit /b 1
)

uv --version >nul 2>&1
if errorlevel 1 (
    echo Installing uv...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    echo Please restart your terminal and run this script again.
    exit /b 0
)

echo Installing dependencies...
uv sync --all-extras

echo.
echo === Setup complete! ===
echo Before running, make sure you have:
echo   1. Created a .env file (copy from .env.example)
echo   2. Placed credentials.json in the project root
echo.
echo Run the app with: scripts\run.bat

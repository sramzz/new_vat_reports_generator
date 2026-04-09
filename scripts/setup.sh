#!/bin/bash
set -e

echo "=== VAT Reports Generator Setup ==="

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed. Please install Python 3.13+."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "Please restart your terminal and run this script again."
    exit 0
fi

echo "Installing dependencies..."
uv sync --all-extras

echo ""
echo "=== Setup complete! ==="
echo "Before running, make sure you have:"
echo "  1. Created a .env file (copy from .env.example)"
echo "  2. Placed credentials.json in the project root"
echo ""
echo "Run the app with: ./scripts/run.sh"

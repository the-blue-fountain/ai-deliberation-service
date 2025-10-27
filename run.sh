#!/bin/bash

# Exit on any error
set -e

echo "=========================================="
echo "Django Application Setup Script"
echo "=========================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed!"
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
    echo "✅ uv installed successfully!"
    echo "Please restart your terminal and run this script again."
    exit 0
fi

echo "✅ uv is installed"
echo ""

# Define virtual environment name
VENV_NAME=".adsys"

# Check if virtual environment exists and remove it
if [ -d "$VENV_NAME" ]; then
    echo "🗑️  Removing existing virtual environment..."
    rm -rf "$VENV_NAME"
    echo "✅ Old virtual environment removed"
    echo ""
fi

# Install Python 3.13.7 using uv
echo "📦 Installing Python 3.13.7..."
uv python install 3.13.7
echo "✅ Python 3.13.7 installed"
echo ""

# Create virtual environment with Python 3.13.7
echo "🔨 Creating virtual environment..."
uv venv "$VENV_NAME" --python 3.13.7
echo "✅ Virtual environment created"
echo ""

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source "$VENV_NAME/bin/activate"
echo "✅ Virtual environment activated"
echo ""

# Install packages from requirements.txt
echo "📥 Installing packages from requirements.txt..."
uv pip install -r requirements.txt
echo "✅ All packages installed"
echo ""

# Navigate to chatbot_site directory
if [ ! -d "chatbot_site" ]; then
    echo "❌ Error: chatbot_site directory not found!"
    echo "Please make sure you're running this script from the correct directory."
    exit 1
fi

echo "📂 Navigating to chatbot_site directory..."
cd chatbot_site
echo ""

# Run Django management commands
echo "🔧 Running Django migrations..."
python3.13 manage.py makemigrations
echo ""

echo "🔧 Applying migrations..."
python3.13 manage.py migrate
echo ""

echo "=========================================="
echo "🚀 Starting Django development server..."
echo "=========================================="
echo ""
echo "Press CTRL+C to stop the server"
echo ""

python3.13 manage.py runserver

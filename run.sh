#!/bin/bash

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo "Error: pyenv is not installed. Please install pyenv first."
    echo "Installation instructions: https://github.com/pyenv/pyenv#installation"
    exit 1
fi

# Install Python 3.13.7 if not already installed
if ! pyenv versions | grep -q "3.13.7"; then
    echo "Installing Python 3.13.7 with pyenv..."
    pyenv install 3.13.7
fi

# Set local Python version to 3.13.7
echo "Setting local Python version to 3.13.7..."
pyenv local 3.13.7

# Create virtual environment
echo "Creating virtual environment..."
python -m venv venv

# Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install required packages
echo "Installing packages from requirements.txt..."
pip install -r requirements.txt

echo "Setup complete. Virtual environment is activated and packages are installed."
echo "To activate the environment in future sessions, run: source venv/bin/activate"
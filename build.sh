#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Navigate to Django project directory
cd chatbot_site

# Collect static files
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

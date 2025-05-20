#!/usr/bin/env bash
# exit on error
set -o errexit

# Install LibreOffice
apt-get update
apt-get install -y libreoffice

# Install Python dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate 
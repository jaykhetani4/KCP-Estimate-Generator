#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies
apt-get update
apt-get install -y software-properties-common
add-apt-repository -y ppa:libreoffice/ppa
apt-get update

# Install LibreOffice and unoconv
apt-get install -y libreoffice
apt-get install -y unoconv

# Install Python dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate 
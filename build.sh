#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies
apt-get update
apt-get install -y software-properties-common
add-apt-repository -y ppa:libreoffice/ppa
apt-get update

# Install LibreOffice and its dependencies
apt-get install -y libreoffice
apt-get install -y libreoffice-writer
apt-get install -y libreoffice-calc
apt-get install -y libreoffice-impress
apt-get install -y libreoffice-draw
apt-get install -y libreoffice-math
apt-get install -y libreoffice-base
apt-get install -y libreoffice-gnome
apt-get install -y libreoffice-gtk3

# Install Python dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate 
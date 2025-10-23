#!/usr/bin/env bash
# Render build script for Django + grpcio

set -o errexit  # exit on error

# Install system dependencies for grpcio
apt-get update && apt-get install -y python3-dev build-essential libssl-dev libffi-dev

# Then install Python dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

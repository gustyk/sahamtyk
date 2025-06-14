#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Menjalankan perintah untuk membuat semua tabel database secara otomatis
flask shell <<< "from models import db; db.create_all(); exit()"
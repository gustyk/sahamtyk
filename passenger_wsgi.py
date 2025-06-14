# passenger_wsgi.py
import os
import sys

# Ganti 'sahamtyk' dengan nama folder aplikasi Anda di server jika berbeda
# Biasanya, baris di bawah ini sudah benar jika struktur Anda standar
sys.path.insert(0, os.path.dirname(__file__))

# Impor objek 'app' dari file app.py Anda
# Server akan menggunakan variabel bernama 'application' ini
from app import app as application
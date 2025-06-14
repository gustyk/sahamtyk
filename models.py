# models.py

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# Model untuk Pengguna (User) - Tidak berubah
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Model untuk Watchlist Saham - Tidak berubah, ini adalah fitur yang sudah ada
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    harga_akumulasi_bawah = db.Column(db.Float, nullable=False)
    harga_akumulasi_atas = db.Column(db.Float, nullable=False)
    harga_cut_loss = db.Column(db.Float, nullable=False)
    harga_take_profit_1 = db.Column(db.Float, nullable=False)
    harga_take_profit_2 = db.Column(db.Float, nullable=True)
    harga_take_profit_3 = db.Column(db.Float, nullable=True)
    tanggal_cut_loss = db.Column(db.Date, nullable=True)
    tanggal_tp_1 = db.Column(db.Date, nullable=True)
    tanggal_tp_2 = db.Column(db.Date, nullable=True)
    tanggal_tp_3 = db.Column(db.Date, nullable=True)

# --- MODEL BARU UNTUK PORTOFOLIO ---
# Model ini akan mencatat setiap transaksi beli atau jual yang Anda lakukan
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    transaction_type = db.Column(db.String(4), nullable=False) # 'BUY' atau 'SELL'
    transaction_date = db.Column(db.Date, nullable=False)
    lots = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True) # Untuk 'alasan beli', dll.
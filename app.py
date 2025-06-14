# app.py (VERSI LENGKAP & FINAL SETELAH REFACTORING)

import os
import yfinance as yf
from datetime import date, datetime
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Stock, Transaction # Pastikan Transaction sudah di-import

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) 
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("://", "ql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Rute Utama ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('portfolio'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('portfolio'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            flash('Login berhasil!', 'success')
            return redirect(url_for('portfolio')) # DIUBAH ke portfolio
        else:
            flash('Login gagal. Periksa kembali username dan password.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if User.query.count() > 0:
        flash('Registrasi sudah ditutup.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Akun berhasil dibuat! Silakan login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('login'))

# --- Fitur Portofolio ---

@app.route('/portfolio')
@login_required
def portfolio():
    # 1. Ambil semua transaksi milik user, urutkan berdasarkan tanggal
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.transaction_date).all()
    
    # 2. Agregasi transaksi menjadi data kepemilikan (holdings)
    holdings = {}
    for t in transactions:
        if t.ticker not in holdings:
            holdings[t.ticker] = {'lots': 0, 'total_cost': 0}
        
        if t.transaction_type == 'BUY':
            holdings[t.ticker]['lots'] += t.lots
            holdings[t.ticker]['total_cost'] += t.lots * t.price * 100
        elif t.transaction_type == 'SELL':
            # Jika ada penjualan, kita kurangi biaya modal secara proporsional
            if holdings[t.ticker]['lots'] > 0:
                avg_cost_per_share = holdings[t.ticker]['total_cost'] / (holdings[t.ticker]['lots'] * 100)
                cost_of_shares_sold = t.lots * 100 * avg_cost_per_share
                holdings[t.ticker]['total_cost'] -= cost_of_shares_sold
            holdings[t.ticker]['lots'] -= t.lots

    # Filter saham yang sudah habis terjual (lot <= 0)
    current_holdings = {ticker: data for ticker, data in holdings.items() if data['lots'] > 0}
    
    # Inisialisasi variabel untuk ringkasan total
    grand_total = {'modal': 0, 'nilai_sekarang': 0}

    # 3. Ambil harga terbaru jika ada saham yang dimiliki
    if current_holdings:
        ticker_list = [ticker + ".JK" for ticker in current_holdings.keys()]
        try:
            latest_data = yf.download(tickers=ticker_list, period="1d", progress=False)
            
            # 4. Lakukan kalkulasi final untuk setiap saham
            for ticker, data in current_holdings.items():
                # Kalkulasi harga beli rata-rata
                data['avg_price'] = data['total_cost'] / (data['lots'] * 100)
                
                # Ambil harga terbaru
                try:
                    latest_price = latest_data['Close'][ticker + '.JK'].iloc[-1]
                except (KeyError, IndexError):
                    latest_price = data['avg_price'] # Jika gagal, anggap harga sama dengan avg
                
                data['latest_price'] = latest_price
                data['nilai_sekarang'] = latest_price * data['lots'] * 100
                data['unrealized_pl'] = data['nilai_sekarang'] - data['total_cost']
                data['unrealized_pl_percent'] = (data['unrealized_pl'] / data['total_cost']) * 100 if data['total_cost'] > 0 else 0
                
                # Akumulasi untuk ringkasan total
                grand_total['modal'] += data['total_cost']
                grand_total['nilai_sekarang'] += data['nilai_sekarang']
        
        except Exception as e:
            flash(f'Gagal mengambil harga saham terbaru: {e}', 'danger')
    
    # Kalkulasi ringkasan total
    grand_total['pl'] = grand_total['nilai_sekarang'] - grand_total['modal']
    grand_total['pl_percent'] = (grand_total['pl'] / grand_total['modal']) * 100 if grand_total['modal'] > 0 else 0

    return render_template('portfolio.html', user=current_user, holdings=current_holdings, totals=grand_total)



@app.route('/tambah-transaksi', methods=['GET', 'POST'])
@login_required
def tambah_transaksi():
    if request.method == 'POST':
        try:
            # Ambil dan proses data dari form
            ticker = request.form.get('ticker').upper()
            tipe = request.form.get('transaction_type')
            # Konversi string tanggal dari form (YYYY-MM-DD) menjadi objek date Python
            tanggal_str = request.form.get('transaction_date')
            tanggal_obj = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
            lots = int(request.form.get('lots'))
            price = float(request.form.get('price'))
            notes = request.form.get('notes')

            # Buat objek Transaction baru
            new_transaction = Transaction(
                user_id=current_user.id,
                ticker=ticker,
                transaction_type=tipe,
                transaction_date=tanggal_obj,
                lots=lots,
                price=price,
                notes=notes
            )

            db.session.add(new_transaction)
            db.session.commit()
            flash('Transaksi berhasil ditambahkan!', 'success')
            return redirect(url_for('portfolio'))

        except ValueError:
            flash('Input tidak valid. Pastikan Lot dan Harga adalah angka.', 'danger')
        except Exception as e:
            flash(f'Terjadi error: {e}', 'danger')

    return render_template('tambah_transaksi.html')


@app.route('/riwayat-transaksi')
@login_required
def riwayat_transaksi():
    # Ambil semua transaksi user, urutkan dari yang paling baru
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.transaction_date.desc()).all()
    return render_template('riwayat_transaksi.html', transactions=transactions)


@app.route('/laporan', methods=['GET', 'POST'])
@login_required
def laporan():
    results = None
    selected_month = date.today().month
    selected_year = date.today().year

    if request.method == 'POST':
        selected_month = int(request.form.get('month'))
        selected_year = int(request.form.get('year'))

        # 1. Ambil semua transaksi
        all_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.transaction_date).all()

        holdings = {} # Untuk melacak status portofolio secara real-time
        realized_trades = [] # Untuk menampung hasil penjualan di periode terpilih

        # 2. Proses setiap transaksi secara kronologis
        for t in all_transactions:
            if t.ticker not in holdings:
                holdings[t.ticker] = {'lots': 0, 'total_cost': 0}

            if t.transaction_type == 'BUY':
                holdings[t.ticker]['lots'] += t.lots
                holdings[t.ticker]['total_cost'] += t.lots * t.price * 100

            elif t.transaction_type == 'SELL':
                pl_for_this_sale = 0
                if holdings[t.ticker]['lots'] > 0:
                    # Hitung harga beli rata-rata SAAT ITU
                    avg_cost_per_share = holdings[t.ticker]['total_cost'] / (holdings[t.ticker]['lots'] * 100)

                    cost_of_goods_sold = t.lots * 100 * avg_cost_per_share
                    sale_proceeds = t.lots * 100 * t.price
                    pl_for_this_sale = sale_proceeds - cost_of_goods_sold

                    # Cek apakah penjualan ini terjadi di periode yang dipilih
                    if t.transaction_date.year == selected_year and t.transaction_date.month == selected_month:
                        realized_trades.append({
                            'date': t.transaction_date,
                            'ticker': t.ticker,
                            'lots': t.lots,
                            'sell_price': t.price,
                            'avg_buy_price': avg_cost_per_share,
                            'pl': pl_for_this_sale
                        })

                # Update holding setelah penjualan
                holdings[t.ticker]['lots'] -= t.lots
                holdings[t.ticker]['total_cost'] -= cost_of_goods_sold if holdings[t.ticker]['lots'] >= 0 else 0

        total_pl = sum(trade['pl'] for trade in realized_trades)
        results = {'trades': realized_trades, 'total_pl': total_pl}

    # Siapkan data untuk dropdown tahun
    start_year = db.session.query(db.func.min(Transaction.transaction_date)).scalar()
    current_year = date.today().year
    years = list(range(start_year.year, current_year + 1)) if start_year else [current_year]

    return render_template('laporan.html', years=years, results=results, selected_month=selected_month, selected_year=selected_year)

@app.route('/detail-saham/<string:ticker>')
@login_required
def detail_saham(ticker):
    try:
        # Ambil periode dari URL query, defaultnya '1y' (1 tahun)
        period = request.args.get('period', '1y')

        # Ambil data historis dari yfinance
        stock_data = yf.Ticker(ticker + ".JK")
        history = stock_data.history(period=period)

        if history.empty:
            flash(f'Tidak dapat menemukan data historis untuk {ticker}', 'warning')
            return redirect(url_for('portfolio'))

        # Siapkan data untuk grafik
        # Ubah format tanggal agar bisa dibaca JavaScript
        labels = history.index.strftime('%d-%m-%Y').tolist()
        # Ambil data harga penutupan
        data = history['Close'].tolist()

        # Ambil info dasar saham untuk ditampilkan
        info = stock_data.info
        stock_info = {
            'name': info.get('longName', ticker),
            'market_cap': info.get('marketCap', 0),
            'sector': info.get('sector', 'N/A')
        }

    except Exception as e:
        flash(f'Terjadi error saat mengambil data untuk {ticker}: {e}', 'danger')
        return redirect(url_for('portfolio'))

    return render_template('detail_saham.html', 
                           ticker=ticker, 
                           stock_info=stock_info,
                           labels=labels, 
                           data=data,
                           active_period=period)

@app.route('/edit-transaksi/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaksi(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        return redirect(url_for('riwayat_transaksi'))

    if request.method == 'POST':
        try:
            transaction.ticker = request.form.get('ticker').upper()
            transaction.transaction_type = request.form.get('transaction_type')
            tanggal_str = request.form.get('transaction_date')
            transaction.transaction_date = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
            transaction.lots = int(request.form.get('lots'))
            transaction.price = float(request.form.get('price'))
            transaction.notes = request.form.get('notes')
            db.session.commit()
            flash('Transaksi berhasil diperbarui.', 'success')
            return redirect(url_for('riwayat_transaksi'))
        except Exception as e:
            flash(f'Gagal memperbarui transaksi: {e}', 'danger')

    return render_template('edit_transaksi.html', t=transaction)

@app.route('/hapus-transaksi/<int:transaction_id>', methods=['POST'])
@login_required
def hapus_transaksi(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        return redirect(url_for('riwayat_transaksi'))

    db.session.delete(transaction)
    db.session.commit()
    flash('Transaksi telah dihapus.', 'info')
    return redirect(url_for('riwayat_transaksi'))


# --- Fitur Watchlist  ---

@app.route('/watchlist')
@login_required
def watchlist():
    stocks = Stock.query.filter_by(user_id=current_user.id).order_by(Stock.ticker).all()
    if stocks:
        ticker_list = [stock.ticker + ".JK" for stock in stocks]
        try:
            data = yf.download(tickers=ticker_list, period="5d", group_by='ticker', progress=False)
            for stock in stocks:
                ticker_jk = stock.ticker + ".JK"
                stock.harga_terbaru = None
                stock.status = "N/A"
                stock.status_color = "secondary"

                if ticker_jk in data.columns:
                    close_prices = data[ticker_jk]['Close'].dropna()
                    if not close_prices.empty:
                        harga_terbaru = close_prices.iloc[-1]
                        stock.harga_terbaru = harga_terbaru
                        if harga_terbaru <= stock.harga_cut_loss and stock.tanggal_cut_loss is None:
                            stock.tanggal_cut_loss = date.today()
                        if harga_terbaru >= stock.harga_take_profit_1 and stock.tanggal_tp_1 is None:
                            stock.tanggal_tp_1 = date.today()
                        if stock.harga_take_profit_2 and harga_terbaru >= stock.harga_take_profit_2 and stock.tanggal_tp_2 is None:
                            stock.tanggal_tp_2 = date.today()
                        if stock.harga_take_profit_3 and harga_terbaru >= stock.harga_take_profit_3 and stock.tanggal_tp_3 is None:
                            stock.tanggal_tp_3 = date.today()
                        if harga_terbaru <= stock.harga_cut_loss: stock.status, stock.status_color = "Cut Loss!", "danger"
                        elif stock.harga_take_profit_1 and harga_terbaru >= stock.harga_take_profit_1: stock.status, stock.status_color = "Take Profit", "success"
                        elif harga_terbaru >= stock.harga_akumulasi_bawah and harga_terbaru <= stock.harga_akumulasi_atas: stock.status, stock.status_color = "Area Akumulasi", "info"
                        else: stock.status, stock.status_color = "Monitoring", "warning"
            db.session.commit()
        except Exception as e:
            flash(f"Gagal memproses data: {e}", "danger")
    return render_template('watchlist.html', user=current_user, stocks=stocks)

# --- Rute CRUD untuk Watchlist ---

@app.route('/tambah-saham', methods=['GET', 'POST'])
@login_required
def tambah_saham():
    if request.method == 'POST':
        ticker = request.form.get('ticker').upper()
        try:
            new_stock = Stock(
                ticker=ticker,
                harga_akumulasi_bawah = float(request.form.get('harga_akumulasi_bawah')),
                harga_akumulasi_atas = float(request.form.get('harga_akumulasi_atas')),
                harga_cut_loss = float(request.form.get('harga_cut_loss')),
                harga_take_profit_1 = float(request.form.get('harga_take_profit_1')),
                harga_take_profit_2 = float(request.form.get('harga_take_profit_2')) if request.form.get('harga_take_profit_2') else None,
                harga_take_profit_3 = float(request.form.get('harga_take_profit_3')) if request.form.get('harga_take_profit_3') else None,
                user_id=current_user.id
            )
            db.session.add(new_stock)
            db.session.commit()
            flash(f'Saham {ticker} berhasil ditambahkan ke watchlist!', 'success')
        except ValueError:
            flash('Pastikan semua input harga adalah angka yang valid.', 'danger')
            return render_template('tambah_saham.html')
        return redirect(url_for('watchlist'))
    return render_template('tambah_saham.html')

@app.route('/edit-saham/<int:stock_id>', methods=['GET', 'POST'])
@login_required
def edit_saham(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    if stock.user_id != current_user.id: return redirect(url_for('watchlist'))
    if request.method == 'POST':
        try:
            stock.ticker = request.form.get('ticker').upper()
            stock.harga_akumulasi_bawah = float(request.form.get('harga_akumulasi_bawah'))
            stock.harga_akumulasi_atas = float(request.form.get('harga_akumulasi_atas'))
            stock.harga_cut_loss = float(request.form.get('harga_cut_loss'))
            stock.harga_take_profit_1 = float(request.form.get('harga_take_profit_1'))
            stock.harga_take_profit_2 = float(request.form.get('harga_take_profit_2')) if request.form.get('harga_take_profit_2') else None
            stock.harga_take_profit_3 = float(request.form.get('harga_take_profit_3')) if request.form.get('harga_take_profit_3') else None
            db.session.commit()
            flash(f'Saham {stock.ticker} berhasil diperbarui.', 'success')
        except ValueError:
            flash('Gagal memperbarui. Pastikan semua input harga adalah angka.', 'danger')
        return redirect(url_for('watchlist'))
    return render_template('edit_saham.html', stock=stock)

@app.route('/hapus-saham/<int:stock_id>', methods=['POST'])
@login_required
def hapus_saham(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    if stock.user_id != current_user.id: return redirect(url_for('watchlist'))
    db.session.delete(stock)
    db.session.commit()
    flash(f'Saham {stock.ticker} telah dihapus.', 'info')
    return redirect(url_for('watchlist'))

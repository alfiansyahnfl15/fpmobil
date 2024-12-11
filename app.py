from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your_default_secret_key")  # Use environment variable for production

# Konfigurasi MySQL
db_config = {
    "user": "ccmobil",
    "password": "mobil_000",
    "host": "fpmobilcc.mysql.database.azure.com",
    "port": 3306,
    "database": "db_merek",
}

socketio = SocketIO(app)

# Helper untuk koneksi database
def get_db_connection():
    return mysql.connector.connect(**db_config)

# Halaman utama
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM db_mobil")
        cars = cursor.fetchall()
    return render_template('index.html', cars=cars)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Username dan password harus diisi!', 'error')
            return redirect('/login')

        with get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM akun WHERE username=%s AND password=%s", (username, password))
            user = cursor.fetchone()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login berhasil!', 'success')
            return redirect('/dashboard')
        else:
            flash('Username atau password salah!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah logout.', 'success')
    return redirect('/')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Username dan password harus diisi!', 'error')
            return redirect('/register')

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO akun (username, password) VALUES (%s, %s)", (username, password))
                conn.commit()
                flash('Registrasi berhasil! Silakan login.', 'success')
        except mysql.connector.Error as err:
            flash(f'Error: {err}', 'error')
        return redirect('/login')
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Anda harus login untuk mengakses halaman ini.', 'error')
        return redirect('/login')

    role = session['role']
    return redirect(f'/dashboard/{role}')

@app.route('/dashboard/admin')
def dashboard_admin():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Akses ditolak.', 'error')
        return redirect('/')

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM db_mobil")
        cars = cursor.fetchall()
        cursor.execute("SELECT * FROM akun")
        users = cursor.fetchall()
    return render_template('dashboard_admin.html', cars=cars, users=users)

@app.route('/dashboard/user')
def dashboard_user():
    if 'user_id' not in session:
        flash('Anda harus login untuk mengakses halaman ini.', 'error')
        return redirect('/login')

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM db_mobil")
        cars = cursor.fetchall()
    return render_template('dashboard_user.html', cars=cars)

@app.route('/mobil/edit/<int:id_mobil>', methods=['GET', 'POST'])
def edit_mobil(id_mobil):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Akses ditolak.', 'error')
        return redirect('/mobil')

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM db_mobil WHERE id_mobil = %s", (id_mobil,))
        car = cursor.fetchone()

        if not car:
            flash('Mobil tidak ditemukan.', 'error')
            return redirect('/mobil')

        if request.method == 'POST':
            data = (
                request.form['nama_mobil'],
                request.form['warna'],
                request.form['merek'],
                request.form['tipe'],
                request.form['deskripsi'],
                request.form['harga'],
                request.form['image_url'],
                id_mobil,
            )
            cursor.execute("""
                UPDATE db_mobil
                SET nama_mobil = %s, warna = %s, merek = %s, tipe = %s, deskripsi = %s, harga = %s, image_url = %s
                WHERE id_mobil = %s
            """, data)
            conn.commit()
            flash('Mobil berhasil diperbarui.', 'success')
            return redirect('/mobil')

    return render_template('edit_mobil.html', car=car)

@app.route('/forum', methods=['GET'])
def forum():
    if 'user_id' not in session:
        return redirect('/login')

    with get_db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username FROM akun WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()

        cursor.execute("""
            SELECT m.message, u.username, m.timestamp
            FROM messages m
            JOIN akun u ON m.user_id=u.id
            ORDER BY m.timestamp
        """)
        messages = cursor.fetchall()

    return render_template('forum.html', user=user, messages=messages)

@socketio.on('send_message')
def handle_send_message(data):
    message = data['message']
    user_id = session['user_id']

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO messages (user_id, message) VALUES (%s, %s)", (user_id, message))
        conn.commit()

    emit('receive_message', {'message': message, 'username': session['username']}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)

# admin.py
from flask import Flask, request, render_template_string, redirect, url_for, session
import sqlite3
from config import ADMIN_ID
import database as db

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_NAME = "lise.db"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>پنل ادمین Lise</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Tahoma, sans-serif; background: #1a3b2f; color: #eee; padding: 20px; direction: rtl; }
        .container { max-width: 1200px; margin: auto; background: #2d5a46; padding: 20px; border-radius: 15px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #4f7a65; padding: 10px; text-align: center; }
        th { background: #1f4d3a; }
        button, input[type=submit] { background: #f0a500; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; }
        .success { color: #a5d6a5; }
        .error { color: #f0a500; }
    </style>
</head>
<body>
<div class="container">
    <h1>🔐 پنل مدیریت فروشگاه Lise</h1>
    {% if not session.logged_in %}
    <form method="post">
        <input type="password" name="password" placeholder="رمز عبور" required>
        <input type="submit" value="ورود">
    </form>
    {% else %}
    <h2>💰 تراکنش‌های نیاز به تایید (کارت به کارت)</h2>
    <table>
        <tr><th>شناسه</th><th>کاربر</th><th>مبلغ</th><th>کد رهگیری</th><th>عملیات</th></tr>
        {% for tx in pending %}
        <tr>
            <td>{{ tx[0] }}</td>
            <td>{{ tx[1] }}</td>
            <td>{{ tx[2] }}</td>
            <td>{{ tx[4] }}</td>
            <td><a href="/confirm/{{ tx[0] }}">✅ تایید</a> | <a href="/reject/{{ tx[0] }}">❌ رد</a></td>
        </tr>
        {% endfor %}
    </table>
    <hr>
    <a href="/logout">🚪 خروج</a>
    {% endif %}
</div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == 'Lise@1403':
            session['logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return "رمز اشتباه است"
    return render_template_string(HTML_TEMPLATE, session=session, pending=[])

@app.route('/panel')
def admin_panel():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    db.init_db()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, method, tracking_code FROM transactions WHERE status='pending'")
    pending = c.fetchall()
    conn.close()
    return render_template_string(HTML_TEMPLATE, session=session, pending=pending)

@app.route('/confirm/<int:tx_id>')
def confirm(tx_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    db.confirm_transaction(tx_id)
    # همچنین سرویس مربوطه را از wait_payment به wait_config تغییر بده
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE services SET status='wait_config' WHERE user_id IN (SELECT user_id FROM transactions WHERE id=?) AND status='wait_payment'", (tx_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/reject/<int:tx_id>')
def reject(tx_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE transactions SET status='rejected' WHERE id=?", (tx_id,))
    c.execute("DELETE FROM services WHERE user_id IN (SELECT user_id FROM transactions WHERE id=?) AND status='wait_payment'", (tx_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
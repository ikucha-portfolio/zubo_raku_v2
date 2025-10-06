from flask import Flask, render_template
import sqlite3
from datetime import date

app = Flask(__name__)

# 一覧ページ（ホーム）
@app.route('/')
def index():
    conn = sqlite3.connect('/Users/ami/Desktop/housework.db')
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories")
    categories = cur.fetchall()
    conn.close()
    return render_template('index.html', categories=categories)

# 今日のやることページ
@app.route('/todo')
def todo():
    today = date.today().strftime("%Y/%m/%d")
    return render_template('todo.html', today=today)

@app.route('/log')
def log():
    return render_template('log.html')

# 編集ページ
@app.route('/edit')
def edit():
    return render_template('edit.html')

# 登録ページ
@app.route('/register')
def register():
    return render_template('register.html')



if __name__ == '__main__':
    app.run(debug=True)

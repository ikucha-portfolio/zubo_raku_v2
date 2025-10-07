from flask import Flask, render_template
import sqlite3
from datetime import date
from collections import defaultdict

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


@app.route('/todo')
def todo():
    today = date.today()
    weekday = today.weekday()  # 0=月曜, 6=日曜

    conn = sqlite3.connect('/Users/ami/Desktop/housework.db')
    cur = conn.cursor()

    # 🧠 今日のタスクを抽出（頻度ロジック付き）
    query = """
    SELECT c.name AS category, s.name AS subtask, s.frequency
    FROM subtasks s
    JOIN categories c ON s.category_id = c.id
    WHERE 
      (s.frequency = '毎日')
      OR (s.frequency = '3日おき' AND (julianday(?) - julianday('2025-10-07')) % 3 = 0)
      OR (s.frequency = '週一' AND ? = 5)
    ORDER BY c.id;
    """
    cur.execute(query, (today, weekday))
    rows = cur.fetchall()
    conn.close()

    # 🗂 カテゴリごとにまとめる
    grouped_tasks = defaultdict(list)
    for category, subtask, freq in rows:
        grouped_tasks[category].append({
            "subtask": subtask,
            "frequency": freq
        })

    return render_template('todo.html', today=today, grouped_tasks=grouped_tasks)



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

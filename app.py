from flask import Flask, render_template, request, redirect, url_for
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
    SELECT s.id, c.name AS category, s.name AS subtask, s.frequency
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
    for subtask_id, category, subtask, freq in rows:
        grouped_tasks[category].append({
        "id": subtask_id,   # ← ここを追加
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

# ✅★ここに追記★
from datetime import timedelta

@app.route('/update_status/<int:progress_id>', methods=['POST'])
def update_status(progress_id):
    action = request.form['status']  # 'done', 'defer', 'skip'
    today = date.today()

    conn = sqlite3.connect('/Users/ami/Desktop/housework.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT frequency FROM progress WHERE id = ?", (progress_id,))
    row = cur.fetchone()
    freq = row['frequency'] if row else '毎日'

    # 次回日の計算
    if freq == '毎日':
        next_date = today + timedelta(days=1)
    elif freq == '3日おき':
        next_date = today + timedelta(days=3)
    elif freq == '週一':
        next_date = today + timedelta(days=7)
    else:
        next_date = None

    # アクション別処理
    if action == 'done':
        cur.execute("""
            UPDATE progress
            SET is_completed = 1,
                completed_date = ?,
                next_date = ?
            WHERE id = ?
        """, (today, next_date, progress_id))

    elif action == 'defer':  # あすへ
        cur.execute("""
            UPDATE progress
            SET planned_date = DATE(planned_date, '+1 day')
            WHERE id = ?
        """, (progress_id,))

    elif action == 'skip':
        cur.execute("""
            UPDATE progress
            SET is_completed = 0,
                completed_date = NULL,
                next_date = ?
            WHERE id = ?
        """, (next_date, progress_id))

    conn.commit()
    conn.close()
    return redirect(url_for('todo'))

if __name__ == '__main__':
    app.run(debug=True)

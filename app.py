

from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date
from collections import defaultdict

app = Flask(__name__)

# 一覧ページ（ホーム）
@app.route('/')
def index():
    conn = sqlite3.connect('/Users/ami/Desktop/housework.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🧠 subtasks と categories を JOIN（display_labelも含める）
    cur.execute("""
        SELECT s.name AS subtask, s.frequency, c.name AS category, c.display_label
        FROM subtasks s
        JOIN categories c ON s.category_id = c.id
        ORDER BY 
          CASE s.frequency
            WHEN '毎日' THEN 1
            WHEN '3日おき' THEN 2
            WHEN '週一' THEN 3
            ELSE 4
          END,
          c.id;
    """)
    rows = cur.fetchall()

    # ✅ 進捗率計算（is_completed 使用／subtask_idベース）
    cur.execute("SELECT COUNT(*) FROM progress;")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM progress WHERE is_completed = 1;")
    done = cur.fetchone()[0]

    conn.close()

    percent = int((done / total) * 100) if total > 0 else 0

    # 🗂 頻度ごとにまとめつつ、自然な表示名を作成
    from collections import defaultdict
    grouped_tasks = defaultdict(list)

    for row in rows:
        category = row["category"]
        subtask = row["subtask"]
        label = row["display_label"]

        # カテゴリ別の結合ルール
        if category == "料理":
            display_name = f"{subtask}{label}"      # 朝ごはん／昼ごはん
        elif "洗濯" in category and "寝具" in category:
            display_name = f"{label}{subtask}"      # 寝具を干す／寝具を洗う
        else:
            display_name = f"{subtask}{label}"      # 玄関掃除／トイレ掃除など

        grouped_tasks[row["frequency"]].append({
            "display_name": display_name,
            "category": category
        })

    # ✅ HTMLへ渡す
    return render_template(
        'index.html',
        grouped_tasks=grouped_tasks,
        percent=percent,
        current_date=date.today().strftime("%Y年%m月%d日 %A")
    )

@app.route('/todo')
def todo():
    today = date.today()
    weekday = today.weekday()  # 0=月曜, 6=日曜

    conn = sqlite3.connect('/Users/ami/Desktop/housework.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🧠 progressテーブルとJOINして完了状態を取得
    query = """
    SELECT 
        s.id AS subtask_id,
        c.name AS category,
        s.name AS subtask,
        s.frequency,
        p.is_completed
    FROM subtasks s
    JOIN categories c ON s.category_id = c.id
    LEFT JOIN progress p ON s.id = p.subtask_id
    WHERE 
        (s.frequency = '毎日')
        OR (s.frequency = '3日おき' AND (julianday(?) - julianday('2025-10-07')) % 3 = 0)
        OR (s.frequency = '週一' AND ? = 5)
    ORDER BY c.id;
    """

    cur.execute(query, (today, weekday))
    rows = cur.fetchall()
    conn.close()

    # 🧩 完了・未完了に分ける
    incomplete_tasks = []
    completed_tasks = []

    for row in rows:
        task_data = {
            "id": row["subtask_id"],
            "category": row["category"],
            "subtask": row["subtask"],
            "frequency": row["frequency"]
        }
        if row["is_completed"] == 1:
            completed_tasks.append(task_data)
        else:
            incomplete_tasks.append(task_data)

    return render_template(
        'todo.html',
        today=today,
        incomplete_tasks=incomplete_tasks,
        completed_tasks=completed_tasks
    )




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

# 🟢 ここに追加！！
@app.route('/add_task', methods=['POST'])
def add_task():
    task_name = request.form['task_name']
    category = request.form['category']
    frequency = request.form['frequency']

    conn = sqlite3.connect('/Users/ami/Desktop/housework.db')
    cur = conn.cursor()

    # カテゴリIDを取得または追加
    cur.execute("SELECT id FROM categories WHERE name = ?", (category,))
    category_row = cur.fetchone()

    if category_row:
        category_id = category_row[0]
    else:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (category,))
        category_id = cur.lastrowid

    # subtasksテーブルに新規タスク追加
    cur.execute(
        "INSERT INTO subtasks (name, category_id, frequency) VALUES (?, ?, ?)",
        (task_name, category_id, frequency)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('index'))
# 🟢 ここまで追加

# ✅★ここに追記★
from datetime import timedelta

from datetime import timedelta

@app.route('/update_status/<int:subtask_id>', methods=['POST'])
def update_status(subtask_id):
    action = request.form['status']  # 'done', 'defer', 'skip'
    today = date.today()

    conn = sqlite3.connect('/Users/ami/Desktop/housework.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🧠 progressテーブルから対象行を取得
    cur.execute("SELECT frequency, planned_date FROM progress WHERE subtask_id = ?", (subtask_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return redirect(url_for('todo'))

    freq = row['frequency']
    planned_date = row['planned_date']

    # 🗓 次回日のロジック
    if freq == '毎日':
        next_date = today + timedelta(days=1)
    elif freq == '3日おき':
        next_date = today + timedelta(days=3)
    elif freq == '週一':
        next_date = today + timedelta(days=7)
    else:
        next_date = today

    # 🎯 各アクションごとの処理
    if action == 'done':
        cur.execute("""
            UPDATE progress
            SET is_completed = 1,
                completed_date = ?,
                next_date = ?,
                planned_date = ?
            WHERE subtask_id = ?
        """, (today, next_date, next_date, subtask_id))

    elif action == 'defer':  # → あすへ
        cur.execute("""
            UPDATE progress
            SET planned_date = DATE(?, '+1 day')
            WHERE subtask_id = ?
        """, (today, subtask_id))


    elif action == 'skip':  # ✕ スキップ
        cur.execute("""
            UPDATE progress
            SET is_completed = 0,
                completed_date = NULL,
                next_date = ?
            WHERE subtask_id = ?
        """, (next_date, subtask_id))

    conn.commit()
    conn.close()

    return redirect(url_for('todo'))

if __name__ == '__main__':
    app.run(debug=True)

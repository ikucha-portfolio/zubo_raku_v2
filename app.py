from flask import Flask, render_template, request, redirect, url_for
import sqlite3, os
from datetime import date, timedelta
from collections import defaultdict

app = Flask(__name__)

# ✅ 共通で使える DBパス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "housework.db")

# 一覧ページ（ホーム）
@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

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

    cur.execute("SELECT COUNT(*) FROM progress;")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM progress WHERE is_completed = 1;")
    done = cur.fetchone()[0]
    conn.close()

    percent = int((done / total) * 100) if total > 0 else 0

    grouped_tasks = defaultdict(list)
    for row in rows:
        category = row["category"]
        subtask = row["subtask"]
        label = row["display_label"]

        if category == "料理":
            display_name = f"{subtask}{label}"
        elif "洗濯" in category and "寝具" in category:
            display_name = f"{label}{subtask}"
        else:
            display_name = f"{subtask}{label}"

        grouped_tasks[row["frequency"]].append({
            "display_name": display_name,
            "category": category
        })

    return render_template(
        'index.html',
        grouped_tasks=grouped_tasks,
        percent=percent,
        current_date=date.today().strftime("%Y年%m月%d日 %A")
    )


@app.route('/todo')
def todo():
    today = date.today()
    weekday = today.weekday()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = """
    SELECT 
        s.id AS subtask_id,
        c.name AS category,
        s.name AS subtask,
        s.frequency,
        p.is_completed,
        p.planned_date,
        p.next_date
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

    incomplete_tasks = []
    completed_tasks = []

    for row in rows:
        task_data = {
            "id": row["subtask_id"],
            "category": row["category"],
            "subtask": row["subtask"],
            "frequency": row["frequency"],
            "is_completed": row["is_completed"],
        }

        if row["is_completed"] == 1:
            task_data["status"] = "done"
        elif row["planned_date"] and str(row["planned_date"]) > str(today):
            task_data["status"] = "defer"
        elif row["next_date"] and str(row["next_date"]) > str(today):
            task_data["status"] = "skip"
        else:
            task_data["status"] = "normal"

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


@app.route('/edit')
def edit():
    return render_template('edit.html')


@app.route('/register')
def register():
    return render_template('register.html')


@app.route('/add_task', methods=['POST'])
def add_task():
    task_name = request.form['task_name']
    category = request.form['category']
    frequency = request.form['frequency']

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id FROM categories WHERE name = ?", (category,))
    category_row = cur.fetchone()

    if category_row:
        category_id = category_row[0]
    else:
        cur.execute("INSERT INTO categories (name) VALUES (?)", (category,))
        category_id = cur.lastrowid

    cur.execute(
        "INSERT INTO subtasks (name, category_id, frequency) VALUES (?, ?, ?)",
        (task_name, category_id, frequency)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('index'))


@app.route('/update_status/<int:subtask_id>', methods=['POST'])
def update_status(subtask_id):
    action = request.form['status']
    today = date.today()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT frequency, planned_date FROM progress WHERE subtask_id = ?", (subtask_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return redirect(url_for('todo'))

    freq = row['frequency']
    planned_date = row['planned_date']

    if freq == '毎日':
        next_date = today + timedelta(days=1)
    elif freq == '3日おき':
        next_date = today + timedelta(days=3)
    elif freq == '週一':
        next_date = today + timedelta(days=7)
    else:
        next_date = today

    if action == 'done':
        cur.execute("""
            UPDATE progress
            SET is_completed = 1,
                completed_date = ?,
                next_date = ?,
                planned_date = ?
            WHERE subtask_id = ?
        """, (today, next_date, next_date, subtask_id))

    elif action == 'defer':
        cur.execute("""
            UPDATE progress
            SET planned_date = DATE(?, '+1 day')
            WHERE subtask_id = ?
        """, (today, subtask_id))

    elif action == 'skip':
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

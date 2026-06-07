from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "budgetcoach_secret_2025"


# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        gender TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        category TEXT,
        note TEXT,
        date TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budget(
        user_id INTEGER PRIMARY KEY,
        monthly_limit REAL,
        daily_target REAL DEFAULT 500
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS goals(
        user_id INTEGER PRIMARY KEY,
        streak INTEGER DEFAULT 0,
        last_date TEXT,
        points INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS avatar(
        user_id INTEGER PRIMARY KEY,
        gender TEXT,
        current_skin TEXT DEFAULT 'basic'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS owned_skins(
        user_id INTEGER,
        skin_name TEXT
    )
    """)

    db.commit()

    # Migration: add daily_target column if missing (for existing databases)
    try:
        cursor.execute("ALTER TABLE budget ADD COLUMN daily_target REAL DEFAULT 500")
        db.commit()
    except Exception:
        pass  # Column already exists


# ---------------- HELPERS ----------------
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated


def get_user_id():
    return session["user_id"]


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect("/dashboard")

    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Please fill in all fields."
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user["password"], password):
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect("/dashboard")
            else:
                error = "Invalid username or password."

    return render_template("login.html", error=error)


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        gender = request.form.get("gender", "")

        if not username or not password or not gender:
            error = "Please fill in all fields."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            db = get_db()
            cursor = db.cursor()

            cursor.execute("SELECT id FROM users WHERE username=?", (username,))
            if cursor.fetchone():
                error = "Username already taken. Choose another."
            else:
                hashed_pw = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users(username, password, gender) VALUES (?, ?, ?)",
                    (username, hashed_pw, gender)
                )
                user_id = cursor.lastrowid

                cursor.execute("INSERT INTO avatar(user_id, gender, current_skin) VALUES (?, ?, 'basic')", (user_id, gender))
                cursor.execute("INSERT INTO owned_skins(user_id, skin_name) VALUES (?, 'basic')", (user_id,))
                cursor.execute("INSERT INTO budget(user_id, monthly_limit, daily_target) VALUES (?, 0, 500)", (user_id,))
                cursor.execute("INSERT INTO goals(user_id, streak, last_date, points) VALUES (?, 0, '', 0)", (user_id,))

                db.commit()
                return redirect("/")

    return render_template("signup.html", error=error)


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    cursor = db.cursor()
    user_id = get_user_id()

    cursor.execute("SELECT username, gender FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    cursor.execute("SELECT points, streak FROM goals WHERE user_id=?", (user_id,))
    goals = cursor.fetchone()

    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND date=?", (user_id, today))
    today_total = cursor.fetchone()[0] or 0

    current_month = datetime.now().strftime("%Y-%m")
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND date LIKE ?", (user_id, f"{current_month}%"))
    month_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT monthly_limit FROM budget WHERE user_id=?", (user_id,))
    budget_row = cursor.fetchone()
    monthly_limit = budget_row["monthly_limit"] if budget_row else 0

    budget_pct = round((month_total / monthly_limit * 100), 1) if monthly_limit else 0
    budget_pct = min(budget_pct, 100)

    return render_template("dashboard.html",
        user=user,
        goals=goals,
        today_total=today_total,
        month_total=month_total,
        monthly_limit=monthly_limit,
        budget_pct=budget_pct
    )


# ---------------- ADD EXPENSE ----------------
@app.route("/add-expense", methods=["GET", "POST"])
@login_required
def add_expense():
    error = ""
    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        category = request.form.get("category", "").strip()
        note = request.form.get("note", "").strip()
        date = request.form.get("date", "")

        if amount <= 0:
            error = "Amount must be greater than 0."
        elif not category:
            error = "Please select a category."
        elif not date:
            error = "Please select a date."
        else:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO expenses(user_id, amount, category, note, date)
                VALUES (?, ?, ?, ?, ?)
            """, (get_user_id(), amount, category, note or "—", date))
            db.commit()
            return redirect("/view-expenses")

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_expense.html", error=error, today=today)


# ---------------- VIEW EXPENSES ----------------
@app.route("/view-expenses", methods=["GET", "POST"])
@login_required
def view_expenses():
    db = get_db()
    cursor = db.cursor()
    user_id = get_user_id()

    cursor.execute("""
        SELECT id, amount, category, note, date
        FROM expenses WHERE user_id=? ORDER BY date DESC
    """, (user_id,))
    expenses = cursor.fetchall()

    total = sum(exp["amount"] for exp in expenses)

    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    current_month = datetime.now().strftime("%Y-%m")

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND date=?", (user_id, today))
    daily_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND date>=?", (user_id, week_ago))
    weekly_total = cursor.fetchone()[0] or 0

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND date LIKE ?", (user_id, f"{current_month}%"))
    monthly_total = cursor.fetchone()[0] or 0

    # Category breakdown for charts
    cursor.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses WHERE user_id=? AND date LIKE ?
        GROUP BY category ORDER BY total DESC
    """, (user_id, f"{current_month}%"))
    category_data = cursor.fetchall()
    chart_labels = [r["category"] for r in category_data]
    chart_values = [r["total"] for r in category_data]
    top_monthly = chart_labels[0] if chart_labels else "None"

    # Daily spending last 7 days for line chart
    cursor.execute("""
        SELECT date, SUM(amount) as total
        FROM expenses WHERE user_id=? AND date>=?
        GROUP BY date ORDER BY date ASC
    """, (user_id, week_ago))
    daily_rows = cursor.fetchall()
    daily_dates = [r["date"] for r in daily_rows]
    daily_amounts = [r["total"] for r in daily_rows]

    # Budget
    if request.method == "POST" and "limit" in request.form:
        try:
            limit_val = float(request.form["limit"])
            if limit_val > 0:
                cursor.execute("""
                    INSERT INTO budget(user_id, monthly_limit)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET monthly_limit=excluded.monthly_limit
                """, (user_id, limit_val))
                db.commit()
        except ValueError:
            pass

    cursor.execute("SELECT monthly_limit, daily_target FROM budget WHERE user_id=?", (user_id,))
    budget_row = cursor.fetchone()
    monthly_limit = budget_row["monthly_limit"] if budget_row else 0
    daily_target = budget_row["daily_target"] if budget_row else 500

    warning = ""
    if monthly_limit and monthly_total > monthly_limit:
        warning = "🚨 Monthly limit exceeded!"
    elif monthly_limit and weekly_total > monthly_limit / 4:
        warning = "⚠️ High weekly spending detected!"
    elif monthly_limit and daily_total > monthly_limit / 30:
        warning = "⚠️ Daily spending is unusually high!"

    today_day = datetime.now().day
    predicted_month_end = round((monthly_total / today_day) * 30, 2) if today_day else monthly_total
    possible_saving = round(monthly_limit - predicted_month_end, 2) if monthly_limit else 0

    suggestion = ""
    if top_monthly == "Food":
        suggestion = "Food is your top expense. Try reducing outside meals and snacks."
    elif top_monthly == "Shopping":
        suggestion = "Shopping is your biggest spend. Consider a 24-hour rule before purchases."
    elif top_monthly == "Travel":
        suggestion = "Travel costs are high. Plan routes and use public transport where possible."
    elif monthly_limit and monthly_total > monthly_limit * 0.8:
        suggestion = "You've used over 80% of your monthly budget. Slow down spending."
    elif not expenses:
        suggestion = "No expenses yet. Start tracking to get smart suggestions!"
    else:
        suggestion = "Your spending looks balanced this month. Keep it up! 🎉"

    return render_template("view_expenses.html",
        expenses=expenses,
        total=total,
        daily_total=daily_total,
        weekly_total=weekly_total,
        monthly_total=monthly_total,
        monthly_limit=monthly_limit,
        daily_target=daily_target,
        warning=warning,
        predicted_month_end=predicted_month_end,
        possible_saving=possible_saving,
        suggestion=suggestion,
        chart_labels=chart_labels,
        chart_values=chart_values,
        daily_dates=daily_dates,
        daily_amounts=daily_amounts
    )


# ---------------- DELETE EXPENSE ----------------
@app.route("/delete-expense/<int:expense_id>")
@login_required
def delete_expense(expense_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, get_user_id()))
    db.commit()
    return redirect("/view-expenses")


# ---------------- EDIT EXPENSE ----------------
@app.route("/edit-expense/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    db = get_db()
    cursor = db.cursor()
    error = ""

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            amount = 0

        category = request.form.get("category", "").strip()
        note = request.form.get("note", "").strip()
        date = request.form.get("date", "")

        if amount <= 0:
            error = "Amount must be greater than 0."
        elif not category or not date:
            error = "Please fill in all required fields."
        else:
            cursor.execute("""
                UPDATE expenses SET amount=?, category=?, note=?, date=?
                WHERE id=? AND user_id=?
            """, (amount, category, note or "—", date, expense_id, get_user_id()))
            db.commit()
            return redirect("/view-expenses")

    cursor.execute("""
        SELECT id, amount, category, note, date FROM expenses
        WHERE id=? AND user_id=?
    """, (expense_id, get_user_id()))
    expense = cursor.fetchone()

    if not expense:
        return redirect("/view-expenses")

    return render_template("edit_expense.html", expense=expense, error=error)


# ---------------- GOALS ----------------
@app.route("/goals")
@login_required
def goals():
    db = get_db()
    cursor = db.cursor()
    user_id = get_user_id()

    DAILY_TARGET = 500  # Fixed — not user-configurable

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    cursor.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND date=?", (user_id, today))
    today_spent = cursor.fetchone()[0] or 0

    cursor.execute("SELECT streak, last_date, points FROM goals WHERE user_id=?", (user_id,))
    data = cursor.fetchone()

    if not data:
        streak, last_date, points = 0, "", 0
        cursor.execute("INSERT INTO goals(user_id, streak, last_date, points) VALUES (?, 0, \'\', 0)", (user_id,))
        db.commit()
    else:
        streak = data["streak"]
        last_date = data["last_date"]
        points = data["points"]

    achieved = today_spent <= DAILY_TARGET

    if last_date != today:
        # Streak resets if user skipped a day entirely
        if last_date != yesterday and last_date != "":
            streak = 0

        if achieved:
            streak += 1
            # 1 point every 10-day streak
            if streak % 10 == 0:
                points += 1
        else:
            streak = 0

        cursor.execute(
            "UPDATE goals SET streak=?, last_date=?, points=? WHERE user_id=?",
            (streak, today, points, user_id)
        )
        db.commit()

    # Last 7 days history
    cursor.execute("""
        SELECT date, SUM(amount) as total FROM expenses
        WHERE user_id=? AND date >= ?
        GROUP BY date
    """, (user_id, (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")))
    spent_by_day = {r["date"]: r["total"] for r in cursor.fetchall()}

    week_history = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        spent = spent_by_day.get(d, 0)
        week_history.append({
            "date": d,
            "day": (datetime.now() - timedelta(days=i)).strftime("%a"),
            "spent": spent,
            "ok": spent <= DAILY_TARGET
        })

    return render_template("goals.html",
        daily_target=DAILY_TARGET,
        today_spent=today_spent,
        achieved=achieved,
        streak=streak,
        points=points,
        week_history=week_history
    )


# ---------------- PERSONALIZATION ----------------
@app.route("/personalization", methods=["GET", "POST"])
@login_required
def personalization():
    db = get_db()
    cursor = db.cursor()
    user_id = get_user_id()

    cursor.execute("SELECT points FROM goals WHERE user_id=?", (user_id,))
    goal_row = cursor.fetchone()
    points = goal_row["points"] if goal_row else 0

    cursor.execute("SELECT gender FROM users WHERE id=?", (user_id,))
    gender = cursor.fetchone()["gender"]

    cursor.execute("SELECT current_skin FROM avatar WHERE user_id=?", (user_id,))
    skin_row = cursor.fetchone()
    current_skin = skin_row["current_skin"] if skin_row else "basic"

    cursor.execute("SELECT skin_name FROM owned_skins WHERE user_id=?", (user_id,))
    owned = [x["skin_name"] for x in cursor.fetchall()]

    if gender == "Female":
        skins = {"formal": 1, "churidar": 2, "traditional": 3, "party wear": 4}
    else:
        skins = {"casuals": 1, "traditional": 2, "chill": 3, "suit": 4}

    message = ""
    msg_type = ""

    if request.method == "POST":
        selected_skin = request.form.get("skin", "")

        if "buy" in request.form and selected_skin in skins:
            cost = skins[selected_skin]
            if selected_skin in owned:
                message = "You already own this skin."
                msg_type = "warn"
            elif points >= cost:
                points -= cost
                cursor.execute("UPDATE goals SET points=? WHERE user_id=?", (points, user_id))
                cursor.execute("INSERT INTO owned_skins(user_id, skin_name) VALUES (?, ?)", (user_id, selected_skin))
                db.commit()
                owned.append(selected_skin)
                message = f"'{selected_skin.title()}' skin unlocked!"
                msg_type = "success"
            else:
                message = f"Not enough points. Need {cost}, have {points}."
                msg_type = "error"

        elif "wear" in request.form and selected_skin in owned:
            cursor.execute("UPDATE avatar SET current_skin=? WHERE user_id=?", (selected_skin, user_id))
            db.commit()
            current_skin = selected_skin
            message = "Avatar updated! Looking great!"
            msg_type = "success"

    return render_template("personalization.html",
        points=points,
        gender=gender,
        skins=skins,
        owned=owned,
        current_skin=current_skin,
        message=message,
        msg_type=msg_type
    )


# ---------------- SETTINGS ----------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db = get_db()
    cursor = db.cursor()
    user_id = get_user_id()
    message = ""
    msg_type = ""

    if request.method == "POST":
        if "new_username" in request.form and request.form["new_username"].strip():
            new_uname = request.form["new_username"].strip()
            if len(new_uname) < 3:
                message = "Username must be at least 3 characters."
                msg_type = "error"
            else:
                cursor.execute("SELECT id FROM users WHERE username=? AND id!=?", (new_uname, user_id))
                if cursor.fetchone():
                    message = "Username already taken."
                    msg_type = "error"
                else:
                    cursor.execute("UPDATE users SET username=? WHERE id=?", (new_uname, user_id))
                    db.commit()
                    session["username"] = new_uname
                    message = "Username updated successfully."
                    msg_type = "success"

        elif "new_password" in request.form and request.form["new_password"].strip():
            new_pw = request.form["new_password"]
            current_pw = request.form.get("current_password", "")
            cursor.execute("SELECT password FROM users WHERE id=?", (user_id,))
            stored = cursor.fetchone()["password"]

            if not check_password_hash(stored, current_pw):
                message = "Current password is incorrect."
                msg_type = "error"
            elif len(new_pw) < 6:
                message = "New password must be at least 6 characters."
                msg_type = "error"
            else:
                cursor.execute("UPDATE users SET password=? WHERE id=?", (generate_password_hash(new_pw), user_id))
                db.commit()
                message = "Password updated successfully."
                msg_type = "success"

    cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
    username = cursor.fetchone()["username"]

    return render_template("settings.html", username=username, message=message, msg_type=msg_type)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RUN ----------------
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "budgetcoach_secret"


# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect("database.db")


def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
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
        monthly_limit REAL
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


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (request.form["username"], request.form["password"])
        )

        user = cursor.fetchone()

        if user:
            session["user_id"] = user[0]
            return redirect("/dashboard")

    return render_template("login.html")


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        gender = request.form["gender"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO users(username, password, gender) VALUES (?, ?, ?)",
            (username, password, gender)
        )

        user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO avatar(user_id, gender, current_skin)
            VALUES (?, ?, 'basic')
        """, (user_id, gender))

        cursor.execute("""
            INSERT INTO owned_skins(user_id, skin_name)
            VALUES (?, 'basic')
        """, (user_id,))

        db.commit()

        return redirect("/")

    return render_template("signup.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ---------------- ADD EXPENSE ----------------
@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO expenses(user_id, amount, category, note, date)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            request.form["amount"],
            request.form["category"],
            request.form["note"],
            request.form["date"]
        ))

        db.commit()
        return redirect("/view-expenses")

    return render_template("add_expense.html")


# ---------------- VIEW EXPENSES ----------------
@app.route("/view-expenses", methods=["GET", "POST"])
def view_expenses():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    user_id = session["user_id"]

    cursor.execute("""
        SELECT id, amount, category, note, date
        FROM expenses
        WHERE user_id=?
        ORDER BY date DESC
    """, (user_id,))
    expenses = cursor.fetchall()

    total = sum(exp[1] for exp in expenses)

    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    current_month = datetime.now().strftime("%Y-%m")

    # DAILY
    cursor.execute("""
        SELECT SUM(amount), category
        FROM expenses
        WHERE user_id=? AND date=?
        GROUP BY category
    """, (user_id, today))
    daily_data = cursor.fetchall()
    daily_total = sum(d[0] for d in daily_data) if daily_data else 0

    # WEEKLY
    cursor.execute("""
        SELECT SUM(amount), category
        FROM expenses
        WHERE user_id=? AND date>=?
        GROUP BY category
    """, (user_id, week_ago))
    weekly_data = cursor.fetchall()
    weekly_total = sum(w[0] for w in weekly_data) if weekly_data else 0

    # MONTHLY
    cursor.execute("""
        SELECT SUM(amount), category
        FROM expenses
        WHERE user_id=? AND date LIKE ?
        GROUP BY category
    """, (user_id, f"{current_month}%"))
    monthly_data = cursor.fetchall()
    monthly_total = sum(m[0] for m in monthly_data) if monthly_data else 0
    top_monthly = max(monthly_data, key=lambda x: x[0])[1] if monthly_data else "None"

    # BUDGET
    if request.method == "POST" and "limit" in request.form:
        cursor.execute("""
            INSERT INTO budget(user_id, monthly_limit)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET monthly_limit=excluded.monthly_limit
        """, (user_id, request.form["limit"]))
        db.commit()

    cursor.execute("SELECT monthly_limit FROM budget WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    monthly_limit = result[0] if result else 0

    # WARNING
    warning = ""
    if monthly_limit and monthly_total > monthly_limit:
        warning = "🚨 Monthly limit exceeded!"
    elif monthly_limit and weekly_total > monthly_limit / 4:
        warning = "⚠ High weekly spending!"
    elif monthly_limit and daily_total > monthly_limit / 30:
        warning = "⚠ High daily spending!"

    # SAVINGS PREDICTION
    today_day = datetime.now().day
    predicted_month_end = round((monthly_total / today_day) * 30, 2) if today_day != 0 else monthly_total
    possible_saving = monthly_limit - predicted_month_end if monthly_limit else 0

    # SMART SUGGESTION
    suggestion = ""

    if top_monthly == "Food":
        suggestion = "You are spending most on Food. Try reducing outside snacks/meals."
    elif top_monthly == "Shopping":
        suggestion = "Shopping is your top expense. Avoid unnecessary purchases."
    elif top_monthly == "Travel":
        suggestion = "Travel cost is high this month. Plan transport efficiently."
    elif monthly_limit and monthly_total > monthly_limit * 0.8:
        suggestion = "Warning: You already used more than 80% of your monthly budget."
    else:
        suggestion = "Good job! Your spending pattern looks balanced."

    return render_template(
        "view_expenses.html",
        expenses=expenses,
        total=total,
        daily_total=daily_total,
        weekly_total=weekly_total,
        monthly_total=monthly_total,
        monthly_limit=monthly_limit,
        warning=warning,
        predicted_month_end=predicted_month_end,
        possible_saving=possible_saving,
        suggestion=suggestion
    )


# ---------------- DELETE EXPENSE ----------------
@app.route("/delete-expense/<int:expense_id>")
def delete_expense(expense_id):
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, session["user_id"]))
    db.commit()

    return redirect("/view-expenses")


# ---------------- EDIT EXPENSE ----------------
@app.route("/edit-expense/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        cursor.execute("""
            UPDATE expenses
            SET amount=?, category=?, note=?, date=?
            WHERE id=? AND user_id=?
        """, (
            request.form["amount"],
            request.form["category"],
            request.form["note"],
            request.form["date"],
            expense_id,
            session["user_id"]
        ))
        db.commit()
        return redirect("/view-expenses")

    cursor.execute("""
        SELECT id, amount, category, note, date
        FROM expenses
        WHERE id=? AND user_id=?
    """, (expense_id, session["user_id"]))

    expense = cursor.fetchone()

    return render_template("edit_expense.html", expense=expense)

    
# ---------------- GOALS ----------------
@app.route("/goals")
def goals():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    user_id = session["user_id"]

    daily_target = 100
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT SUM(amount) FROM expenses
        WHERE user_id=? AND date=?
    """, (user_id, today))

    result = cursor.fetchone()
    today_spent = result[0] if result[0] else 0

    cursor.execute("""
        SELECT streak, last_date, points
        FROM goals
        WHERE user_id=?
    """, (user_id,))
    data = cursor.fetchone()

    if not data:
        streak = 0
        last_date = ""
        points = 0

        cursor.execute("""
            INSERT INTO goals(user_id, streak, last_date, points)
            VALUES (?, 0, '', 0)
        """, (user_id,))
        db.commit()
    else:
        streak, last_date, points = data

    achieved = today_spent <= daily_target

    if last_date != today:
        if achieved:
            streak += 1
            if streak % 10 == 0:
                points += 1
        else:
            streak = 0

        cursor.execute("""
            UPDATE goals
            SET streak=?, last_date=?, points=?
            WHERE user_id=?
        """, (streak, today, points, user_id))
        db.commit()

    return render_template(
        "goals.html",
        daily_target=daily_target,
        today_spent=today_spent,
        achieved=achieved,
        streak=streak
    )


# ---------------- PERSONALIZATION ----------------
@app.route("/personalization", methods=["GET", "POST"])
def personalization():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    user_id = session["user_id"]

    # -------- GOALS / POINTS --------
    cursor.execute("SELECT points FROM goals WHERE user_id=?", (user_id,))
    goal_row = cursor.fetchone()

    if not goal_row:
        cursor.execute("""
            INSERT INTO goals(user_id, streak, last_date, points)
            VALUES (?, 0, '', 0)
        """, (user_id,))
        db.commit()
        points = 0
    else:
        points = goal_row[0]

    # -------- GET GENDER FROM USERS TABLE --------
    cursor.execute("SELECT gender FROM users WHERE id=?", (user_id,))
    gender = cursor.fetchone()[0]

    # -------- GET CURRENT SKIN FROM AVATAR TABLE --------
    cursor.execute("SELECT current_skin FROM avatar WHERE user_id=?", (user_id,))
    skin_row = cursor.fetchone()

    if not skin_row:
        cursor.execute("""
            INSERT INTO avatar(user_id, gender, current_skin)
            VALUES (?, ?, 'basic')
        """, (user_id, gender))

        cursor.execute("""
            INSERT INTO owned_skins(user_id, skin_name)
            VALUES (?, 'basic')
        """, (user_id,))

        db.commit()
        current_skin = "basic"
    else:
        current_skin = skin_row[0]

    # -------- OWNED SKINS --------
    cursor.execute("SELECT skin_name FROM owned_skins WHERE user_id=?", (user_id,))
    owned = [x[0] for x in cursor.fetchall()]

    # -------- SKINS BY GENDER --------
    if gender == "Girl":
        skins = {
            "formal": 1,
            "churidar": 2,
            "saree": 3,
            "party": 4
        }
    else:
        skins = {
            "casual": 1,
            "mundu": 2,
            "baggy": 3,
            "rich": 4
        }

    message = ""

    # -------- BUY / WEAR --------
    if request.method == "POST":
        selected_skin = request.form["skin"]

        if "buy" in request.form:
            cost = skins[selected_skin]

            if selected_skin not in owned and points >= cost:
                points -= cost

                cursor.execute(
                    "UPDATE goals SET points=? WHERE user_id=?",
                    (points, user_id)
                )

                cursor.execute(
                    "INSERT INTO owned_skins(user_id, skin_name) VALUES (?, ?)",
                    (user_id, selected_skin)
                )

                db.commit()
                owned.append(selected_skin)
                message = "Skin Purchased!"

            else:
                message = "Not enough points or already owned."

        if "wear" in request.form:
            if selected_skin in owned:
                cursor.execute(
                    "UPDATE avatar SET current_skin=? WHERE user_id=?",
                    (selected_skin, user_id)
                )
                db.commit()
                current_skin = selected_skin
                message = "Avatar Updated!"

    return render_template(
        "personalization.html",
        points=points,
        gender=gender,
        skins=skins,
        owned=owned,
        current_skin=current_skin,
        message=message
    )
# ---------------- SETTINGS ----------------
@app.route("/settings", methods=["GET", "POST"])
def settings():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    user_id = session["user_id"]
    message = ""

    if request.method == "POST":

        if "new_username" in request.form and request.form["new_username"] != "":
            cursor.execute(
                "UPDATE users SET username=? WHERE id=?",
                (request.form["new_username"], user_id)
            )
            db.commit()
            message = "Username Updated"

        if "new_password" in request.form and request.form["new_password"] != "":
            cursor.execute(
                "UPDATE users SET password=? WHERE id=?",
                (request.form["new_password"], user_id)
            )
            db.commit()
            message = "Password Updated"

    cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
    username = cursor.fetchone()[0]

    return render_template("settings.html", username=username, message=message)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- RUN ----------------
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
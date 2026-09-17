# BudgetCoach

A personal finance management web application built with Flask and SQLite.

## Overview

BudgetCoach helps users track daily expenses, set monthly budgets, and stay motivated through a streak-based gamification system. Users earn points by maintaining daily spending discipline and spend them to unlock avatar customizations.

## Features

- **Expense Tracking** — Add, edit, and delete expenses with category tagging
- **Budget Management** — Set a monthly spending limit with real-time progress tracking
- **Visual Analytics** — Monthly category breakdown (doughnut chart) and 7-day spending trend (line chart)
- **Savings Prediction** — Projects month-end spending based on current pace
- **Smart Suggestions** — Contextual advice based on spending patterns
- **Streak System** — Daily ₹500 target; consecutive days build a streak
- **Points & Avatar Shop** — Every 10-day streak earns 1 point; spend points to unlock gender-based avatar skins
- **Secure Authentication** — Passwords hashed using Werkzeug's PBKDF2-SHA256

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Database | SQLite |
| Frontend | HTML, CSS, Jinja2 |
| Charts | Chart.js |
| Security | Werkzeug (password hashing) |

## Project Structure

```
BudgetCoach/
├── app.py                  # Main application — routes and logic
├── database.db             # SQLite database (auto-created on first run)
├── requirements.txt        # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css       # Dark theme stylesheet
│   └── images/             # Avatar images
└── templates/
    ├── login.html
    ├── signup.html
    ├── dashboard.html
    ├── add_expense.html
    ├── view_expenses.html
    ├── edit_expense.html
    ├── goals.html
    ├── personalization.html
    └── settings.html
```

## Setup & Run

**1. Install dependencies**
```bash
python -m pip install -r requirements.txt
```

**2. Run the app**
```bash
python app.py
```

**3. Open in browser**
```
http://127.0.0.1:5001
```

## Database Schema

- **users** — id, username, password (hashed), gender
- **expenses** — id, user_id, amount, category, note, date
- **budget** — user_id, monthly_limit
- **goals** — user_id, streak, last_date, points
- **avatar** — user_id, gender, current_skin
- **owned_skins** — user_id, skin_name

## Gamification Logic

1. Daily target is fixed at ₹500
2. Spending under ₹500 on a given day counts as a successful day
3. Consecutive successful days build a streak
4. Every 10-day streak awards 1 point
5. Missing a day resets the streak to 0
6. Points are spent in the Personalization page to unlock avatar skins

## Developer

**Mekhana Rajesh**  
MCA Student, Cochin University of Science and Technology (CUSAT)  
[GitHub](https://github.com/mekhanaa) · [LinkedIn](https://linkedin.com/in/mekhana-rajesh)

# Test change

Testing my GitHub contribution.

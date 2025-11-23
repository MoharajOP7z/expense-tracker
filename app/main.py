import os
import sqlite3
from datetime import date, datetime
from calendar import monthrange

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------- CONFIG ----------------
DB_DIR = "data"
DB_FILE = os.path.join(DB_DIR, "expenses.db")
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

st.set_page_config(page_title="Expense Tracker", page_icon="💰", layout="wide")

# ---------- Constants / categories ----------
CATEGORIES = ["Food", "Transport", "Shopping", "Rent", "Bills", "Subscriptions", "Health", "Other"]

# ---------- DB helpers ----------
def get_connection():
    return sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)


def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dt TEXT NOT NULL,
        type TEXT NOT NULL,
        category TEXT,
        description TEXT,
        amount REAL NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(category, year, month)
    )
    """)
    conn.commit()
    conn.close()


# Budget helpers
def set_budget(category, year, month, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO budgets (category, year, month, amount)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(category, year, month) DO UPDATE SET amount=excluded.amount
        """,
        (category, int(year), int(month), float(amount)),
    )
    conn.commit()
    conn.close()


def get_budgets_for_month(year, month):
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM budgets WHERE year=? AND month=?", conn, params=(int(year), int(month))
        )
    except Exception:
        df = pd.DataFrame(columns=["id", "category", "year", "month", "amount"])
    finally:
        conn.close()
    return df


def get_budget_for_category_month(category, year, month):
    conn = get_connection()
    c = conn.cursor()
    row = c.execute(
        "SELECT amount FROM budgets WHERE category=? AND year=? AND month=?",
        (category, int(year), int(month)),
    ).fetchone()
    conn.close()
    return float(row[0]) if row else None


# Expense helpers
def add_expense(dt, tx_type, category, description, amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO expenses (dt, type, category, description, amount) VALUES (?, ?, ?, ?, ?)",
        (dt.isoformat(), tx_type, category, description, float(amount)),
    )
    conn.commit()
    conn.close()


def load_expenses_df():
    conn = get_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM expenses", conn)
        if "dt" in df.columns:
            df["dt"] = pd.to_datetime(df["dt"])
    except Exception:
        df = pd.DataFrame(columns=["id", "dt", "type", "category", "description", "amount"])
    finally:
        conn.close()
    return df


# initialize DB and load data
init_db()

# ---------- UI: Header ----------
st.title("💰 Expense Tracker")
st.write("Welcome to your personal expense tracker app!")

# define today once
today = date.today()

# ---------- SIDEBAR: Budget form ----------
st.sidebar.header("Set Monthly Budget")
sel_category = st.sidebar.selectbox("Category", CATEGORIES)
sel_year = st.sidebar.number_input("Year", value=today.year, step=1)
sel_month = st.sidebar.number_input("Month", value=today.month, min_value=1, max_value=12, step=1)
sel_amount = st.sidebar.number_input("Budget Amount (₹)", min_value=0.0, step=100.0, format="%.2f")

if st.sidebar.button("Save Budget"):
    if sel_amount <= 0:
        st.sidebar.error("Budget amount must be > 0")
    else:
        set_budget(sel_category, sel_year, sel_month, sel_amount)
        st.sidebar.success(f"Budget saved for {sel_category} — ₹{sel_amount:,.2f}")

# ---------- SIDEBAR: Add Expense form ----------
st.sidebar.markdown("---")
st.sidebar.header("Add Expense / Income")
with st.sidebar.form("add_expense_form", clear_on_submit=True):
    ex_date = st.date_input("Date", value=today)
    ex_type = st.selectbox("Type", ["expense", "income"])
    ex_category = st.selectbox("Category", CATEGORIES)
    ex_description = st.text_input("Description")
    ex_amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0, format="%.2f")
    submitted = st.form_submit_button("Add Transaction")

if submitted:
    if ex_amount <= 0:
        st.sidebar.error("Amount must be > 0")
    else:
        add_expense(ex_date, ex_type, ex_category, ex_description, ex_amount)
        st.sidebar.success(f"{ex_type.title()} added: ₹{ex_amount:,.2f}")
        st.experimental_rerun()

# reload data after potential writes
df = load_expenses_df()

# ---------- Main: Budgets display ----------
current_year = today.year
current_month = today.month

bud_df = get_budgets_for_month(current_year, current_month)

st.subheader(f"Budgets — {current_month}/{current_year}")

if not bud_df.empty:
    # compute spent per category for this month
    if not df.empty:
        df_this_month = df[(df["dt"].dt.year == current_year) & (df["dt"].dt.month == current_month)]
    else:
        df_this_month = pd.DataFrame(columns=df.columns)

    spent_by_cat = (
        df_this_month[df_this_month["type"] == "expense"]
        .groupby("category")["amount"]
        .sum()
        .reset_index()
    )

    merged = pd.merge(bud_df, spent_by_cat, how="left", on="category").fillna(0)
    merged = merged.rename(columns={"amount_x": "budget_amount", "amount_y": "spent"})

    for _, r in merged.iterrows():
        cat = r["category"]
        budget_amt = float(r["budget_amount"])
        spent = float(r["spent"])
        pct = (spent / budget_amt * 100) if budget_amt > 0 else 0
        st.markdown(f"**{cat}** — Spent: ₹{spent:,.2f} / Budget: ₹{budget_amt:,.2f} — {pct:.0f}%")
        st.progress(min(1.0, pct / 100.0))
        if budget_amt > 0 and spent > budget_amt:
            st.warning(f"Over budget in {cat}: exceeded by ₹{spent - budget_amt:,.2f}")

    # bar chart
    fig_budget = px.bar(
        merged, x="category", y=["spent", "budget_amount"], barmode="group",
        labels={"value": "Amount", "category": "Category"}, title="Spent vs Budget (this month)"
    )
    st.plotly_chart(fig_budget, use_container_width=True)
else:
    st.info("No budgets set for this month. Add budgets in the sidebar.")

# ---------- Debug / small history view ----------
st.markdown("---")
st.subheader("Expense History (recent)")
if df.empty:
    st.write("No transactions yet — add one using the sidebar.")
else:
    # show last 50 transactions
    df_display = df.sort_values(by="dt", ascending=False).head(50).copy()
    df_display["dt"] = df_display["dt"].dt.strftime("%Y-%m-%d")
    st.dataframe(df_display[["dt", "type", "category", "description", "amount"]], use_container_width=True)

# small debug
st.write("DEBUG TODAY:", today)

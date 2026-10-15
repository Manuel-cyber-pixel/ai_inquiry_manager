import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "instance" / "inquiries.db"
CATEGORIES = ("Inquiry", "Complaint", "Order issue", "Other")
PRIORITIES = ("Low", "Normal", "High", "Urgent")
STATUSES = ("New", "In progress", "Resolved")
MAX_CUSTOMER_LENGTH = 100
MAX_MESSAGE_LENGTH = 5000
MAX_REPLY_LENGTH = 5000

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-development-key")
logging.basicConfig(level=logging.INFO)


@contextmanager
def get_db():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def categorize(message):
    text = message.casefold()
    categories = (
        ("Complaint", ("complaint", "unhappy", "disappointed", "terrible", "damaged", "broken", "poor service", "refund")),
        ("Order issue", ("order", "delivery", "delivered", "shipment", "tracking", "package", "shipping", "late")),
        ("Inquiry", ("?", "price", "pricing", "cost", "available", "availability", "hours", "information", "how do", "can i", "do you")),
    )
    for category, keywords in categories:
        if any(keyword in text for keyword in keywords):
            return category
    return "Other"


def initialize_database():
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                reply TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(messages)")
        }
        if "status" not in columns:
            connection.execute(
                "ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'New'"
            )
        count = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        if count == 0:
            samples = [
                ("Jordan Lee", "Could you tell me if the blue travel mug is available and what it costs?", "Inquiry", "Normal"),
                ("Sam Rivera", "My order #1842 was supposed to arrive three days ago. Can you check the tracking?", "Order issue", "High"),
                ("Taylor Morgan", "The item arrived broken and I am very disappointed. I would like a refund.", "Complaint", "Urgent"),
                ("Alex Kim", "Thank you for your help at the shop yesterday!", "Other", "Low"),
            ]
            connection.executemany(
                """
                INSERT INTO messages (customer, message, category, priority, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(customer, message, category, priority, datetime.now().isoformat(timespec="minutes")) for customer, message, category, priority in samples],
            )


def generate_reply(customer, category):
    greeting = f"Hi {customer},"
    templates = {
        "Inquiry": "Thanks for reaching out. We'd be happy to help with your question. Could you share any additional details that would help us give you the most accurate information?",
        "Complaint": "We're sorry to hear about your experience, and we appreciate you letting us know. Our team will review this and follow up with you to make things right.",
        "Order issue": "Thanks for contacting us about your order. We're sorry for the trouble. Please share your order number if it isn't included in your message, and we'll look into the status for you.",
        "Other": "Thanks for getting in touch. We appreciate your message and will be happy to help. Could you share any other details that might help us assist you?",
    }
    return f"{greeting}\n\n{templates[category]}\n\nBest,\nCustomer Support"


def message_redirect(message_id):
    return redirect(url_for("index", _anchor=f"message-{message_id}"))


@app.route("/")
def index():
    category_filter = request.args.get("category", "")
    priority_filter = request.args.get("priority", "")
    status_filter = request.args.get("status", "")
    invalid_filter = False
    if category_filter not in ("", *CATEGORIES):
        category_filter = ""
        invalid_filter = True
    if priority_filter not in ("", *PRIORITIES):
        priority_filter = ""
        invalid_filter = True
    if status_filter not in ("", *STATUSES):
        status_filter = ""
        invalid_filter = True
    if invalid_filter:
        flash("An invalid inbox filter was ignored.", "error")

    conditions = []
    parameters = []
    if category_filter:
        conditions.append("category = ?")
        parameters.append(category_filter)
    if priority_filter:
        conditions.append("priority = ?")
        parameters.append(priority_filter)
    if status_filter:
        conditions.append("status = ?")
        parameters.append(status_filter)
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    try:
        with get_db() as connection:
            messages = connection.execute(
                "SELECT id, customer, message, category, priority, status, reply, created_at "
                f"FROM messages{where_clause} ORDER BY id DESC",
                parameters,
            ).fetchall()
    except sqlite3.Error:
        app.logger.exception("Could not load messages from the database")
        flash("The message list could not be loaded. Please check the application log.", "error")
        messages = []
    return render_template(
        "index.html",
        messages=messages,
        categories=CATEGORIES,
        priorities=PRIORITIES,
        statuses=STATUSES,
        category_filter=category_filter,
        priority_filter=priority_filter,
        status_filter=status_filter,
        filters_active=bool(category_filter or priority_filter or status_filter),
    )


@app.route("/messages", methods=["POST"])
def add_message():
    customer = request.form.get("customer", "").strip()
    message = request.form.get("message", "").strip()
    priority = request.form.get("priority", "")

    if not customer or len(customer) > MAX_CUSTOMER_LENGTH:
        flash(f"Enter a customer name between 1 and {MAX_CUSTOMER_LENGTH} characters.", "error")
        return redirect(url_for("index"))
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        flash(f"Enter a message between 1 and {MAX_MESSAGE_LENGTH} characters.", "error")
        return redirect(url_for("index"))
    if priority not in PRIORITIES:
        flash("Choose a valid priority.", "error")
        return redirect(url_for("index"))

    try:
        with get_db() as connection:
            connection.execute(
                """
                INSERT INTO messages (customer, message, category, priority, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (customer, message, categorize(message), priority, datetime.now().isoformat(timespec="minutes")),
            )
        flash("Message added.", "success")
    except sqlite3.Error:
        app.logger.exception("Could not save a new message")
        flash("The message could not be saved. Please try again.", "error")
    return redirect(url_for("index"))


@app.route("/messages/<int:message_id>/suggest", methods=["POST"])
def suggest_reply(message_id):
    try:
        with get_db() as connection:
            row = connection.execute(
                "SELECT customer, category FROM messages WHERE id = ?", (message_id,)
            ).fetchone()
            if row is None:
                flash("That message could not be found.", "error")
            else:
                reply = generate_reply(row["customer"], row["category"])
                connection.execute("UPDATE messages SET reply = ? WHERE id = ?", (reply, message_id))
                flash("Reply draft generated. Review and edit it before using it.", "success")
    except sqlite3.Error:
        app.logger.exception("Could not generate a reply draft")
        flash("The reply draft could not be generated. Please try again.", "error")
    return message_redirect(message_id)


@app.route("/messages/<int:message_id>/category", methods=["POST"])
def update_category(message_id):
    category = request.form.get("category", "")
    if category not in CATEGORIES:
        flash("Choose a valid category.", "error")
        return message_redirect(message_id)

    try:
        with get_db() as connection:
            result = connection.execute(
                "UPDATE messages SET category = ? WHERE id = ?", (category, message_id)
            )
            if result.rowcount == 0:
                flash("That message could not be found.", "error")
            else:
                flash(
                    "Category updated. Regenerate the reply draft if you want it to match the new category.",
                    "success",
                )
    except sqlite3.Error:
        app.logger.exception("Could not update the message category")
        flash("The category could not be updated. Please try again.", "error")
    return message_redirect(message_id)


@app.route("/messages/<int:message_id>/status", methods=["POST"])
def update_status(message_id):
    status = request.form.get("status", "")
    if status not in STATUSES:
        flash("Choose a valid status.", "error")
        return message_redirect(message_id)

    try:
        with get_db() as connection:
            result = connection.execute(
                "UPDATE messages SET status = ? WHERE id = ?", (status, message_id)
            )
            if result.rowcount == 0:
                flash("That message could not be found.", "error")
            else:
                flash("Message status updated.", "success")
    except sqlite3.Error:
        app.logger.exception("Could not update the message status")
        flash("The message status could not be updated. Please try again.", "error")
    return message_redirect(message_id)


@app.route("/messages/<int:message_id>/reply", methods=["POST"])
def save_reply(message_id):
    reply = request.form.get("reply", "").strip()
    if not reply or len(reply) > MAX_REPLY_LENGTH:
        flash(f"Reply drafts must be between 1 and {MAX_REPLY_LENGTH} characters.", "error")
        return message_redirect(message_id)
    try:
        with get_db() as connection:
            result = connection.execute("UPDATE messages SET reply = ? WHERE id = ?", (reply, message_id))
            if result.rowcount == 0:
                flash("That message could not be found.", "error")
            else:
                flash("Reviewed draft saved. No message has been sent.", "success")
    except sqlite3.Error:
        app.logger.exception("Could not save the reply draft")
        flash("The reply draft could not be saved. Please try again.", "error")
    return message_redirect(message_id)


if __name__ == "__main__":
    initialize_database()
    app.run(host="127.0.0.1", debug=False)

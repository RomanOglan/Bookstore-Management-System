import os
from flask import Flask, render_template
from db import get_connection

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/dbtest")
def dbtest():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Books")
        count = cur.fetchone()[0]
        cur.close()
    finally:
        conn.close()
    return render_template("dbtest.html", count=count)


if __name__ == "__main__":
    app.run(debug=True)

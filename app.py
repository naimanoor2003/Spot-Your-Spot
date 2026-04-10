from flask import Flask, jsonify, render_template, request, redirect, url_for, session
import random
import threading
import time

app = Flask(__name__)
app.secret_key = "seatfinder2024"

# --- Users ---
users = {
    "student1": {"password": "student123", "role": "student"},
    "student2": {"password": "student123", "role": "student"},
    "admin": {"password": "admin123", "role": "admin"}
}

# --- Generate seats: rows x 10 cols, aisle after col 4 ---
def generate_seats(num_rows):
    seats = []
    seat_id = 0
    for row in range(num_rows):
        for col in range(10):
            accessible = (row == 0 and col in [0, 1, 8, 9])
            seats.append({
                "id": seat_id,
                "row": row,
                "col": col,
                "occupied": random.choice([True, False]),
                "accessible": accessible
            })
            seat_id += 1
    return seats

# --- Lecture Halls with different sizes ---
halls = {
    "hall_a": {
        "name": "Lecture Hall A",
        "capacity": 120,
        "rows": 12,
        "lecture_time": "10:00 - 11:00",
        "seats": generate_seats(12)
    },
    "hall_b": {
        "name": "Lecture Hall B",
        "capacity": 150,
        "rows": 15,
        "lecture_time": "11:00 - 12:00",
        "seats": generate_seats(15)
    },
    "hall_c": {
        "name": "Lecture Hall C",
        "capacity": 200,
        "rows": 20,
        "lecture_time": "13:00 - 14:00",
        "seats": generate_seats(20)
    }
}

entrances = [
    {"id": "left", "label": "Left Entrance", "col": 0},
    {"id": "right", "label": "Right Entrance", "col": 9}
]

# --- Simulate sensor changes every 8 seconds ---
def simulate_changes():
    while True:
        time.sleep(8)
        for hall in halls.values():
            for _ in range(random.randint(2, 4)):
                seat = random.choice(hall["seats"])
                seat["occupied"] = not seat["occupied"]

thread = threading.Thread(target=simulate_changes, daemon=True)
thread.start()

# --- Routes ---
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")
        if username in users and users[username]["password"] == password and users[username]["role"] == role:
            session["username"] = username
            session["role"] = role
            return redirect(url_for("select_hall"))
        else:
            error = "Invalid username, password or role. Please try again."
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    success = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")
        role = request.form.get("role")

        if not username or not password or not confirm or not role:
            error = "Please fill in all fields."
        elif username in users:
            error = "Username already exists. Please choose another."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            # Only allow student self-registration
            users[username] = {"password": password, "role": "student"}
            success = "Account created! You can now log in as a student."
            

    return render_template("register.html", error=error, success=success)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/halls")
def select_hall():
    if "username" not in session:
        return redirect(url_for("login"))
    hall_list = [{"id": k, "name": v["name"], "capacity": v["capacity"],
                  "lecture_time": v["lecture_time"],
                  "available": sum(1 for s in v["seats"] if not s["occupied"])}
                 for k, v in halls.items()]
    return render_template("halls.html", halls=hall_list,
                           username=session["username"], role=session["role"])

@app.route("/hall/<hall_id>")
def view_hall(hall_id):
    if "username" not in session:
        return redirect(url_for("login"))
    if hall_id not in halls:
        return redirect(url_for("select_hall"))
    return render_template("index.html", hall_id=hall_id,
                           hall_name=halls[hall_id]["name"],
                           lecture_time=halls[hall_id]["lecture_time"],
                           username=session["username"], role=session["role"])

@app.route("/api/seats/<hall_id>")
def get_seats(hall_id):
    if hall_id not in halls:
        return jsonify({"error": "Hall not found"}), 404
    return jsonify({"seats": halls[hall_id]["seats"], "entrances": entrances})

@app.route("/api/toggle/<hall_id>/<int:seat_id>", methods=["POST"])
def toggle_seat(hall_id, seat_id):
    if "role" not in session or session["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    if hall_id not in halls:
        return jsonify({"error": "Hall not found"}), 404
    for seat in halls[hall_id]["seats"]:
        if seat["id"] == seat_id:
            seat["occupied"] = not seat["occupied"]
            return jsonify({"success": True, "seat": seat})
    return jsonify({"success": False}), 404

@app.route("/admin")
def admin_dashboard():
    if "username" not in session or session["role"] != "admin":
        return redirect(url_for("login"))
    hall_stats = []
    for k, v in halls.items():
        total = len(v["seats"])
        occupied = sum(1 for s in v["seats"] if s["occupied"])
        available = total - occupied
        occupancy_pct = int((occupied / total) * 100)
        rows = {}
        for s in v["seats"]:
            if s["row"] not in rows:
                rows[s["row"]] = 0
            if s["occupied"]:
                rows[s["row"]] += 1
        busiest_row = max(rows, key=rows.get) + 1 if rows else 1
        hall_stats.append({
            "id": k,
            "name": v["name"],
            "total": total,
            "occupied": occupied,
            "available": available,
            "occupancy_pct": occupancy_pct,
            "lecture_time": v["lecture_time"],
            "busiest_row": busiest_row
        })
    return render_template("admin.html", halls=hall_stats,
                           username=session["username"])

@app.route("/api/reset/<hall_id>", methods=["POST"])
def reset_hall(hall_id):
    if "role" not in session or session["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    if hall_id not in halls:
        return jsonify({"error": "Hall not found"}), 404
    for seat in halls[hall_id]["seats"]:
        seat["occupied"] = False
    return jsonify({"success": True})

@app.route("/api/dashboard")
def dashboard_api():
    if "role" not in session or session["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    hall_stats = []
    for k, v in halls.items():
        total = len(v["seats"])
        occupied = sum(1 for s in v["seats"] if s["occupied"])
        hall_stats.append({
            "id": k,
            "total": total,
            "occupied": occupied,
            "available": total - occupied
        })
    return jsonify({"halls": hall_stats})
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
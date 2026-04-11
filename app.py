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
def recommend_seat(seats, preference="none", accessible_only=False):
    """
    Seat recommendation engine.
    Scores each available seat based on:
    - Preferred area (front/middle/back)
    - Proximity to nearest entrance
    - Accessibility requirements
    - Aisle adjacency (easier access)
    - Row popularity weighting
    Returns the top 3 recommended seats with scores.
    """
    total_rows = max(s["row"] for s in seats) + 1
    front_threshold = total_rows // 3
    back_threshold = (total_rows * 2) // 3

    candidates = []

    for seat in seats:
        if seat["occupied"]:
            continue
        if accessible_only and not seat["accessible"]:
            continue

        score = 0

        # --- Area preference scoring ---
        if preference == "front":
            if seat["row"] < front_threshold:
                score += 50
            elif seat["row"] < front_threshold * 1.5:
                score += 25
        elif preference == "back":
            if seat["row"] >= back_threshold:
                score += 50
            elif seat["row"] >= back_threshold - 2:
                score += 25
        elif preference == "middle":
            if front_threshold <= seat["row"] < back_threshold:
                score += 50
            elif abs(seat["row"] - (total_rows // 2)) <= 2:
                score += 25
        else:
            # No preference — slight bias towards middle
            if front_threshold <= seat["row"] < back_threshold:
                score += 10

        # --- Entrance proximity scoring ---
        dist_left = seat["col"]
        dist_right = 9 - seat["col"]
        min_dist = min(dist_left, dist_right)
        # Closer to entrance = higher score
        score += max(0, 20 - (min_dist * 2))

        # --- Aisle adjacency bonus ---
        if seat["col"] in [4, 5]:
            score += 10

        # --- Accessibility bonus ---
        if seat["accessible"]:
            score += 15 if accessible_only else 5

        # --- Avoid very back row unless preferred ---
        if seat["row"] == total_rows - 1 and preference != "back":
            score -= 10

        candidates.append({
            "seat": seat,
            "score": score,
            "entrance": "Left" if dist_left <= dist_right else "Right"
        })

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Return top 3
    return candidates[:3]

def simulate_changes():
    """
    Behavioural occupancy simulation.
    Models realistic lecture hall patterns:
    - Front and aisle-adjacent seats fill first
    - Late arrivals cluster towards back rows
    - Natural variation with weighted probability
    """
    while True:
        time.sleep(8)
        for hall in halls.values():
            total = len(hall["seats"])
            occupied_count = sum(1 for s in hall["seats"] if s["occupied"])
            occupancy_rate = occupied_count / total

            for seat in hall["seats"]:
                # Base probability of change
                change_prob = 0.03

                # Front rows more likely to be occupied (students prefer front)
                if seat["row"] < 3:
                    if not seat["occupied"]:
                        change_prob = 0.08  # Higher chance of becoming occupied
                    else:
                        change_prob = 0.01  # Low chance of freeing up

                # Back rows more volatile — late arrivals and early leavers
                elif seat["row"] >= (total // 10) - 3:
                    change_prob = 0.05

                # Aisle adjacent seats fill faster
                if seat["col"] in [4, 5]:
                    if not seat["occupied"]:
                        change_prob += 0.03

                # Accessible seats have lower churn
                if seat["accessible"]:
                    change_prob = 0.01

                # If hall is very full, more likely seats free up
                if occupancy_rate > 0.85:
                    if seat["occupied"]:
                        change_prob += 0.04

                # If hall is very empty, more likely seats fill up
                if occupancy_rate < 0.2:
                    if not seat["occupied"]:
                        change_prob += 0.05

                # Apply probability
                if random.random() < change_prob:
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
@app.route("/api/recommend/<hall_id>")
def get_recommendation(hall_id):
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 403
    if hall_id not in halls:
        return jsonify({"error": "Hall not found"}), 404
    preference = request.args.get("preference", "none")
    accessible_only = request.args.get("accessible", "false") == "true"
    recommendations = recommend_seat(
        halls[hall_id]["seats"],
        preference=preference,
        accessible_only=accessible_only
    )
    return jsonify({"recommendations": [
        {
            "seat_id": r["seat"]["id"],
            "seat_number": r["seat"]["id"] + 1,
            "row": r["seat"]["row"] + 1,
            "col": r["seat"]["col"] + 1,
            "score": r["score"],
            "entrance": r["entrance"],
            "accessible": r["seat"]["accessible"]
        }
        for r in recommendations
    ]})
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
from flask import Flask, render_template, flash, redirect, url_for, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, StaffProfile, Trek, Booking


app = Flask(__name__)


app.config["SECRET_KEY"] = "dev-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///trekking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)


VALID_ROLES = ["admin", "staff", "user"]


def password_is_hashed(password):
    if not password:
        return False
    return password.startswith("scrypt:") or password.startswith("pbkdf2:")


def create_admin():
    admin = User.query.filter_by(email="admin@trek.com").first()

    if admin is None:
        admin = User(
            name="Admin",
            email="admin@trek.com",
            phone_number="0000000000",
            password=generate_password_hash("admin123"),
            role="admin",
            status="active"
        )

        db.session.add(admin)
        db.session.commit()
        
    elif not password_is_hashed(admin.password):
        admin.password = generate_password_hash("admin123")
        db.session.commit()


def dashboard_route(role):
    if role == "admin":
        return "admin_dashboard"
    
    elif role == "staff":
        return "staff_dashboard"
    
    elif role == "user":
        return "user_dashboard"
    
    else:
        return "home"


def check_access(required_role):
    if "user_id" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    if user is None:
        session.clear()
        flash("Please login again", "warning")
        return redirect(url_for("login"))

    if user.status == "blacklisted":
        session.clear()
        flash("Your account is blacklisted", "danger")
        return redirect(url_for("login"))

    if user.role == "staff" and user.status == "pending":
        session.clear()
        flash("Staff account pending approval", "warning")
        return redirect(url_for("login"))

    if user.role not in VALID_ROLES:
        session.clear()
        flash("Invalid user role", "danger")
        return redirect(url_for("login"))

    if user.role != required_role:
        flash("You are not allowed to access this page", "danger")
        return redirect(url_for(dashboard_route(user.role)))

    return None


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required", "danger")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if user is None:
            flash("Invalid email or password", "danger")
            return redirect(url_for("login"))

        if not check_password_hash(user.password, password):
            flash("Invalid email or password", "danger")
            return redirect(url_for("login"))

        if user.role not in VALID_ROLES:
            flash("Invalid user role", "danger")
            return redirect(url_for("login"))

        if user.status == "blacklisted":
            flash("Your account is blacklisted", "danger")
            return redirect(url_for("login"))

        if user.role == "staff" and user.status == "pending":
            flash("Staff account pending approval", "warning")
            return redirect(url_for("login"))

        if user.status != "active":
            flash("Account is not active", "danger")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role
        session["name"] = user.name

        flash("Logged in successfully", "success")
        return redirect(url_for(dashboard_route(user.role)))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone_number = request.form.get("phone_number", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name:
            flash("Name is required", "danger")
            return redirect(url_for("register"))

        if not email:
            flash("Email is required", "danger")
            return redirect(url_for("register"))
        
        if not phone_number:
            flash("Phone number is required", "danger")
            return redirect(url_for("register"))

        if role not in ["staff", "user"]:
            flash("Invalid role selected", "danger")
            return redirect(url_for("register"))

        if not password:
            flash("Password is required", "danger")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters", "danger")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Email already registered", "danger")
            return redirect(url_for("register"))

        status = "pending" if role == "staff" else "active"

        new_user = User(
            name=name,
            email=email,
            phone_number=phone_number,
            password=generate_password_hash(password),
            role=role,
            status=status
        )

        db.session.add(new_user)
        db.session.flush()

        if role == "staff":
            staff_profile = StaffProfile(
                user_id=new_user.id
            )
            db.session.add(staff_profile)
        db.session.commit()

        if role == "staff":
            flash("Staff registration submitted. Please wait for admin approval.", "info")
            return redirect(url_for("login"))

        session["user_id"] = new_user.id
        session["role"] = new_user.role
        session["name"] = new_user.name

        flash("Registration successful", "success")
        return redirect(url_for("user_dashboard"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("home"))


@app.route("/admin/dashboard")
def admin_dashboard():
    access_check = check_access("admin")

    if access_check:
        return access_check

    total_users = User.query.filter_by(role="user").count()
    total_staff = User.query.filter_by(role="staff").count()
    total_treks = Trek.query.count()
    total_bookings = Booking.query.count()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_staff=total_staff,
        total_treks=total_treks,
        total_bookings=total_bookings
    )


@app.route("/staff/dashboard")
def staff_dashboard():
    access_check = check_access("staff")

    if access_check:
        return access_check

    return render_template("staff/dashboard.html")


@app.route("/user/dashboard")
def user_dashboard():
    access_check = check_access("user")

    if access_check:
        return access_check

    return render_template("user/dashboard.html")
    

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_admin()

    app.run(debug=True)
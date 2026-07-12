from flask import Flask, render_template, flash, redirect, url_for, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, StaffProfile, Trek, Booking
from datetime import date
from functools import wraps
from sqlalchemy import or_


app = Flask(__name__)


app.config["SECRET_KEY"] = "dev-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///trekking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)


VALID_ROLES = ["admin", "staff", "user"]


def is_valid_email(email):
    if " " in email or email.count("@") != 1:
        return False

    local_part, domain = email.split("@")
    domain_parts = domain.split(".")

    return bool(
        local_part
        and len(domain_parts) >= 2
        and all(domain_parts)
    )


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

    if user.status != "active":
        session.clear()
        flash("Account is not active", "warning")
        return redirect(url_for("login"))

    if user.role not in VALID_ROLES:
        session.clear()
        flash("Invalid user role", "danger")
        return redirect(url_for("login"))

    if user.role != required_role:
        flash("You are not allowed to access this page", "danger")
        return redirect(url_for(dashboard_route(user.role)))

    return None


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        access_check = check_access("admin")

        if access_check:
            return access_check

        return func(*args, **kwargs)
    return wrapper


def staff_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        access_check = check_access("staff")

        if access_check:
            return access_check

        return func(*args, **kwargs)
    return wrapper


DIFFICULTY_OPTIONS = ["Easy", "Moderate", "Hard"]

TREK_STATUS_OPTIONS = ["Pending", "Approved", "Open", "Closed", "Started", "Ongoing", "Completed"]


def validate_trek_form(form):
    errors = []

    name = form.get("name", "").strip()
    location = form.get("location", "").strip()
    difficulty = form.get("difficulty", "").strip()
    duration = form.get("duration", "").strip()
    available_slots = form.get("available_slots", "").strip()
    start_date = form.get("start_date", "").strip()
    end_date = form.get("end_date", "").strip()
    description = form.get("description", "").strip()
    status = form.get("status", "").strip()

    if not name:
        errors.append("Trek name is required.")

    if not location:
        errors.append("Location is required.")

    if difficulty not in DIFFICULTY_OPTIONS:
        errors.append("Please select a valid difficulty.")

    if status not in TREK_STATUS_OPTIONS:
        errors.append("Please select a valid status.")

    try:
        duration = int(duration)
        if duration <= 0:
            errors.append("Duration must be greater than 0.")
    except ValueError:
        errors.append("Duration must be a number.")

    try:
        available_slots = int(available_slots)
        if available_slots < 0:
            errors.append("Available slots cannot be negative.")
    except ValueError:
        errors.append("Available slots must be a number.")

    try:
        start_date = date.fromisoformat(start_date)
    except ValueError:
        errors.append("Start date is invalid.")

    try:
        end_date = date.fromisoformat(end_date)
    except ValueError:
        errors.append("End date is invalid.")

    if isinstance(start_date, date) and isinstance(end_date, date):
        if end_date < start_date:
            errors.append("End date cannot be before start date.")

    trek_data = {
        "name": name,
        "location": location,
        "difficulty": difficulty,
        "duration": duration if isinstance(duration, int) else 0,
        "available_slots": available_slots if isinstance(available_slots, int) else 0,
        "start_date": start_date if isinstance(start_date, date) else None,
        "end_date": end_date if isinstance(end_date, date) else None,
        "description": description,
        "status": status
    }

    return errors, trek_data


def get_active_staff():
    if "user_id" not in session or session.get("role") != "staff":
        return None

    staff = User.query.get(session["user_id"])

    if not staff or staff.status != "active":
        return None

    return staff


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
        
        if not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
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
            flash("Your account has been blacklisted. Please contact admin.", "danger")
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
        
        if not is_valid_email(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("register"))
        
        if not phone_number:
            flash("Phone number is required", "danger")
            return redirect(url_for("register"))
        
        if not phone_number.isdigit() or len(phone_number) != 10:
            flash("Phone number must be exactly 10 digits.", "danger")
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
@admin_required
def admin_dashboard():
    total_users = User.query.filter_by(role="user").count()
    total_staff = User.query.filter_by(role="staff").count()
    total_treks = Trek.query.count()
    total_bookings = Booking.query.count()

    return render_template(
        "admin/dashboard.html",
        name=session.get("name"),
        total_users=total_users,
        total_staff=total_staff,
        total_treks=total_treks,
        total_bookings=total_bookings
    )


@app.route("/admin/staff")
@admin_required
def admin_staff():
    staff_members = User.query.filter_by(role="staff").order_by(User.id.desc()).all()

    return render_template(
        "admin/staff.html",
        staff_members=staff_members
    )


@app.route("/admin/staff/<int:staff_id>/approve", methods=["POST"])
@admin_required
def approve_staff(staff_id):
    staff = User.query.get_or_404(staff_id)

    if staff.role != "staff":
        flash("Only staff accounts can be approved.", "danger")
        return redirect(url_for("admin_staff"))

    if staff.status != "pending":
        flash("Only pending staff can be approved.", "warning")
        return redirect(url_for("admin_staff"))

    staff.status = "active"
    db.session.commit()

    flash("Staff approved successfully.", "success")
    return redirect(url_for("admin_staff"))


@app.route("/admin/staff/<int:staff_id>/blacklist", methods=["POST"])
@admin_required
def blacklist_staff(staff_id):
    staff = User.query.get_or_404(staff_id)

    if staff.role != "staff":
        flash("Only staff accounts can be blacklisted.", "danger")
        return redirect(url_for("admin_staff"))

    if staff.status != "active":
        flash("Only active staff can be blacklisted.", "warning")
        return redirect(url_for("admin_staff"))

    staff.status = "blacklisted"
    db.session.commit()

    flash("Staff blacklisted successfully.", "success")
    return redirect(url_for("admin_staff"))


@app.route("/admin/staff/<int:staff_id>/reactivate", methods=["POST"])
@admin_required
def reactivate_staff(staff_id):
    staff = User.query.get_or_404(staff_id)

    if staff.role != "staff":
        flash("Only staff accounts can be reactivated.", "danger")
        return redirect(url_for("admin_staff"))

    if staff.status != "blacklisted":
        flash("Only blacklisted staff can be reactivated.", "warning")
        return redirect(url_for("admin_staff"))

    staff.status = "active"
    db.session.commit()

    flash("Staff reactivated successfully.", "success")
    return redirect(url_for("admin_staff"))


@app.route("/admin/treks")
@admin_required
def admin_treks():
    treks = Trek.query.order_by(Trek.id.desc()).all()

    approved_staff = User.query.filter_by(
        role="staff",
        status="active"
    ).order_by(User.name).all()

    staff_users = User.query.filter_by(role="staff").all()
    staff_names = {}

    for staff in staff_users:
        staff_names[staff.id] = staff.name

    return render_template(
        "admin/treks.html",
        treks=treks,
        approved_staff=approved_staff,
        staff_names=staff_names
    )


@app.route("/admin/treks/<int:trek_id>/assign-staff", methods=["POST"])
@admin_required
def assign_staff_to_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    staff_id = request.form.get("assigned_staff_id", "").strip()

    if staff_id == "":
        trek.assigned_staff_id = None
        db.session.commit()

        flash("Staff assignment removed.", "success")
        return redirect(url_for("admin_treks"))

    if not staff_id.isdigit():
        flash("Invalid staff selected.", "danger")
        return redirect(url_for("admin_treks"))

    staff = User.query.filter_by(
        id=int(staff_id),
        role="staff",
        status="active"
    ).first()

    if staff is None:
        flash("Only approved staff can be assigned to treks.", "danger")
        return redirect(url_for("admin_treks"))

    trek.assigned_staff_id = staff.id
    db.session.commit()

    flash("Staff assigned to trek successfully.", "success")
    return redirect(url_for("admin_treks"))


@app.route("/admin/treks/add", methods=["GET", "POST"])
@admin_required
def add_trek():
    if request.method == "POST":
        errors, trek_data = validate_trek_form(request.form)

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "admin/add_trek.html",
                difficulty_options=DIFFICULTY_OPTIONS,
                status_options=TREK_STATUS_OPTIONS,
                form_data=request.form
            )

        trek = Trek(
            name=trek_data["name"],
            location=trek_data["location"],
            difficulty=trek_data["difficulty"],
            duration=trek_data["duration"],
            available_slots=trek_data["available_slots"],
            start_date=trek_data["start_date"],
            end_date=trek_data["end_date"],
            description=trek_data["description"],
            status=trek_data["status"]
        )

        db.session.add(trek)
        db.session.commit()

        flash("Trek added successfully.", "success")
        return redirect(url_for("admin_treks"))

    return render_template(
        "admin/add_trek.html",
        difficulty_options=DIFFICULTY_OPTIONS,
        status_options=TREK_STATUS_OPTIONS,
        form_data={}
    )


@app.route("/admin/treks/edit/<int:trek_id>", methods=["GET", "POST"])
@admin_required
def edit_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    approved_staff = User.query.filter_by(
        role="staff",
        status="active"
    ).order_by(User.name).all()

    if request.method == "POST":
        errors, trek_data = validate_trek_form(request.form)

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "admin/edit_trek.html",
                trek=trek,
                difficulty_options=DIFFICULTY_OPTIONS,
                status_options=TREK_STATUS_OPTIONS,
                approved_staff=approved_staff
            )

        staff_id = request.form.get("assigned_staff_id", "").strip()

        if staff_id == "":
            trek.assigned_staff_id = None

        elif not staff_id.isdigit():
            flash("Invalid staff selected.", "danger")

            return render_template(
                "admin/edit_trek.html",
                trek=trek,
                difficulty_options=DIFFICULTY_OPTIONS,
                status_options=TREK_STATUS_OPTIONS,
                approved_staff=approved_staff
            )

        else:
            staff = User.query.filter_by(
                id=int(staff_id),
                role="staff",
                status="active"
            ).first()

            if staff is None:
                flash("Only approved staff can be assigned to treks.", "danger")

                return render_template(
                    "admin/edit_trek.html",
                    trek=trek,
                    difficulty_options=DIFFICULTY_OPTIONS,
                    status_options=TREK_STATUS_OPTIONS,
                    approved_staff=approved_staff
                )

            trek.assigned_staff_id = staff.id

        trek.name = trek_data["name"]
        trek.location = trek_data["location"]
        trek.difficulty = trek_data["difficulty"]
        trek.duration = trek_data["duration"]
        trek.available_slots = trek_data["available_slots"]
        trek.start_date = trek_data["start_date"]
        trek.end_date = trek_data["end_date"]
        trek.description = trek_data["description"]
        trek.status = trek_data["status"]

        if trek_data["status"] == "Completed":
            bookings = Booking.query.filter_by(trek_id=trek.id, booking_status="Booked").all()

            for booking in bookings:
                booking.booking_status = "Completed"

        db.session.commit()

        flash("Trek updated successfully.", "success")
        return redirect(url_for("admin_treks"))

    return render_template(
        "admin/edit_trek.html",
        trek=trek,
        difficulty_options=DIFFICULTY_OPTIONS,
        status_options=TREK_STATUS_OPTIONS,
        approved_staff=approved_staff
    )


@app.route("/admin/treks/delete/<int:trek_id>", methods=["POST"])
@admin_required
def delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)

    booking_count = Booking.query.filter_by(trek_id=trek.id).count()

    if booking_count > 0:
        trek.status = "Closed"
        db.session.commit()
        flash("This trek has bookings, so it was marked as Closed instead of deleting.", "warning")
        return redirect(url_for("admin_treks"))

    db.session.delete(trek)
    db.session.commit()

    flash("Trek deleted successfully.", "success")
    return redirect(url_for("admin_treks"))


@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.filter(User.role != "staff").order_by(User.id).all()

    return render_template("admin/users.html", users=users)


@app.route("/admin/users/<int:user_id>/blacklist", methods=["POST"])
@admin_required
def blacklist_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == session.get("user_id"):
        flash("You cannot blacklist your own account.", "danger")
        return redirect(url_for("admin_users"))

    if user.role == "admin":
        flash("Admin account cannot be blacklisted.", "danger")
        return redirect(url_for("admin_users"))

    if user.role == "staff":
        flash("Staff accounts are managed from the staff page.", "warning")
        return redirect(url_for("admin_users"))
    
    if user.status != "active":
        flash("Only active users can be blacklisted.", "warning")
        return redirect(url_for("admin_users"))

    user.status = "blacklisted"
    db.session.commit()

    flash("User blacklisted successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/reactivate", methods=["POST"])
@admin_required
def reactivate_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.role == "admin":
        flash("Admin account is already active.", "info")
        return redirect(url_for("admin_users"))

    if user.role == "staff":
        flash("Staff accounts are managed from the staff page.", "warning")
        return redirect(url_for("admin_users"))
    
    if user.status != "blacklisted":
        flash("Only blacklisted users can be reactivated.", "warning")
        return redirect(url_for("admin_users"))

    user.status = "active"
    db.session.commit()

    flash("User reactivated successfully.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    bookings = Booking.query.order_by(Booking.booking_date.desc()).all()

    return render_template("admin/bookings.html", bookings=bookings)


@app.route("/admin/search", methods=["GET", "POST"])
@admin_required
def admin_search():
    search_type = request.args.get("search_type", "")
    keyword = request.args.get("keyword", "").strip()

    users = []
    staff = []
    treks = []
    searched = False

    if keyword and search_type:
        searched = True

        if search_type == "users":
            users_query = User.query.filter(User.role == "user")

            if keyword.isdigit():
                users = users_query.filter(User.id == int(keyword)).all()
            else:
                users = users_query.filter(
                    or_(
                        User.name.ilike(f"%{keyword}%"),
                        User.email.ilike(f"%{keyword}%")
                    )
                ).all()

        elif search_type == "staff":
            staff_query = User.query.filter(User.role == "staff")

            if keyword.isdigit():
                staff = staff_query.filter(User.id == int(keyword)).all()
            else:
                staff = staff_query.filter(
                    or_(
                        User.name.ilike(f"%{keyword}%"),
                        User.email.ilike(f"%{keyword}%")
                    )
                ).all()

        elif search_type == "treks":
            treks_query = Trek.query

            if keyword.isdigit():
                treks = treks_query.filter(Trek.id == int(keyword)).all()
            else:
                treks = treks_query.filter(
                    or_(
                        Trek.name.ilike(f"%{keyword}%"),
                        Trek.location.ilike(f"%{keyword}%")
                    )
                ).all()

    return render_template(
        "admin/search.html",
        search_type=search_type,
        keyword=keyword,
        users=users,
        staff=staff,
        treks=treks,
        searched=searched
    )


@app.route("/staff/dashboard")
@staff_required
def staff_dashboard():
    assigned_treks = Trek.query.filter_by(assigned_staff_id=session.get("user_id")).order_by(Trek.id.desc()).all()

    assigned_trek_count = len(assigned_treks)

    booking_counts = {}

    for trek in assigned_treks:
        booking_counts[trek.id] = Booking.query.filter(Booking.trek_id == trek.id, Booking.booking_status.in_(["Booked", "Completed"])).count()

    return render_template("staff/dashboard.html", name=session.get("name"), assigned_treks=assigned_treks, assigned_trek_count=assigned_trek_count, booking_counts=booking_counts)


@app.route("/staff/assigned-treks")
@staff_required
def staff_assigned_treks():
    staff_id = session.get("user_id")

    assigned_treks = Trek.query.filter_by(assigned_staff_id=staff_id).order_by(Trek.id.desc()).all()

    trek_data = []

    for trek in assigned_treks:
        booking_count = Booking.query.filter(Booking.trek_id==trek.id, Booking.booking_status.in_(["Booked", "Completed"])).count()

        trek_data.append({
            "trek": trek,
            "booking_count": booking_count
        })

    allowed_statuses = ["Open", "Closed", "Started", "Ongoing", "Completed"]

    return render_template(
        "staff/assigned_treks.html",
        trek_data=trek_data,
        allowed_statuses=allowed_statuses
    )


@app.route("/staff/assigned-treks/<int:trek_id>/update", methods=["POST"])
@staff_required
def update_assigned_trek(trek_id):
    staff_id = session.get("user_id")
    trek = Trek.query.get_or_404(trek_id)

    if trek.assigned_staff_id != staff_id:
        flash("You can update only your assigned treks.", "danger")
        return redirect(url_for("staff_assigned_treks"))

    available_slots = request.form.get("available_slots", "").strip()
    status = request.form.get("status", "").strip()

    allowed_statuses = ["Open", "Closed", "Started", "Ongoing", "Completed"]

    try:
        available_slots = int(available_slots)
    except ValueError:
        flash("Slots must be a whole number.", "danger")
        return redirect(url_for("staff_assigned_treks"))

    if available_slots < 0:
        flash("Slots cannot be negative.", "danger")
        return redirect(url_for("staff_assigned_treks"))

    if status not in allowed_statuses:
        flash("Invalid trek status selected.", "danger")
        return redirect(url_for("staff_assigned_treks"))

    trek.available_slots = available_slots
    trek.status = status

    if status == "Completed":
        bookings = Booking.query.filter_by(trek_id=trek.id, booking_status="Booked").all()

        for booking in bookings:
            booking.booking_status = "Completed"

    db.session.commit()

    flash("Trek updated successfully.", "success")
    return redirect(url_for("staff_assigned_treks"))


@app.route("/staff/participants/<int:trek_id>")
@staff_required
def staff_participants(trek_id):
    staff = get_active_staff()

    if not staff:
        flash("Please login as active staff to access this page.", "danger")
        return redirect(url_for("login"))

    trek = Trek.query.get_or_404(trek_id)

    if trek.assigned_staff_id != staff.id:
        flash("You are not allowed to view participants of this trek.", "danger")
        return redirect(url_for("staff_assigned_treks"))

    bookings = Booking.query.filter_by(trek_id=trek.id).order_by(Booking.booking_date.desc()).all()

    return render_template(
        "staff/participants.html",
        trek=trek,
        bookings=bookings
    )


@app.route("/staff/profile", methods=["GET", "POST"])
@staff_required
def staff_profile():
    staff = get_active_staff()

    if not staff:
        flash("Please login as active staff to access this page.", "danger")
        return redirect(url_for("login"))

    profile = StaffProfile.query.filter_by(user_id=staff.id).first()

    if not profile:
        profile = StaffProfile(user_id=staff.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()
        bio = request.form.get("bio", "").strip()

        if not name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("staff_profile"))
        
        if not phone_number:
            flash("Phone number cannot be empty.", "danger")
            return redirect(url_for("staff_profile"))

        if not phone_number.isdigit() or len(phone_number) != 10:
            flash("Phone number must be exactly 10 digits.", "danger")
            return redirect(url_for("staff_profile"))

        staff.name = name
        staff.phone_number = phone_number
        profile.bio = bio

        db.session.commit()

        session["name"] = staff.name

        flash("Profile updated successfully.", "success")
        return redirect(url_for("staff_profile"))

    return render_template(
        "staff/profile.html",
        user=staff,
        profile=profile
    )


@app.route("/user/dashboard")
def user_dashboard():
    access_check = check_access("user")

    if access_check:
        return access_check
    
    today = date.today()

    available_treks = Trek.query.filter(Trek.status == "Open", Trek.start_date >= today).count()

    booked_treks = Booking.query.filter_by(user_id=session["user_id"], booking_status="Booked").count()

    recent_bookings = Booking.query.filter_by(user_id=session["user_id"]).order_by(Booking.booking_date.desc()).limit(3).all()

    return render_template("user/dashboard.html", name=session.get("name"), available_treks=available_treks, booked_treks=booked_treks, recent_bookings=recent_bookings)


@app.route("/user/treks")
def user_treks():
    access_check = check_access("user")

    if access_check:
        return access_check

    search = request.args.get("search", "").strip()
    location = request.args.get("location", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    today = date.today()

    trek_query = Trek.query.filter(Trek.status == "Open", Trek.start_date >= today)

    if search:
        trek_query = trek_query.filter(
            Trek.name.ilike(f"%{search}%")
        )

    if location:
        trek_query = trek_query.filter(
            Trek.location == location
        )

    if difficulty in ["Easy", "Moderate", "Hard"]:
        trek_query = trek_query.filter(
            Trek.difficulty == difficulty
        )

    treks = trek_query.order_by(Trek.start_date.asc()).all()

    location_rows = (
        db.session.query(Trek.location)
        .filter(Trek.status == "Open", Trek.start_date >= today)
        .distinct()
        .order_by(Trek.location.asc())
        .all()
    )

    locations = [row[0] for row in location_rows]

    return render_template(
        "user/browse_treks.html",
        treks=treks,
        locations=locations,
        search=search,
        selected_location=location,
        selected_difficulty=difficulty
    )


@app.route("/user/book/<int:trek_id>", methods=["POST"])
def book_trek(trek_id):
    access_check = check_access("user")

    if access_check:
        return access_check

    user = User.query.get(session["user_id"])
    trek = Trek.query.get(trek_id)

    if trek is None:
        flash("Trek not found.", "danger")
        return redirect(url_for("user_treks"))

    if trek.status != "Open":
        flash("This trek is not open for booking.", "warning")
        return redirect(url_for("user_treks"))
    
    if trek.start_date < date.today():
        flash("This trek has already started and cannot be booked.", "warning")
        return redirect(url_for("user_treks"))

    existing_booking = Booking.query.filter_by(
        user_id=user.id,
        trek_id=trek.id,
        booking_status="Booked"
    ).first()

    if existing_booking:
        flash("You have already booked this trek.", "warning")
        return redirect(url_for("user_treks"))

    if trek.available_slots <= 0:
        trek.status = "Closed"
        db.session.commit()

        flash("No slots are available for this trek.", "warning")
        return redirect(url_for("user_treks"))

    booking = Booking(
        user_id=user.id,
        trek_id=trek.id,
        booking_status="Booked",
        payment_status="not_required"
    )

    db.session.add(booking)

    trek.available_slots = trek.available_slots - 1

    if trek.available_slots == 0:
        trek.status = "Closed"

    db.session.commit()

    flash("Trek booked successfully.", "success")
    return redirect(url_for("user_bookings"))


@app.route("/user/bookings")
def user_bookings():
    access_check = check_access("user")

    if access_check:
        return access_check

    today = date.today()

    booked_records = Booking.query.filter_by(
        user_id=session["user_id"],
        booking_status="Booked"
    ).order_by(Booking.booking_date.desc()).all()

    bookings = []

    for booking in booked_records:
        if (
            booking.trek.status != "Completed"
            and booking.trek.end_date >= today
        ):
            bookings.append(booking)

    return render_template("user/bookings.html", bookings=bookings, today=today)


@app.route("/user/cancel-booking/<int:booking_id>", methods=["POST"])
def cancel_booking(booking_id):
    access_check = check_access("user")

    if access_check:
        return access_check

    booking = Booking.query.filter_by(
        id=booking_id,
        user_id=session["user_id"]
    ).first()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("user_bookings"))

    if booking.booking_status != "Booked":
        flash("This booking is already cancelled or completed.", "warning")
        return redirect(url_for("user_bookings"))

    trek = booking.trek

    if trek.status in ["Started", "Ongoing", "Completed"]:
        flash("This booking can no longer be cancelled.", "warning")
        return redirect(url_for("user_bookings"))

    if trek.end_date < date.today():
        flash("Past trek bookings cannot be cancelled.", "warning")
        return redirect(url_for("user_bookings"))

    was_full = trek.available_slots == 0

    booking.booking_status = "Cancelled"
    trek.available_slots += 1

    if was_full and trek.status == "Closed":
        trek.status = "Open"

    db.session.commit()

    flash("Booking cancelled successfully.", "success")
    return redirect(url_for("user_bookings"))


@app.route("/user/history")
def user_history():
    access_check = check_access("user")

    if access_check:
        return access_check

    today = date.today()

    all_bookings = Booking.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Booking.booking_date.desc()).all()

    history_bookings = []

    for booking in all_bookings:
        if (
            booking.booking_status in ["Cancelled", "Completed"]
            or booking.trek.status == "Completed"
            or booking.trek.end_date < today
        ):
            history_bookings.append(booking)

    return render_template(
        "user/history.html",
        bookings=history_bookings,
        today=today
    )


@app.route("/user/profile", methods=["GET", "POST"])
def user_profile():
    access_check = check_access("user")

    if access_check:
        return access_check

    user = User.query.get(session["user_id"])

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone_number = request.form.get("phone_number", "").strip()

        if not name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("user_profile"))

        if not phone_number:
            flash("Phone number cannot be empty.", "danger")
            return redirect(url_for("user_profile"))

        if not phone_number.isdigit() or len(phone_number) != 10:
            flash("Phone number must be exactly 10 digits.", "danger")
            return redirect(url_for("user_profile"))

        user.name = name
        user.phone_number = phone_number

        db.session.commit()

        session["name"] = user.name

        flash("Profile updated successfully.", "success")
        return redirect(url_for("user_profile"))

    return render_template(
        "user/profile.html",
        user=user
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_admin()

    app.run(debug=True)
from flask import Flask, render_template, flash, redirect, url_for
from werkzeug.security import generate_password_hash
from models import db, User

app = Flask(__name__)

app.config["SECRET_KEY"] = "dev-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///trekking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


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
        print("Admin user created")
    else:
        print("Admin user already exists")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/login")
def login():
    flash("Login page will be added later", "info")
    return redirect(url_for("home"))


@app.route("/register")
def register():
    flash("Registration page will be added later", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_admin()

    app.run(debug=True)
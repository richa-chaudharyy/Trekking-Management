from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")

    bookings = db.relationship("Booking", backref="user", lazy=True)
    staff_profile = db.relationship("StaffProfile", backref="user", uselist=False, lazy=True)
    assigned_treks = db.relationship("Trek", back_populates="assigned_staff", lazy=True)

    def __repr__(self):
        return f"<User {self.email}>"


class StaffProfile(db.Model):
    __tablename__ = "staff_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    bio = db.Column(db.Text)

    def __repr__(self):
        return f"<StaffProfile {self.user_id}>"


class Trek(db.Model):
    __tablename__ = "treks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    assigned_staff = db.relationship("User", back_populates="assigned_treks")
    bookings = db.relationship("Booking", backref="trek", lazy=True)

    def __repr__(self):
        return f"<Trek {self.name}>"


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey("treks.id"), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    booking_status = db.Column(db.String(20), nullable=False, default="Booked")
    payment_status = db.Column(db.String(20), nullable=False, default="not_required")

    def __repr__(self):
        return f"<Booking {self.id}>"
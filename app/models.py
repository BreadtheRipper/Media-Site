# models.py
from flask_login import UserMixin  # Ensure UserMixin is imported
from . import db

class User(db.Model, UserMixin):  # Inherit from UserMixin
    __tablename__ = 'user'  # Correct table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    uploads = db.relationship('Upload', backref='user', lazy=True)  # Relationship to Upload

    def __repr__(self):
        return f'<User {self.username}>'  # Add a repr for better debugging


class Upload(db.Model):
    __tablename__ = 'upload'  # Define a table name for consistency
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Changed to user_id for clarity
    share_token = db.Column(db.String(36), unique=True, nullable=True)  # Unique token for sharing

    def __repr__(self):
        return f'<Upload {self.title}>'

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

# IMPORTING MODULE FOR AUTH, LOGIN
from flask_login import LoginManager, login_user, logout_user, login_required
#IMPORTING MODULE FOR DATE, TIME
import datetime

# IMPORTING MODEL FILE
from models import db, User

# IMPORTING WERZEUG FOR CHECKING PASSWORD HASH AND TO GENERATE PASSWORD HASH
from werkzeug.security import check_password_hash, generate_password_hash

# IMPORTING JWT FOR CREATING ACCESS_TOKEN AND OTHER
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt

load_dotenv()

login_manager = LoginManager()


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///auth.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['JWT_SECRET_KEY'] =os.getenv("JWT_SECRET_KEY")

login_manager.init_app(app)
db.init_app(app)

jwt = JWTManager(app)

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/login", methods=['POST'])
def login():

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400


    user_exists = db.session.scalar(db.select(User).where(User.email == email))

    if not user_exists:
        return jsonify({"error": "Wrong email or password"}), 401

    if not check_password_hash(user_exists.password, password):
        return jsonify({"error": "Wrong email or password"}), 401

    if user_exists.status != "active":
        return jsonify({"error": "This account is inactive."}), 403

    access_token = create_access_token({
        "identity": user_exists.email,
        "user_id" : user_exists.id,
        "status": user_exists.status,
        "role": user_exists.role
    })
    
    login_user(user_exists)

    return jsonify({"access_token": access_token}), 200 
    



if __name__ == "__main__":
    app.run(debug=True, port=5005)
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv

# IMPORTING MODULE FOR AUTH, LOGIN

# IMPORTING MODULE FOR DATE, TIME
import datetime

# IMPORTING MODEL FILE
from models import db, User, RevokedToken

# IMPORTING WERZEUG FOR CHECKING PASSWORD HASH AND TO GENERATE PASSWORD HASH
from werkzeug.security import check_password_hash, generate_password_hash

# IMPORTING JWT FOR CREATING ACCESS_TOKEN AND OTHER
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt

load_dotenv()


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///auth.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['JWT_SECRET_KEY'] =os.getenv("JWT_SECRET_KEY")

db.init_app(app)

jwt = JWTManager(app)

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):

    token = db.session.scalar(
        db.select(RevokedToken).where(
            RevokedToken.jti == jwt_payload["jti"]
        )
    )
    
    return token is not None

with app.app_context():
    db.create_all()


@app.route("/login", methods=['POST'])
def login():

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400
    
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

    access_token = create_access_token(
        identity=str(user_exists.id),
        additional_claims={"role": user_exists.role}
    )
    

    return jsonify({"access_token": access_token}), 200 
    
@app.route("/register", methods=['POST'])
def register():

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    name = data.get('name')
    last_name = data.get('last_name')
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    if name and last_name and username and email and password and confirm_password:


        username_exists = db.session.scalar(db.select(User).where(User.username == username))

        if username_exists:
            return jsonify({"error": "User with this username already exists"}), 409
        

        email_exists = db.session.scalar(db.select(User).where(User.email == email))

        if email_exists:
            return jsonify({"error": "User with this email exists"}), 409

        # CREATE EMAIL VERIFICATION LATER

        if password != confirm_password:
            return jsonify({"error": "Passwords do not match"}) , 400

        new_user = User(
            name=name,
            last_name=last_name,
            username=username,
            email=email,
            password= generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        return jsonify({"success": "You have successfully registered."}), 201


    else:
        return jsonify({"error": "You need to enter all fields"}), 400
    

@app.route("/logout", methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]

    revoked_token = RevokedToken(jti=jti)
    db.session.add(revoked_token)
    db.session.commit()

    return jsonify({"success": "You have successfully logged out."}), 200

@app.route("/change-password", methods=['POST'])
@jwt_required()
def change_password():

    # DODATI RUCNU VALIDACIJU SIFRE DA NE BI KORISNIK PREKO JSON-A DIREKTNO POSLAO PODATKE OVOJ RUTI 

    user_id = get_jwt_identity()

    user_exists = db.session.scalar(db.select(User).where(User.id == user_id))

    if not user_exists:
        return jsonify({"error": "User with this ID does not exist!"}), 404

    if user_exists.status != "active":
        return jsonify({"error": "This user profile is not active"}), 403

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400
    
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    confirm_new_password = data.get("confirm_new_password")

    if not current_password or not new_password or not confirm_new_password:
        return jsonify({"error": "You didnt send some of these fields: current password, new password, confirm new password"}), 400

    if not check_password_hash(user_exists.password, current_password):
        return jsonify({"error": "Your current password is not correct"}), 400

    if new_password != confirm_new_password:
        return jsonify({"error": "New password do not match"}), 400

    user_exists.password = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({"success": "Your password has been changed successfully."}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5005)
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from dotenv import load_dotenv
import requests

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# IMPORTING MODULE FOR DATE, TIME
import datetime

# IMPORTING MODEL FILE
from models import db, User, RevokedToken, Address

# IMPORTING WERZEUG FOR CHECKING PASSWORD HASH AND TO GENERATE PASSWORD HASH
from werkzeug.security import check_password_hash, generate_password_hash

# IMPORTING JWT FOR CREATING ACCESS_TOKEN AND OTHER
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt, create_refresh_token
from flask_jwt_extended import decode_token
from flask_jwt_extended.exceptions import JWTDecodeError
from jwt.exceptions import InvalidTokenError
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///auth.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['JWT_SECRET_KEY'] =os.getenv("JWT_SECRET_KEY")

NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL")

serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

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

    data = request.get_json(silent=True)

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

    if not user_exists.email_verified:
        return jsonify({
            "error": "Please verify your email address before logging in."
        }), 403

    access_token = create_access_token(
        identity=str(user_exists.id),
        additional_claims={"role": user_exists.role}
    )

    refresh_token = create_refresh_token(identity=str(user_exists.id))
    

    return jsonify({"access_token": access_token, "refresh_token": refresh_token}), 200 
    
@app.route("/register", methods=['POST'])
def register():

    data = request.get_json(silent=True)

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

        verification_token = serializer.dumps(
            new_user.email,
            salt="email-verification"
        )

        verification_url = (
            f"http://127.0.0.1:5005/verify-email"
            f"?token={verification_token}"
        )

        try:
            response = requests.post(
                f"{NOTIFICATION_SERVICE_URL}/send-verification-email",
                json={
                    "email": new_user.email,
                    "verification_url": verification_url
                },
                timeout=5
            )

            response.raise_for_status()

        except requests.RequestException:
            return jsonify({
                "success": "You have successfully registered.",
                "warning": "Your account was created, but the verification email could not be sent."
            }), 201

        return jsonify({
            "success": "You have successfully registered. Please check your email to verify your account."
        }), 201


    else:
        return jsonify({"error": "You need to enter all fields"}), 400


@app.route("/verify-email", methods=['GET'])
def verify_email():
    token = request.args.get("token")

    if not token:
        return jsonify({"error": "Verification token is required."}) , 400

    try:
        email = serializer.loads(
            token,
            salt="email-verification",
            max_age=3600,
        )
    except SignatureExpired:
        return jsonify({"error": "Verification token has expired."}) , 400
    
    except BadSignature:
        return jsonify({"error": "Invalid verification token."}) , 400

    user = db.session.scalar(db.select(User).where(User.email == email))

    if not user:
        return jsonify({"error": "User not found."}), 404

    if user.email_verified:
        return jsonify({"message": "Your email address is already verified."}), 200

    user.email_verified = True
    db.session.commit()

    return jsonify({
        "success": "Your email address has been verified successfully."
    }), 200

@app.route("/logout", methods=["POST"])
@jwt_required(refresh=True)
def logout():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    access_token = data.get("access_token")

    if not isinstance(access_token, str) or not access_token.strip():
        return jsonify({"error": "Access token is required."}), 400

    # Refresh token je već proveren kroz dekorator.
    refresh_payload = get_jwt()

    # Proveravamo potpis access tokena, čak i ako je istekao.
    try:
        access_payload = decode_token(access_token, allow_expired=True)
    except (InvalidTokenError, JWTDecodeError):
        return jsonify({"error": "Invalid access token."}), 400

    if access_payload.get("type") != "access":
        return jsonify({"error": "An access token is required."}), 400

    if access_payload["sub"] != refresh_payload["sub"]:
        return jsonify({
            "error": "Both tokens must belong to the same user."
        }), 403

    # Oba ID-a čuvamo u jednoj transakciji.
    try:
        for jti in (access_payload["jti"], refresh_payload["jti"]):
            already_revoked = db.session.scalar(
                db.select(RevokedToken).where(RevokedToken.jti == jti)
            )

            if not already_revoked:
                db.session.add(RevokedToken(jti=jti))

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not complete logout."}), 500

    return jsonify({
        "success": "You have successfully logged out."
    }), 200

@app.route("/change-password", methods=['POST'])
@jwt_required()
def change_password():

    # DODATI RUCNU VALIDACIJU SIFRE DA NE BI KORISNIK PREKO JSON-A DIREKTNO POSLAO PODATKE OVOJ RUTI 

    user_id = int(get_jwt_identity())

    user_exists = db.session.scalar(db.select(User).where(User.id == user_id))

    if not user_exists:
        return jsonify({"error": "User with this ID does not exist!"}), 404

    if user_exists.status != "active":
        return jsonify({"error": "This user profile is not active"}), 403

    data = request.get_json(silent=True)

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


@app.route("/refresh-token", methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if not user:
        return jsonify({"error": "User not found."}), 404

    if user.status != "active":
        return jsonify({"error": "This account is inactive."}), 403
    
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "role": user.role
        }
    )

    return jsonify({"access_token": access_token}), 200


@app.route("/profile")
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if not user:
        return jsonify({"error": "User not found."}), 404

    if user.status != "active":
        return jsonify({"error": "This account is inactive."}), 403

    return jsonify(
        {
            "name": user.name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status":user.status
        }
    )

@app.route("/edit-profile", methods=["PATCH"])
@jwt_required()
def edit_profile():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if not user:
        return jsonify({"error": "User not found."}), 404

    if user.status != "active":
        return jsonify({"error": "This account is inactive."}), 403

    allowed_fields = {"name", "last_name", "username"}

    if not data:
        return jsonify({"error": "No fields provided."}), 400

    for field in data:
        if field not in allowed_fields:
            return jsonify({"error": "Only name, last_name and username can be updated."}), 400

    for field, value in data.items():
        if not isinstance(value, str) or not value.strip():
            return jsonify({"error": f"{field} must be a non-empty string."}), 400

    if "username" in data:
        username = data["username"].strip()

        username_exists = db.session.scalar(
            db.select(User).where(
                User.username == username,
                User.id != user.id
            )
        )

        if username_exists:
            return jsonify({
                "error": "User with this username already exists."
            }), 409

    if "name" in data:
        user.name = data["name"].strip()

    if "last_name" in data:
        user.last_name = data["last_name"].strip()

    if "username" in data:
        user.username = username

    db.session.commit()

    return jsonify({
        "success": "Your profile has been updated successfully."
    }), 200

@app.route("/deactivate-account", methods=['PATCH'])
@jwt_required()
def deactivate_account():

    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))

    if not user:
        return jsonify({"error": "This user does not exist!"}), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    current_password = data.get("current_password")

    if not current_password or not isinstance(current_password, str):    
        return jsonify({"error": "Current password is required and must be a string."}), 400

    if not check_password_hash(user.password, current_password):
        return jsonify({"error": "Your current password is incorrect."}), 400

    if user.status == "inactive":
        return jsonify({"error": "Your status is already inactive"}), 400

    user.status = "inactive"
    db.session.commit()

    return jsonify({"success": "Your account has been deactivated successfully."}), 200


@app.route("/addresses", methods=['POST'])
@jwt_required()
def add_address():

    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "This user does not exist!"}), 404
    
    if user.status != "active":
        return jsonify({"error": "This account is inactive."}), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    fields = {
        "name": data.get("name"),
        "last_name": data.get("last_name"),
        "street_name": data.get("street_name"),
        "street_number": data.get("street_number"),
        "country": data.get("country"),
        "postal_code": data.get("postal_code"),
        "city": data.get("city"),
        "phone_number": data.get("phone_number"),
    }

    for field, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            return jsonify({
                "error": f"{field} must be a non-empty string."
            }), 400

        fields[field] = value.strip()
        

    new_address = Address(user_id=user_id,**fields)

    db.session.add(new_address)
    db.session.commit()

    return jsonify({"success": "New address has been added successfully"}), 201

@app.route("/addresses", methods=['GET'])
@jwt_required()
def show_addresses():

    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "This user does not exist!"}), 404

    if user.status != "active":
        return jsonify({"error": "This account is inactive."}), 403

    all_addresses = db.session.scalars(db.select(Address).where(Address.user_id == user_id))

    addresses = [
        {
            "id": address.id,
            "name": address.name,
            "last_name": address.last_name,
            "street_name": address.street_name,
            "street_number": address.street_number,
            "country": address.country,
            "postal_code": address.postal_code,
            "city": address.city,
            "phone_number": address.phone_number
        }
        for address in all_addresses
    ]

    if not addresses:
        return jsonify({"addresses": addresses}), 200

    return jsonify({"addresses": addresses}), 200

@app.route("/addresses/<int:address_id>", methods=["PATCH"])
@jwt_required()
def edit_address(address_id):

    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "This user does not exist!"}), 404

    if user.status != "active":
        return jsonify({"error": "This account is inactive."}), 403

    data = request.get_json(silent=True)

    if not isinstance(data , dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if not data:
        return jsonify({"error": "No fields provided."}), 400


    allowed_fields = ["name", "last_name", "street_name", "street_number", "country", "postal_code", "city", "phone_number"]

    for field in data:
        if field not in allowed_fields:
            return jsonify({"error": "You can only edit ('name', 'last name', 'street name', 'street number', 'country', 'postal code', 'city', 'phone number')"}), 400

    for field, value in data.items():

        if not isinstance(value, str) or not value.strip():
            return jsonify({"error": f"{field} must be a non-empty string."}), 400

    old_address = db.session.scalar(db.select(Address).where(Address.id == address_id, Address.user_id == user_id))

    if not old_address:
        return jsonify({"error": "Address not found."}), 404

    if "name" in data:
        old_address.name = data.get('name').strip()

    if "last_name" in data:
        old_address.last_name = data.get('last_name').strip()

    if "street_name" in data:
        old_address.street_name = data.get('street_name').strip()

    if "street_number" in data:
        old_address.street_number = data.get("street_number").strip()

    if "country" in data:
        old_address.country = data.get('country').strip()

    if "postal_code" in data:
        old_address.postal_code = data.get("postal_code").strip()

    if "city" in data:
        old_address.city = data.get('city').strip()

    if "phone_number" in data:
        old_address.phone_number = data.get("phone_number").strip()

    db.session.commit()
    return jsonify({"success": "Your address has been updated successfully."}), 200


@app.route("/addresses/<int:address_id>", methods=['DELETE'])
@jwt_required()
def delete_address(address_id):

    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "This user does not exist!"}), 404

    if user.status != "active":
        return jsonify({"error": "This account is inactive."}), 403

    address = db.session.scalar(db.select(Address).where(Address.id == address_id, Address.user_id == user_id))

    if not address:
        return jsonify({"error": "There is no address with that ID"}), 404

    db.session.delete(address)
    db.session.commit()

    return jsonify({"success": "Your address has been deleted successfully."}), 200










if __name__ == "__main__":
    app.run(debug=True, port=5005)
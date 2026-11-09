from flask import Flask, request, jsonify
from flask_migrate import Migrate
import requests
import secrets

from models import db , Cart, CartItem

from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity

import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cart.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL")

def check_token_with_auth():
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/validate-token",
            headers={
                "Authorization": request.headers.get("Authorization", ""),
            },
            timeout=5,
            allow_redirects=False
                        
        )

    except requests.RequestException:
        return jsonify({"error": "Authentication service is unavailable."}), 503

    if response.status_code in (401,403,422):
        return jsonify({"error": "Access token is not accepted."}), response.status_code

    if response.status_code != 200:
        return jsonify({"error": "Could not verify access token."}), 503

    return None


@app.route("/cart/items", methods=['POST'])
@jwt_required(optional=True)
def add_item():

    user_id = get_jwt_identity()

    if user_id is not None:
        auth_error = check_token_with_auth()
        if auth_error is not None:
            return auth_error

        user_id = int(user_id)

    data = request.get_json()
    if not isinstance(data , dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if "sku" not in data:
        return jsonify({"error": "SKU is required."}), 400

    sku = data.get("sku")
    if not isinstance(sku, str) or not sku.strip():
        return jsonify({"error": "SKU needs to be an string and not empty field."}), 400

    sku = sku.strip()

    if "quantity" not in data:
        return jsonify({"error": "Quantity is required."}), 400

    quantity = data.get("quantity")

    if not isinstance(quantity, int) or isinstance(quantity, bool):
        return jsonify({"error": "Quantity needs to be a integer and not boolen."}), 400

    if quantity <= 0:
        return jsonify({"error": "Quantity must be greater than zero."}), 400
    
    if user_id is not None:
        cart = db.session.scalar(
            db.select(Cart).where(Cart.user_id == user_id)
        )

        if cart is None:
            cart = Cart(user_id=user_id)
            db.session.add(cart)
            db.session.flush()

    else:
        guest_token = request.cookies.get("guest_token")
        cart = None

        if guest_token:

            cart = db.session.scalar(db.select(Cart).where(Cart.guest_token == guest_token, Cart.user_id.is_(None)))


        if cart is None:

            guest_token = secrets.token_urlsafe(32)

            cart = Cart(
                guest_token=guest_token
            )

            db.session.add(cart)
            db.session.flush()

    try:
        response = requests.get(
            f"{CATALOG_SERVICE_URL}/variants/{sku}",
            timeout=5
        )

        if response.status_code == 404:
            db.session.rollback()
            return jsonify({"error": "SKU not found."}), 404

        if response.status_code != 200:
            db.session.rollback()
            return jsonify({"error": "Catalog service is unavailable."}), 503

        
    except requests.RequestException:
        db.session.rollback()
        return jsonify({"error": "Authentication service is unavailable."}), 503


    try:
        inventory_response = requests.get(
            f"{INVENTORY_SERVICE_URL}/inventory/{sku}",
            timeout=5
        )

        if inventory_response.status_code == 404:
            db.session.rollback()
            return jsonify({"error": "Inventory record not found."}), 404

        if inventory_response.status_code != 200:
            db.session.rollback()
            return jsonify({"error": "Inventory service not unavailable."}), 503

        inventory_data = inventory_response.json()

        if not isinstance(inventory_data, dict):
            db.session.rollback()
            return jsonify({"error": "Invalid inventory response."}), 502

        available_quantity = inventory_data.get("available_quantity")

        if not isinstance(available_quantity, int) or isinstance(available_quantity, bool):
            db.session.rollback()
            return jsonify({"error": "Invalid available quantity."}), 502

    except requests.RequestException:
        db.session.rollback()
        return jsonify({"error": "Inventory service is unavailable"}), 503

    cart_item = db.session.scalar(
        db.select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.sku == sku
        )
    )

    old_quantity = 0
    if cart_item is not None:
        old_quantity = cart_item.quantity

    total_quantity = old_quantity + quantity
    remaining = available_quantity - total_quantity

    if remaining < 0:
        db.session.rollback()
        return jsonify({"error": "Not enough stock available."}), 409

    if cart_item is None:
        cart_item = CartItem(
            cart_id=cart.id,
            sku=sku,
            quantity=total_quantity
        )
        db.session.add(cart_item)
    else:
        cart_item.quantity = total_quantity

    db.session.commit()

    response = jsonify({"success": "Successfully Added to cart"})

    if user_id is None:
        response.set_cookie(
            "guest_token",
            guest_token,
            max_age=60*60*24*30,
            httponly=True,
            samesite="Lax",
            secure=False,
        )

    return response, 200

@app.route("/cart/items/<string:sku>", methods=['PATCH'])
@jwt_required(optional=True)
def update_cart_item(sku):

    user_id = get_jwt_identity()

    if user_id is not None:
        auth_error = check_token_with_auth()
        if auth_error is not None:
            return auth_error

        user_id = int(user_id)

    if user_id is not None:
        user_cart = db.session.scalar(db.select(Cart).where(Cart.user_id == user_id))

        if not user_cart:
            return jsonify({"error": "Cart not found."}), 404

    else:
        guest_token = request.cookies.get("guest_token")

        if not guest_token:
            return jsonify({"error": "Guest cart not found."}), 404

        user_cart = db.session.scalar(db.select(Cart).where(Cart.guest_token == guest_token, Cart.user_id.is_(None)))

        if not user_cart:
            return jsonify({"error": "Guest cart not found."}), 404
        
    cart_item = db.session.scalar(db.select(CartItem).where(CartItem.cart_id == user_cart.id, CartItem.sku == sku))

    if not cart_item:
        return jsonify({"error": "Cart item not found."}), 404

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    new_quantity = data.get("quantity")

    if not isinstance(new_quantity , int) or isinstance(new_quantity, bool):
        return jsonify({"error": "New quantity needs to be a integer and not boolen"}), 400

    if new_quantity <= 0:
        return jsonify({"error": "Quantity must be greater than zero."}), 400


    try:
        response = requests.get(
            f"{INVENTORY_SERVICE_URL}/inventory/{sku}",
            timeout=5
        )

        if response.status_code == 404:
            return jsonify({"error": "Inventory record not found."}), 404

        if response.status_code != 200:
            return jsonify({"error": "Inventory service is unavailable."}), 503
        
        inventory_data = response.json()

        if not isinstance(inventory_data, dict):
            return jsonify({"error": "Invalid inventory response."}), 502

        available_quantity = inventory_data.get("available_quantity")

        if not isinstance(available_quantity, int) or isinstance(available_quantity, bool):
            return jsonify({"error": "Invalid available quantity."}), 502
        
    except requests.RequestException:
        return jsonify({"error": "Inventory service is unavailable"}), 503

    remaining = available_quantity - new_quantity

    if remaining < 0:
        return jsonify({"error": "Not enough stock available."}), 409
    
    cart_item.quantity = new_quantity
    db.session.commit()

    return jsonify({"success": "Cart item quantity has been updated successfully."}), 200

@app.route("/cart/items/<string:sku>", methods=['DELETE'])
@jwt_required(optional=True)
def remove_cart_item(sku):

    user_id = get_jwt_identity()

    if user_id is not None:
        auth_error = check_token_with_auth()
        if auth_error is not None:
            return auth_error

        user_id = int(user_id)

    if user_id is not None:
        user_cart = db.session.scalar(db.select(Cart).where(Cart.user_id == user_id))

        if not user_cart:
            db.session.rollback()
            return jsonify({"error": "Cart not found."}), 404

    else:

        guest_token = request.cookies.get("guest_token")

        if not guest_token:
            return jsonify({"error": "Guest token not found."}), 404

        user_cart = db.session.scalar(db.select(Cart).where(Cart.guest_token == guest_token, Cart.user_id.is_(None)))

        if not user_cart:
            db.session.rollback()
            return jsonify({"error": "Cart not found."}), 404

    cart_item = db.session.scalar(db.select(CartItem).where(CartItem.sku == sku, CartItem.cart_id == user_cart.id))

    if not cart_item:
        return jsonify({"error": "Item in cart not found."}), 404

    db.session.delete(cart_item)
    db.session.commit()

    return jsonify({"success": "Item successfully removed."}), 200

    


if __name__ == "__main__":
    app.run(debug=True, port=5008)
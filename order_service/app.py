from flask import Flask, request, jsonify
from flask_migrate import Migrate
from models import db, Order, OrderItems
from flask_jwt_extended import get_jwt_identity, jwt_required, JWTManager
from dotenv import load_dotenv
import os
import requests
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError


load_dotenv()

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///order.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
SHOPPING_CART_SERVICE_URL = os.getenv("SHOPPING_CART_SERVICE_URL")

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


@app.route("/orders", methods=["POST"])
@jwt_required(optional=True)
def create_order():

    user_id = get_jwt_identity()

    if user_id is not None:
        auth_error = check_token_with_auth()

        if auth_error is not None:
            return auth_error

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid token identity."}), 401

    # Podaci koje korisnik šalje Order servisu.
    order_data = request.get_json(silent=True)

    if not isinstance(order_data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if "order_address" not in order_data:
        return jsonify({"error": "Order address is required."}), 400

    order_address = order_data.get("order_address")

    if not isinstance(order_address, str) or not order_address.strip():
        return jsonify({
            "error": "Order address must be a non-empty string."
        }), 400

    order_address = order_address.strip()

    # Preuzimanje proverene korpe.
    try:
        response = requests.get(
            f"{SHOPPING_CART_SERVICE_URL}/cart/checkout/validate",
            headers={
                "Authorization": request.headers.get("Authorization", "")
            },
            cookies={
                "guest_token": request.cookies.get("guest_token", "")
            },
            timeout=5,
            allow_redirects=False
        )

    except requests.RequestException:
        return jsonify({
            "error": "Shopping cart service is unavailable."
        }), 503

    if response.status_code not in (200, 400, 401, 403, 404, 409, 422):
        return jsonify({
            "error": "Shopping cart service is unavailable."
        }), 503

    try:
        data = response.json()
    except ValueError:
        return jsonify({
            "error": "Invalid shopping cart response."
        }), 502

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid shopping cart response."
        }), 502

    # Prosleđujemo konkretan problem koji je Cart servis pronašao.
    if response.status_code != 200:
        return jsonify(data), response.status_code

    items = data.get("items")

    if not isinstance(items, list) or not items:
        return jsonify({
            "error": "Cart items must be a non-empty list."
        }), 502

    # Provera ukupne cene i iznosa popusta.
    try:
        total_price = Decimal(str(data.get("total_price")))
        discount_amount = Decimal(str(data.get("discount_amount")))
    except InvalidOperation:
        return jsonify({"error": "Invalid cart prices."}), 502

    if (
        not total_price.is_finite()
        or not discount_amount.is_finite()
        or total_price < 0
        or discount_amount < 0
    ):
        return jsonify({"error": "Invalid cart prices."}), 502

    # Provera svih stavki pre upisa u bazu.
    validated_items = []
    items_total = Decimal("0.00")

    for item in items:
        if not isinstance(item, dict):
            return jsonify({
                "error": "Each cart item must be an object."
            }), 502

        sku = item.get("sku")

        if not isinstance(sku, str) or not sku.strip():
            return jsonify({"error": "Invalid item SKU."}), 502

        quantity = item.get("quantity")

        if (
            not isinstance(quantity, int)
            or isinstance(quantity, bool)
            or quantity <= 0
        ):
            return jsonify({"error": "Invalid item quantity."}), 502

        try:
            unit_price = Decimal(str(item.get("unit_price")))
        except InvalidOperation:
            return jsonify({"error": "Invalid item price."}), 502

        if not unit_price.is_finite() or unit_price <= 0:
            return jsonify({"error": "Invalid item price."}), 502

        items_total += unit_price * quantity

        validated_items.append({
            "sku": sku.strip(),
            "quantity": quantity,
            "unit_price": unit_price
        })

    # Ukupna cena mora odgovarati zbiru stavki umanjenom za popust.
    if total_price != items_total - discount_amount:
        return jsonify({"error": "Invalid cart totals."}), 502

    order_number = str(uuid4())

    # Zajednički upis porudžbine i svih njenih stavki.
    try:
        order = Order(
            user_id=user_id,
            order_number=order_number,
            price=total_price,
            order_address=order_address,
            order_status="pending"
        )

        db.session.add(order)
        db.session.flush()

        for item in validated_items:
            order_item = OrderItems(
                order_id=order.id,
                sku=item["sku"],
                quantity=item["quantity"],
                unit_price=item["unit_price"]
            )

            db.session.add(order_item)

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not create order."}), 500

    return jsonify({
        "success": "Order has been created successfully.",
        "order_number": order_number,
        "total_price": str(total_price),
        "discount_amount": str(discount_amount)
    }), 201



if __name__ == "__main__":
    app.run(debug=True, port=5003, host="0.0.0.0")
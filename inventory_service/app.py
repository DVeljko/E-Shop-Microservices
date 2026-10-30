from flask import Flask, request, jsonify
from models import db, InventoryRecords, StockReservation
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, jwt_required, get_jwt
import requests

import os
from dotenv import load_dotenv

from secrets import compare_digest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

load_dotenv()

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

INVENTORY_SERVICE_KEY = os.getenv("INVENTORY_SERVICE_KEY")

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL")
PRODUCT_CATALOG_URL = os.getenv("PRODUCT_CATALOG_URL")

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

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

@app.route("/inventory", methods=["POST"])
@jwt_required()
def add_inventory():
    auth_error = check_token_with_auth()

    if auth_error is not None:
        return auth_error

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access."}), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    sku = data.get("sku")

    if not isinstance(sku, str) or not sku.strip():
        return jsonify({
            "error": "SKU must be a non-empty string."
        }), 400

    sku = sku.strip()

    inventory_exists = db.session.scalar(
        db.select(InventoryRecords).where(InventoryRecords.sku == sku)
    )

    if inventory_exists:
        return jsonify({
            "error": "Inventory for this SKU already exists."
        }), 409

    try:
        response = requests.get(
            f"{PRODUCT_CATALOG_URL}/variants/{sku}",
            timeout=5,
            allow_redirects=False
        )

    except requests.RequestException:
        return jsonify({
            "error": "Product catalog service is unavailable."
        }), 503

    if response.status_code == 404:
        return jsonify({
            "error": "An active variant with this SKU was not found."
        }), 404

    if response.status_code != 200:
        return jsonify({
            "error": "Could not verify SKU with the product catalog service."
        }), 502

    new_inventory = InventoryRecords(
        sku=sku,
    )

    db.session.add(new_inventory)
    db.session.commit()

    return jsonify({
        "success": "Inventory has been created successfully.",
        "sku": new_inventory.sku,
        "quantity": new_inventory.quantity
    }), 201

@app.route("/inventory/<string:sku>", methods=['GET'])
def availability_check(sku):

    inventory = db.session.scalar(db.select(InventoryRecords).where(InventoryRecords.sku == sku))

    if not inventory:
        return jsonify({"error": "SKU not found."}), 404

    return jsonify({
        "sku": inventory.sku,
        "quantity": inventory.quantity,
        "available": inventory.quantity > 0
    }), 200

    


@app.route("/inventory/adjustments", methods=['PATCH'])
@jwt_required()
def adjust_inventory():

    auth_error = check_token_with_auth()

    if auth_error is not None:
        return auth_error

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error":"Only admin can access."}), 403

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if "sku" not in data:
        return jsonify({"error": "SKU is required."}), 400

    sku = data.get("sku")
    if not isinstance(sku, str) or not sku.strip():
        return jsonify({"error": "SKU needs to be a string and not empty field."}), 400

    sku = sku.strip()

    if "quantity_change" not in data:
        return jsonify({"error": "Quantity changes is required."}), 400

    quantity_change = data.get("quantity_change")
    if not isinstance(quantity_change, int) or isinstance(quantity_change, bool):
        return jsonify({"error": "Quantity change needs to be an integer and not boolean."}), 400

    sku_exists = db.session.scalar(db.select(InventoryRecords).where(InventoryRecords.sku == sku))
    if not sku_exists:
        return jsonify({"error": "Product with that SKU does not exist."}), 404

    validate_quantity = sku_exists.quantity + quantity_change
    if validate_quantity < 0:
        return jsonify({"error": "You cant go to negative number with quantity."}), 400

    sku_exists.quantity = validate_quantity

    db.session.commit()

    return jsonify({
        "success": "Inventory quantity has been updated successfully.",
        "sku": sku_exists.sku,
        "quantity": sku_exists.quantity,
    }) , 200

@app.route("/inventory/reservations", methods=["POST"])
def inventory_reservation():
    
    if not INVENTORY_SERVICE_KEY:
        return jsonify({"error": "Service authentication is not configured."}), 503

    provided_key = request.headers.get("X-Service-Key", "")

    if not compare_digest(
        provided_key.encode("utf-8"),
        INVENTORY_SERVICE_KEY.encode("utf-8")
    ):
        return jsonify({"error": "Unauthorized service."}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    sku = data.get("sku")

    if not isinstance(sku, str) or not sku.strip():
        return jsonify({"error": "SKU must be a non-empty string."}), 400

    sku = sku.strip()

    order_id = data.get("order_id")

    if not isinstance(order_id, int) or isinstance(order_id, bool):
        return jsonify({"error": "Order ID must be an integer."}), 400

    if order_id <= 0:
        return jsonify({"error": "Order ID must be greater than zero."}), 400

    reserved_quantity = data.get("reserved_quantity")

    if (not isinstance(reserved_quantity, int)or isinstance(reserved_quantity, bool)):
        return jsonify({"error": "Reserved quantity must be an integer."}), 400

    if reserved_quantity <= 0:
        return jsonify({"error": "Reserved quantity must be greater than zero."}), 400

    try:
        # SQLite: zauzimamo pravo upisa pre čitanja stanja.
        db.session.execute(text("BEGIN IMMEDIATE"))

        inventory = db.session.scalar(db.select(InventoryRecords).where(InventoryRecords.sku == sku))

        if not inventory:
            db.session.rollback()
            return jsonify({"error": "SKU not found."}), 404

        reserved = db.session.scalars(db.select(StockReservation).where(StockReservation.inventory_id == inventory.id,StockReservation.status == "reserved")).all()

        already_reserved = 0

        for reserve in reserved:
            already_reserved += reserve.reserved_quantity

        available = inventory.quantity - already_reserved

        if reserved_quantity > available:
            db.session.rollback()
            return jsonify({"error": "Not enough stock available."}), 409

        new_reservation = StockReservation(
            inventory_id=inventory.id,
            order_id=order_id,
            reserved_quantity=reserved_quantity,
            status="reserved"
        )

        db.session.add(new_reservation)

        # Izvršavamo INSERT da dobijemo ID, pa potvrđujemo transakciju.
        db.session.flush()
        reservation_id = new_reservation.id
        db.session.commit()

    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "Inventory is temporarily unavailable. Please try again."}), 503

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not create reservation."}), 500

    return jsonify({
        "success": "Stock has been reserved successfully.",
        "reservation_id": reservation_id,
        "order_id": order_id,
        "sku": sku,
        "reserved_quantity": reserved_quantity
    }), 201


@app.route("/inventory/reservations/<int:reservation_id>/release", methods=['POST'])
def release_reservation(reservation_id):

    if not INVENTORY_SERVICE_KEY:
        return jsonify({"error": "Service authentication is not configured."}), 503

    provided_key = request.headers.get("X-Service-Key", "")

    if not compare_digest(
        provided_key.encode("utf-8"),
        INVENTORY_SERVICE_KEY.encode("utf-8")
    ):
        return jsonify({"error": "Unauthorized service."}), 401

    try:
        db.session.execute(text("BEGIN IMMEDIATE"))
        reservation_exists = db.session.scalar(db.select(StockReservation).where(StockReservation.id == reservation_id))

        if not reservation_exists:

            db.session.rollback()
            return jsonify({"error": "Reservation not found."}), 404

        if reservation_exists.status == "released":

            db.session.rollback()
            return jsonify({"success": "Reservation is already released."}), 200

        if reservation_exists.status != "reserved":

            db.session.rollback()
            return jsonify({"error": "Only an active reservation can be released."}), 409

        reservation_exists.status = "released"
        db.session.commit()

    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "Could not release reservation."}), 500

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not release reservation."}), 500


    return jsonify({"success": "Reservation is released."}), 200

@app.route("/inventory/reservations/<int:reservation_id>/confirm", methods=['POST'])
def confirm_reservation(reservation_id):

    if not INVENTORY_SERVICE_KEY:
        return jsonify({"error": "Service authentication is not configured."}), 503

    provided_key = request.headers.get("X-Service-Key", "")

    if not compare_digest(
        provided_key.encode("utf-8"),
        INVENTORY_SERVICE_KEY.encode("utf-8")
    ):

        return jsonify({"error": "Unauthorized service."}), 401

    try:
        db.session.execute(text("BEGIN IMMEDIATE"))
        reservation_exists = db.session.scalar(db.select(StockReservation).where(StockReservation.id == reservation_id))

        
        if not reservation_exists:
            db.session.rollback()
            return jsonify({"error": "Reservation not found."}), 404

        if reservation_exists.status == "confirmed":
            db.session.rollback()
            return jsonify({"success": "Reservation is already confirmed."}), 200

        if reservation_exists.status != "reserved":
            db.session.rollback()
            return jsonify({"error": "Only an active reservation can be confirmed."}), 409

        inventory = db.session.get(InventoryRecords, reservation_exists.inventory_id)

        if not inventory:
            db.session.rollback()
            return jsonify({"error": "Inventory record not found."}), 404

        if inventory.quantity < reservation_exists.reserved_quantity:
            db.session.rollback()
            return jsonify({"error": "Not enough stock to confirm reservation."}), 409

        inventory.quantity -= reservation_exists.reserved_quantity

        reservation_exists.status = "confirmed"
        db.session.commit()

    except OperationalError:
        db.session.rollback()
        return jsonify({"error": "Could not confirm reservation"}), 500

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not confirm reservation."}), 500    

    return jsonify({"success": "Reservation has been confirmed successfully."}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5007)
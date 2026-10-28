from flask import Flask, request, jsonify
from models import db, InventoryRecords
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, jwt_required, get_jwt
import requests

import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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




    






if __name__ == "__main__":
    app.run(debug=True, port=5007)
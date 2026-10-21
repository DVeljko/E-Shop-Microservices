from flask import Flask, jsonify, request
from flask_migrate import Migrate
from models import db, Category, Product, ProductCategory, ProductImage, ProductVariant
import os
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, jwt_required, get_jwt


load_dotenv()

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///product_catalog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

@app.route("/categories", methods=['POST'])
@jwt_required()
def create_category():

    claims = get_jwt()
    role = claims.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access!"}), 403

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    name = data.get("name")
    parent_id = data.get("parent_id")

    if parent_id is not None:
        if not isinstance(parent_id, int) or isinstance(parent_id, bool):
            return jsonify({"error": "Parent ID must be an integer."}), 400
        
        parent_exists = db.session.scalar(db.select(Category).where(Category.id == parent_id))
        if not parent_exists:
            return jsonify({"error": "Parent category not found."}), 404

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "You need to enter a string and not empty field"}), 400

    name = name.strip()

    name_exists = db.session.scalar(db.select(Category).where(Category.name == name))
    if name_exists:
        return jsonify({"error": "Category with this name already exists!"}), 409

    new_category = Category(
        name=name,
        parent_id=parent_id
    )

    db.session.add(new_category)
    db.session.commit()

    return jsonify({"success": "Successfully created new category."}), 201

@app.route("/categories", methods=['GET'])
def show_all_categories():

    categories = Category.query.filter_by(is_active=True).all()

    data = [{
        "category_id": category.id,
        "names": category.name,
        "category_parent_id": category.parent_id,
    } 

        for category in categories
    
    ]

    return jsonify(data), 200

@app.route("/categories/<int:category_id>", methods=['PATCH'])
@jwt_required()
def edit_category(category_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access"}), 403
    
    category = db.session.scalar(db.select(Category).where(Category.id == category_id))

    if not category:
        return jsonify({"error": "Category with this ID does not exist!"}), 404

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400


    name = data.get("name")
    parent_id = data.get("parent_id")

    if "name" in data:
        if not isinstance(name , str) or not name.strip():
            return jsonify({"error": "You need to enter name as a string and not empty field"}), 400

        name = name.strip()

        name_exists = db.session.scalar(db.select(Category).where(Category.name == name, Category.id != category_id))

        if name_exists:
            return jsonify({"error": "There is already a category with that name!"}), 409

        category.name = name

    if "parent_id" in data:
        parent_id = data["parent_id"]

        if parent_id is not None:
            if not isinstance(parent_id, int) or isinstance(parent_id, bool):
                return jsonify({"error": "Parent ID must be an integer or null."}), 400

            if parent_id == category.id:
                return jsonify({"error": "A category cannot be its own parent."}), 400

            parent = db.session.get(Category, parent_id)

            if parent is None:
                return jsonify({"error": "Parent category not found."}), 404

        category.parent_id = parent_id


    db.session.commit()
    return jsonify({"success": "Category has been updated successfully."}), 200


@app.route("/categories/<int:category_id>", methods=['DELETE'])
@jwt_required()
def delete_category(category_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access"}), 403

    category = db.session.scalar(db.select(Category).where(Category.id == category_id))

    if not category:
        return jsonify({"error": "There is no category with that ID"}), 404

    if category.subcategories or category.products:
        return jsonify({"error": "Cannot delete a category with subcategories or products."}) , 409

    db.session.delete(category)
    db.session.commit()

    return jsonify({"success": "Successfully deleted category"}), 200




if __name__ == "__main__":
    app.run(debug=True)
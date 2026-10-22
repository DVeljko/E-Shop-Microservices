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


# PRODUCTS

@app.route("/products", methods=["POST"])
@jwt_required()
def add_product():

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access"}), 403

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    name = data.get("name")
    description = data.get("description")
    price = data.get("price")
    is_featured = data.get("is_featured")
    category_ids = data.get("category_ids")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "You need to enter a string and not empty field"}), 400

    name = name.strip()

    products_exist = db.session.scalar(db.select(Product).where(Product.name == name))

    if products_exist:
        return jsonify({"error": "Product with that name already exists."}), 409

    if not isinstance(description, str) or not description.strip():
        return jsonify({"error": "Description must be a non-empty string."}), 400

    if not isinstance(category_ids, list):
        return jsonify({"error": "Category IDS needs to be a list."}), 400

    categories = []

    for id in category_ids:
        if not isinstance(id, int) or isinstance(id, bool):
            return jsonify({"error": "Each category ID must be an integer."}), 400

        category_exists = db.session.scalar(db.select(Category).where(Category.id == id))

        if not category_exists:
            return jsonify({"error": "Category or subcategory does not exist."}), 404

        if category_exists not in categories:
            categories.append(category_exists)

    if not isinstance(price, (float, int)) or isinstance(price, bool):
        return jsonify({"error": "Price needs to be float or integer."}), 400

    if price <= 0:
        return jsonify({"error": "Price needs to be bigger than zero."}), 400
    
    if not isinstance(is_featured, bool):
        return jsonify({"error": "Is featured needs to be a bool."}), 400

    new_product = Product(
        name=name,
        description=description.strip(),
        price=price,
        is_featured=is_featured,
    )

    new_product.categories = categories

    db.session.add(new_product)
    db.session.commit()

    return jsonify({"success": "You have successfully added new product"}), 201

@app.route("/products" , methods=['GET'])
def show_all_products():

    products = Product.query.filter_by(is_active=True).all()

    data = [
        {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "sale_price": product.sale_price,
            "is_featured": product.is_featured

        }


        for product in products
    ]

    return jsonify(data), 200

@app.route("/products/<int:product_id>", methods=['PATCH'])
@jwt_required()
def edit_product(product_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access."}), 403

    product = db.session.scalar(db.select(Product).where(Product.id == product_id))

    if not product:
        return jsonify({"error": "Product with this ID does not exist."}), 404

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if "name" in data:
        new_name = data.get("name")
        if not isinstance(new_name, str) or not new_name.strip():
            return jsonify({"error": "You need to enter an string and not empty field."}), 400


        new_name = new_name.strip()
        new_name_exists = db.session.scalar(db.select(Product).where(Product.name == new_name, Product.id != product_id))
        if new_name_exists:
            return jsonify({"error": "Product with that name already exists."}), 409

        product.name = new_name

    if "description" in data:
        new_description = data.get("description")
        if not isinstance(new_description, str) or not new_description.strip():
            return jsonify({"error": "You need to enter an string and not empty field."}), 400

        product.description = new_description.strip()

    if "price" in data:
        new_price = data.get("price")
        if not isinstance(new_price, (int, float)) or isinstance(new_price, bool):
            return jsonify({"error": "The price needs to be an intger or float number."}) , 400

        if new_price <= 0:
            return jsonify({"error": "The price needs to be higher than 0."}), 400
        
        product.price = new_price

    if "sale_price" in data:
        new_sale_price = data.get("sale_price")

        if new_sale_price is not None:
            if not isinstance(new_sale_price, (int, float)) or isinstance(new_sale_price, bool):
                return jsonify({"error": "The sale price needs to be an integer or float number. "}) , 400


        product.sale_price = new_sale_price

    if "is_active" in data:
        new_is_active = data.get("is_active")  
        if not isinstance(new_is_active, bool):
            return jsonify({"error": "Active status needs to be a boolen."}), 400

        product.is_active = new_is_active



    if "is_featured" in data:
        new_is_featured = data.get("is_featured")
        if not isinstance(new_is_featured, bool):
            return jsonify({"error": "Featured status needs to be an boolean."}), 400

        
        product.is_featured = new_is_featured


    if product.sale_price is not None:
        if product.sale_price <= 0 or product.sale_price >= product.price:
            return jsonify({
                "error": "Sale price must be greater than zero and less than the regular price."
            }), 400

    db.session.commit()

    return jsonify({"success": "You have successfully updated product."}), 200

@app.route("/products/<int:product_id>", methods=['DELETE'])
@jwt_required()
def delete_product(product_id):

    claim = get_jwt()
    role = claim.get('role')

    if role != "admin":
        return jsonify({"error": "Only admin can access."}), 403

    product_exists = db.session.scalar(db.select(Product).where(Product.id == product_id))
    if not product_exists:
        return jsonify({"error": "Product with that ID does not exist."}), 404


    db.session.delete(product_exists)
    db.session.commit()

    return jsonify({"success": "You have successfully deleted a product."}), 200



@app.route("/products/<int:product_id>" , methods=['GET'])
def show_single_product(product_id):

    product_exists = db.session.scalar(db.select(Product).where(Product.id == product_id))
    if not product_exists or not product_exists.is_active:
        return jsonify({"error": "Product not found"}), 404

    data = {
        "id": product_exists.id,
        "name": product_exists.name,
        "description": product_exists.description,
        "price": product_exists.price,
        "sale_price": product_exists.sale_price,
        "is_active": product_exists.is_active,
        "is_featured": product_exists.is_featured
    }

    return jsonify(data), 200


if __name__ == "__main__":
    app.run(debug=True)
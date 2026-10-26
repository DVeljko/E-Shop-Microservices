from flask import Flask, jsonify, request
from flask_migrate import Migrate
from models import db, Category, Product, ProductCategory, ProductImage, ProductVariant
import os
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager, jwt_required, get_jwt
from decimal import Decimal, InvalidOperation
from sqlalchemy import func


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
        return jsonify({"error": "Product not found."}), 404

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

@app.route("/products/<int:product_id>/images", methods=['POST'])
@jwt_required()
def add_image_to_product(product_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only Admin can access."}), 403

    product_exists = db.session.scalar(db.select(Product).where(Product.id == product_id))
    if not product_exists:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if "image_url" not in data:
        return jsonify({"error": "Image URL is required."}), 400

    image_url = data.get("image_url")
    if not isinstance(image_url, str) or not image_url.strip():
        return jsonify({"error": "You need to enter a string and not empy field."}), 400

    image_url = image_url.strip()

    if "is_primary" not in data:
        return jsonify({"error": "Is primary is required."}), 400

    is_primary = data.get("is_primary")
    if not isinstance(is_primary, bool):
        return jsonify({"error": "Is primary must be a boolean"}), 400

    if "position" not in data:
        return jsonify({"error": "Position is required"}), 400

    position = data.get("position")
    if not isinstance(position, int) or isinstance(position, bool):
        return jsonify({"error": "Position needs to be an integer."}), 400

    if position < 0:
        return jsonify({"error": "Position cant be an negative number."}), 400


    if is_primary:
        primary_exists = db.session.scalar(db.select(ProductImage).where(ProductImage.product_id == product_id, ProductImage.is_primary == is_primary))

        if primary_exists:
            return jsonify({"error": "This product already has an primary image."}), 409


    new_image = ProductImage(
        product_id=product_id,
        image_url=image_url,
        is_primary=is_primary,
        position=position
    )

    db.session.add(new_image)
    db.session.commit()

    return jsonify({"success": " You have successfully added a new image for product."}) , 201


@app.route("/products/<int:product_id>/images/<int:image_id>", methods=['PATCH'])
@jwt_required()
def edit_product_image(product_id, image_id):

    claim = get_jwt()
    role = claim.get('role')

    if role != "admin":
        return jsonify({"error": "Only Admin can access."}), 403

    data = request.get_json()

    if not isinstance(data , dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    product_exits = db.session.scalar(db.select(Product).where(Product.id == product_id))
    if not product_exits:
        return jsonify({"error": "Product not found."}) , 404

    image_exists = db.session.scalar(db.select(ProductImage).where(ProductImage.product_id == product_id,ProductImage.id == image_id))
    if not image_exists: 
        return jsonify({"error": "Image not found."}), 404

    if "image_url" in data:
        new_image_url = data.get("image_url")
        if not isinstance(new_image_url, str) or not new_image_url.strip():
            return jsonify({"error": "Image URL needs to be an string and not empty field."}), 400   

        new_image_url = new_image_url.strip()
        image_exists.image_url = new_image_url

    if "is_primary" in data:
        new_is_primary = data.get("is_primary")

        if not isinstance(new_is_primary, bool):
            return jsonify({"error": "is_primary must be a boolean."}), 400

        if new_is_primary:
            primary_exists = db.session.scalar(
                db.select(ProductImage).where(
                    ProductImage.product_id == product_id,
                    ProductImage.is_primary == True,
                    ProductImage.id != image_id
                )
            )

            if primary_exists:
                primary_exists.is_primary = False

        image_exists.is_primary = new_is_primary

    if "position" in data:
        new_position = data.get("position")
        if not isinstance(new_position, int) or isinstance(new_position, bool):
            return jsonify({"error": "Position needs to be an integer."}) , 400

        if new_position < 0:
            return jsonify({"error": "You cant enter an negative number as position."}), 400

        image_exists.position = new_position

    db.session.commit()
    return jsonify({"success": "You have successfully updated product image."}), 200


@app.route("/products/<int:product_id>/images", methods=['GET'])
def show_all_product_images(product_id):

    product_exist = db.session.scalar(db.select(Product).where(Product.id == product_id,Product.is_active == True))
    if not product_exist:
        return jsonify({"error": "Product not found."}), 404

    images = sorted(
        product_exist.images,
        key=lambda image: (image.position, image.id)
    )

    images = [
        {
            "id": image.id,
            "image_url": image.image_url,
            "is_primary": image.is_primary,
            "position": image.position
        }
        for image in images
    ]

    return jsonify(images), 200

@app.route("/products/<int:product_id>/images/<int:image_id>", methods=['DELETE'])
@jwt_required()
def delete_product_image(product_id, image_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": " Only Admin can access."}), 403

    image_exist = db.session.scalar(db.select(ProductImage).where(ProductImage.product_id == product_id, ProductImage.id == image_id))
    if not image_exist:
        return jsonify({"error": "Image not found"}), 404

    db.session.delete(image_exist)
    db.session.commit()

    return jsonify({"success": "Image has been successfully deleted."}), 200


@app.route("/products/<int:product_id>/variants", methods=['POST'])
@jwt_required()
def add_product_variant(product_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access."}) , 403

    product_exists = db.session.scalar(db.select(Product).where(Product.id == product_id))

    if not product_exists:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json()

    if not isinstance(data , dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if "sku" not in data:
        return jsonify({"error": "Sku is required."}), 400

    sku = data.get("sku")
    if not isinstance(sku, str) or not sku.strip():
        return jsonify({"error": "Sku needs to be a string and not empty field."}), 400

    sku = sku.strip()

    sku_exists = db.session.scalar(db.select(ProductVariant).where(ProductVariant.sku == sku))
    if sku_exists:
        return jsonify({"error": "A variant with this SKU already exists."}), 409

    if "attributes" not in data:
        return jsonify({"error": "Attributes is required."}), 400

    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        return jsonify({"error": "Attributes must be an object."}), 400

    price = data.get("price")

    if price is not None:
        if not isinstance(price, (int, float)) or  isinstance(price, bool):
            return jsonify({"error": "Price must be an number."}), 400

        if price <= 0:
            return jsonify({"error": "Price must be greater than zero."}), 400

    new_variant = ProductVariant(
        product_id=product_id,
        sku=sku,
        attributes=attributes,
        price=price
    )

    db.session.add(new_variant)
    db.session.commit()

    return jsonify({"success": "You have successfully added a new variant."}), 201


@app.route("/products/<int:product_id>/variants")
def show_product_variants(product_id):

    product_exists = db.session.scalar(db.select(Product).where(Product.id == product_id, Product.is_active == True))
    if not product_exists:
        return jsonify({"error": "Product not found."}), 404

    active_variants = db.session.scalars(db.select(ProductVariant).where(ProductVariant.product_id == product_id, ProductVariant.is_active == True)).all()
    if not active_variants:
        return jsonify([]), 200

    data = [
        {
            "id": variant.id,
            "sku": variant.sku,
            "attributes": variant.attributes,
            "price": variant.price if variant.price is not None else product_exists.price
        }
        for variant in active_variants
    ]

    return jsonify(data), 200

@app.route("/products/<int:product_id>/variants/<int:variant_id>", methods=['PATCH'])
@jwt_required()
def edit_product_variant(product_id, variant_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access."}), 403

    product_exists = db.session.scalar(db.select(Product).where(Product.id == product_id))
    if not product_exists:
        return jsonify({"error": "Product not found."}), 404

    variant_exists = db.session.scalar(db.select(ProductVariant).where(ProductVariant.product_id == product_id, ProductVariant.id == variant_id))
    if not variant_exists:
        return jsonify({"error": "Variant not found."}), 404

    data = request.get_json()

    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object."}), 400

    if "sku" in data:
        new_sku = data.get("sku")
        if not isinstance(new_sku, str) or not new_sku.strip():
            return jsonify({"error": "SKU needs to be a string and not empty field."}), 400

        new_sku = new_sku.strip()

        sku_exists = db.session.scalar(db.select(ProductVariant).where(ProductVariant.sku == new_sku, ProductVariant.id != variant_id))
        if sku_exists:
            return jsonify({"error": "SKU already exists."}), 409

        variant_exists.sku = new_sku

    if "attributes" in data:
        new_attributes = data.get("attributes")
        if not isinstance(new_attributes, dict):
            return jsonify({"error": "Attributes needs to be sent as an object."}), 400

        variant_exists.attributes = new_attributes

    if "price" in data:
        new_price = data.get("price")

        if new_price is not None:
            if not isinstance(new_price, (int, float)) or isinstance(new_price, bool):
                return jsonify({"error": "Price must be a number."}), 400

            if new_price <= 0:
                return jsonify({"error": "Price must be greater than zero."}), 400

        variant_exists.price = new_price

    if "is_active" in data:
        new_is_active = data.get("is_active")
        if not isinstance(new_is_active, bool):
            return jsonify({"error": "Active status needs to be a boolean."}), 400

        variant_exists.is_active = new_is_active

    db.session.commit()
    return jsonify({"success": " You have successfully updated product variant."}), 200


@app.route("/products/<int:product_id>/variants/<int:variant_id>", methods=['DELETE'])
@jwt_required()
def delete_product_variant(product_id, variant_id):

    claim = get_jwt()
    role = claim.get("role")

    if role != "admin":
        return jsonify({"error": "Only admin can access."}), 403

    product_exists = db.session.scalar(db.select(Product).where(Product.id == product_id))

    if not product_exists:
        return jsonify({"error": "Product not found."}), 404

    variant_exists = db.session.scalar(db.select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.product_id == product_id))

    if not variant_exists:
        return jsonify({"error": "Variant not found."}), 404

    db.session.delete(variant_exists)
    db.session.commit()

    return jsonify({"success": "You have successfully deleted a product variant."}), 200

@app.route("/products", methods=["GET"])
def search_product():
    
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id")
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    is_featured = request.args.get("is_featured")
    on_sale = request.args.get("on_sale")
    sort = request.args.get("sort", "name_asc").strip().lower()

    # Paginacija: podrazumevano stranica 1, po 20 proizvoda.
    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        return jsonify({
            "error": "page and per_page must be integers."
        }), 400

    if page < 1:
        return jsonify({"error": "page must be at least 1."}), 400

    if per_page < 1 or per_page > 100:
        return jsonify({
            "error": "per_page must be between 1 and 100."
        }), 400

    # Uvek prikazujemo samo aktivne proizvode.
    query = db.select(Product).where(Product.is_active == True)

    # Pretraga po nazivu.
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))

    # Kategorija kojoj je proizvod dodeljen.
    if category_id is not None:
        try:
            category_id = int(category_id)
        except ValueError:
            return jsonify({
                "error": "Category ID must be an integer."
            }), 400

        if category_id < 1:
            return jsonify({
                "error": "Category ID must be greater than zero."
            }), 400

        query = query.where(
            Product.categories.any(Category.id == category_id)
        )

    # Provera minimalne cene.
    if min_price is not None:
        try:
            min_price = Decimal(min_price)
        except InvalidOperation:
            return jsonify({
                "error": "min_price must be a number."
            }), 400

        if not min_price.is_finite() or min_price < 0:
            return jsonify({
                "error": "min_price must be a finite, non-negative number."
            }), 400

    # Provera maksimalne cene.
    if max_price is not None:
        try:
            max_price = Decimal(max_price)
        except InvalidOperation:
            return jsonify({
                "error": "max_price must be a number."
            }), 400

        if not max_price.is_finite() or max_price < 0:
            return jsonify({
                "error": "max_price must be a finite, non-negative number."
            }), 400

    if min_price is not None and max_price is not None:
        if min_price > max_price:
            return jsonify({
                "error": "min_price cannot be greater than max_price."
            }), 400

    # Akcijska cena ako postoji, inače redovna.
    effective_price = func.coalesce(Product.sale_price, Product.price)

    if min_price is not None:
        query = query.where(effective_price >= min_price)

    if max_price is not None:
        query = query.where(effective_price <= max_price)

    # Istaknuti ili neistaknuti proizvodi.
    if is_featured is not None:
        is_featured = is_featured.strip().lower()

        if is_featured not in ("true", "false"):
            return jsonify({
                "error": "is_featured must be true or false."
            }), 400

        query = query.where(
            Product.is_featured == (is_featured == "true")
        )

    # Proizvodi sa akcijskom cenom ili bez nje.
    if on_sale is not None:
        on_sale = on_sale.strip().lower()

        if on_sale not in ("true", "false"):
            return jsonify({
                "error": "on_sale must be true or false."
            }), 400

        if on_sale == "true":
            query = query.where(Product.sale_price.is_not(None))
        else:
            query = query.where(Product.sale_price.is_(None))

    # Dozvoljeni načini sortiranja.
    sort_options = {
        "price_asc": effective_price.asc(),
        "price_desc": effective_price.desc(),
        "name_asc": Product.name.asc(),
        "name_desc": Product.name.desc()
    }

    if sort not in sort_options:
        return jsonify({
            "error": "sort must be price_asc, price_desc, name_asc or name_desc."
        }), 400

    # ID određuje redosled kada su cena ili naziv isti.
    query = query.order_by(sort_options[sort], Product.id.asc())

    # Učitavamo samo traženu stranicu.
    pagination = db.paginate(
        query,
        page=page,
        per_page=per_page,
        max_per_page=100,
        error_out=False
    )

    products = [
        {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "sale_price": product.sale_price,
            "effective_price": (
                product.sale_price
                if product.sale_price is not None
                else product.price
            ),
            "is_active": product.is_active,
            "is_featured": product.is_featured
        }
        for product in pagination.items
    ]

    return jsonify({
        "products": products,
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }
    }), 200


    

    
if __name__ == "__main__":
    app.run(debug=True)
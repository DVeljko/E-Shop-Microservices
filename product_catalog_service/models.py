from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Numeric, Text, JSON
from decimal import Decimal


db = SQLAlchemy()

class Category(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    parent_id: Mapped[int] = mapped_column(ForeignKey("category.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class Product(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sale_price: Mapped[Decimal  ] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_featured: Mapped[bool] = mapped_column(nullable=False, default=False)

class ProductCategory(db.Model):

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), primary_key=True)

    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), primary_key=True)


class ProductImage(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), nullable=False)
    image_url: Mapped[str] = mapped_column(nullable=False)
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)

class ProductVariant(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"),nullable=False)
    sku: Mapped[str] = mapped_column(unique=True,nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON,nullable=False,default=dict)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2),nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False,default=True)
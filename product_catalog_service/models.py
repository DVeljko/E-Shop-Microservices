from decimal import Decimal
from typing import Optional

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, JSON, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


db = SQLAlchemy()


class Category(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("category.id"),nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False,default=True)

    parent: Mapped[Optional["Category"]] = relationship("Category",remote_side=[id],back_populates="subcategories")

    subcategories: Mapped[list["Category"]] = relationship("Category",back_populates="parent")

    products: Mapped[list["Product"]] = relationship("Product",secondary="product_category",back_populates="categories")


class Product(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2),nullable=False)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2),nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False,default=True)
    is_featured: Mapped[bool] = mapped_column(nullable=False,default=False)

    categories: Mapped[list["Category"]] = relationship("Category",secondary="product_category",back_populates="products")

    images: Mapped[list["ProductImage"]] = relationship("ProductImage",back_populates="product",cascade="all, delete-orphan")

    variants: Mapped[list["ProductVariant"]] = relationship("ProductVariant",back_populates="product",cascade="all, delete-orphan")


class ProductCategory(db.Model):

    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"),primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"),primary_key=True)


class ProductImage(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"),nullable=False)
    image_url: Mapped[str] = mapped_column(nullable=False)
    is_primary: Mapped[bool] = mapped_column(nullable=False,default=False)
    position: Mapped[int] = mapped_column(nullable=False,default=0)

    product: Mapped["Product"] = relationship("Product",back_populates="images")


class ProductVariant(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"),nullable=False)
    sku: Mapped[str] = mapped_column(unique=True,nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON,nullable=False,default=dict)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False,default=True)
    
    product: Mapped["Product"] = relationship("Product",back_populates="variants")
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

db = SQLAlchemy()

class Cart(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=True)
    guest_token: Mapped[str | None] = mapped_column(nullable=True,unique=True)
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey("coupon.id", name="fk_cart_coupon_id_coupon"),nullable=True)

class CartItem(db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("cart.id", name="fk_cart_item_cart_id_cart"),nullable=False)
    sku: Mapped[str] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)

class Coupon(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True,nullable=False)
    discount_percent: Mapped[int] = mapped_column(nullable=False)


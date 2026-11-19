from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Numeric
from datetime import datetime
from decimal import Decimal


db = SQLAlchemy()

class Order(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(nullable=True)
    order_number: Mapped[str] = mapped_column(unique=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10,2),nullable=False)
    order_address: Mapped[str] = mapped_column(nullable=False)
    order_status: Mapped[str] = mapped_column(nullable=False)
    order_date: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now)

class OrderItems(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), nullable=False)
    sku: Mapped[str] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10,2), nullable=False)

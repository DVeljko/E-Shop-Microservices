from sqlalchemy.orm import Mapped, mapped_column
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, Enum

from datetime import datetime, timezone

db = SQLAlchemy()

class InventoryRecords(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(nullable=False, unique=True)
    quantity: Mapped[int] = mapped_column(nullable=False, default=0)


class StockReservation(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(nullable=False) 
    status: Mapped[str] = mapped_column(nullable=False, default="reserved")

    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory_records.id"), nullable=False)

class StockMovement(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory_records.id"),nullable=False)
    quantity_change: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(Enum("adjustment", "purchase", name="stock_movement_reason", create_constraint=True, validate_strings=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
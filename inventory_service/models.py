from sqlalchemy.orm import Mapped, mapped_column
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey

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
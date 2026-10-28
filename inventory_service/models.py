from sqlalchemy.orm import Mapped, mapped_column
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class InventoryRecords(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(nullable=False, unique=True)
    quantity: Mapped[int] = mapped_column(nullable=False)

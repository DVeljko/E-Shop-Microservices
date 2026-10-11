from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin ,db.Model):

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    last_name: Mapped[str] = mapped_column(nullable=False)
    username: Mapped[str] = mapped_column(nullable=False, unique=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    role: Mapped[str] = mapped_column(nullable=False, default="customer")
    password: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="active")


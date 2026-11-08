"""Add guest cart support

Revision ID: 161821fe7640
Revises: 89bff57e3515
Create Date: 2026-11-08 12:33:42.174405
"""

from alembic import op
import sqlalchemy as sa


revision = "161821fe7640"
down_revision = "89bff57e3515"
branch_labels = None
depends_on = None


naming_convention = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
}


def upgrade():
    with op.batch_alter_table("cart", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("guest_token", sa.String(), nullable=True)
        )

        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=True
        )

        batch_op.create_unique_constraint(
            "uq_cart_guest_token",
            ["guest_token"]
        )

    with op.batch_alter_table(
        "cart_item",
        schema=None,
        naming_convention=naming_convention
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_cart_item_card_id_cart",
            type_="foreignkey"
        )

        batch_op.alter_column(
            "card_id",
            new_column_name="cart_id",
            existing_type=sa.Integer(),
            existing_nullable=False
        )

        batch_op.create_foreign_key(
            "fk_cart_item_cart_id_cart",
            "cart",
            ["cart_id"],
            ["id"]
        )


def downgrade():
    with op.batch_alter_table(
        "cart_item",
        schema=None,
        naming_convention=naming_convention
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_cart_item_cart_id_cart",
            type_="foreignkey"
        )

        batch_op.alter_column(
            "cart_id",
            new_column_name="card_id",
            existing_type=sa.Integer(),
            existing_nullable=False
        )

        batch_op.create_foreign_key(
            "fk_cart_item_card_id_cart",
            "cart",
            ["card_id"],
            ["id"]
        )

    with op.batch_alter_table("cart", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_cart_guest_token",
            type_="unique"
        )

        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False
        )

        batch_op.drop_column("guest_token")
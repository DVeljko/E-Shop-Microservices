"""Add coupons and cart coupon support"""

from alembic import op
import sqlalchemy as sa


revision = "589ec4d8cbd1"
down_revision = "161821fe7640"
branch_labels = None
depends_on = None


def upgrade():
    # Prethodni neuspešni pokušaj je možda već napravio ovu tabelu.
    if not sa.inspect(op.get_bind()).has_table("coupon"):
        op.create_table(
            "coupon",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("discount_percent", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code")
        )

    with op.batch_alter_table("cart", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("coupon_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_cart_coupon_id_coupon",
            "coupon",
            ["coupon_id"],
            ["id"]
        )

    with op.batch_alter_table("cart_item", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_cart_item_cart_id_cart",
            "cart",
            ["cart_id"],
            ["id"]
        )


def downgrade():
    with op.batch_alter_table("cart_item", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_cart_item_cart_id_cart",
            type_="foreignkey"
        )

    with op.batch_alter_table("cart", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_cart_coupon_id_coupon",
            type_="foreignkey"
        )
        batch_op.drop_column("coupon_id")

    op.drop_table("coupon")
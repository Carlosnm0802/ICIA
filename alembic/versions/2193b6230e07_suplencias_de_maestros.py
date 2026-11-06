"""suplencias de maestros

Revision ID: 2193b6230e07
Revises: 7edfe740fe74
Create Date: 2026-11-06 17:23:26.354227

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2193b6230e07'
down_revision: Union[str, Sequence[str], None] = '7edfe740fe74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("sesion_maestros", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("maestro_titular_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_sesion_maestros_titular",
            "maestros",
            ["maestro_titular_id"],
            ["id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "ck_sesion_maestros_suplencia",
            "maestro_titular_id IS NULL OR maestro_titular_id <> maestro_id",
        )
        batch_op.create_index(
            "idx_sesion_maestros_titular",
            ["maestro_titular_id"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("sesion_maestros", schema=None) as batch_op:
        batch_op.drop_index("idx_sesion_maestros_titular")
        batch_op.drop_constraint(
            "ck_sesion_maestros_suplencia",
            type_="check",
        )
        batch_op.drop_constraint(
            "fk_sesion_maestros_titular",
            type_="foreignkey",
        )
        batch_op.drop_column("maestro_titular_id")


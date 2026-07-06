"""add_landed_cost_fields

Revision ID: f7a8b9c0d1e2
Revises: 7d4944f5f4ac
Create Date: 2026-07-06 14:48:10.123456

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: str | None = '7d4944f5f4ac'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new metadata and review columns to landed_costs
    op.add_column('landed_costs', sa.Column('raw_source_name', sa.String(length=255), nullable=True))
    op.add_column(
        'landed_costs',
        sa.Column('weighted_avg_gcv_kcal_per_kg', sa.Numeric(precision=14, scale=2), nullable=True),
    )
    op.add_column(
        'landed_costs',
        sa.Column(
            'cost_basis',
            sa.String(length=64),
            server_default='CERTIFIED_WEIGHTED_AVERAGE',
            nullable=False,
        ),
    )
    op.add_column(
        'landed_costs',
        sa.Column('extraction_confidence', sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column('landed_costs', sa.Column('parser_notes', sa.String(length=2000), nullable=True))
    op.add_column(
        'landed_costs',
        sa.Column('status', sa.String(length=32), server_default='PENDING_REVIEW', nullable=False),
    )
    op.add_column(
        'landed_costs',
        sa.Column('needs_review', sa.Boolean(), server_default='false', nullable=False),
    )

    # Alter existing columns to be nullable
    op.alter_column('landed_costs', 'plant_id', existing_type=sa.UUID(), nullable=True)
    op.alter_column(
        'landed_costs',
        'basic_cost',
        existing_type=sa.NUMERIC(precision=14, scale=2),
        nullable=True,
    )
    op.alter_column(
        'landed_costs',
        'freight',
        existing_type=sa.NUMERIC(precision=14, scale=2),
        nullable=True,
    )
    op.alter_column(
        'landed_costs',
        'taxes',
        existing_type=sa.NUMERIC(precision=14, scale=2),
        nullable=True,
    )
    op.alter_column(
        'landed_costs', 'total_landed_cost', existing_type=sa.NUMERIC(precision=14, scale=2), nullable=True
    )
    op.alter_column('landed_costs', 'effective_from', existing_type=sa.DATE(), nullable=True)


def downgrade() -> None:
    # Revert columns to not nullable (requires records to be valid/cleaned, but fits standard revert schema)
    op.alter_column('landed_costs', 'effective_from', existing_type=sa.DATE(), nullable=False)
    op.alter_column(
        'landed_costs', 'total_landed_cost', existing_type=sa.NUMERIC(precision=14, scale=2), nullable=False
    )
    op.alter_column(
        'landed_costs',
        'taxes',
        existing_type=sa.NUMERIC(precision=14, scale=2),
        nullable=False,
    )
    op.alter_column(
        'landed_costs',
        'freight',
        existing_type=sa.NUMERIC(precision=14, scale=2),
        nullable=False,
    )
    op.alter_column(
        'landed_costs',
        'basic_cost',
        existing_type=sa.NUMERIC(precision=14, scale=2),
        nullable=False,
    )
    op.alter_column('landed_costs', 'plant_id', existing_type=sa.UUID(), nullable=False)


    # Drop columns
    op.drop_column('landed_costs', 'needs_review')
    op.drop_column('landed_costs', 'status')
    op.drop_column('landed_costs', 'parser_notes')
    op.drop_column('landed_costs', 'extraction_confidence')
    op.drop_column('landed_costs', 'cost_basis')
    op.drop_column('landed_costs', 'weighted_avg_gcv_kcal_per_kg')
    op.drop_column('landed_costs', 'raw_source_name')

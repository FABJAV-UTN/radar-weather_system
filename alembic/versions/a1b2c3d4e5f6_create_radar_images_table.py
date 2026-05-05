"""create_radar_images_table

Revision ID: a1b2c3d4e5f6
Revises: f37b65691850
Create Date: 2026-05-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f37b65691850'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'radar_images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('location', sa.String(length=100), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('image_timestamp', sa.DateTime(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('datotif_id', sa.Integer(), nullable=False),
        sa.Column('extent', Geometry(geometry_type='POLYGON', srid=4326), nullable=True),
        sa.Column('width_px', sa.Integer(), nullable=True),
        sa.Column('height_px', sa.Integer(), nullable=True),
        sa.Column('max_dbz', sa.Float(), nullable=True),
        sa.Column('storm_pixel_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filename'),
    )
    op.create_index('ix_radar_images_location', 'radar_images', ['location'])
    op.create_index('ix_radar_images_image_timestamp', 'radar_images', ['image_timestamp'])


def downgrade() -> None:
    op.drop_index('ix_radar_images_image_timestamp', table_name='radar_images')
    op.drop_index('ix_radar_images_location', table_name='radar_images')
    op.drop_table('radar_images')
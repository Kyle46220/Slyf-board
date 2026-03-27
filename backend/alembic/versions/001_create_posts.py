"""create posts table

Revision ID: 001
Revises:
Create Date: 2026-03-27

"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hash", sa.String(length=36), nullable=False),
        sa.Column(
            "content_type",
            sa.Enum("text", "image", "video", "link", name="content_type_enum"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("media_path", sa.Text(), nullable=True),
        sa.Column("og_title", sa.Text(), nullable=True),
        sa.Column("og_description", sa.Text(), nullable=True),
        sa.Column("og_image_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hash"),
    )


def downgrade() -> None:
    op.drop_table("posts")
    sa.Enum(name="content_type_enum").drop(op.get_bind(), checkfirst=False)

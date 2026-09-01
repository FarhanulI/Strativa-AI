"""Refactor business root to content profile root.

Revision ID: 9c2b8f8b6b11
Revises: 78e5a005d8db
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c2b8f8b6b11"
down_revision: str | None = "78e5a005d8db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum("creator", "business", name="contentprofiletype"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expertise", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("goals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_content_profiles_workspace_id", "content_profiles", ["workspace_id"], unique=False
    )

    # Preserve existing business rows by migrating them into business-type content profiles.
    op.execute(
        """
        INSERT INTO content_profiles (
            id,
            workspace_id,
            type,
            name,
            description,
            website,
            location,
            positioning,
            topics,
            expertise,
            goals,
            created_at,
            updated_at
        )
        SELECT
            id,
            workspace_id,
            'business'::contentprofiletype,
            name,
            description,
            website_url,
            location,
            NULL,
            NULL,
            NULL,
            NULL,
            created_at,
            updated_at
        FROM businesses
        """
    )

    op.create_table(
        "brands_new",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("mission", sa.Text(), nullable=True),
        sa.Column("vision", sa.Text(), nullable=True),
        sa.Column("unique_selling_proposition", sa.Text(), nullable=True),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("personality", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("voice", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tone", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("messaging_guidelines", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("visual_identity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["content_profile_id"], ["content_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_profile_id"),
    )
    op.create_index(
        "ix_brands_new_content_profile_id",
        "brands_new",
        ["content_profile_id"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO brands_new (
            id,
            content_profile_id,
            positioning,
            mission,
            vision,
            unique_selling_proposition,
            values,
            personality,
            voice,
            tone,
            messaging_guidelines,
            visual_identity,
            created_at,
            updated_at
        )
        SELECT
            b.id,
            b.business_id,
            b.positioning,
            b.mission,
            b.vision,
            b.unique_selling_proposition,
            b.values,
            b.personality,
            b.voice,
            b.tone,
            b.messaging_guidelines,
            b.visual_identity,
            b.created_at,
            b.updated_at
        FROM brands b
        """
    )

    op.drop_table("brands")
    op.rename_table("brands_new", "brands")
    op.create_index("ix_brands_content_profile_id", "brands", ["content_profile_id"], unique=False)

    op.drop_index("ix_businesses_workspace_id", table_name="businesses")
    op.drop_table("businesses")


def downgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("business_model", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_businesses_workspace_id", "businesses", ["workspace_id"], unique=False)

    op.execute(
        """
        INSERT INTO businesses (
            id,
            workspace_id,
            name,
            description,
            industry,
            website_url,
            location,
            business_model,
            created_at,
            updated_at
        )
        SELECT
            id,
            workspace_id,
            name,
            description,
            NULL,
            website,
            location,
            NULL,
            created_at,
            updated_at
        FROM content_profiles
        WHERE type = 'business'::contentprofiletype
        """
    )

    op.create_table(
        "brands_old",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("positioning", sa.Text(), nullable=True),
        sa.Column("mission", sa.Text(), nullable=True),
        sa.Column("vision", sa.Text(), nullable=True),
        sa.Column("unique_selling_proposition", sa.Text(), nullable=True),
        sa.Column("values", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("personality", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("voice", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("tone", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("messaging_guidelines", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("visual_identity", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id"),
    )
    op.create_index("ix_brands_old_business_id", "brands_old", ["business_id"], unique=False)

    op.execute(
        """
        INSERT INTO brands_old (
            id,
            business_id,
            positioning,
            mission,
            vision,
            unique_selling_proposition,
            values,
            personality,
            voice,
            tone,
            messaging_guidelines,
            visual_identity,
            created_at,
            updated_at
        )
        SELECT
            b.id,
            b.content_profile_id,
            b.positioning,
            b.mission,
            b.vision,
            b.unique_selling_proposition,
            b.values,
            b.personality,
            b.voice,
            b.tone,
            b.messaging_guidelines,
            b.visual_identity,
            b.created_at,
            b.updated_at
        FROM brands b
        INNER JOIN businesses bs ON bs.id = b.content_profile_id
        """
    )

    op.drop_table("brands")
    op.rename_table("brands_old", "brands")
    op.create_index("ix_brands_business_id", "brands", ["business_id"], unique=False)

    op.drop_index("ix_content_profiles_workspace_id", table_name="content_profiles")
    op.drop_table("content_profiles")
    op.execute("DROP TYPE IF EXISTS contentprofiletype")

"""Índices trigram (PostgreSQL) para busca por trecho em nome, e-mail e empresa.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUNAS = ("nome", "email", "empresa")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for c in COLUNAS:
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_lead_{c}_trgm ON lead USING gin ({c} gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_telefone_trgm ON lead USING gin (telefone gin_trgm_ops)")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for c in (*COLUNAS, "telefone"):
        op.execute(f"DROP INDEX IF EXISTS ix_lead_{c}_trgm")

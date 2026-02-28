"""Utilitários para manter o schema do banco compatível com o código.

Este projeto nasceu com `db.create_all()` (sem migrations). Em SQLite isso até passa,
mas em produção com Postgres qualquer coluna nova no model não aparece automaticamente,
gerando erros como:

    psycopg2.errors.UndefinedColumn: column configuracao_sistema.email_remetente does not exist

Este módulo aplica um *poka‑yoke* simples e idempotente:
- cria tabelas faltantes via create_all (feito no create_app)
- adiciona colunas faltantes essenciais com ALTER TABLE

Observação: isso NÃO substitui migrations (é um guarda‑corpo para manter o sistema vivo).
"""

from __future__ import annotations

from sqlalchemy import text, inspect


def _has_column(engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _add_column(engine, dialect: str, table: str, ddl: str) -> None:
    """Executa um ALTER TABLE seguro/compatível."""
    # Postgres suporta IF NOT EXISTS; SQLite não.
    with engine.begin() as conn:
        conn.execute(text(ddl))


def ensure_schema(db) -> None:
    """Garante compatibilidade mínima do schema com os models atuais."""

    engine = db.engine
    dialect = engine.dialect.name.lower()

    # -------------------------
    # configuracao_sistema
    # -------------------------
    # Colunas que já quebraram produção (e-mail)
    if not _has_column(engine, "configuracao_sistema", "email_remetente"):
        if dialect == "postgresql":
            _add_column(
                engine,
                dialect,
                "configuracao_sistema",
                "ALTER TABLE configuracao_sistema ADD COLUMN IF NOT EXISTS email_remetente VARCHAR(255)",
            )
        else:
            # SQLite: sem IF NOT EXISTS → checagem acima já garante idempotência.
            _add_column(
                engine,
                dialect,
                "configuracao_sistema",
                "ALTER TABLE configuracao_sistema ADD COLUMN email_remetente VARCHAR(255)",
            )

    # (Mantém simetria com o model)
    if not _has_column(engine, "configuracao_sistema", "nome_remetente"):
        if dialect == "postgresql":
            _add_column(
                engine,
                dialect,
                "configuracao_sistema",
                "ALTER TABLE configuracao_sistema ADD COLUMN IF NOT EXISTS nome_remetente VARCHAR(255)",
            )
        else:
            _add_column(engine, dialect, "configuracao_sistema", "ALTER TABLE configuracao_sistema ADD COLUMN nome_remetente VARCHAR(255)")

    # SMTP campos (não deveriam quebrar, mas garantimos)
    _maybe_add(engine, dialect, "configuracao_sistema", "smtp_host", "VARCHAR(255)")
    _maybe_add(engine, dialect, "configuracao_sistema", "smtp_port", "INTEGER")
    _maybe_add(engine, dialect, "configuracao_sistema", "smtp_usuario", "VARCHAR(255)")
    _maybe_add(engine, dialect, "configuracao_sistema", "smtp_senha", "VARCHAR(255)")
    _maybe_add(engine, dialect, "configuracao_sistema", "smtp_tls", "BOOLEAN")
    _maybe_add(engine, dialect, "configuracao_sistema", "smtp_ssl", "BOOLEAN")
    _maybe_add(engine, dialect, "configuracao_sistema", "assunto_padrao", "VARCHAR(255)")

    # -------------------------
    # email_destinatario
    # -------------------------
    # Pode existir só em versões mais novas.
    # create_all cria a tabela, mas se já existir faltando colunas, garantimos.
    try:
        insp = inspect(engine)
        if "email_destinatario" in insp.get_table_names():
            _maybe_add(engine, dialect, "email_destinatario", "nome", "VARCHAR(255)")
            _maybe_add(engine, dialect, "email_destinatario", "ativo", "BOOLEAN")
    except Exception:
        # Não derruba o app por isso.
        return


def _maybe_add(engine, dialect: str, table: str, column: str, coltype: str) -> None:
    if _has_column(engine, table, column):
        return
    if dialect == "postgresql":
        ddl = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {coltype}"
    else:
        ddl = f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"
    _add_column(engine, dialect, table, ddl)

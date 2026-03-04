import os


def _clean_database_url(raw: str) -> str:
    """Normaliza DATABASE_URL vinda de variáveis/CLI.

    Casos comuns que quebram o SQLAlchemy:
    - prefixo acidental: "psql 'postgresql://...'"
    - aspas simples/duplas em volta
    - postgres:// (SQLAlchemy prefere postgresql://)
    """
    s = (raw or "").strip()
    if not s:
        return s

    if s.lower().startswith("psql "):
        s = s[5:].strip()

    # remove aspas externas
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1].strip()

    if s.startswith("postgres://"):
        s = s.replace("postgres://", "postgresql://", 1)

    return s


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'uma-chave-muito-segura-da-nestle')
    ENABLE_MYDOT = True
    # Banco: usa env (Render/Neon) e cai para SQLite local
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    DEFAULT_SQLITE = f"sqlite:///{os.path.join(BASEDIR, 'psa_storage.db')}"
    SQLALCHEMY_DATABASE_URI = _clean_database_url(os.getenv('DATABASE_URL', DEFAULT_SQLITE))

    SQLALCHEMY_TRACK_MODIFICATIONS = False

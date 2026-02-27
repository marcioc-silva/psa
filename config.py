import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")

    # 1) tenta Postgres (Neon) via env var
    db_url = os.getenv("DATABASE_URL")

    # 2) normaliza caso venha postgres://
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # 3) fallback local (dev) para sqlite na pasta instance
    if not db_url:
        db_path = os.path.join(basedir, "instance", "app.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        db_url = "sqlite:///" + db_path

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

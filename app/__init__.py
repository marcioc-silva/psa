import os
from datetime import datetime, timezone

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

# Extensões (criadas fora da factory)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app(config_object=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Base do projeto (pasta /app)
    basedir = os.path.abspath(os.path.dirname(__file__))

    # =========================
    # Configuração
    # =========================
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        instance_dir = os.path.join(basedir, "..", "instance")
        os.makedirs(instance_dir, exist_ok=True)
        sqlite_path = os.path.join(instance_dir, "psa_storage.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {"pool_pre_ping": True})

    # =========================
    # Extensões
    # =========================
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "warning"

    # =========================
    # Context Processor
    # =========================
    @app.context_processor
    def inject_now():
        return {"now": datetime.now(timezone.utc)}

    # =========================
    # Blueprints
    # =========================
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Poka-yoke: se rotas críticas não forem carregadas, falha no boot (evita regressões em deploy)
    missing = [ep for ep in ("main.login", "main.registrar") if ep not in app.view_functions]
    if missing:
        raise RuntimeError(f"Endpoints ausentes: {missing}. Rotas do blueprint 'main' não foram carregadas.")

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    from app.routes.importer import bp as importer_bp
    app.register_blueprint(importer_bp)

    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    # =========================
    # Flask-Login user_loader
    # =========================
    try:
        # Agora o contrato é: app.models exporta User (via app/models/__init__.py)
        from app.models import User
    except Exception:
        User = None

    @login_manager.user_loader
    def load_user(user_id):
        if User is None:
            return None
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # =========================
    # Banco: create_all apenas em DEV
    # =========================
    if app.debug or os.getenv("FLASK_ENV") == "development":
        with app.app_context():
            db.create_all()

    return app

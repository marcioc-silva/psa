import os
from datetime import datetime, timezone
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app(config_object=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Base do projeto (pasta /app)
    basedir = os.path.abspath(os.path.dirname(__file__))

    # =========================
    # Config (Poka-Yoke de Prod)
    # =========================

    # 1) SECRET_KEY via ambiente (evita vazar segredo no Git/Render)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")

    # 2) DATABASE_URL via ambiente (Render/Postgres/Neon) com fallback para sqlite local
    #    e correção do esquema postgres:// -> postgresql:// (alguns provedores ainda entregam "postgres://")
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        instance_dir = os.path.join(basedir, "..", "instance")
        os.makedirs(instance_dir, exist_ok=True)  # garante a pasta instance em deploy/local
        sqlite_path = os.path.join(instance_dir, "psa_storage.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # (Opcional, mas recomendável) evita overhead e warnings em SQLAlchemy 2.x
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {"pool_pre_ping": True})

    # =========================
    # Extensões
    # =========================
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # =========================
    # Context Processor
    # =========================
    @app.context_processor
    def inject_now():
        # UTC consciente (timezone-aware) pra não dar confusão em comparações
        return {"now": datetime.now(timezone.utc)}

    # =========================
    # Blueprints
    # =========================
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    from app.routes.importer import bp as importer_bp
    app.register_blueprint(importer_bp)

    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    # =========================
    # Flask-Login user_loader
    # =========================
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        # get() do Session é o caminho moderno (evita warning do Query.get)
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # =========================
    # Banco: migrations > create_all
    # =========================
    # Em apps com Flask-Migrate, create_all() costuma causar "drift" de schema.
    # Deixe migrations cuidarem do schema.
    #
    # Se você quer manter um fallback só pra DEV, deixe assim:
    if app.debug or os.getenv("FLASK_ENV") == "development":
        with app.app_context():
            db.create_all()

    return app

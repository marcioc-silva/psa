import os
from datetime import datetime, timezone
from flask import Flask, request, has_request_context, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def create_app(config_object=None):
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    from app.models.usuario import Usuario
    from app.models.material import MaterialPSA
    
    static_path = os.path.join(basedir, "static")

    app = Flask(
        __name__, 
        template_folder="templates", 
        static_folder=static_path, 
        static_url_path="/static"
    )

    @app.context_processor
    def inject_globals():
        ctx = {
            "now": datetime.now(timezone.utc),
            "has_enviar_reporte": "reports.enviar_reporte" in app.view_functions,
            "ctx_version": "CTX-2026-03-03-04",
        }

        if not has_request_context():
            ctx.update({
                "data_atual": None,
                "psa_key_atual": None,
                "datas": [],
                "psas": []
            })
            return ctx

        data_filtro = request.args.get("data_filtro")
        psa_key = request.args.get("psa_key")
        ctx["data_atual"] = data_filtro
        ctx["psa_key_atual"] = psa_key

        if not current_user.is_authenticated:
            ctx.update({"datas": [], "psas": []})
            return ctx

        try:
            from app.services.kpis import calcular_kpis, listar_datas_importacao, listar_psas
            ctx["datas"] = listar_datas_importacao()
            ctx["psas"] = listar_psas()
            k = calcular_kpis(data_filtro=data_filtro, psa_key=psa_key)
            ctx.update(k)
        except Exception as e:
            app.logger.exception("Falha ao injetar KPIs: %s", e)
            ctx.update({
                "total": 0, "conferidos": 0, "pendentes": 0,
                "acuracidade": 0.0, "taxa_qualidade": 100.0,
                "ctx_error": str(e)[:120]
            })

        return ctx

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

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "warning"

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)
    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)
    from app.routes.importer import bp as importer_bp
    app.register_blueprint(importer_bp)
    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)
    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp)
    from app.routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)
    from app.routes.manual import bp as manual_bp
    app.register_blueprint(manual_bp)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Usuario, int(user_id))
        except (TypeError, ValueError):
            return None

    if app.config.get("ENABLE_MYDOT", True):
        try:
            from mydot.mydot_module.routes.mydot import bp as mydot_bp
            app.register_blueprint(mydot_bp, url_prefix="/mydot")
        except Exception as e:
            app.logger.warning(f"MyDot desabilitado (não impacta PSA): {e}")
            
        if app.debug or os.getenv("FLASK_ENV") == "development":
            with app.app_context():
                db.create_all()

    return app

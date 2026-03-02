import os
from datetime import datetime, timezone

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user

# Extensões (criadas fora da factory)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
def create_app(config_object=None):
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    
    static_path = os.path.join(basedir, "static")

    app = Flask(
        __name__, 
        template_folder="templates", 
        static_folder=static_path,     # Agora aponta para /app/static
        static_url_path="/static"      # Mantém a URL como /static/ no navegador
    )        

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

    # garante que os models sejam conhecidos pelo SQLAlchemy/Migrate
    from app.models.usuario import Usuario  # noqa: F401
    from app.models.material import MaterialPSA  # noqa: F401

    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.login_message_category = "warning"

    # =========================
    # Context Processor (KPIs + Datas) — para os cards funcionarem em TODAS as páginas
    # =========================
    @app.context_processor
    def inject_globals():
        from datetime import datetime, timezone
        from flask import current_app, request
        from flask_login import current_user
    
        ctx = {
            "now": datetime.now(timezone.utc),
            "has_enviar_reporte": "reports.enviar_reporte" in current_app.view_functions,
        }
    
        # Só calcula KPIs/datas para usuário logado
        if not current_user.is_authenticated:
            return ctx
    
        data_filtro = request.args.get("data_filtro")
    
        try:
            from app.services.kpis import calcular_kpis, listar_datas_importacao
    
            ctx["data_atual"] = data_filtro
            ctx["datas"] = listar_datas_importacao()
            ctx["ctx_version"] = "CTX-2026-03-01-01"
    
            k = calcular_kpis(data_filtro)
            ctx.update(
                total=k.get("total", 0),
                conferidos=k.get("conferidos", 0),
                pendentes=k.get("pendentes", 0),
                acuracidade=k.get("acuracidade", 0.0),
                taxa_qualidade=k.get("taxa_qualidade", 100.0),
                itens_com_divergencia=k.get("itens_com_divergencia", 0),
                total_retencao=k.get("total_retencao", 0),
            )
        except Exception as e:
            # ✅ Loga o erro no Render, mas não derruba a página
            current_app.logger.exception("Falha ao injetar KPIs no context_processor: %s", e)
    
            ctx.setdefault("data_atual", data_filtro)
            ctx.setdefault("datas", [])
            ctx.setdefault("total", 0)
            ctx.setdefault("conferidos", 0)
            ctx.setdefault("pendentes", 0)
            ctx.setdefault("acuracidade", 0.0)
            ctx.setdefault("taxa_qualidade", 100.0)
            ctx.setdefault("itens_com_divergencia", 0)
            ctx.setdefault("total_retencao", 0)
    
        return ctx

    # =========================
    # Blueprints
    # =========================
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    # Poka-yoke: se rotas críticas não forem carregadas, falha no boot (evita regressões em deploy)
    missing = [ep for ep in ("main.login", "main.registrar") if ep not in app.view_functions]
    if missing:
        raise RuntimeError(
            f"Endpoints ausentes: {missing}. Rotas do blueprint 'main' não foram carregadas."
        )

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    from app.routes.importer import bp as importer_bp
    app.register_blueprint(importer_bp)

    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    # ✅ admin
    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    # =========================
    # Flask-Login user_loader
    # =========================
    from app.models.usuario import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(Usuario, int(user_id))
        except (TypeError, ValueError):
            return None

    # =========================
    # Banco: create_all apenas em DEV
    # =========================
    if app.debug or os.getenv("FLASK_ENV") == "development":
        with app.app_context():
            db.create_all()

    return app

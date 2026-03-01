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
    # 1. Localiza o caminho absoluto da pasta /app (onde este arquivo está)
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    # 2. Sobe um nível para encontrar a pasta 'static' na raiz do projeto
    # Isso é essencial para o Render localizar os arquivos
    root_path = os.path.abspath(os.path.join(basedir, ".."))
    static_path = os.path.join(root_path, "static")

    app = Flask(
        __name__, 
        template_folder="templates", 
        static_folder=static_path,     # Define o local físico real
        static_url_path="/static"      # Define o prefixo da URL no navegador
    )
    
    # ... restante do seu código (configurações de DB, Blueprints, etc)

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
        from flask import current_app

        ctx = {
            "now": datetime.now(timezone.utc),
            # poka‑yoke do menu: não quebra template se rota não existir em algum ambiente
            "has_enviar_reporte": "reports.enviar_reporte" in current_app.view_functions,
        }

        # Só calcula KPIs/datas para usuário logado (evita custo e evita erro no login)
        if not current_user.is_authenticated:
            return ctx

        # Usa o mesmo parâmetro do dashboard
        data_filtro = request.args.get("data_filtro")

        try:
            from app.services.kpis import calcular_kpis, listar_datas_importacao

            ctx["data_atual"] = data_filtro
            ctx["datas"] = listar_datas_importacao()

            k = calcular_kpis(data_filtro)
            ctx.update(
                total=k["total"],
                conferidos=k["conferidos"],
                pendentes=k["pendentes"],
                acuracidade=k["acuracidade"],
                taxa_qualidade=k["taxa_qualidade"],
                itens_com_divergencia=k["itens_com_divergencia"],
                total_retencao=k["total_retencao"],
            )
        except Exception:
            # Se algo falhar aqui, nunca derrube a renderização do template
            ctx.setdefault("data_atual", data_filtro)
            ctx.setdefault("datas", [])
            ctx.setdefault("total", 0)
            ctx.setdefault("conferidos", 0)
            ctx.setdefault("pendentes", 0)
            ctx.setdefault("acuracidade", 0)
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

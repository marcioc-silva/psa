from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from datetime import datetime
import os
from datetime import datetime
from flask import request, session
from flask_login import current_user
from app.services.kpis import calcular_kpis, listar_datas_importacao

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Garante que a pasta instance existe (caso use SQLite localmente)
    instance_path = os.path.join(os.path.dirname(__file__), '..', 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)

    # Inicializa as extensões
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)

    # CRÍTICO: Criação das tabelas no banco de dados
    with app.app_context():
        # Importa os modelos para que o SQLAlchemy os reconheça
        # POKA-YOKE de import: em versões antigas do projeto o model
        # vinha como app.models.user.User. No projeto atual é app.models.usuario.Usuario.
        try:
            from app.models.usuario import Usuario  # type: ignore
        except ModuleNotFoundError:  # fallback legado
            from app.models.user import User as Usuario  # type: ignore
        from app.models.material import MaterialPSA, HistoricoPSA
        from app.models.configuracao import ConfiguracaoSistema
        
        # Cria as tabelas se elas não existirem
        db.create_all()

        # POKA-YOKE: create_all() não cria colunas novas em tabelas já existentes.
        # Isso evita o 500 em produção quando o model evolui (ex.: email_remetente).
        try:
            from app.services.schema import ensure_schema
            ensure_schema(db)
        except Exception:
            # Nunca derruba o app por causa de verificação/ajuste de schema.
            app.logger.exception("Falha ao executar ensure_schema (continuando mesmo assim)")

    @login_manager.user_loader
    def load_user(user_id):
        try:
            from app.models.usuario import Usuario  # type: ignore
        except ModuleNotFoundError:
            from app.models.user import User as Usuario  # type: ignore
        return Usuario.query.get(int(user_id))

    # Login obrigatório global (exceto login/registro/static)
    from flask_login import current_user
    from flask import request, redirect, url_for

    @app.before_request
    def _require_login_global():
        if request.endpoint in (None, 'static'):
            return
        allow = {'main.login', 'main.registrar'}
        if request.endpoint in allow:
            return
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))

    # Registro de Blueprints
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    from app.routes.importer import bp as importer_bp
    app.register_blueprint(importer_bp)

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    # Rotas do scanner/conferência (sem prefixo) para compatibilidade com o frontend
    try:
        from app.routes.routes_scanner_api import bp_scanner_api
        app.register_blueprint(bp_scanner_api)
    except Exception:
        app.logger.exception("Falha ao registrar bp_scanner_api")

    try:
        from app.routes.routes_conferencia import bp_conf
        app.register_blueprint(bp_conf)
    except Exception:
        app.logger.exception("Falha ao registrar bp_conf")

from datetime import datetime
from flask import request, session
from flask_login import current_user
from app.services.kpis import calcular_kpis, listar_datas_importacao

@app.context_processor
def inject_now():
    # 1) Se veio na URL, atualiza a session (inclui limpar com "")
    if 'data_filtro' in request.args:
        valor = request.args.get('data_filtro')
        session['data_filtro'] = valor if valor else None

    # 2) Fallback: se não veio na URL, usa o que estiver salvo
    data_atual = session.get('data_filtro')

    if not current_user.is_authenticated:
        return {
            'now': datetime.now(),
            'data_atual': None,
            'datas': []
        }

    kpis = calcular_kpis(data_atual)
    datas = listar_datas_importacao()

    return {
        'now': datetime.now(),
        'data_atual': data_atual,
        'datas': datas,
        **kpis,
    }

    return app

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.login'


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Garante que a pasta instance existe (onde fica o SQLite)
    import os
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'instance'), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)

    # Importa models
    from app.models.usuario import Usuario
    from app.models.material import MaterialPSA, HistoricoPSA
    from app.models.configuracao import ConfiguracaoSistema

    
    @login_manager.user_loader
    def load_user(user_id):
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

    # Blueprints
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

    @app.context_processor
    def inject_now():
        from flask import request
        from flask_login import current_user
        from app.services.kpis import calcular_kpis, listar_datas_importacao

        data_atual = request.args.get('data_filtro')

        if not current_user.is_authenticated:
            return {
                'now': datetime.now(),
                'data_atual': None,
                'datas': [],
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
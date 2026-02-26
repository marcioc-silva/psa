import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

login_manager = LoginManager()
# 1. REMOVI o import do reports_bp daqui do topo para evitar o erro circular

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    # configure SECRET_KEY e DATABASE_URI AQUI, antes de init_app
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "uma-chave-muito-segura-da-nestle")
    app.config["SQLALCHEMY_DATABASE_URI"] = resolve_database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "login"   # ou "main.login" se estiver em blueprint

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    # 3. Processador de contexto corrigido
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    # 4. REGISTRO DE BLUEPRINTS (Importações locais para evitar erros)
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    from app.routes.importer import bp as importer_bp
    app.register_blueprint(importer_bp)

    # Importação do reports movida para cá, garantindo que o db já existe
    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    with app.app_context():
        db.create_all()

    return app

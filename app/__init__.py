import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager # Importação mantida

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager() # 1. CRIAÇÃO da instância (Poka-Yoke de inicialização)

def create_app():
    app = Flask(__name__, 
                template_folder='templates', 
                static_folder='static')

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '..', 'instance', 'psa_storage.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'nestle-aracatuba-supervisao'

    # 2. Inicializa db, migrate e LOGIN_MANAGER
    db.init_app(app)
    migrate.init_app(app, db)
    
    # CONEXÃO DO LOGIN AO APP (Isso resolve o erro 500 do Render)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # Define para onde vai quem não está logado

    # 3. Processador de contexto
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    # 4. REGISTRO DE BLUEPRINTS
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.api import bp as api_bp
    app.register_blueprint(api_bp)

    from app.routes.importer import bp as importer_bp
    app.register_blueprint(importer_bp)

    from app.routes.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    # 5. Adicione o user_loader (Necessário para o Flask-Login funcionar)
    from app.models.user import User # Certifique-se que o caminho do seu model de User está correto
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    return app
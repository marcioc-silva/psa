import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# 1. REMOVI o import do reports_bp daqui do topo para evitar o erro circular

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__, 
                template_folder='templates', 
                static_folder='static')

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, '..', 'instance', 'psa_storage.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'nestle-aracatuba-supervisao'

    # 2. Inicializa db e migrate primeiro
    db.init_app(app)
    migrate.init_app(app, db)

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
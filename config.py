import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def resolve_database_url():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    base_dir = os.path.abspath(os.path.dirname(__file__))  # pasta app/
    db_path = os.path.join(base_dir, "psa_storage.db")
    return f"sqlite:///{db_path}"

def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "uma-chave-muito-segura-da-nestle")
    app.config["SQLALCHEMY_DATABASE_URI"] = resolve_database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "login"  # ou "main.login" se estiver em blueprint

    from app.models.material import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Usuario, int(user_id))

    # aqui você registra suas rotas/blueprints
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    return app

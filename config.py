import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-dev'
    # Define SQLite como padrão, mas aceita DATABASE_URL para PostgreSQL (Heroku/Render/AWS)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///psa_storage.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    VERSION = "1.2.0"
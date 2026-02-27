from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    sap = db.Column(db.String(20), unique=True, nullable=False)
    nome_completo = db.Column(db.String(100), nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)

    # Níveis: 'admin' ou 'operador'
    cargo = db.Column(db.String(20), nullable=False, default='operador')

    @property
    def is_admin(self) -> bool:
        return (self.cargo or '').lower() == 'admin'

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
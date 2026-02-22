from datetime import datetime
from app import db
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    # O campo SAP será o identificador único para login (ex: 12345678)
    sap = db.Column(db.String(20), unique=True, nullable=False)
    nome_completo = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Níveis: 'admin' ou 'operador'
    cargo = db.Column(db.String(20), nullable=False, default='operador')

    def definir_senha(self, senha):
        self.password_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.password_hash, senha)
    

class MaterialPSA(db.Model):
    __tablename__ = 'material_psa'
    id = db.Column(db.Integer, primary_key=True)
    
    # --- Identificação ---
    unidade_deposito = db.Column(db.String(50), unique=True, nullable=False) # UD
    cod_material = db.Column(db.String(50), nullable=False)
    desc_material = db.Column(db.String(200))
    lote = db.Column(db.String(50))
    
    # --- Localização e Quantidade ---
    posicao_deposito = db.Column(db.String(50))
    tipo_deposito = db.Column(db.String(20)) # PSA, Depósito Fixo, etc.
    quantidade_estoque = db.Column(db.Float, default=0.0)
    unidade_medida = db.Column(db.String(10)) # PC, KG, UN
    
    # --- Inteligência de Datas ---
    data_vencimento = db.Column(db.Date)
    data_ultimo_mov = db.Column(db.Date)
    data_importacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # --- Controle de Auditoria ---
    conferido = db.Column(db.Boolean, default=False)
    data_conferencia = db.Column(db.DateTime)
    conferente_sap = db.Column(db.String(20)) # Removi a FK temporariamente para evitar erro se a tabela usuarios não existir
    
    # --- Gestão de Divergências ---
    possui_divergencia = db.Column(db.Boolean, default=False)
    observacao_conferente = db.Column(db.Text)

    def to_dict(self):
        """Retorno limpo para o Scanner e Dashboard (Sem definições de colunas aqui)"""
        return {
            "id": self.id,
            "ud": self.unidade_deposito,
            "material": self.cod_material,
            "descricao": self.desc_material,
            "lote": self.lote or "S/L",
            "posicao": self.posicao_deposito or "S/P",
            "tipdep": self.tipo_deposito,
            "qtd": f"{self.quantidade_estoque:.0f}",
            "unidade": self.unidade_medida,
            "vencimento": self.data_vencimento.strftime('%d/%m/%Y') if self.data_vencimento else "S/V",
            "ult_mov": self.data_ultimo_mov.strftime('%d/%m/%Y') if self.data_ultimo_mov else "---",
            "status": "CONFERIDO" if self.conferido else "PENDENTE",
            "alerta_risco": self.possui_divergencia,
            "observacao": self.observacao_conferente or ""
        }

class HistoricoPSA(db.Model):
    __tablename__ = 'historico_psa'
    id = db.Column(db.Integer, primary_key=True)
    
    # Referência ao material original
    material_id = db.Column(db.Integer) 
    unidade_deposito = db.Column(db.String(50)) # Guardamos a UD para busca rápida
    
    # Dados do "Momento da Batida" (O que pode mudar no futuro)
    lote_visto = db.Column(db.String(50))
    qtd_visto = db.Column(db.Float)
    
    # Rastreabilidade
    data_evento = db.Column(db.DateTime, default=datetime.utcnow)
    conferente_sap = db.Column(db.String(20))
    tipo_movimento = db.Column(db.String(50)) # Ex: "Conferência Scanner" ou "Ajuste Manual"
    observacao = db.Column(db.Text)
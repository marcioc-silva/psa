from __future__ import annotations

from datetime import datetime
from app import db

# Dica: se quiser isolar o MyDot, configure SQLALCHEMY_BINDS['mydot'] no PSA
# e adicione __bind_key__ = 'mydot' aqui.



class MyDotPunch(db.Model):
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)

    # Modo industrial: link com Usuario do PSA
    user_id = db.Column(db.Integer, nullable=True, index=True)

    # Modo individual: identifica “perfil” por dispositivo
    device_id = db.Column(db.String(64), nullable=True, index=True)

    # entrada/saida/pausa/retorno
    kind = db.Column(db.String(16), nullable=False, index=True)

    ts_utc = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    # Geolocalização (opcional)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    acc_m = db.Column(db.Float, nullable=True)

    # Auditoria
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # Foto (caminho relativo, salvo em app/static/mydot/uploads)
    photo_path = db.Column(db.String(255), nullable=True)

    # Hash da imagem (para detectar repetição/clone)
    img_hash = db.Column(db.String(64), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<MyDotPunch id={self.id} kind={self.kind} ts_utc={self.ts_utc}>"

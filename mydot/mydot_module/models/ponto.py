from app import db
from datetime import datetime, timezone


class MyDotPunch(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)

    # Identidade (modo individual ou modo login)
    device_id = db.Column(db.String(64), index=True, nullable=True)
    user_id = db.Column(db.Integer, index=True, nullable=True)  # opcional, sem FK por enquanto

    # Conteúdo do registro
    kind = db.Column(db.String(10), nullable=False)   # entrada/saida/pausa/retorno (ou o que você decidir)
    label = db.Column(db.String(40), nullable=True)   # opcional (interpretação, turno etc.)

    ts_utc = db.Column(db.DateTime(timezone=True), nullable=False,
                       default=lambda: datetime.now(timezone.utc))

    # Geo (opcional)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)
    acc_m = db.Column(db.Float, nullable=True)

    # Auditoria (opcional)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    # Foto
    photo_path = db.Column(db.String(255), nullable=True)
    img_hash = db.Column(db.String(64), index=True, nullable=True)
from app import db
from datetime import datetime, timezone

import pytz
from datetime import datetime

class MyDotPunch(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), index=True, nullable=True)
    kind = db.Column(db.String(10), nullable=False)

    # Altere o default para já pegar o horário de São Paulo sem fuso (Naive)
    # Isso garante que o SQLite salve exatamente o número que você quer ver
    ts_utc = db.Column(db.String(30), nullable=False)
    #  ts_utc = db.Column(db.DateTime, nullable=False, 
    #                    default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')).replace(tzinfo=None))

    @property
    def ts_local(self):
        # Como o dado já vai estar "limpo" no banco com a hora de SP, 
        # basta retornar o valor puro
        return self.ts_utc
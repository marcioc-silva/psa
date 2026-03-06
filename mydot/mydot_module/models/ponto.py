from zoneinfo import ZoneInfo
from app import db
from datetime import datetime
import pytz


class MyDotPunch(db.Model):
    __bind_key__ = "mydot"
    __tablename__ = "mydot_punch"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(64), index=True, nullable=True)
    kind = db.Column(db.String(10), nullable=False)

    # Altere o default para já pegar o horário de São Paulo sem fuso (Naive)
    # Isso garante que o SQLite salve exatamente o número que você quer ver
    ts_utc = db.Column(db.DateTime, nullable=False, 
                       default=lambda: datetime.now(pytz.timezone('America/Sao_Paulo')).replace(tzinfo=None))

    @property
    def ts_local(self):
        # Se o banco salvou como UTC, forçamos a exibição em SP
        # Se você seguiu a dica anterior de salvar já em SP, basta retornar self.ts_utc
        fuso_sp = ZoneInfo("America/Sao_Paulo")
        if self.ts_utc.tzinfo is None:
            # Se o dado no banco não tiver fuso, dizemos que ele é UTC e convertemos para SP
            return self.ts_utc.replace(tzinfo=pytz.timezone.utc).astimezone(fuso_sp)
        return self.ts_utc.astimezone(fuso_sp)
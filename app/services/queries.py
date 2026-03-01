from __future__ import annotations

from datetime import datetime
from sqlalchemy import func

from app.models import MaterialPSA  # ajuste se seu model estiver em outro módulo


def scoped_material_query(db_session, data_filtro: str | None):
    """
    Retorna uma query base de MaterialPSA já com o filtro de data aplicado (quando válido).
    data_filtro: string YYYY-MM-DD ou None
    """
    query = db_session.query(MaterialPSA)

    if data_filtro:
        try:
            data_dt = datetime.strptime(data_filtro, "%Y-%m-%d").date()
            query = query.filter(func.date(MaterialPSA.data_importacao) == data_dt)
        except ValueError:
            # se vier lixo, ignora o filtro em vez de quebrar
            pass

    return query

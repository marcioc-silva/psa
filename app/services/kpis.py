from __future__ import annotations

from datetime import datetime, timedelta, date, time
from typing import Optional, Dict, Any

from sqlalchemy import func

from app.models.material import MaterialPSA
from app import db


def _parse_data_filtro(data_filtro: str | None) -> date | None:
    """Aceita 'YYYY-MM-DD' ou 'DD/MM/YYYY' e retorna date. Qualquer outra coisa -> None."""
    if not data_filtro:
        return None

    s = str(data_filtro).strip()
    if not s or s.lower() == "none":
        return None

    # tenta DD/MM/YYYY
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def calcular_kpis(data_filtro: str | None = None) -> Dict[str, Any]:
    """Calcula KPIs principais para dashboard e reporte por e-mail."""
    data_dt = _parse_data_filtro(data_filtro)

    q = MaterialPSA.query
    if data_dt:
        q = q.filter(func.date(MaterialPSA.data_importacao) == data_dt)

    materiais = q.all()
    total = len(materiais)

    conferidos = sum(1 for m in materiais if bool(getattr(m, "conferido", False)))
    pendentes = total - conferidos

    itens_com_divergencia = sum(
        1 for m in materiais if bool(getattr(m, "possui_divergencia", False))
    )

    acuracidade = round((conferidos / total * 100), 1) if total > 0 else 0.0

    taxa_qualidade = (
        round(((total - itens_com_divergencia) / total * 100), 1) if total > 0 else 0.0
    )

    # Retenção (heurística atual): pendentes com importação há mais de 48h
    limite = datetime.now() - timedelta(hours=48)

    def _to_dt(v) -> datetime | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, date):
            return datetime.combine(v, time.min)
        return None

    total_retencao = sum(
        1
        for m in materiais
        if not bool(getattr(m, "conferido", False))
        and (_to_dt(getattr(m, "data_importacao", None)) is not None)
        and (_to_dt(getattr(m, "data_importacao", None)) <= limite)
    )

    return {
        "total": total,
        "conferidos": conferidos,
        "pendentes": pendentes,
        "itens_com_divergencia": itens_com_divergencia,
        "acuracidade": acuracidade,
        "taxa_qualidade": taxa_qualidade,
        "total_retencao": total_retencao,
        "data_filtro_date": data_dt,  # útil internamente
    }

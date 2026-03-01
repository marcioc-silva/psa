from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

from sqlalchemy import func

from app import db
from app.models.material import MaterialPSA


def _parse_data_filtro(data_filtro: str | None) -> Optional[date]:
    """Aceita 'DD/MM/YYYY' ou 'YYYY-MM-DD' e retorna date, ou None."""
    if not data_filtro:
        return None
    s = (data_filtro or "").strip()
    if not s or s.lower() == "none":
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def listar_datas_importacao() -> List[str]:
    """Lista datas únicas de importação no formato DD/MM/YYYY (desc)."""
    col = MaterialPSA.data_importacao
    rows = (
        db.session.query(func.date(col).label("d"))
        .filter(col.isnot(None))
        .distinct()
        .order_by(func.date(col).desc())
        .all()
    )
    out: List[str] = []
    for (d,) in rows:
        if d:
            out.append(d.strftime("%d/%m/%Y"))
    return out


def calcular_kpis(data_filtro: str | None = None) -> Dict[str, Any]:
    """Calcula KPIs usados nos cards, com ou sem filtro de data."""
    dt = _parse_data_filtro(data_filtro)

    base = MaterialPSA.query
    if dt:
        base = base.filter(func.date(MaterialPSA.data_importacao) == dt)

    total = base.count()

    conferidos_q = base.filter(MaterialPSA.conferido.is_(True))
    conferidos = conferidos_q.count()

    pendentes = total - conferidos

    # Divergências: só se a coluna existir
    itens_com_divergencia = 0
    if hasattr(MaterialPSA, "possui_divergencia"):
        itens_com_divergencia = base.filter(MaterialPSA.possui_divergencia.is_(True)).count()

    taxa_qualidade = round(((conferidos - itens_com_divergencia) / conferidos * 100), 1) if conferidos > 0 else 100.0
    acuracidade = round((conferidos / total * 100), 1) if total > 0 else 0.0

    # Retenção: pendentes parados há mais de 48h
    limite_dt = datetime.now() - timedelta(hours=48)
    ret_q = base.filter(MaterialPSA.conferido.is_(False))

    # data_importacao pode ser date OU datetime. Tentamos inferir.
    try:
        is_dt = MaterialPSA.data_importacao.type.python_type is datetime
    except Exception:
        is_dt = False

    if is_dt:
        ret_q = ret_q.filter(MaterialPSA.data_importacao <= limite_dt)
    else:
        ret_q = ret_q.filter(func.date(MaterialPSA.data_importacao) <= limite_dt.date())

    total_retencao = ret_q.count()

    return {
        "total": total,
        "conferidos": conferidos,
        "pendentes": pendentes,
        "itens_com_divergencia": itens_com_divergencia,
        "taxa_qualidade": taxa_qualidade,
        "acuracidade": acuracidade,
        "total_retencao": total_retencao,
    }

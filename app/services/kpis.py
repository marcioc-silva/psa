from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any

from sqlalchemy import func

from app.models.material import MaterialPSA


def _parse_data_filtro(data_filtro: str | None) -> Optional[date]:
    if not data_filtro:
        return None
    s = str(data_filtro).strip()
    if not s or s.lower() == "none":
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def calcular_kpis(*, data_filtro: str | None = None, psa_key: str | None = None) -> Dict[str, Any]:
    dt = _parse_data_filtro(data_filtro)

    q = MaterialPSA.query

    # ✅ filtro por PSA
    if psa_key:
        q = q.filter(MaterialPSA.psa_key == psa_key)

    # ✅ filtro por data de importação (se você quiser manter assim)
    if dt:
        q = q.filter(func.date(MaterialPSA.data_importacao) == dt)

    materiais = q.all()

    total = len(materiais)
    conferidos = sum(1 for m in materiais if bool(m.conferido))
    pendentes = total - conferidos

    itens_com_divergencia = sum(1 for m in materiais if bool(getattr(m, "possui_divergencia", False)))

    taxa_qualidade = round(((conferidos - itens_com_divergencia) / conferidos * 100), 1) if conferidos > 0 else 100.0
    acuracidade = round((conferidos / total * 100), 1) if total > 0 else 0.0

    # ✅ retenção: 48h, preferindo data_ultimo_mov; fallback para data_importacao
    limite = datetime.now() - timedelta(hours=48)

    def _ref_dt(m: MaterialPSA):
        # se seu campo for DATE, converte pra datetime no começo do dia
        if getattr(m, "data_ultimo_mov", None):
            d = m.data_ultimo_mov
            if isinstance(d, date) and not isinstance(d, datetime):
                return datetime.combine(d, datetime.min.time())
            return d
        return m.data_importacao

    retidos = [
        m for m in materiais
        if (not bool(m.conferido)) and (_ref_dt(m) is not None) and (_ref_dt(m) <= limite)
    ]

    total_retencao = len(retidos)
    retencao_pendente = total_retencao  # ✅ por enquanto: “retidos e pendentes” são a mesma coisa

    return {
        "total": total,
        "conferidos": conferidos,
        "pendentes": pendentes,
        "itens_com_divergencia": itens_com_divergencia,
        "taxa_qualidade": taxa_qualidade,
        "acuracidade": acuracidade,
        "total_retencao": total_retencao,
        "retencao_pendente": retencao_pendente,
        "psa_key": psa_key,
        "data_filtro": data_filtro,
    }


def listar_datas_importacao(psa_key: str | None = None):
    q = MaterialPSA.query.filter(MaterialPSA.data_importacao.isnot(None))
    if psa_key:
        q = q.filter(MaterialPSA.psa_key == psa_key)

    materiais = q.all()
    datas_unicas = {m.data_importacao.strftime("%d/%m/%Y") for m in materiais if m.data_importacao}
    return sorted(list(datas_unicas), reverse=True)

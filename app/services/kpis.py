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

    # aceita DD/MM/YYYY e YYYY-MM-DD
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def calcular_kpis(data_filtro: str | None = None) -> Dict[str, Any]:
    """Calcula KPIs do dashboard (e-mail/report) com o mesmo contrato esperado pelo frontend."""
    dt = _parse_data_filtro(data_filtro)

    q = MaterialPSA.query
    if dt:
        q = q.filter(func.date(MaterialPSA.data_importacao) == dt)

    materiais = q.all()

    total = len(materiais)
    conferidos = sum(1 for m in materiais if bool(m.conferido))
    pendentes = total - conferidos

    itens_com_divergencia = sum(1 for m in materiais if bool(getattr(m, "possui_divergencia", False)))

    # taxa de qualidade: semelhante ao main.dashboard (baseado em conferidos)
    taxa_qualidade = round(((conferidos - itens_com_divergencia) / conferidos * 100), 1) if conferidos > 0 else 100.0
    acuracidade = round((conferidos / total * 100), 1) if total > 0 else 0.0

    # retenção (critico): pendentes há mais de 48h desde importação
    limite = datetime.now() - timedelta(hours=48)
    total_retencao = sum(
        1 for m in materiais
        if (not bool(m.conferido)) and m.data_importacao and m.data_importacao <= limite
    )

    return {
        "total": total,
        "conferidos": conferidos,
        "pendentes": pendentes,
        "itens_com_divergencia": itens_com_divergencia,
        "taxa_qualidade": taxa_qualidade,
        "acuracidade": acuracidade,
        "total_retencao": total_retencao,
        "retencao_pendente": retidos_pendentes,
    }

def listar_datas_importacao():
    """Retorna uma lista com as datas únicas de importação formatadas para o filtro global."""
    materiais = MaterialPSA.query.filter(MaterialPSA.data_importacao.isnot(None)).all()
    
    # Extrai as datas únicas no formato DD/MM/YYYY
    datas_unicas = {
        m.data_importacao.strftime('%d/%m/%Y') 
        for m in materiais 
        if m.data_importacao
    }
    
    # Retorna a lista ordenada (da mais recente para a mais antiga)
    return sorted(list(datas_unicas), reverse=True)

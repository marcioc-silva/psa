from datetime import datetime

from sqlalchemy import func

from app.models.material import MaterialPSA
from app.services.scoping import scoped_material_query


def parse_data_filtro(data_filtro: str | None):
    if not data_filtro:
        return None
    try:
        return datetime.strptime(data_filtro, '%d-%m-%Y').date()
    except Exception:
        return None


def calcular_kpis(data_filtro: str | None):
    q = scoped_material_query()

    data_dt = parse_data_filtro(data_filtro)
    if data_dt:
        q = q.filter(func.date(MaterialPSA.data_importacao) == data_dt)

    materiais = q.all()
    total = len(materiais)
    conferidos = sum(1 for m in materiais if m.conferido)
    pendentes = total - conferidos
    acuracidade = round((conferidos / total * 100), 1) if total > 0 else 0

    itens_com_divergencia = sum(1 for m in materiais if m.possui_divergencia)
    taxa_qualidade = round(((total - itens_com_divergencia) / total * 100), 1) if total > 0 else 0

    hoje = datetime.now()
    total_retencao = sum(
        1
        for m in materiais
        if m.data_importacao and (hoje - m.data_importacao).days > 30 and not m.conferido
    )

    return {
        'total': total,
        'conferidos': conferidos,
        'pendentes': pendentes,
        'acuracidade': acuracidade,
        'itens_com_divergencia': itens_com_divergencia,
        'taxa_qualidade': taxa_qualidade,
        'total_retencao': total_retencao,
    }


def listar_datas_importacao():
    # Lista de datas (YYYY-MM-DD) disponíveis para o usuário atual
    datas = sorted(
        {
            m.data_importacao.strftime('%m-%Y-%d')
            for m in scoped_material_query().all()
            if m.data_importacao
        },
        reverse=True,
    )
    return datas

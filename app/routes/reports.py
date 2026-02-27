from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
from flask_login import login_required
from app.models.material import MaterialPSA
from datetime import datetime, timedelta
from app import db
from collections import Counter
from sqlalchemy import func

from app.services.authz import admin_required
from app.services.email_report import enviar_reporte_por_email

from app.services.scoping import scoped_material_query

bp = Blueprint('reports', __name__, url_prefix='/reports')


@bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')

from flask import request

@bp.route('/lista/<tipo>')
@login_required
def lista_materiais(tipo):
    # Captura a data que vem da URL (ex: /lista/pendentes?data_filtro=17/02/2026)
    data_filtro = request.args.get('data_filtro')
    
    # Inicia a query base pelo tipo (ex: Pendentes ou Conferidos)
    if tipo == 'pendentes':
        query = scoped_material_query().filter_by(conferido=False)
    elif tipo == 'conferidos':
        query = scoped_material_query().filter_by(conferido=True)
    else:
        query = scoped_material_query()

    # Aplica o segundo filtro (Data) apenas se ele existir
    if data_filtro and data_filtro != 'None':
        # Filtra comparando a data formatada no banco com a data recebida
        materiais = [m for m in query.all() if m.data_importacao.strftime('%d/%m/%Y') == data_filtro]
    else:
        materiais = query.all()

    return render_template('reports/lista.html', materiais=materiais, tipo=tipo, data_atual=data_filtro)

@bp.route('/alerta_critico')
@login_required
def alerta_critico():
    hoje = datetime.now()
    # Filtra tudo o que está parado há mais de 72 hora, independente do dia de importação
    limite = hoje - timedelta(hours=72)
    
    materiais_em_atraso = scoped_material_query().filter(
        MaterialPSA.data_importacao <=limite, 
        MaterialPSA.conferido == False
    ).all()
    
    # IMPORTANTE: O nome da variável enviada DEVE ser 'alertas'
    return render_template('reports/alerta_critico.html', 
                           alertas=materiais_em_atraso, 
                           now=hoje)

@bp.route('/kpis')
@login_required
def kpis():
    tipo_pareto = request.args.get('tipo_pareto', 'ocorrencias')
    materiais = scoped_material_query().all()
    hoje = datetime.now()

    # --- 1. Definição da regra ANTES do loop ---
    if tipo_pareto == 'ocorrencias':
        desc_regra = "Carga de Trabalho (UDs)"
    elif tipo_pareto == 'estoque':
        desc_regra = "Volume Físico (Quantidade)"
    elif tipo_pareto == 'retencao':
        desc_regra = "Gargalo de Tempo (Dias de Retenção)"
    else:
        desc_regra = "Critério não definido"

    # --- 2. Rosca e IRA ---
    encontrados = scoped_material_query().filter_by(conferido=True).count()
    pendentes = scoped_material_query().filter_by(conferido=False).count()
    total = encontrados + pendentes
    ira = round((encontrados / total * 100), 1) if total > 0 else 0

    # --- 3. Pareto ---
    dados_pareto = {}

    for m in materiais:
        nome = (m.desc_material or "N/D")[:20]

        if tipo_pareto == 'ocorrencias':
            dados_pareto[nome] = dados_pareto.get(nome, 0) + 1

        elif tipo_pareto == 'estoque':
            dados_pareto[nome] = dados_pareto.get(nome, 0) + (m.quantidade_estoque or 0)

        elif tipo_pareto == 'retencao':
            dias = (hoje - m.data_importacao).days if m.data_importacao else 0
            dados_pareto[nome] = dados_pareto.get(nome, 0) + max(0, dias)

    ordenado = sorted(dados_pareto.items(), key=lambda x: x[1], reverse=True)[:10]
    labels = [x[0] for x in ordenado]
    valores = [x[1] for x in ordenado]

    soma_total = sum(dados_pareto.values())
    acumulado = []
    soma_temp = 0

    for v in valores:
        soma_temp += v
        perc = (soma_temp / soma_total * 100) if soma_total > 0 else 0
        acumulado.append(round(perc, 1))

    # --- 4. Aging ---
    pendentes_lista = scoped_material_query().filter_by(conferido=False).all()
    vencimentos = [p.data_vencimento.strftime('%Y-%m') for p in pendentes_lista if p.data_vencimento]
    aging_counts = Counter(vencimentos)
    labels_venc = sorted(aging_counts.keys())
    valores_venc = [aging_counts[l] for l in labels_venc]

    return render_template(
        'reports/kpis.html',
        ira=ira,
        encontrados=encontrados,
        pendentes=pendentes,
        labels=labels,
        valores=valores,
        acumulado=acumulado,
        tipo_filtro=tipo_pareto,
        desc_regra=desc_regra,
        labels_venc=labels_venc,
        valores_venc=valores_venc
    )

@bp.route('/risco')
@login_required
def risco():
    # Visão de Supervisor: O que falta e o que já foi feito (ordenado por data)
    pendentes = scoped_material_query().filter_by(conferido=False).all()
    conferidos = scoped_material_query().filter_by(conferido=True).order_by(MaterialPSA.data_conferencia.desc()).all()
    return render_template('reports/risco.html', pendentes=pendentes, conferidos=conferidos)

from flask import render_template, request, Blueprint
from datetime import datetime

@bp.route('/pareto_retencao')
@login_required
def pareto_retencao():
    # Em vez de 'from app.models', usamos a importação relativa do pacote
    try:
        from ..models.material import MaterialPSA
    except (ImportError, ValueError):
        # Se falhar, tentamos o import absoluto de emergência
        from app.models.material import MaterialPSA

    data_filtro = request.args.get('data_filtro')
    
    # Filtro base: apenas o que não foi conferido
    query = scoped_material_query().filter_by(conferido=False)

    if data_filtro and data_filtro != 'None' and data_filtro != '':
        materiais = [m for m in query.all() if m.data_importacao.strftime('%d/%m/%Y') == data_filtro]
    else:
        materiais = query.all()

    hoje = datetime.now()
    retencao_por_material = {}

    for m in materiais:
        if m.data_importacao:
            dias = (hoje - m.data_importacao).days
            dias = max(0, dias) # Evita números negativos
            desc = (m.desc_material or "Sem Descrição")[:15]
            retencao_por_material[desc] = retencao_por_material.get(desc, 0) + dias

    # Ordenação decrescente (Pareto)
    sorted_data = sorted(retencao_por_material.items(), key=lambda x: x[1], reverse=True)
    
    # Top 8 para o gráfico vertical não ficar apertado
    labels = [x[0] for x in sorted_data[:8]]
    valores = [x[1] for x in sorted_data[:8]]

    return render_template('reports/pareto_retencao.html', 
                           labels=labels, 
                           valores=valores, 
                           data_atual=data_filtro)


@bp.route('/enviar_reporte', methods=['GET', 'POST'])
@login_required
@admin_required
def enviar_reporte():
    """Envia o reporte por e-mail usando as configurações do Admin."""
    data_filtro = request.args.get('data_filtro')
    ok, msg = enviar_reporte_por_email(data_filtro=data_filtro)
    flash(msg, 'success' if ok else 'danger')
    return redirect(url_for('admin.config'))

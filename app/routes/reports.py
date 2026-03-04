from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.models.material import MaterialPSA
from app.services.email_report import enviar_reporte_por_email


bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/")
@login_required
def index():
    return render_template("reports/index.html")


@bp.route("/lista/<tipo>")
@login_required
def lista_materiais(tipo: str):
    # Ex: /reports/lista/pendentes?data_filtro=17/02/2026
    data_filtro = request.args.get("data_filtro")

    if tipo == "pendentes":
        query = MaterialPSA.query.filter_by(conferido=False)
    elif tipo == "conferidos":
        query = MaterialPSA.query.filter_by(conferido=True)
    else:
        query = MaterialPSA.query

    if data_filtro and data_filtro != "None":
        materiais = [m for m in query.all() if m.data_importacao and m.data_importacao.strftime("%d/%m/%Y") == data_filtro]
    else:
        materiais = query.all()

    return render_template("reports/lista.html", materiais=materiais, tipo=tipo, data_atual=data_filtro)


@bp.route("/alerta-critico")
@login_required
def alerta_critico():
    hoje = datetime.now()

    # Como data_ultimo_mov é DATE, trabalhamos por dias fechados.
    # Limite: entrou há mais de 2 dias (equivalente gerencial a "48h / 2 dias")
    limite_data = (hoje.date() - timedelta(days=2))

    materiais_em_atraso = (
        MaterialPSA.query
        .filter(
            MaterialPSA.data_ultimo_mov.isnot(None),
            MaterialPSA.data_ultimo_mov <= limite_data,
            MaterialPSA.conferido.is_(False),
        )
        .all()
    )

    return render_template(
        "reports/alerta_critico.html",
        alertas=materiais_em_atraso,
        now=hoje,
        today=hoje.date()
    )


@bp.route("/kpis")
@login_required
def kpis():
    tipo_pareto = request.args.get("tipo_pareto", "ocorrencias")
    materiais = MaterialPSA.query.all()
    hoje = datetime.now()

    encontrados = MaterialPSA.query.filter_by(conferido=True).count()
    pendentes = MaterialPSA.query.filter_by(conferido=False).count()
    total = encontrados + pendentes
    ira = round((encontrados / total * 100), 1) if total > 0 else 0

    dados_pareto: dict[str, float] = {}
    desc_regra = "Carga de Trabalho (UDs)"
    for m in materiais:
        nome = (m.desc_material or "N/D")[:20]

        if tipo_pareto == "ocorrencias":
            dados_pareto[nome] = dados_pareto.get(nome, 0) + 1
            desc_regra = "Carga de Trabalho (UDs)"
        elif tipo_pareto == "estoque":
            dados_pareto[nome] = dados_pareto.get(nome, 0) + float(m.quantidade_estoque or 0)
            desc_regra = "Volume Físico (Quantidade)"
        elif tipo_pareto == "retencao":
            dias = (hoje - m.data_importacao).days if m.data_importacao else 0
            dados_pareto[nome] = dados_pareto.get(nome, 0) + max(0, dias)
            desc_regra = "Gargalo de Tempo (Dias de Retenção)"

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

    pendentes_lista = MaterialPSA.query.filter_by(conferido=False).all()
    vencimentos = [p.data_vencimento.strftime("%Y-%m") for p in pendentes_lista if p.data_vencimento]
    aging_counts = Counter(vencimentos)
    labels_venc = sorted(aging_counts.keys())
    valores_venc = [aging_counts[l] for l in labels_venc]

    return render_template(
        "reports/kpis.html",
        ira=ira,
        encontrados=encontrados,
        pendentes=pendentes,
        labels=labels,
        valores=valores,
        acumulado=acumulado,
        tipo_filtro=tipo_pareto,
        desc_regra=desc_regra,
        labels_venc=labels_venc,
        valores_venc=valores_venc,
    )


@bp.route("/risco")
@login_required
def risco():
    pendentes = MaterialPSA.query.filter_by(conferido=False).all()
    conferidos = (
        MaterialPSA.query.filter_by(conferido=True).order_by(MaterialPSA.data_conferencia.desc()).all()
    )
    return render_template("reports/risco.html", pendentes=pendentes, conferidos=conferidos)


@bp.route("/pareto_retencao")
@login_required
def pareto_retencao():
    data_filtro = request.args.get("data_filtro")

    query = MaterialPSA.query.filter_by(conferido=False)

    # Mantive sua lógica de filtro, mas trocando a coluna para data_ultimo_mov.
    if data_filtro and data_filtro not in ("None", ""):
        materiais = [
            m for m in query.all()
            if m.data_ultimo_mov and m.data_ultimo_mov.strftime("%d/%m/%Y") == data_filtro
        ]
    else:
        materiais = query.all()

    hoje = datetime.now().date()
    retencao_por_material: dict[str, int] = {}

    for m in materiais:
        if m.data_ultimo_mov:
            dias = max(0, (hoje - m.data_ultimo_mov).days)
            desc = (m.desc_material or "Sem Descrição")[:15]
            retencao_por_material[desc] = retencao_por_material.get(desc, 0) + dias

    sorted_data = sorted(retencao_por_material.items(), key=lambda x: x[1], reverse=True)
    labels = [x[0] for x in sorted_data[:8]]
    valores = [x[1] for x in sorted_data[:8]]

    return render_template("reports/pareto_retencao.html", labels=labels, valores=valores, data_atual=data_filtro)


@bp.route("/enviar-reporte", methods=["POST", "GET"], endpoint="enviar_reporte")
@login_required
def _enviar_reporte_route():
    data_filtro = request.args.get("data_filtro") or request.form.get("data_filtro")
    ok, msg = enviar_reporte_por_email(data_filtro=data_filtro)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("main.dashboard", data_filtro=data_filtro) if data_filtro else url_for("main.dashboard"))

@bp.route("/preview-reporte")
@login_required
def preview_reporte():
    data_filtro = request.args.get("data_filtro")
    assunto, html = montar_reporte_html(data_filtro=data_filtro)
    return html

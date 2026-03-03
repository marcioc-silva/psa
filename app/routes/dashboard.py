
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from sqlalchemy import func, case
from datetime import datetime, timedelta

from app import db
from app.models.material import MaterialPSA

bp = Blueprint("dash", __name__, url_prefix="/dash")


@bp.route("/")
@login_required
def dashboard():
    # só renderiza o layout; dados vêm via fetch no JS
    return render_template("dash/dashboard.html")


@bp.route("/api/dashboard")
@login_required
def dashboard_data():
    # filtros
    psa = request.args.get("psa")  # ex: "143:PSAKRONES"
    dias = request.args.get("dias", type=int, default=30)

    # janela de tempo (para tendências)
    dt_ini = datetime.now() - timedelta(days=dias)

    q = MaterialPSA.query

    if psa:
        q = q.filter(MaterialPSA.psa_key == psa)

    # KPIs
    total = q.count()

    conferidas = q.filter(MaterialPSA.conferido.is_(True)).count()
    pendentes = q.filter(MaterialPSA.conferido.is_(False)).count()
    divergentes = q.filter(MaterialPSA.possui_divergencia.is_(True)).count()

    # IRA (exemplo: conferidas / total)
    ira = (conferidas / total * 100.0) if total else 0.0
    meta_ira = 98.5

    # Donut: status
    status_labels = ["Conferidas", "Pendentes", "Divergência"]
    status_values = [conferidas, pendentes, divergentes]

    # Pareto por material (top 10 por "carga": qtd de UDs)
    pareto_rows = (
        q.with_entities(
            MaterialPSA.desc_material.label("material"),
            func.count(MaterialPSA.id).label("uds"),
        )
        .group_by(MaterialPSA.desc_material)
        .order_by(func.count(MaterialPSA.id).desc())
        .limit(10)
        .all()
    )
    pareto_labels = [r.material[:28] + ("…" if len(r.material) > 28 else "") for r in pareto_rows]
    pareto_values = [int(r.uds) for r in pareto_rows]

    # Vencimento (UDs por mês de vencimento)
    venc_rows = (
        q.with_entities(
            func.to_char(MaterialPSA.data_vencimento, "YYYY-MM").label("mes"),
            func.count(MaterialPSA.id).label("uds"),
        )
        .filter(MaterialPSA.data_vencimento.isnot(None))
        .group_by(func.to_char(MaterialPSA.data_vencimento, "YYYY-MM"))
        .order_by(func.to_char(MaterialPSA.data_vencimento, "YYYY-MM"))
        .all()
    )
    venc_labels = [r.mes for r in venc_rows]
    venc_values = [int(r.uds) for r in venc_rows]

    # Pendência por PSA (top 10)
    psa_rows = (
        MaterialPSA.query.with_entities(
            MaterialPSA.psa_key,
            func.count(MaterialPSA.id).label("pendentes")
        )
        .filter(MaterialPSA.conferido.is_(False))
        .group_by(MaterialPSA.psa_key)
        .order_by(func.count(MaterialPSA.id).desc())
        .limit(10)
        .all()
    )
    psa_labels = [r.psa_key for r in psa_rows]
    psa_values = [int(r.pendentes) for r in psa_rows]

    # Tendência: conferências por dia (últimos N dias)
    trend_rows = (
        q.with_entities(
            func.date(MaterialPSA.data_conferencia).label("dia"),
            func.count(MaterialPSA.id).label("qtd"),
        )
        .filter(MaterialPSA.data_conferencia.isnot(None))
        .filter(MaterialPSA.data_conferencia >= dt_ini)
        .group_by(func.date(MaterialPSA.data_conferencia))
        .order_by(func.date(MaterialPSA.data_conferencia))
        .all()
    )
    trend_labels = [str(r.dia) for r in trend_rows]
    trend_values = [int(r.qtd) for r in trend_rows]

    return jsonify({
        "filters": {
            "psa": psa,
            "dias": dias,
        },
        "kpis": {
            "total": total,
            "conferidas": conferidas,
            "pendentes": pendentes,
            "divergentes": divergentes,
            "ira": round(ira, 1),
            "meta_ira": meta_ira,
        },
        "charts": {
            "status": {"labels": status_labels, "values": status_values},
            "pareto": {"labels": pareto_labels, "values": pareto_values},
            "vencimento": {"labels": venc_labels, "values": venc_values},
            "pendencia_psa": {"labels": psa_labels, "values": psa_values},
            "trend_conferencia": {"labels": trend_labels, "values": trend_values},
        }
    })

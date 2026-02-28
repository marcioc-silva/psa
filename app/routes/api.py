from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import cast, String

from app import db
from app.models.material import MaterialPSA, HistoricoPSA
from app.services.scoping import scoped_material_query


bp = Blueprint("api", __name__, url_prefix="/api")


def _norm_ud(value: str) -> str:
    ud = (value or "").strip()
    # Excel/Pandas às vezes vira "123.0"
    if ud.endswith(".0"):
        ud = ud[:-2]
    return ud


# ================================
# DETALHE UD (Scanner / Manual)
# ================================
@bp.route("/get_detalhes_ud/<ud>", methods=["GET"])
@login_required
def get_detalhes_ud(ud: str):
    ud = _norm_ud(ud)
    if not ud:
        return jsonify({"success": False, "message": "UD inválida."}), 400

    # match exato primeiro
    material = scoped_material_query().filter_by(unidade_deposito=ud).first()

    # fallback parcial (remove zeros à esquerda)
    if not material:
        termo = f"%{ud.lstrip('0')}%"
        material = scoped_material_query().filter(
            cast(MaterialPSA.unidade_deposito, String).like(termo)
        ).first()

    if not material:
        return jsonify({"success": False, "message": "UD não encontrada."}), 404

    return jsonify({
        "success": True,
        "material": material.to_dict(),
    })


# ================================
# AUTOCOMPLETE / BUSCA MANUAL
# ================================
@bp.route("/search_manual", methods=["GET"])
@login_required
def search_manual():
    q = _norm_ud(request.args.get("q", ""))
    if not q or len(q) < 2:
        return jsonify({"success": True, "items": []})

    # Sugestões por prefixo/contém. Limitado para não pesar.
    termo = f"%{q}%"
    itens = (
        scoped_material_query()
        .filter(cast(MaterialPSA.unidade_deposito, String).like(termo))
        .order_by(MaterialPSA.unidade_deposito.asc())
        .limit(15)
        .all()
    )

    return jsonify({
        "success": True,
        "items": [
            {
                "ud": m.unidade_deposito,
                "descricao": getattr(m, "desc_material", None) or getattr(m, "descricao", None) or "",
                "id": m.id,
                "conferido": bool(m.conferido),
            }
            for m in itens
        ],
    })


# ================================
# CONSULTA MATERIAL (Scanner / Manual) - compat
# ================================
@bp.route("/consultar/<codigo>", methods=["GET"])
@login_required
def consultar(codigo: str):
    bruto = _norm_ud(codigo)
    if not bruto:
        return jsonify({"success": False, "message": "Código inválido."}), 400

    material = scoped_material_query().filter_by(unidade_deposito=bruto).first()
    if not material:
        termo_busca = f"%{bruto.lstrip('0')}%"
        material = scoped_material_query().filter(
            cast(MaterialPSA.unidade_deposito, String).like(termo_busca)
        ).first()

    if not material:
        return jsonify({"success": False, "message": "Material não encontrado."}), 404

    return jsonify({"success": True, "material": material.to_dict()})


# ================================
# DETALHE POR ID (LUPA MODAL)
# ================================
@bp.route("/material/<int:material_id>", methods=["GET"])
@login_required
def detalhe_material(material_id: int):
    material = scoped_material_query().filter_by(id=material_id).first()
    if not material:
        return jsonify({"success": False, "message": "Material não encontrado."}), 404
    return jsonify({"success": True, "material": material.to_dict()})


# ================================
# CONFIRMAR CONFERÊNCIA
# ================================
@bp.route("/confirmar", methods=["POST"])
@login_required
def confirmar():
    data = request.get_json(silent=True) or {}

    material_id = data.get("id")
    observacao = (data.get("observacao") or "").strip()
    possui_divergencia = bool(data.get("possui_divergencia", False))
    conferente_sap = (data.get("conferente_id") or "").strip()

    material = scoped_material_query().filter_by(id=material_id).first()
    if not material:
        return jsonify({"success": False, "message": "Material não encontrado."}), 404

    material.conferido = True
    material.data_conferencia = datetime.now()
    material.possui_divergencia = possui_divergencia
    material.observacao_conferente = observacao
    if conferente_sap:
        material.conferente_sap = conferente_sap

    # Rastro no histórico (poka-yoke de rastreabilidade)
    try:
        hist = HistoricoPSA(
            material_id=material.id,
            unidade_deposito=material.unidade_deposito,
            lote_visto=material.lote,
            qtd_visto=material.quantidade_estoque,
            conferente_sap=conferente_sap or None,
            status_final="CONFERIDO",
            data_evento=datetime.now(),
            observacao=observacao,
        )
        db.session.add(hist)
    except Exception:
        # Se não der pra gravar histórico por alguma diferença de schema, não trava a conferência.
        pass

    db.session.commit()
    return jsonify({"success": True})

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import cast, String

from app import db
from app.models.material import MaterialPSA
from app.services.scoping import scoped_material_query

bp = Blueprint("api", __name__, url_prefix="/api")

@bp.route("/get_detalhes_ud/<ud>", methods=["GET"])
@login_required
def get_detalhes_ud(ud):
    ud = (ud or "").strip()
    if not ud:
        return jsonify({"success": False, "message": "UD inválida."}), 400

    # match exato primeiro
    material = scoped_material_query().filter_by(unidade_deposito=ud).first()

    # fallback parcial
    if not material:
        termo = f"%{ud.lstrip('0')}%"
        material = scoped_material_query().filter(
            cast(MaterialPSA.unidade_deposito, String).like(termo)
        ).first()

    if not material:
        return jsonify({"success": False, "message": "UD não encontrada."}), 404
# ================================
# CONSULTA MATERIAL (Scanner / Manual)
# ================================
@bp.route("/consultar/<codigo>", methods=["GET"])
@login_required
def consultar(codigo):
    bruto = (codigo or "").strip()

    if not bruto:
        return jsonify({"success": False, "message": "Código inválido."}), 400

    # 1️⃣ Tenta match exato primeiro (mais seguro)
    material = scoped_material_query().filter_by(
        unidade_deposito=bruto
    ).first()

    # 2️⃣ Se não encontrou, tenta busca parcial removendo zeros à esquerda
    if not material:
        termo_busca = f"%{bruto.lstrip('0')}%"
        material = scoped_material_query().filter(
            cast(MaterialPSA.unidade_deposito, String).like(termo_busca)
        ).first()

    if not material:
        return jsonify({"success": False, "message": "Material não encontrado."}), 404

    return jsonify({
        "success": True,
        "material": material.to_dict()
    })


# ================================
# DETALHE POR ID (LUPA MODAL)
# ================================
@bp.route("/material/<int:material_id>", methods=["GET"])
@login_required
def detalhe_material(material_id):

    material = scoped_material_query().filter_by(id=material_id).first()

    if not material:
        return jsonify({"success": False, "message": "Material não encontrado."}), 404

    return jsonify({
        "success": True,
        "material": material.to_dict()
    })


# ================================
# CONFIRMAR CONFERÊNCIA
# ================================
@bp.route("/confirmar", methods=["POST"])
@login_required
def confirmar():

    data = request.get_json()

    material_id = data.get("id")
    observacao = data.get("observacao", "").strip()
    possui_divergencia = data.get("possui_divergencia", False)

    material = scoped_material_query().filter_by(id=material_id).first()

    if not material:
        return jsonify({"success": False, "message": "Material não encontrado."}), 404

    material.conferido = True
    material.possui_divergencia = possui_divergencia
    material.observacao_conferente = observacao

    db.session.commit()

    return jsonify({"success": True})
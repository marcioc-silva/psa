# routes_scanner_api.py
from __future__ import annotations

from flask import Blueprint, jsonify, current_app, request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from flask import request
from datetime import datetime
from app.models.material import MaterialPSA, HistoricoPSA
from app import db

bp_scanner_api = Blueprint("scanner_api", __name__)


def normaliza_ud(valor: str) -> str:
    ud = (valor or "").strip()
    if ud.endswith(".0"):
        ud = ud[:-2]
    return ud


@bp_scanner_api.get("/get_detalhes_ud/<string:ud>")
def get_detalhes_ud(ud: str):
    ud_norm = normaliza_ud(ud)

    if not ud_norm:
        return jsonify({"ok": False, "error": "UD inválida"}), 400

    try:
        stmt = select(MaterialPSA).where(MaterialPSA.unidade_deposito == ud_norm).limit(1)
        item = db.session.execute(stmt).scalar_one_or_none()

        if item is None:
            return jsonify({"ok": False, "error": "UD não encontrada"}), 404

        payload = {
            "ok": True,
            "id": item.id,
            "ud": item.unidade_deposito,
            "descricao": getattr(item, "desc_material", None),
            "qtd": getattr(item, "quantidade_estoque", None),
            "unidade": getattr(item, "unidade_medida", None),
            "lote": getattr(item, "lote", None),
            "vencimento": item.data_vencimento.strftime("%d/%m/%Y") if getattr(item, "data_vencimento", None) else None,
            "ult_mov": item.data_ultimo_mov.strftime("%d/%m/%Y") if getattr(item, "data_ultimo_mov", None) else None,
            "status": "CONFERIDO" if getattr(item, "conferido", False) else "PENDENTE",
        }

        return jsonify(payload), 200

    except SQLAlchemyError as e:
        current_app.logger.exception("Erro SQL ao buscar detalhes da UD: %s", e)
        return jsonify({"ok": False, "error": "Erro ao consultar banco de dados"}), 500

    except Exception as e:
        current_app.logger.exception("Erro inesperado ao buscar detalhes da UD: %s", e)
        return jsonify({"ok": False, "error": "Erro interno inesperado"}), 500


@bp_scanner_api.get("/search_manual")
def search_manual():
    termo = (request.args.get("q", "") or "").strip()

    if len(termo) < 3:
        return jsonify([]), 200

    try:
        stmt = (
            select(MaterialPSA)
            .where(MaterialPSA.unidade_deposito.like(f"%{termo}%"))
            .limit(20)
        )
        itens = db.session.execute(stmt).scalars().all()

        return jsonify([
            {"ud": i.unidade_deposito, "texto": getattr(i, "desc_material", None) or "Sem descrição"}
            for i in itens
        ]), 200

    except SQLAlchemyError as e:
        current_app.logger.exception("Erro SQL no search_manual: %s", e)
        return jsonify([]), 200  # não derruba a UI

    except Exception as e:
        current_app.logger.exception("Erro inesperado no search_manual: %s", e)
        return jsonify([]), 200
    

@bp_scanner_api.route("/confirmar", methods=["POST"])
def confirmar_leitura():
    try:
        data = request.get_json(silent=True) or {}
        material_id = data.get("id")

        if not material_id:
            return jsonify({"ok": False, "error": "ID não informado"}), 400

        material = db.session.get(MaterialPSA, material_id)
        if not material:
            return jsonify({"ok": False, "error": "Material não encontrado"}), 404

        possui_divergencia = bool(data.get("possui_divergencia", False))
        observacao = (data.get("observacao") or "").strip()

        material.conferido = True
        material.data_conferencia = datetime.utcnow()
        material.possui_divergencia = possui_divergencia
        material.observacao_conferente = observacao

        hist = HistoricoPSA(
            user_id=material.user_id,
            
            material_id=material.id,
            unidade_deposito=material.unidade_deposito,
            lote_visto=material.lote,
            qtd_visto=material.quantidade_estoque,
            data_evento=datetime.utcnow(),
            tipo_movimento="Conferência Scanner",
            observacao=observacao
        )
        db.session.add(hist)
        db.session.commit()

        return jsonify({"ok": True}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Erro ao confirmar leitura: %s", e)
        return jsonify({"ok": False, "error": "Erro interno ao confirmar"}), 500

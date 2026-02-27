# routes_scanner_api.py
from __future__ import annotations

from flask import Blueprint, jsonify, current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

# Ajuste o import conforme seu projeto:
# - se você usa "from app import db"
# - ou "from extensions import db"
from app import db


bp_scanner_api = Blueprint("scanner_api", __name__)


def normaliza_ud(valor: str) -> str:
    """
    Normaliza a UD para evitar mismatch vindo de Excel/Pandas:
    - remove espaços
    - remove sufixo .0 (quando Excel exporta como '123.0')
    """
    ud = (valor or "").strip()
    if ud.endswith(".0"):
        ud = ud[:-2]
    return ud


def _get_model():
    """
    PONTO CRÍTICO:
    Ajuste o import do seu Model aqui.
    Eu deixei como exemplo um model chamado 'MaterialPSA'.
    Troque pelo seu model real.
    """
    # Exemplo comum:
    # from app.models import MaterialPSA
    from app.models import MaterialPSA  # <-- TROQUE se seu model tiver outro nome
    return MaterialPSA


@bp_scanner_api.get("/get_detalhes_ud/<string:ud>")
def get_detalhes_ud(ud: str):
    from app.models.material import MaterialPSA

    ud_norm = normaliza_ud(ud)
    if not ud_norm:
        return jsonify({"ok": False, "error": "UD inválida"}), 400

    try:
        stmt = select(MaterialPSA).where(MaterialPSA.unidade_deposito == ud_norm).limit(1)
        item = db.session.execute(stmt).scalar_one_or_none()

        if item is None:
            return jsonify({"ok": False, "error": "UD não encontrada no sistema", "ud": ud_norm}), 404

        payload = {
            "ok": True,
            "ud": item.unidade_deposito,
            "cod_material": getattr(item, "codigo_material", None) or getattr(item, "cod_material", None),
            "lote": item.lote,
            "descricao": getattr(item, "descricao", None),
            "posicao_deposito": item.posicao_deposito,
            "tipo_deposito": item.tipo_deposito,
            "unidade_medida": item.unidade_medida,
            "quantidade_estoque": float(item.quantidade_estoque) if item.quantidade_estoque is not None else None,
            "data_vencimento": item.data_vencimento.isoformat() if item.data_vencimento else None,
            "data_ultimo_mov": item.data_ultimo_mov.isoformat() if item.data_ultimo_mov else None,
            "data_importacao": item.data_importacao.isoformat() if item.data_importacao else None,
            "conferido": bool(item.conferido),
            "possui_divergencia": bool(item.possui_divergencia),
            "observacao_conferente": item.observacao_conferente,
        }
        return jsonify(payload), 200

    except Exception as e:
        current_app.logger.exception("Erro inesperado ao buscar detalhes da UD: %s", e)
        return jsonify({"ok": False, "error": "Erro interno inesperado"}), 500
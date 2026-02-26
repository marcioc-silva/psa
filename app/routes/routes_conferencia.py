from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from app.models.material import MaterialPSA, HistoricoPSA

# Criamos um Blueprint para organizar as rotas de conferência
bp_conf = Blueprint('conferencia', __name__)

@bp_conf.route('/confirmar_conferencia', methods=['POST'])
def confirmar_conferencia():
    """
    Rota chamada pelo scanner (BIP) para validar o material
    e registar o rasto no histórico.
    """
    data = request.get_json()
    ud_lida = data.get('ud')
    sap_conferente = data.get('conferente_id')
    observacao = data.get('observacao', '')

    if not ud_lida or not sap_conferente:
        return jsonify({"status": "erro", "mensagem": "Dados insuficientes (UD ou ID em falta)"}), 400

    # 1. Localizar o material no cadastro atual
    material = MaterialPSA.query.filter_by(unidade_deposito=ud_lida).first()

    if not material:
        return jsonify({"status": "erro", "mensagem": f"UD {ud_lida} não encontrada no sistema"}), 404

    try:
        # --- OPERAÇÃO 1: Criar o Registo de Histórico (O rasto imutável) ---
        novo_historico = HistoricoPSA(
            material_id=material.id,
            unidade_deposito=material.unidade_deposito,
            lote_visto=material.lote,             # Regista o lote no momento do BIP
            qtd_visto=material.quantidade_estoque, # Regista a quantidade no momento do BIP
            conferente_sap=sap_conferente,
            status_final="CONFERIDO",
            data_evento=datetime.now(),
            observacao=observacao
        )
        db.session.add(novo_historico)

        # --- OPERAÇÃO 2: Atualizar a Tabela de Material (Status Atual) ---
        material.conferido = True
        material.data_conferencia = datetime.now()
        material.conferente_sap = sap_conferente
        
        # Se houver divergência marcada no scanner, podemos atualizar aqui
        if data.get('divergente'):
            material.possui_divergencia = True
            material.observacao_auditoria = observacao

        # --- FINALIZAÇÃO: Gravar tudo no banco de uma só vez ---
        db.session.commit()

        return jsonify({
            "status": "sucesso", 
            "mensagem": "BIP registado com sucesso!",
            "material": material.desc_material
        }), 200

    except Exception as e:
        db.session.rollback() # Se algo falhar, cancela as duas operações
        return jsonify({"status": "erro", "mensagem": f"Erro ao salvar: {str(e)}"}), 500
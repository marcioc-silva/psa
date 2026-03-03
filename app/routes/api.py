import re
from flask import Blueprint, jsonify, request
from sqlalchemy import String, cast
from app.models.material import MaterialPSA
from app import db
from app.services.kpis import calcular_kpis
from datetime import datetime
from flask_login import login_required

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/consultar/<path:codigo>')
def consultar(codigo):
    # Mantemos apenas o básico do básico do tratamento
    bruto = str(codigo).strip()
    
    # Criamos o termo de busca parcial (ex: %3761...%)
    # O sinal '%' diz ao banco: "procure qualquer coisa que contenha isso no meio"
    termo_busca = f"%{bruto.lstrip('0')}%"
    
    print(f"--- MODO BUSCA PARCIAL PSA ---")
    print(f"Recebido: '{bruto}'")
    print(f"Tentando encontrar algo que contenha: '{termo_busca}'")

    # A busca agora é tolerante à sujeira no início ou no fim do campo do banco
    material = MaterialPSA.query.filter(
        cast(MaterialPSA.unidade_deposito, String).like(termo_busca)
    ).first()

    if material:
        print(f"✅ SUCESSO: Match parcial realizado!")
        return jsonify({
            'found': True, 
            'material': material.to_dict()
        })
    
    print(f"❌ FALHA: Mesmo na busca parcial, '{bruto}' não foi encontrado.")
    return jsonify({'found': False, 'error': 'Não encontrado'}), 404

@bp.route('/confirmar', methods=['POST'])
def confirmar_conferencia_api():
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"status": "erro", "mensagem": "Dados não fornecidos"}), 400

        ud = dados.get('ud')
        sap_conferente = dados.get('conferente_id')
        bp.logger.info(f"--- SOLICITAÇÃO DE CONFERÊNCIA: {ud} ---")
        # Procura o material pela Unidade de Depósito (UD)
        material = MaterialPSA.query.filter_by(unidade_deposito=ud).first()
        
        if material:
            material.conferido = True
            material.data_conferencia = datetime.now()
            # Se adicionaste a coluna no banco, guarda o ID
            if hasattr(material, 'conferente_id'):
                material.conferente_id = sap_conferente
            
            db.session.commit()
            return jsonify({"status": "sucesso", "mensagem": "Material conferido!"}), 200
        
        return jsonify({"status": "erro", "mensagem": "Material não encontrado"}), 404

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@bp.get("/kpis")
@login_required
def kpis():
    data_filtro = request.args.get("data_filtro")
    psa_key = request.args.get("psa_key")
    k = calcular_kpis(data_filtro=data_filtro, psa_key=psa_key)
    return jsonify(k)

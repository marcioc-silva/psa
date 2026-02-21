import pandas as pd
import numpy as np
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from app.models.material import MaterialPSA
from app import db
from datetime import datetime

bp = Blueprint('importer', __name__, url_prefix='/importer')

@bp.route('/')
def index():
    # Busca apenas os materiais da última importação para não sobrecarregar a tela de upload
    materiais = MaterialPSA.query.order_by(MaterialPSA.data_importacao.desc()).limit(50).all()
    return render_template('importer/index.html', materiais=materiais)

@bp.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('importer.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('importer.index'))

    try:
        # Lendo o Excel e tratando valores nulos
        #df = pd.read_excel(file)
        # Forçamos as colunas crítdf = pd.read_excel(file, dtype={'Unidade de depósito': str, 'Material': str, 'Lote': str})icas a serem lidas como String logo de cara
        

        df = df.replace({np.nan: None})
        
        data_atual = datetime.now()

        # Função interna para limpar o ".0" de números longos (UD e Material)
        def limpar_numero(val):
            if val is None or str(val).strip() == "" or str(val).lower() == "none":
                return None
            return str(val).split('.')[0].strip()

        # --- NOVA LÓGICA DE LIMPEZA (Sincronização) ---
        # 1. Mapeamos todas as UDs que vieram no Excel novo
        uds_atuais_no_excel = []
        for _, row in df.iterrows():
            ud = limpar_numero(row.get('Unidade de depósito'))
            if ud:
                uds_atuais_no_excel.append(ud)

        # 2. EXCLUSÃO: Remove do banco tudo que NÃO está nessa lista do Excel
        # Isso garante que se o item saiu do SAP, ele sai do sistema.
        if uds_atuais_no_excel:
            MaterialPSA.query.filter(MaterialPSA.unidade_deposito.notin_(uds_atuais_no_excel)).delete(synchronize_session=False)
        # ----------------------------------------------

        count_novos = 0
        count_existentes = 0

        for _, row in df.iterrows():
            ud_codigo = limpar_numero(row.get('Unidade de depósito'))
            
            if not ud_codigo:
                continue

            # Verifica se a UD já existe
            existente = MaterialPSA.query.filter_by(unidade_deposito=ud_codigo).first()
            
            if not existente:
                # Tratamento de Data de Vencimento
                raw_venc = row.get('Data do vencimento')
                data_venc = None
                if raw_venc:
                    try:
                        data_venc = pd.to_datetime(raw_venc).date()
                    except:
                        data_venc = None

                novo_material = MaterialPSA(
                    unidade_deposito=ud_codigo,
                    cod_material=limpar_numero(row.get('Material')),
                    desc_material=str(row.get('Texto breve material') or "SEM DESCRIÇÃO"),
                    lote=limpar_numero(row.get('Lote')) or "S/L",
                    posicao_deposito=str(row.get('Posição no depósito') or ""),
                    tipo_deposito=str(row.get('Tipo de depósito') or ""),
                    quantidade_estoque=float(row.get('Estoque total', 0) or row.get('Quantidade total', 0)),
                    unidade_medida=str(row.get('UM básica', 'UN')),
                    data_vencimento=data_venc,
                    conferido=False,
                    data_importacao=data_atual
                )
                db.session.add(novo_material)
                count_novos += 1
            else:
                # Se já existe, apenas garantimos que ele continua lá (contagem para o log)
                count_existentes += 1
        
        db.session.commit()
        
        # MENSAGEM ÚNICA DE SUPERVISOR
        flash(f'Sincronização concluída! {count_novos} novos itens importados e itens ausentes removidos.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro no processamento: {str(e)}', 'danger')

    return redirect(url_for('main.dashboard'))

@bp.route('/exportar')
def exportar():
    materiais = MaterialPSA.query.all()
    # Cria lista de dicionários para o DataFrame
    data_list = []
    for m in materiais:
        data_list.append({
            'UD': m.unidade_deposito,
            'Material': m.cod_material,
            'Lote': m.lote,
            'Qtd': m.quantidade_estoque,
            'Vencimento': m.data_vencimento,
            'Status': 'Conferido' if m.conferido else 'Pendente'
        })
    
    df = pd.DataFrame(data_list)
    output_path = "relatorio_psa_aracatuba.xlsx"
    df.to_excel(output_path, index=False)
    return send_file(output_path, as_attachment=True)
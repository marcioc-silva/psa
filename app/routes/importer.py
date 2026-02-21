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
        # Forçamos as colunas críticas a serem lidas como String logo de cara
        df = pd.read_excel(file, dtype={'Unidade de depósito': str, 'Material': str, 'Lote': str})
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
                
                # CORREÇÃO: Mapeando o nome exato da coluna que vem do SAP/Excel
                # Verifique se no Excel a coluna chama 'Data do último mov.' ou 'data_ultimo_mov'
                raw_ultmov = row.get('Último movimento') or row.get('data_ultimo_mov')
                
                data_venc = None
                data_ultmov = None

                if raw_venc:
                    try:
                        data_venc = pd.to_datetime(raw_venc).date()
                    except:
                        data_venc = None

                if raw_ultmov:
                    try:
                        data_ultmov = pd.to_datetime(raw_ultmov).date()
                    except:
                        data_ultmov = None        

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
                    # CORREÇÃO: O nome do campo deve ser data_ultimo_mov (conforme seu modelo)
                    data_ultimo_mov=data_ultmov,   
                    conferido=False,
                    data_importacao=data_atual
                )
                db.session.add(novo_material)
                count_novos += 1
            else:
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
    import os
    import pandas as pd
    from flask import send_file
    from datetime import datetime

    # 1. Busca todos os registros no banco
    materiais = MaterialPSA.query.all()

    # 2. Define o caminho absoluto para evitar erro de "Arquivo não encontrado"
    # Isso garante que o arquivo seja salvo na mesma pasta deste script
    basedir = os.path.abspath(os.path.dirname(__file__))
    filename = "relatorio_psa_aracatuba.xlsx"
    output_path = os.path.join(basedir, filename)

    # 3. Monta a lista com TODOS os campos baseada no seu modelo
    data_list = []
    for m in materiais:
        data_list.append({
            "ID": m.id,
            "UD": m.unidade_deposito,
            "Material": m.cod_material,
            "Descrição": m.desc_material,
            "Lote": m.lote or "S/L",
            "Posição": m.posicao_deposito or "S/P",
            "Tipo Dep": m.tipo_deposito,
            "Qtd": m.quantidade_estoque,
            "Unidade": m.unidade_medida,
            "Vencimento": m.data_vencimento.strftime('%d/%m/%Y') if m.data_vencimento else "S/V",
            "Últ. Mov.": m.data_ultimo_mov.strftime('%d/%m/%Y') if m.data_ultimo_mov else "---",
            "Status": "CONFERIDO" if m.conferido else "PENDENTE",
            "Divergência": "SIM" if m.possui_divergencia else "NÃO",
            "Observação": m.observacao_conferente or ""
        })

    # 4. Cria o DataFrame e gera o arquivo Excel
    df = pd.DataFrame(data_list)
    df.to_excel(output_path, index=False)

    # 5. Envia o arquivo para o navegador
    return send_file(output_path, as_attachment=True)
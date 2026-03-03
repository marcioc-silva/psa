import pandas as pd
from datetime import datetime
from app import db
from app.models.material import MaterialPSA

def processar_arquivo(filepath):
    # Lê o Excel forçando a Unidade de Depósito como texto
    df = pd.read_excel(filepath, dtype={'Unidade de depósito': str})
    
    # Remove duplicatas dentro do próprio arquivo Excel para evitar erro de UniqueConstraint
    df = df.drop_duplicates(subset=['Unidade de depósito'], keep='last')
    
    novos = 0
    atualizados = 0
    data_lote = datetime.now()
    
    for _, row in df.iterrows():
        ud_texto = str(row['Unidade de depósito']).strip()
        
        # Pula linhas vazias se houver
        if not ud_texto or ud_texto.lower() == 'nan':
            continue

        # Prepara o dicionário da linha para salvar no campo JSON (dados_flexiveis)
        dados_extras = row.to_dict()
        for key, value in dados_extras.items():
            if pd.isna(value):
                dados_extras[key] = ""
            else:
                dados_extras[key] = str(value)

        # Busca se a Unidade de Depósito já existe no banco de dados
        material_existente = MaterialPSA.query.filter_by(unidade_deposito=ud_texto).first()

        if material_existente:
            # --- LÓGICA DE ATUALIZAÇÃO ---
            material_existente.dados_flexiveis = dados_extras
            material_existente.texto_breve = str(row.get('Texto breve material', material_existente.texto_breve))
            material_existente.lote = str(row.get('Lote', material_existente.lote))
            # Preservamos a data_importacao original para não perder o histórico
            atualizados += 1
        
        else:
            # --- LÓGICA DE CRIAÇÃO ---
            novo = MaterialPSA(
                unidade_deposito=ud_texto,
                material=str(row.get('Material', '')),
                texto_breve=str(row.get('Texto breve material', '')),
                lote=str(row.get('Lote', '')),
                dados_flexiveis=dados_extras,
                data_importacao=data_lote
            )
            db.session.add(novo)
            novos += 1

    try:
        db.session.commit()
        return True, f"Importação Concluída! {novos} novos itens criados. {atualizados} atualizados."
    except Exception as e:
        db.session.rollback()
        return False, f"Erro ao salvar no banco: {str(e)}"

import pandas as pd
from app import db
from app.models.material import MaterialPSA
from datetime import datetime

def processar_arquivo(filepath):
    # Lê o Excel forçando a UD como texto
    df = pd.read_excel(filepath, dtype={'Unidade de depósito': str})
    
    novos = 0
    atualizados = 0
    data_lote = datetime.now()
    for _, row in df.iterrows():
        ud_texto = str(row['Unidade de depósito']).strip()
        
        # Prepara o JSON da linha inteira
        dados_extras = row.to_dict()
        for key, value in dados_extras.items():
            if pd.isna(value):
                dados_extras[key] = ""
            else:
                dados_extras[key] = str(value)

        # Busca material existente
        material_existente = MaterialPSA.query.filter_by(unidade_deposito=ud_texto).first()

        if material_existente:
            # --- LÓGICA DE ATUALIZAÇÃO ---
            # Atualizamos os dados flexíveis (Validade, Movimento, etc.)
            material_existente.dados_flexiveis = dados_extras
            # Atualizamos campos básicos caso tenham mudado
            material_existente.texto_breve = str(row.get('Texto breve material', material_existente.texto_breve))
            material_existente.lote = str(row.get('Lote', material_existente.lote))
            
            # OBS: NÃO tocamos na 'data_importacao', preservando o histórico de dias!
            atualizados += 1
        
        else:
            # --- LÓGICA DE CRIAÇÃO ---
            novo = MaterialPSA(
                unidade_deposito=ud_texto,
                material=str(row['Material']),
                texto_breve=str(row.get('Texto breve material', '')),
                lote=str(row.get('Lote', '')),
                dados_flexiveis=dados_extras,
                data_importacao=data_lote # Data de HOJE para os novos
            )
            db.session.add(novo)
            novos += 1

    db.session.commit()
    return True, f"Importação Concluída! {novos} novos itens criados. {atualizados} itens existentes foram atualizados com novos dados."
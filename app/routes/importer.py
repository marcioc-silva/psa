import pandas as pd
import numpy as np
from flask_login import login_user, login_required, logout_user
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from app.models.material import MaterialPSA
from app import db
from datetime import datetime, timedelta, time

bp = Blueprint('importer', __name__, url_prefix='/importer')

@bp.route('/')
@login_required
def index():
    # Busca apenas os materiais da última importação para não sobrecarregar a tela de upload
    materiais = MaterialPSA.query.order_by(MaterialPSA.data_importacao.desc()).limit(50).all()
    return render_template('importer/index.html', materiais=materiais)

@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('importer.index'))

    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('importer.index'))

    try:
        df = pd.read_excel(
            file,
            dtype={'Unidade de depósito': str, 'Material': str, 'Lote': str}
        )
        df = df.replace({np.nan: None})

        data_atual = datetime.now()

        def limpar_numero(val):
            if val is None or str(val).strip() == "" or str(val).lower() == "none":
                return None
            return str(val).split('.')[0].strip()

        # -----------------------------
        # ✅ NOVO: separa sozinho por PSA
        # -----------------------------
        grupos = {}  # psa_key -> {"psa_tipo":..., "psa_posicao":..., "rows":[...], "uds":set()}
        total_linhas_validas = 0

        for _, row in df.iterrows():
            ud = limpar_numero(row.get('Unidade de depósito'))
            if not ud:
                continue

            tipo_dep = row.get('Tipo de depósito')
            pos_dep = row.get('Posição no depósito')

            psa_tipo, psa_posicao, psa_key = make_psa_fields(tipo_dep, pos_dep)
            if not psa_tipo or not psa_posicao:
                # se o excel vier sem essas colunas, melhor falhar cedo do que fazer limpeza errada
                continue

            if psa_key not in grupos:
                grupos[psa_key] = {
                    "psa_tipo": psa_tipo,
                    "psa_posicao": psa_posicao,
                    "rows": [],
                    "uds": set(),
                }

            grupos[psa_key]["rows"].append(row)
            grupos[psa_key]["uds"].add(ud)
            total_linhas_validas += 1

        if not grupos:
            flash("Arquivo não contém UDs válidas com PSA (Tipo/Posição).", "warning")
            return redirect(url_for('importer.index'))

        count_novos = 0
        count_atualizados = 0
        count_deletados = 0

        # -----------------------------
        # ✅ Processa PSA por PSA
        # -----------------------------
        for psa_key, g in grupos.items():
            psa_tipo = g["psa_tipo"]
            psa_posicao = g["psa_posicao"]
            uds_set = g["uds"]

            # 1) Carrega existentes desse PSA (somente os que estão no excel)
            existentes = (
                MaterialPSA.query
                .filter(MaterialPSA.psa_key == psa_key)
                .filter(MaterialPSA.unidade_deposito.in_(list(uds_set)))
                .all()
            )
            por_ud = {m.unidade_deposito: m for m in existentes}

            # 2) Upsert
            for row in g["rows"]:
                ud_codigo = limpar_numero(row.get('Unidade de depósito'))
                if not ud_codigo:
                    continue

                existente = por_ud.get(ud_codigo)

                # Datas
                raw_venc = row.get('Data do vencimento')
                raw_ultmov = row.get('Último movimento') or row.get('data_ultimo_mov')

                data_venc = None
                data_ultmov = None

                if raw_venc:
                    try:
                        data_venc = pd.to_datetime(raw_venc).date()
                    except Exception:
                        data_venc = None

                if raw_ultmov:
                    try:
                        data_ultmov = pd.to_datetime(raw_ultmov).date()
                    except Exception:
                        data_ultmov = None

                # Quantidade
                qtd = row.get('Estoque total', 0) or row.get('Quantidade total', 0)
                try:
                    qtd = float(qtd or 0)
                except Exception:
                    qtd = 0.0

                if not existente:
                    novo_material = MaterialPSA(
                        unidade_deposito=ud_codigo,
                        cod_material=limpar_numero(row.get('Material')),
                        desc_material=str(row.get('Texto breve material') or "SEM DESCRIÇÃO"),
                        lote=limpar_numero(row.get('Lote')) or "S/L",
                        posicao_deposito=str(row.get('Posição no depósito') or ""),
                        tipo_deposito=str(row.get('Tipo de depósito') or ""),
                        quantidade_estoque=qtd,
                        unidade_medida=str(row.get('UM básica', 'UN')),
                        data_vencimento=data_venc,
                        data_ultimo_mov=data_ultmov,
                        conferido=False,
                        data_importacao=data_atual,

                        # ✅ novos campos PSA
                        psa_tipo=psa_tipo,
                        psa_posicao=psa_posicao,
                        psa_key=psa_key,
                    )
                    db.session.add(novo_material)
                    count_novos += 1

                else:
                    # ✅ Atualiza dados vindos do SAP SEM resetar conferência/divergência
                    existente.cod_material = limpar_numero(row.get('Material'))
                    existente.desc_material = str(row.get('Texto breve material') or existente.desc_material or "SEM DESCRIÇÃO")
                    existente.lote = limpar_numero(row.get('Lote')) or existente.lote or "S/L"
                    existente.posicao_deposito = str(row.get('Posição no depósito') or existente.posicao_deposito or "")
                    existente.tipo_deposito = str(row.get('Tipo de depósito') or existente.tipo_deposito or "")
                    existente.quantidade_estoque = qtd
                    existente.unidade_medida = str(row.get('UM básica', existente.unidade_medida or 'UN'))
                    existente.data_vencimento = data_venc
                    existente.data_ultimo_mov = data_ultmov
                    existente.data_importacao = data_atual  # snapshot do “último import”

                    # ✅ mantém alinhado (caso tenha sido nulo antes)
                    existente.psa_tipo = psa_tipo
                    existente.psa_posicao = psa_posicao
                    existente.psa_key = psa_key

                    count_atualizados += 1

            db.session.flush()

            # 3) Limpeza só desse PSA
            deletados = (
                MaterialPSA.query
                .filter(MaterialPSA.psa_key == psa_key)
                .filter(~MaterialPSA.unidade_deposito.in_(list(uds_set)))
                .delete(synchronize_session=False)
            )
            count_deletados += int(deletados or 0)

            db.session.commit()

        flash(
            f"Import concluído! PSAs: {len(grupos)} | Novos: {count_novos} | Atualizados: {count_atualizados} | Removidos: {count_deletados}",
            "success"
        )

    except Exception as e:
        db.session.rollback()
        flash(f'Erro no processamento: {str(e)}', 'danger')

    return redirect(url_for('main.dashboard'))

@bp.route('/exportar')
@login_required
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

    def _norm_posicao(v):
        return (v or "").strip().upper()
    
    def _norm_tipo(v):
        s = str(v).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s
    
    def make_psa_key(tipo, posicao):
        t = _norm_tipo(tipo)
        p = _norm_posicao(posicao)
        return t, p, f"{t}:{p}"

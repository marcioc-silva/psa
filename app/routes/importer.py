import os
import re
from datetime import datetime, time, date

import numpy as np
import pandas as pd
from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models.material import MaterialPSA
from app.services.scoping import scoped_material_query


bp = Blueprint('importer', __name__, url_prefix='/importer')


def limpar_numero(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == 'none':
        return None
    return s.split('.')[0].strip()


def parse_float(val, default=0.0):
    if val is None:
        return float(default)
    try:
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return float(default)
            s = s.replace('.', '').replace(',', '.')
            return float(s)
        return float(val)
    except Exception:
        return float(default)


def parse_date(val):
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.date()
    except Exception:
        return None


def data_importacao_from_filename(filename: str):
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', filename or '')
    if not m:
        return None
    dd, mm, yyyy = map(int, m.groups())
    try:
        return datetime(yyyy, mm, dd, 0, 0, 0)
    except ValueError:
        return None


@bp.route('/')
@login_required
def index():
    materiais = scoped_material_query().order_by(MaterialPSA.data_importacao.desc()).limit(50).all()
    return render_template('importer/index.html', materiais=materiais)


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('importer.index'))

    file = request.files['file']
    if not file or file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('importer.index'))

    try:
        df = pd.read_excel(
            file,
            dtype={'Unidade de depósito': str, 'Material': str, 'Lote': str},
        ).replace({np.nan: None})

        # Data de importação padronizada (00:00) e, se possível, pelo nome do arquivo
        data_base = data_importacao_from_filename(file.filename) or datetime.now()
        data_importacao = datetime.combine(data_base.date(), time.min)

        # UDs no excel
        uds_excel = []
        for _, row in df.iterrows():
            ud = limpar_numero(row.get('Unidade de depósito'))
            if ud:
                uds_excel.append(ud)

        # Sincronização por usuário: remove do banco apenas o que é desse usuário
        if uds_excel:
            scoped_material_query().filter(MaterialPSA.unidade_deposito.notin_(uds_excel)).delete(synchronize_session=False)

        novos = 0
        atualizados = 0
        ignorados = 0

        for _, row in df.iterrows():
            ud = limpar_numero(row.get('Unidade de depósito'))
            if not ud:
                ignorados += 1
                continue

            cod_material = limpar_numero(row.get('Material'))
            desc = str(row.get('Texto breve material') or 'SEM DESCRIÇÃO')
            lote = limpar_numero(row.get('Lote')) or 'S/L'
            pos = str(row.get('Posição no depósito') or '')
            tipo = str(row.get('Tipo de depósito') or '')
            um = str(row.get('UM básica') or 'UN')

            qtd = parse_float(
                row.get('Estoque total', None)
                if row.get('Estoque total', None) is not None
                else row.get('Quantidade total', 0),
                default=0.0,
            )

            data_venc = parse_date(row.get('Data do vencimento'))
            raw_ultmov = row.get('Último movimento') or row.get('data_ultimo_mov')
            data_ultmov = parse_date(raw_ultmov)

            existente = scoped_material_query().filter_by(unidade_deposito=ud).first()
            if not existente:
                db.session.add(
                    MaterialPSA(
                        user_id=current_user.id,
                        unidade_deposito=ud,
                        cod_material=cod_material,
                        desc_material=desc,
                        lote=lote,
                        posicao_deposito=pos,
                        tipo_deposito=tipo,
                        quantidade_estoque=qtd,
                        unidade_medida=um,
                        data_vencimento=data_venc,
                        data_ultimo_mov=data_ultmov,
                        conferido=False,
                        data_importacao=data_importacao,
                    )
                )
                novos += 1
            else:
                existente.cod_material = cod_material
                existente.desc_material = desc
                existente.lote = lote
                existente.posicao_deposito = pos
                existente.tipo_deposito = tipo
                existente.quantidade_estoque = qtd
                existente.unidade_medida = um
                existente.data_vencimento = data_venc
                existente.data_ultimo_mov = data_ultmov
                existente.data_importacao = data_importacao
                atualizados += 1

        db.session.commit()
        flash(
            f"Importação concluída ({data_importacao.strftime('%d/%m/%Y')}) — {novos} novos, {atualizados} atualizados, {ignorados} ignorados. Itens ausentes removidos (sincronização).",
            'success',
        )

    except Exception as e:
        db.session.rollback()
        flash(f'Erro no processamento: {str(e)}', 'danger')

    return redirect(url_for('main.dashboard'))


@bp.route('/exportar')
@login_required
def exportar():
    materiais = scoped_material_query().all()

    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'uploads'))
    os.makedirs(uploads_dir, exist_ok=True)

    filename = f"relatorio_psa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = os.path.join(uploads_dir, filename)

    data_list = []
    for m in materiais:
        data_list.append(
            {
                'UD': m.unidade_deposito,
                'Material': m.cod_material,
                'Descrição': m.desc_material,
                'Lote': m.lote or 'S/L',
                'Posição': m.posicao_deposito or 'S/P',
                'Tipo Dep': m.tipo_deposito or '',
                'Qtd': m.quantidade_estoque,
                'Unidade': m.unidade_medida,
                'Vencimento': m.data_vencimento.strftime('%d/%m/%Y') if m.data_vencimento else 'S/V',
                'Últ. Mov.': m.data_ultimo_mov.strftime('%d/%m/%Y') if m.data_ultimo_mov else '---',
                'Data Importação': m.data_importacao.strftime('%d/%m/%Y %H:%M:%S') if m.data_importacao else '---',
                'Status': 'CONFERIDO' if m.conferido else 'PENDENTE',
                'Divergência': 'SIM' if m.possui_divergencia else 'NÃO',
                'Observação': m.observacao_conferente or '',
            }
        )

    pd.DataFrame(data_list).to_excel(output_path, index=False)
    return send_file(output_path, as_attachment=True)

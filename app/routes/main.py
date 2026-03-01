from datetime import datetime, timedelta, time

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user
from sqlalchemy import String, cast

from app import db
from app.models.material import MaterialPSA, Usuario

bp = Blueprint('main', __name__)

def date_to_dt(d):
    """Aceita date/datetime/None e devolve datetime (00:00 do dia)."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    # se for date
    return datetime.combine(d, time.min)
# =========================
# DASHBOARD
# =========================
@bp.route('/')
@login_required
def dashboard():
    todos_materiais = MaterialPSA.query.order_by(
        MaterialPSA.data_importacao.desc()
    ).all()

    datas_unicas = {
        m.data_importacao.strftime('%d/%m/%Y')
        for m in todos_materiais
        if m.data_importacao
    }

    datas_formatadas = sorted(list(datas_unicas), reverse=True)

    data_filtro = request.args.get('data_filtro')

    if data_filtro:
        materiais_exibidos = [
            m for m in todos_materiais
            if m.data_importacao and
               m.data_importacao.strftime('%d/%m/%Y') == data_filtro
        ]
    else:
        materiais_exibidos = todos_materiais

    total_itens = len(materiais_exibidos)
    conferidos = sum(1 for m in materiais_exibidos if m.conferido)
    pendentes = total_itens - conferidos

    itens_com_divergencia = sum(
        1 for m in materiais_exibidos
        if getattr(m, 'possui_divergencia', False)
    )    
    
    limite_critico = datetime.now() - timedelta(hours=48)

    itens_criticos = sum(
        1 for m in materiais_exibidos
        if (not m.conferido)
        and (date_to_dt(m.data_importacao) is not None)
        and (date_to_dt(m.data_importacao) <= limite_critico)
    )
    taxa_qualidade = round(
        ((conferidos - itens_com_divergencia) / conferidos * 100), 1
    ) if conferidos > 0 else 100.0

    acuracidade = round(
        (conferidos / total_itens * 100), 1
    ) if total_itens > 0 else 0.0

    return render_template(
        'index.html',
        datas=datas_formatadas,
        data_atual=data_filtro,
        total=total_itens,
        conferidos=conferidos,
        pendentes=pendentes,
        acuracidade=acuracidade,
        taxa_qualidade=taxa_qualidade,
        itens_com_divergencia=itens_com_divergencia,
        total_retencao=itens_criticos,
        materiais=materiais_exibidos
    )


# =========================
# DETALHES UD (Scanner)
# =========================
@bp.route('/get_detalhes_ud/<string:ud_numero>')
@login_required
def get_detalhes_ud(ud_numero):

    termo = str(ud_numero).strip()

    # 1️⃣ Tentativa EXATA (mais segura para conferência)
    ud_obj = MaterialPSA.query.filter(
        cast(MaterialPSA.unidade_deposito, String) == termo
    ).first()

    # 2️⃣ Fallback tolerante (caso QR venha com prefixo/sufixo)
    if not ud_obj:
        ud_obj = MaterialPSA.query.filter(
            cast(MaterialPSA.unidade_deposito, String).ilike(f"%{termo}%")
        ).first()

    if not ud_obj:
        return jsonify({'error': 'Não encontrado'}), 404

    return jsonify({
        'id': ud_obj.id,
        'ud': str(ud_obj.unidade_deposito).strip(),
        'material_sap': str(
            getattr(ud_obj, 'material',
            getattr(ud_obj, 'cod_material', 'S/C'))
        ).split('.')[0],
        'descricao': getattr(
            ud_obj,
            'texto_breve',
            getattr(ud_obj, 'desc_material', 'S/D')
        ),
        'qtd': f"{float(getattr(
            ud_obj,
            'quantidade',
            getattr(ud_obj, 'quantidade_estoque', 0)
        )):.0f}",
        'lote': ud_obj.lote or "S/L",
        'vencimento': ud_obj.data_vencimento.strftime('%d/%m/%Y')
            if ud_obj.data_vencimento else "S/V",
        'ult_mov': ud_obj.data_ultimo_mov.strftime('%d/%m/%Y')
            if ud_obj.data_ultimo_mov else "---",
        'conferido': ud_obj.conferido,
        'status': "CONFERIDO" if ud_obj.conferido else "PENDENTE"
    })


# =========================
# CONFIRMAR LEITURA
# =========================
@bp.route('/api/confirmar', methods=['POST'])
@login_required
def confirmar_leitura():

    data = request.get_json()
    material = db.session.get(MaterialPSA, data.get('id'))

    if not material:
        return jsonify({'success': False, 'message': 'Material não encontrado'})

    try:
        material.conferido = True
        material.data_conferencia = datetime.utcnow()

        if hasattr(material, 'possui_divergencia'):
            material.possui_divergencia = data.get('possui_divergencia', False)
            material.observacao_conferente = data.get('observacao', '')

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# =========================
# BUSCA MANUAL (Robusta)
# =========================
@bp.route('/api/search_manual')
@login_required
def search_manual():

    termo = (request.args.get('q') or '').strip()

    if len(termo) < 3:
        return jsonify([])

    resultados = MaterialPSA.query.filter(
        cast(MaterialPSA.unidade_deposito, String).ilike(f"%{termo}%"),
        MaterialPSA.conferido.is_(False)
    ).limit(10).all()

    return jsonify([{
        'ud': str(m.unidade_deposito).strip(),
        'material': getattr(
            m,
            'cod_material',
            getattr(m, 'material', 'S/C')
        ),
        'texto': getattr(
            m,
            'desc_material',
            getattr(m, 'texto_breve', 'S/D')
        )
    } for m in resultados])


# =========================
# SCANNER PAGE
# =========================
@bp.route('/api/scanner')
@login_required
def scanner_page():
    return render_template('scanner.html')


# =========================
# LOGIN / LOGOUT
# =========================
@bp.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        sap = request.form.get('sap')
        senha = request.form.get('password')

        usuario = Usuario.query.filter_by(sap=sap).first()

        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))

        flash('SAP ou senha incorretos.', 'danger')

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


# =========================
# REGISTRAR
# =========================
@bp.route('/registrar', methods=['GET', 'POST'])
def registrar():
    return render_template('registrar.html')

@bp.route('/relatorio_divergencias')
@login_required
def relatorio_divergencias():
    # Filtra onde a quantidade_estoque é diferente da quantidade_contada
    # Ajuste os nomes dos campos conforme seu modelo no SQLAlchemy
    divergencias = MaterialPSA.query.filter(MaterialPSA.possui_divergencia == True).all()
    
    return render_template('relatorio_lista.html', materiais=divergencias)

from flask import session
from app.services.queries import scoped_material_query

@bp.route("/pendentes")
@login_required
def pendentes():
    data_filtro = session.get("data_filtro")
    query = scoped_material_query(db.session, data_filtro)
    materiais = query.filter(MaterialPSA.conferido == False).all()
    return render_template("pendentes.html", materiais=materiais)

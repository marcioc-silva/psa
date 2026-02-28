from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from app.models.material import Usuario
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from app.models.material import MaterialPSA
from app import db
from datetime import datetime, timedelta
from sqlalchemy import String, cast
bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def dashboard():
    # 1. PEGAR TUDO DO BANCO (Ordenado pela importação mais recente)
    todos_materiais = MaterialPSA.query.order_by(MaterialPSA.data_importacao.desc()).all()

    # 2. AGRUPAR DATAS PARA O MENU (Tratando milissegundos e nulos)
    datas_unicas = set()
    for m in todos_materiais:
        if m.data_importacao:
            datas_unicas.add(m.data_importacao.strftime('%d/%m/%Y'))
    
    datas_formatadas = sorted(list(datas_unicas), reverse=True)

    # 3. FILTRAR DADOS POR DATA (Sincronizado com o select do index.html)
    data_filtro = request.args.get('data_filtro')
    if data_filtro:
        materiais_exibidos = [m for m in todos_materiais if m.data_importacao and m.data_importacao.strftime('%d/%m/%Y') == data_filtro]
    else:
        materiais_exibidos = todos_materiais

    # 4. CÁLCULOS DE KPI (Nomes de variáveis idênticos aos do index.html)
    total_itens = len(materiais_exibidos)
    conferidos = sum(1 for m in materiais_exibidos if m.conferido)
    pendentes = total_itens - conferidos
    
    # KPIs de Qualidade e Retenção
    itens_com_divergencia = sum(1 for m in materiais_exibidos if getattr(m, 'possui_divergencia', False))
    
    # Limite Crítico (48 horas para o card de Retenção)
    limite_critico = datetime.now() - timedelta(hours=48)
    itens_criticos = sum(1 for m in materiais_exibidos if not m.conferido and m.data_importacao and m.data_importacao <= limite_critico)

    # Cálculo das Percentagens (Proteção contra divisão por zero)
    taxa_qualidade = round(((conferidos - itens_com_divergencia) / conferidos * 100), 1) if conferidos > 0 else 100.0
    acuracidade = round((conferidos / total_itens * 100), 1) if total_itens > 0 else 0.0
    
    # 5. RETORNO PARA O INDEX.HTML
    return render_template('index.html',
                           datas=datas_formatadas, 
                           data_atual=data_filtro,
                           total=total_itens,
                           conferidos=conferidos,
                           pendentes=pendentes,
                           acuracidade=acuracidade,
                           taxa_qualidade=taxa_qualidade,
                           itens_com_divergencia=itens_com_divergencia,
                           total_retencao=itens_criticos, # Nome esperado pelo index.html
                           materiais=materiais_exibidos)

@bp.route('/get_detalhes_ud/<string:ud_numero>')
def get_detalhes_ud(ud_numero):
    # POKA-YOKE: Limpeza total do dado recebido
    termo = str(ud_numero).strip()
    
    print(f"\n[COMPARAR PSA] Buscando UD: '{termo}'", flush=True)

    # O SEGREDO: Cast para String garante que a comparação funcione no Render/Postgres
    # Mesmo que a UD seja um número no banco, o LIKE vai funcionar agora
    ud_obj = MaterialPSA.query.filter(
        cast(MaterialPSA.unidade_deposito, String).like(f"%{termo}%")
    ).first()
    
    if not ud_obj:
        print(f"[COMPARAR PSA] Erro: UD '{termo}' não encontrada no banco.", flush=True)
        return jsonify({'error': 'Não encontrado'}), 404
    
    print(f"[COMPARAR PSA] Sucesso: Localizada UD {ud_obj.unidade_deposito}", flush=True)

    # Retorno unificado conforme seu padrão Nestlé
    return jsonify({
        'id': ud_obj.id,
        'ud': ud_obj.unidade_deposito,
        'material_sap': str(getattr(ud_obj, 'material', getattr(ud_obj, 'cod_material', 'S/C'))).split('.')[0],
        'descricao': getattr(ud_obj, 'texto_breve', getattr(ud_obj, 'desc_material', 'S/D')),
        'qtd': f"{float(getattr(ud_obj, 'quantidade', getattr(ud_obj, 'quantidade_estoque', 0))):.0f}",
        'lote': ud_obj.lote or "S/L",
        'vencimento': ud_obj.data_vencimento.strftime('%d/%m/%Y') if ud_obj.data_vencimento else "S/V",
        'ult_mov': ud_obj.data_ultimo_mov.strftime('%d/%m/%Y') if ud_obj.data_ultimo_mov else "---",
        'conferido': ud_obj.conferido,
        'status': "CONFERIDO" if ud_obj.conferido else "PENDENTE"
    })

@bp.route('/api/confirmar', methods=['POST'])
def confirmar_leitura():
    data = request.get_json()
    material = MaterialPSA.query.get(data.get('id'))
    
    if material:
        try:
            material.conferido = True
            material.data_conferencia = datetime.utcnow()
            
            # Grava divergências se as colunas existirem
            if hasattr(material, 'possui_divergencia'):
                material.possui_divergencia = data.get('possui_divergencia', False)
                material.observacao_conferente = data.get('observacao', '')
            
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    
    return jsonify({'success': False, 'message': 'Material não encontrado'})

@bp.route('/search_manual', methods=['GET'])
@login_required
def search_manual():
    try:
        termo = request.args.get('q', '').strip()
        if not termo or len(termo) < 3:
            return jsonify([])

        resultados = MaterialPSA.query.filter(
            MaterialPSA.unidade_deposito.contains(termo),
            MaterialPSA.conferido == False
        ).limit(10).all()

        # Usamos getattr para garantir compatibilidade caso as colunas mudem de nome
        return jsonify([{
            'ud': m.unidade_deposito, 
            'material': getattr(m, 'cod_material', getattr(m, 'material', 'S/C')), 
            'texto': getattr(m, 'desc_material', getattr(m, 'texto_breve', 'S/D'))
        } for m in resultados])
    except Exception as e:
        print(f"Erro na busca manual: {e}")
        return jsonify([]), 500

@bp.route('/scanner')
@login_required
def scanner_page():
    return render_template('scanner.html')

@bp.route('/relatorios/divergencias')
@login_required
def relatorio_divergencias():
    # Pega a data que vem do clique no card
    data_filtro = request.args.get('data_filtro')
    
    # Tratamento para string 'None' ou vazia
    if data_filtro == 'None' or not data_filtro:
        data_filtro = None
        
    # Busca materiais que possuem a marcação de divergência
    query = MaterialPSA.query.filter_by(possui_divergencia=True)
    
    if data_filtro:
        # Filtra pela data de importação formatada
        todos_erros = query.all()
        materiais_filtrados = [m for m in todos_erros if m.data_importacao and m.data_importacao.strftime('%d/%m/%Y') == data_filtro]
    else:
        # Mostra os erros mais recentes de conferência
        materiais_filtrados = query.order_by(MaterialPSA.data_conferencia.desc()).all()
        
    return render_template('relatorio_lista.html', materiais=materiais_filtrados, data_atual=data_filtro)

@bp.route('/resetar-testes')
@login_required
def resetar_testes():
    try:
        db.session.query(MaterialPSA).update({MaterialPSA.conferido: False, MaterialPSA.data_conferencia: None})
        db.session.commit()
        flash('Base resetada com sucesso.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        sap = request.form.get('sap')
        senha = request.form.get('password')       

        # Busca o usuário pelo SAP
        usuario = Usuario.query.filter_by(sap=sap).first()
        
        # Verifica se o usuário existe e se a senha está correta
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('main.dashboard')) # Mude 'index' para sua página principal
        else:
            flash('SAP ou senha incorretos. Tente novamente.', 'danger')

        print(f'Senha',sap)
        print(f'Senha',senha)
        print(f'Usuário',usuario)
           
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/conferencia')
@login_required # Isso impede o acesso de quem não logou
def conferencia():
    return render_template('conferencia.html', nome=current_user.nome_completo)

@bp.route('/registrar', methods=['GET', 'POST'])
def registrar():
    return render_template('registrar.html')

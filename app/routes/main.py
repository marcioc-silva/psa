from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from app.models.material import MaterialPSA
from app import db
from datetime import datetime, timedelta

bp = Blueprint('main', __name__)

@bp.route('/')
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
    termo = str(ud_numero).strip()
    ud_obj = MaterialPSA.query.filter(MaterialPSA.unidade_deposito.like(f"%{termo}%")).first()
    
    if not ud_obj:
        return jsonify({'error': 'Não encontrado'}), 404
    
    # Pegamos os dados reais do objeto no banco
    # Usamos getattr para garantir que funcione independente do nome da coluna (material ou cod_material)
    return jsonify({
        'id': ud_obj.id,
        'ud': ud_obj.unidade_deposito,
        'material_sap': str(getattr(ud_obj, 'material', getattr(ud_obj, 'cod_material', 'S/C'))).split('.')[0],
        
        # AQUI ESTÁ O SEGREDO: Mapear para os nomes que o base.html espera
        'descricao': getattr(ud_obj, 'texto_breve', getattr(ud_obj, 'desc_material', 'S/D')), # Modal espera .descricao
        'qtd': f"{float(getattr(ud_obj, 'quantidade', getattr(ud_obj, 'quantidade_estoque', 0))):.0f}", # Modal espera .qtd
        
        'lote': ud_obj.lote or "S/L",
        'validade': ud_obj.validade.strftime('%d/%m/%Y') if hasattr(ud_obj, 'validade') and ud_obj.validade else "S/V",
        'data_import': ud_obj.data_importacao.strftime('%d/%m/%Y') if ud_obj.data_importacao else "---",
        'ult_mov': getattr(ud_obj, 'ultimo_movimento', '---'),
        'conferido': ud_obj.conferido
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
def scanner_page():
    return render_template('scanner.html')

@bp.route('/relatorios/divergencias')
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
def resetar_testes():
    try:
        db.session.query(MaterialPSA).update({MaterialPSA.conferido: False, MaterialPSA.data_conferencia: None})
        db.session.commit()
        flash('Base resetada com sucesso.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('main.dashboard'))
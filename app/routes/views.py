from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
def index():
    # Esta será a tela principal com os cards de cada sistema
    return render_template('portal.html')

@views_bp.route('/qualidade')
def modulo_qualidade():
    # Espaço reservado para um futuro sistema de Qualidade
    return render_template('em_desenvolvimento.html', sistema="Gestão da Qualidade")

from app.models.material import MaterialPSA

# ... outras rotas (index, dashboard_psa) ...



# Certifique-se que a função dashboard_psa está enviando as variáveis
@views_bp.route('/psa')
def dashboard_psa():
    from app.models.material import MaterialPSA
    total = MaterialPSA.query.count()
    pendentes = MaterialPSA.query.filter_by(conferido=False).count()
    return render_template('dashboard_psa.html', total=total, pendentes=pendentes)
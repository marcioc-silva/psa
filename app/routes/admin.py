from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.models.configuracao import ConfiguracaoSistema
from app.services.authz import admin_required


bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/config', methods=['GET', 'POST'])
@login_required
@admin_required
def config():
    cfg = ConfiguracaoSistema.get_singleton()

    if request.method == 'POST':
        email = (request.form.get('email_gerente') or '').strip()
        cfg.email_gerente = email or None
        flash('Configurações salvas com sucesso.', 'success')
        return redirect(url_for('admin.config'))

    return render_template('admin/config.html', cfg=cfg)

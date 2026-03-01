from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models.configuracao import ConfiguracaoSistema, EmailDestinatario
from app.services.authz import admin_required


bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/config', methods=['GET', 'POST'])
@login_required
@admin_required
def config():
    cfg = ConfiguracaoSistema.get_singleton()

    if request.method != 'POST':
        destinatarios = EmailDestinatario.query.order_by(
            EmailDestinatario.ativo.desc(),
            EmailDestinatario.email.asc()
        ).all()
        return render_template('admin/config.html', cfg=cfg, destinatarios=destinatarios)

    # POST começa aqui
    acao = request.form.get('acao')

    if acao == 'salvar_config':
        print(">>> salvar_config acionado", flush=True)
        print(">>> form:", dict(request.form), flush=True)
        try:
            cfg.email_remetente = (request.form.get('email_remetente') or '').strip() or None

            nome_rem = (request.form.get('nome_remetente') or '').strip() or None
            if hasattr(cfg, 'nome_remetente'):
                cfg.nome_remetente = nome_rem

            cfg.smtp_host = (request.form.get('smtp_host') or '').strip() or None

            smtp_port = (request.form.get('smtp_port') or '').strip()
            cfg.smtp_port = int(smtp_port) if smtp_port.isdigit() else None

            cfg.smtp_usuario = (request.form.get('smtp_usuario') or '').strip() or None

            senha = (request.form.get('smtp_senha') or '').strip()
            if senha:
                cfg.smtp_senha = senha

            cfg.smtp_tls = 'smtp_tls' in request.form
            cfg.smtp_ssl = 'smtp_ssl' in request.form

            cfg.assunto_padrao = (request.form.get('assunto_padrao') or '').strip() or None

            db.session.commit()
            flash('Configuração de e-mail salva com sucesso!', 'success')

        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Falha ao salvar configuração: {e}', 'danger')

        return redirect(url_for('admin.config'))

        if acao == 'add_destinatario':
            email = (request.form.get('dest_email') or '').strip().lower()
            nome = (request.form.get('dest_nome') or '').strip() or None
            if not email or '@' not in email:
                flash('Informe um e-mail válido para o destinatário.', 'warning')
                return redirect(url_for('admin.config'))

            existente = EmailDestinatario.query.filter_by(email=email).first()
            if existente:
                existente.ativo = True
                if nome:
                    existente.nome = nome
            else:
                db.session.add(EmailDestinatario(email=email, nome=nome, ativo=True))
            db.session.commit()
            flash('Destinatário adicionado!', 'success')
            return redirect(url_for('admin.config'))

        if acao == 'remover_destinatario':
            dest_id = request.form.get('dest_id')
            dest = EmailDestinatario.query.get(dest_id) if dest_id else None
            if dest:
                dest.ativo = False
                db.session.commit()
                flash('Destinatário removido.', 'success')
            return redirect(url_for('admin.config'))

    destinatarios = EmailDestinatario.query.order_by(EmailDestinatario.ativo.desc(), EmailDestinatario.email.asc()).all()
    return render_template('admin/config.html', cfg=cfg, destinatarios=destinatarios)

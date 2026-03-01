from __future__ import annotations

from datetime import datetime

from flask import url_for

from app import db
from app.models.configuracao import ConfiguracaoSistema, EmailDestinatario
from app.models.material import MaterialPSA
from app.services.kpis import calcular_kpis
from app.services.mailer import send_email


def _fmt_data(d: datetime | None) -> str:
    if not d:
        return "---"
    return d.strftime("%d/%m/%Y")


def _fmt_dt(d: datetime | None) -> str:
    if not d:
        return "---"
    return d.strftime("%d/%m/%Y %H:%M")


def montar_reporte_html(*, data_filtro: str | None = None) -> tuple[str, str]:
    """Retorna (assunto, html_body)."""
    cfg = ConfiguracaoSistema.get_singleton()
    assunto = (cfg.assunto_padrao or "Reporte PSA - Nestlé Araçatuba").strip()

    k = calcular_kpis(data_filtro)

    q = MaterialPSA.query
    if data_filtro:
        q = q.filter(MaterialPSA.data_importacao == data_filtro)
        assunto = f"{assunto} | Importação {data_filtro}"

    divergencias = (
        q.filter(MaterialPSA.possui_divergencia.is_(True))
        .order_by(MaterialPSA.data_conferencia.desc().nullslast(), MaterialPSA.data_importacao.desc().nullslast())
        .limit(30)
        .all()
    )

    # links úteis
    try:
        link_dashboard = url_for('main.dashboard', _external=True, data_filtro=data_filtro) if data_filtro else url_for('main.dashboard', _external=True)
        link_div = url_for('reports.relatorio_divergencias', _external=True, data_filtro=data_filtro) if data_filtro else url_for('reports.relatorio_divergencias', _external=True)
    except Exception:
        # em caso de chamada fora de request context
        link_dashboard = ""
        link_div = ""

    html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif; background:#f6f7f8; padding:20px;">
      <div style="max-width:900px; margin:0 auto; background:#ffffff; border-radius:14px; overflow:hidden; box-shadow:0 6px 18px rgba(0,0,0,.08)">
        <div style="background:#212529; color:#fff; padding:18px 20px;">
          <div style="font-size:18px; font-weight:700;">Reporte PSA</div>
          <div style="font-size:12px; opacity:.85;">Nestlé Araçatuba • Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
        </div>

        <div style="padding:18px 20px;">
          <div style="display:flex; flex-wrap:wrap; gap:10px;">
            <div style="flex:1; min-width:160px; border:1px solid #eee; border-radius:12px; padding:12px;">
              <div style="font-size:11px; color:#666; letter-spacing:.08em; text-transform:uppercase;">Total</div>
              <div style="font-size:22px; font-weight:700;">{k['total']}</div>
            </div>
            <div style="flex:1; min-width:160px; border:1px solid #eee; border-radius:12px; padding:12px;">
              <div style="font-size:11px; color:#666; letter-spacing:.08em; text-transform:uppercase;">Conferidos</div>
              <div style="font-size:22px; font-weight:700;">{k['conferidos']}</div>
            </div>
            <div style="flex:1; min-width:160px; border:1px solid #eee; border-radius:12px; padding:12px;">
              <div style="font-size:11px; color:#666; letter-spacing:.08em; text-transform:uppercase;">Pendentes</div>
              <div style="font-size:22px; font-weight:700;">{k['pendentes']}</div>
            </div>
            <div style="flex:1; min-width:160px; border:1px solid #eee; border-radius:12px; padding:12px;">
              <div style="font-size:11px; color:#666; letter-spacing:.08em; text-transform:uppercase;">Qualidade</div>
              <div style="font-size:22px; font-weight:700;">{k['taxa_qualidade']}%</div>
            </div>
          </div>

          <div style="margin-top:16px; display:flex; gap:10px; flex-wrap:wrap;">
            {f'<a href="{link_dashboard}" style="background:#0056b3;color:#fff;text-decoration:none;padding:10px 12px;border-radius:10px;font-weight:700;font-size:12px;">Abrir Dashboard</a>' if link_dashboard else ''}
            {f'<a href="{link_div}" style="background:#D51C29;color:#fff;text-decoration:none;padding:10px 12px;border-radius:10px;font-weight:700;font-size:12px;">Ver Divergências</a>' if link_div else ''}
          </div>

          <h3 style="margin:18px 0 10px; font-size:16px;">Divergências recentes (até 30)</h3>
          <div style="border:1px solid #eee; border-radius:12px; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:12px;">
              <thead>
                <tr style="background:#212529; color:#fff;">
                  <th style="text-align:left; padding:10px;">UD</th>
                  <th style="text-align:left; padding:10px;">Material</th>
                  <th style="text-align:left; padding:10px;">Lote</th>
                  <th style="text-align:right; padding:10px;">Qtd</th>
                  <th style="text-align:left; padding:10px;">Venc.</th>
                  <th style="text-align:left; padding:10px;">Conferência</th>
                </tr>
              </thead>
              <tbody>
    """

    if divergencias:
        for m in divergencias:
            html += f"""
                <tr style="border-top:1px solid #eee;">
                  <td style="padding:10px; font-family:Consolas,monospace; font-weight:700; color:#0056b3;">{m.unidade_deposito}</td>
                  <td style="padding:10px;">{(m.desc_material or '')[:60]}</td>
                  <td style="padding:10px;">{m.lote or 'S/L'}</td>
                  <td style="padding:10px; text-align:right; font-weight:700;">{int(m.quantidade_estoque or 0)}</td>
                  <td style="padding:10px; color:#D51C29; font-weight:700;">{_fmt_data(m.data_vencimento)}</td>
                  <td style="padding:10px;">{_fmt_dt(m.data_conferencia)}</td>
                </tr>
            """
    else:
        html += """<tr><td colspan="6" style="padding:12px; text-align:center; color:#666;">Sem divergências registradas para o filtro atual.</td></tr>"""

    html += """
              </tbody>
            </table>
          </div>

          <div style="margin-top:14px; font-size:12px; color:#666;">
            <div><b>Acuracidade:</b> {ac}% • <b>Retenção:</b> {ret} semanas</div>
          </div>
        </div>

        <div style="background:#f6f7f8; padding:12px 20px; font-size:11px; color:#666;">
          Este e-mail foi gerado automaticamente pelo Controle PSA.
        </div>
      </div>
    </div>
    """.format(ac=k['acuracidade'], ret=k['total_retencao'])

    return assunto, html


def enviar_reporte_por_email(*, data_filtro: str | None = None) -> tuple[bool, str]:
    """Envia o reporte. Retorna (ok, mensagem)."""
    cfg = ConfiguracaoSistema.get_singleton()

    # validação mínima
    if not cfg.email_remetente:
        return False, "Configure o e-mail do remetente (Admin > Configurações)."
    if not cfg.smtp_host or not cfg.smtp_port:
        return False, "Configure servidor/porta SMTP (Admin > Configurações)."

    destinatarios = [d.email for d in EmailDestinatario.query.filter_by(ativo=True).all()]
    if not destinatarios:
        return False, "Cadastre pelo menos 1 destinatário (Admin > Configurações)."

    assunto, html = montar_reporte_html(data_filtro=data_filtro)

    try:
        send_email(
            smtp_host=cfg.smtp_host,
            smtp_port=int(cfg.smtp_port),
            smtp_usuario=cfg.smtp_usuario,
            smtp_senha=cfg.smtp_senha,
            use_tls=bool(cfg.smtp_tls),
            use_ssl=bool(cfg.smtp_ssl),
            sender_email=cfg.email_remetente,
            sender_name=cfg.nome_remetente,
            to_emails=destinatarios,
            subject=assunto,
            html_body=html,
        )
        return True, f"Reporte enviado para: {', '.join(destinatarios)}"
    except Exception as e:
        db.session.rollback()
        return False, f"Falha ao enviar e-mail: {e}"

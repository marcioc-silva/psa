from __future__ import annotations

from datetime import datetime

from flask import url_for
from sqlalchemy import func

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
    assunto_base = (cfg.assunto_padrao or "Reporte PSA - Nestlé Araçatuba").strip()

    # KPIs
    k = calcular_kpis(data_filtro=data_filtro)

    # Query base (respeita filtro de data)
    q = MaterialPSA.query
    if data_filtro:
        dt = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(str(data_filtro), fmt).date()
                break
            except ValueError:
                continue
        if dt:
            q = q.filter(func.date(MaterialPSA.data_importacao) == dt)
        assunto = f"{assunto_base} | Importação {data_filtro}"
    else:
        assunto = assunto_base

    # Divergências recentes (tabela)
    divergencias = (
        q.filter(MaterialPSA.possui_divergencia.is_(True))
        .order_by(MaterialPSA.data_conferencia.desc().nullslast(), MaterialPSA.data_importacao.desc().nullslast())
        .limit(30)
        .all()
    )

    # Top PSAs com pendência (gestão)
    top_psa_pend = (
        q.filter(MaterialPSA.conferido.is_(False))
        .with_entities(MaterialPSA.psa_key, func.count(MaterialPSA.id).label("qtd"))
        .filter(MaterialPSA.psa_key.isnot(None))
        .group_by(MaterialPSA.psa_key)
        .order_by(func.count(MaterialPSA.id).desc())
        .limit(5)
        .all()
    )

    # Top materiais com divergência (gestão)
    top_mat_div = (
        q.filter(MaterialPSA.possui_divergencia.is_(True))
        .with_entities(MaterialPSA.desc_material, func.count(MaterialPSA.id).label("qtd"))
        .group_by(MaterialPSA.desc_material)
        .order_by(func.count(MaterialPSA.id).desc())
        .limit(5)
        .all()
    )


    try:
        link_preview = url_for(
            "reports.preview_reporte",
            _external=True,
            data_filtro=data_filtro
        ) if data_filtro else url_for("reports.preview_reporte", _external=True)
    
    except Exception:
        link_preview = ""
    
    # Links úteis (fallbacks seguros)
    link_dashboard = ""
    link_div = ""
    try:
        link_dashboard = url_for("dashboard.dashboard", _external=True)
    
        link_div = (
            url_for("main.relatorio_divergencias", _external=True, data_filtro=data_filtro)
            if data_filtro
            else url_for("main.relatorio_divergencias", _external=True)
        )

    except Exception:
        link_dashboard = ""
        link_div = ""

    # Poka-yoke nos KPIs
    total = int(k.get("total") or 0)
    conferidos = int(k.get("conferidos") or 0)
    pendentes = int(k.get("pendentes") or 0)
    diverg = int(k.get("divergencias") or k.get("divergentes") or 0)  # aceita chaves diferentes
    taxa_qual = float(k.get("taxa_qualidade") or 0.0)
    acur = float(k.get("acuracidade") or 0.0)
    ret = k.get("total_retencao") or "---"

    # Status semântico rápido
    # (ajuste limites conforme sua realidade)
    if taxa_qual >= 98.5:
        status_txt = "Dentro da meta"
        status_bg = "#198754"  # verde
    elif taxa_qual >= 95:
        status_txt = "Atenção"
        status_bg = "#fd7e14"  # laranja
    else:
        status_txt = "Crítico"
        status_bg = "#dc3545"  # vermelho

    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")

    def badge(text: str, bg: str, fg: str = "#fff") -> str:
        return f"""<span style="display:inline-block;background:{bg};color:{fg};padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;">{text}</span>"""

    def pill(label: str, value: str, hint: str = "", color: str = "#0d6efd") -> str:
        hint_html = f"""<div style="font-size:11px;color:#6c757d;margin-top:2px;">{hint}</div>""" if hint else ""
        return f"""
        <div style="flex:1; min-width:170px; border:1px solid #eee; border-radius:14px; padding:12px 14px;">
          <div style="font-size:11px; color:#6c757d; letter-spacing:.08em; text-transform:uppercase;">{label}</div>
          <div style="display:flex;align-items:flex-end;gap:10px;margin-top:6px;">
            <div style="font-size:24px; font-weight:800; color:#212529;">{value}</div>
            <div>{badge(status_txt, status_bg) if label == "Qualidade" else ""}</div>
          </div>
          {hint_html}
        </div>
        """

    def list_block(title: str, rows: list[tuple[str, int]]) -> str:
        if not rows:
            return f"""
            <div style="flex:1; min-width:260px; border:1px solid #eee; border-radius:14px; padding:12px 14px;">
              <div style="font-size:12px;font-weight:800;color:#212529;margin-bottom:8px;">{title}</div>
              <div style="font-size:12px;color:#6c757d;">Sem dados para o filtro atual.</div>
            </div>
            """
        items = ""
        for name, qty in rows:
            name = (name or "---")
            items += f"""
            <div style="display:flex;justify-content:space-between;gap:10px;border-top:1px solid #f1f1f1;padding:8px 0;">
              <div style="font-size:12px;color:#212529;max-width:75%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{name}</div>
              <div style="font-size:12px;font-weight:800;color:#0d6efd;">{int(qty)}</div>
            </div>
            """
        return f"""
        <div style="flex:1; min-width:260px; border:1px solid #eee; border-radius:14px; padding:12px 14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:12px;font-weight:800;color:#212529;">{title}</div>
            <div style="font-size:11px;color:#6c757d;">Top 5</div>
          </div>
          <div style="margin-top:6px;">{items}</div>
        </div>
        """

    # Montagem do HTML
    html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif; background:#f6f7f8; padding:20px;">
      <div style="max-width:920px; margin:0 auto; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 8px 22px rgba(0,0,0,.10)">
        <div style="background:#212529; color:#fff; padding:18px 20px;">
          <div style="font-size:18px; font-weight:800;">Reporte PSA</div>
          <div style="font-size:12px; opacity:.85;">Nestlé Araçatuba • Gerado em {gerado_em}</div>
        </div>

        <div style="padding:18px 20px;">
          <!-- Resumo executivo -->
          <div style="background:#f8f9fa;border:1px solid #eee;border-radius:14px;padding:12px 14px;margin-bottom:14px;">
            <div style="font-size:13px;font-weight:800;color:#212529;margin-bottom:6px;">
              Resumo executivo
            </div>
            <div style="font-size:12px;color:#495057;line-height:1.5;">
              IRA/Qualidade em <b>{taxa_qual:.1f}%</b> (meta recomendada 98,5%). Total <b>{total}</b> UDs, com <b>{conferidos}</b> conferidas,
              <b>{pendentes}</b> pendentes e <b>{diverg}</b> com divergência.
              Acuracidade atual: <b>{acur:.1f}%</b>.
            </div>
          </div>

          <!-- Cards KPI -->
          <div style="display:flex; flex-wrap:wrap; gap:10px;">
            {pill("Total", f"{total}", "UDs no filtro atual")}
            {pill("Conferidos", f"{conferidos}", "UDs conferidas")}
            {pill("Pendentes", f"{pendentes}", "Prioridade operacional", color="#fd7e14")}
            {pill("Qualidade", f"{taxa_qual:.1f}%", "Indicador principal")}
          </div>

          <!-- Links -->          
          <div style="margin-top:14px; display:flex; gap:10px; flex-wrap:wrap;">
            {f'<a href="{link_dashboard}" style="background:#0d6efd;color:#fff;text-decoration:none;padding:10px 12px;border-radius:12px;font-weight:800;font-size:12px;">Abrir Dashboard</a>' if link_dashboard else ''}
            {f'<a href="{link_div}" style="background:#D51C29;color:#fff;text-decoration:none;padding:10px 12px;border-radius:12px;font-weight:800;font-size:12px;">Ver Divergências</a>' if link_div else ''}
            {f'<a href="{link_preview}" style="background:#198754;color:#fff;text-decoration:none;padding:10px 12px;border-radius:12px;font-weight:800;font-size:12px;">Abrir reporte no navegador</a>' if link_preview else ''}
          </div>

          <!-- Top lists -->
          <div style="margin-top:14px; display:flex; gap:10px; flex-wrap:wrap;">
            {list_block("Pendências por PSA", [(r[0], r[1]) for r in top_psa_pend])}
            {list_block("Materiais com mais divergência", [((r[0] or '')[:42], r[1]) for r in top_mat_div])}
          </div>

          <h3 style="margin:18px 0 10px; font-size:16px; color:#212529;">Divergências recentes (até 30)</h3>
          <div style="border:1px solid #eee; border-radius:14px; overflow:hidden;">
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
                  <td style="padding:10px; font-family:Consolas,monospace; font-weight:800; color:#0d6efd;">{m.unidade_deposito}</td>
                  <td style="padding:10px;">{(m.desc_material or '')[:60]}</td>
                  <td style="padding:10px;">{m.lote or 'S/L'}</td>
                  <td style="padding:10px; text-align:right; font-weight:800;">{int(m.quantidade_estoque or 0)}</td>
                  <td style="padding:10px; color:#D51C29; font-weight:800;">{_fmt_data(m.data_vencimento)}</td>
                  <td style="padding:10px;">{_fmt_dt(m.data_conferencia)}</td>
                </tr>
            """
    else:
        html += """<tr><td colspan="6" style="padding:12px; text-align:center; color:#6c757d;">Sem divergências registradas para o filtro atual.</td></tr>"""

    html += f"""
              </tbody>
            </table>
          </div>

          <div style="margin-top:12px; font-size:12px; color:#6c757d;">
            <div><b>Acuracidade:</b> {acur:.1f}% • <b>Retenção:</b> {ret} semanas</div>
          </div>
        </div>

        <div style="background:#f6f7f8; padding:12px 20px; font-size:11px; color:#6c757d;">
          Este e-mail foi gerado automaticamente pelo Controle PSA.
        </div>
      </div>
    </div>
    """

    return assunto, html


def enviar_reporte_por_email(*, data_filtro: str | None = None) -> tuple[bool, str]:
    """Envia o reporte. Retorna (ok, mensagem)."""
    cfg = ConfiguracaoSistema.get_singleton()

    # --- Normalização (poka-yoke contra espaços/quebra de linha) ---
    smtp_host = (cfg.smtp_host or "").strip()
    smtp_port = int(cfg.smtp_port or 0)

    smtp_usuario = (cfg.smtp_usuario or "").strip()
    smtp_senha = (cfg.smtp_senha or "").strip()

    email_remetente = (cfg.email_remetente or "").strip()
    nome_remetente = (cfg.nome_remetente or "").strip() or None

    use_tls = bool(cfg.smtp_tls)
    use_ssl = bool(cfg.smtp_ssl)

    # validação mínima
    if not email_remetente:
        return False, "Configure o e-mail do remetente (Admin > Configurações)."
    if not smtp_host or not smtp_port:
        return False, "Configure servidor/porta SMTP (Admin > Configurações)."

    # ✅ se smtp_usuario não foi preenchido, assume o remetente
    # (evita login com None/vazio)
    if not smtp_usuario:
        smtp_usuario = email_remetente

    if not smtp_senha:
        return False, "Configure a senha SMTP (Admin > Configurações)."

    # ✅ Gmail costuma ser mais feliz quando o From == usuário autenticado
    # Se você quer manter um 'remetente' diferente, recomendo usar Reply-To no mailer.
    sender_email = smtp_usuario

    destinatarios = [(d.email or "").strip() for d in EmailDestinatario.query.filter_by(ativo=True).all()]
    destinatarios = [e for e in destinatarios if e]  # remove vazios

    if not destinatarios:
        return False, "Cadastre pelo menos 1 destinatário ativo (Admin > Configurações)."

    assunto, html = montar_reporte_html(data_filtro=data_filtro)

    try:
        send_email(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_usuario=smtp_usuario,
            smtp_senha=smtp_senha,
            use_tls=use_tls,
            use_ssl=use_ssl,
            sender_email=sender_email,          # ✅ alinhado com login
            sender_name=nome_remetente,
            to_emails=destinatarios,
            subject=assunto,
            html_body=html,
            # ✅ opcional (se seu send_email suportar): reply_to=email_remetente
        )
        return True, f"Reporte enviado para: {', '.join(destinatarios)}"
    except Exception as e:
        db.session.rollback()
        return False, f"Falha ao enviar e-mail: {e}"

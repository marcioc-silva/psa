# PSA - Nestlé Araçatuba (Controle PSA)

## Rodar local
1. Crie um virtualenv e instale:
   pip install -r requirements.txt
2. Defina variáveis (opcional):
   - DATABASE_URL=postgresql://...  (ou deixe vazio para SQLite local)
   - SECRET_KEY=...
3. Suba:
   flask --app wsgi run --debug

## Deploy (Render)
Start Command sugerido:
gunicorn "wsgi:app" --bind 0.0.0.0:$PORT --workers 1 --threads 2

## Banco Neon / Postgres
- Em Render, coloque **apenas** a URL Postgres em `DATABASE_URL`.
  Exemplo válido:
  postgresql://usuario:senha@host/db?sslmode=require

⚠️ Não cole comando `psql ...` dentro do DATABASE_URL. Tem que ser só a URL.

## Feature: Envio de Reporte por E-mail
- A configuração fica em: /admin/config  (ou menu Configurações)
- Sender (remetente) é único; Destinatários são múltiplos (CRUD).
- Botão "Enviar Reporte" fica no topo (dashboard header).
- O envio usa SMTP do e-mail pessoal configurado (ex.: Gmail com App Password).
  Para Gmail:
  - Host: smtp.gmail.com
  - Porta: 587
  - TLS: ligado
  - Usuário: seuemail@gmail.com
  - Senha: App Password (recomendado), não a senha normal.

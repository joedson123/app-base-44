# Deploy no Render (Flask)

1) Conecte o repositório no Render → New → Web Service.
2) Build Command: `pip install -r requirements.txt`
3) Start Command: `gunicorn -b 0.0.0.0:$PORT app:app`
4) Tipo: Web Service (não Static).
5) (Opcional) Ative Auto-Deploy.

> Obs: SQLite não persiste no plano free; use Render Disk pago ou Postgres.

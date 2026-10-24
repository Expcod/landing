# Nova Code landing — landing.novacode.uz

- `frontend/` — статик сайт (nginx root: /var/www/landing.novacode.uz). Бўлимлар `assets/content.js` орқали `/api/content/` дан тўлдирилади.
- `backend/` — Django admin (/admin/): кейслар, мижозлар, экранлар, видеолар, аризалар, созламалар. API: `GET /api/content/`, `POST /api/lead/`.
- `deploy-*` — nginx ва systemd конфиглари.

Backend ишга тушириш:
```
cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt
python3 -c "import secrets;print(secrets.token_urlsafe(50))" > secret_key
venv/bin/python manage.py migrate && venv/bin/python manage.py collectstatic --noinput
```

## Аризалар → Telegram бот ва Odoo CRM (Meta Ads)

Ҳар бир янги ариза (`POST /api/lead/`) сақлангач, фонда:
- Telegram ботга хабар юборилади;
- Odoo'даги **Meta Ads** модулига (`instagram_ads`) лид бўлиб тушади: `POST /instagram_ads/api/lead`, «Yangi» босқичи, манба = «Tashqi API».

Созлаш: admin → **Созламалар**:
- *Telegram бот токени* — «Сақлаш» босилганда бот webhook'и (`/api/tg/webhook/`) ўзи уланади.
  Ботга `/start` босган ҳар бир одам (ёки бот қўшилган гуруҳ) салом хабарини олади ва admin → **Telegram обуначилар**га қўшилади; аризалар шуларнинг ҳаммасига боради. `/stop` — обунадан чиқиш, admin'да «Аризалар юборилсин» белгисини олиб ҳам ўчириш мумкин.
- *Odoo манзили* (`https://demo.novaodoo.uz`), *базаси* (`crm`), *API калити* — Odoo → Meta Ads → Sozlash → «Lead API kaliti».

Токен ва калитлар фақат базада сақланади, git'га тушмайди. Юборилмай қолган аризалар: admin → Аризалар → белгилаб, «Telegram ва Odoo CRM'га қайта юбориш».
Деплойдан кейин: `venv/bin/python manage.py migrate` ва сервисни қайта ишга тушириш.

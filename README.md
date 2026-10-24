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
- *Telegram бот токени* ва *чат ID лари* (вергул билан). Ботга `/start` ёзинг ёки уни гуруҳга қўшинг — ID шу саҳифада «Ботга ёзган чатлар»да чиқади.
- *Odoo манзили* (`https://demo.novaodoo.uz`), *базаси* (`crm`), *API калити* — Odoo → Meta Ads → Sozlash → «Lead API kaliti».

Токен ва калитлар фақат базада сақланади, git'га тушмайди. Юборилмай қолган аризалар: admin → Аризалар → белгилаб, «Telegram ва Odoo CRM'га қайта юбориш».
Деплойдан кейин: `venv/bin/python manage.py migrate` ва сервисни қайта ишга тушириш.

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

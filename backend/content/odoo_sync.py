"""Аризалар босқичини Odoo (Meta Ads модули) билан икки томонлама синхронлаш.

Асосий манба — Odoo:
- босқичлар рўйхати Odoo'даги instagram.lead.stage'дан олинади;
- панелда босқич ўзгарса, аввал Odoo'га ёзилади, кейин бу ерда сақланади;
- Odoo'да ўзгарса, панел очилганда (30 сонияда бир марта) ёки «Odoo'дан янгилаш» босилганда тортиб олинади.

Фақат шу сайтдан тушган аризалар (Lead.odoo_id бор) синхронланади — Instagram ва бошқа
манбалардан Odoo'га тушган лидлар панелга келмайди.
"""
import logging

from django.core.cache import cache
from django.db import transaction

from .models import Lead, OdooStage, SiteSettings
from .notify import _post, odoo_base

log = logging.getLogger(__name__)
CACHE_KEY = 'odoo_sync_at'
TTL = 30  # сония

# Odoo'га уланишдан олдинги эски ҳолатлар → Odoo босқичи номи (бир марталик мослаштириш)
LEGACY = {'new': 'Yangi', 'called': "Bog'lanildi", 'meeting': 'Uchrashuv belgilandi', 'rejected': 'Atkaz boldi'}


class OdooError(RuntimeError):
    pass


def configured(s=None):
    s = s or SiteSettings.get()
    return bool(s.odoo_url and s.odoo_db and s.odoo_user_key)


def rpc(s, model, method, **kw):
    """Odoo 19 JSON-2 API: /json/2/<model>/<method>."""
    try:
        return _post(f'{odoo_base(s)}/json/2/{model}/{method}', kw,
                     {'Authorization': f'bearer {s.odoo_user_key}', 'X-Odoo-Database': s.odoo_db})
    except Exception as e:  # noqa: BLE001
        raise OdooError(str(e)[:300]) from None


def first_stage():
    return OdooStage.objects.filter(active=True).first()


def sync_stages(s):
    rows = rpc(s, 'instagram.lead.stage', 'search_read', domain=[],
               fields=['name', 'sequence', 'is_won', 'is_lost'])
    seen = []
    for r in rows:
        OdooStage.objects.update_or_create(odoo_id=r['id'], defaults=dict(
            name=r['name'], sequence=r['sequence'], is_won=r['is_won'], is_lost=r['is_lost'], active=True))
        seen.append(r['id'])
    OdooStage.objects.exclude(odoo_id__in=seen).update(active=False)


def _legacy_stage(lead, by_name, lost, first):
    name = LEGACY.get(lead.status)
    if name and name in by_name:
        return by_name[name]
    return lost if lead.status == 'rejected' and lost else first


@transaction.atomic
def pull_leads(s):
    """Odoo'даги ҳозирги босқични панелга олади. Odoo'га етмаган эски аризалар эски ҳолати бўйича жойлашади."""
    stages = {st.odoo_id: st for st in OdooStage.objects.filter(active=True)}
    first = first_stage()
    leads = {l.odoo_id: l for l in Lead.objects.filter(odoo_id__gt=0)}
    changed = 0
    if leads:
        rows = rpc(s, 'instagram.lead', 'search_read', domain=[['id', 'in', list(leads)]],
                   fields=['stage_id'], context={'active_test': False})
        for r in rows:
            sid = r['stage_id'][0] if r.get('stage_id') else None
            st = stages.get(sid)
            lead = leads[r['id']]
            if st and lead.stage_id != st.pk:
                lead.stage = st
                lead.save(update_fields=['stage'])
                changed += 1
    # Odoo'да нусхаси йўқ аризалар (интеграциядан олдинги ёки юборилмаганлар) — бир марта жойлаштирилади
    by_name = {st.name: st for st in stages.values()}
    lost = next((st for st in stages.values() if st.is_lost), None)
    for lead in Lead.objects.filter(stage__isnull=True):
        lead.stage = _legacy_stage(lead, by_name, lost, first)
        lead.save(update_fields=['stage'])
        changed += 1
    return changed


def refresh(force=False):
    """Панел саҳифаси очилганда чақирилади. (ok, хато матни)."""
    s = SiteSettings.get()
    if not configured(s):
        return False, 'Odoo фойдаланувчи API калити киритилмаган — босқичлар синхронланмаяпти.'
    if not force and cache.get(CACHE_KEY):
        return True, ''
    try:
        sync_stages(s)
        pull_leads(s)
    except OdooError as e:
        log.warning('Odoo sync: %s', e)
        cache.set(CACHE_KEY, 1, 10)  # Odoo ишламаса, ҳар саҳифада кутиб қолмаслик учун
        return False, f'Odoo билан боғланиб бўлмади: {e}'
    cache.set(CACHE_KEY, 1, TTL)
    return True, ''


def set_stage(lead, stage):
    """Панелдан босқични ўзгартириш: аввал Odoo'га, кейин бу ерга."""
    s = SiteSettings.get()
    if lead.odoo_id and configured(s):
        rpc(s, 'instagram.lead', 'write', ids=[lead.odoo_id], vals={'stage_id': stage.odoo_id})
    lead.stage = stage
    lead.save(update_fields=['stage'])

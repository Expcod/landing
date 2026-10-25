/* Nova Code панели: кичик ёрдамчилар (фреймворксиз) */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  function post(url, body, json) {
    var headers = { 'X-CSRFToken': csrf(), 'X-Requested-With': 'fetch' };
    if (json) headers['Content-Type'] = 'application/json';
    return fetch(url, { method: 'POST', headers: headers, body: json ? JSON.stringify(body) : body, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }
  function toast(text, kind) {
    var box = $('.toasts');
    var t = document.createElement('div');
    t.className = 'toast ' + (kind || '');
    t.innerHTML = '<span></span><button type="button" aria-label="Ёпиш" data-close>×</button>';
    t.firstChild.textContent = text;
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 4000);
  }
  window.ncToast = toast;

  // Тостлар: ўзи ёпилади
  $$('.toast').forEach(function (t) { setTimeout(function () { t.remove(); }, 5000); });
  document.addEventListener('click', function (e) {
    if (e.target.matches('[data-close]')) e.target.closest('.toast').remove();
  });

  // Мавзу (ёруғ / қоронғи)
  $$('[data-theme-toggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      var root = document.documentElement;
      var dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
      root.dataset.theme = dark ? 'light' : 'dark';
      try { localStorage.setItem('nc-theme', root.dataset.theme); } catch (x) {}
    });
  });

  // Мобил «Яна» менюси
  var sheet = $('#sheet');
  $$('[data-open-sheet]').forEach(function (b) { b.addEventListener('click', function () { sheet.showModal(); }); });
  if (sheet) sheet.addEventListener('click', function (e) { if (e.target === sheet) sheet.close(); });

  // Ўчириш каби хавфли амаллар: <form data-confirm="Матн" data-confirm-title="..." data-confirm-ok="...">
  var dlg = $('#confirm');
  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f.dataset.confirm || f.dataset.confirmed) return;
    e.preventDefault();
    $('[data-confirm-title]', dlg).textContent = f.dataset.confirmTitle || 'Аминмисиз?';
    $('[data-confirm-text]', dlg).textContent = f.dataset.confirm;
    $('[data-confirm-ok]', dlg).textContent = f.dataset.confirmOk || 'Ўчириш';
    dlg.returnValue = '';
    dlg.showModal();
    dlg.addEventListener('close', function once() {
      dlg.removeEventListener('close', once);
      if (dlg.returnValue === 'yes') {
        f.dataset.confirmed = '1';
        if (e.submitter && e.submitter.name) {
          var h = document.createElement('input');
          h.type = 'hidden'; h.name = e.submitter.name; h.value = e.submitter.value; f.appendChild(h);
        }
        f.submit();
      }
    });
  });

  // Яширин калитни кўрсатиш
  $$('input[data-reveal]').forEach(function (inp) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'btn btn-ghost btn-s'; b.textContent = 'Кўрсатиш';
    b.addEventListener('click', function () {
      var show = inp.type === 'password';
      inp.type = show ? 'text' : 'password';
      b.textContent = show ? 'Яшириш' : 'Кўрсатиш';
    });
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;gap:8px;align-items:center';
    inp.parentNode.insertBefore(wrap, inp);
    wrap.appendChild(inp); wrap.appendChild(b);
  });

  // ---------- Аризалар канбани ----------
  function setStatus(card, status, from) {
    var url = card.dataset.statusUrl;
    var fd = new FormData(); fd.append('status', status);
    return post(url, fd).then(function (r) {
      var sel = $('select[data-status]', card); if (sel) sel.value = status;
      recount();
      toast('«' + card.dataset.name + '» → ' + r.label);
    }).catch(function () {
      toast('Ҳолатни сақлаб бўлмади. Саҳифани янгилаб, қайта уриниб кўринг.', 'error');
      if (from) from.appendChild(card);
    });
  }
  function recount() {
    $$('.column').forEach(function (col) {
      var n = $$('.lcard', col).length;
      var el = $('.column-head .n', col); if (el) el.textContent = n;
      var tab = $('.col-tabs [data-col="' + col.dataset.status + '"] .n'); if (tab) tab.textContent = n;
    });
  }
  var board = $('.board');
  if (board && window.Sortable) {
    $$('.column-body', board).forEach(function (body) {
      Sortable.create(body, {
        group: 'leads', animation: 150, delay: 180, delayOnTouchOnly: true, filter: 'a,select,button', preventOnFilter: false,
        onAdd: function (ev) { setStatus(ev.item, ev.to.closest('.column').dataset.status, ev.from); }
      });
    });
  }
  if (board) {
    board.addEventListener('change', function (e) {
      if (!e.target.matches('select[data-status]')) return;
      var card = e.target.closest('.lcard');
      var from = card.parentNode;
      var to = $('.column[data-status="' + e.target.value + '"] .column-body', board);
      to.insertBefore(card, to.firstChild);
      setStatus(card, e.target.value, from);
    });
  }
  // Мобилда устунлар таблари
  $$('.col-tabs [data-col]').forEach(function (b) {
    b.addEventListener('click', function () {
      $$('.col-tabs [data-col]').forEach(function (x) { x.classList.toggle('on', x === b); });
      $$('.board .column').forEach(function (c) { c.classList.toggle('is-shown', c.dataset.status === b.dataset.col); });
    });
  });

  // Ариза саҳифасида ҳолат тугмалари
  $$('.status-pick button').forEach(function (b) {
    b.addEventListener('click', function () {
      var fd = new FormData(); fd.append('status', b.dataset.value);
      post(b.closest('.status-pick').dataset.url, fd).then(function (r) {
        $$('.status-pick button').forEach(function (x) { x.classList.toggle('on', x === b); });
        toast('Ҳолат: ' + r.label);
      }).catch(function () { toast('Ҳолатни сақлаб бўлмади.', 'error'); });
    });
  });

  // ---------- Контент: тартиб ва кўрсатиш ----------
  var items = $('.items[data-reorder]');
  if (items && window.Sortable) {
    Sortable.create(items, {
      handle: '.handle', animation: 150,
      onEnd: function () {
        var ids = $$('.item', items).map(function (li) { return li.dataset.id; });
        post(items.dataset.reorder, { ids: ids }, true)
          .then(function () { toast('Тартиб сақланди — сайтда шундай кўринади.'); })
          .catch(function () { toast('Тартибни сақлаб бўлмади.', 'error'); });
      }
    });
  }
  $$('input[data-toggle-url]').forEach(function (sw) {
    sw.addEventListener('change', function () {
      post(sw.dataset.toggleUrl, new FormData()).then(function (r) {
        sw.closest('.item').classList.toggle('off', !r.active);
        toast(r.active ? 'Сайтда кўрсатилади.' : 'Сайтдан яширилди.');
      }).catch(function () { sw.checked = !sw.checked; toast('Сақлаб бўлмади.', 'error'); });
    });
  });

  // Файл танланганда олдиндан кўриш
  $$('input[type=file]').forEach(function (inp) {
    inp.addEventListener('change', function () {
      var f = inp.files && inp.files[0];
      var picked = inp.closest('.picker') && inp.closest('.picker').querySelector('.picked');
      if (picked) picked.textContent = f ? f.name : 'Файл танланмаган';
      if (!f || !/^image\//.test(f.type)) return;
      var box = inp.closest('.field').querySelector('.preview');
      if (!box) { box = document.createElement('div'); box.className = 'preview'; var at = inp.closest('.picker') || inp; at.parentNode.insertBefore(box, at); }
      box.innerHTML = '<img alt="">';
      box.firstChild.src = URL.createObjectURL(f);
    });
  });
})();

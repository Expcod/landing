/* Nova Code landing: кейслар, экранлар, мижозлар ва видеоларни /api/content/ дан олади.
   API ишламаса, HTML ичидаги ҳозирги маълумот қолади (видеолар учун — DEFAULT_REELS). */
(function () {
  var DEFAULT_REELS = [
    ['1790747843578', 'DW_tdJ2DBx8', 'Belita текстиль фабрикаси раҳбарларидан бири Бобуржондан самимий фикр'],
    ['1790686899679', 'DdE0ap8g3YX', 'Тарозини Odoo’га уладик: кунига 2 соат → йилига 30 иш куни тежалди'],
    ['1790752232149', 'DZaG7N5o5DZ', 'Ходимлар ишлайди. AI агент эса назорат қилади'],
    ['1790752264357', 'DXB_4dYjEx2', 'UzAvto қандай дастур ишлатади?'],
    ['1790752274359', 'DW1dr--jCAG', 'Odoo нима?']
  ].map(function (r) {
    var b = 'https://odoo.novacode.uz/uploads/reel-' + r[0];
    return { src: b + '.mp4', poster: b + '.jpg', url: 'https://www.instagram.com/reel/' + r[1] + '/', cap: r[2] };
  });

  var $ = function (id) { return document.getElementById(id); };
  var esc = function (v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  var pct = function (v) { v = parseInt(v, 10) || 0; return Math.max(0, Math.min(100, v)) + '%'; };
  var check = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#23A575" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex: none; margin-top: 2px"><path d="M20 6 9 17l-5-5"></path></svg>';
  var trend = '<div style="width: 44px; height: 44px; border-radius: 12px; background: #F4F1FF; color: #6C5CE7; display: flex; align-items: center; justify-content: center; flex: none"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6C5CE7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8"></path><path d="M14 7h7v7"></path></svg></div>';

  function clients(list) {
    $('clientsRow').innerHTML = list.map(function (c) {
      return c.logo
        ? '<img src="' + esc(c.logo) + '" alt="' + esc(c.name) + '" style="height: 32px; max-width: 130px; width: auto; object-fit: contain; display: block">'
        : '<span>' + esc(c.name) + '</span>';
    }).join('');
  }

  function results(list) {
    $('heroResults').innerHTML = '<div style="font-size: 13px; font-weight: 700; color: #626779; padding: 14px 0 6px">Мижозларимиз натижаси</div>' +
      list.map(function (r) {
        return '<div style="display: flex; align-items: center; gap: 14px; padding: 14px 0; border-top: 1px solid #F0F0F4">' + trend +
          '<div style="flex: 1; min-width: 0"><div style="font-size: 22px; font-weight: 800; letter-spacing: -0.02em; line-height: 1.15">' + esc(r.num) + '</div>' +
          '<div style="font-size: 13px; color: #626779; margin-top: 2px"><b style="color: #171923">' + esc(r.who) + '</b> · ' + esc(r.what) + '</div></div>' +
          (r.logo ? '<div class="rlogo" style="flex: none; width: 96px; height: 44px; display: flex; align-items: center; justify-content: flex-end"><img src="' + esc(r.logo) + '" alt="' + esc(r.who) + ' логотипи" style="max-width: 96px; max-height: 36px; object-fit: contain; display: block"></div>' : '') +
          '</div>';
      }).join('');
  }

  function bar(label, value, width, color, fill) {
    return '<div style="display: flex; flex-direction: column; gap: 4px"><div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: 700; color: ' + color + '"><span>' + label + '</span><span>' + esc(value) + '</span></div>' +
      '<div style="height: 12px; border-radius: 999px; background: #F4F4F7; overflow: hidden"><div style="height: 100%; border-radius: 999px; background: ' + fill + '; width: ' + pct(width) + '"></div></div></div>';
  }

  function cases(list) {
    $('casesGrid').innerHTML = list.map(function (c) {
      return '<div class="card" style="padding: 26px; display: flex; flex-direction: column; gap: 18px">' +
        '<div><div style="font-weight: 800; font-size: 18px">' + esc(c.who) + '</div><div class="muted" style="font-size: 14px">' + esc(c.what) + '</div></div>' +
        '<div style="display: flex; flex-direction: column; gap: 10px">' +
        bar('Олдин', c.bLabel, c.bW, '#B35A00', '#F5A25D') + bar('Кейин', c.aLabel, c.aW, '#1B7A55', '#23A575') + '</div>' +
        '<div style="border-top: 1px solid #EFEFF4; padding-top: 16px"><div style="font-size: 30px; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1">' + esc(c.num) + '</div>' +
        '<div class="muted" style="font-size: 15px; margin-top: 4px">' + esc(c.line) + '</div></div></div>';
    }).join('');
  }

  function screens(list) {
    $('screensList').innerHTML = list.map(function (x, i) {
      return '<div style="display: flex; flex-wrap: wrap; gap: 32px; align-items: center; flex-direction: ' + (i % 2 ? 'row-reverse' : 'row') + ';">' +
        '<div style="flex: 1 1 360px; min-width: 0; display: flex; flex-direction: column; gap: 14px">' +
        '<span style="align-self: flex-start; padding: 5px 12px; border-radius: 999px; background: #F4F1FF; color: #4B3FC4; font-weight: 700; font-size: 13px">' + esc(x.tag) + '</span>' +
        '<div style="font-size: clamp(24px, 3vw, 34px); font-weight: 800; letter-spacing: -0.025em; line-height: 1.15">' + esc(x.title) + '</div>' +
        '<div style="display: flex; flex-direction: column; gap: 10px">' + x.points.map(function (p) {
          return '<div style="display: flex; gap: 10px; align-items: flex-start; font-size: 16px; line-height: 1.5">' + check + '<span>' + esc(p) + '</span></div>';
        }).join('') + '</div></div>' +
        '<div style="flex: 1.3 1 440px; min-width: 0; background: linear-gradient(160deg, #EEEAFF, #E9F2FF); border-radius: 22px; padding: clamp(14px, 3vw, 32px); display: flex; justify-content: center">' +
        '<img src="' + esc(x.src) + '" alt="' + esc(x.title) + '" loading="lazy" style="width: 100%; max-width: ' + (parseInt(x.max, 10) || 600) + 'px; height: auto; display: block; border-radius: 12px; box-shadow: 0 30px 60px -24px rgba(15,20,32,.55)"></div></div>';
    }).join('');
  }

  // Видео карусель: ўртадаги видео тиниқ ва ўзи (овозсиз) ўйнайди, ён томонлари хира
  var goal = function (n, p) { if (window.ncGoal) window.ncGoal(n, p); };
  var once = {};
  var goalOnce = function (n, p) { var k = n + (p && p.video || ''); if (once[k]) return; once[k] = 1; goal(n, p); };
  var R = { list: [], cur: 0, muted: true };
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var playIcon = '<span class="pbtn"><svg width="22" height="22" viewBox="0 0 24 24" fill="#171923" aria-hidden="true"><path d="M8 5v14l11-7z"></path></svg></span>';
  var muteIcon = function (m) {
    return m
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4z"></path><path d="m23 9-6 6M17 9l6 6"></path></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M11 5 6 9H2v6h4l5 4z"></path><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"></path></svg>';
  };

  function reels(list) {
    R.list = list; R.cur = 0;
    $('reels').style.display = list.length ? '' : 'none';
    $('reelsTrack').innerHTML = list.map(function (r, i) {
      return '<div class="reel" data-i="' + i + '"><video src="' + esc(r.src) + '" poster="' + esc(r.poster) + '" muted playsinline preload="metadata"></video>' +
        playIcon + '<button type="button" class="mute" aria-label="Овоз">' + muteIcon(true) + '</button><div class="cap">' + esc(r.cap) + '</div></div>';
    }).join('');
    layout();
  }

  function layout() {
    var n = R.list.length, els = document.querySelectorAll('#reelsTrack .reel');
    Array.prototype.forEach.call(els, function (el, i) {
      var d = i - R.cur;
      if (d > n / 2) d -= n; else if (d < -n / 2) d += n;   // айлана бўйича энг яқин томон
      var a = Math.abs(d), on = d === 0, v = el.querySelector('video');
      el.classList.toggle('on', on);
      el.style.transform = 'translateY(-50%) translateX(calc(var(--gap) * ' + d + ')) scale(' + (on ? 1 : a === 1 ? 0.84 : 0.7) + ')';
      el.style.opacity = a > 2 ? 0 : on ? 1 : a === 1 ? 0.55 : 0.3;
      el.style.filter = on ? 'none' : 'grayscale(.6) blur(' + (a === 1 ? 1 : 2) + 'px)';
      el.style.zIndex = 10 - a;
      el.style.pointerEvents = a > 2 ? 'none' : '';
      if (on) {
        v.muted = R.muted; v.preload = 'auto';
        el.querySelector('.mute').innerHTML = muteIcon(R.muted);
        if (!reduce) { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
      } else {
        v.pause(); v.muted = true;
        if (a === 0 || v.currentTime) v.currentTime = 0;
      }
    });
    var c = $('reelCount'), z = function (x) { return (x < 10 ? '0' : '') + x; };
    if (c) c.textContent = z(R.cur + 1) + ' / ' + z(n);
  }

  function go(i) {
    var n = R.list.length; if (!n) return;
    R.cur = ((i % n) + n) % n; layout();
  }

  document.querySelectorAll('#reels .rbtn').forEach(function (b) {
    b.addEventListener('click', function () { go(R.cur + +b.getAttribute('data-dir')); });
  });

  $('reelsTrack').addEventListener('click', function (e) {
    var card = e.target.closest('.reel'); if (!card) return;
    var i = +card.getAttribute('data-i');
    if (e.target.closest('.mute')) {
      R.muted = !R.muted;
      if (!R.muted) goalOnce('video_unmute', { video: R.list[i] && R.list[i].cap });
      var v = card.querySelector('video'); v.muted = R.muted;
      e.target.closest('.mute').innerHTML = muteIcon(R.muted);
      if (v.paused) v.play().catch(function () {});
      return;
    }
    if (i !== R.cur) return go(i);
    var vv = card.querySelector('video');
    if (vv.paused) vv.play().catch(function () {}); else vv.pause();
  });

  // Аналитика: видео бошланди / ярмигача / охиригача кўрилди (ҳар бир видео учун бир марта)
  var vname = function (v) { var c = v.closest('.reel'); var r = c && R.list[+c.getAttribute('data-i')]; return r ? r.cap : ''; };
  $('reelsTrack').addEventListener('play', function (e) {
    if (e.target.closest('.reel.on')) goalOnce('video_start', { video: vname(e.target) });
  }, true);
  $('reelsTrack').addEventListener('timeupdate', function (e) {
    var v = e.target; if (!v.duration || !v.closest('.reel.on')) return;
    if (v.currentTime / v.duration >= 0.5) goalOnce('video_50', { video: vname(v) });
  }, true);
  $('reelsTrack').addEventListener('ended', function (e) { goalOnce('video_complete', { video: vname(e.target) }); }, true);
  document.querySelectorAll('#reels .rbtn').forEach(function (b) { b.addEventListener('click', function () { goalOnce('video_swipe'); }); });

  // Аналитика: форма бўлимига етди, тўлдира бошлади, алоқа тугмалари
  if ('IntersectionObserver' in window && $('audit')) {
    var fo = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { goalOnce('form_view'); fo.disconnect(); } }, { threshold: 0.3 });
    fo.observe($('audit'));
  }
  var lf = $('leadForm');
  if (lf) lf.addEventListener('focusin', function () { goalOnce('form_start'); });
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]'); if (!a) return;
    var h = a.getAttribute('href');
    if (/^tel:/.test(h)) goal('click_phone');
    else if (/t\.me\//.test(h)) goal('click_telegram');
    else if (/instagram\.com/.test(h)) goal('click_instagram');
    else if (h === '#audit') goal('click_cta');
  }, true);

  // Видео тугаса — кейингисига ўтади
  $('reelsTrack').addEventListener('ended', function (e) {
    if (e.target.closest('.reel.on')) go(R.cur + 1);
  }, true);

  // Телефонда бармоқ билан суриш
  var sx = null;
  $('reelsTrack').addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; }, { passive: true });
  $('reelsTrack').addEventListener('touchend', function (e) {
    if (sx === null) return;
    var dx = e.changedTouches[0].clientX - sx; sx = null;
    if (Math.abs(dx) > 40) go(R.cur + (dx < 0 ? 1 : -1));
  });

  // Бўлим экрандан чиқса, видео тўхтайди; қайтса — давом этади
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (es) {
      var v = document.querySelector('#reelsTrack .reel.on video'); if (!v) return;
      if (es[0].isIntersecting) { if (!reduce) v.play().catch(function () {}); } else v.pause();
    }, { threshold: 0.35 }).observe($('reelsTrack'));
  }

  reels(DEFAULT_REELS);

  function pixel(id) {
    if (!/^\d+$/.test(id) || window.fbq) return;
    /* Meta Pixel стандарт коди */
    !function (f, b, e, v, n, t, s) {
      if (f.fbq) return; n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
      if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = '2.0'; n.queue = [];
      t = b.createElement(e); t.async = !0; t.src = v; s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
    }(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');
    window.fbq('init', id);
    window.fbq('track', 'PageView');
  }

  fetch('/api/content/').then(function (r) { if (!r.ok) throw r; return r.json(); }).then(function (d) {
    try { pixel(String(d.pixel_id || '')); } catch (e) { console.error(e); }
    var run = function (fn, list) { if (list && list.length) { try { fn(list); } catch (e) { console.error(e); } } };
    run(clients, d.clients);
    run(results, d.results);
    run(cases, d.cases);
    run(screens, d.screens);
    if (d.reels) reels(d.reels);
  }).catch(function () { /* API ишламаса, ҳозирги HTML қолади */ });
})();

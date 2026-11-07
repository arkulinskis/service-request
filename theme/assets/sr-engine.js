/* sr-engine.js: Service Request's browser engines, reached from Python through client_code/sr.py and the
   Map / Uploader components. Everything else (pages, lists, dialogs) is Python Forms.
     maps        Leaflet + OpenStreetMap tiles, loaded only when a map is shown: the board's price-tag pins, a bounty's
                 circle or exact pin, the spot picker's draggable pin
     places      Nominatim search / reverse lookup (only on a tap, as its usage policy asks), "use my location"
     photos      shrink on the phone (a full JPEG + a thumbnail), then upload right away through a Python callback
     extras      confetti, the landing page's drawn neighbourhood map, CSV download
   Moved from the JavaScript version (web/pages/_sr.html) with the page code taken out. */
(function () {
  'use strict';
  var UI = window.UI, esc = UI.esc;
  var SR = window.SR = {};
  SR.HOME = { lat: 45.5088, lng: -73.5878 };  // Montréal: where maps open when we know nothing else

  SR.money = function (n) {
    n = Number(n || 0);
    var whole = Math.round(n) === n;
    return '$' + n.toLocaleString('en-CA', { minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: 2 });
  };

  /* ---------------------------------------------------------------- maps */
  var leafletP = null;
  SR.leaflet = function () {
    if (window.L && window.L.map) return Promise.resolve(window.L);
    if (leafletP) return leafletP;
    leafletP = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      s.onload = function () { window.L ? resolve(window.L) : reject(new Error('no map')); };
      s.onerror = function () { leafletP = null; reject(new Error('The map couldn\'t load.')); };
      document.head.appendChild(s);
      setTimeout(function () { if (!window.L) { leafletP = null; reject(new Error('The map is taking too long to load.')); } }, 12000);
    });
    return leafletP;
  };
  /* OpenStreetMap's own tiles (light use, with the browser's normal Referer). Dark mode inverts them in CSS. */
  function tiles(L, map) {
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
  }
  function pricePin(L, b, cls) {
    return L.divIcon({ className: '', iconSize: [0, 0], iconAnchor: [0, 0],
      html: '<span class="sr-pin ' + (cls || '') + '" data-pin="' + esc(b.id || '') + '">' + esc(b.label || SR.money(b.base + (b.bonus || 0))) + '</span>' });
  }
  function failed(el, e, extra) {
    el.innerHTML = '<div class="sr-map-msg">' + esc((e && e.message) || 'The map couldn\'t load.') + (extra ? ' ' + esc(extra) : '') + '</div>';
  }
  function safeRemove(map) { try { if (map) map.remove(); } catch (e) {} }

  /* The board: price-tag pins (click = open, hover = light up the card), "You" pin. Returns a controller. */
  SR.mapBoard = function (el, center, hooks) {
    var ctl = { map: null, layer: null, L: null, dead: false, pending: null, markers: {} };
    ctl.pins = function (listJson, spotJson) {
      var list = JSON.parse(listJson || '[]'), spot = spotJson ? JSON.parse(spotJson) : null;
      if (!ctl.map) { ctl.pending = [listJson, spotJson]; return; }
      var L = ctl.L, pts = [];
      ctl.layer.clearLayers(); ctl.markers = {};
      list.forEach(function (b) {
        if (b.lat == null) return;
        var mk = L.marker([b.lat, b.lng], { icon: pricePin(L, b), riseOnHover: true, keyboard: false }).addTo(ctl.layer);
        mk.on('click', function () { hooks.open(b.id); });
        mk.on('mouseover', function () { hooks.hover(b.id, true); });
        mk.on('mouseout', function () { hooks.hover(b.id, false); });
        ctl.markers[b.id] = mk; pts.push([b.lat, b.lng]);
      });
      if (spot) L.marker([spot.lat, spot.lng], { icon: pricePin(L, { label: 'You' }, 'me'), interactive: false }).addTo(ctl.layer);
      if (pts.length) ctl.map.fitBounds(pts, { padding: [40, 40], maxZoom: 14, animate: false });
      else ctl.map.setView([center.lat, center.lng], 12, { animate: false });
    };
    ctl.hot = function (id, on) {
      var pin = el.querySelector('[data-pin="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
      if (pin) pin.classList.toggle('hot', !!on);
    };
    ctl.resize = function () { if (ctl.map) ctl.map.invalidateSize(); };
    ctl.destroy = function () { ctl.dead = true; safeRemove(ctl.map); ctl.map = null; };
    SR.leaflet().then(function (L) {
      if (ctl.dead) return;
      el.innerHTML = '';
      ctl.L = L;
      ctl.map = L.map(el, { scrollWheelZoom: false }).setView([center.lat, center.lng], 12);
      tiles(L, ctl.map);
      ctl.layer = L.layerGroup().addTo(ctl.map);
      if (ctl.pending) { var p = ctl.pending; ctl.pending = null; ctl.pins(p[0], p[1]); }
    }, function (e) { if (!ctl.dead) failed(el, e); });
    return ctl;
  };

  /* One place: the exact spot with a pin (the helper, the poster, the post wizard) or a ~500 m circle (everyone else). */
  SR.mapPoint = function (el, lat, lng, exact, label, zoomControl) {
    var ctl = { map: null, dead: false };
    ctl.resize = function () { if (ctl.map) ctl.map.invalidateSize(); };
    ctl.destroy = function () { ctl.dead = true; safeRemove(ctl.map); ctl.map = null; };
    SR.leaflet().then(function (L) {
      if (ctl.dead) return;
      el.innerHTML = '';
      ctl.map = L.map(el, { scrollWheelZoom: false, zoomControl: zoomControl !== false }).setView([lat, lng], exact ? (zoomControl === false ? 15 : 16) : 14);
      tiles(L, ctl.map);
      if (exact) L.marker([lat, lng], { icon: pricePin(L, { label: label || 'Job' }, 'me') }).addTo(ctl.map);
      else L.circle([lat, lng], { radius: 500, color: '#111', weight: 2, fillColor: '#ffd400', fillOpacity: .35 }).addTo(ctl.map);
      setTimeout(ctl.resize, 120);
    }, function (e) { if (!ctl.dead) failed(el, e); });
    return ctl;
  };

  /* The spot picker's map: tap or drag the pin; onPick(lat, lng) tells Python (which looks up the area name). */
  SR.mapSpot = function (el, lat, lng, pinLabel, onPick) {
    var ctl = { map: null, marker: null, L: null, dead: false, pos: lat != null ? { lat: lat, lng: lng } : null };
    ctl.setPos = function (la, ln, zoom) {
      ctl.pos = { lat: +la, lng: +ln };
      if (!ctl.map) return;
      var L = ctl.L;
      if (!ctl.marker) {
        ctl.marker = L.marker([ctl.pos.lat, ctl.pos.lng], { icon: pricePin(L, { label: pinLabel || 'Here' }, 'me'), draggable: true }).addTo(ctl.map)
          .on('dragend', function (ev) { var ll = ev.target.getLatLng(); ctl.pos = { lat: ll.lat, lng: ll.lng }; onPick(ll.lat, ll.lng); });
      } else ctl.marker.setLatLng([ctl.pos.lat, ctl.pos.lng]);
      if (zoom) ctl.map.setView([ctl.pos.lat, ctl.pos.lng], zoom, { animate: false });
    };
    ctl.destroy = function () { ctl.dead = true; safeRemove(ctl.map); ctl.map = null; };
    SR.leaflet().then(function (L) {
      if (ctl.dead) return;
      ctl.L = L;
      el.innerHTML = '';
      var p = ctl.pos;
      ctl.map = L.map(el, { scrollWheelZoom: true }).setView([p ? p.lat : SR.HOME.lat, p ? p.lng : SR.HOME.lng], p ? 15 : 11);
      tiles(L, ctl.map);
      ctl.map.on('click', function (ev) { ctl.setPos(ev.latlng.lat, ev.latlng.lng); onPick(ev.latlng.lat, ev.latlng.lng); });
      if (p) ctl.setPos(p.lat, p.lng);
      setTimeout(function () { if (ctl.map) ctl.map.invalidateSize(); }, 150);
    }, function (e) { if (!ctl.dead) failed(el, e, 'Use your location or search a place instead.'); });
    return ctl;
  };

  /* ---------------------------------------------------------------- places (Nominatim) and location */
  function areaName(a) {
    if (!a) return '';
    var local = a.neighbourhood || a.suburb || a.quarter || a.city_district || a.borough || '';
    var town = a.city || a.town || a.village || a.municipality || a.county || '';
    return [local, town].filter(Boolean).filter(function (v, i, all) { return all.indexOf(v) === i; }).join(', ').slice(0, 60);
  }
  /* Resolve JSON text {area, street} (empty strings when the lookup fails). */
  SR.reverse = function (lat, lng) {
    return fetch('https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=17&addressdetails=1&lat=' + lat + '&lon=' + lng)
      .then(function (r) { return r.json(); }).then(function (j) {
        var a = j.address || {};
        return JSON.stringify({ area: areaName(a), street: [a.house_number, a.road].filter(Boolean).join(' ') });
      }).catch(function () { return JSON.stringify({ area: '', street: '' }); });
  };
  /* Resolve JSON text: a list of {lat, lng, name, street, label}, or {error} when search isn't working. */
  SR.search = function (text) {
    return fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&countrycodes=ca&limit=5&q=' + encodeURIComponent(text))
      .then(function (r) { return r.json(); }).then(function (list) {
        return JSON.stringify(list.map(function (p) {
          var a = p.address || {};
          var name = areaName(a) || (p.display_name || '').split(',').slice(0, 2).join(',');
          return { lat: +p.lat, lng: +p.lon, name: name.slice(0, 60), street: [a.house_number, a.road].filter(Boolean).join(' '), label: p.display_name || name };
        }));
      }).catch(function () { return JSON.stringify({ error: 'Search isn\'t working right now. Tap the map instead.' }); });
  };
  /* Resolve JSON text {lat, lng} or {error}. */
  SR.locate = function (precise) {
    return new Promise(function (resolve) {
      if (!navigator.geolocation) { resolve(JSON.stringify({ error: 'This browser can\'t share its location. Search a place instead.' })); return; }
      navigator.geolocation.getCurrentPosition(function (p) {
        resolve(JSON.stringify({ lat: p.coords.latitude, lng: p.coords.longitude }));
      }, function () { resolve(JSON.stringify({ error: 'We couldn\'t get your location. Allow it in your browser, or search a place.' })); },
      { enableHighAccuracy: !!precise, timeout: 12000, maximumAge: 600000 });
    });
  };

  /* ---------------------------------------------------------------- photos: shrink on the phone, upload right away */
  function drawJpeg(img, max, quality) {
    var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height, s = Math.min(1, max / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w * s)); c.height = Math.max(1, Math.round(h * s));
    var g = c.getContext('2d');
    g.fillStyle = '#ffffff'; g.fillRect(0, 0, c.width, c.height);
    g.imageSmoothingQuality = 'high';
    g.drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL('image/jpeg', quality);
  }
  SR.shrink = function (file) {
    return new Promise(function (resolve, reject) {
      if (!file || !/^image\//.test(file.type || 'image/')) { reject(new Error('That file isn\'t a picture.')); return; }
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        try { var full = drawJpeg(img, 1600, 0.82), thumb = drawJpeg(img, 480, 0.74); URL.revokeObjectURL(url); resolve({ full: full, thumb: thumb }); }
        catch (e) { reject(new Error('That picture couldn\'t be read.')); }
      };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('That picture couldn\'t be read. Try a JPEG or PNG.')); };
      img.src = url;
    });
  };
  /* A photo picker inside `box`: tiles + an "add" tile. upload(full, thumb) is Python: it returns JSON text {key} or
     {error} (a Promise here, since it makes a server call). toast(msg) is Python too. Returns {keys(), busy()}. */
  SR.uploader = function (box, max, label, upload, toast) {
    var tiles = [], seq = 0;
    function draw() {
      box.innerHTML = '<div class="sr-up">' + tiles.map(function (t) {
        return '<div class="tile' + (t.key ? '' : ' busy') + '" data-tile="' + t.id + '"><img src="' + esc(t.src) + '" alt="">' +
          '<button type="button" data-rm="' + t.id + '" aria-label="Remove photo">' + UI.icon('x') + '</button></div>';
      }).join('') + (tiles.length < max ? '<label class="add">' + UI.icon('camera') + '<span>' + esc(label || 'Add photo') + '</span>' +
        '<input type="file" accept="image/*" multiple data-file></label>' : '') + '</div>';
    }
    box.addEventListener('change', function (e) {
      if (!e.target.matches('[data-file]')) return;
      Array.prototype.slice.call(e.target.files || [], 0, max - tiles.length).forEach(function (file) {
        var t = { id: 't' + (++seq), key: null, src: '' };
        tiles.push(t);
        SR.shrink(file).then(function (d) {
          t.src = d.thumb; draw();
          return Promise.resolve(upload(d.full, d.thumb));
        }).then(function (reply) {
          var r = JSON.parse(reply);
          if (r.error) throw new Error(r.error);
          t.key = r.key; draw();
        }).catch(function (err) {
          tiles = tiles.filter(function (x) { return x !== t; }); draw(); toast((err && err.message) || 'That photo didn\'t upload.');
        });
      });
      draw();
    });
    box.addEventListener('click', function (e) {
      var rm = e.target.closest('[data-rm]');
      if (rm) { e.preventDefault(); tiles = tiles.filter(function (x) { return x.id !== rm.getAttribute('data-rm'); }); draw(); }
    });
    draw();
    return {
      keys: function () { return JSON.stringify(tiles.filter(function (t) { return t.key; }).map(function (t) { return t.key; })); },
      busy: function () { return tiles.some(function (t) { return !t.key; }); }
    };
  };

  /* ---------------------------------------------------------------- confetti, download */
  SR.confetti = function () {
    if (UI.reducedMotion && UI.reducedMotion()) return;
    var box = document.createElement('div'), colors = ['#ffd400', '#111111', '#ffffff', '#ffd400', '#ff8a3d'];
    box.className = 'sr-confetti';
    box.setAttribute('aria-hidden', 'true');
    for (var i = 0; i < 80; i++) {
      var p = document.createElement('i');
      p.style.left = Math.random() * 100 + 'vw';
      p.style.background = colors[i % colors.length];
      p.style.animationDelay = (Math.random() * .4) + 's';
      p.style.setProperty('--dx', (Math.random() * 200 - 100) + 'px');
      p.style.setProperty('--r', (Math.random() * 900 - 450) + 'deg');
      box.appendChild(p);
    }
    document.body.appendChild(box);
    setTimeout(function () { box.remove(); }, 3200);
  };
  SR.download = function (name, text, type) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/csv' }));
    a.download = name; document.body.appendChild(a); a.click(); a.remove();
  };

  /* ---------------------------------------------------------------- the landing page's hero map
     A made-up Montréal block (the street grid tilts like the real one), a park, the river, and bounty pins from the real
     task catalogue. Pins sit right of the card on desktop, across the top on phones. pinsJson: [{icon, cat, name, price}] */
  function tag(base, bonus) {
    return '<span class="sr-tag sm"><b>' + SR.money(base) + '</b>' + (bonus ? '<i>+' + SR.money(bonus) + ' at 80%</i>' : '<i>bounty</i>') + '</span>';
  }
  function tile(p) { return '<span class="sr-ti sm c-' + esc(p.cat) + '">' + UI.icon(p.icon) + '</span>'; }
  SR.heroArt = function (el, pinsJson) {
    var streets = '', i, tasks = JSON.parse(pinsJson || '[]');
    for (i = -6; i < 22; i++) streets += '<path d="M' + (i * 110) + ' -200 L' + (i * 110 + 520) + ' 900"/>';
    for (i = -4; i < 14; i++) streets += '<path d="M-300 ' + (i * 86) + ' L1600 ' + (i * 86 - 300) + '"/>';
    var map = '<div class="lp-map" aria-hidden="true"><svg viewBox="0 0 1280 640" preserveAspectRatio="xMidYMid slice">' +
      '<rect width="1280" height="640" fill="var(--land)"/>' +
      '<path d="M1280 470 C1120 520 1010 560 900 640 L1280 640 Z" fill="var(--water)"/>' +
      '<path d="M760 120 L930 60 L990 190 L820 250 Z" fill="var(--park)"/>' +
      '<path d="M1080 300 L1180 262 L1214 350 L1112 388 Z" fill="var(--park)"/>' +
      '<g stroke="var(--casing)" stroke-width="16" fill="none">' + streets + '</g>' +
      '<g stroke="var(--street)" stroke-width="11" fill="none">' + streets + '</g>' +
      '<path d="M560 -40 L1340 520" stroke="var(--casing)" stroke-width="26" fill="none"/><path d="M560 -40 L1340 520" stroke="var(--street)" stroke-width="20" fill="none"/>' +
      '<g fill="var(--label)" font-family="inherit" font-size="13" font-weight="700" letter-spacing="2">' +
        '<text x="820" y="168" transform="rotate(-20 820 168)">PARC</text>' +
        '<text x="1010" y="600" transform="rotate(-14 1010 600)">FLEUVE</text>' +
        '<text x="980" y="300" transform="rotate(35.6 980 300)">BOUL. SAINT-LAURENT</text></g>' +
      '</svg></div>';
    var spots = [[58, 30], [72, 22], [86, 36], [66, 58], [80, 66], [92, 54], [74, 86]];
    var pins = tasks.slice(0, 7).map(function (t, n) {
      return '<div class="lp-pin' + (n === 3 ? ' hot' : '') + '" style="left:' + spots[n][0] + '%;top:' + spots[n][1] + '%;animation-delay:' + (n * 0.12) + 's">' +
        tile(t) + tag(t.price, n % 2 ? 10 : 0) + '</div>';
    }).join('');
    var pop = tasks[3] ? '<div class="lp-pop" style="left:66%;top:58%"><b>' + esc(tasks[3].name) + '</b>Rosemont · about 400 m away' +
      '<div class="ui-row">' + tag(tasks[3].price, 10) + '<span class="muted">3 offers</span></div></div>' : '';
    el.innerHTML = map + '<div class="lp-pins" aria-hidden="true"><span class="lp-you" style="left:76%;top:48%"></span>' + pins + pop + '</div>' +
      '<span class="lp-legend" aria-hidden="true">Bounties near you, right now</span>';
  };
})();

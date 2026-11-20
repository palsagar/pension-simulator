/* Pension Simulator front end.
   Alpine.js holds the state of the controls, calls POST /simulate when one changes,
   and hands the result to Observable Plot. No build step.
   The server is asked twice per view: once with defaults (the baseline) and once with the visitor's settings. */
(function () {
  'use strict';

  const API = (window.PENSION_API_BASE || '').replace(/\/$/, '');
  const MINUS = '−';
  const WORKING_AGE_FROM = 20; // lower edge of "working age" in the pyramid, FIRST_AGE in ledger.py

  /* ---------- formatting ---------- */
  const num = (v, d) => { const s = Math.abs(v).toFixed(d); return (v < 0 && Number(s) !== 0 ? MINUS : '') + s; };
  const pct = (v, d) => num(v, d) + '%';
  const signed = (v, d) => { const s = Math.abs(v).toFixed(d); return Number(s) === 0 ? s : (v < 0 ? MINUS : '+') + s; };
  const thousands = (v) => Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const ageParts = (a) => {
    let y = Math.floor(a + 1e-9); let m = Math.round((a - y) * 12);
    if (m === 12) { y += 1; m = 0; }
    return { y: String(y), rest: m ? 'years, ' + m + (m === 1 ? ' month' : ' months') : 'years', short: m ? y + ' years ' + m + ' months' : y + ' years' };
  };

  /* ---------- the controls ---------- */
  // `scale` turns the API value into the value shown on the slider (0.232 -> 23.2).
  const p1 = (v) => pct(v, 1);
  const SLIDERS = [
    { key: 'retirement_age_year', group: 'main', label: 'Year the new age is reached', min: 2025, max: 2050, step: 1, scale: 1, fmt: (v) => String(v), help: 'The retirement age moves in equal steps from today’s value and reaches the new value in this year.' },
    { key: 'contribution_rate', group: 'main', label: 'Contribution rate', min: 0, max: 60, step: 0.1, scale: 100, fmt: p1, help: 'The share of the average wage that each worker pays into the pension system.' },
    { key: 'benefit_level', group: 'main', label: 'Benefit level', min: 0, max: 150, step: 0.1, scale: 100, fmt: p1, help: 'A newly awarded pension as a share of the average wage.' },
    { key: 'wage_growth', group: 'assumptions', label: 'Wage growth per year, above inflation', min: -1, max: 4, step: 0.1, scale: 100, fmt: p1, help: 'How fast the average wage rises each year after inflation.' },
    { key: 'interest_rate', group: 'assumptions', label: 'Interest rate on pension debt, above inflation', min: -2, max: 6, step: 0.1, scale: 100, fmt: p1, help: 'The yearly cost of carrying pension debt, after inflation.' },
    { key: 'fertility', group: 'assumptions', label: 'Children per woman in 2040', min: 0.5, max: 4, step: 0.01, scale: 1, fmt: (v) => v.toFixed(2), help: 'The average number of children per woman that the country reaches by 2040.' },
    { key: 'net_migration', group: 'assumptions', label: 'Net migration per year', min: -1000000, max: 2000000, step: 1000, scale: 1, fmt: (v) => (v < 0 ? MINUS : '') + thousands(Math.abs(v)), help: 'People who arrive minus people who leave, each year.' },
    { key: 'longevity_pace', group: 'assumptions', label: 'Pace of gains in life expectancy', min: 0, max: 150, step: 5, scale: 100, fmt: (v) => pct(v, 0), help: 'At 100% life expectancy rises as the United Nations projects. At 0% it stops rising.' }
  ];
  const RULES = [
    { key: 'borrow', label: 'Borrow', note: 'Later generations pay, with interest.' },
    { key: 'raise_contributions', label: 'Raise contributions', note: 'Today’s workers pay more.' },
    { key: 'cut_pensions', label: 'Cut pensions', note: 'Today’s retirees get less.' }
  ];
  const KEYS = ['retirement_age', 'retirement_age_year', 'contribution_rate', 'benefit_level', 'balancing_rule', 'indexation', 'wage_growth', 'interest_rate', 'fertility', 'net_migration', 'longevity_pace'];
  const URL_KEYS = { retirement_age: 'age', retirement_age_year: 'by', contribution_rate: 'rate', benefit_level: 'benefit', balancing_rule: 'rule', indexation: 'index', wage_growth: 'wages', interest_rate: 'interest', fertility: 'children', net_migration: 'migration', longevity_pace: 'longevity' };
  // A value from the address is used only when the service would accept it. A link with a value
  // outside the range of a control would otherwise leave the page with no result to show.
  const allowed = (k, v) => {
    if (k === 'retirement_age') return v >= 55 && v <= 75;
    if (k === 'balancing_rule') return RULES.some((r) => r.key === v);
    if (k === 'indexation') return v === 'prices' || v === 'wages';
    const s = SLIDERS.find((x) => x.key === k); return v >= s.min / s.scale && v <= s.max / s.scale;
  };
  const snap = (s, v) => { const d = (String(s.step).split('.')[1] || '').length; return Number((Math.round(v / s.step) * s.step).toFixed(d)); };

  /* ---------- scales: the curves should fill the figure, whatever the country or scenario ---------- */
  // The domain is the data range plus 6% of air on each side, so a curve always spans about 88% of the
  // plot height. Ticks are round values inside that domain; the plot edges need not be ticks.
  // Zero joins the domain when the data come close to it (or when `zero` is set), and a positive
  // lower edge is snapped to half a tick step so that "Axis starts at" reads as a round number.
  function fitScale(lo, hi, opt) {
    opt = opt || {};
    (opt.include || []).forEach((v) => { lo = Math.min(lo, v); hi = Math.max(hi, v); });
    if (!isFinite(lo) || !isFinite(hi)) { lo = 0; hi = 1; }
    let span = hi - lo;
    if (span < 1e-9) span = Math.abs(hi) * 0.2 || 1;
    let a = lo - span * 0.06; let b = hi + span * 0.06;
    if (lo >= 0 && a < 0) a = 0;
    if (hi <= 0 && b > 0) b = 0;
    if (opt.zero || (a > 0 && a < 0.3 * b)) a = Math.min(a, 0);
    if (opt.zero) b = Math.max(b, 0);
    const raw = (b - a) / 4.5; const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    let step = mag; let best = Infinity;
    [1, 2, 2.5, 5, 10].forEach((m) => { const d = Math.abs(Math.log(m * mag / raw)) + (m === 2.5 ? 0.15 : 0); if (d < best) { best = d; step = m * mag; } });
    if (a > 0) a = Math.floor(a / (step / 2) + 1e-9) * (step / 2);
    const ticks = []; for (let k = Math.ceil(a / step - 1e-9); k * step <= b + step * 1e-9; k++) ticks.push(Number((k * step).toPrecision(12)));
    const dec = (String(Number(step.toPrecision(6))).split('.')[1] || '').length;
    return { t0: Number(a.toPrecision(12)), t1: b, ticks, dec, step };
  }
  // Round a maximum up to 1, 2, 2.5 or 5 times a power of ten (the pyramid's half width).
  function niceCeil(v) { const mag = Math.pow(10, Math.floor(Math.log10(v))); return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map((m) => m * mag).find((x) => x >= v * 0.999); }
  window.pensionFitScale = fitScale;

  /* ---------- charts ---------- */
  function tokens(root) {
    const cs = getComputedStyle(root); const t = (n) => cs.getPropertyValue(n).trim();
    return { ink: t('--color-ink'), muted: t('--color-muted'), tick: t('--color-tick'), grid: t('--color-grid'), control: t('--color-control'), card: t('--color-card'), rule: t('--color-rule'),
      accent: t('--color-accent'), second: t('--color-second'), young: t('--color-young'), working: t('--color-working'), retired: t('--color-retired') };
  }
  const MARGIN = { top: 24, right: 52, bottom: 28, left: 44 };
  const LINE = { scen: 2.75, base: 1.5 };

  function mount(el, c, height, margin, options) {
    const width = Math.max(240, el.clientWidth);
    const svg = Plot.plot(Object.assign({ width, height, marginTop: margin.top, marginRight: margin.right, marginBottom: margin.bottom, marginLeft: margin.left,
      style: { fontFamily: 'inherit', fontSize: '12px', background: 'transparent', color: c.tick, overflow: 'visible' } }, options));
    el.replaceChildren(svg);
  }

  /* One chart over time or over birth years.
     o.x: array of x values; o.lines: [{ key, values, kind: 'scen' | 'second' | 'base' }];
     o.area: [upperValues, lowerValues] or null; o.ends: [{ values, text, muted }]; o.refs: [{ v, label }]. */
  function lineChart(el, c, o) {
    if (!el || !el.clientWidth) return;
    const n = o.x.length; const height = el.clientHeight || 240;
    let lo = Infinity; let hi = -Infinity;
    o.lines.forEach((l) => l.values.forEach((v) => { if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; } }));
    const sc = fitScale(lo, hi, o.scale);
    const rows = o.x.map((x, i) => { const r = { x, i }; o.lines.forEach((l) => { r[l.key] = l.values[i]; }); if (o.area) { r.a1 = o.area[0][i]; r.a2 = o.area[1][i]; } return r; });
    const stroke = { scen: c.accent, second: c.second, base: c.tick };
    const marks = [
      Plot.gridY(sc.ticks, { stroke: c.grid, strokeOpacity: 1 }),
      Plot.axisY(sc.ticks, { tickFormat: (v) => o.fmt(v, sc.dec), tickSize: 0, label: null }),
      Plot.axisX(o.xTicks, { tickFormat: (v) => String(v), tickSize: 0, label: null })
    ];
    if (sc.t0 <= 0 && sc.t1 >= 0) marks.push(Plot.ruleY([0], { stroke: c.control }));
    (o.refs || []).forEach((r) => {
      marks.push(Plot.ruleY([r.v], { stroke: c.ink }));
      marks.push(Plot.text([r], { x: o.x[0], y: r.v, text: () => r.label, textAnchor: 'start', dx: 6, dy: -8, fill: c.ink }));
    });
    if (o.area) marks.push(Plot.areaY(rows, { x: 'x', y1: 'a1', y2: 'a2', fill: c.accent, fillOpacity: 0.13 }));
    if (o.mark != null) marks.push(Plot.ruleX([o.mark], { stroke: c.ink }));
    o.lines.filter((l) => l.kind === 'base').concat(o.lines.filter((l) => l.kind !== 'base')).forEach((l) => {
      marks.push(Plot.lineY(rows, { x: 'x', y: l.key, stroke: stroke[l.kind], strokeWidth: l.kind === 'base' ? LINE.base : LINE.scen, strokeDasharray: l.kind === 'base' ? '5 4' : null, strokeLinecap: l.kind === 'base' ? 'butt' : 'round' }));
    });
    if (o.mark != null) {
      const r = rows.find((d) => d.x === o.mark);
      if (r) o.lines.filter((l) => l.kind !== 'base' && r[l.key] != null).forEach((l) => marks.push(Plot.dot([r], { x: 'x', y: l.key, r: 5, fill: stroke[l.kind], stroke: c.card, strokeWidth: 2 })));
    }
    // labels at the right end, kept at least 15px apart
    const inner = height - MARGIN.top - MARGIN.bottom;
    const ends = (o.ends || []).filter((e) => e.values[n - 1] != null).map((e) => ({ e, v: e.values[n - 1], px: (1 - (e.values[n - 1] - sc.t0) / (sc.t1 - sc.t0)) * inner }));
    ends.sort((p, q) => p.px - q.px);
    for (let i = 1; i < ends.length; i++) if (ends[i].px - ends[i - 1].px < 15) { const mid = (ends[i].px + ends[i - 1].px) / 2; ends[i - 1].px = mid - 7.5; ends[i].px = mid + 7.5; }
    ends.forEach((d) => marks.push(Plot.text([d], { x: o.x[n - 1], y: d.v, text: () => d.e.text, textAnchor: 'start', dx: 8, dy: d.px - (1 - (d.v - sc.t0) / (sc.t1 - sc.t0)) * inner, fill: d.e.muted ? c.tick : c.ink, fontWeight: d.e.muted ? 400 : 600 })));
    if (o.tip) {
      marks.push(Plot.ruleX(rows, Plot.pointerX({ x: 'x', stroke: c.muted, strokeOpacity: 0.6 })));
      marks.push(Plot.tip(rows, Plot.pointerX({ x: 'x', y: o.lines.find((l) => l.kind !== 'base').key, title: (d) => o.tip(d.i), fill: c.card, stroke: c.rule, textPadding: 8, fontSize: 12 })));
    }
    mount(el, c, height, MARGIN, { x: { type: 'linear', domain: [o.x[0], o.x[n - 1]] }, y: { domain: [sc.t0, sc.t1] }, marks, ariaLabel: o.aria });
    if (sc.t0 > 0) {
      const s = document.createElement('span'); s.className = 'axis-note'; s.textContent = 'Axis starts at ' + o.fmt(sc.t0, sc.dec + (Math.abs(sc.t0 / sc.step - Math.round(sc.t0 / sc.step)) > 1e-6 ? 1 : 0)); s.style.left = MARGIN.left + 'px';
      el.appendChild(s);
    }
  }

  function pyramidChart(el, c, pop, retirementAge, max, aria) {
    if (!el || !el.clientWidth) return;
    const women = pop[0]; const men = pop[1]; const rows = [];
    const band = (lo, hi, fill) => {
      for (let a = Math.floor(lo); a < Math.min(101, Math.ceil(hi)); a++) {
        const y1 = Math.max(a, lo); const y2 = Math.min(a + 1, hi);
        if (y2 > y1) rows.push({ y1, y2, x1: -women[a], x2: men[a], fill });
      }
    };
    band(0, WORKING_AGE_FROM, c.young); band(WORKING_AGE_FROM, retirementAge, c.working); band(retirementAge, 101, c.retired);
    const label = (v) => (v === 0 ? '0' : el.clientWidth < 520 ? Math.abs(v) / 1000 + 'k' : thousands(Math.abs(v)));
    // Wide figures name the two boundaries in the right margin; narrow ones set them on the line.
    const wide = el.clientWidth >= 520; const right = wide ? 150 : 52;
    el.parentElement.style.setProperty('--pyr-right', right + 'px');
    const bounds = [{ y: WORKING_AGE_FROM, t: wide ? 'Working age\nfrom ' + WORKING_AGE_FROM : 'Age ' + WORKING_AGE_FROM }, { y: retirementAge, t: (wide ? 'Retirement age\n' : 'Retirement age ') + ageParts(retirementAge).short }];
    mount(el, c, el.clientHeight || 400, { top: 6, right, bottom: 26, left: 44 }, {
      x: { domain: [-max, max] }, y: { domain: [0, 101] }, ariaLabel: aria,
      marks: [
        Plot.axisX([-max, -max / 2, 0, max / 2, max], { tickFormat: label, tickSize: 0, label: null }),
        Plot.axisY([0, 20, 40, 60, 80, 100], { tickSize: 0, label: null }),
        Plot.rect(rows, { x1: 'x1', x2: 'x2', y1: 'y1', y2: 'y2', fill: (d) => d.fill }),
        Plot.ruleX([0], { stroke: c.card }),
        Plot.ruleY([WORKING_AGE_FROM, retirementAge], { stroke: c.ink, strokeWidth: 1.5 }),
        wide ? Plot.text(bounds, { x: max, y: 'y', text: 't', textAnchor: 'start', dx: 8, lineHeight: 1.25, fill: c.ink, fontWeight: 600 })
          : Plot.text(bounds, { x: max, y: 'y', text: 't', textAnchor: 'end', dy: -9, dx: -2, fill: c.ink, fontWeight: 600, stroke: c.card, strokeWidth: 5, paintOrder: 'stroke' })
      ]
    });
  }

  /* ---------- the page ---------- */
  document.addEventListener('alpine:init', () => {
    Alpine.data('sim', () => {
      // Results stay outside Alpine's reactive state: they are large and never bound directly.
      const data = { base: null, run: null, max: 1 };
      const popMax = (run) => { let mx = 0; run.population.forEach((yr) => yr.forEach((sx) => sx.forEach((v) => { if (v > mx) mx = v; }))); return niceCeil(mx); };
      let lastWidth = 0;
      let seq = 0; let controller = null; let frame = 0; let timer = null; let baseSeq = 0; let busy = false; let queued = false;

      return {
        countries: [], code: 'FRA', p: {}, horizon: 25, error: false, version: 0,
        py: 0, playing: false, birth: 1990, unit: 'w', help: {}, theme: 'light', sheetOpen: false,
        rules: RULES,
        mainSliders: SLIDERS.filter((s) => s.group === 'main'),
        assumptionSliders: SLIDERS.filter((s) => s.group === 'assumptions'),

        async init() {
          let saved = null; try { saved = localStorage.getItem('pension-theme'); } catch (e) { /* storage may be blocked */ }
          this.theme = saved || (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
          const q = new URLSearchParams(location.search);
          try {
            const r = await fetch(API + '/countries'); if (!r.ok) throw new Error(r.status);
            this.countries = (await r.json()).sort((a, b) => a.name.localeCompare(b.name));
          } catch (e) { this.error = true; return; }
          const wanted = (q.get('country') || 'FRA').toUpperCase();
          this.code = this.countries.some((c) => c.code === wanted) ? wanted : this.countries[0].code;
          this.p = Object.assign({}, this.defaults);
          KEYS.forEach((k) => { const v = q.get(URL_KEYS[k]); if (v == null || v === '') return; const x = typeof this.defaults[k] === 'number' ? Number(v) : v; if (allowed(k, x)) this.p[k] = x; });
          if (q.get('to') === '2100') this.horizon = 75;
          await this.loadBaseline();
          ['horizon', 'theme', 'unit', 'birth'].forEach((k) => this.$watch(k, () => { if (k === 'horizon') { this.py = Math.min(this.py, this.horizon); this.syncUrl(); } this.$nextTick(() => this.draw()); }));
          this.$watch('py', () => this.drawPyramid());
          this.$watch('p.balancing_rule', () => this.$nextTick(() => this.draw()));
          new ResizeObserver(() => { const w = this.$el.clientWidth; if (w === lastWidth) return; lastWidth = w; requestAnimationFrame(() => this.draw()); }).observe(this.$el);
        },

        /* ----- state ----- */
        get country() { return this.countries.find((c) => c.code === this.code) || null; },
        get defaults() { return this.country ? this.country.defaults : {}; },
        get countryName() { return this.country ? this.country.name : ''; },
        get changed() { return KEYS.some((k) => this.p[k] !== this.defaults[k]); },
        get defIdx() { return Math.max(0, Math.min(80, Math.round(((this.defaults.retirement_age || 55) - 55) * 4))); },
        get ageIdx() { return Math.max(0, Math.min(80, Math.round(((this.p.retirement_age || 55) - 55) * 4))); },
        get ageText() { return ageParts(this.p.retirement_age || 55); },
        get defaultNote() { return this.country ? this.countryName + ' today: ' + ageParts(this.defaults.retirement_age).short : ''; },
        get heroTick() { return 'calc(14px + (100% - 28px) * ' + (this.defIdx / 80).toFixed(4) + ')'; },
        ui(s) { const v = this.p[s.key]; return v == null ? s.min : snap(s, v * s.scale); },
        tickLeft(s) { const v = this.defaults[s.key]; const f = v == null ? 0 : (snap(s, v * s.scale) - s.min) / (s.max - s.min); return 'calc(10px + (100% - 20px) * ' + f.toFixed(4) + ')'; },
        // A slider that returns to the default position gets the country's exact default back.
        setUi(s, raw) { const v = Number(raw); const d = this.defaults[s.key]; this.set(s.key, v === snap(s, d * s.scale) ? d : Number((v / s.scale).toFixed(6))); },
        setAge(raw) { const i = Number(raw); this.set('retirement_age', i === this.defIdx ? this.defaults.retirement_age : 55 + i / 4); },
        set(key, value) { this.p[key] = value; this.schedule(); },
        reset() { this.p = Object.assign({}, this.defaults); this.schedule(); },
        // When the baseline of the new country cannot be loaded, the page goes back to the country
        // whose result is still on screen. The message stays visible.
        async pickCountry(code) {
          this.stopPlay(); const was = { code: this.code, p: this.p };
          this.code = code; this.p = Object.assign({}, this.defaults);
          if (!(await this.loadBaseline())) { this.code = was.code; this.p = was.p; }
        },
        toggleTheme() { this.theme = this.theme === 'dark' ? 'light' : 'dark'; try { localStorage.setItem('pension-theme', this.theme); } catch (e) { /* ignore */ } },

        /* ----- server ----- */
        async post(body, signal) {
          const r = await fetch(API + '/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
          if (!r.ok) throw new Error('simulate ' + r.status);
          return r.json();
        },
        // A new baseline makes every request still under way out of date, so that a late answer
        // for the previous country cannot replace the charts of the new one.
        // Returns false when the baseline could not be loaded.
        async loadBaseline() {
          const mine = ++baseSeq; seq++; if (controller) controller.abort(); busy = false; queued = false;
          let base; try { base = await this.post({ country: this.code }); } catch (e) { if (mine !== baseSeq) return true; this.error = true; return false; }
          if (mine !== baseSeq) return true;
          data.base = base; this.error = false;
          if (!this.changed) { data.run = data.base; data.max = popMax(data.base); this.version++; this.syncUrl(); this.$nextTick(() => this.draw()); } else await this.simulate();
          return true;
        },
        // Every control is live: at most one request per animation frame, and one request at a time.
        // A change made while a request is under way waits, and goes out when that request returns.
        // Each answer is drawn, so the charts follow a drag even when the connection is slow. A newer
        // request must not cancel the older one: on a slow connection no answer would ever arrive.
        schedule() { if (frame) return; frame = requestAnimationFrame(() => { frame = 0; this.simulate(); }); },
        async simulate() {
          if (busy) { queued = true; return; }
          const mine = ++seq; const ctl = controller = new AbortController(); busy = true;
          // A request that gets no answer would block every later one. It is given up after 10 seconds and reported as failed.
          let late = false; const limit = setTimeout(() => { late = true; ctl.abort(); }, 10000);
          const body = { country: this.code }; KEYS.forEach((k) => { if (this.p[k] !== this.defaults[k]) body[k] = this.p[k]; });
          try {
            const run = this.changed ? await this.post(body, ctl.signal) : data.base;
            if (mine !== seq || !run) return;
            data.run = run; data.max = popMax(run); this.error = false; this.version++; this.syncUrl(); this.$nextTick(() => this.draw());
          } catch (e) { if ((e.name !== 'AbortError' || late) && mine === seq) this.error = true; }
          // A new baseline has already cleared the flags, so an answer from before it leaves them alone.
          finally { clearTimeout(limit); if (mine === seq) { busy = false; if (queued) { queued = false; this.simulate(); } } }
        },
        syncUrl() {
          const q = new URLSearchParams(); if (this.code !== 'FRA') q.set('country', this.code);
          KEYS.forEach((k) => { if (this.p[k] !== this.defaults[k]) q.set(URL_KEYS[k], this.p[k]); });
          if (this.horizon === 75) q.set('to', '2100');
          const s = q.toString(); history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash);
        },

        /* ----- headline figures ----- */
        get stats() {
          void this.version; const run = data.run; const base = data.base; if (!run || !base) return [];
          const h = this.horizon; const y = run.years[h]; const ch = this.changed;
          const debtS = run.pension_debt_gdp[h] * 100; const debtB = base.pension_debt_gdp[h] * 100;
          const spS = run.pensions_gdp[h] * 100; const spB = base.pensions_gdp[h] * 100;
          const srS = run.support_ratio[h]; const srB = base.support_ratio[h];
          const fd = (v) => (v == null ? 'None' : String(v));
          let fdDelta = 'Unchanged'; const a = run.first_deficit_year; const b = base.first_deficit_year;
          if (a == null && b != null) fdDelta = 'No deficit to 2100';
          else if (a != null && b == null) fdDelta = 'Deficit appears';
          else if (a != null && a !== b) fdDelta = Math.abs(a - b) + (Math.abs(a - b) === 1 ? ' year ' : ' years ') + (a > b ? 'later' : 'earlier');
          return [
            { id: 'debt', label: 'Pension debt in ' + y, value: pct(debtS, 0), unit: 'of GDP', context: debtS < -0.5 ? 'A surplus' : 'Accumulated since ' + run.years[0], changed: ch, delta: signed(debtS - debtB, 0) + ' points', base: 'Baseline ' + pct(debtB, 0) },
            { id: 'deficit', label: 'First year in deficit', value: fd(a), unit: '', context: a == null ? 'Balanced through 2100' : 'Pensions exceed contributions', changed: ch, delta: fdDelta, base: 'Baseline ' + fd(b) },
            { id: 'support', label: 'Workers per retiree in ' + y, value: num(srS, 2), unit: '', context: num(run.support_ratio[0], 2) + ' today', changed: ch, delta: signed(srS - srB, 2), base: 'Baseline ' + num(srB, 2) },
            { id: 'spending', label: 'Pension spending in ' + y, value: pct(spS, 1), unit: 'of GDP', context: pct(run.pensions_gdp[0] * 100, 1) + ' today', changed: ch, delta: signed(spS - spB, 1) + ' points', base: 'Baseline ' + pct(spB, 1) }
          ];
        },
        get leverTitle() { return this.p.balancing_rule === 'cut_pensions' ? 'Benefit level that balances each year' : 'Contribution rate that balances each year'; },
        get leverSub() { return 'Deficits are no longer borrowed, so the cost moves here: ' + (this.p.balancing_rule === 'cut_pensions' ? 'the average pension as a share of the average wage.' : 'the share of the average wage paid into the system.'); },

        /* ----- population ----- */
        retirementAgeIn(i) { return data.run ? data.run.retirement_age[i] : 62; },
        get groups() {
          void this.version; const run = data.run; if (!run) return [];
          const pop = run.population[this.py]; const R = this.retirementAgeIn(this.py); const sums = [0, 0, 0];
          for (let a = 0; a <= 100; a++) {
            const v = pop[0][a] + pop[1][a];
            const young = a < WORKING_AGE_FROM ? 1 : 0; const working = a < WORKING_AGE_FROM ? 0 : Math.max(0, Math.min(1, R - a));
            sums[0] += v * young; sums[1] += v * working; sums[2] += v * (1 - young - working);
          }
          const tot = sums[0] + sums[1] + sums[2]; const mil = (v) => (v / 1e6).toFixed(1) + ' million';
          return [
            { label: 'Retired', color: 'var(--color-retired)', count: mil(sums[2]), share: pct(sums[2] / tot * 100, 0) },
            { label: 'Working age', color: 'var(--color-working)', count: mil(sums[1]), share: pct(sums[1] / tot * 100, 0) },
            { label: 'Below working age', color: 'var(--color-young)', count: mil(sums[0]), share: pct(sums[0] / tot * 100, 0) }
          ];
        },
        stopPlay() { if (timer) { clearInterval(timer); timer = null; } this.playing = false; },
        togglePlay() {
          if (this.playing) { this.stopPlay(); return; }
          if (this.py >= this.horizon) this.py = 0;
          this.playing = true;
          timer = setInterval(() => { if (this.py >= this.horizon) this.stopPlay(); else this.py++; }, 160);
        },

        /* ----- generations ----- */
        get genReadout() {
          void this.version; const run = data.run; const base = data.base; if (!run) return { a: '', b: '' };
          const i = this.birth - run.cohorts.birth_years[0]; const f = (v) => (v == null ? 'no value' : num(v, 1));
          return { a: 'Born in ' + this.birth + ': pays in ' + f(run.cohorts.lifetime_contributions[i]) + ' years of average wage and gets back ' + f(run.cohorts.lifetime_pensions[i]) + '.',
            b: this.changed ? 'Baseline: ' + f(base.cohorts.lifetime_contributions[i]) + ' and ' + f(base.cohorts.lifetime_pensions[i]) + '.' : '' };
        },
        get retReadout() {
          void this.version; const run = data.run; const base = data.base; if (!run) return { a: '', b: '' };
          const key = this.unit === 'p' ? 'return_above_prices' : 'return_above_wages'; const i = this.birth - run.cohorts.birth_years[0];
          const f = (v) => (v == null ? 'not defined' : pct(v * 100, 2));
          return { a: 'Born in ' + this.birth + ': a yearly return of ' + f(run.cohorts[key][i]) + (this.unit === 'p' ? ' above inflation.' : ' above wage growth.'), b: this.changed ? 'Baseline: ' + f(base.cohorts[key][i]) + '.' : '' };
        },

        /* ----- drawing ----- */
        draw() {
          const run = data.run; const base = data.base; if (!run || !base || !window.Plot) return;
          const c = tokens(this.$el); const h = this.horizon; const n = h + 1; const ch = this.changed;
          const years = run.years.slice(0, n); const xTicks = years.filter((y, i) => i % (h > 25 ? 15 : 5) === 0);
          const cut = (a, k) => a.slice(0, n).map((v) => (v == null ? null : v * k));
          const pf = (v, d) => pct(v, d); const name = this.countryName; const last = years[h];
          const tipRow = (label, a, b, f) => (i) => years[i] + '\n' + label + ' ' + f(a[i]) + (ch ? '\nBaseline ' + f(b[i]) : '');

          const dS = cut(run.pension_debt_gdp, 100); const dB = cut(base.pension_debt_gdp, 100);
          lineChart(this.$refs.debt, c, { x: years, xTicks, fmt: pf, scale: { zero: true },
            lines: [{ key: 'b', values: dB, kind: 'base' }, { key: 's', values: dS, kind: 'scen' }], area: ch ? [dS, dB] : null,
            ends: (ch ? [{ values: dB, text: pct(dB[h], 0), muted: true }] : []).concat([{ values: dS, text: pct(dS[h], 0) }]),
            tip: tipRow('Pension debt', dS, dB, (v) => pct(v, 0) + ' of GDP'),
            aria: 'Pension debt in ' + name + ', ' + years[0] + ' to ' + last + '. Your scenario ends at ' + pct(dS[h], 0) + ' of GDP, the baseline at ' + pct(dB[h], 0) + '.' });

          const mI = cut(run.contributions_gdp, 100); const mO = cut(run.pensions_gdp, 100); const bI = cut(base.contributions_gdp, 100); const bO = cut(base.pensions_gdp, 100);
          lineChart(this.$refs.money, c, { x: years, xTicks, fmt: pf, area: [mO, mI],
            lines: (ch ? [{ key: 'bo', values: bO, kind: 'base' }, { key: 'bi', values: bI, kind: 'base' }] : []).concat([{ key: 'i', values: mI, kind: 'second' }, { key: 'o', values: mO, kind: 'scen' }]),
            ends: [{ values: mO, text: pct(mO[h], 1) }, { values: mI, text: pct(mI[h], 1) }],
            tip: (i) => years[i] + '\nPensions ' + pct(mO[i], 1) + '\nContributions ' + pct(mI[i], 1) + '\nBalance ' + signed(mI[i] - mO[i], 1) + ' points',
            aria: 'Contributions and pensions in ' + name + ' as shares of GDP. In ' + last + ' pensions are ' + pct(mO[h], 1) + ' and contributions ' + pct(mI[h], 1) + '.' });

          const sS = cut(run.support_ratio, 1); const sB = cut(base.support_ratio, 1);
          lineChart(this.$refs.support, c, { x: years, xTicks, fmt: (v, d) => num(v, Math.max(1, d)), scale: { include: [1] }, refs: [{ v: 1, label: 'One worker per retiree' }],
            lines: [{ key: 'b', values: sB, kind: 'base' }, { key: 's', values: sS, kind: 'scen' }],
            ends: (ch ? [{ values: sB, text: num(sB[h], 2), muted: true }] : []).concat([{ values: sS, text: num(sS[h], 2) }]),
            tip: tipRow('Workers per retiree', sS, sB, (v) => num(v, 2)),
            aria: 'Workers per retiree in ' + name + ', from ' + num(sS[0], 2) + ' in ' + years[0] + ' to ' + num(sS[h], 2) + ' in ' + last + '.' });

          if (this.p.balancing_rule !== 'borrow') {
            const key = this.p.balancing_rule === 'cut_pensions' ? 'benefit_level' : 'contribution_rate'; const label = key === 'benefit_level' ? 'Benefit level' : 'Contribution rate';
            const lS = cut(run[key], 100); const lB = cut(base[key], 100);
            lineChart(this.$refs.lever, c, { x: years, xTicks, fmt: pf, lines: [{ key: 'b', values: lB, kind: 'base' }, { key: 's', values: lS, kind: 'scen' }],
              ends: [{ values: lB, text: pct(lB[h], 1), muted: true }, { values: lS, text: pct(lS[h], 1) }], tip: tipRow(label, lS, lB, (v) => pct(v, 1)),
              aria: label + ' in ' + name + ', ' + pct(lS[0], 1) + ' in ' + years[0] + ' and ' + pct(lS[h], 1) + ' in ' + last + '.' });
          }

          const by = run.cohorts.birth_years; const bTicks = by.filter((y) => y % 10 === 0); const nf = (v, d) => num(v, d);
          const gI = run.cohorts.lifetime_contributions; const gO = run.cohorts.lifetime_pensions;
          lineChart(this.$refs.gen, c, { x: by, xTicks: bTicks, fmt: nf, mark: this.birth,
            lines: (ch ? [{ key: 'bo', values: base.cohorts.lifetime_pensions, kind: 'base' }, { key: 'bi', values: base.cohorts.lifetime_contributions, kind: 'base' }] : []).concat([{ key: 'i', values: gI, kind: 'second' }, { key: 'o', values: gO, kind: 'scen' }]),
            aria: 'Lifetime contributions and pensions by birth year, ' + by[0] + ' to ' + by[by.length - 1] + ', in years of average wage.' });
          const rk = this.unit === 'p' ? 'return_above_prices' : 'return_above_wages'; const x100 = (a) => a.map((v) => (v == null ? null : v * 100));
          lineChart(this.$refs.ret, c, { x: by, xTicks: bTicks, fmt: (v, d) => pct(v, Math.max(1, d)), mark: this.birth,
            lines: (ch ? [{ key: 'b', values: x100(base.cohorts[rk]), kind: 'base' }] : []).concat([{ key: 's', values: x100(run.cohorts[rk]), kind: 'scen' }]),
            aria: 'Rate of return on contributions by birth year, ' + (this.unit === 'p' ? 'above inflation.' : 'above wage growth.') });

          this.drawPyramid(c);
        },
        drawPyramid(c) {
          const run = data.run; if (!run || !window.Plot) return;
          const g = this.groups;
          pyramidChart(this.$refs.pyramid, c || tokens(this.$el), run.population[this.py], this.retirementAgeIn(this.py), data.max,
            'Population of ' + this.countryName + ' by age and sex in ' + run.years[this.py] + ': ' + g.map((x) => x.count + ' ' + x.label.toLowerCase()).join(', ') + '.');
        }
      };
    });
  });
})();

/* Smoke test (tools/ui_test.py runs it at 1280 px and at 390 px): every page address opens without errors, is not
   empty and doesn't scroll sideways. Signed out (landing, board, a bounty, a neighbour, rules, sign in / up, a bad
   bounty link), then as a new member (board, a bounty with the offer form, the report dialog, the post wizard's first
   two steps, a bounty they posted = the poster's view, my jobs tabs, ledger, profile + the area picker, their public
   page), then as admin (every Admin tab, a bounty as moderator).
   Python/JS errors are caught by ui_test.py from the browser log. Resolves to {ok, log}. */
(async function () {
  const log = [], bad = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 20000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const errs = [];
  window.addEventListener('error', (e) => errs.push(String(e.message || e)));
  const visible = (el) => !!el && el.getClientRects().length > 0;
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function button(re, root) { return $$((root || '') + ' button').find((b) => re.test(b.textContent.trim()) && visible(b)); }
  function check(name, expect) {
    const main = $('.ui-main');
    const text = main ? main.innerText.trim() : '';
    const w = document.documentElement.scrollWidth, vw = screen.width <= 500 ? screen.width : window.innerWidth;
    const problems = [];
    if (text.length < 40) problems.push('empty page');
    if (expect && !new RegExp(expect.source, 'i').test(text)) problems.push('missing ' + expect);
    if (w > vw + 1) {
      const wide = $$('body *').filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 1; })
        .slice(0, 3).map((e) => e.tagName.toLowerCase() + '.' + String(e.className).split(' ').slice(0, 2).join('.'));
      problems.push('scrolls sideways (' + w + ' > ' + vw + ') ' + wide.join(' '));
    }
    if (errs.length) problems.push('errors: ' + errs.splice(0).join(' / '));
    if (problems.length) bad.push(name + ': ' + problems.join('; '));
    log.push((problems.length ? 'BAD  ' : 'ok   ') + name);
  }
  async function open(hash, expect) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash, hash, 30000);
    await sleep(700);
    check(hash, expect);
  }
  async function dialog(name, opener, expect) {
    if (!opener) { bad.push('dialog ' + name + ': no button to open it'); return; }
    opener.click();
    const dlg = await until(() => $$('.modal, .anvil-modal').find((m) => visible(m) && m.innerText.trim().length > 10), 'dialog ' + name, 15000);
    await sleep(600);
    const text = dlg.innerText;
    const problems = [];
    if (expect && !expect.test(text)) problems.push('missing ' + expect);
    if (errs.length) problems.push('errors: ' + errs.splice(0).join(' / '));
    if (problems.length) bad.push('dialog ' + name + ': ' + problems.join('; '));
    log.push((problems.length ? 'BAD  ' : 'ok   ') + 'dialog ' + name);
    const close = $$('.modal button, .anvil-modal button').find((b) => /^(Cancel|Close|Back)$/.test(b.textContent.trim()) && visible(b));
    if (close) close.click();
    await until(() => !$$('.modal, .anvil-modal').some(visible), 'dialog closed', 10000);
    await sleep(300);
  }
  async function signUp(name, email, password) {
    location.hash = '#auth/signup';
    await until(() => window.UI_READY && $$('.au-card input').length >= 3, 'sign-up form');
    await sleep(400);
    const inputs = $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter(visible);
    type(inputs[0], name); type(inputs[1], email); type(inputs[2], password);
    const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
    button(/Create account/, '.au-card .anvil-role-btn-block').click();
    const end = Date.now() + 30000;
    while (Date.now() < end) {
      if (location.hash === '#board' && window.UI_READY) return true;
      const msg = $('.au-card .anvil-role-msg-error');
      if (msg && visible(msg) && msg.textContent.trim()) { log.push('sign-up said: ' + msg.textContent.trim()); return false; }
      await sleep(200);
    }
    log.push('sign-up: still on ' + location.hash);
    return false;
  }
  async function signIn(email, password) {
    location.hash = '#auth';
    await until(() => window.UI_READY && $$('.au-card input[type=password]').length, 'sign-in form');
    await sleep(400);
    type($('.au-card input[type=email]'), email); type($('.au-card input[type=password]'), password);
    button(/Sign in/, '.au-card .anvil-role-btn-block').click();
    await until(() => location.hash === '#board' && window.UI_READY, 'signed in as ' + email, 30000);
  }
  async function signOut() {
    $('.anvil-role-avatar button').click();
    await sleep(300);
    button(/Sign out/, '.ui-menu').click();
    await until(() => {
      const a = $('.anvil-role-avatar button');
      return location.hash === '#landing' && window.UI_READY && (!a || !visible(a));
    }, 'signed out');
    await sleep(500);
  }
  try {
    // ---- signed out
    await open('#landing', /A neighbour/);
    await open('#board', /Bounties near/);
    await until(() => $$('a.sr-card').length > 0, 'bounty cards (demo data)', 30000);
    const bountyHref = $('a.sr-card').getAttribute('href');
    await open(bountyHref, /About the job/);
    check('bounty (visitor)', /Join to make an offer/);
    const nb = $('.bt-person a.bt-who');
    if (nb) await open(nb.getAttribute('href'), /How records work/); else bad.push('no poster card on the bounty');
    await open('#rules', /Six scams/);
    await open('#rules/scams', /Six scams/);
    await open('#bounty/' + encodeURIComponent('[1,999999]'), /not found|no longer/);
    await open('#auth', /Sign in/);
    await open('#auth/signup', /Create account/);

    // ---- a new member
    const ok = await signUp('Smoke Neighbour', 'smoke' + Date.now() + '@example.com', 'Sr-' + Math.random().toString(36).slice(2) + '-Kq7');
    if (!ok) throw new Error('sign-up failed');
    await sleep(600);
    check('#board (member)', /Bounties near/);
    await open(bountyHref, /Make an offer|Offer sent|Not this time/);
    await dialog('report', button(/Report this bounty/), /What happened/);
    await open('#post', /What do you need done/);
    const taskBtn = $('.ps-task');
    if (taskBtn) { taskBtn.click(); await sleep(900); check('#post step 2', /Say what needs doing/); } else bad.push('no task to pick');
    await open('#post/leaves', /Say what needs doing|What do you need done/);
    // the poster's view: post a bounty through the same server call the wizard makes
    const posted = JSON.parse(await window.srCall('post_bounty', JSON.stringify([{
      task: 'leaves', title: 'Rake the front yard please', details: 'Front yard and the side path, bags are in the shed.', size: 'medium',
      when_date: '', when_note: 'Saturday', lat: 45.53, lng: -73.58, area: 'Rosemont', address: '1234 rue Fullum', base: 30, bonus: 10, bar: 80,
      checklist: ['Lawn raked', 'Leaves bagged', 'Bags at the curb'], pay_method: 'either', photo_keys: [] }])));
    if (posted.ok === false) bad.push('post_bounty: ' + posted.error);
    else {
      await open('#bounty/' + encodeURIComponent(posted.id), /How quality is measured/);
      check('bounty (poster)', /Waiting for|Pick your helper|moderator/);
      const raise = button(/Raise the bounty/);
      if (raise) await dialog('raise', raise, /Quality bonus/);
    }
    for (const t of ['jobs', 'jobs/posted', 'jobs/doing', 'jobs/offers']) await open('#' + t, /My jobs/);
    await open('#ledger', /Ledger/);
    await open('#profile', /Helper profile/);
    await dialog('area picker', button(/Set my area|Change/), /Name of the area/);
    const pub = $('.pf-head a.ui-btn');
    if (pub) await open(pub.getAttribute('href'), /How records work/);
    await open('#landing', /Open the board/);
    await signOut();

    // ---- admin (ADMIN_EMAILS in Accounts.py): sign up the first time, sign in after that
    const adminPw = 'Sr-smoke-adm-93Kx-7q';
    if (!(await signUp('Admin Tester', 'arkulinskis@gmail.com', adminPw))) await signIn('arkulinskis@gmail.com', adminPw);
    for (const t of ['overview', 'queue', 'safety', 'bounties', 'feedback', 'users', 'demo']) await open('#admin/' + t, /Admin/);
    await open(bountyHref, /About the job/);
    await signOut();
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' | ') : 'PASSED');
    return { ok: !bad.length, log: log };
  } catch (e) {
    log.push(String(e && e.message || e));
    if (bad.length) log.push('PROBLEMS: ' + bad.join(' | '));
    return { ok: false, log: log };
  }
})();

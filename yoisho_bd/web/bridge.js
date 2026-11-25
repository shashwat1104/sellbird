// ── Yoisho BD OS inside Sellbird's dashboard ──
//
// Served inside /static/app.js, just before Sellbird starts its first screen,
// so deep links (#yorgs, #yorg/ORG-000001) open directly. Adds one dock place,
// "Pipeline", with three views (Organizations, Opportunities, Tasks), an
// organization page, and a "Your BD" block at the top of Today. Everything
// uses Sellbird's own components (section-head, card, btn, tag, form-input,
// dialog.modal), so it looks and behaves like the rest of the dashboard.
// All names live in one object, window.yo, to stay clear of Sellbird's.

(function () {
  'use strict';
  const yo = window.yo = {};
  let V = null;                 // reference lists from /api/yoisho/vocab
  let orgId = '';               // which organization the yorg screen shows
  const state = {orgs: {sort: 'updated', dir: 'desc'}, opps: {active: '1'}, contacts: ''};

  // ── screens ──

  const PAGES = {
    yorgs: {pill: 'Organizations', title: 'Organizations',
            lede: 'Companies, schools, universities and partners you are working on.'},
    yopps: {pill: 'Opportunities', title: 'Opportunities',
            lede: 'Learn, Study and Work opportunities. Values stay empty until you know them.'},
    ytasks: {pill: 'Tasks', title: 'Tasks', lede: 'What to do, and when. Tick a task to complete it.'},
    ycontacts: {pill: 'Contacts', title: 'Contacts', lede: 'Decision-makers at your organizations.'},
    yorg: {parent: 'yorgs', title: 'Organization', lede: ''},
  };
  for (const [id, p] of Object.entries(PAGES)) {
    SCREENS[id] = p.parent ? {place: 'pipeline', parent: p.parent} : {place: 'pipeline', pill: p.pill};
  }
  PARENT_NAMES.yorgs = 'Organizations';
  SCREEN_ALIASES.pipeline = 'yorgs';
  SCREEN_ALIASES.organizations = 'yorgs';

  const inner = document.getElementById('inner');
  for (const [id, p] of Object.entries(PAGES)) {
    const el = document.createElement('div');
    el.id = id;
    el.className = 'section yo-page';
    el.innerHTML = `<div class="section-head"><div><h1 tabindex="-1">${escHtml(p.title)}</h1><p>${escHtml(p.lede)}</p></div>` +
      `<div class="page-actions" id="${id}-actions"></div></div><div id="${id}-body"></div>`;
    inner.appendChild(el);
  }

  // The dock: Pipeline sits right after Today.
  const dock = document.querySelector('.navlist');
  const today = dock && dock.querySelector('[data-place="today"]');
  if (today) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'navitem';
    b.dataset.place = 'pipeline';
    b.setAttribute('aria-label', 'Pipeline');
    b.onclick = () => goTab(_lastScreen.pipeline || 'yorgs');
    b.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16M4 12h11M4 17h7"/><circle cx="18.5" cy="16.5" r="2.5"/></svg>' +
      '<span class="lbl" aria-hidden="true">Pipeline</span><span class="nav-count" id="nav-pipeline"></span>';
    today.after(b);
  }

  // An organization's page has its id in the address: #yorg/ORG-000001.
  const sellbirdFromHash = fromHash;
  fromHash = function () {
    const raw = (window.location.hash || '').slice(1);
    if (raw.slice(0, 5) === 'yorg/') {
      try { orgId = decodeURIComponent(raw.slice(5)); } catch { orgId = ''; }
      return orgId ? 'yorg' : 'yorgs';
    }
    return sellbirdFromHash();
  };

  const sellbirdLoad = loadCurrentTab;
  loadCurrentTab = function () {
    sellbirdLoad();
    const run = {yorgs: renderOrgs, yopps: renderOpps, ytasks: renderTasks, ycontacts: renderContacts,
                 yorg: renderOrg, today: renderTodayBlock}[currentTab];
    if (run) ready().then(run).catch(showErr);
    if (currentTab === 'yorg' && orgId) {
      try { history.replaceState(null, '', '#yorg/' + encodeURIComponent(orgId)); } catch { /* ignore */ }
    }
  };

  yo.openOrg = id => { orgId = id; showTab('yorg'); };

  // ── helpers ──

  async function ready() {
    if (!V) V = await call('/vocab');
  }

  async function call(path, method, data) {
    const opts = {method: method || 'GET', headers: {}};
    if (data !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(data); }
    let resp;
    try { resp = await authFetch('/api/yoisho' + path, opts); }
    catch { throw {status: 0, error: 'Could not reach the server. Check the private connection window is open.'}; }
    let body = {};
    try { body = await resp.json(); } catch { /* empty */ }
    if (!resp.ok) throw Object.assign({status: resp.status}, body, {error: body.error || body.detail || `Request failed (${resp.status})`});
    return body;
  }

  function showErr(e) {
    const body = document.getElementById(currentTab + '-body');
    const msg = e && e.status === 401 ? 'Signed out. Open your private dashboard link again.' : escHtml((e && e.error) || 'Something went wrong.');
    if (body) body.innerHTML = emptyState('&#9888;', 'Could not load this page', msg);
  }

  const lab = (table, code) => (V && V[table] && V[table][code]) || code || '';
  function options(table, selected, blank) {
    let entries = Array.isArray(V[table]) ? V[table].map(v => [v, v]) : Object.entries(V[table]);
    if (blank !== undefined) entries = entries.filter(([k]) => k !== '');
    return (blank !== undefined ? `<option value="">${escHtml(blank)}</option>` : '') +
      entries.map(([k, v]) => `<option value="${escHtml(k)}"${k === selected ? ' selected' : ''}>${escHtml(v)}</option>`).join('');
  }
  function day(d) {
    if (!d) return '';
    const date = new Date(d.length <= 10 ? d + 'T00:00:00' : d);
    return isNaN(date) ? d : date.toLocaleDateString('en-IN', {day: 'numeric', month: 'short', year: 'numeric'});
  }
  const todayISO = () => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Kolkata'}).format(new Date());
  const toast = (m, t) => showToast(m, t || 'success');
  const setBody = (id, html) => { const el = document.getElementById(id + '-body'); if (el) el.innerHTML = html; };
  const setActions = (id, html) => { const el = document.getElementById(id + '-actions'); if (el) el.innerHTML = html; };
  const classTag = c => `<span class="tag ${c === 'GREEN' ? 'good' : c === 'YELLOW' ? 'wait' : 'bad'}">${escHtml(c === 'YELLOW' ? 'Yellow: review' : c.charAt(0) + c.slice(1).toLowerCase())}</span>`;
  const prioTag = o => o.priority ? `<span class="tag acc">${escHtml(o.priority)}</span>${o.opportunity_score !== null ? ` <span class="yo-dim">${escHtml(o.opportunity_score)}</span>` : ''}` : '<span class="yo-dim">Not scored</span>';

  // ── dialog forms ──

  let submitFn = null;
  const dlg = document.createElement('dialog');
  dlg.className = 'modal yo-modal';
  dlg.id = 'yo-dialog';
  dlg.setAttribute('aria-labelledby', 'yo-dialog-title');
  document.body.appendChild(dlg);
  dlg.addEventListener('close', () => { submitFn = null; });

  function openForm(title, fields, values, submitLabel, onSubmit, extraHtml) {
    values = values || {};
    const html = fields.map(([name, text, type, extra]) => {
      extra = extra || {};
      const v = values[name] ?? '';
      const fid = 'yo-f-' + name;
      const req = extra.required ? ' required' : '';
      const wide = type === 'textarea' || extra.wide ? ' yo-wide' : '';
      if (type === 'check') return `<div class="form-group${wide}"><label class="yo-check"><input type="checkbox" id="${fid}" name="${name}"${v ? ' checked' : ''}> ${escHtml(text)}</label></div>`;
      let input;
      if (type === 'textarea') input = `<textarea class="form-input" rows="3" id="${fid}" name="${name}"${req}>${escHtml(v)}</textarea>`;
      else if (type && type.startsWith('select:')) input = `<select class="form-input" id="${fid}" name="${name}"${req}>${options(type.slice(7), v, extra.blank !== undefined ? extra.blank : '')}</select>`;
      else input = `<input class="form-input" id="${fid}" name="${name}" type="${type || 'text'}" value="${escHtml(v)}"${req}${extra.placeholder ? ` placeholder="${escHtml(extra.placeholder)}"` : ''}>`;
      return `<div class="form-group${wide}"><label class="form-label" for="${fid}">${escHtml(text)}${req ? ' *' : ''}</label>${input}</div>`;
    }).join('');
    dlg.innerHTML = `<form method="dialog" id="yo-form"><div class="modal-head"><div><h3 id="yo-dialog-title">${escHtml(title)}</h3></div>
      <button type="button" class="btn btn-ghost btn-sm btn-icon" aria-label="Close" onclick="yo.close()">&times;</button></div>
      <div class="modal-body"><div class="yo-grid">${html}</div>${extraHtml || ''}<div id="yo-form-err"></div></div>
      <div class="modal-foot"><button type="button" class="btn btn-ghost" onclick="yo.close()">Cancel</button>
      <button type="submit" class="btn btn-primary">${escHtml(submitLabel || 'Save')}</button></div></form>`;
    submitFn = onSubmit;
    dlg.querySelector('form').addEventListener('submit', submit);
    if (!dlg.open) dlg.showModal();
    const first = dlg.querySelector('input:not([type=checkbox]), select, textarea');
    if (first) first.focus();
  }
  yo.close = () => { if (dlg.open) dlg.close(); };

  async function submit(event) {
    event.preventDefault();
    const form = event.target;
    const data = {};
    for (const el of form.elements) if (el.name) data[el.name] = el.type === 'checkbox' ? el.checked : el.value.trim();
    const err = document.getElementById('yo-form-err');
    err.innerHTML = '';
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try { await submitFn(data); yo.close(); }
    catch (e) {
      let html = `<div class="yo-err">${escHtml(e.error || 'Could not save.')}`;
      if (e.status === 409 && e.existing) html += ` <a href="#" onclick="yo.close();yo.openOrg('${escHtml(e.existing.id)}');return false">Open ${escHtml(e.existing.name)}</a>`;
      err.innerHTML = html + '</div>';
    } finally { btn.disabled = false; }
  }

  // Only changed fields go to the server, so the change log stays accurate.
  function changed(before, after) {
    const out = {};
    for (const [k, v] of Object.entries(after)) {
      if (k.startsWith('_')) { if (v) out[k] = v; continue; }
      const old = before[k] === null || before[k] === undefined ? '' : before[k];
      const norm = typeof v === 'boolean' ? (v ? 1 : 0) : v;
      if (String(old) !== String(norm)) out[k] = norm;
    }
    return out;
  }
  const REASON = ['_reason', 'Reason for the change (optional)', 'text', {wide: true}];

  const ORG_FORM = [
    ['name', 'Name', 'text', {required: true}], ['website', 'Website', 'text', {placeholder: 'example.com'}],
    ['org_type', 'Organization type', 'select:org_types', {blank: 'Choose'}], ['industry', 'Industry'],
    ['sub_industry', 'Sub-industry'], ['country', 'Country'], ['state_region', 'State / Prefecture'], ['city', 'City'],
    ['crm_stage', 'CRM stage', 'select:crm_stage'], ['next_action', 'Next action'],
    ['next_action_date', 'Next action date', 'date'], ['notes', 'Notes', 'textarea'],
  ];
  const CONTACT_FORM = [
    ['name', 'Name', 'text', {required: true}], ['job_title', 'Job title'], ['department', 'Department'],
    ['email', 'Email', 'email'], ['email_source', 'Where the email came from', 'text', {placeholder: 'Company website, business card, Hunter'}],
    ['verification_status', 'Email check', 'select:verification'], ['linkedin', 'LinkedIn URL', 'url'],
    ['country', 'Country'], ['language', 'Language'], ['relevance', 'Why this person'],
    ['next_follow_up', 'Next follow-up', 'date'], ['is_primary', 'Primary contact (2 at most per organization)', 'check'],
    ['notes', 'Notes', 'textarea'],
  ];
  const OPP_FORM = [
    ['name', 'Opportunity', 'text', {required: true}], ['pillar', 'Pillar', 'select:pillar', {required: true, blank: 'Choose'}],
    ['opp_type', 'Type', 'text', {placeholder: 'Corporate training, student recruitment'}], ['stage', 'Stage', 'select:opp_stage'],
    ['description', 'Description', 'textarea'], ['evidence', 'Evidence', 'textarea'],
    ['hypothesis', 'Hypothesis (not yet proven)', 'textarea'],
    ['potential_value', 'Potential value (only if known)', 'text', {placeholder: 'Leave empty if unknown'}],
    ['probability', 'Probability % (only if known)', 'number'], ['target_date', 'Target date', 'date'],
    ['next_action', 'Next action'], ['next_action_date', 'Next action date', 'date'], ['outcome', 'Outcome'],
    ['notes', 'Notes', 'textarea'],
  ];
  const TASK_FORM = [
    ['title', 'Task', 'text', {required: true, wide: true}], ['due_date', 'Due date', 'date'],
    ['priority', 'Priority', 'select:task_priority'], ['task_type', 'Type', 'text', {placeholder: 'Research, follow-up, call'}],
    ['notes', 'Notes', 'textarea'],
  ];
  const NOTE_FORM = [
    ['kind', 'What happened', 'select:interaction_kind', {required: true}], ['occurred_on', 'Date', 'date'],
    ['summary', 'Summary', 'textarea'], ['outcome', 'Outcome'], ['next_action', 'Next action'],
    ['next_action_date', 'Next action date', 'date'],
  ];

  const refresh = () => loadCurrentTab();

  // ── Today: "Your BD" block at the top ──

  async function renderTodayBlock() {
    const host = document.getElementById('today');
    if (!host) return;
    let block = document.getElementById('yo-today');
    if (!block) {
      block = document.createElement('section');
      block.id = 'yo-today';
      block.className = 'yo-today';
      const head = host.querySelector('.section-head, h1');
      const anchor = head ? head.closest('.section-head') || head : null;
      if (anchor && anchor.parentNode === host) anchor.after(block); else host.prepend(block);
    }
    const [c, t] = await Promise.all([call('/counts'), call('/tasks')]);
    const due = [...t.buckets.overdue, ...t.buckets.today];
    const stat = (n, text, tab) => `<button type="button" class="yo-stat" onclick="goTab('${tab}')"><span class="yo-num">${escHtml(n)}</span><span>${escHtml(text)}</span></button>`;
    block.innerHTML = `<div class="yo-today-head"><h2>Your business development</h2><a href="#yorgs" onclick="goTab('yorgs');return false">Open Pipeline</a></div>
      <div class="yo-stats">${stat(c.organizations, 'Organizations', 'yorgs')}${stat(c.qualified, 'Qualified', 'yorgs')}${stat(c.p1, 'P1', 'yorgs')}
      ${stat(c.active_opportunities, 'Active opportunities', 'yopps')}${stat(c.tasks_due, 'Tasks due', 'ytasks')}</div>
      ${due.length ? `<div class="card yo-due"><div class="card-title">Due today and overdue</div><ul class="yo-list">${due.slice(0, 5).map(taskLine).join('')}</ul></div>` : ''}`;
    const count = document.getElementById('nav-pipeline');
    if (count) { count.textContent = c.tasks_due || ''; count.classList.toggle('on', c.tasks_due > 0); }
  }

  // ── organizations ──

  async function renderOrgs() {
    const f = state.orgs;
    const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
    const data = await call('/orgs?' + qs);
    setActions('yorgs', '<button class="btn btn-primary btn-sm" onclick="yo.addOrg()">' + icon('plus') + 'Add organization</button>');
    const sel = (name, table, text) => `<div class="form-group"><label class="form-label" for="yo-${name}">${escHtml(text)}</label>
      <select class="form-input" id="yo-${name}" onchange="yo.filter('${name}', this.value)">${options(table, f[name] || '', 'All')}</select></div>`;
    const filtered = Object.entries(f).some(([k, v]) => v && !['sort', 'dir'].includes(k));
    const rows = data.items.map(o => `<tr class="yo-row${o.archived_at ? ' yo-archived' : ''}" tabindex="0" onclick="yo.openOrg('${escHtml(o.id)}')" onkeydown="if(event.key==='Enter')yo.openOrg('${escHtml(o.id)}')">
      <td><div class="yo-name">${escHtml(o.name)}</div><div class="yo-dim">${escHtml(o.domain || 'no website')}</div></td>
      <td>${escHtml([o.city, o.country].filter(Boolean).join(', '))}</td><td>${escHtml(o.org_type)}</td><td>${prioTag(o)}</td>
      <td><div class="yo-tags">${classTag(o.competitor_class)}${o.relationship_status !== 'COLD_PROSPECT' ? `<span class="tag">${escHtml(lab('relationship_status', o.relationship_status))}</span>` : ''}</div></td>
      <td>${escHtml(lab('japan_connection', o.japan_connection))}</td>
      <td>${escHtml(o.next_action)}${o.next_action_date ? `<div class="yo-dim">${escHtml(day(o.next_action_date))}</div>` : ''}</td></tr>`).join('');
    setBody('yorgs', `<div class="card yo-filters"><div class="yo-filter-row">
        <div class="form-group yo-grow"><label class="form-label" for="yo-search">Search</label><input class="form-input" id="yo-search" type="search" value="${escHtml(f.search || '')}" placeholder="Name, website, city, industry" onchange="yo.filter('search', this.value)"></div>
        ${sel('priority', 'priority', 'Priority')}${sel('competitor_class', 'competitor_class', 'Class')}
        ${sel('relationship_status', 'relationship_status', 'Relationship')}${sel('japan_connection', 'japan_connection', 'Japan')}
        <div class="form-group"><label class="form-label" for="yo-org_type">Type</label><select class="form-input" id="yo-org_type" onchange="yo.filter('org_type', this.value)">${options('org_types', f.org_type || '', 'All')}</select></div>
        <div class="form-group"><label class="form-label" for="yo-sort">Sort</label><select class="form-input" id="yo-sort" onchange="yo.filter('sort', this.value)">
          ${[['updated', 'Recently updated'], ['added', 'Recently added'], ['name', 'Name'], ['score', 'Score'], ['next_action_date', 'Next action date'], ['city', 'City']]
            .map(([k, t]) => `<option value="${k}"${f.sort === k ? ' selected' : ''}>${t}</option>`).join('')}</select></div>
        <label class="yo-check"><input type="checkbox" ${f.archived ? 'checked' : ''} onchange="yo.filter('archived', this.checked ? '1' : '')"> Show archived</label>
      </div></div>
      ${data.items.length ? `<div class="card flush"><table><thead><tr><th>Name</th><th>Location</th><th>Type</th><th>Priority</th><th>Labels</th><th>Japan</th><th>Next action</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : filtered ? emptyState('&#128269;', 'No matches', 'No organization matches these filters. <a href="#" onclick="yo.clearFilters();return false">Clear filters</a>')
        : emptyState('&#127981;', 'No organizations yet', 'Add one by hand now. Discovery searches arrive in the next build step.')}`);
  }
  yo.filter = (name, value) => {
    state.orgs[name] = value;
    if (name === 'sort') state.orgs.dir = ['name', 'city', 'next_action_date'].includes(value) ? 'asc' : 'desc';
    renderOrgs().catch(showErr);
  };
  yo.clearFilters = () => { state.orgs = {sort: 'updated', dir: 'desc'}; renderOrgs().catch(showErr); };
  yo.addOrg = () => ready().then(() => openForm('Add organization', ORG_FORM.filter(f => f[0] !== 'crm_stage'), {}, 'Add', async data => {
    const org = await call('/orgs', 'POST', data);
    toast(`${org.name} added as ${org.id}`);
    yo.openOrg(org.id);
  }));

  async function renderOrg() {
    if (!orgId) { showTab('yorgs'); return; }
    const d = await call('/orgs/' + encodeURIComponent(orgId));
    const o = d.org;
    const co = d.cold_outreach;
    const head = document.querySelector('#yorg .section-head h1');
    if (head) head.textContent = o.name;
    const lede = document.querySelector('#yorg .section-head p');
    if (lede) lede.innerHTML = `<span class="yo-tags"><span class="tag">${escHtml(o.id)}</span>
      ${o.website ? `<a class="tag" href="${escHtml(/^https?:/i.test(o.website) ? o.website : 'https://' + o.website)}" target="_blank" rel="noopener noreferrer">${escHtml(o.domain || o.website)}</a>` : ''}
      ${o.priority ? `<span class="tag acc">${escHtml(o.priority)}</span>` : ''}${classTag(o.competitor_class)}
      <span class="tag">${escHtml(lab('relationship_status', o.relationship_status))}</span>${o.archived_at ? '<span class="tag bad">Archived</span>' : ''}</span>`;
    document.title = o.name + ' · Yoisho BD OS';
    setActions('yorg', `<button class="btn btn-secondary btn-sm" onclick="yo.editOrg()">Edit details</button>` +
      (o.archived_at ? `<button class="btn btn-secondary btn-sm" onclick="yo.restoreOrg()">Restore</button>` : `<button class="btn btn-ghost btn-sm" onclick="yo.archiveOrg()">Archive</button>`));
    const activeContacts = d.contacts.filter(c => !c.archived_at);
    const dl = [['Type', o.org_type], ['Industry', [o.industry, o.sub_industry].filter(Boolean).join(' / ')],
      ['Location', [o.city, o.state_region, o.country].filter(Boolean).join(', ')], ['CRM stage', lab('crm_stage', o.crm_stage)],
      ['Japan connection', lab('japan_connection', o.japan_connection)], ['Research', lab('research_status', o.research_status)],
      ['Score', o.opportunity_score ?? 'Not scored'], ['Last contact', day(o.last_contact) || 'None recorded'],
      ['Next action', [o.next_action, day(o.next_action_date)].filter(Boolean).join(', ') || 'None set'], ['Added', day(o.created_at)]];
    setBody('yorg', `
      <div class="yo-banner ${co.allowed ? 'good' : o.competitor_class === 'YELLOW' ? 'wait' : 'bad'}">Cold outreach: ${co.allowed ? 'allowed once qualified (email comes in Phase 2)' : escHtml(co.reason)}</div>
      <div class="yo-two">
        <div class="card"><div class="card-title">Details</div><dl class="yo-dl">${dl.map(([k, v]) => `<dt>${escHtml(k)}</dt><dd>${escHtml(v)}</dd>`).join('')}</dl>
          ${o.notes ? `<p class="yo-notes">${escHtml(o.notes)}</p>` : ''}</div>
        <div class="card"><div class="card-title">Labels</div><p class="lede">Red stops all cold outreach. Only you set Red. Every change needs a reason and is logged.</p>
          <div class="yo-grid"><div class="form-group"><label class="form-label" for="yo-class">Competitor class</label><select class="form-input" id="yo-class">${options('competitor_class', o.competitor_class)}</select></div>
          <div class="form-group"><label class="form-label" for="yo-class-reason">Reason</label><input class="form-input" id="yo-class-reason" placeholder="Why"></div></div>
          <div class="yo-actions"><button class="btn btn-secondary btn-sm" onclick="yo.saveClass()">Save class</button>${o.competitor_reason ? `<span class="yo-dim">Now: ${escHtml(o.competitor_reason)} (${escHtml(o.competitor_set_by)})</span>` : ''}</div>
          <div class="yo-grid"><div class="form-group"><label class="form-label" for="yo-rel">Relationship status</label><select class="form-input" id="yo-rel">${options('relationship_status', o.relationship_status)}</select></div>
          <div class="form-group"><label class="form-label" for="yo-rel-note">Note</label><input class="form-input" id="yo-rel-note" value="${escHtml(o.relationship_note)}"></div></div>
          <div class="yo-actions"><button class="btn btn-secondary btn-sm" onclick="yo.saveRel()">Save relationship</button></div></div>
      </div>
      <div class="card"><div class="yo-card-head"><div class="card-title">Contacts (${activeContacts.length})</div><button class="btn btn-secondary btn-sm" onclick="yo.addContact()">${icon('plus')}Add contact</button></div>
        ${d.contacts.length ? `<ul class="yo-list">${d.contacts.map(c => `<li class="${c.archived_at ? 'yo-archived' : ''}"><div><a href="#" onclick="yo.editContact('${escHtml(c.id)}');return false" class="yo-name">${escHtml(c.name)}</a>${c.is_primary ? ' <span class="tag acc">Primary</span>' : ''}
          <div class="yo-dim">${escHtml([c.job_title, c.department].filter(Boolean).join(', '))}${c.email ? ` · ${escHtml(c.email)} (${escHtml(lab('verification', c.verification_status))}, from ${escHtml(c.email_source)})` : ''}</div></div>${c.archived_at ? '<span class="yo-dim">Archived</span>' : ''}</li>`).join('')}</ul>`
          : '<p class="lede">No contacts yet. Up to 2 primary contacts. Names only from a real source, never guessed.</p>'}</div>
      <div class="card"><div class="yo-card-head"><div class="card-title">Opportunities</div><button class="btn btn-secondary btn-sm" onclick="yo.addOpp()">${icon('plus')}Add opportunity</button></div>
        ${d.opportunities.length ? `<ul class="yo-list">${d.opportunities.map(p => `<li class="${p.archived_at ? 'yo-archived' : ''}"><div><a href="#" onclick="yo.editOpp('${escHtml(p.id)}');return false" class="yo-name">${escHtml(p.name)}</a>
          <div class="yo-dim">${escHtml(lab('pillar', p.pillar))} · ${escHtml(lab('opp_stage', p.stage))}${p.next_action ? ` · Next: ${escHtml(p.next_action)}` : ''}</div></div></li>`).join('')}</ul>`
          : '<p class="lede">No opportunities yet. If there is no real opportunity, leave this empty.</p>'}</div>
      <div class="card"><div class="yo-card-head"><div class="card-title">Tasks</div><button class="btn btn-secondary btn-sm" onclick="yo.addTask('${escHtml(o.id)}')">${icon('plus')}Add task</button></div>
        ${d.tasks.length ? `<ul class="yo-list">${d.tasks.map(taskLine).join('')}</ul>` : '<p class="lede">No tasks for this organization.</p>'}</div>
      <div class="card"><div class="yo-card-head"><div class="card-title">Calls, meetings and notes</div><button class="btn btn-secondary btn-sm" onclick="yo.addNote()">${icon('plus')}Record</button></div>
        ${d.interactions.length ? `<ul class="yo-list">${d.interactions.map(i => `<li><div><span class="tag">${escHtml(lab('interaction_kind', i.kind))}</span> <span class="yo-dim">${escHtml(day(i.occurred_on))}</span>
          <div class="yo-notes">${escHtml(i.summary)}</div>${i.outcome ? `<div class="yo-dim">Outcome: ${escHtml(i.outcome)}</div>` : ''}</div></li>`).join('')}</ul>`
          : '<p class="lede">Nothing recorded yet. Record calls, meetings, introductions and notes here.</p>'}</div>
      <div class="card"><div class="card-title">Research evidence</div>
        ${d.evidence.length ? `<ul class="yo-list">${d.evidence.map(e => `<li><div><span class="tag ${e.label === 'FACT' ? 'good' : e.label === 'INFERENCE' ? 'wait' : ''}">${escHtml(lab('evidence_label', e.label))}</span> ${escHtml(e.claim)}
          ${e.source_url ? `<div class="yo-dim"><a href="${escHtml(e.source_url)}" target="_blank" rel="noopener noreferrer">${escHtml(e.source_title || e.source_url)}</a>${e.source_date ? ` · ${escHtml(e.source_date)}` : ''}</div>` : ''}</div></li>`).join('')}</ul>`
          : '<p class="lede">No research yet. Research briefs with sources arrive in a later Phase 1 step.</p>'}</div>
      <div class="card"><div class="card-title">Change log</div>
        ${d.history.length ? `<ul class="yo-list yo-small">${d.history.slice().reverse().map(h => `<li><div><b>${escHtml(h.field)}</b>: ${escHtml(h.old_value ?? '')} → ${escHtml(h.new_value ?? '')}${h.reason ? ` <span class="yo-dim">(${escHtml(h.reason)})</span>` : ''}</div><span class="yo-dim">${escHtml(h.actor)}, ${escHtml(day(h.at))}</span></li>`).join('')}</ul>` : '<p class="lede">No changes yet.</p>'}</div>`);

    yo.editOrg = () => openForm('Edit details', [...ORG_FORM, REASON], o, 'Save', async data => {
      const diff = changed(o, data);
      if (Object.keys(diff).some(k => !k.startsWith('_'))) { await call('/orgs/' + o.id, 'PATCH', diff); toast('Saved'); }
      refresh();
    });
    yo.saveClass = async () => {
      try { await call(`/orgs/${o.id}/competitor`, 'POST', {value: document.getElementById('yo-class').value, reason: document.getElementById('yo-class-reason').value}); toast('Class saved'); refresh(); }
      catch (e) { toast(e.error || 'Could not save', 'error'); }
    };
    yo.saveRel = async () => {
      try { await call(`/orgs/${o.id}/relationship`, 'POST', {value: document.getElementById('yo-rel').value, note: document.getElementById('yo-rel-note').value}); toast('Relationship saved'); refresh(); }
      catch (e) { toast(e.error || 'Could not save', 'error'); }
    };
    yo.archiveOrg = () => openForm('Archive ' + o.name, [['reason', 'Reason', 'text', {wide: true}]], {}, 'Archive', async data => {
      await call(`/orgs/${o.id}/archive`, 'POST', data); toast('Archived. Restore it any time.'); refresh();
    });
    yo.restoreOrg = async () => { await call(`/orgs/${o.id}/restore`, 'POST', {}); toast('Restored'); refresh(); };
    yo.addContact = () => openForm('Add contact', CONTACT_FORM, {verification_status: 'UNVERIFIED'}, 'Add', async data => {
      await call('/contacts', 'POST', Object.assign({org_id: o.id}, data)); toast('Contact added'); refresh();
    });
    yo.addOpp = () => openForm('Add opportunity', OPP_FORM, {stage: 'IDENTIFIED'}, 'Add', async data => {
      await call('/opportunities', 'POST', Object.assign({org_id: o.id}, data)); toast('Opportunity added'); refresh();
    });
    yo.addNote = () => openForm('Record a call, meeting or note', NOTE_FORM, {kind: 'NOTE', occurred_on: todayISO()}, 'Save', async data => {
      await call('/interactions', 'POST', Object.assign({org_id: o.id}, data)); toast('Recorded'); refresh();
    });
  }

  // ── contacts ──

  yo.editContact = async id => {
    await ready();
    const c = (await call('/contacts?archived=1')).items.find(x => x.id === id);
    if (!c) { toast('Contact not found', 'error'); return; }
    openForm(c.name, [...CONTACT_FORM, REASON], c, 'Save', async data => {
      const diff = changed(c, data);
      if (Object.keys(diff).length) await call('/contacts/' + c.id, 'PATCH', diff);
      toast('Saved'); refresh();
    }, `<div class="yo-actions">${c.archived_at ? `<button type="button" class="btn btn-secondary btn-sm" onclick="yo.contactArchive('${escHtml(c.id)}', false)">Restore contact</button>`
      : `<button type="button" class="btn btn-ghost btn-sm" onclick="yo.contactArchive('${escHtml(c.id)}', true)">Archive contact</button>`}</div>`);
  };
  yo.contactArchive = async (id, archive) => {
    try { await call(`/contacts/${id}/${archive ? 'archive' : 'restore'}`, 'POST', {reason: ''}); yo.close(); toast(archive ? 'Archived' : 'Restored'); refresh(); }
    catch (e) { toast(e.error || 'Could not save', 'error'); }
  };

  async function renderContacts() {
    const data = await call('/contacts?search=' + encodeURIComponent(state.contacts));
    setActions('ycontacts', '');
    setBody('ycontacts', `<div class="card yo-filters"><div class="yo-filter-row"><div class="form-group yo-grow"><label class="form-label" for="yo-csearch">Search</label>
      <input class="form-input" id="yo-csearch" type="search" value="${escHtml(state.contacts)}" placeholder="Name, title, email, organization" onchange="yo.contactSearch(this.value)"></div></div></div>
      ${data.items.length ? `<div class="card flush"><table><thead><tr><th>Name</th><th>Organization</th><th>Role</th><th>Email</th><th>Next follow-up</th></tr></thead><tbody>
        ${data.items.map(c => `<tr class="yo-row" tabindex="0" onclick="yo.editContact('${escHtml(c.id)}')"><td class="yo-name">${escHtml(c.name)}${c.is_primary ? ' <span class="tag acc">Primary</span>' : ''}</td>
        <td><a href="#" onclick="event.stopPropagation();yo.openOrg('${escHtml(c.org_id)}');return false">${escHtml(c.org_name)}</a></td><td>${escHtml(c.job_title)}</td>
        <td>${escHtml(c.email)}${c.email ? `<div class="yo-dim">${escHtml(lab('verification', c.verification_status))}</div>` : ''}</td><td>${escHtml(day(c.next_follow_up))}</td></tr>`).join('')}</tbody></table></div>`
        : emptyState('&#128100;', state.contacts ? 'No matches' : 'No contacts yet', state.contacts ? 'No contact matches this search.' : 'Open an organization and add its decision-makers there.')}`);
  }
  yo.contactSearch = q => { state.contacts = q; renderContacts().catch(showErr); };

  // ── opportunities ──

  yo.editOpp = async id => {
    await ready();
    const p = (await call('/opportunities?archived=1')).items.find(x => x.id === id);
    if (!p) { toast('Opportunity not found', 'error'); return; }
    openForm(p.name, [...OPP_FORM, REASON], p, 'Save', async data => {
      const diff = changed(p, data);
      if (Object.keys(diff).length) await call('/opportunities/' + p.id, 'PATCH', diff);
      toast('Saved'); refresh();
    }, `<p class="yo-dim">${escHtml(p.org_name)} · ${escHtml(p.id)}</p><div class="yo-actions">
      ${p.archived_at ? `<button type="button" class="btn btn-secondary btn-sm" onclick="yo.oppArchive('${escHtml(p.id)}', false)">Restore</button>` : `<button type="button" class="btn btn-ghost btn-sm" onclick="yo.oppArchive('${escHtml(p.id)}', true)">Archive</button>`}
      <button type="button" class="btn btn-secondary btn-sm" onclick="yo.close();yo.addTask('${escHtml(p.org_id)}','${escHtml(p.id)}')">Add task for this</button></div>`);
  };
  yo.oppArchive = async (id, archive) => {
    try { await call(`/opportunities/${id}/${archive ? 'archive' : 'restore'}`, 'POST', {reason: ''}); yo.close(); toast(archive ? 'Archived' : 'Restored'); refresh(); }
    catch (e) { toast(e.error || 'Could not save', 'error'); }
  };

  async function renderOpps() {
    const f = state.opps;
    const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
    const data = await call('/opportunities?' + qs);
    setActions('yopps', '');
    setBody('yopps', `<div class="card yo-filters"><div class="yo-filter-row">
        <div class="form-group yo-grow"><label class="form-label" for="yo-osearch">Search</label><input class="form-input" id="yo-osearch" type="search" value="${escHtml(f.search || '')}" onchange="yo.oppFilter('search', this.value)"></div>
        <div class="form-group"><label class="form-label" for="yo-pillar">Pillar</label><select class="form-input" id="yo-pillar" onchange="yo.oppFilter('pillar', this.value)">${options('pillar', f.pillar || '', 'All')}</select></div>
        <div class="form-group"><label class="form-label" for="yo-stage">Stage</label><select class="form-input" id="yo-stage" onchange="yo.oppFilter('stage', this.value)">${options('opp_stage', f.stage || '', 'All')}</select></div>
        <label class="yo-check"><input type="checkbox" ${f.active ? 'checked' : ''} onchange="yo.oppFilter('active', this.checked ? '1' : '')"> Active only</label></div></div>
      ${data.items.length ? `<div class="card flush"><table><thead><tr><th>Opportunity</th><th>Organization</th><th>Pillar</th><th>Stage</th><th>Next action</th></tr></thead><tbody>
        ${data.items.map(p => `<tr class="yo-row" tabindex="0" onclick="yo.editOpp('${escHtml(p.id)}')"><td class="yo-name">${escHtml(p.name)}</td>
        <td><a href="#" onclick="event.stopPropagation();yo.openOrg('${escHtml(p.org_id)}');return false">${escHtml(p.org_name)}</a></td>
        <td>${escHtml(lab('pillar', p.pillar))}</td><td>${escHtml(lab('opp_stage', p.stage))}</td><td>${escHtml(p.next_action)}${p.next_action_date ? `<div class="yo-dim">${escHtml(day(p.next_action_date))}</div>` : ''}</td></tr>`).join('')}</tbody></table></div>`
        : emptyState('&#127919;', 'No opportunities here', 'Add opportunities from an organization\'s page.')}`);
  }
  yo.oppFilter = (name, value) => { state.opps[name] = value; renderOpps().catch(showErr); };

  // ── tasks ──

  function taskLine(t) {
    const overdue = t.status === 'OPEN' && t.due_date && t.due_date < todayISO();
    return `<li><label class="yo-check yo-task"><input type="checkbox" ${t.status === 'DONE' ? 'checked' : ''} onchange="yo.toggleTask('${escHtml(t.id)}', this.checked)" aria-label="Done: ${escHtml(t.title)}">
      <span><span class="${t.status === 'DONE' ? 'yo-done' : ''}">${escHtml(t.title)}</span>
      <span class="yo-dim yo-block">${t.org_name ? `${escHtml(t.org_name)} · ` : ''}${t.due_date ? `<span class="${overdue ? 'yo-overdue' : ''}">${overdue ? 'Overdue, ' : 'Due '}${escHtml(day(t.due_date))}</span>` : 'No date'} · ${escHtml(lab('task_priority', t.priority))}</span></span></label>
      <button type="button" class="btn btn-ghost btn-sm" onclick="yo.editTask('${escHtml(t.id)}')">Edit</button></li>`;
  }
  yo.toggleTask = async (id, done) => {
    try { await call('/tasks/' + id, 'PATCH', {status: done ? 'DONE' : 'OPEN'}); toast(done ? 'Done' : 'Reopened'); refresh(); }
    catch (e) { toast(e.error || 'Could not save', 'error'); }
  };
  yo.editTask = async id => {
    await ready();
    const t = ((await call('/tasks?status=&search=')).items || []).find(x => x.id === id);
    if (!t) { toast('Task not found', 'error'); return; }
    openForm('Edit task', [...TASK_FORM, REASON], t, 'Save', async data => {
      const diff = changed(t, data);
      if (Object.keys(diff).length) await call('/tasks/' + t.id, 'PATCH', diff);
      toast('Saved'); refresh();
    }, `<div class="yo-actions"><button type="button" class="btn btn-ghost btn-sm" onclick="yo.taskArchive('${escHtml(t.id)}')">Archive task</button></div>`);
  };
  yo.taskArchive = async id => {
    try { await call(`/tasks/${id}/archive`, 'POST', {reason: ''}); yo.close(); toast('Archived'); refresh(); }
    catch (e) { toast(e.error || 'Could not save', 'error'); }
  };
  yo.addTask = (orgIdArg, oppId) => ready().then(() => openForm('Add task', TASK_FORM, {priority: 'MEDIUM', due_date: todayISO()}, 'Add', async data => {
    if (orgIdArg) data.org_id = orgIdArg;
    if (oppId) data.opp_id = oppId;
    await call('/tasks', 'POST', data); toast('Task added'); refresh();
  }));

  async function renderTasks() {
    const b = (await call('/tasks')).buckets;
    const total = Object.values(b).reduce((n, l) => n + l.length, 0);
    setActions('ytasks', '<button class="btn btn-primary btn-sm" onclick="yo.addTask()">' + icon('plus') + 'Add task</button>');
    const block = (title, list, note) => `<div class="card"><div class="card-title">${escHtml(title)} <span class="yo-dim">${list.length}</span></div>
      ${list.length ? `<ul class="yo-list">${list.map(taskLine).join('')}</ul>` : `<p class="lede">${escHtml(note)}</p>`}</div>`;
    setBody('ytasks', total === 0 ? emptyState('&#9989;', 'No open tasks', 'Add one here, or from an organization\'s page.')
      : block('Overdue', b.overdue, 'Nothing overdue.') + block('Today', b.today, 'Nothing due today.') +
        block('Next 7 days', b.upcoming, 'Nothing in the next 7 days.') +
        (b.later.length ? block('Later', b.later, '') : '') + (b.no_date.length ? block('No date', b.no_date, '') : ''));
  }
})();

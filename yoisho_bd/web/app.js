// Yoisho BD OS screens. Plain JavaScript, no build step.
// Every request goes through authFetch (Sellbird's auth.js): token as a
// bearer header, same origin only. Every value shown is escaped.

'use strict';

let V = null;                // reference lists from /api/yoisho/vocab
const view = document.getElementById('view');

// ── small helpers ──

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}
function label(table, code) { return (V && V[table] && V[table][code]) || code || ''; }
function opts(table, selected, blank) {
  let entries = Array.isArray(V[table]) ? V[table].map(v => [v, v]) : Object.entries(V[table]);
  // With a blank choice ("All", "Choose"), a table's own empty entry would be a second blank.
  if (blank !== undefined) entries = entries.filter(([k]) => k !== '');
  return (blank !== undefined ? `<option value="">${esc(blank)}</option>` : '') +
    entries.map(([k, v]) => `<option value="${esc(k)}"${k === selected ? ' selected' : ''}>${esc(v)}</option>`).join('');
}
function fmtDate(d) {
  if (!d) return '';
  const date = new Date(d.length <= 10 ? d + 'T00:00:00' : d);
  return isNaN(date) ? d : date.toLocaleDateString('en-IN', {day: 'numeric', month: 'short', year: 'numeric'});
}
function todayISO() {
  const parts = new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Kolkata'}).format(new Date());
  return parts;
}
function toast(message) {
  const t = document.getElementById('toast');
  t.textContent = message; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 3200);
}

async function api(path, method, data) {
  const opts = {method: method || 'GET', headers: {}};
  if (data !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(data); }
  let resp;
  try { resp = await authFetch('/api/yoisho' + path, opts); }
  catch (e) { throw {status: 0, error: 'Could not reach the server. Check the private connection window is open.'}; }
  let body = {};
  try { body = await resp.json(); } catch { /* empty */ }
  if (!resp.ok) throw Object.assign({status: resp.status}, body, {error: body.error || body.detail || `Request failed (${resp.status})`});
  return body;
}

function showError(e, where) {
  const msg = e && e.status === 401
    ? 'Signed out. Open your private dashboard link again.'
    : esc((e && e.error) || 'Something went wrong.');
  (where || view).innerHTML = `<div class="err">${msg}</div>`;
}

function empty(title, text, actionHtml) {
  return `<div class="card empty"><strong>${esc(title)}</strong>${esc(text)}${actionHtml ? `<div class="actions" style="justify-content:center">${actionHtml}</div>` : ''}</div>`;
}

// ── modal forms ──

let modalSubmit = null;
function openModal(title, html, onSubmit) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = html;
  modalSubmit = onSubmit;
  const m = document.getElementById('modal');
  m.hidden = false;
  const first = m.querySelector('input, select, textarea');
  if (first) first.focus();
}
function closeModal() { document.getElementById('modal').hidden = true; modalSubmit = null; }
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !document.getElementById('modal').hidden) closeModal(); });

// fields: [name, label, type, extra]; type: text|url|email|date|number|textarea|select:<table>|check
function formHtml(id, fields, values, submitLabel) {
  values = values || {};
  const body = fields.map(([name, text, type, extra]) => {
    const v = values[name] ?? '';
    const fid = `${id}-${name}`;
    const wide = type === 'textarea' || (extra && extra.wide) ? ' wide' : '';
    const req = extra && extra.required ? ' required' : '';
    let input;
    if (type === 'textarea') input = `<textarea id="${fid}" name="${name}"${req}>${esc(v)}</textarea>`;
    else if (type && type.startsWith('select:')) input = `<select id="${fid}" name="${name}"${req}>${opts(type.slice(7), v, extra && extra.blank !== undefined ? extra.blank : '')}</select>`;
    else if (type === 'check') return `<div class="${wide}"><label class="check"><input type="checkbox" id="${fid}" name="${name}"${v ? ' checked' : ''}> ${esc(text)}</label></div>`;
    else input = `<input id="${fid}" name="${name}" type="${type || 'text'}" value="${esc(v)}"${req}${extra && extra.placeholder ? ` placeholder="${esc(extra.placeholder)}"` : ''}>`;
    return `<div class="${wide}"><label for="${fid}">${esc(text)}${req ? ' *' : ''}</label>${input}</div>`;
  }).join('');
  return `<form id="${id}" onsubmit="return submitModal(event)"><div class="form-grid">${body}</div>
    <div id="${id}-err"></div>
    <div class="actions"><button class="btn primary" type="submit">${esc(submitLabel || 'Save')}</button>
    <button class="btn" type="button" onclick="closeModal()">Cancel</button></div></form>`;
}
function formData(form) {
  const out = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    out[el.name] = el.type === 'checkbox' ? el.checked : el.value.trim();
  }
  return out;
}
async function submitModal(event) {
  event.preventDefault();
  const form = event.target;
  const errBox = document.getElementById(form.id + '-err');
  errBox.innerHTML = '';
  const button = form.querySelector('button[type=submit]');
  button.disabled = true;
  try { await modalSubmit(formData(form)); closeModal(); }
  catch (e) {
    let html = `<div class="err">${esc(e.error || 'Could not save.')}`;
    if (e.status === 409 && e.existing) html += ` <a href="#org/${esc(e.existing.id)}" onclick="closeModal()">Open ${esc(e.existing.name)}</a>`;
    errBox.innerHTML = html + '</div>';
  } finally { button.disabled = false; }
  return false;
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

// ── field sets ──

const ORG_FORM = [
  ['name', 'Name', 'text', {required: true}], ['website', 'Website', 'text', {placeholder: 'example.com'}],
  ['org_type', 'Organization type', 'select:org_types', {blank: 'Choose'}], ['industry', 'Industry'],
  ['sub_industry', 'Sub-industry'], ['country', 'Country'], ['state_region', 'State / Prefecture'], ['city', 'City'],
  ['crm_stage', 'CRM stage', 'select:crm_stage'], ['next_action', 'Next action'],
  ['next_action_date', 'Next action date', 'date'], ['notes', 'Notes', 'textarea'],
];
const CONTACT_FORM = [
  ['name', 'Name', 'text', {required: true}], ['job_title', 'Job title'], ['department', 'Department'],
  ['email', 'Email', 'email'], ['email_source', 'Where the email came from', 'text', {placeholder: 'Company website, business card, Hunter...'}],
  ['verification_status', 'Email check', 'select:verification'], ['linkedin', 'LinkedIn URL', 'url'],
  ['country', 'Country'], ['language', 'Language'], ['relevance', 'Why this person'],
  ['next_follow_up', 'Next follow-up', 'date'], ['is_primary', 'Primary contact (2 at most per organization)', 'check'],
  ['notes', 'Notes', 'textarea'],
];
const OPP_FORM = [
  ['name', 'Opportunity', 'text', {required: true}], ['pillar', 'Pillar', 'select:pillar', {required: true, blank: 'Choose'}],
  ['opp_type', 'Type', 'text', {placeholder: 'Corporate training, student recruitment...'}],
  ['stage', 'Stage', 'select:opp_stage'], ['description', 'Description', 'textarea'],
  ['evidence', 'Evidence', 'textarea'], ['hypothesis', 'Hypothesis (not yet proven)', 'textarea'],
  ['potential_value', 'Potential value (only if known)', 'text', {placeholder: 'Leave empty if unknown'}],
  ['probability', 'Probability % (only if known)', 'number'], ['priority', 'Priority', 'select:task_priority', {blank: 'Not set'}],
  ['target_date', 'Target date', 'date'], ['next_action', 'Next action'], ['next_action_date', 'Next action date', 'date'],
  ['outcome', 'Outcome'], ['notes', 'Notes', 'textarea'],
];
const TASK_FORM = [
  ['title', 'Task', 'text', {required: true, wide: true}], ['due_date', 'Due date', 'date'],
  ['priority', 'Priority', 'select:task_priority'], ['task_type', 'Type', 'text', {placeholder: 'Research, follow-up, call...'}],
  ['notes', 'Notes', 'textarea'],
];
const NOTE_FORM = [
  ['kind', 'What happened', 'select:interaction_kind', {required: true}], ['occurred_on', 'Date', 'date'],
  ['summary', 'Summary', 'textarea'], ['outcome', 'Outcome'], ['next_action', 'Next action'],
  ['next_action_date', 'Next action date', 'date'],
];

// ── routing ──

const ROUTES = {home: renderHome, orgs: renderOrgs, org: renderOrg, contacts: renderContacts,
                opps: renderOpps, tasks: renderTasks, search: renderSearch};

function route() {
  const hash = (location.hash || '#home').slice(1);
  const [name, arg] = hash.split('/');
  const fn = ROUTES[name] || renderHome;
  document.querySelectorAll('.nav a').forEach(a => a.classList.toggle('on', a.dataset.tab === (name === 'org' ? 'orgs' : name)));
  if (!authToken()) { renderLocked(); return; }
  view.innerHTML = '<p class="loading">Loading...</p>';
  Promise.resolve(fn(decodeURIComponent(arg || ''))).catch(e => showError(e));
  view.focus({preventScroll: true});
}
window.addEventListener('hashchange', route);

function renderLocked() {
  view.innerHTML = `<div class="card locked"><h1>Locked</h1>
    <p class="lede">Open your private dashboard link to unlock Yoisho BD OS. It starts with
    <code>http://127.0.0.1:5555/#token=</code>. Keep the private connection window open on your laptop while you work.</p></div>`;
}

function doSearch(event) {
  event.preventDefault();
  const q = document.getElementById('q').value.trim();
  if (q) location.hash = 'search/' + encodeURIComponent(q);
  return false;
}

// ── home ──

async function renderHome() {
  const [counts, tasks, recent] = await Promise.all([
    api('/counts'), api('/tasks'), api('/orgs?sort=added&dir=desc')]);
  const b = tasks.buckets;
  const stat = (n, text, href) => `<a class="card stat" href="${href}" style="text-decoration:none"><div class="num">${n}</div><div class="label">${esc(text)}</div></a>`;
  const taskList = list => list.length ? `<ul class="list">${list.slice(0, 6).map(taskLine).join('')}</ul>` : '';
  const due = [...b.overdue, ...b.today];
  view.innerHTML = `
    <h1>Today</h1>
    <p class="lede">Your business development at a glance. Every number below comes from your own records.</p>
    <div class="grid stats">
      ${stat(counts.organizations, 'Organizations', '#orgs')}
      ${stat(counts.qualified, 'Qualified', '#orgs')}
      ${stat(counts.p1, 'P1 organizations', '#orgs')}
      ${stat(counts.active_opportunities, 'Active opportunities', '#opps')}
      ${stat(counts.tasks_due, 'Tasks due', '#tasks')}
    </div>
    <div class="grid two">
      <section class="card"><div class="section-head"><h3>Due today and overdue</h3><a href="#tasks" class="small">All tasks</a></div>
        ${due.length ? taskList(due) : `<p class="muted">Nothing due. ${b.upcoming.length ? `${b.upcoming.length} coming up this week.` : ''}</p>`}</section>
      <section class="card"><div class="section-head"><h3>Recently added</h3><a href="#orgs" class="small">All organizations</a></div>
        ${recent.items.length ? `<ul class="list">${recent.items.slice(0, 6).map(o => `<li><a href="#org/${esc(o.id)}" class="row-title">${esc(o.name)}</a><span class="muted small">${esc(fmtDate(o.created_at))}</span></li>`).join('')}</ul>`
          : `<p class="muted">No organizations yet. <a href="#orgs" onclick="setTimeout(addOrg,50)">Add the first one</a>. Discovery searches arrive in the next step.</p>`}</section>
    </div>`;
}

// ── organizations ──

let orgFilters = {sort: 'updated', dir: 'desc'};

async function renderOrgs() {
  const f = orgFilters;
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const data = await api('/orgs?' + qs);
  const sel = (name, table, blank) => `<div><label for="f-${name}">${esc(blank)}</label><select id="f-${name}" onchange="setOrgFilter('${name}', this.value)">${opts(table, f[name] || '', 'All')}</select></div>`;
  const rows = data.items.map(o => `
    <tr class="row${o.archived_at ? ' archived' : ''}" onclick="location.hash='org/${esc(o.id)}'">
      <td><div class="row-title">${esc(o.name)}</div><div class="muted small">${esc(o.domain || 'no website')}</div></td>
      <td>${esc([o.city, o.country].filter(Boolean).join(', '))}</td>
      <td>${esc(o.org_type)}</td>
      <td>${o.priority ? `<span class="tag ${esc(o.priority)}">${esc(o.priority)}</span>` : '<span class="muted small">Not scored</span>'}${o.opportunity_score !== null ? ` <span class="muted small">${esc(o.opportunity_score)}</span>` : ''}</td>
      <td><div class="tags"><span class="tag ${esc(o.competitor_class)}">${esc(o.competitor_class)}</span>${o.relationship_status !== 'COLD_PROSPECT' ? `<span class="tag navy">${esc(label('relationship_status', o.relationship_status))}</span>` : ''}</div></td>
      <td>${esc(label('japan_connection', o.japan_connection))}</td>
      <td>${esc(o.next_action)}${o.next_action_date ? `<div class="muted small">${esc(fmtDate(o.next_action_date))}</div>` : ''}</td>
    </tr>`).join('');
  const filtered = Object.entries(f).some(([k, v]) => v && !['sort', 'dir'].includes(k));
  view.innerHTML = `
    <div class="detail-head"><div><h1>Organizations</h1><p class="lede">Companies, schools, universities and partners. ${data.items.length} shown.</p></div>
      <button class="btn primary" onclick="addOrg()">Add organization</button></div>
    <div class="toolbar">
      <div class="grow"><label for="f-search">Search</label><input id="f-search" type="search" value="${esc(f.search || '')}" placeholder="Name, website, city, industry" onchange="setOrgFilter('search', this.value)"></div>
      ${sel('priority', 'priority', 'Priority')}
      ${sel('competitor_class', 'competitor_class', 'Class')}
      ${sel('relationship_status', 'relationship_status', 'Relationship')}
      ${sel('japan_connection', 'japan_connection', 'Japan connection')}
      <div><label for="f-org_type">Type</label><select id="f-org_type" onchange="setOrgFilter('org_type', this.value)">${opts('org_types', f.org_type || '', 'All')}</select></div>
      <div><label for="f-sort">Sort by</label><select id="f-sort" onchange="setOrgFilter('sort', this.value)">
        ${[['updated', 'Recently updated'], ['added', 'Recently added'], ['name', 'Name'], ['score', 'Score'], ['next_action_date', 'Next action date'], ['city', 'City']]
          .map(([k, t]) => `<option value="${k}"${f.sort === k ? ' selected' : ''}>${t}</option>`).join('')}</select></div>
      <label class="check"><input type="checkbox" ${f.archived ? 'checked' : ''} onchange="setOrgFilter('archived', this.checked ? '1' : '')"> Show archived</label>
    </div>
    ${data.items.length ? `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Location</th><th>Type</th><th>Priority</th><th>Labels</th><th>Japan</th><th>Next action</th></tr></thead><tbody>${rows}</tbody></table></div>`
      : filtered ? empty('No matches', 'No organization matches these filters.', `<button class="btn" onclick="orgFilters={sort:'updated',dir:'desc'};renderOrgs()">Clear filters</button>`)
      : empty('No organizations yet', 'Add one by hand now. Discovery searches arrive in the next step.', '<button class="btn primary" onclick="addOrg()">Add organization</button>')}`;
}

function setOrgFilter(name, value) {
  orgFilters[name] = value;
  if (name === 'sort') orgFilters.dir = value === 'name' || value === 'city' || value === 'next_action_date' ? 'asc' : 'desc';
  renderOrgs().catch(e => showError(e));
}

function addOrg() {
  openModal('Add organization', formHtml('f-org-new', ORG_FORM.filter(f => f[0] !== 'crm_stage'), {}, 'Add'), async data => {
    const org = await api('/orgs', 'POST', data);
    toast(`${org.name} added as ${org.id}`);
    location.hash = 'org/' + org.id;
  });
}

async function renderOrg(id) {
  const d = await api('/orgs/' + encodeURIComponent(id));
  const o = d.org;
  const co = d.cold_outreach;
  const activeContacts = d.contacts.filter(c => !c.archived_at);
  view.innerHTML = `
    <div class="crumbs"><a href="#orgs">Organizations</a></div>
    <div class="detail-head">
      <div><h1>${esc(o.name)}</h1>
        <div class="tags"><span class="tag navy">${esc(o.id)}</span>
          ${o.website ? `<a class="tag" href="${esc(/^https?:/i.test(o.website) ? o.website : 'https://' + o.website)}" target="_blank" rel="noopener noreferrer">${esc(o.domain || o.website)}</a>` : ''}
          ${o.priority ? `<span class="tag ${esc(o.priority)}">${esc(o.priority)}</span>` : ''}
          <span class="tag ${esc(o.competitor_class)}">${esc(label('competitor_class', o.competitor_class))}</span>
          <span class="tag">${esc(label('relationship_status', o.relationship_status))}</span>
          ${o.archived_at ? '<span class="tag RED">Archived</span>' : ''}</div></div>
      <div class="actions" style="margin:0">
        <button class="btn" onclick="editOrg()">Edit details</button>
        ${o.archived_at ? `<button class="btn" onclick="restoreOrg()">Restore</button>` : `<button class="btn danger" onclick="archiveOrg()">Archive</button>`}
      </div>
    </div>
    <div class="banner ${co.allowed ? 'ok' : o.competitor_class === 'YELLOW' ? 'wait' : 'stop'}">Cold outreach: ${co.allowed ? 'allowed once qualified (email arrives in Phase 2)' : esc(co.reason)}</div>

    <div class="grid two">
      <section class="card section"><h3>Details</h3>
        <dl class="small" style="display:grid;grid-template-columns:150px 1fr;gap:6px 12px;margin:0">
          ${[['Type', o.org_type], ['Industry', [o.industry, o.sub_industry].filter(Boolean).join(' / ')], ['Location', [o.city, o.state_region, o.country].filter(Boolean).join(', ')],
             ['CRM stage', label('crm_stage', o.crm_stage)], ['Japan connection', label('japan_connection', o.japan_connection)],
             ['Research', label('research_status', o.research_status)], ['Score', o.opportunity_score ?? 'Not scored'],
             ['Last contact', fmtDate(o.last_contact) || 'None recorded'], ['Next action', [o.next_action, fmtDate(o.next_action_date)].filter(Boolean).join(', ') || 'None set'],
             ['Added', fmtDate(o.created_at)]]
            .map(([k, v]) => `<dt class="muted">${esc(k)}</dt><dd style="margin:0">${esc(v)}</dd>`).join('')}
        </dl>
        ${o.notes ? `<p style="white-space:pre-wrap;margin-top:12px">${esc(o.notes)}</p>` : ''}
      </section>
      <section class="card section"><h3>Labels</h3>
        <p class="small muted">Red stops all cold outreach. Only you set Red. Every change needs a reason and is logged.</p>
        <div class="form-grid">
          <div><label for="lab-class">Competitor class</label><select id="lab-class">${opts('competitor_class', o.competitor_class)}</select></div>
          <div><label for="lab-reason">Reason</label><input id="lab-reason" placeholder="Why"></div>
        </div>
        <div class="actions"><button class="btn small" onclick="saveClass()">Save class</button>
          ${o.competitor_reason ? `<span class="muted small">Now: ${esc(o.competitor_reason)} (set by ${esc(o.competitor_set_by)})</span>` : ''}</div>
        <div class="form-grid" style="margin-top:14px">
          <div><label for="lab-rel">Relationship status</label><select id="lab-rel">${opts('relationship_status', o.relationship_status)}</select></div>
          <div><label for="lab-note">Note</label><input id="lab-note" value="${esc(o.relationship_note)}"></div>
        </div>
        <div class="actions"><button class="btn small" onclick="saveRel()">Save relationship</button></div>
      </section>
    </div>

    <section class="card section"><div class="section-head"><h3>Contacts (${activeContacts.length})</h3><button class="btn small" onclick="addContact()">Add contact</button></div>
      ${d.contacts.length ? `<ul class="list">${d.contacts.map(c => `<li class="${c.archived_at ? 'archived' : ''}"><div><a href="#" onclick="editContact('${esc(c.id)}');return false" class="row-title">${esc(c.name)}</a>${c.is_primary ? ' <span class="tag P1">Primary</span>' : ''}
        <div class="muted small">${esc([c.job_title, c.department].filter(Boolean).join(', '))}${c.email ? ` · ${esc(c.email)} (${esc(label('verification', c.verification_status))}, from ${esc(c.email_source)})` : ''}</div></div>
        ${c.archived_at ? '<span class="muted small">Archived</span>' : ''}</li>`).join('')}</ul>`
        : '<p class="muted">No contacts yet. Up to 2 primary contacts. Names only from a real source, never guessed.</p>'}
    </section>

    <section class="card section"><div class="section-head"><h3>Opportunities</h3><button class="btn small" onclick="addOpp()">Add opportunity</button></div>
      ${d.opportunities.length ? `<ul class="list">${d.opportunities.map(p => `<li class="${p.archived_at ? 'archived' : ''}"><div><a href="#" onclick="editOpp('${esc(p.id)}');return false" class="row-title">${esc(p.name)}</a>
        <div class="muted small">${esc(label('pillar', p.pillar))} · ${esc(label('opp_stage', p.stage))}${p.next_action ? ` · Next: ${esc(p.next_action)}` : ''}</div></div></li>`).join('')}</ul>`
        : '<p class="muted">No opportunities yet. If there is no real opportunity, leave this empty.</p>'}
    </section>

    <section class="card section"><div class="section-head"><h3>Tasks</h3><button class="btn small" onclick="addTask('${esc(o.id)}')">Add task</button></div>
      ${d.tasks.length ? `<ul class="list">${d.tasks.map(taskLine).join('')}</ul>` : '<p class="muted">No tasks for this organization.</p>'}
    </section>

    <section class="card section"><div class="section-head"><h3>Calls, meetings and notes</h3><button class="btn small" onclick="addNote()">Record</button></div>
      ${d.interactions.length ? `<ul class="list">${d.interactions.map(i => `<li><div><span class="tag">${esc(label('interaction_kind', i.kind))}</span> <span class="muted small">${esc(fmtDate(i.occurred_on))}</span>
        <div style="white-space:pre-wrap">${esc(i.summary)}</div>${i.outcome ? `<div class="small muted">Outcome: ${esc(i.outcome)}</div>` : ''}</div></li>`).join('')}</ul>`
        : '<p class="muted">Nothing recorded yet. Record calls, meetings, introductions and notes here.</p>'}
    </section>

    <section class="card section"><h3>Research evidence</h3>
      ${d.evidence.length ? `<ul class="list">${d.evidence.map(e => `<li><div><span class="tag ${e.label === 'FACT' ? 'GREEN' : e.label === 'INFERENCE' ? 'YELLOW' : ''}">${esc(label('evidence_label', e.label))}</span> ${esc(e.claim)}
        ${e.source_url ? `<div class="small"><a href="${esc(e.source_url)}" target="_blank" rel="noopener noreferrer">${esc(e.source_title || e.source_url)}</a>${e.source_date ? ` · ${esc(e.source_date)}` : ''}</div>` : ''}</div></li>`).join('')}</ul>`
        : '<p class="muted">No research yet. Research briefs with sources arrive in a later Phase 1 step.</p>'}
    </section>

    <section class="card section"><h3>Change log</h3>
      ${d.history.length ? `<ul class="list small">${d.history.slice().reverse().map(h => `<li><div><strong>${esc(h.field)}</strong>: ${esc(h.old_value ?? '')} → ${esc(h.new_value ?? '')}${h.reason ? ` <span class="muted">(${esc(h.reason)})</span>` : ''}</div><span class="muted">${esc(h.actor)}, ${esc(fmtDate(h.at))}</span></li>`).join('')}</ul>` : '<p class="muted">No changes yet.</p>'}
    </section>`;

  const reload = () => renderOrg(id).catch(e => showError(e));
  window.editOrg = () => openModal('Edit details', formHtml('f-org-edit', [...ORG_FORM, ['_reason', 'Reason for the change (optional)', 'text', {wide: true}]], o), async data => {
    const diff = changed(o, data);
    if (!Object.keys(diff).filter(k => !k.startsWith('_')).length) return;
    await api('/orgs/' + o.id, 'PATCH', diff); toast('Saved'); reload();
  });
  window.saveClass = async () => {
    try { await api(`/orgs/${o.id}/competitor`, 'POST', {value: document.getElementById('lab-class').value, reason: document.getElementById('lab-reason').value}); toast('Class saved'); reload(); }
    catch (e) { toast(e.error || 'Could not save'); }
  };
  window.saveRel = async () => {
    try { await api(`/orgs/${o.id}/relationship`, 'POST', {value: document.getElementById('lab-rel').value, note: document.getElementById('lab-note').value}); toast('Relationship saved'); reload(); }
    catch (e) { toast(e.error || 'Could not save'); }
  };
  window.archiveOrg = () => openModal('Archive organization', formHtml('f-arch', [['reason', 'Reason', 'text', {wide: true}]], {}, 'Archive'), async data => {
    await api(`/orgs/${o.id}/archive`, 'POST', data); toast('Archived. Restore it any time.'); reload();
  });
  window.restoreOrg = async () => { await api(`/orgs/${o.id}/restore`, 'POST', {}); toast('Restored'); reload(); };
  window.addContact = () => openModal('Add contact', formHtml('f-con-new', CONTACT_FORM, {verification_status: 'UNVERIFIED'}, 'Add'), async data => {
    await api('/contacts', 'POST', Object.assign({org_id: o.id}, data)); toast('Contact added'); reload();
  });
  window.addOpp = () => openModal('Add opportunity', formHtml('f-opp-new', OPP_FORM, {stage: 'IDENTIFIED'}, 'Add'), async data => {
    await api('/opportunities', 'POST', Object.assign({org_id: o.id}, data)); toast('Opportunity added'); reload();
  });
  window.addNote = () => openModal('Record a call, meeting or note', formHtml('f-note', NOTE_FORM, {kind: 'NOTE', occurred_on: todayISO()}, 'Save'), async data => {
    await api('/interactions', 'POST', Object.assign({org_id: o.id}, data)); toast('Recorded'); reload();
  });
  window.afterChange = reload;
}

// ── contacts ──

async function editContact(id, after) {
  const c = (await api('/contacts?archived=1&search=')).items.find(x => x.id === id);
  if (!c) { toast('Contact not found'); return; }
  const done = after || window.afterChange || route;
  openModal(`${c.name}`, formHtml('f-con-edit', [...CONTACT_FORM, ['_reason', 'Reason for the change (optional)', 'text', {wide: true}]], c) +
    `<div class="actions">${c.archived_at ? `<button class="btn" onclick="contactArchive('${esc(c.id)}', false)">Restore contact</button>` : `<button class="btn danger" onclick="contactArchive('${esc(c.id)}', true)">Archive contact</button>`}</div>`,
    async data => { const diff = changed(c, data); if (Object.keys(diff).length) await api('/contacts/' + c.id, 'PATCH', diff); toast('Saved'); done(); });
  window.contactArchive = async (cid, archive) => {
    try { await api(`/contacts/${cid}/${archive ? 'archive' : 'restore'}`, 'POST', {reason: ''}); closeModal(); toast(archive ? 'Archived' : 'Restored'); done(); }
    catch (e) { toast(e.error || 'Could not save'); }
  };
}

async function renderContacts() {
  const search = renderContacts.q || '';
  const data = await api('/contacts?search=' + encodeURIComponent(search));
  window.afterChange = () => renderContacts().catch(e => showError(e));
  view.innerHTML = `<h1>Contacts</h1><p class="lede">Decision-makers at your organizations. Add contacts from an organization's page.</p>
    <div class="toolbar"><div class="grow"><label for="c-search">Search</label><input id="c-search" type="search" value="${esc(search)}" placeholder="Name, title, email, organization" onchange="renderContacts.q=this.value;renderContacts().catch(e=>showError(e))"></div></div>
    ${data.items.length ? `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Organization</th><th>Role</th><th>Email</th><th>Next follow-up</th></tr></thead><tbody>
      ${data.items.map(c => `<tr class="row" onclick="editContact('${esc(c.id)}')"><td class="row-title">${esc(c.name)}${c.is_primary ? ' <span class="tag P1">Primary</span>' : ''}</td>
      <td><a href="#org/${esc(c.org_id)}" onclick="event.stopPropagation()">${esc(c.org_name)}</a></td><td>${esc(c.job_title)}</td>
      <td>${esc(c.email)}${c.email ? `<div class="muted small">${esc(label('verification', c.verification_status))}</div>` : ''}</td><td>${esc(fmtDate(c.next_follow_up))}</td></tr>`).join('')}</tbody></table></div>`
      : empty(search ? 'No matches' : 'No contacts yet', search ? 'No contact matches this search.' : 'Open an organization and add its decision-makers there.')}`;
}

// ── opportunities ──

async function editOpp(id, after) {
  const p = (await api('/opportunities?archived=1')).items.find(x => x.id === id);
  if (!p) { toast('Opportunity not found'); return; }
  const done = after || window.afterChange || route;
  openModal(p.name, `<p class="small muted">${esc(p.org_name)} · ${esc(p.id)}</p>` + formHtml('f-opp-edit', [...OPP_FORM, ['_reason', 'Reason for the change (optional)', 'text', {wide: true}]], p) +
    `<div class="actions">${p.archived_at ? `<button class="btn" onclick="oppArchive('${esc(p.id)}', false)">Restore</button>` : `<button class="btn danger" onclick="oppArchive('${esc(p.id)}', true)">Archive</button>`}
      <button class="btn" onclick="closeModal();addTask('${esc(p.org_id)}','${esc(p.id)}')">Add task for this</button></div>`,
    async data => { const diff = changed(p, data); if (Object.keys(diff).length) await api('/opportunities/' + p.id, 'PATCH', diff); toast('Saved'); done(); });
  window.oppArchive = async (oid, archive) => {
    try { await api(`/opportunities/${oid}/${archive ? 'archive' : 'restore'}`, 'POST', {reason: ''}); closeModal(); toast(archive ? 'Archived' : 'Restored'); done(); }
    catch (e) { toast(e.error || 'Could not save'); }
  };
}

let oppFilters = {active: '1'};
async function renderOpps() {
  const qs = new URLSearchParams(Object.entries(oppFilters).filter(([, v]) => v)).toString();
  const data = await api('/opportunities?' + qs);
  window.afterChange = () => renderOpps().catch(e => showError(e));
  view.innerHTML = `<h1>Opportunities</h1><p class="lede">Learn, Study and Work opportunities. Values and probabilities stay empty until you know them.</p>
    <div class="toolbar">
      <div class="grow"><label for="o-search">Search</label><input id="o-search" type="search" value="${esc(oppFilters.search || '')}" onchange="oppFilters.search=this.value;renderOpps().catch(e=>showError(e))"></div>
      <div><label for="o-pillar">Pillar</label><select id="o-pillar" onchange="oppFilters.pillar=this.value;renderOpps().catch(e=>showError(e))">${opts('pillar', oppFilters.pillar || '', 'All')}</select></div>
      <div><label for="o-stage">Stage</label><select id="o-stage" onchange="oppFilters.stage=this.value;renderOpps().catch(e=>showError(e))">${opts('opp_stage', oppFilters.stage || '', 'All')}</select></div>
      <label class="check"><input type="checkbox" ${oppFilters.active ? 'checked' : ''} onchange="oppFilters.active=this.checked?'1':'';renderOpps().catch(e=>showError(e))"> Active only</label>
    </div>
    ${data.items.length ? `<div class="table-wrap"><table><thead><tr><th>Opportunity</th><th>Organization</th><th>Pillar</th><th>Stage</th><th>Next action</th></tr></thead><tbody>
      ${data.items.map(p => `<tr class="row" onclick="editOpp('${esc(p.id)}')"><td class="row-title">${esc(p.name)}</td><td><a href="#org/${esc(p.org_id)}" onclick="event.stopPropagation()">${esc(p.org_name)}</a></td>
      <td>${esc(label('pillar', p.pillar))}</td><td>${esc(label('opp_stage', p.stage))}</td><td>${esc(p.next_action)}${p.next_action_date ? `<div class="muted small">${esc(fmtDate(p.next_action_date))}</div>` : ''}</td></tr>`).join('')}</tbody></table></div>`
      : empty('No opportunities here', 'Add opportunities from an organization\'s page.')}`;
}

// ── tasks ──

function taskLine(t) {
  const overdue = t.status === 'OPEN' && t.due_date && t.due_date < todayISO();
  return `<li><label class="check" style="flex:1"><input type="checkbox" ${t.status === 'DONE' ? 'checked' : ''} onchange="toggleTask('${esc(t.id)}', this.checked)" aria-label="Done: ${esc(t.title)}">
    <span><span class="${t.status === 'DONE' ? 'muted' : ''}" style="${t.status === 'DONE' ? 'text-decoration:line-through' : ''}">${esc(t.title)}</span>
    <span class="muted small" style="display:block">${t.org_name ? `${esc(t.org_name)} · ` : ''}${t.due_date ? `<span style="${overdue ? 'color:var(--bad);font-weight:600' : ''}">${overdue ? 'Overdue, ' : 'Due '}${esc(fmtDate(t.due_date))}</span>` : 'No date'} · ${esc(label('task_priority', t.priority))}</span></span></label>
    <button class="btn small" onclick="editTask('${esc(t.id)}')">Edit</button></li>`;
}

async function toggleTask(id, done) {
  try { await api('/tasks/' + id, 'PATCH', {status: done ? 'DONE' : 'OPEN'}); toast(done ? 'Done' : 'Reopened'); (window.afterChange || route)(); }
  catch (e) { toast(e.error || 'Could not save'); }
}

async function editTask(id) {
  const all = await api('/tasks?status=&search=');
  const t = (all.items || []).find(x => x.id === id);
  if (!t) { toast('Task not found'); return; }
  openModal('Edit task', formHtml('f-task-edit', [...TASK_FORM, ['_reason', 'Reason for the change (optional)', 'text', {wide: true}]], t) +
    `<div class="actions"><button class="btn danger" onclick="taskArchive('${esc(t.id)}')">Archive task</button></div>`,
    async data => { const diff = changed(t, data); if (Object.keys(diff).length) await api('/tasks/' + t.id, 'PATCH', diff); toast('Saved'); (window.afterChange || route)(); });
  window.taskArchive = async tid => {
    try { await api(`/tasks/${tid}/archive`, 'POST', {reason: ''}); closeModal(); toast('Archived'); (window.afterChange || route)(); }
    catch (e) { toast(e.error || 'Could not save'); }
  };
}

function addTask(orgId, oppId) {
  openModal('Add task', formHtml('f-task-new', TASK_FORM, {priority: 'MEDIUM', due_date: todayISO()}, 'Add'), async data => {
    if (orgId) data.org_id = orgId;
    if (oppId) data.opp_id = oppId;
    await api('/tasks', 'POST', data); toast('Task added'); (window.afterChange || route)();
  });
}

async function renderTasks() {
  const data = await api('/tasks');
  const b = data.buckets;
  window.afterChange = () => renderTasks().catch(e => showError(e));
  const block = (title, list, note) => `<section class="card section"><h3>${esc(title)} (${list.length})</h3>${list.length ? `<ul class="list">${list.map(taskLine).join('')}</ul>` : `<p class="muted">${esc(note)}</p>`}</section>`;
  const total = Object.values(b).reduce((n, l) => n + l.length, 0);
  view.innerHTML = `<div class="detail-head"><div><h1>Tasks</h1><p class="lede">${total} open. Tick a task to complete it, or Edit to reschedule.</p></div>
    <button class="btn primary" onclick="addTask()">Add task</button></div>
    ${block('Overdue', b.overdue, 'Nothing overdue.')}
    ${block('Today', b.today, 'Nothing due today.')}
    ${block('Next 7 days', b.upcoming, 'Nothing in the next 7 days.')}
    ${b.later.length ? block('Later', b.later, '') : ''}
    ${b.no_date.length ? block('No date', b.no_date, '') : ''}`;
}

// ── search ──

async function renderSearch(q) {
  document.getElementById('q').value = q;
  const r = await api('/search?q=' + encodeURIComponent(q));
  window.afterChange = () => renderSearch(q).catch(e => showError(e));
  const n = r.organizations.length + r.contacts.length + r.opportunities.length + r.tasks.length;
  const group = (title, items, line) => items.length ? `<section class="card section"><h3>${esc(title)} (${items.length})</h3><ul class="list">${items.map(line).join('')}</ul></section>` : '';
  view.innerHTML = `<h1>Search: ${esc(q)}</h1><p class="lede">${n} result${n === 1 ? '' : 's'}.</p>
    ${n ? '' : empty('Nothing found', 'Try a shorter word, a city, or part of a website.')}
    ${group('Organizations', r.organizations, o => `<li><a class="row-title" href="#org/${esc(o.id)}">${esc(o.name)}</a><span class="muted small">${esc(o.city)}</span></li>`)}
    ${group('Contacts', r.contacts, c => `<li><a class="row-title" href="#" onclick="editContact('${esc(c.id)}');return false">${esc(c.name)}</a><span class="muted small">${esc(c.org_name)}</span></li>`)}
    ${group('Opportunities', r.opportunities, p => `<li><a class="row-title" href="#" onclick="editOpp('${esc(p.id)}');return false">${esc(p.name)}</a><span class="muted small">${esc(p.org_name)}</span></li>`)}
    ${group('Tasks', r.tasks, taskLine)}`;
}

// ── start ──

(async function start() {
  if (!authToken() && !_pendingSignIn) { renderLocked(); return; }
  try { V = await api('/vocab'); }
  catch (e) { if (e.status === 401) { clearAuthToken(); renderLocked(); return; } showError(e); return; }
  route();
})();

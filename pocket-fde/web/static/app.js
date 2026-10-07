const $ = (id) => document.getElementById(id);
const state = { cases: [], selected: null, status: null, busy: false, result: null };
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const prose = (value) => escapeHTML(value).replace(/\[([A-Za-z0-9_:.\/-]+)\]/g, '<span class="citation">[$1]</span>');
const initialAnalysis = $('analysis-content').innerHTML;
const DRAFT_KEY = 'pocketfde.workspace.v1';
let drafts = { selected: null, entries: {} };
const brain = { data: null, filter: 'approved', selected: null, open: false, loading: false };
let accessDestination = null;
try { const saved = JSON.parse(localStorage.getItem(DRAFT_KEY)); if (saved?.entries) drafts = saved; } catch { /* Storage may be disabled. */ }
function rememberDraft() {
  if (!state.status) return;
  const id = state.selected?.id || 'CUSTOM';
  drafts.selected = id;
  drafts.entries[id] = { incident: { title: $('issue-title').value, description: $('description').value,
    version: $('version').value, customer_tier: $('customer-tier').value, evidence: $('evidence').value },
    retrieval: $('retrieval-mode').value, result: state.result, touched: Date.now() };
  const recent = Object.entries(drafts.entries).sort((a,b) => b[1].touched - a[1].touched).slice(0,20);
  drafts.entries = Object.fromEntries(recent);
  try { localStorage.setItem(DRAFT_KEY, JSON.stringify(drafts)); }
  catch { $('save-note').textContent = 'Browser storage is unavailable. Copy your analysis before leaving.'; }
}
function restoreDraft(draft) {
  if (!draft?.incident) return;
  const incident = draft.incident;
  $('issue-title').value = incident.title; $('description').value = incident.description;
  $('version').value = incident.version || ''; $('customer-tier').value = incident.customer_tier;
  $('evidence').value = incident.evidence;
  if (state.status.retrieval_modes.some((m) => m.id === draft.retrieval && m.ready)) $('retrieval-mode').value = draft.retrieval;
  updateSearchMode(); $('version-help').hidden = !!$('version').value;
  if (draft.result) renderAnalysis(draft.result);
}
async function refreshHistory() {
  if (state.status?.access_required) return;
  try {
    const data = await api('/api/history');
    $('saved-analysis').innerHTML = '<option value="">Your recent work</option>' + data.records.map((r) => `<option value="${escapeHTML(r.id)}">${escapeHTML(r.title)} · ${r.retrieval_mode === 'hybrid' ? 'Hybrid' : 'Keyword'}</option>`).join('');
  } catch (error) { $('save-note').textContent = error.message; }
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 400000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal, headers: { 'Content-Type': 'application/json', ...options.headers } });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401 && path !== '/api/access' && state.status) {
        state.status.access_required = true;
        state.status.model.ready = false;
        $('model-status').textContent = 'Unlock live demo';
      }
      const message = Array.isArray(data.detail) ? data.detail.map((e) => e.msg).join('; ') : data.detail;
      throw new Error(message || 'The request could not finish. Try again.');
    }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out. Please try again.');
    if (error instanceof TypeError) throw new Error('Cannot reach the app. Check that the local server is running.');
    throw error;
  } finally { clearTimeout(timeout); }
}

function showError(id, message) { $(id).textContent = message; $(id).hidden = !message; }
function updateStatus(status) {
  state.status = status;
  $('model-status').textContent = status.access_required ? 'Unlock live demo' : status.model.ready ? `${status.model.label} connected` : 'Connect a model';
  $('model-status-dot').classList.toggle('connected', status.model.ready);
  $('card-count').textContent = status.cards;
  $('knowledge-count').textContent = `${status.knowledge_items} knowledge items · ${status.cards} reviewed cards · ${status.notes} learning notes`;
  $('case-count').textContent = state.cases.length;
  const selected = $('retrieval-mode').value;
  $('retrieval-mode').innerHTML = status.retrieval_modes.map((mode) => `<option value="${escapeHTML(mode.id)}" ${mode.ready ? '' : 'disabled'}>${escapeHTML(mode.label)}${mode.ready ? '' : ' — setup needed'}</option>`).join('');
  $('retrieval-mode').value = status.retrieval_modes.some((m) => m.id === selected && m.ready) ? selected : 'surya';
  updateSearchMode();
}
function updateSearchMode() {
  const mode = state.status?.retrieval_modes.find((m) => m.id === $('retrieval-mode').value);
  if (!mode) return;
  $('pipeline-tag').textContent = mode.label;
  $('method-name').textContent = mode.label;
  $('method-description').textContent = mode.description;
}
function renderCases() {
  const query = $('case-search').value.toLowerCase();
  const filtered = state.cases.filter((c) => `${c.id} ${c.title}`.toLowerCase().includes(query));
  $('case-list').innerHTML = filtered.map((c) => `<button type="button" class="case-item ${state.selected?.id === c.id ? 'active' : ''}" data-case="${escapeHTML(c.id)}" aria-pressed="${state.selected?.id === c.id}"><span class="case-meta"><strong>${escapeHTML(c.id)}</strong><span>${escapeHTML(c.version || 'Version unknown')}</span></span><span class="case-item-title">${escapeHTML(c.title)}</span></button>`).join('') || '<p class="sidebar-muted">No matching cases.</p>';
  $('case-list').querySelectorAll('button').forEach((button) => button.addEventListener('click', () => {
    if (!state.busy) { showWorkspace('triage'); selectCase(state.cases.find((c) => c.id === button.dataset.case)); }
  }));
}
function resetOutput() {
  state.result = null;
  $('analysis-content').innerHTML = initialAnalysis;
  $('analysis-status').textContent = 'Ready when you are';
  $('source-count').textContent = 'Not retrieved yet';
  $('source-list').innerHTML = '<p class="sources-empty">Inspect sources to see the knowledge matched to this incident. No model connection required.</p>';
  showError('form-error', '');
  $('version-help').hidden = !!$('version').value;
}
function selectCase(selected) {
  state.selected = selected || null;
  $('selected-case').textContent = selected?.id || 'CUSTOM ISSUE';
  $('issue-title').value = selected?.title || '';
  $('description').value = selected?.description || '';
  $('version').value = selected?.version || '';
  $('customer-tier').value = selected?.customer_tier || 'standard';
  $('evidence').value = (selected?.provided_evidence || []).join('\n');
  $('case-status').hidden = !['CLOSED', 'RESOLVED'].includes(selected?.status);
  $('case-status').textContent = 'Resolved case — you’re analyzing the original incident report.';
  renderCases(); resetOutput();
  restoreDraft(drafts.entries[selected?.id || 'CUSTOM']);
  rememberDraft();
}
function inputPayload() {
  if (!$('incident-form').reportValidity()) return null;
  const incident = {
    id: state.selected?.id || 'CUSTOM', title: $('issue-title').value.trim(),
    description: $('description').value.trim(), version: $('version').value || null,
    customer_tier: $('customer-tier').value,
    provided_evidence: $('evidence').value.split('\n').map((s) => s.trim()).filter(Boolean),
  };
  const original = state.selected;
  const unchanged = original && ['title', 'description', 'version', 'customer_tier'].every((k) => original[k] === incident[k]) && JSON.stringify(original.provided_evidence) === JSON.stringify(incident.provided_evidence);
  const retrieval = $('retrieval-mode').value;
  return unchanged ? { case_id: original.id, retrieval } : { incident, retrieval };
}
function busy(value, analyzing = false) {
  state.busy = value;
  $('incident-form').querySelectorAll('input,select,textarea,button').forEach((el) => el.disabled = value);
  $('new-case').disabled = value;
  $('analysis-content').parentElement.setAttribute('aria-busy', String(value && analyzing));
  $('analyze-button').innerHTML = value && analyzing ? 'Analyzing…' : '<span class="button-icon" aria-hidden="true">✦</span> Analyze incident';
  $('inspect-button').textContent = value && !analyzing ? 'Retrieving…' : 'Inspect sources';
}
function renderSources(sources) {
  $('source-count').textContent = `${sources.length} matches`;
  $('source-list').innerHTML = sources.length ? sources.map((s) => `<details class="source-item"><summary><strong class="source-id">${escapeHTML(s.id)}</strong><span class="source-kind">${escapeHTML(s.kind)}</span><span class="source-version ${s.version_match ? '' : 'source-caveat'}">${!s.versions.length ? 'Version scope unconfirmed' : s.version_match === null ? 'Confirm version' : s.version_match ? escapeHTML(s.versions.join(' / ')) : 'Different version'}</span></summary><pre>${s.source_path ? 'Source: ' + escapeHTML(s.source_path) + '\n\n' : ''}${escapeHTML(s.text)}${s.caveat ? '\n\nCaveat: ' + escapeHTML(s.caveat) : ''}</pre></details>`).join('') : '<p class="sources-empty">No relevant knowledge was found for this incident.</p>';
}
function renderAnalysis(data) {
  state.result = data;
  const r = data.result;
  $('analysis-status').textContent = r.escalate ? 'Needs investigation' : 'Analysis complete';
  const questions = `<section class="analysis-section"><h3>Questions to move this forward</h3>${r.questions.length ? `<ol>${r.questions.map((q) => `<li>${prose(q.text)}</li>`).join('')}</ol>` : '<p>No usable diagnostic questions were returned. This analysis needs review before applying a fix.</p>'}</section>`;
  const logs = r.logs_to_check.length ? `<section class="analysis-section"><h3>Logs to check</h3>${r.logs_to_check.map((l) => `<div class="log-row"><code>${escapeHTML(l.stream)}</code><span>${l.on_in_prod ? 'On in production' : 'Enable first'}</span></div>${l.on_in_prod ? '' : `<p class="log-help">Enable ${escapeHTML(l.enable_flag)}. ${escapeHTML(l.caveat)}</p>`}`).join('')}</section>` : '';
  const caveat = r.version_caveat ? `<section class="analysis-section"><h3>Version considerations</h3><p>${prose(r.version_caveat)}</p></section>` : '';
  const doNot = r.do_not_apply.length ? `<section class="analysis-section"><h3>Avoid for this version</h3><p>${r.do_not_apply.map(prose).join('<br>')}</p></section>` : '';
  const handover = r.handover ? `<section class="analysis-section"><details><summary>Team handover brief</summary>${Object.entries(r.handover).filter(([k,v]) => v && !['case_id','bounces'].includes(k)).map(([k,v]) => `<p><strong>${escapeHTML(k.replaceAll('_', ' '))}:</strong> ${prose(Array.isArray(v) ? v.join(', ') : v)}</p>`).join('')}</details></section>` : '';
  $('analysis-content').innerHTML = `<div class="analysis-body">${r.escalate ? `<div class="escalation"><strong>Further investigation needed.</strong><br>${prose(r.escalation_reason || 'The available evidence does not support a confident conclusion.')}</div>` : ''}<div class="owner-block"><span class="owner-label">${r.escalate ? 'Owner hypothesis' : 'Likely owner'}</span><div class="owner-team">${r.owning_team ? 'Team ' + escapeHTML(r.owning_team) : 'Unassigned'}<span class="confidence ${escapeHTML(r.confidence)}">${escapeHTML(r.confidence)} confidence</span></div><div class="owner-name">${escapeHTML(data.team_name || 'Collect more evidence before assigning')}</div><div class="owner-contact">${escapeHTML(r.owner_contact || '')}</div></div><section class="analysis-section"><h3>Why this team</h3><p>${prose(r.reasoning || 'No supported explanation was returned.')}</p></section>${questions}${logs}${r.recommended_fix ? `<section class="analysis-section"><h3>Suggested next step</h3><p>${prose(r.recommended_fix)}</p></section>` : ''}${caveat}${doNot}${handover}${r.grounding_issues.length ? `<section class="analysis-section"><h3>Verification notes</h3><p>${r.grounding_issues.map(prose).join('<br>')}</p></section>` : ''}<div class="metrics"><span><strong>${Number(r.cost.tokens).toLocaleString()}</strong> measured tokens</span><span><strong>${Number(data.elapsed_s).toFixed(1)}s</strong> elapsed</span><span>${escapeHTML(data.provider)} · ${escapeHTML(data.model)}</span></div><div class="result-actions"><button type="button" class="text-button" id="copy-result">Copy analysis</button></div></div>`;
  $('copy-result').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      $('copy-result').textContent = 'Copied';
    } catch { $('copy-result').textContent = 'Copy unavailable in this browser'; }
  });
  renderSources(data.sources);
  const method = document.createElement('span');
  method.textContent = state.status.retrieval_modes.find((m) => m.id === data.retrieval_mode)?.label || data.retrieval;
  $('analysis-content').querySelector('.metrics').appendChild(method);
  if (data.fallback_used) {
    const fallback = document.createElement('span');
    fallback.textContent = 'Fallback model used because primary quota or availability was limited.';
    $('analysis-content').querySelector('.metrics').appendChild(fallback);
  }
  renderLearningStatus(data);
  $('save-note').textContent = data.save_status || 'Restored analysis. Review the evidence before applying a fix.';
  if (data.knowledge_revision !== state.status.knowledge_revision) $('save-note').textContent = 'Saved with an earlier knowledge revision. Analyze again for current guidance.';
}
function renderLearningStatus(data) {
  const old = $('analysis-content').querySelector('.learning-status');
  if (old) old.remove();
  if (!data.learning) return;
  const note = data.learning;
  const section = document.createElement('section');
  section.className = 'analysis-section learning-status';
  const text = note.status === 'failed' ? note.message : note.status === 'pending' ?
    (note.created ? 'A provisional learning was automatically saved to Needs review.' : 'This investigation already has a learning in Needs review.') :
    `This investigation's learning has already been ${note.status}. Its review decision is preserved.`;
  section.innerHTML = `<h3>Second Brain</h3><p>${escapeHTML(text)} ${note.status === 'pending' ? 'It stays out of both search modes until a human approves it.' : ''}</p>${note.id ? '<button type="button" class="text-button" id="review-auto-learning">View learning</button>' : data.saved_id ? '<button type="button" class="text-button" id="retry-auto-learning">Retry saving learning</button>' : ''}`;
  $('analysis-content').querySelector('.analysis-body').appendChild(section);
  if (note.id) $('review-auto-learning').addEventListener('click', async () => {
    showWorkspace('brain');
    $('brain-search').value = ''; $('brain-version').value = '';
    await loadBrain();
    const current = brain.data?.learnings.find((entry) => entry.id === note.id);
    if (current) {
      brain.filter = current.status;
      brain.selected = current.status === 'approved' ? 'WEB-NOTE:' + note.id : note.id;
      renderBrain();
    }
  });
  if (!note.id && data.saved_id) $('retry-auto-learning').addEventListener('click', async () => {
    const button = $('retry-auto-learning'); button.disabled = true;
    try {
      data.learning = await api(`/api/history/${encodeURIComponent(data.saved_id)}/learning`, {method:'POST'});
      renderLearningStatus(data); rememberDraft();
    } catch (error) { section.querySelector('p').textContent = error.message; button.disabled = false; }
  });
}
async function runAction(analyzing) {
  const payload = inputPayload();
  if (!payload || state.busy) return;
  showError('form-error', '');
  if (analyzing && !payload.incident?.version && !$('version').value) {
    showError('form-error', 'Confirm the platform version before analyzing. You can still inspect sources.');
    $('version').focus(); return;
  }
  if (analyzing && state.status?.access_required) { $('access-dialog').showModal(); return; }
  if (analyzing && !state.status?.model.ready) { openSettings(); return; }
  busy(true, analyzing);
  if (analyzing) {
    state.result = null;
    $('analysis-status').textContent = 'Working on it';
    $('analysis-content').innerHTML = '<div class="loading-analysis"><div class="loading-spinner" aria-hidden="true"></div><strong>Connecting the evidence.</strong><br>Retrieving knowledge and asking the model<br>to identify the owner and next steps.</div>';
  }
  try {
    const data = await api(analyzing ? '/api/analyze' : '/api/context', { method: 'POST', body: JSON.stringify(payload) });
    analyzing ? renderAnalysis(data) : renderSources(data.sources);
  } catch (error) {
    showError('form-error', error.message);
    if (analyzing) {
      $('analysis-status').textContent = 'Could not complete';
      $('analysis-content').innerHTML = `<div class="empty-analysis"><div class="empty-icon">!</div><h3>Let’s check the connection.</h3><p>${escapeHTML(error.message)}</p></div>`;
    }
  } finally { busy(false); rememberDraft(); if (analyzing) refreshHistory(); }
}
function providerChanged() {
  const selected = state.status.providers.find((p) => p.id === $('provider').value);
  $('model-id').value = selected.default_model;
  const local = selected.id === 'claude_cli';
  $('api-key-group').hidden = local; $('claude-help').hidden = !local;
  $('api-key').value = '';
  showError('settings-error', '');
}
function openSettings() {
  if (!state.status) return;
  if (state.status.access_required) { $('access-dialog').showModal(); return; }
  $('provider').value = state.status.model.provider;
  providerChanged();
  $('model-id').value = state.status.model.model;
  $('settings-dialog').showModal();
}
$('incident-form').addEventListener('submit', (event) => { event.preventDefault(); runAction(true); });
$('inspect-button').addEventListener('click', () => runAction(false));
$('new-case').addEventListener('click', () => { showWorkspace('triage'); selectCase(null); $('issue-title').focus(); });
$('case-search').addEventListener('input', renderCases);
$('incident-form').querySelectorAll('input,textarea,select').forEach((el) => el.addEventListener('input', () => { resetOutput(); rememberDraft(); }));
$('retrieval-mode').addEventListener('change', () => { updateSearchMode(); resetOutput(); });
$('settings-button').addEventListener('click', openSettings);
$('close-settings').addEventListener('click', () => { $('settings-dialog').close(); $('api-key').value = ''; });
$('settings-dialog').addEventListener('close', () => { $('api-key').value = ''; });
$('provider').addEventListener('change', providerChanged);
$('close-access').addEventListener('click', () => $('access-dialog').close());
$('access-dialog').addEventListener('close', () => { $('access-code').value = ''; });
$('access-form').addEventListener('submit', async (event) => {
  event.preventDefault(); $('unlock-button').disabled = true; showError('access-error', '');
  try {
    await api('/api/access', { method: 'POST', body: JSON.stringify({ code: $('access-code').value }) });
    updateStatus(await api('/api/status')); $('access-dialog').close(); await refreshHistory();
    if (accessDestination === 'brain' || brain.open) { accessDestination = null; await loadBrain(); }
  } catch (error) { showError('access-error', error.message); }
  finally { $('access-code').value = ''; $('unlock-button').disabled = false; }
});
$('saved-analysis').addEventListener('change', async () => {
  if (!$('saved-analysis').value || state.busy) return;
  try {
    const record = await api('/api/history/' + encodeURIComponent($('saved-analysis').value));
    record.analysis.saved_id = record.id;
    state.selected = state.cases.find((c) => c.id === record.incident.id) || null;
    $('selected-case').textContent = record.incident.id; $('case-status').hidden = true;
    restoreDraft({ incident: { ...record.incident, evidence: record.incident.provided_evidence.join('\n') },
      retrieval: record.analysis.retrieval_mode, result: record.analysis });
    renderCases(); rememberDraft();
    showWorkspace('triage');
  } catch (error) { showError('form-error', error.message); }
});

function showWorkspace(section) {
  brain.open = section === 'brain';
  $('triage-view').hidden = brain.open;
  $('brain-view').hidden = !brain.open;
  $('triage-tab').setAttribute('aria-pressed', String(!brain.open));
  $('brain-tab').setAttribute('aria-pressed', String(brain.open));
  $('workspace-title').textContent = brain.open ? 'Second Brain' : 'Incident triage';
  history.replaceState(null, '', location.pathname + location.search + (brain.open ? '#second-brain' : ''));
}
function unlockBrain() {
  accessDestination = 'brain';
  $('access-dialog').showModal();
}
async function loadBrain() {
  if (brain.loading) return;
  $('brain-locked').hidden = !state.status?.access_required;
  $('brain-library').hidden = !!state.status?.access_required;
  if (!state.status || state.status.access_required) return;
  brain.loading = true;
  $('brain-refresh').disabled = true;
  showError('brain-error', '');
  try {
    brain.data = await api('/api/brain');
    $('brain-library').hidden = false;
    $('brain-locked').hidden = true;
    $('approved-count').textContent = brain.data.sources.length;
    $('pending-count').textContent = brain.data.learnings.filter((n) => n.status === 'pending').length;
    $('rejected-count').textContent = brain.data.learnings.filter((n) => n.status === 'rejected').length;
    renderBrain();
  } catch (error) {
    showError('brain-error', error.message);
    if (state.status?.access_required) { $('brain-library').hidden = true; $('brain-locked').hidden = false; }
  } finally { brain.loading = false; $('brain-refresh').disabled = false; }
}
function brainEntries() {
  if (!brain.data) return [];
  const query = $('brain-search').value.trim().toLowerCase();
  const version = $('brain-version').value;
  const entries = brain.filter === 'approved' ? brain.data.sources : brain.data.learnings.filter((n) => n.status === brain.filter);
  return entries.filter((n) => `${n.id} ${n.title} ${n.content}`.toLowerCase().includes(query)
    && (!version || (version === 'unknown' ? !n.versions.length : n.versions.includes(version))));
}
function renderBrain() {
  for (const filter of ['approved', 'pending', 'rejected']) $('brain-' + filter).setAttribute('aria-pressed', String(brain.filter === filter));
  const entries = brainEntries();
  const selected = entries.find((n) => n.id === brain.selected);
  if (!selected) brain.selected = null;
  $('brain-results-count').textContent = `${entries.length} ${entries.length === 1 ? 'entry' : 'entries'} · ${brain.filter === 'approved' ? 'Available to both search modes' : 'Excluded from both search modes'}`;
  const kinds = {note:'Learning', card:'Case card', doc:'Guide', flag:'Configuration', obs:'Logs', ownership:'Ownership', version:'Platform version'};
  $('brain-list').innerHTML = entries.map((n) => `<button type="button" class="brain-entry" aria-pressed="${n.id === brain.selected}" data-entry="${escapeHTML(n.id)}"><strong>${escapeHTML(n.title)}</strong><span>${escapeHTML(kinds[n.kind] || 'Learning')} · ${escapeHTML(n.versions.join(', ') || 'Version scope not established')}</span></button>`).join('') || '<p class="sources-empty">No entries match this view. Try another filter or add a learning.</p>';
  $('brain-list').querySelectorAll('button').forEach((button) => button.addEventListener('click', () => {
    brain.selected = button.dataset.entry;
    renderBrain();
    if (window.matchMedia('(max-width:900px)').matches) $('brain-detail').scrollIntoView({block:'start'});
  }));
  renderBrainDetail(selected);
}
function renderBrainDetail(entry) {
  if (!entry) {
    $('brain-detail').innerHTML = '<p class="sources-empty">Select an entry to read its full content, evidence and version scope.</p>';
    return;
  }
  const note = entry.web_id ? brain.data.learnings.find((n) => n.id === entry.web_id) : entry;
  const date = (value) => new Date(value * 1000).toLocaleString();
  const provenance = note.author ? `<p class="brain-provenance">${note.origin === 'analysis' ? 'Automatically drafted' : 'Submitted'} by ${escapeHTML(note.author)} · ${escapeHTML(date(note.created_at))}${note.origin === 'analysis' ? `<br>Investigation: ${escapeHTML(note.source_case)} · ${note.retrieval_mode === 'hybrid' ? 'Hybrid' : 'Keyword'} · ${escapeHTML(note.model || '')}` : ''}${note.review ? `<br>${note.status === 'approved' ? 'Approved' : 'Rejected'} by ${escapeHTML(note.review.reviewer)} · ${escapeHTML(date(note.review.reviewed_at))}<br>Review: ${escapeHTML(note.review.reason)}` : ''}</p>` : '<p class="brain-provenance">Maintained in the reviewed project knowledge. Add a new learning to propose a correction.</p>';
  const reviewForm = entry.status === 'pending' ? `<form id="brain-review-form" class="brain-review-form"><h3>Review this learning</h3><p class="field-help">Anyone with demo access can review. Approval adds this note to Keyword and Hybrid search. Check its evidence and applicability first.</p><label for="reviewer-name">Reviewer name</label><input id="reviewer-name" required minlength="2" maxlength="80" autocomplete="name"><label for="review-reason">Review notes</label><textarea id="review-reason" required minlength="5" maxlength="2000" rows="3" placeholder="What did you verify, or why should this be rejected?"></textarea><label class="review-confirm"><input id="review-verified" type="checkbox"> I verified the evidence and stated version scope.</label><p id="review-error" class="error-message" role="alert" hidden></p><div class="brain-review-actions"><button type="submit" name="decision" value="rejected" class="secondary-button">Reject learning</button><button type="submit" name="decision" value="approved" class="primary-button">Approve for search</button></div></form>` : '';
  $('brain-detail').innerHTML = `<h2>${escapeHTML(entry.title)}</h2><div class="brain-detail-meta"><span>${entry.status === 'pending' ? 'Pending review' : entry.status === 'rejected' ? 'Rejected' : 'Reviewed knowledge'}</span><span>${escapeHTML(entry.versions.join(', ') || 'Version scope not established')}</span></div>${entry.caveat ? `<p class="field-help">${escapeHTML(entry.caveat)}</p>` : !entry.versions.length ? '<p class="field-help">Confirm version applicability before using this guidance.</p>' : ''}<pre class="brain-body">${escapeHTML(entry.content)}</pre><p class="brain-provenance">Source: ${escapeHTML(entry.id)}${entry.source_path ? `<br>${escapeHTML(entry.source_path)}` : ''}</p>${provenance}${reviewForm}`;
  if (reviewForm) $('brain-review-form').addEventListener('submit', (event) => reviewLearning(event, entry.id));
}
async function reviewLearning(event, id) {
  event.preventDefault();
  const decision = event.submitter?.value;
  if (!decision) return;
  showError('review-error', '');
  if (decision === 'approved' && !$('review-verified').checked) {
    showError('review-error', 'Verify the evidence and version scope, then check the confirmation before approving.');
    return;
  }
  const form = event.currentTarget;
  const buttons = form.querySelectorAll('button');
  buttons.forEach((button) => { button.disabled = true; });
  const payload = { status: decision, reviewer: $('reviewer-name').value.trim(), reason: $('review-reason').value.trim(), verified: $('review-verified').checked };
  try {
    await api(`/api/brain/learnings/${encodeURIComponent(id)}/review`, {method:'POST', body:JSON.stringify(payload)});
    brain.filter = decision;
    brain.selected = decision === 'approved' ? 'WEB-NOTE:' + id : id;
    await loadBrain();
    try { updateStatus(await api('/api/status')); } catch (error) { showError('brain-error', 'Decision saved. ' + error.message); }
    $('brain-message').textContent = decision === 'approved' ? 'Learning approved. Both search modes now use it. Existing analyses keep their original knowledge revision.' : 'Learning rejected. It stays out of both search modes.';
    $('brain-message').hidden = false;
  } catch (error) {
    if ($('review-error')) showError('review-error', error.message);
    if (state.status?.access_required) { $('brain-library').hidden = true; $('brain-locked').hidden = false; }
  } finally { buttons.forEach((button) => { button.disabled = false; }); }
}
function openLearning() {
  if (!state.status) return;
  if (state.status.access_required) { unlockBrain(); return; }
  showError('learning-error', '');
  $('learning-dialog').showModal();
  $('learning-name').focus();
}
$('brain-tab').addEventListener('click', () => { showWorkspace('brain'); loadBrain(); });
$('triage-tab').addEventListener('click', () => showWorkspace('triage'));
$('brain-unlock').addEventListener('click', unlockBrain);
$('add-learning').addEventListener('click', openLearning);
$('brain-refresh').addEventListener('click', loadBrain);
for (const filter of ['approved', 'pending', 'rejected']) $('brain-' + filter).addEventListener('click', () => {
  brain.filter = filter; brain.selected = null; $('brain-message').hidden = true; renderBrain();
});
$('brain-search').addEventListener('input', renderBrain);
$('brain-version').addEventListener('change', renderBrain);
for (const id of ['close-learning', 'cancel-learning']) $(id).addEventListener('click', () => $('learning-dialog').close());
$('learning-form').addEventListener('submit', async (event) => {
  event.preventDefault(); showError('learning-error', ''); $('submit-learning').disabled = true;
  const payload = { title:$('learning-name').value.trim(), author:$('learning-author').value.trim(), content:$('learning-content').value.trim(), versions:Array.from($('learning-form').querySelectorAll('input[name="learning-version"]:checked'), (input) => input.value) };
  try {
    const note = await api('/api/brain/learnings', {method:'POST', body:JSON.stringify(payload)});
    $('learning-dialog').close(); $('learning-form').reset();
    brain.filter = 'pending'; brain.selected = note.id;
    $('brain-search').value = ''; $('brain-version').value = '';
    await loadBrain();
    $('brain-message').textContent = 'Learning saved for review. Neither search mode uses it until it is approved.';
    $('brain-message').hidden = false;
  } catch (error) { showError('learning-error', error.message); }
  finally { $('submit-learning').disabled = false; }
});
$('settings-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('connect-button'); button.disabled = true; button.textContent = 'Verifying connection…';
  showError('settings-error', '');
  try {
    const payload = { provider: $('provider').value, model: $('model-id').value.trim(), api_key: $('api-key').value.trim() };
    await api('/api/settings', { method: 'POST', body: JSON.stringify(payload) });
    updateStatus(await api('/api/status'));
    $('settings-dialog').close();
  } catch (error) { showError('settings-error', error.message); }
  finally { $('api-key').value = ''; button.disabled = false; button.textContent = 'Connect & verify'; }
});
$('disconnect-button').addEventListener('click', async () => {
  try { await api('/api/settings', { method: 'DELETE' }); updateStatus(await api('/api/status')); $('settings-dialog').close(); }
  catch (error) { showError('settings-error', error.message); }
});

async function init() {
  try {
    const [catalog, status] = await Promise.all([api('/api/cases'), api('/api/status')]);
    state.cases = catalog.cases;
    updateStatus(status);
    $('provider').innerHTML = status.providers.map((p) => `<option value="${escapeHTML(p.id)}">${escapeHTML(p.label)}</option>`).join('');
    const selected = drafts.selected;
    selectCase(selected === 'CUSTOM' ? null : state.cases.find((c) => c.id === selected) || state.cases[0]);
    await refreshHistory();
    if (location.hash === '#second-brain') { showWorkspace('brain'); await loadBrain(); }
  } catch (error) { showError('form-error', error.message); $('model-status').textContent = 'App unavailable'; }
}
init();

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'\"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','\"':'&quot;'}[char]));
const list = (items) => `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
const PROCESSING_MESSAGES = [
  'Please wait patiently, the investigation is still in progress.',
  'This may take a moment while we carefully analyze the evidence.',
  'We\'re working through the evidence. Just a little longer.',
  'Please hold on, our investigators are reviewing the incident.',
  'Analyzing the evidence and narrowing down the possible causes.',
  'The investigation is underway. We\'ll have a verdict soon.',
  'Good investigations take time. We\'re carefully checking the evidence.',
  'We\'re examining every detail before reaching a conclusion.',
  'Almost there — the tribunal is reviewing the findings.',
  'Just a moment more — your investigation is nearly complete.'
];

let currentInvestigationRun = null;
let renderedInvestigation = null;
let processingMessageTimer = null;
let processingMessageTimeout = null;
let lastProcessingMessage = '';
// File size constants
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function showOnly(id) {
  const sections = ['landing', 'submission', 'progress', 'dashboard'];
  const target = document.getElementById(id);
  if (!target) {
    return;
  }

  sections.forEach(section => {
    const sectionEl = document.getElementById(section);
    if (sectionEl) {
      sectionEl.classList.toggle('hidden', section !== id);
    }
  });

  document.body.classList.toggle('result-page-footer-visible', id === 'dashboard');
  window.scrollTo({ top: 0, behavior: 'auto' });
}

// Modal handling for demo
const demoModal = $('#demo-modal');
const confirmDemoBtn = $('#confirm-demo');
const cancelDemoBtn = $('#cancel-demo');
const modalClose = $('.modal-close');

function openDemoModal() {
  demoModal.classList.remove('hidden');
}

function closeDemoModal() {
  demoModal.classList.add('hidden');
}

const demoButton = $('#demo-button');
if (demoButton) {
  demoButton.addEventListener('click', () => openDemoModal());
}

const headerDemoButton = $('#header-demo-button');
if (headerDemoButton) {
  headerDemoButton.addEventListener('click', () => openDemoModal());
}

const headerNewInvestigation = $('#header-new-investigation');
if (headerNewInvestigation) {
  headerNewInvestigation.addEventListener('click', () => {
    cancelActiveInvestigation();
    showOnly('submission');
    resetForm();
    resetProgressState();
  });
}

confirmDemoBtn.addEventListener('click', () => {
  closeDemoModal();
  runInvestigation('DEMO-INC-2026-001', true);
});
cancelDemoBtn.addEventListener('click', () => closeDemoModal());
modalClose.addEventListener('click', () => closeDemoModal());

// Close modal when clicking outside of it
demoModal.addEventListener('click', (event) => {
  if (event.target === demoModal) {
    closeDemoModal();
  }
});

// File upload handling with size validation
document.querySelectorAll('input[type=file]').forEach(input => input.addEventListener('change', () => {
  const label = document.querySelector(`[data-for=\"${input.name}\"]`);
  const warning = document.querySelector(`.file-warning[data-for=\"${input.name}\"]`);
  
  if (input.files[0]) {
    const file = input.files[0];
    const fileSize = file.size;
    
    // Update file name
    label.textContent = file.name;
    label.classList.add('selected-file');
    
    // Check file size and show warning if needed
    if (fileSize > MAX_FILE_SIZE) {
      warning.textContent = `⚠ File exceeds 20 MB limit (${formatFileSize(fileSize)})`;
      warning.classList.add('file-size-warning');
      input.classList.add('file-error');
    } else {
      warning.textContent = '';
      warning.classList.remove('file-size-warning');
      input.classList.remove('file-error');
    }
  } else {
    label.textContent = input.id === 'logs' ? '.log or .txt' : '.zip · max 20 MB';
    label.classList.remove('selected-file');
    warning.textContent = '';
    warning.classList.remove('file-size-warning');
    input.classList.remove('file-error');
  }
}));

const startButton = $('#start-button');
if (startButton) {
  startButton.addEventListener('click', () => {
    showOnly('submission');
    resetForm();
    resetProgressState();
  });
}

function goHome() {
  cancelActiveInvestigation();
  resetForm();
  resetProgressState();

  if (document.getElementById('landing')) {
    showOnly('landing');
    return;
  }

  window.location.href = '/';
}

const backHomeSubmission = $('#back-home-submission');
if (backHomeSubmission) backHomeSubmission.addEventListener('click', () => goHome());

const backHomeProgress = $('#back-home-progress');
if (backHomeProgress) backHomeProgress.addEventListener('click', () => goHome());

const backHomeDashboard = $('#back-home-dashboard');
if (backHomeDashboard) backHomeDashboard.addEventListener('click', () => goHome());

if (document.getElementById('landing')) {
  document.querySelectorAll('a[href="/"]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      goHome();
    });
  });
}

const newInvestigationButton = $('#new-investigation');
if (newInvestigationButton) {
  newInvestigationButton.addEventListener('click', () => {
    cancelActiveInvestigation();
    showOnly('submission');
    resetForm();
    resetProgressState();
  });
}

const resultFooterNewInvestigation = $('#result-footer-new-investigation');
if (resultFooterNewInvestigation) {
  resultFooterNewInvestigation.addEventListener('click', () => {
    cancelActiveInvestigation();
    showOnly('submission');
    resetForm();
    resetProgressState();
  });
}

const resultFooterBackHome = $('#result-footer-back-home');
if (resultFooterBackHome) {
  resultFooterBackHome.addEventListener('click', () => goHome());
}

function resetForm() {
  $('#investigation-form').reset();
  $('#form-error').textContent = '';
  resetSubmitButtonState();

  document.querySelectorAll('input[type=file]').forEach(input => {
    const warning = document.querySelector(`.file-warning[data-for="${input.name}"]`);
    const label = document.querySelector(`[data-for="${input.name}"]`);
    if (warning) {
      warning.textContent = '';
      warning.classList.remove('file-size-warning');
    }
    if (label) {
      label.textContent = input.id === 'logs' ? '.log or .txt' : '.zip · max 20 MB';
      label.classList.remove('selected-file');
    }
    input.classList.remove('file-error');
  });
}

function isInvestigationActive(session) {
  return Boolean(session && session === currentInvestigationRun && !session.cancelled);
}

function stopProcessingMessages() {
  if (processingMessageTimer) {
    clearInterval(processingMessageTimer);
    processingMessageTimer = null;
  }
  if (processingMessageTimeout) {
    clearTimeout(processingMessageTimeout);
    processingMessageTimeout = null;
  }
}

function cancelActiveInvestigation() {
  if (currentInvestigationRun) {
    currentInvestigationRun.cancelled = true;
    if (typeof currentInvestigationRun.abort === 'function') {
      currentInvestigationRun.abort();
    }
    if (typeof currentInvestigationRun.stopProgress === 'function') {
      currentInvestigationRun.stopProgress();
      currentInvestigationRun.stopProgress = null;
    }
  }

  stopProcessingMessages();

  const status = $('#processing-status');
  if (status) {
    status.textContent = 'Please wait patiently...';
  }
}

function resetSubmitButtonState() {
  const button = document.querySelector('.submit-button');
  if (!button) return;

  button.disabled = false;
  button.classList.remove('is-loading');

  const label = button.querySelector('.button-label');
  const status = button.querySelector('.button-status');
  const spinner = button.querySelector('.button-spinner');

  if (label) label.textContent = 'Begin investigation';
  if (status) status.textContent = '';
  if (spinner) spinner.style.display = 'none';
}

function resetProgressState() {
  const stages = [...document.querySelectorAll('.progress-list [data-stage]')];
  stages.forEach((stage, index) => {
    const status = stage.querySelector('em');
    stage.classList.remove('active', 'complete');
    if (index === 0) stage.classList.add('active');
    if (status) status.textContent = index === 0 ? 'WORKING' : 'QUEUED';
  });
}

function startProgress() {
  const stages = [...document.querySelectorAll('.progress-list [data-stage]')];
  let activeStage = 0;
  const update = () => stages.forEach((stage, index) => {
    const status = stage.querySelector('em');
    stage.classList.toggle('active', index === activeStage);
    stage.classList.toggle('complete', index < activeStage);
    status.textContent = index < activeStage ? 'DONE' : index === activeStage ? 'WORKING' : 'QUEUED';
  });
  update();
  const timer = setInterval(() => {
    if (activeStage < stages.length - 1) {
      activeStage += 1;
      update();
    }
  }, 650);
  return () => {
    clearInterval(timer);
    activeStage = stages.length;
    update();
  };
}

function setProcessingMessage(text) {
  lastProcessingMessage = text;
  const progressStatus = $('#processing-status');
  const submitButtonStatus = document.querySelector('.submit-button.is-loading .button-status');

  if (progressStatus) {
    progressStatus.textContent = text;
  }
  if (submitButtonStatus) {
    submitButtonStatus.textContent = text;
  }
}

function pickProcessingMessage() {
  const options = PROCESSING_MESSAGES.filter(message => message !== lastProcessingMessage);
  const pool = options.length ? options : PROCESSING_MESSAGES;
  return pool[Math.floor(Math.random() * pool.length)];
}

function startProcessingMessages() {
  stopProcessingMessages();
  const initialMessage = 'Please wait patiently, the investigation is still in progress.';
  setProcessingMessage(initialMessage);

  processingMessageTimeout = setTimeout(() => {
    if (!isInvestigationActive(currentInvestigationRun)) {
      return;
    }

    setProcessingMessage(pickProcessingMessage());
    processingMessageTimer = setInterval(() => {
      if (!isInvestigationActive(currentInvestigationRun)) {
        stopProcessingMessages();
        return;
      }
      setProcessingMessage(pickProcessingMessage());
    }, 5000);
  }, 6000);
}

function setSubmitLoading(isLoading) {
  const button = document.querySelector('.submit-button');
  if (!button) return;

  button.disabled = isLoading;
  button.classList.toggle('is-loading', isLoading);

  const label = button.querySelector('.button-label');
  const status = button.querySelector('.button-status');
  const spinner = button.querySelector('.button-spinner');

  if (label) {
    label.textContent = 'Begin investigation';
  }

  if (status) {
    status.textContent = isLoading ? 'Please wait patiently, the investigation is still in progress.' : '';
  }

  if (spinner) {
    spinner.style.display = isLoading ? 'inline-block' : 'none';
  }
}

function beginInvestigationSession() {
  cancelActiveInvestigation();
  const abortController = new AbortController();
  currentInvestigationRun = {
    cancelled: false,
    abort: () => abortController.abort(),
    abortController,
    stopProgress: null
  };
  return currentInvestigationRun;
}

$('#investigation-form').addEventListener('submit', async event => {
  event.preventDefault();
  $('#form-error').textContent = '';

  // Validate file sizes
  const logsFile = $('#logs').files[0];
  const sourceFile = $('#source_zip').files[0];

  if (logsFile && logsFile.size > MAX_FILE_SIZE) {
    $('#form-error').textContent = `Log file exceeds 20 MB limit (${formatFileSize(logsFile.size)})`;
    return;
  }

  if (sourceFile && sourceFile.size > MAX_FILE_SIZE) {
    $('#form-error').textContent = `Source ZIP file exceeds 20 MB limit (${formatFileSize(sourceFile.size)})`;
    return;
  }

  const formData = new FormData(event.target);
  const repoUrl = (formData.get('github_repo_url') || '').toString().trim();
  if (!formData.get('observation').trim() && !$('#logs').files.length && !$('#source_zip').files.length && !repoUrl) {
    $('#form-error').textContent = 'No evidence was provided. Upload logs, source code, connect a GitHub repository, or add an observation to begin.';
    return;
  }

  const session = beginInvestigationSession();
  setSubmitLoading(true);
  startProcessingMessages();

  try {
    const response = await fetch('/api/investigations', {
      method: 'POST',
      body: formData,
      signal: session.abortController.signal
    });
    const result = await response.json();
    if (!isInvestigationActive(session)) {
      return;
    }
    if (!response.ok) {
      $('#form-error').textContent = result.error;
      setSubmitLoading(false);
      stopProcessingMessages();
      return;
    }
    setSubmitLoading(false);
    await runInvestigation(result.investigation_id, false, session);
  } catch (error) {
    if (error && error.name === 'AbortError') {
      return;
    }
    if (!isInvestigationActive(session)) {
      return;
    }
    $('#form-error').textContent = 'The investigation could not be started. Please try again.';
    setSubmitLoading(false);
    stopProcessingMessages();
  }
});

async function runInvestigation(id, demo, existingSession) {
  const session = existingSession && isInvestigationActive(existingSession)
    ? existingSession
    : beginInvestigationSession();

  showOnly('progress');
  $('#progress-id').textContent = id;
  const finishProgress = startProgress();
  session.stopProgress = finishProgress;
  startProcessingMessages();

  try {
    const response = await fetch(demo ? '/api/investigate' : `/api/investigations/${encodeURIComponent(id)}/run`, {
      method: 'POST',
      signal: session.abortController.signal
    });

    if (!isInvestigationActive(session)) {
      finishProgress();
      return;
    }

    const data = await response.json();
    finishProgress();
    if (!isInvestigationActive(session)) {
      return;
    }
    if (!response.ok) {
      stopProcessingMessages();
      setSubmitLoading(false);
      $('#form-error').textContent = data.error;
      showOnly('submission');
      return;
    }

    stopProcessingMessages();
    await new Promise(resolve => setTimeout(resolve, 1500));
    if (!isInvestigationActive(session)) {
      return;
    }
    currentInvestigationRun = null;
    renderDashboard(data);
  } catch (error) {
    finishProgress();
    if ((error && error.name === 'AbortError') || !isInvestigationActive(session)) {
      return;
    }
    stopProcessingMessages();
    setSubmitLoading(false);
    $('#form-error').textContent = 'The investigation could not be completed. Please try again.';
    showOnly('submission');
  }
}

function renderDashboard(data) {
  renderedInvestigation = data;
  showOnly('dashboard');
  $('#case-title').textContent = data.incident.title;
  $('#case-verdict').textContent = data.tribunal.judge.verdict;
  $('#case-observation').textContent = data.incident.user_impact || data.incident.description;
  $('#case-mode').textContent = data.demo ? 'DEMO INVESTIGATION' : 'USER INVESTIGATION';

  // NEW IN v6: Render investigation summary first
  renderInvestigationSummary(data.investigation_summary || {});
  renderInvestigatorTimeline(data.investigator_timeline || []);
  renderRecommendedActions(data.recommended_actions || {});

  // Render project profile section
  renderProjectProfile(data.project_discovery || {});
  
  // Render timeline section
  renderTimeline(data.timeline || {});
  renderTrustLayer(data.trust_layer || {});

  const discovery = data.project_discovery || {};
  const evidenceStatus = data.evidence_status || {};
  $('#investigators').innerHTML = data.investigators.map(item => `<article class="investigator-card"><div class="card-top"><span class="agent-icon">◈</span><span class="complete">● ${escapeHtml(item.status.toUpperCase())}</span></div><h3>${escapeHtml(item.agent)}</h3>${list(item.findings)}${item.evidence.length ? `<div class="evidence-lines">${list(item.evidence)}</div>` : ''}<div class="confidence">CONFIDENCE <strong>${Math.round(item.confidence * 100)}%</strong></div></article>`).join('') + `
    <article class="investigator-card">
      <div class="card-top"><span class="agent-icon">◎</span><span class="complete">● PROJECT DISCOVERY</span></div>
      <h3>Repository Summary</h3>
      <ul>
        <li>Repository: ${escapeHtml(discovery.repository || 'Unknown')}</li>
        <li>Language: ${escapeHtml(discovery.language || 'Unknown')}</li>
        <li>${escapeHtml(discovery.framework_detected || 'Framework detection not yet confident.')}</li>
        <li>Entry points: ${escapeHtml((discovery.entry_points || []).join(', ') || 'Not identified')}</li>
        <li>Test framework: ${escapeHtml(discovery.test_framework || 'Not detected')}</li>
        <li>Tests detected: ${escapeHtml(String(discovery.tests_detected ?? 0))}</li>
        <li>Git history: ${escapeHtml(discovery.git_history ? 'Available' : 'Not available')}</li>
      </ul>
    </article>
    <article class="investigator-card">
      <div class="card-top"><span class="agent-icon">◌</span><span class="complete">● EVIDENCE STATUS</span></div>
      <h3>Evidence Availability</h3>
      <ul>
        <li>Application Logs: ${escapeHtml(evidenceStatus.application_logs || 'Not Provided')}</li>
        <li>Error Reports: ${escapeHtml(evidenceStatus.error_reports || 'Not Provided')}</li>
        <li>Stack Trace: ${escapeHtml(evidenceStatus.stack_trace || 'Not Provided')}</li>
        <li>Failing Tests: ${escapeHtml(evidenceStatus.failing_tests || 'Not Detected')}</li>
        <li>Git History: ${escapeHtml(evidenceStatus.git_history || 'Not Available')}</li>
        <li>Source Code: ${escapeHtml(evidenceStatus.source_code || 'Not Available')}</li>
      </ul>
    </article>`;
  const { prosecutor, defense, judge } = data.tribunal;
  const evidenceIds = ids => (ids || []).map(id => `<span class="attribution-badge fact">${escapeHtml(id)}</span>`).join(' ');
  const chain = items => (items || []).length ? `<ol class="causal-chain">${(items || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ol>` : '';
  const challenge = (defense.challenges || [])[0];
  $('#tribunal').innerHTML = `<article class="argument prosecutor"><span class="attribution-badge reasoning">REASONING · PROSECUTOR</span><h3>Case for the hypothesis</h3><p>${escapeHtml(prosecutor.argument)}</p><div class="tribunal-evidence">Evidence: ${evidenceIds(prosecutor.evidence_ids)}</div>${chain(prosecutor.causal_chain)}<div class="citation">${list(prosecutor.citations || [])}</div></article><article class="argument defense"><span class="attribution-badge reasoning">REASONING · DEFENSE</span><h3>Challenge to certainty</h3><p>${escapeHtml(defense.argument)}</p>${challenge ? `<div class="challenge"><strong>${escapeHtml(challenge.evidence_id)}</strong><br>${escapeHtml(challenge.argument)}<br><em>Gap: ${escapeHtml(challenge.gap)}</em></div>` : ''}<div class="citation">Missing evidence: ${list(defense.missing_evidence || [])}</div></article><article class="judge-card"><span class="judge-seal">⚖</span><span class="attribution-badge reasoning">REASONING · JUDGE</span><h3>${escapeHtml(judge.verdict)}</h3><p>${escapeHtml(judge.reason)}</p><div class="tribunal-evidence">Supporting evidence: ${evidenceIds(judge.supporting_evidence_ids)}</div><p><strong>Strongest challenge:</strong> ${escapeHtml(judge.strongest_defense_argument || 'Not recorded')}</p><div class="verdict-change"><strong>What would change this verdict?</strong>${list(judge.what_would_change_verdict || [])}</div><strong>${Math.round(judge.confidence * 100)}% CONFIDENCE</strong></article>`;
  $('#verdict-badge').textContent = judge.verdict;
  $('#ledger').innerHTML = `<div class="ledger-column"><h3>Facts</h3>${list(data.ledger.facts || [])}<h3>Observations</h3>${list(data.ledger.observations || [])}</div><div class="ledger-column against"><h3>Evidence against</h3>${list(data.ledger.evidence_against || [])}<h3>Hypotheses</h3>${list(data.ledger.hypotheses || [])}<h3>Alternative explanations</h3>${list((data.ledger.alternatives || []).map(item => `${item.name}: ${item.status} · ${item.reason}`))}</div><div class="ledger-column"><h3>Missing evidence</h3>${list(data.ledger.missing_evidence || [])}<h3>What changes the verdict</h3>${list(data.ledger.what_would_change_verdict || [])}<h3>Human verification</h3>${list(data.ledger.human_verification || [])}</div>`;
  renderDevOpsContext(data.investigators || []);
  const { reproduction, fix, verification } = data.proof;
  $('#proof').innerHTML = `<div class="proof-step"><span class="proof-icon red">01</span><span class="proof-label">BUG REPRODUCED</span><strong>${reproduction.status}</strong><small>${escapeHtml(reproduction.message)}</small></div><div class="proof-arrow">→</div><div class="proof-step"><span class="proof-icon amber">02</span><span class="proof-label">FIX GENERATED</span><strong>${data.demo ? 'MINIMAL DIFF' : 'NOT RUN'}</strong><small>${escapeHtml(fix.description)}</small></div><div class="proof-arrow">→</div><div class="proof-step"><span class="proof-icon green">03</span><span class="proof-label">FIX VERIFIED</span><strong>${verification.status}</strong><small>${escapeHtml(verification.message)}</small></div>`;
  $('#diff').textContent = fix.diff;
  renderVerificationAction(data);
  
  // Render similar patterns section
  if (data.similar_patterns && data.similar_patterns.length > 0) {
    renderSimilarPatterns(data.similar_patterns);
  } else {
    $('#similar-patterns').innerHTML = '<p style="color:#999; padding:20px; text-align:center;">No similar patterns detected in this investigation.</p>';
  }
}

function renderTrustLayer(trustLayer) {
  const facts = trustLayer.facts || [];
  const valid = (trustLayer.validation_errors || []).length === 0;
  $('#trust-status').className = `trust-status ${valid ? 'valid' : 'invalid'}`;
  $('#trust-status').textContent = valid
    ? '✓ Trust-layer contract validated: evidence, reasoning, tribunal, and verification policy are present.'
    : `⚠ Trust-layer validation issues: ${(trustLayer.validation_errors || []).join(' · ')}`;
  if (!facts.length) {
    $('#evidence-catalog').innerHTML = '<p>No directly cited evidence was extracted. Add logs, source, or Git history for an auditable catalogue.</p>';
    return;
  }
  $('#evidence-catalog').innerHTML = facts.map(fact => `<article class="fact-card"><div class="fact-meta"><span class="attribution-badge fact">FACT · ${escapeHtml(fact.id)}</span><span>${escapeHtml(fact.type)}</span></div><p>${escapeHtml(fact.excerpt)}</p><div class="fact-source">${escapeHtml(fact.source)}${fact.line ? `:${escapeHtml(fact.line)}` : ''} · ${escapeHtml(fact.investigator)}</div></article>`).join('');
}

function renderVerificationAction(data) {
  const action = $('#verification-action');
  const result = $('#verification-result');
  result.innerHTML = '';
  if (!data.demo) {
    action.innerHTML = `<span class="attribution-badge proof">PROOF POLICY</span><p>Uploaded and GitHub repository code is never executed by BugSleuth. Use the reproduction plan in your own isolated environment.</p>`;
    return;
  }
  action.innerHTML = `<span class="attribution-badge proof">VERIFIED PROOF</span><p>Run a real pytest RED → GREEN check against a temporary copy of the trusted demo source.</p><button class="verify-button" id="run-demo-verification">▶ Run verification</button>`;
  $('#run-demo-verification').addEventListener('click', runDemoVerification);
}

async function runDemoVerification() {
  const button = $('#run-demo-verification');
  button.disabled = true;
  button.textContent = 'Running pytest…';
  try {
    const response = await fetch('/api/investigations/DEMO-INC-2026-001/verify', { method: 'POST' });
    const data = await response.json();
    if (!response.ok || data.status === 'error') throw new Error(data.message || data.error || 'Verification failed');
    $('#verification-result').innerHTML = `<p><span class="attribution-badge proof">${data.status === 'verified' ? '✓ VERIFIED' : 'NOT VERIFIED'}</span> ${escapeHtml(data.message || '')}</p><div class="verification-panels"><article class="verification-panel before"><strong>BEFORE PATCH</strong><p>Passed: ${escapeHtml(data.before.passed)} · Failed: ${escapeHtml(data.before.failed)}</p><pre class="verification-output">${escapeHtml(data.before.output)}</pre></article><article class="verification-panel after"><strong>AFTER PATCH</strong><p>Passed: ${escapeHtml(data.after.passed)} · Failed: ${escapeHtml(data.after.failed)}</p><pre class="verification-output">${escapeHtml(data.after.output)}</pre></article></div>`;
  } catch (error) {
    $('#verification-result').textContent = `Verification could not complete: ${error.message}`;
  } finally {
    button.disabled = false;
    button.textContent = '▶ Run verification again';
  }
}

function renderProjectProfile(discovery) {
  if (!discovery || !Object.keys(discovery).length) {
    $('#project-profile').innerHTML = '<p style="color:#999; padding:20px;">Project profile not available.</p>';
    return;
  }
  
  $('#project-profile').innerHTML = `
    <article class="profile-card">
      <h3>${escapeHtml(discovery.project_name || 'Unknown Project')}</h3>
      <div class="profile-grid">
        <div class="profile-item"><span class="label">Language</span><strong>${escapeHtml(discovery.language || 'Unknown')}</strong></div>
        <div class="profile-item"><span class="label">Framework</span><strong>${escapeHtml(discovery.framework || 'Not detected')}</strong></div>
        <div class="profile-item"><span class="label">Test Framework</span><strong>${escapeHtml(discovery.test_framework || 'Not detected')}</strong></div>
        <div class="profile-item"><span class="label">Source Files</span><strong>${escapeHtml(String(discovery.source_file_count || 0))}</strong></div>
        <div class="profile-item"><span class="label">Test Files</span><strong>${escapeHtml(String(discovery.test_file_count || 0))}</strong></div>
        <div class="profile-item"><span class="label">Git History</span><strong>${escapeHtml(discovery.has_git_history ? 'Available' : 'Not available')}</strong></div>
        ${discovery.entry_points && discovery.entry_points.length > 0 ? `<div class="profile-item full-width"><span class="label">Entry Points</span><strong>${escapeHtml(discovery.entry_points.join(', '))}</strong></div>` : ''}
        ${discovery.dependency_files && discovery.dependency_files.length > 0 ? `<div class="profile-item full-width"><span class="label">Dependencies</span><strong>${escapeHtml(discovery.dependency_files.join(', '))}</strong></div>` : ''}
      </div>
    </article>
  `;
}

function renderDevOpsContext(investigators) {
  const pipeline = investigators.find(item => item.agent === 'Pipeline Investigator');
  const deployment = investigators.find(item => item.agent === 'Deployment Context Investigator');
  const pipelineDetected = pipeline && pipeline.pipeline_detected;
  const deploymentProfile = deployment && deployment.deployment_profile ? deployment.deployment_profile : null;

  if (!pipeline && !deployment) {
    $('#devops-context').innerHTML = '<p style="color:#999; padding:20px;">No supported delivery configuration was detected.</p>';
    return;
  }

  $('#devops-context').innerHTML = `
    <article class="profile-card">
      <h3>Pipeline</h3>
      <div class="profile-grid">
        <div class="profile-item"><span class="label">GitHub Actions / CI</span><strong>${pipelineDetected ? 'Detected' : 'Not detected'}</strong></div>
        <div class="profile-item"><span class="label">Test stage</span><strong>${pipeline && pipeline.test_steps && pipeline.test_steps.length ? 'Yes' : 'Not clearly identified'}</strong></div>
        <div class="profile-item"><span class="label">Deployment step</span><strong>${pipeline && pipeline.deployment_steps && pipeline.deployment_steps.length ? 'Detected' : 'Not clearly identified'}</strong></div>
        <div class="profile-item"><span class="label">Execution results</span><strong>Not available</strong></div>
      </div>
    </article>
    <article class="profile-card">
      <h3>Containers & infrastructure</h3>
      <div class="profile-grid">
        <div class="profile-item"><span class="label">Docker</span><strong>${deploymentProfile && deploymentProfile.containerization && deploymentProfile.containerization !== 'Not detected' ? 'Detected' : 'Not detected'}</strong></div>
        <div class="profile-item"><span class="label">Compose</span><strong>${deploymentProfile && deploymentProfile.compose_present ? 'Detected' : 'Not detected'}</strong></div>
        <div class="profile-item"><span class="label">Kubernetes</span><strong>${deploymentProfile && deploymentProfile.orchestration && deploymentProfile.orchestration !== 'Not detected' ? 'Detected' : 'Not detected'}</strong></div>
        <div class="profile-item"><span class="label">Cloud provider</span><strong>${(deploymentProfile && deploymentProfile.cloud_provider) || 'Not confidently identified'}</strong></div>
      </div>
    </article>
  `;
}

function renderTimeline(timeline) {
  if (!timeline || !timeline.events || timeline.events.length === 0) {
    $('#timeline').innerHTML = '<p style="color:#999; padding:20px;">No timeline events extracted.</p>';
    return;
  }
  
  const events = timeline.events || [];
  const timelineHtml = events.map((event, index) => {
    const eventTypeClass = (event.event_type || 'unknown').toLowerCase();
    const timestamp = event.timestamp ? ` · ${escapeHtml(event.timestamp)}` : '';
    return `
      <div class="timeline-event ${eventTypeClass}">
        <div class="timeline-dot"></div>
        <div class="timeline-content">
          <span class="event-type">${escapeHtml((event.event_type || 'UNKNOWN').toUpperCase())}</span>
          <span class="event-source"> · ${escapeHtml(event.source || 'Unknown')}</span>
          <p>${escapeHtml(event.description || 'No description')}</p>
          ${timestamp}
        </div>
      </div>
    `;
  }).join('');
  
  $('#timeline').innerHTML = `<div class="timeline-list">${timelineHtml}</div>`;
}

function renderSimilarPatterns(patterns) {
  if (!patterns || patterns.length === 0) {
    $('#similar-patterns').innerHTML = '<p style="color:#999; padding:20px; text-align:center;">No similar patterns detected.</p>';
    return;
  }
  
  const patternsHtml = patterns.map((pattern, index) => {
    const riskColor = pattern.risk_level === 'HIGH' ? '#d32f2f' : pattern.risk_level === 'MEDIUM' ? '#f57c00' : '#388e3c';
    return `
      <article class="pattern-card">
        <div class="pattern-header">
          <h4>${escapeHtml(pattern.source_file)}</h4>
          <span class="risk-badge" style="background-color:${riskColor}; color:white; padding:4px 8px; border-radius:3px; font-size:12px; font-weight:bold;">
            ${escapeHtml(pattern.risk_level || 'LOW')} RISK
          </span>
        </div>
        ${pattern.line_number ? `<div class="line-info">Line ${escapeHtml(String(pattern.line_number))}</div>` : ''}
        <pre class="pattern-excerpt">${escapeHtml(pattern.excerpt || '')}</pre>
        <p class="pattern-reason"><strong>Why it's similar:</strong> ${escapeHtml(pattern.similarity_reason || '')}</p>
        <p class="pattern-confidence">Confidence: ${Math.round((pattern.match_confidence || 0.5) * 100)}%</p>
        <p style="color:#999; font-size:12px; margin-top:8px;">⚠ This pattern requires human review. Not automatically confirmed as a bug.</p>
      </article>
    `;
  }).join('');
  
  $('#similar-patterns').innerHTML = `
    <p style="margin-bottom:16px; color:#666;">
      Found ${escapeHtml(String(patterns.length))} similar pattern${patterns.length !== 1 ? 's' : ''} in the codebase.
      These may indicate potential issues that warrant further review.
    </p>
    <div class="patterns-grid">${patternsHtml}</div>
  `;
}

function renderInvestigationSummary(summary) {
  if (!summary) return;
  
  const html = `
    <article class="summary-card">
      <div class="summary-metric">
        <span class="label">VERDICT</span>
        <strong class="value">${escapeHtml(summary.verdict)}</strong>
        <small>${escapeHtml(summary.verdict_explanation)}</small>
      </div>
      <div class="summary-metric">
        <span class="label">EVIDENCE STRENGTH</span>
        <strong class="value">${escapeHtml(summary.evidence_strength)}</strong>
      </div>
      <div class="summary-metric">
        <span class="label">HYPOTHESIS CONFIDENCE</span>
        <strong class="value">${escapeHtml(summary.hypothesis_confidence)}</strong>
      </div>
      <div class="summary-metric">
        <span class="label">VERIFICATION STATUS</span>
        <strong class="value">${escapeHtml(summary.verification_status)}</strong>
      </div>
    </article>
    <article class="summary-findings">
      <div class="findings-section">
        <h4>What we know</h4>
        ${summary.what_we_know && summary.what_we_know.length > 0 
          ? `<ul>${summary.what_we_know.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
          : '<p style="color:#999;">No confirmed evidence yet.</p>'}
      </div>
      <div class="findings-section">
        <h4>What we need</h4>
        ${summary.what_we_need && summary.what_we_need.length > 0
          ? `<ul>${summary.what_we_need.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
          : '<p style="color:#999;">Evidence is sufficient for current analysis.</p>'}
      </div>
      <div class="findings-section full-width">
        <h4>Primary Finding</h4>
        <p><strong>${escapeHtml(summary.primary_finding)}</strong></p>
      </div>
      <div class="findings-section full-width">
        <h4>Recommended Next Step</h4>
        <p>${escapeHtml(summary.recommended_next_step)}</p>
      </div>
    </article>
  `;
  
  $('#investigation-summary').innerHTML = html;
}

function renderInvestigatorTimeline(timeline) {
  if (!timeline || timeline.length === 0) return;
  
  const html = timeline.map(entry => {
    const isSuccess = entry.status === 'COMPLETE';
    const isError = entry.status === 'FAILED' || entry.status === 'ERROR';
    const statusColor = isSuccess ? '#16a34a' : isError ? '#dc2626' : '#d97706';
    const iconClass = isSuccess ? 'status-success' : isError ? 'status-danger' : 'status-warning';
    const findingsText = entry.findings_count !== null ? ` · ${entry.findings_count} finding${entry.findings_count !== 1 ? 's' : ''}` : '';
    return `
      <div class="timeline-entry">
        <span class="timeline-icon ${iconClass}" style="color: ${statusColor};">${entry.icon}</span>
        <div class="timeline-content">
          <strong>${escapeHtml(entry.agent)}</strong>
          <span class="timeline-status">${entry.status}${findingsText}</span>
        </div>
      </div>
    `;
  }).join('');
  
  $('#investigator-timeline').innerHTML = `<div class="timeline-list">${html}</div>`;
}

function renderRecommendedActions(actions) {
  if (!actions) return;
  
  const renderActionList = (list, priority) => {
    return list.map(action => `
      <div class="action-item">
        <div class="action-header">
          <h4>${escapeHtml(action.action)}</h4>
          <span class="priority-badge ${priority.toLowerCase()}">${priority}</span>
        </div>
        <p class="action-why"><strong>Why:</strong> ${escapeHtml(action.why)}</p>
      </div>
    `).join('');
  };
  
  const html = `
    ${actions.high_priority && actions.high_priority.length > 0 ? `
      <div class="action-section">
        <h3>High Priority</h3>
        ${renderActionList(actions.high_priority, 'HIGH')}
      </div>
    ` : ''}
    ${actions.medium_priority && actions.medium_priority.length > 0 ? `
      <div class="action-section">
        <h3>Medium Priority</h3>
        ${renderActionList(actions.medium_priority, 'MEDIUM')}
      </div>
    ` : ''}
    ${actions.optional && actions.optional.length > 0 ? `
      <div class="action-section">
        <h3>Optional</h3>
        ${renderActionList(actions.optional, 'OPTIONAL')}
      </div>
    ` : ''}
  `;
  
  $('#recommended-actions').innerHTML = html;
}

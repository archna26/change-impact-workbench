/* ==========================================================
   Change Impact Workbench — ciw.js
   Legacy Retail Co | IBM Bob 2.0 Hackathon

   All analysis is performed by ciw_engine.py via the Flask
   API. This file handles only UI rendering and user input.
   ========================================================== */

"use strict";

/* ── State ───────────────────────────────────────────────── */
const state = {
  catalog:       null,
  currentStep:   1,
  changeRequest: "",
  selected:      null,   // { name, type, lang, source_path, line_no? }
  report:        null,   // raw API response
  triageMap:     {},     // key = "tier:index" → "relevant" | "not-relevant" | "investigate"
  walkthrough:   null,   // "ordsts" | "billrate" | null
};

const STEPS = [
  { n: 1, label: "Describe Change"   },
  { n: 2, label: "Select Artifact"   },
  { n: 3, label: "Trace Impact"      },
  { n: 4, label: "Triage Findings"   },
  { n: 5, label: "Build Checklist"   },
  { n: 6, label: "Export Report"     },
];

/* ── Walkthroughs ────────────────────────────────────────── */
const WALKTHROUGHS = {
  ordsts: {
    label: "ORDSTS — IBM i Status Field",
    lang: "IBM i stack (DDS / ILE RPG / CL)",
    changeRequest:
      "Add a new order status 'H' (Hold) to the ORDSTS field in ORDHDR. " +
      "The obvious change is updating ORDENTRY to write 'H'. However, batch " +
      "programs INVUPDJOB and COMMJOB use negative predicates that must also " +
      "be updated to exclude held orders.",
    artifact: { name: "ORDSTS", type: "field", lang: "ibmi",
                source_path: "src/QDDSSRC/ORDHDR.DDS", line_no: 10 },
  },
  billrate: {
    label: "BILL-RATE — COBOL Billing Rate",
    lang: "COBOL stack (Copybook / COBOL programs — platform unknown)",
    changeRequest:
      "Increase the BILL-RATE precision from PIC 9(3)V99 to support sub-cent " +
      "rates. The obvious change is the BILREC copybook definition. However, " +
      "both CALCBILL and BILPRINT COPY BILREC and will be affected by any " +
      "precision or scale change.",
    artifact: { name: "BILL-RATE", type: "field", lang: "cobol",
                source_path: "src/QCBLSRC/BILREC.CPY", line_no: 15 },
  },
};

/* ── Boot ────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  renderShell();
  try {
    const resp = await fetch("/api/catalog/summary");
    state.catalog = await resp.json();
  } catch (e) {
    state.catalog = { error: String(e) };
  }
  renderSidebar();
  renderStep(1);
});

/* ── Shell ───────────────────────────────────────────────── */
function renderShell() {
  const root = document.getElementById("app-root");
  root.innerHTML = `
    <header>
      <div>
        <h1>Change Impact Workbench</h1>
        <span class="sub">Legacy Retail Co · Source-repository analysis prototype</span>
      </div>
      <span class="badge">IBM Bob 2.0 Hackathon</span>
    </header>
    <div class="main-layout">
      <div id="sidebar">
        <div class="sidebar-header">Repository</div>
        <div id="sidebar-content"><div class="empty-state"><span class="spinner"></span></div></div>
      </div>
      <div id="main-panel">
        <div class="steps-bar" id="steps-bar"></div>
        <div id="content-host"></div>
      </div>
    </div>`;
  renderStepsBar();
}

/* ── Steps bar ───────────────────────────────────────────── */
function renderStepsBar() {
  const bar = document.getElementById("steps-bar");
  bar.innerHTML = STEPS.map(s => {
    const isActive = s.n === state.currentStep;
    const isDone   = s.n < state.currentStep;
    const cls      = isActive ? "active" : isDone ? "done" : "";
    return `<div class="step-item ${cls}" data-step="${s.n}">
      <span class="step-num">${isDone ? "✓" : s.n}</span>${s.label}
    </div>`;
  }).join("");
  bar.querySelectorAll(".step-item").forEach(el => {
    el.addEventListener("click", () => {
      const n = parseInt(el.dataset.step);
      if (n <= state.currentStep || n <= 2) renderStep(n);
    });
  });
}

/* ── Sidebar ─────────────────────────────────────────────── */
function renderSidebar() {
  const sc = document.getElementById("sidebar-content");
  if (!state.catalog || state.catalog.error) {
    sc.innerHTML = `<div class="empty-state" style="font-size:12px;color:#b45309">
      Catalog unavailable: ${(state.catalog?.error || "unknown error")}</div>`;
    return;
  }

  const { tree, meta } = state.catalog;
  let html = `
    <div class="sidebar-section" style="padding-bottom:10px;">
      <p style="font-size:11px;color:var(--muted);margin-bottom:8px;">
        Sample walkthroughs — click to pre-fill all steps:
      </p>
      <button class="sample-btn" id="wt-ordsts">
        ORDSTS change
        <span class="sample-tag">IBM i · DDS field → RPG batch predicates</span>
      </button>
      <button class="sample-btn" id="wt-billrate">
        BILL-RATE change
        <span class="sample-tag">COBOL · Copybook field → CALCBILL · BILPRINT</span>
      </button>
    </div>
    <div style="border-top:1px solid var(--border);padding:10px 16px 0;">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
                  color:var(--muted);margin-bottom:8px;">Browse Repository</div>`;

  // Application node
  for (const [appName, collections] of Object.entries(tree || {})) {
    html += `<div style="font-size:12px;font-weight:700;padding:4px 0 6px;color:var(--text)">${esc(appName)}</div>`;
    for (const [coll, members] of Object.entries(collections)) {
      html += `<div class="tree-coll">${esc(coll)}</div>`;
      (members.programs || []).forEach(p => {
        html += `<div class="tree-node clickable" data-pick-name="${esc(p.name)}"
                      data-pick-type="program" data-pick-lang="${esc(p.lang||p.language||'')}"
                      data-pick-path="${esc(p.source_path||'')}">
          ${esc(p.name)}
          <span class="info-pill" style="margin-left:4px">${esc(p.language||p.lang||'')}</span>
        </div>`;
      });
      (members.fields || []).forEach(f => {
        html += `<div class="tree-node clickable" data-pick-name="${esc(f.name)}"
                      data-pick-type="field" data-pick-lang="${esc(f.lang||f.language||'')}"
                      data-pick-path="${esc(f.source_path||'')}"
                      data-pick-line="${f.line_no||''}">
          ${esc(f.name)}
          <span class="info-pill" style="margin-left:4px">${esc(f.data_type||'')}</span>
        </div>`;
      });
    }
  }
  html += `</div>`;

  // Limitations footer
  html += `<div style="padding:12px 16px;border-top:1px solid var(--border);margin-top:8px;">
    <div style="font-size:10px;color:var(--muted);line-height:1.5">
      <strong>Scope</strong>: Source text analysis only.<br>
      No IBM i / mainframe connection. No compilation.<br>
      COBOL platform: unknown (no JCL/compiler metadata).
    </div>
  </div>`;

  sc.innerHTML = html;

  // Sidebar click handlers
  sc.querySelectorAll(".tree-node.clickable").forEach(el => {
    el.addEventListener("click", () => {
      state.selected = {
        name:        el.dataset.pickName,
        type:        el.dataset.pickType,
        lang:        normLang(el.dataset.pickLang),
        source_path: el.dataset.pickPath,
        line_no:     el.dataset.pickLine ? parseInt(el.dataset.pickLine) : undefined,
      };
      renderStep(2);
    });
  });

  document.getElementById("wt-ordsts")?.addEventListener("click", () => loadWalkthrough("ordsts"));
  document.getElementById("wt-billrate")?.addEventListener("click", () => loadWalkthrough("billrate"));
}

/* ── Walkthrough loader ──────────────────────────────────── */
function loadWalkthrough(key) {
  const wt = WALKTHROUGHS[key];
  state.walkthrough    = key;
  state.changeRequest  = wt.changeRequest;
  state.selected       = { ...wt.artifact };
  state.report         = null;
  state.triageMap      = {};
  state.currentStep    = 1;
  renderStep(1);
}

function normLang(langRaw) {
  if (!langRaw) return null;
  const s = langRaw.toLowerCase();
  if (s === "ibmi" || s.includes("rpg") || s.includes("cl") || s.includes("dds")) return "ibmi";
  if (s === "cobol" || s.includes("cobol")) return "cobol";
  return null;
}

/* ── Render step dispatcher ──────────────────────────────── */
function renderStep(n) {
  state.currentStep = n;
  renderStepsBar();
  const host = document.getElementById("content-host");
  if      (n === 1) host.innerHTML = renderStep1();
  else if (n === 2) host.innerHTML = renderStep2();
  else if (n === 3) host.innerHTML = renderStep3();
  else if (n === 4) host.innerHTML = renderStep4();
  else if (n === 5) host.innerHTML = renderStep5();
  else if (n === 6) host.innerHTML = renderStep6();
  bindStepHandlers(n);
}

/* ── Step 1 — Describe change ────────────────────────────── */
function renderStep1() {
  const wtBanner = state.walkthrough ? `
    <div class="walkthrough-banner">
      <strong>Sample walkthrough:</strong> ${esc(WALKTHROUGHS[state.walkthrough].label)}
      — ${esc(WALKTHROUGHS[state.walkthrough].lang)}.
      This is an example using the same engine, not a special-case analysis path.
    </div>` : "";

  return `<div class="content-area">
    ${wtBanner}
    <div class="section-title">Step 1 — Describe the Proposed Change</div>
    <p class="section-desc">
      Describe the change in plain language. This text is stored in the report and
      shown alongside findings. The deterministic engine does <strong>not</strong>
      interpret free text automatically — select the starting artifact in Step 2.
    </p>
    <div class="disclaimer-box">
      <strong>Prototype scope:</strong> This tool performs static text search over
      fictional representative source files (Legacy Retail Co).
      It is <strong>not</strong> connected to a live IBM i or mainframe environment.
      No source is compiled or executed.
    </div>
    <div class="form-group">
      <label>Change request description</label>
      <textarea id="cr-text" placeholder="e.g. Add a new order status 'H' (Hold) to ORDSTS…"
        >${esc(state.changeRequest)}</textarea>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" id="btn-step1-next">Continue to Artifact Selection →</button>
    </div>
  </div>`;
}

/* ── Step 2 — Select artifact ────────────────────────────── */
function renderStep2() {
  const sel = state.selected;
  const langDisplay = sel?.lang === "ibmi" ? "IBM i" : sel?.lang === "cobol" ? "COBOL" : "Any";

  const wtBanner = state.walkthrough ? `
    <div class="walkthrough-banner">
      <strong>Sample walkthrough — pre-selected artifact:</strong>
      <code>${esc(sel?.name || "")}</code> (${esc(sel?.type || "")}, ${langDisplay})
    </div>` : "";

  return `<div class="content-area">
    ${wtBanner}
    <div class="section-title">Step 2 — Select Starting Artifact</div>
    <p class="section-desc">
      Browse the repository tree on the left, or search below.
      The engine will trace all source relationships from this artifact.
    </p>

    <div class="form-group">
      <label>Search indexed symbols (field or program name)</label>
      <div style="display:flex;gap:8px;">
        <input id="sym-search" placeholder="Type to search…" value="${sel ? esc(sel.name) : ''}" />
        <button class="btn btn-secondary" id="btn-sym-search">Search</button>
      </div>
    </div>
    <div id="sym-results"></div>

    ${sel ? `
    <div style="background:var(--ok-bg);border:1px solid #bbf7d0;border-radius:var(--radius);
                padding:12px 16px;margin:16px 0;">
      <div style="font-size:12px;font-weight:700;color:var(--ok);margin-bottom:4px">
        ✓ Selected artifact
      </div>
      <div style="font-size:13px;">
        <strong>${esc(sel.name)}</strong>
        <span class="info-pill" style="margin-left:6px;">${esc(sel.type)}</span>
        <span class="info-pill" style="margin-left:4px;">${langDisplay}</span>
      </div>
      ${sel.source_path ? `<div style="font-size:12px;color:var(--muted);margin-top:4px;font-family:var(--font-mono)">${esc(sel.source_path)}${sel.line_no ? ':' + sel.line_no : ''}</div>` : ""}
    </div>` : `
    <div class="empty-state" style="padding:20px 0">
      No artifact selected yet — browse the sidebar or search above.
    </div>`}

    <div class="btn-row">
      <button class="btn btn-secondary" id="btn-step2-back">← Back</button>
      <button class="btn btn-primary" id="btn-step2-next" ${sel ? "" : "disabled"}>
        Trace Impact →
      </button>
    </div>
  </div>`;
}

/* ── Step 3 — Trace impact ───────────────────────────────── */
function renderStep3() {
  if (!state.report) {
    return `<div class="content-area">
      <div class="section-title">Step 3 — Trace Candidate Impact</div>
      <p class="section-desc">Running engine analysis…</p>
      <div style="margin-top:20px;text-align:center"><span class="spinner"></span></div>
    </div>`;
  }
  const r = state.report;
  const wtBanner = state.walkthrough ? `
    <div class="walkthrough-banner">
      <strong>Sample walkthrough — ${esc(WALKTHROUGHS[state.walkthrough].label)}:</strong>
      ${r.confirmed_count} confirmed source references · ${r.needs_review_count} needs review.
      Each edge has source path, line number, and evidence text.
    </div>` : "";

  return `<div class="content-area">
    ${wtBanner}
    <div class="section-title">Step 3 — Impact Trace Results</div>
    <p class="section-desc">
      Starting artifact: <code>${esc(r.starting_artifact)}</code>
      · Type: <code>${esc(r.artifact_type)}</code>
      · Language scope: <code>${esc(r.lang)}</code>
    </p>
    <div class="disclaimer-box" style="margin-bottom:12px;">${esc(r.engine_disclaimer)}</div>

    <div class="findings-grid">
      <div class="col-confirmed">
        <div class="findings-col-title">
          Confirmed Source References (${r.confirmed.length})
        </div>
        <div class="finding-card" id="confirmed-list">
          ${r.confirmed.map((d, i) => renderFindingItem(d, "confirmed", i, false)).join("") || '<div class="empty-state">None</div>'}
        </div>
      </div>
      <div class="col-nr">
        <div class="findings-col-title">
          Needs Review — Behavioral Impact (${r.needs_review.length})
        </div>
        <div class="finding-card" id="nr-list">
          ${r.needs_review.map((d, i) => renderFindingItem(d, "needs_review", i, false)).join("") || '<div class="empty-state">None</div>'}
        </div>
      </div>
    </div>

    <details style="margin-top:8px;">
      <summary style="cursor:pointer;font-size:13px;color:var(--muted);margin-bottom:6px;">
        Unknown / out-of-scope areas (${r.unknown.length})
      </summary>
      <ul class="unknown-list">
        ${r.unknown.map(u => `<li>${esc(u)}</li>`).join("")}
      </ul>
    </details>

    <div id="source-viewer-panel"></div>

    <div class="btn-row" style="margin-top:16px;">
      <button class="btn btn-secondary" id="btn-step3-back">← Back</button>
      <button class="btn btn-primary" id="btn-step3-next">Triage Findings →</button>
    </div>
  </div>`;
}

/* ── Step 4 — Triage ─────────────────────────────────────── */
function renderStep4() {
  if (!state.report) { renderStep(3); return ""; }
  const r = state.report;

  const allFindings = [
    ...r.confirmed.map((d, i) => ({ ...d, _tier: "confirmed", _i: i })),
    ...r.needs_review.map((d, i) => ({ ...d, _tier: "needs_review", _i: i })),
  ];

  const wtBanner = state.walkthrough ? `
    <div class="walkthrough-banner">
      <strong>Sample walkthrough:</strong> Mark each finding Relevant, Not Relevant,
      or Needs Investigation. Decisions are recorded in the export.
      They do not alter the engine's output.
    </div>` : "";

  return `<div class="content-area">
    ${wtBanner}
    <div class="section-title">Step 4 — Triage Findings</div>
    <p class="section-desc">
      Mark each finding as <strong>Relevant</strong>, <strong>Not Relevant</strong>,
      or <strong>Needs Investigation</strong> for your change.
      These decisions are yours — the engine cannot make them.
      Triage state is stored locally in this session only.
    </p>

    ${allFindings.map(d => renderFindingItem(d, d._tier, d._i, true)).join("")}

    <div id="source-viewer-panel"></div>
    <div class="btn-row" style="margin-top:16px;">
      <button class="btn btn-secondary" id="btn-step4-back">← Back</button>
      <button class="btn btn-primary" id="btn-step4-next">Build Checklist →</button>
    </div>
  </div>`;
}

/* ── Step 5 — Checklist ──────────────────────────────────── */
function renderStep5() {
  if (!state.report) { renderStep(3); return ""; }
  const r = state.report;

  const ACTIONS = {
    DEFINES:         "Update definition; document business rule for new value",
    WRITES_FIELD:    "Confirm new value is written and validated correctly",
    READS_FIELD:     "Verify read usage handles new value without error",
    SQL_PREDICATE:   "Review predicate — determine if exhaustive/negative pattern breaks with new value",
    DIRECT_CALLER:   "Test caller output with changed behavior; update expected values",
    COBOL_CALL:      "Test COBOL caller output with changed behavior",
    INDIRECT_CALLER: "Verify end-to-end downstream output; re-run integration test",
    COPY_MEMBER:     "Verify all COPY usages handle field change; regression test each program",
  };

  const rows = [];
  let rowNum = 1;

  // Confirmed rows
  r.confirmed.forEach((d, i) => {
    const tk = `confirmed:${i}`;
    const triage = state.triageMap[tk] || "unset";
    const action = ACTIONS[d.relationship] || "Review for compatibility";
    const ev = d.evidence[0];
    rows.push({ n: rowNum++, target: d.target, rel: d.relationship,
                tier: "confirmed", triage, action,
                evidence: ev ? `${ev.source_path}:${ev.line_no}` : "",
                note: d.note });
  });

  // Needs-review rows
  r.needs_review.forEach((d, i) => {
    const tk = `needs_review:${i}`;
    const triage = state.triageMap[tk] || "unset";
    rows.push({ n: rowNum++, target: d.target, rel: d.relationship,
                tier: "needs-review", triage,
                action: d.review_question || "Human review required",
                evidence: d.evidence[0] ? `${d.evidence[0].source_path}:${d.evidence[0].line_no}` : "",
                note: d.note });
  });

  const triageWarning = rows.some(r => r.triage === "unset") ?
    `<div class="disclaimer-box" style="margin-bottom:14px;">
      Some findings have not been triaged. Return to Step 4 to mark them,
      or export with unresolved items.
    </div>` : "";

  return `<div class="content-area">
    <div class="section-title">Step 5 — Change &amp; Regression Checklist</div>
    <p class="section-desc">
      Each row is tied to a confirmed source relationship or a human-entered
      business invariant. Expected results are not generated from token matches alone —
      mark invariants in Step 4 comments and in your own test suite.
    </p>
    ${triageWarning}
    <div style="overflow-x:auto;">
      <table class="checklist-table">
        <thead>
          <tr>
            <th>#</th><th>Artifact</th><th>Relationship</th><th>Action / Test Required</th>
            <th>Evidence</th><th>Tier</th><th>Triage</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map(row => `
            <tr>
              <td>${row.n}</td>
              <td><code>${esc(row.target)}</code></td>
              <td><span class="rel-badge rel-${row.rel}">${esc(row.rel)}</span></td>
              <td style="font-size:12px;">${esc(row.action)}</td>
              <td style="font-family:var(--font-mono);font-size:11px;color:var(--accent)">
                ${esc(row.evidence)}
              </td>
              <td><span class="tier-${row.tier}">${row.tier}</span></td>
              <td style="font-size:11px;">${triageLabel(row.triage)}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>
    <div class="btn-row" style="margin-top:16px;">
      <button class="btn btn-secondary" id="btn-step5-back">← Back</button>
      <button class="btn btn-primary" id="btn-step5-next">Export Report →</button>
    </div>
  </div>`;
}

/* ── Step 6 — Export ─────────────────────────────────────── */
function renderStep6() {
  if (!state.report) { renderStep(3); return ""; }
  const text = buildExportText();
  return `<div class="content-area">
    <div class="section-title">Step 6 — Export Report</div>
    <p class="section-desc">
      The report below contains the change request, selected artifact, engine evidence,
      human triage decisions, unresolved areas, suggested tests, and limitations.
      Copy or download it.
    </p>
    <div class="btn-row" style="margin-bottom:14px;">
      <button class="btn btn-secondary" id="btn-step6-back">← Back</button>
      <button class="btn btn-primary" id="btn-copy-export">Copy to Clipboard</button>
      <button class="btn btn-secondary" id="btn-download-export">Download .md</button>
    </div>
    <div class="export-preview" id="export-preview">${esc(text)}</div>
  </div>`;
}

/* ── Finding item renderer ───────────────────────────────── */
function renderFindingItem(dep, tier, index, showTriage) {
  const key    = `${tier}:${index}`;
  const triage = state.triageMap[key];
  const tCls   = triage === "relevant" ? "triage-relevant"
               : triage === "not-relevant" ? "triage-not-relevant"
               : triage === "investigate"  ? "triage-investigate"
               : "";

  const evHtml = dep.evidence.map(ev => `
    <div class="finding-ev">
      <span class="ev-path" data-path="${esc(ev.source_path)}" data-line="${ev.line_no}"
            title="View source">${esc(ev.source_path)}</span>
      <span class="ev-line">:${ev.line_no}</span>
      <span class="ev-text">${esc(ev.match_text || ev.line_text || "")}</span>
    </div>`).join("");

  const triageHtml = showTriage ? `
    <div class="triage-row">
      <button class="triage-btn ${triage === 'relevant' ? 'active-relevant' : ''}"
              data-key="${key}" data-val="relevant">✓ Relevant</button>
      <button class="triage-btn ${triage === 'not-relevant' ? 'active-not' : ''}"
              data-key="${key}" data-val="not-relevant">— Not Relevant</button>
      <button class="triage-btn ${triage === 'investigate' ? 'active-investigate' : ''}"
              data-key="${key}" data-val="investigate">? Needs Investigation</button>
    </div>` : "";

  return `<div class="finding-item ${tCls}" data-key="${key}">
    <div class="finding-header">
      <span class="finding-target">${esc(dep.target)}</span>
      <span class="rel-badge rel-${dep.relationship}">${esc(dep.relationship)}</span>
      <span class="info-pill">${tier === "confirmed" ? "confirmed" : "needs review"}</span>
    </div>
    <div class="finding-note">${esc(dep.note)}</div>
    ${dep.review_question ? `<div class="finding-note" style="color:var(--warn)">
      ❓ ${esc(dep.review_question)}</div>` : ""}
    ${evHtml}
    ${triageHtml}
  </div>`;
}

/* ── Step event binding ──────────────────────────────────── */
function bindStepHandlers(step) {
  const $ = id => document.getElementById(id);

  if (step === 1) {
    $("btn-step1-next")?.addEventListener("click", () => {
      state.changeRequest = ($("cr-text")?.value || "").trim();
      renderStep(2);
    });
  }

  if (step === 2) {
    $("btn-step2-back")?.addEventListener("click", () => renderStep(1));
    $("btn-step2-next")?.addEventListener("click", () => runAnalysis());
    $("btn-sym-search")?.addEventListener("click", () => searchSymbols());
    $("sym-search")?.addEventListener("keydown", e => {
      if (e.key === "Enter") searchSymbols();
    });
  }

  if (step === 3) {
    $("btn-step3-back")?.addEventListener("click", () => renderStep(2));
    $("btn-step3-next")?.addEventListener("click", () => renderStep(4));
    bindSourceViewers();
  }

  if (step === 4) {
    $("btn-step4-back")?.addEventListener("click", () => renderStep(3));
    $("btn-step4-next")?.addEventListener("click", () => renderStep(5));
    bindSourceViewers();
    document.querySelectorAll(".triage-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.key;
        const val = btn.dataset.val;
        state.triageMap[key] = (state.triageMap[key] === val) ? null : val;
        renderStep(4);
      });
    });
  }

  if (step === 5) {
    $("btn-step5-back")?.addEventListener("click", () => renderStep(4));
    $("btn-step5-next")?.addEventListener("click", () => renderStep(6));
  }

  if (step === 6) {
    $("btn-step6-back")?.addEventListener("click", () => renderStep(5));
    $("btn-copy-export")?.addEventListener("click", async () => {
      await navigator.clipboard.writeText(buildExportText());
      const btn = $("btn-copy-export");
      btn.textContent = "Copied!";
      setTimeout(() => btn.textContent = "Copy to Clipboard", 1500);
    });
    $("btn-download-export")?.addEventListener("click", () => {
      const a = document.createElement("a");
      const artifact = state.report?.starting_artifact || "artifact";
      a.download = `ciw_impact_${artifact.toLowerCase()}.md`;
      a.href = "data:text/markdown;charset=utf-8," + encodeURIComponent(buildExportText());
      a.click();
    });
  }
}

/* ── Source viewer ───────────────────────────────────────── */
function bindSourceViewers() {
  document.querySelectorAll(".ev-path").forEach(el => {
    el.addEventListener("click", async () => {
      const path = el.dataset.path;
      const line = parseInt(el.dataset.line) || 0;
      const panel = document.getElementById("source-viewer-panel");
      if (!panel) return;
      panel.innerHTML = `<div class="source-viewer"><div class="source-viewer-header">
        ${esc(path)} · Loading… <button class="source-viewer-close" id="sv-close">✕</button>
      </div></div>`;
      document.getElementById("sv-close")?.addEventListener("click", () => { panel.innerHTML = ""; });
      try {
        const resp = await fetch(`/api/source?path=${encodeURIComponent(path)}&line=${line}`);
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        renderSourceViewer(panel, data, path);
      } catch (e) {
        panel.innerHTML = `<div class="disclaimer-box">Source view error: ${esc(String(e))}</div>`;
      }
    });
  });
}

function renderSourceViewer(panel, data, path) {
  const hl = data.highlight_line;
  const linesHtml = data.lines.map(ln => `
    <div class="source-line ${ln.no === hl ? 'hl' : ''}">
      <span class="ln">${ln.no}</span>
      <span class="lc">${esc(ln.text)}</span>
    </div>`).join("");

  panel.innerHTML = `
    <div class="source-viewer">
      <div class="source-viewer-header">
        <span>${esc(path)}</span>
        <button class="source-viewer-close" id="sv-close">✕</button>
      </div>
      <div class="source-lines" id="sv-lines">${linesHtml}</div>
    </div>`;

  document.getElementById("sv-close")?.addEventListener("click", () => { panel.innerHTML = ""; });

  // Scroll to highlighted line
  if (hl > 0) {
    const hlEl = panel.querySelector(".source-line.hl");
    hlEl?.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

/* ── Symbol search ───────────────────────────────────────── */
async function searchSymbols() {
  const q = document.getElementById("sym-search")?.value?.trim() || "";
  const resultsDiv = document.getElementById("sym-results");
  if (!resultsDiv) return;
  resultsDiv.innerHTML = `<div><span class="spinner"></span></div>`;
  try {
    const resp = await fetch(`/api/symbols?q=${encodeURIComponent(q)}`);
    const data = await resp.json();
    if (!data.results.length) {
      resultsDiv.innerHTML = `<div class="empty-state" style="padding:10px 0;">No symbols found for "${esc(q)}"</div>`;
      return;
    }
    resultsDiv.innerHTML = `<div style="border:1px solid var(--border);border-radius:var(--radius);
      overflow:hidden;max-height:220px;overflow-y:auto;margin-bottom:12px;">
      ${data.results.slice(0, 30).map(r => `
        <div class="tree-node clickable sym-pick" data-name="${esc(r.name)}" data-type="${esc(r.type)}"
             data-lang="${esc(r.lang||'')}" data-path="${esc(r.source_path||'')}"
             data-line="${r.line_no||''}" style="border-left:none;margin-left:0;padding:8px 12px;">
          <strong>${esc(r.name)}</strong>
          <span class="info-pill" style="margin-left:6px;">${esc(r.type)}</span>
          <span class="info-pill" style="margin-left:4px;">${esc(r.language||r.lang||'')}</span>
          ${r.container ? `<span style="font-size:11px;color:var(--muted);margin-left:6px;">in ${esc(r.container)}</span>` : ''}
        </div>`).join("")}
    </div>`;
    resultsDiv.querySelectorAll(".sym-pick").forEach(el => {
      el.addEventListener("click", () => {
        state.selected = {
          name:        el.dataset.name,
          type:        el.dataset.type,
          lang:        normLang(el.dataset.lang),
          source_path: el.dataset.path,
          line_no:     el.dataset.line ? parseInt(el.dataset.line) : undefined,
        };
        renderStep(2);
      });
    });
  } catch (e) {
    resultsDiv.innerHTML = `<div class="disclaimer-box">Search error: ${esc(String(e))}</div>`;
  }
}

/* ── Run analysis ────────────────────────────────────────── */
async function runAnalysis() {
  if (!state.selected) return;
  state.report = null;
  state.triageMap = {};
  renderStep(3);  // shows spinner

  try {
    const resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        artifact:      state.selected.name,
        artifact_type: state.selected.type,
        lang:          state.selected.lang || null,
        change_request: state.changeRequest,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      state.report = { error: err.error || "Analysis failed" };
    } else {
      state.report = await resp.json();
    }
  } catch (e) {
    state.report = { error: String(e) };
  }
  renderStep(3);
}

/* ── Export builder ──────────────────────────────────────── */
function buildExportText() {
  const r = state.report;
  if (!r) return "No report generated.";

  const now = new Date().toISOString().slice(0, 16).replace("T", " ");
  const wt  = state.walkthrough ? `\nSample walkthrough: ${WALKTHROUGHS[state.walkthrough].label}` : "";

  let out = `# Change Impact Report — Legacy Retail Co\n`;
  out += `Generated: ${now}${wt}\n\n`;
  out += `## Limitations\n${r.engine_disclaimer}\n\n`;
  out += `## Change Request\n${r.change_request || "(not provided)"}\n\n`;
  out += `## Starting Artifact\n`;
  out += `- Name: ${r.starting_artifact}\n- Type: ${r.artifact_type}\n- Language scope: ${r.lang}\n\n`;

  out += `## Confirmed Source References (${r.confirmed.length})\n\n`;
  r.confirmed.forEach((d, i) => {
    const tk = `confirmed:${i}`;
    out += `### ${d.target}  [${d.relationship}]\n`;
    out += `- Note: ${d.note}\n`;
    out += `- Triage: ${state.triageMap[tk] || "unset"}\n`;
    d.evidence.forEach(ev => {
      out += `- Evidence: ${ev.source_path}:${ev.line_no} → ${ev.match_text}\n`;
    });
    out += "\n";
  });

  out += `## Needs Review — Behavioral Impact (${r.needs_review.length})\n\n`;
  r.needs_review.forEach((d, i) => {
    const tk = `needs_review:${i}`;
    out += `### ${d.target}  [${d.relationship}]\n`;
    out += `- Note: ${d.note}\n`;
    if (d.review_question) out += `- Review question: ${d.review_question}\n`;
    out += `- Triage: ${state.triageMap[tk] || "unset"}\n`;
    d.evidence.forEach(ev => {
      out += `- Evidence: ${ev.source_path}:${ev.line_no} → ${ev.match_text}\n`;
    });
    out += "\n";
  });

  out += `## Unknown / Out-of-Scope\n`;
  r.unknown.forEach(u => { out += `- ${u}\n`; });

  // Triage summary
  const allTriaged = Object.values(state.triageMap).filter(Boolean);
  const unresolvedCount = (r.confirmed.length + r.needs_review.length) - allTriaged.length;
  out += `\n## Human Decisions Summary\n`;
  out += `- Relevant: ${allTriaged.filter(v => v === "relevant").length}\n`;
  out += `- Not relevant: ${allTriaged.filter(v => v === "not-relevant").length}\n`;
  out += `- Needs investigation: ${allTriaged.filter(v => v === "investigate").length}\n`;
  out += `- Unset: ${unresolvedCount}\n`;

  out += `\n---\nChange Impact Workbench · IBM Bob 2.0 Hackathon · Legacy Retail Co\n`;
  out += `Source-repository analysis prototype. No IBM i / mainframe connection.\n`;
  return out;
}

/* ── Triage label ────────────────────────────────────────── */
function triageLabel(t) {
  if (t === "relevant")     return `<span style="color:var(--ok);font-weight:700">✓ Relevant</span>`;
  if (t === "not-relevant") return `<span style="color:var(--muted)">— Not Relevant</span>`;
  if (t === "investigate")  return `<span style="color:var(--warn);font-weight:700">? Investigate</span>`;
  return `<span style="color:var(--muted);font-style:italic">unset</span>`;
}

/* ── Escape ──────────────────────────────────────────────── */
function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

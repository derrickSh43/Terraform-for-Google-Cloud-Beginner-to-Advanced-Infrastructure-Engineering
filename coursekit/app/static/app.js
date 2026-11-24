/* Course app: lesson flow (learn -> lab -> challenge -> troubleshoot -> done), editor, checks. */
"use strict";

const STEP_LABEL = { learn: "Learn", lab: "Lab", challenge: "Challenge", broken: "Troubleshoot", done: "Done" };
const S = {
  course: null, lesson: null, stage: "learn", viewStage: null,
  target: "workspace",            // which folder the editor shows: workspace | broken
  files: [], open: null, models: {}, dirty: new Set(),
  report: null, checking: false, editor: null, monaco: null, resultsTab: "req",
};

// ------------------------------------------------------------------ utilities
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

let toastTimer;
function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg; t.className = kind; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), 3500);
}

const prog = () => S.lesson.progress || (S.lesson.progress = {});
const stepDone = (s) => ["passed", "skipped"].includes(prog()[s]);

async function saveProgress(patch) {
  const r = await api("/api/progress", { id: S.lesson.id, progress: patch });
  S.lesson.progress = r.progress;
}

function currentStage() {
  if (!S.lesson.started) return "learn";
  for (const s of S.lesson.steps) if (!stepDone(s)) return s;
  return "done";
}

// ------------------------------------------------------------------ boot
async function boot() {
  S.course = await api("/api/course");
  renderDrawer();
  const editorReady = loadEditor();          // load the editor while the lesson renders
  S.editorReady = editorReady;
  const want = new URLSearchParams(location.search).get("lesson");
  await openLesson(want || S.course.current);
}

async function openLesson(id) {
  if (S.dirty.size && !confirm("You have unsaved changes. Save them first?")) { /* discard */ } else if (S.dirty.size) await saveAll();
  S.lesson = await api(`/api/lesson?id=${id}`);
  S.report = null; S.viewStage = null;
  S.stage = currentStage();
  history.replaceState(null, "", `?lesson=${S.lesson.id}`);
  $("#lesson-title").textContent = `Lesson ${S.lesson.id} · ${S.lesson.title}`;
  document.title = `${S.lesson.id} · ${S.lesson.title}`;
  $("#drawer").hidden = true;
  renderDrawer();
  render();
  renderResults();
  await switchTarget(S.stage === "broken" ? "broken" : "workspace", true);
}

// ------------------------------------------------------------------ header + drawer
function renderStages() {
  const stages = ["learn", ...S.lesson.steps, "done"];
  const cur = S.stage, view = S.viewStage || S.stage;
  $("#stages").innerHTML = stages.map((s, i) => {
    let cls = "stage", dot = "○";
    const st = s === "learn" ? (S.lesson.started ? "passed" : "") : s === "done" ? (cur === "done" ? "passed" : "") : prog()[s];
    if (st === "passed") { cls += " done"; dot = "✓"; }
    if (st === "skipped") { cls += " skipped"; dot = "–"; }
    if (s === view) { cls += " current"; dot = s === cur && st !== "passed" ? "●" : dot; }
    const reachable = s === "learn" || st || s === cur;
    return (i ? '<span class="stage-sep">›</span>' : "") +
      `<button class="${cls}" data-stage="${s}" ${reachable ? "" : "disabled"}><span class="dot">${dot}</span>${STEP_LABEL[s]}</button>`;
  }).join("");
  $("#stages").querySelectorAll("button").forEach((b) => b.onclick = () => viewStage(b.dataset.stage));
}

async function viewStage(s) {
  S.viewStage = s === S.stage ? null : s;
  if (S.lesson.started) await switchTarget(s === "broken" ? "broken" : "workspace");
  render();
}

function renderDrawer() {
  if (!S.course) return;
  const names = { 1: "Foundations", 2: "Core infrastructure", 3: "Cloud apps & automation", 4: "Advanced & system design" };
  let html = "", phase = null;
  for (const l of S.course.lessons) {
    if (l.phase !== phase) { phase = l.phase; html += `<div class="phase-head">Phase ${phase} · ${names[phase] || ""}</div>`; }
    const mark = l.done ? "✓" : l.started ? "●" : "";
    const cls = ["lesson-item", l.status !== "ready" ? "planned" : "", S.lesson && S.lesson.id === l.id ? "active" : ""].join(" ");
    html += `<div class="${cls}" data-id="${l.id}"><span class="num">${l.id}</span><span class="mark" style="color:${l.done ? "var(--ok)" : "var(--accent)"}">${mark}</span><span>${esc(l.title)}</span></div>`;
  }
  $("#lesson-list").innerHTML = html;
  $("#lesson-list").querySelectorAll(".lesson-item:not(.planned)").forEach((el) => el.onclick = () => openLesson(el.dataset.id));
}

// ------------------------------------------------------------------ left pane
function render() {
  renderStages();
  const view = S.viewStage || S.stage;
  const c = $("#content");
  if (view === "learn") c.innerHTML = learnView();
  else if (view === "lab" || view === "challenge") c.innerHTML = taskView(view);
  else if (view === "broken") c.innerHTML = brokenView();
  else c.innerHTML = doneView();
  c.scrollTop = 0; $("#left").scrollTop = 0;
  wireContent();
}

function learnView() {
  const L = S.lesson;
  let start = "";
  if (!L.started) {
    start = `<div class="card"><div class="kicker">Ready?</div>
      <p>Read the lesson below, then set up your files. They open in the editor on the right.</p>
      <div class="actions">` +
      (L.prev_started ? `<button class="primary big" data-act="start-mine">Start, continuing from my lesson ${L.prev} work</button>
                         <button data-act="start-fresh">Start from the official starter</button>`
                      : `<button class="primary big" data-act="start-fresh">Start the lab →</button>`) +
      `</div></div>`;
  } else {
    start = `<div class="card"><div class="actions"><button class="primary" data-act="goto-current">Continue: ${STEP_LABEL[S.stage]} →</button></div></div>`;
  }
  return `<div class="hero">${start}</div>${L.readme}${!L.started ? start : ""}`;
}

function taskIndex(step) {
  const n = S.lesson.tasks[step].length;
  return Math.min(prog()[`${step}_task`] || 0, n - 1);
}

function outcomesFor(ids) {
  if (!S.report) return [];
  return S.report.requirements.filter((r) => ids.includes(r.id));
}

function outcomeHtml(o) {
  return `<div class="outcome ${o.passed ? "pass" : "fail"}"><div class="head">${o.passed ? "✓" : "✗"} ${esc(o.id)} · ${esc(o.title)}</div>` +
    (o.passed ? "" : (o.message ? `<div class="msg">${esc(o.message)}</div>` : "") + (o.hint ? `<div class="hint">Hint: ${esc(o.hint)}</div>` : "")) + `</div>`;
}

function taskView(step) {
  const tasks = S.lesson.tasks[step];
  const done = prog()[step];
  const i = taskIndex(step);
  const t = tasks[i];
  const passed = new Set(S.report ? S.report.passed_ids : []);
  const failedStages = S.report ? S.report.stages.filter((s) => s.status === "fail") : [];
  let status = "";
  if (S.report && !S.checking && (t.ids.length || t.final)) {
    if (t.final) {
      status = S.report.passed && S.report.level === (step === "challenge" ? "challenge" : "lab")
        ? `<div class="card ok"><b>✓ ${STEP_LABEL[step]} complete.</b></div>`
        : `<div class="card bad"><b>Not everything passes yet.</b>${failedStages.map(stageHtml).join("")}${S.report.requirements.filter((r) => !r.passed).map(outcomeHtml).join("")}</div>`;
    } else {
      const mine = outcomesFor(t.ids);
      const ok = mine.length && mine.every((o) => o.passed);
      status = `<div class="card ${ok ? "ok" : "bad"}">${ok ? "<b>✓ Task done.</b>" : '<div class="kicker">From your last check</div>'}${failedStages.map(stageHtml).join("")}${mine.map(outcomeHtml).join("")}` +
        (!mine.length && failedStages.length ? `<div class="note">The requirement checks run once the configuration is valid.</div>` : "") + `</div>`;
    }
  }
  const chips = t.ids.map((id) => `<span class="chip ${passed.has(id) ? "pass" : (S.report && S.report.requirements.some((r) => r.id === id) ? "fail" : "")}">${id}</span>`).join("");
  const info = !t.ids.length && !t.final;
  const doneTask = t.final ? false : (t.ids.length && t.ids.every((id) => passed.has(id)));
  const finalOk = t.final && S.report && S.report.passed && S.report.level === (step === "challenge" ? "challenge" : "lab");
  let actions;
  if (done && t.final) actions = `<button class="primary" data-act="goto-current">Continue: ${STEP_LABEL[S.stage]} →</button>`;
  else if (finalOk) actions = `<button class="primary big" data-act="step-complete">${step === "lab" ? "On to the next part →" : "Continue →"}</button>`;
  else if (info) actions = `<button class="primary" data-act="next-task">Continue →</button>`;
  else if (doneTask) actions = `<button class="primary big" data-act="next-task">Next task →</button>`;
  else actions = `<button class="primary big" data-act="check">${S.checking ? '<span class="spinner"></span>Checking…' : "▶ Check this task"}</button>`;
  actions += i > 0 ? `<button class="ghost" data-act="prev-task">◀ Back</button>` : "";
  if (!t.final && !doneTask && !info) actions += `<button class="ghost" data-act="skip-task">Skip task</button>`;
  if (t.final && !finalOk && !done) actions += `<button class="ghost" data-act="skip-step">Skip the ${STEP_LABEL[step].toLowerCase()}</button>`;

  const list = tasks.map((x, k) => {
    const ok = x.ids.length && x.ids.every((id) => passed.has(id));
    return `<li class="${k === i ? "current" : ""} ${ok ? "passed" : ""}" data-task="${k}">${ok ? "✓" : k === i ? "●" : "○"} ${esc(x.title)}</li>`;
  }).join("");
  const shellNote = /terraform (init|plan|validate)|course\.py/.test(t.html)
    ? `<div class="note">In this app, <b>▶ Check</b> runs <code>terraform init</code>, <code>validate</code> and an offline <code>plan</code> for you. Results appear under the editor.</div>` : "";
  return `<div class="kicker">${STEP_LABEL[step]} · task ${i + 1} of ${tasks.length}</div>
    <div class="task-title">${esc(t.title)}</div><div class="chips">${chips}</div>
    ${t.final ? `<p>${esc(step === "lab" ? "Everything in the lab must pass, including the guard rails that protect what is already deployed." : "Lab and challenge requirements together, one last time.")}</p>` : t.html}
    ${shellNote}<div id="task-status">${status}<div class="actions">${actions}</div></div>
    <div class="card"><div class="kicker">All tasks</div><ul class="tasklist">${list}</ul></div>`;
}

function stageHtml(s) {
  return `<div class="outcome fail"><div class="head">✗ ${esc(s.name)}: ${esc(s.summary)}</div>${s.detail ? `<div class="msg">${esc(s.detail.split("\n").slice(0, 30).join("\n"))}</div>` : ""}</div>`;
}

function brokenView() {
  const done = prog().broken;
  const ok = S.report && S.report.passed && S.target === "broken";
  return `<div class="kicker">Troubleshooting</div><div class="task-title">Something is broken. Find out what, and fix it.</div>
    ${S.lesson.broken}
    <div class="note">The broken configuration is open in the editor (<code>workspace/${S.lesson.id}-broken</code>). Press ▶ Check to see how it fails.</div>
    ${S.report && S.target === "broken" && !S.checking ? `<div id="task-status" class="card ${ok ? "ok" : "bad"}">${ok ? "<b>✓ Fixed!</b> Compare your reasoning with the answer." : "<b>Still failing.</b>"}${S.report.stages.filter((s) => s.status === "fail").map(stageHtml).join("")}${S.report.requirements.filter((r) => !r.passed).map(outcomeHtml).join("")}</div>` : ""}
    <div class="actions">${ok || done ? `<button class="primary big" data-act="broken-done">Finish the lesson →</button>` :
      `<button class="primary big" data-act="check">${S.checking ? '<span class="spinner"></span>Checking…' : "▶ Check my fix"}</button>`}
      <button class="ghost" data-act="answer">Show the answer</button>
      ${ok || done ? "" : `<button class="ghost" data-act="skip-step">Skip troubleshooting</button>`}
      <button class="ghost" data-act="reset-broken">Restore the broken files</button></div>
    <div id="answer"></div>`;
}

function doneView() {
  const L = S.lesson;
  const idx = S.course.lessons.findIndex((l) => l.id === L.id);
  const next = S.course.lessons.slice(idx + 1).find((l) => l.status === "ready");
  const line = (s) => `<li>${STEP_LABEL[s]}: ${prog()[s] === "passed" ? "✓ passed" : "skipped"}</li>`;
  return `<div class="card ok"><div class="kicker">Lesson ${L.id} complete</div><div class="task-title">${esc(L.title)}</div>
    <ul>${L.steps.map(line).join("")}</ul><h3>You can now</h3>${L.objectives}
    <div class="actions">${next ? `<button class="primary big" data-act="next-lesson" data-id="${next.id}">Next lesson: ${next.id} · ${esc(next.title)} →</button>` : "<b>That was the last lesson. Congratulations!</b>"}
    <button class="ghost" data-act="view-learn">Re-read the lesson</button></div></div>`;
}

function wireContent() {
  const on = (act, fn) => document.querySelectorAll(`[data-act="${act}"]`).forEach((b) => b.onclick = fn);
  on("start-fresh", () => startLesson(false));
  on("start-mine", () => startLesson(true));
  on("goto-current", () => viewStage(S.stage));
  on("view-learn", () => viewStage("learn"));
  on("check", runCheck);
  on("next-task", () => moveTask(+1, true));
  on("prev-task", () => moveTask(-1));
  on("skip-task", () => moveTask(+1));
  on("skip-step", skipStep);
  on("step-complete", completeStep);
  on("answer", showAnswer);
  on("broken-done", completeBroken);
  on("reset-broken", resetBroken);
  on("next-lesson", (e) => openLesson(e.currentTarget.dataset.id));
  document.querySelectorAll(".tasklist li").forEach((li) => li.onclick = async () => {
    const step = S.viewStage || S.stage;
    await saveProgress({ [`${step}_task`]: +li.dataset.task }); render();
  });
  document.querySelectorAll("#content a[data-md-link]").forEach((a) => {
    const href = a.getAttribute("href");
    if (/^https?:/.test(href)) { a.target = "_blank"; a.rel = "noopener"; }
    else a.onclick = (e) => { e.preventDefault(); toast(`See ${href} in the lesson folder`); };
  });
}

// ------------------------------------------------------------------ flow actions
async function startLesson(fromMine) {
  try {
    await api("/api/start", { id: S.lesson.id, from_mine: fromMine });
    S.lesson = await api(`/api/lesson?id=${S.lesson.id}`);
    S.stage = currentStage(); S.viewStage = null;
    S.course = await api("/api/course"); renderDrawer();
    await switchTarget("workspace", true);
    render(); toast("Your files are ready in the editor.", "ok");
  } catch (e) { toast(e.message, "bad"); }
}

async function moveTask(delta, autoSkipPassing = false) {
  const step = S.viewStage || S.stage;
  const tasks = S.lesson.tasks[step];
  let i = taskIndex(step) + delta;
  if (autoSkipPassing && S.report) {
    const passed = new Set(S.report.passed_ids);
    while (i < tasks.length - 1 && tasks[i].ids.length && tasks[i].ids.every((id) => passed.has(id))) i++;
  }
  i = Math.max(0, Math.min(i, tasks.length - 1));
  await saveProgress({ [`${step}_task`]: i });
  render();
}

async function skipStep() {
  const step = S.viewStage || S.stage;
  if (!confirm(`Skip the ${STEP_LABEL[step].toLowerCase()}? You can come back to it from the bar at the top.`)) return;
  await saveProgress({ [step]: "skipped" });
  await advanceStage();
}

async function completeStep() {
  const step = S.viewStage || S.stage;
  await saveProgress({ [step]: "passed" });
  await advanceStage();
}

async function advanceStage() {
  S.stage = currentStage(); S.viewStage = null; S.report = null;
  if (S.stage === "broken") await api("/api/start", { id: S.lesson.id, target: "broken" });
  await switchTarget(S.stage === "broken" ? "broken" : "workspace", true);
  S.course = await api("/api/course"); renderDrawer();
  render(); renderResults();
}

async function completeBroken() { await saveProgress({ broken: "passed" }); await advanceStage(); }

async function resetBroken() {
  if (!confirm("Restore the original broken files? Your edits to the broken copy are lost.")) return;
  await api("/api/reset", { id: S.lesson.id, target: "broken" });
  for (const k of Object.keys(S.models)) S.models[k].dispose?.();
  S.models = {}; S.dirty.clear();
  await switchTarget("broken", true); toast("Broken files restored.");
}

async function showAnswer() {
  const r = await api(`/api/answer?id=${S.lesson.id}`);
  $("#answer").innerHTML = `<div class="card"><div class="kicker">Answer</div>${r.html}</div>`;
  $("#answer").scrollIntoView({ behavior: "smooth" });
}

// ------------------------------------------------------------------ checks
async function runCheck() {
  if (S.checking) return;
  if (!S.lesson.started) { toast("Start the lesson first."); return; }
  const view = S.viewStage || S.stage;
  await saveAll();
  S.checking = true; render(); renderResults();
  $("#btn-check").disabled = true;
  try {
    const challenge = view === "challenge" || (view === "done" && S.lesson.steps.includes("challenge"));
    S.report = await api("/api/check", { id: S.lesson.id, target: S.target, challenge });
    markErrors();
    const step = view;
    if (S.target === "broken" && S.report.passed) { await saveProgress({ broken: "passed" }); }
    if ((step === "lab" || step === "challenge") && S.lesson.tasks[step]) {
      const t = S.lesson.tasks[step][taskIndex(step)];
      if (t.final && S.report.passed) await saveProgress({ [step]: "passed" });
    }
    const n = S.report.requirements.length, ok = S.report.requirements.filter((r) => r.passed).length;
    toast(S.report.passed ? "All checks pass ✓" : n ? `${ok}/${n} requirements met` : "A Terraform stage failed - see the details", S.report.passed ? "ok" : "bad");
  } catch (e) { toast(e.message, "bad"); }
  S.checking = false; $("#btn-check").disabled = false;
  render(); renderResults();
  const st = $("#task-status") || $("#content .card.ok, #content .card.bad");
  if (st) st.scrollIntoView({ behavior: "smooth", block: "start" });
}

function markErrors() {
  if (!S.monaco || !S.report) return;
  const byFile = {};
  for (const st of S.report.stages) {
    for (const m of (st.detail || "").matchAll(/\[(error|warning)\]\s+([^\s:]+):(\d+)\s+(.*)/g)) {
      const match = S.files.filter((f) => f === m[2] || f.endsWith("/" + m[2]));
      if (match.length !== 1) continue;
      (byFile[match[0]] ||= []).push({ severity: m[1] === "error" ? S.monaco.MarkerSeverity.Error : S.monaco.MarkerSeverity.Warning,
        startLineNumber: +m[3], endLineNumber: +m[3], startColumn: 1, endColumn: 200, message: m[4] });
    }
  }
  for (const [f, model] of Object.entries(S.models)) if (model.uri) S.monaco.editor.setModelMarkers(model, "course", byFile[f] || []);
}

function renderResults() {
  const body = $("#results-body"), r = S.report;
  document.querySelectorAll("#results-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === S.resultsTab));
  if (S.checking) { body.innerHTML = `<div class="pad"><span class="spinner"></span>Running terraform fmt, init, validate and an offline plan, then the requirement checks… (this can take a minute)</div>`; $("#results-summary").textContent = ""; return; }
  if (!r) { body.innerHTML = `<div class="muted pad">Press ▶ Check to run terraform fmt, init, validate and an offline plan, then the lesson's requirement checks.</div>`; $("#results-summary").textContent = ""; return; }
  const n = r.requirements.length, ok = r.requirements.filter((x) => x.passed).length;
  $("#results-summary").innerHTML = r.passed ? `<span style="color:var(--ok)">✓ all checks pass</span>` : `${ok}/${n} requirements · ${r.stages.filter((s) => s.status === "fail").length} failed stage(s)`;
  if (S.resultsTab === "req") {
    body.innerHTML = n ? `<div class="pad">${r.requirements.map(outcomeHtml).join("")}</div>` : `<div class="pad muted">Requirement checks didn't run - a Terraform stage failed. See Pipeline.</div>`;
  } else if (S.resultsTab === "pipeline") {
    body.innerHTML = r.stages.map((s) => `<div class="stage-row"><span class="st ${s.status}">${s.status.toUpperCase()}</span><span>${esc(s.name)}</span><span class="muted">${esc(s.summary)}</span></div>` +
      (s.status === "fail" && s.detail ? `<div class="detail">${esc(s.detail)}</div>` : "")).join("");
  } else if (S.resultsTab === "plan") {
    const plans = r.stages.filter((s) => s.name.startsWith("plan"));
    body.innerHTML = plans.length ? plans.map((s) => `<pre class="out"><b>${esc(s.name)}</b>\n${esc(s.detail || s.summary)}</pre>`).join("") : `<div class="pad muted">No plan yet - an earlier stage failed.</div>`;
  } else {
    const tests = r.stages.filter((s) => s.name.startsWith("tests"));
    body.innerHTML = tests.length ? tests.map((s) => `<div class="stage-row"><span class="st ${s.status}">${s.status.toUpperCase()}</span><span>${esc(s.name)}</span><span class="muted">${esc(s.summary)}</span></div>` + (s.detail ? `<div class="detail">${esc(s.detail)}</div>` : "")).join("") : `<div class="pad muted">This lesson has no terraform tests (or they didn't run).</div>`;
  }
}

// ------------------------------------------------------------------ editor
function langFor(path) {
  if (/\.(tf|tfvars|hcl|tftpl)$/.test(path)) return "hcl";
  if (/\.ya?ml$/.test(path)) return "yaml";
  if (/\.md$/.test(path)) return "markdown";
  if (/\.sh$/.test(path)) return "shell";
  if (/\.json$/.test(path)) return "json";
  if (/\.ps1$/.test(path)) return "powershell";
  return "plaintext";
}

function loadEditor() {
  return new Promise((resolve) => {
    const src = S.course.editor;
    const fallback = () => { if (!S.editor) { S.editor = plainEditor(); $("#editor-source").textContent = "editor: plain (run `python course.py setup` for the VS Code editor)"; } resolve(); };
    const timer = setTimeout(fallback, 8000);
    const s = document.createElement("script");
    s.src = `${src.vs}/loader.js`;
    s.onerror = () => { clearTimeout(timer); fallback(); };
    s.onload = () => {
      window.require.config({ paths: { vs: src.vs } });
      window.require(["vs/editor/editor.main"], () => {
        clearTimeout(timer);
        S.monaco = window.monaco;
        S.editor = S.monaco.editor.create($("#editor"), {
          theme: "vs-dark", automaticLayout: true, fontSize: 13, minimap: { enabled: false },
          tabSize: 2, insertSpaces: true, scrollBeyondLastLine: false, renderWhitespace: "selection", model: null,
        });
        S.editor.addCommand(S.monaco.KeyMod.CtrlCmd | S.monaco.KeyCode.KeyS, () => saveCurrent());
        S.editor.addCommand(S.monaco.KeyMod.CtrlCmd | S.monaco.KeyCode.Enter, () => runCheck());
        $("#editor-source").textContent = src.source === "local" ? "editor: Monaco (VS Code)" : "editor: Monaco (VS Code, from CDN)";
        resolve();
      }, fallback);
    };
    document.head.appendChild(s);
  });
}

function plainEditor() {
  const ta = document.createElement("textarea");
  ta.className = "plain"; ta.spellcheck = false; ta.disabled = true;
  $("#editor").appendChild(ta);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab") { e.preventDefault(); const p = ta.selectionStart; ta.setRangeText("  ", p, ta.selectionEnd, "end"); ta.dispatchEvent(new Event("input")); }
  });
  ta.addEventListener("input", () => { if (S.open) { S.models[S.open].text = ta.value; markDirty(S.open); } });
  return { plain: ta };
}

async function switchTarget(target, force = false) {
  await S.editorReady;
  if (S.target === target && !force && S.files.length) return;
  if (S.dirty.size) await saveAll();
  for (const m of Object.values(S.models)) m.dispose?.();
  S.models = {}; S.dirty.clear(); S.open = null; S.target = target;
  $("#files-label").textContent = target === "broken" ? `workspace/${S.lesson.id}-broken` : "Your files";
  if (!S.lesson.started && target === "workspace") { S.files = []; renderFiles(); showEmpty(true); return; }
  S.files = (await api(`/api/files?id=${S.lesson.id}&target=${target}`)).files;
  renderFiles();
  if (S.files.length) await openFile(S.files.find((f) => f === "main.tf") || S.files[0]); else showEmpty(true);
}

function showEmpty(on) {
  $("#editor-empty").hidden = !on;
  if (S.editor?.plain) S.editor.plain.hidden = on;
  if (S.editor && !S.editor.plain) $("#editor").querySelector(".monaco-editor") && ($("#editor").querySelector(".monaco-editor").style.visibility = on ? "hidden" : "visible");
}

function renderFiles() {
  $("#file-list").innerHTML = S.files.map((f) => {
    const i = f.lastIndexOf("/");
    const label = i < 0 ? esc(f) : `<span class="dir">${esc(f.slice(0, i + 1))}</span>${esc(f.slice(i + 1))}`;
    return `<div class="file ${f === S.open ? "active" : ""} ${S.dirty.has(f) ? "dirty" : ""}" data-f="${esc(f)}" title="${esc(f)}">${label}</div>`;
  }).join("");
  $("#file-list").querySelectorAll(".file").forEach((el) => el.onclick = () => openFile(el.dataset.f));
  const tabs = Object.keys(S.models);
  $("#tabs").innerHTML = tabs.map((f) => `<button class="tab ${f === S.open ? "active" : ""} ${S.dirty.has(f) ? "dirty" : ""}" data-f="${esc(f)}">${esc(f.split("/").pop())}</button>`).join("");
  $("#tabs").querySelectorAll(".tab").forEach((el) => el.onclick = () => openFile(el.dataset.f));
}

async function openFile(path) {
  if (!S.models[path]) {
    const r = await api(`/api/file?id=${S.lesson.id}&target=${S.target}&path=${encodeURIComponent(path)}`);
    if (S.monaco) {
      const uri = S.monaco.Uri.parse(`file:///${S.target}/${path}`);
      S.monaco.editor.getModel(uri)?.dispose();
      const model = S.monaco.editor.createModel(r.text, langFor(path), uri);
      model.onDidChangeContent(() => markDirty(path));
      S.models[path] = model;
    } else {
      S.models[path] = { text: r.text };
    }
  }
  S.open = path;
  showEmpty(false);
  if (S.monaco) S.editor.setModel(S.models[path]);
  else { S.editor.plain.disabled = false; S.editor.plain.value = S.models[path].text; }
  markErrors();
  renderFiles();
}

function markDirty(path) { if (!S.dirty.has(path)) { S.dirty.add(path); renderFiles(); } }

async function saveFile(path) {
  const m = S.models[path];
  const text = S.monaco ? m.getValue() : m.text;
  await api("/api/file", { id: S.lesson.id, target: S.target, path, text });
  S.dirty.delete(path);
}

async function saveCurrent() { if (S.open) { await saveFile(S.open); renderFiles(); toast(`Saved ${S.open}`, "ok"); } }
async function saveAll() { for (const p of [...S.dirty]) await saveFile(p); renderFiles(); }

async function formatFiles() {
  await saveAll();
  const r = await api("/api/fmt", { id: S.lesson.id, target: S.target });
  if (!r.ok) { toast("terraform fmt found a syntax error - see the message in Pipeline after ▶ Check", "bad"); return; }
  for (const f of r.changed) {
    if (!S.models[f]) continue;
    const t = (await api(`/api/file?id=${S.lesson.id}&target=${S.target}&path=${encodeURIComponent(f)}`)).text;
    if (S.monaco) { S.models[f].setValue(t); S.dirty.delete(f); } else { S.models[f].text = t; if (f === S.open) S.editor.plain.value = t; }
  }
  renderFiles();
  toast(r.changed.length ? `Formatted ${r.changed.join(", ")}` : "Already formatted ✓", "ok");
}

async function newFile() {
  if (!S.lesson.started) return;
  const name = prompt("New file (path inside your folder), e.g. outputs.tf or modules/web/main.tf");
  if (!name) return;
  try {
    await api("/api/file", { id: S.lesson.id, target: S.target, path: name.trim(), text: "" });
    S.files = (await api(`/api/files?id=${S.lesson.id}&target=${S.target}`)).files;
    await openFile(name.trim());
  } catch (e) { toast(e.message, "bad"); }
}

// ------------------------------------------------------------------ wiring
function wire() {
  $("#menu-btn").onclick = () => ($("#drawer").hidden = !$("#drawer").hidden);
  $("#drawer-close").onclick = () => ($("#drawer").hidden = true);
  $("#btn-save").onclick = () => saveCurrent();
  $("#btn-fmt").onclick = () => formatFiles();
  $("#btn-check").onclick = () => runCheck();
  $("#btn-new").onclick = () => newFile();
  document.querySelectorAll("#results-tabs button").forEach((b) => b.onclick = () => { S.resultsTab = b.dataset.tab; renderResults(); });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveCurrent(); }
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); runCheck(); }
  });
  window.addEventListener("beforeunload", (e) => { if (S.dirty.size) { e.preventDefault(); e.returnValue = ""; } });
  // resizable split
  const div = $("#divider"), left = $("#left");
  div.onmousedown = (e) => {
    e.preventDefault();
    const move = (ev) => { left.style.width = Math.max(300, Math.min(ev.clientX, window.innerWidth - 420)) + "px"; };
    const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
    document.addEventListener("mousemove", move); document.addEventListener("mouseup", up);
  };
}

wire();
boot().catch((e) => { $("#content").innerHTML = `<div class="card bad">Couldn't load the course: ${esc(e.message)}</div>`; });

const editor       = document.getElementById('code-editor');
const lineNums     = document.getElementById('line-numbers');
const syntaxLayer  = document.getElementById('syntax-highlight');
const errorLayer   = document.getElementById('error-lines');
const btnFix       = document.getElementById('btn-fix');
const editorView   = document.getElementById('editor-view');
const splitView    = document.getElementById('split-view');
const fixActions   = document.getElementById('fix-actions');
const splitOrig    = document.getElementById('split-orig');
const splitFixed   = document.getElementById('split-fixed');
const fixSummary   = document.getElementById('fix-summary-text');
const statRoles    = document.getElementById('stat-roles');
const statPerms    = document.getElementById('stat-perms');
const verdictBadge = document.getElementById('verdict-badge');
const issueList    = document.getElementById('issue-list');
const tokenTbody   = document.getElementById('token-tbody');
const astPre       = document.getElementById('ast-pre');
const symPre       = document.getElementById('sym-pre');
let currentAnalysis = null;
let currentFixes    = null;
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}
function highlightCode(text) {
    let html = escapeHtml(text);
    html = html.replace(/(\/\/[^\n]*)/g, '<span class="c-comment">$1</span>');
    html = html.replace(/\b(role|inherits|permissions|conflict|assign|to)\b/g, '<span class="c-keyword">$1</span>');
    return html;
}
function rebuildEditor() {
    const text  = editor.value;
    const lines = text.split('\n');
    lineNums.innerHTML = lines.map((_, i) => `<div class="ln-row">${i + 1}</div>`).join('');
    syntaxLayer.innerHTML = lines.map(l => `<div class="code-row">${highlightCode(l) || ' '}</div>`).join('');
    syncScroll();
}
function syncScroll() {
    const t = editor.scrollTop;
    const l = editor.scrollLeft;
    lineNums.scrollTop     = t;
    syntaxLayer.scrollTop  = t;
    syntaxLayer.scrollLeft = l;
    errorLayer.scrollTop   = t;
}
let debounceTimer;
editor.addEventListener('input', () => {
    rebuildEditor();
    if (currentAnalysis) {
        errorLayer.innerHTML = '';
        verdictBadge.textContent = 'ANALYZING...';
        verdictBadge.className = 'badge';
    }
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        if (editor.value.trim() === '') {
            resetAnalysis();
        } else {
            analyzePolicy();
        }
    }, 600);
});
editor.addEventListener('scroll', syncScroll);
editor.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
        e.preventDefault();
        const start = editor.selectionStart;
        const end   = editor.selectionEnd;
        editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
        editor.selectionStart = editor.selectionEnd = start + 4;
        editor.dispatchEvent(new Event('input'));
    }
});
function buildErrorOverlays(errors, warnings, risks) {
    const text  = editor.value;
    const lines = text.split('\n');
    const lineClasses = {};   // lineNum -> class
    const mark = (items, cls) => {
        items.forEach(item => {
            const ln = item.line;
            if (ln >= 1 && ln <= lines.length) {
                if (!lineClasses[ln] || cls === 'hl-error') lineClasses[ln] = cls;
            }
        });
    };
    mark(errors,   'hl-error');
    mark(risks,    'hl-risk');
    mark(warnings, 'hl-warning');
    errorLayer.innerHTML = lines.map((_, i) => {
        const ln = i + 1;
        const cls = lineClasses[ln] || '';
        return `<div class="code-row ${cls}" data-line="${ln}"></div>`;
    }).join('');
    syncScroll();
}
function jumpToLine(lineNum) {
    if (!lineNum || lineNum < 1) return;
    const firstRow = syntaxLayer.querySelector('.code-row');
    const rowH = firstRow ? firstRow.offsetHeight : 20;
    const target = (lineNum - 1) * rowH - editor.clientHeight / 2;
    editor.scrollTop = Math.max(0, target);
    syncScroll();
    const rows = errorLayer.querySelectorAll(`.code-row[data-line="${lineNum}"]`);
    rows.forEach(r => {
        r.classList.add('hl-pulse');
        setTimeout(() => r.classList.remove('hl-pulse'), 1200);
    });
}
document.getElementById('file-upload').addEventListener('change', function (e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
        editor.value = ev.target.result;
        rebuildEditor();
        resetAnalysis();
        if (editor.value.trim() !== '') {
            analyzePolicy();
        }
        this.value = ''; // allow re-uploading same file
    };
    reader.readAsText(file);
});
function loadExample() {
    editor.value =
`role Viewer {
    permissions: read
}
role Editor inherits Viewer {
    permissions: write
}
role Admin inherits Editor {
    permissions: delete
}
conflict Viewer, Admin
assign Admin to Alice
assign Viewer to Bob`;
    rebuildEditor();
    resetAnalysis();
    analyzePolicy();
}
function resetAnalysis() {
    currentAnalysis = null;
    currentFixes    = null;
    btnFix.disabled = true;
    verdictBadge.className   = 'badge';
    verdictBadge.textContent = 'PENDING';
    statRoles.textContent = '0';
    statPerms.textContent = '0';
    issueList.innerHTML = '<li class="empty-state">Run analysis to see results</li>';
    errorLayer.innerHTML = '';
    document.getElementById('count-error').textContent   = '0';
    document.getElementById('count-warning').textContent = '0';
    document.getElementById('count-risk').textContent    = '0';
}
async function analyzePolicy() {
    const code = editor.value.trim();
    if (!code) { alert('Editor is empty. Please type or upload a policy.'); return; }
    try {
        const res  = await fetch('/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code})
        });
        const data = await res.json();
        currentAnalysis = data;
        renderAnalysis(data);
    } catch (err) {
        alert('Could not reach the backend. Make sure app.py is running.');
        console.error(err);
    }
}
async function suggestFixes() {
    if (!currentAnalysis) return;
    try {
        const res  = await fetch('/fix', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({code: editor.value})
        });
        const data = await res.json();
        if (data.success) {
            currentFixes = data;
            showSplitView();
        } else {
            alert('Fix failed: ' + (data.error || 'unknown error'));
        }
    } catch (err) {
        alert('Could not reach the backend.');
        console.error(err);
    }
}
function renderAnalysis(data) {
    const s = data.summary || {};
    statRoles.textContent = s.roles ?? 0;
    statPerms.textContent = s.permissions ?? 0;
    verdictBadge.textContent = s.verdict || 'PENDING';
    verdictBadge.className = 'badge ' + {
        'SAFE':     'badge-success',
        'UNSAFE':   'badge-error',
        'WARNINGS': 'badge-warning',
    }[s.verdict] ?? '';
    const hasIssues = (data.errors && data.errors.length) ||
                      (data.warnings && data.warnings.length) ||
                      (data.risks && data.risks.length);
    btnFix.disabled = !hasIssues;
    buildErrorOverlays(data.errors || [], data.warnings || [], data.risks || []);
    renderIssues();
    tokenTbody.innerHTML = (data.tokens || [])
        .map(t => `<tr><td>${t.line}</td><td>${escapeHtml(t.type)}</td><td>${escapeHtml(String(t.value))}</td></tr>`)
        .join('');
    astPre.textContent = JSON.stringify(data.ast || {}, null, 2);
    symPre.textContent = JSON.stringify(data.symbol_table || {}, null, 2);
    if (data.graph && data.graph.nodes.length > 0) renderGraph(data.graph);
    else document.getElementById('d3-graph').innerHTML =
        '<p style="padding:1rem;color:#888;">No roles to visualise.</p>';
}
function renderIssues() {
    if (!currentAnalysis) return;
    const showErr  = document.getElementById('filter-error').checked;
    const showWarn = document.getElementById('filter-warning').checked;
    const showRisk = document.getElementById('filter-risk').checked;
    const errors   = currentAnalysis.errors   || [];
    const warnings = currentAnalysis.warnings || [];
    const risks    = currentAnalysis.risks    || [];
    document.getElementById('count-error').textContent   = errors.length;
    document.getElementById('count-warning').textContent = warnings.length;
    document.getElementById('count-risk').textContent    = risks.length;
    let html = '';
    const addItems = (items, cls, label, show) => {
        if (!show) return;
        items.forEach(item => {
            html += `<li onclick="jumpToLine(${item.line})">
                <div class="issue-badge ${cls}">${label}</div>
                <div class="issue-msg">${escapeHtml(item.message)}</div>
                <div class="issue-line">Line ${item.line}</div>
            </li>`;
        });
    };
    addItems(errors,   'error',   'ERROR', showErr);
    addItems(risks,    'risk',    'RISK',  showRisk);
    addItems(warnings, 'warning', 'WARN',  showWarn);
    issueList.innerHTML = html || '<li class="empty-state">✅ No issues match current filters.</li>';
}
document.getElementById('filter-error').addEventListener('change', renderIssues);
document.getElementById('filter-warning').addEventListener('change', renderIssues);
document.getElementById('filter-risk').addEventListener('change', renderIssues);
function showSplitView() {
    editorView.style.display = 'none';
    splitView.style.display  = 'flex';
    fixActions.style.display = 'flex';
    splitOrig.value  = editor.value;
    splitFixed.value = currentFixes.fixed_code;
    const log = currentFixes.changelog || [];
    const safe = log.filter(c => c.severity === 'SAFE').length;
    const heur = log.filter(c => c.severity === 'HEURISTIC').length;
    const dest = log.filter(c => c.severity === 'DESTRUCTIVE').length;
    fixSummary.innerHTML = `<strong>Fix Summary:</strong> ${safe} Safe · ${heur} Heuristic · ${dest} Destructive changes`;
}
function cancelFix() {
    editorView.style.display = 'flex';
    splitView.style.display  = 'none';
    fixActions.style.display = 'none';
    currentFixes = null;
}
function applyFix() {
    editor.value = splitFixed.value;
    rebuildEditor();
    cancelFix();
    analyzePolicy();
}
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => { c.style.display = 'none'; c.classList.remove('active'); });
    event.target.classList.add('active');
    const tab = document.getElementById(tabId);
    tab.style.display = 'flex';
    tab.classList.add('active');
}
function downloadReport() {
    if (!currentAnalysis) { alert('Analyze first.'); return; }
    const s = currentAnalysis.summary || {};
    let txt  = 'RBAC Policy Verification Report\n================================\n\n';
    if (currentAnalysis.errors.length)   txt += 'ERRORS:\n'   + currentAnalysis.errors.map(e => `  [Line ${e.line}] ${e.message}`).join('\n') + '\n\n';
    if (currentAnalysis.risks.length)    txt += 'RISKS:\n'    + currentAnalysis.risks.map(e => `  [Line ${e.line}] ${e.message}`).join('\n') + '\n\n';
    if (currentAnalysis.warnings.length) txt += 'WARNINGS:\n' + currentAnalysis.warnings.map(e => `  [Line ${e.line}] ${e.message}`).join('\n') + '\n\n';
    txt += `Verdict: ${s.verdict}\nRoles: ${s.roles} | Permissions: ${s.permissions}\n`;
    const blob = new Blob([txt], {type: 'text/plain'});
    const a = Object.assign(document.createElement('a'), {href: URL.createObjectURL(blob), download: 'rbac_report.txt'});
    a.click();
    URL.revokeObjectURL(a.href);
}
function renderGraph(graphData) {
    const container = document.getElementById('d3-graph');
    container.innerHTML = '';
    const W = container.clientWidth  || 600;
    const H = container.clientHeight || 380;
    const nodes = graphData.nodes.map(d => ({...d}));
    const links = graphData.edges.map(d => ({source: d.from, target: d.to, type: d.type}));
    const svg = d3.select('#d3-graph').append('svg')
        .attr('width', W).attr('height', H);
    svg.append('defs').selectAll('marker')
        .data(['inherits', 'conflict']).join('marker')
        .attr('id', d => `arr-${d}`)
        .attr('viewBox', '0 -5 10 10').attr('refX', 22).attr('refY', 0)
        .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
        .append('path')
        .attr('fill', d => d === 'conflict' ? '#dc3545' : '#888')
        .attr('d', 'M0,-5L10,0L0,5');
    const sim = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(120))
        .force('charge', d3.forceManyBody().strength(-350))
        .force('center', d3.forceCenter(W / 2, H / 2));
    const link = svg.append('g').selectAll('line').data(links).join('line')
        .attr('stroke', d => d.type === 'conflict' ? '#dc3545' : '#888')
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', d => d.type === 'conflict' ? '6 3' : 'none')
        .attr('marker-end', d => `url(#arr-${d.type})`);
    const node = svg.append('g').selectAll('circle').data(nodes).join('circle')
        .attr('r', 14)
        .attr('fill', d => d.color === 'cyclic' ? '#dc3545' : d.color === 'high_priv' ? '#fd7e14' : '#0d6efd')
        .attr('stroke', '#fff').attr('stroke-width', 2)
        .call(d3.drag()
            .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on('end',   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
    const label = svg.append('g').selectAll('text').data(nodes).join('text')
        .text(d => d.id).attr('font-size', 12).attr('dx', 18).attr('dy', 4)
        .attr('fill', '#333').attr('font-family', 'sans-serif');
    sim.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        label.attr('x', d => d.x).attr('y', d => d.y);
    });
}
rebuildEditor();

const editor = document.getElementById('code-editor');
const lineNums = document.getElementById('line-numbers');
const syntaxLayer = document.getElementById('syntax-highlight');
const errorLayer = document.getElementById('error-lines');
const btnFix = document.getElementById('btn-fix');
const editorView = document.getElementById('editor-view');
const splitView = document.getElementById('split-view');
const fixActions = document.getElementById('fix-actions');
const splitOrig = document.getElementById('split-orig');
const splitFixed = document.getElementById('split-fixed');
const fixSummary = document.getElementById('fix-summary-text');
const statRoles = document.getElementById('stat-roles');
const statPerms = document.getElementById('stat-perms');
const verdictBadge = document.getElementById('verdict-badge');
const issueList = document.getElementById('issue-list');
const tokenTbody = document.getElementById('token-tbody');
const astPre = document.getElementById('ast-pre');
const symPre = document.getElementById('sym-pre');
const filterError = document.getElementById('filter-error');
const filterWarning = document.getElementById('filter-warning');
const filterRisk = document.getElementById('filter-risk');
const countError = document.getElementById('count-error');
const countWarning = document.getElementById('count-warning');
const countRisk = document.getElementById('count-risk');
const graphContainer = document.getElementById('d3-graph');

const KEYWORD_PATTERN = /\b(role|inherits|permissions|conflict|assign|to)\b/g;

let currentAnalysis = null;
let currentFixes = null;
let debounceTimer;
let latestAnalysisRequest = 0;

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function highlightCode(text) {
    const escaped = escapeHtml(text);

    // Check for block comment spanning this line (starts with *)
    const trimmed = text.trim();
    if (trimmed.startsWith('*') || trimmed.startsWith('/*') || trimmed.startsWith('*/')) {
        return `<span class="c-comment">${escaped}</span>`;
    }

    // Check for line comments (// or #)
    const commentMatch = escaped.match(/(\/\/|#).*/);

    if (!commentMatch) {
        return escaped.replace(KEYWORD_PATTERN, '<span class="c-keyword">$1</span>');
    }

    const commentStart = commentMatch.index ?? escaped.length;
    const codePart = escaped
        .slice(0, commentStart)
        .replace(KEYWORD_PATTERN, '<span class="c-keyword">$1</span>');
    const commentPart = escaped.slice(commentStart);

    return `${codePart}<span class="c-comment">${commentPart}</span>`;
}

function syncScroll() {
    const top = editor.scrollTop;
    const left = editor.scrollLeft;

    lineNums.scrollTop = top;
    syntaxLayer.scrollTop = top;
    syntaxLayer.scrollLeft = left;
    errorLayer.scrollTop = top;
}

function rebuildEditor() {
    const lines = editor.value.split('\n');
    const gutterWidth = Math.max(36, String(lines.length).length * 10 + 14);

    document.documentElement.style.setProperty('--line-number-width', `${gutterWidth}px`);
    lineNums.innerHTML = lines.map((_, index) => `<div class="ln-row">${index + 1}</div>`).join('');
    syntaxLayer.innerHTML = lines
        .map((line) => `<div class="code-row">${highlightCode(line) || ' '}</div>`)
        .join('');

    syncScroll();
}

function setFixMode(showSplitPane) {
    editorView.style.display = showSplitPane ? 'none' : 'flex';
    splitView.style.display = showSplitPane ? 'flex' : 'none';
    fixActions.style.display = showSplitPane ? 'flex' : 'none';

    if (!showSplitPane) {
        splitOrig.value = '';
        splitFixed.value = '';
        fixSummary.textContent = '';
    }
}

function showGraphMessage(message) {
    graphContainer.innerHTML = `<p class="graph-message">${escapeHtml(message)}</p>`;
}

function buildErrorOverlays(errors, warnings, risks) {
    const lines = editor.value.split('\n');
    const lineClasses = {};

    const mark = (items, className) => {
        items.forEach((item) => {
            const lineNumber = item.line;
            if (lineNumber >= 1 && lineNumber <= lines.length) {
                if (!lineClasses[lineNumber] || className === 'hl-error') {
                    lineClasses[lineNumber] = className;
                }
            }
        });
    };

    mark(errors, 'hl-error');
    mark(risks, 'hl-risk');
    mark(warnings, 'hl-warning');

    errorLayer.innerHTML = lines
        .map((_, index) => {
            const lineNumber = index + 1;
            const className = lineClasses[lineNumber] || '';
            return `<div class="code-row ${className}" data-line="${lineNumber}"></div>`;
        })
        .join('');

    syncScroll();
}

function jumpToLine(lineNumber) {
    if (!lineNumber || lineNumber < 1) {
        return;
    }

    const firstRow = syntaxLayer.querySelector('.code-row');
    const rowHeight = firstRow ? firstRow.offsetHeight : 20;
    const targetScrollTop = (lineNumber - 1) * rowHeight - editor.clientHeight / 2;

    editor.scrollTop = Math.max(0, targetScrollTop);
    editor.focus();
    syncScroll();

    const rows = errorLayer.querySelectorAll(`.code-row[data-line="${lineNumber}"]`);
    rows.forEach((row) => {
        row.classList.add('hl-pulse');
        setTimeout(() => row.classList.remove('hl-pulse'), 1200);
    });
}

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
    latestAnalysisRequest += 1;
    currentAnalysis = null;
    currentFixes = null;
    btnFix.disabled = true;

    setFixMode(false);
    verdictBadge.className = 'badge';
    verdictBadge.textContent = 'PENDING';
    statRoles.textContent = '0';
    statPerms.textContent = '0';
    issueList.innerHTML = '<li class="empty-state">Run analysis to see results</li>';
    tokenTbody.innerHTML = '';
    astPre.textContent = '';
    symPre.textContent = '';
    errorLayer.innerHTML = '';
    countError.textContent = '0';
    countWarning.textContent = '0';
    countRisk.textContent = '0';
    showGraphMessage('Run analysis to visualise the role hierarchy.');
}

async function analyzePolicy() {
    const code = editor.value.trim();
    if (!code) {
        alert('Editor is empty. Please type or upload a policy.');
        return;
    }

    const requestId = ++latestAnalysisRequest;
    currentFixes = null;
    setFixMode(false);
    btnFix.disabled = true;
    verdictBadge.textContent = 'ANALYZING...';
    verdictBadge.className = 'badge';

    let data;
    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
        });

        if (!response.ok) {
            throw new Error(`Analyze request failed with status ${response.status}`);
        }

        data = await response.json();
    } catch (error) {
        if (requestId !== latestAnalysisRequest) {
            return;
        }

        alert('Could not reach the backend. Make sure app.py is running.');
        console.error(error);
        return;
    }

    if (requestId !== latestAnalysisRequest) {
        return;
    }

    currentAnalysis = data;

    try {
        renderAnalysis(data);
    } catch (error) {
        console.error('Failed to render analysis results.', error);
        alert('Analysis completed, but one or more panels could not be rendered. Check the browser console for details.');
    }
}

async function suggestFixes() {
    if (!currentAnalysis) {
        alert('Run analysis first before requesting fixes.');
        return;
    }

    try {
        const response = await fetch('/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: editor.value }),
        });

        if (!response.ok) {
            throw new Error(`Fix request failed with status ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
            currentFixes = data;
            showSplitView();
        } else {
            alert(`Fix failed: ${data.error || 'unknown error'}`);
        }
    } catch (error) {
        alert('Could not reach the backend.');
        console.error(error);
    }
}

function renderAnalysis(data) {
    const errors = data.errors || [];
    const warnings = data.warnings || [];
    const risks = data.risks || [];
    const summary = data.summary || {};
    const verdictClasses = {
        SAFE: 'badge-success',
        UNSAFE: 'badge-error',
        WARNINGS: 'badge-warning',
    };
    const verdictClass = verdictClasses[summary.verdict] || '';
    const hasIssues = errors.length || warnings.length || risks.length;

    statRoles.textContent = summary.roles ?? 0;
    statPerms.textContent = summary.permissions ?? 0;
    verdictBadge.textContent = summary.verdict || 'PENDING';
    verdictBadge.className = verdictClass ? `badge ${verdictClass}` : 'badge';
    btnFix.disabled = !data.success || !hasIssues;

    buildErrorOverlays(errors, warnings, risks);
    renderIssues();

    tokenTbody.innerHTML = (data.tokens || [])
        .map((token) => (
            `<tr><td>${token.line}</td><td>${escapeHtml(token.type)}</td><td>${escapeHtml(String(token.value))}</td></tr>`
        ))
        .join('');

    astPre.textContent = JSON.stringify(data.ast || {}, null, 2);
    symPre.textContent = JSON.stringify(data.symbol_table || {}, null, 2);

    if (data.graph && Array.isArray(data.graph.nodes) && data.graph.nodes.length > 0) {
        renderGraph(data.graph);
    } else {
        showGraphMessage('No roles to visualise.');
    }
}

function renderIssues() {
    if (!currentAnalysis) {
        return;
    }

    const errors = currentAnalysis.errors || [];
    const warnings = currentAnalysis.warnings || [];
    const risks = currentAnalysis.risks || [];

    countError.textContent = errors.length;
    countWarning.textContent = warnings.length;
    countRisk.textContent = risks.length;

    let html = '';
    const addItems = (items, className, label, show) => {
        if (!show) {
            return;
        }

        items.forEach((item) => {
            html += `<li onclick="jumpToLine(${item.line})">
                <div class="issue-badge ${className}">${label}</div>
                <div class="issue-msg">${escapeHtml(item.message)}</div>
                <div class="issue-line">Line ${item.line}</div>
            </li>`;
        });
    };

    addItems(errors, 'error', 'ERROR', filterError.checked);
    addItems(risks, 'risk', 'RISK', filterRisk.checked);
    addItems(warnings, 'warning', 'WARN', filterWarning.checked);

    const totalIssues = errors.length + risks.length + warnings.length;
    const emptyMsg = totalIssues === 0
        ? '<li class="empty-state">No issues found — policy looks solid!</li>'
        : '<li class="empty-state">No issues match the current filters.</li>';

    issueList.innerHTML = html || emptyMsg;
}

function showSplitView() {
    if (!currentFixes) {
        return;
    }

    setFixMode(true);
    splitOrig.value = editor.value;
    splitFixed.value = currentFixes.fixed_code || editor.value;

    const log = currentFixes.changelog || [];
    const safeCount = log.filter((entry) => entry.severity === 'SAFE').length;
    const heuristicCount = log.filter((entry) => entry.severity === 'HEURISTIC').length;
    const destructiveCount = log.filter((entry) => entry.severity === 'DESTRUCTIVE').length;

    fixSummary.textContent = log.length
        ? `Fix Summary: ${safeCount} safe | ${heuristicCount} heuristic | ${destructiveCount} destructive`
        : 'No automatic changes were suggested.';
}

function cancelFix() {
    currentFixes = null;
    setFixMode(false);
}

function applyFix() {
    editor.value = splitFixed.value;
    rebuildEditor();
    cancelFix();
    analyzePolicy();
}

function switchTab(tabId, button) {
    document.querySelectorAll('.tab-btn').forEach((tabButton) => tabButton.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach((tabContent) => {
        // Use class toggling only — never set inline display style so CSS rules aren't overridden
        tabContent.classList.remove('active');
    });

    if (button) {
        button.classList.add('active');
    }

    const tab = document.getElementById(tabId);
    tab.classList.add('active');

    if (
        tabId === 'tab-graph' &&
        currentAnalysis &&
        currentAnalysis.graph &&
        Array.isArray(currentAnalysis.graph.nodes) &&
        currentAnalysis.graph.nodes.length > 0
    ) {
        renderGraph(currentAnalysis.graph);
    }
}

function downloadReport() {
    if (!currentAnalysis) {
        alert('Analyze first.');
        return;
    }

    const summary = currentAnalysis.summary || {};
    const errors = currentAnalysis.errors || [];
    const risks = currentAnalysis.risks || [];
    const warnings = currentAnalysis.warnings || [];
    let text = 'RBAC Policy Verification Report\n================================\n\n';

    if (errors.length) {
        text += `ERRORS:\n${errors.map((entry) => `  [Line ${entry.line}] ${entry.message}`).join('\n')}\n\n`;
    }
    if (risks.length) {
        text += `RISKS:\n${risks.map((entry) => `  [Line ${entry.line}] ${entry.message}`).join('\n')}\n\n`;
    }
    if (warnings.length) {
        text += `WARNINGS:\n${warnings.map((entry) => `  [Line ${entry.line}] ${entry.message}`).join('\n')}\n\n`;
    }

    text += `Verdict: ${summary.verdict}\nRoles: ${summary.roles} | Permissions: ${summary.permissions}\n`;

    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = Object.assign(document.createElement('a'), {
        href: url,
        download: 'rbac_report.txt',
    });

    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
}

function renderGraph(graphData) {
    if (typeof d3 === 'undefined') {
        showGraphMessage('Hierarchy graph unavailable because D3 failed to load. Other analysis results are still available.');
        return;
    }

    const nodes = (graphData.nodes || []).map((node) => ({ ...node }));
    if (nodes.length === 0) {
        showGraphMessage('No roles to visualise.');
        return;
    }

    const nodeIds = new Set(nodes.map((node) => node.id));
    const links = (graphData.edges || [])
        .filter((edge) => nodeIds.has(edge.from) && nodeIds.has(edge.to))
        .map((edge) => ({ source: edge.from, target: edge.to, type: edge.type }));

    graphContainer.innerHTML = '';

    const width = graphContainer.clientWidth || 600;
    const height = graphContainer.clientHeight || 380;
    const nodeRadius = 14;
    const graphPadding = 24;
    const labelGap = 18;
    const approxLabelCharWidth = 7;
    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
    const estimateLabelWidth = (entry) => Math.max(40, String(entry.id || '').length * approxLabelCharWidth);
    const constrainNode = (entry) => {
        entry.x = clamp(entry.x ?? width / 2, nodeRadius + graphPadding, width - nodeRadius - graphPadding);
        entry.y = clamp(entry.y ?? height / 2, nodeRadius + graphPadding, height - nodeRadius - graphPadding);
    };
    const getLabelPlacement = (entry) => {
        const labelWidth = estimateLabelWidth(entry);
        const rightX = entry.x + labelGap;
        const leftX = entry.x - labelGap;

        if (rightX + labelWidth <= width - graphPadding) {
            return { x: rightX, anchor: 'start' };
        }

        if (leftX - labelWidth >= graphPadding) {
            return { x: leftX, anchor: 'end' };
        }

        return {
            x: clamp(entry.x, graphPadding + labelWidth / 2, width - graphPadding - labelWidth / 2),
            anchor: 'middle',
        };
    };

    const svg = d3.select('#d3-graph')
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`);

    svg.append('defs')
        .selectAll('marker')
        .data(['inherits', 'conflict'])
        .join('marker')
        .attr('id', (type) => `arr-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 7)
        .attr('markerHeight', 7)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', (type) => (type === 'conflict' ? '#dc3545' : '#888'))
        .attr('d', 'M0,-5L10,0L0,5');

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id((node) => node.id).distance(120))
        .force('charge', d3.forceManyBody().strength(-350))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide().radius(nodeRadius + 24))
        .force('x', d3.forceX(width / 2).strength(0.06))
        .force('y', d3.forceY(height / 2).strength(0.06));

    const link = svg.append('g')
        .selectAll('line')
        .data(links)
        .join('line')
        .attr('stroke', (edge) => (edge.type === 'conflict' ? '#dc3545' : '#888'))
        .attr('stroke-width', 2)
        .attr('stroke-dasharray', (edge) => (edge.type === 'conflict' ? '6 3' : 'none'))
        .attr('marker-end', (edge) => `url(#arr-${edge.type})`);

    const node = svg.append('g')
        .selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('r', nodeRadius)
        .attr('fill', (entry) => (
            entry.color === 'cyclic'
                ? '#dc3545'
                : entry.color === 'high_priv'
                    ? '#fd7e14'
                    : '#0d6efd'
        ))
        .attr('stroke', '#fff')
        .attr('stroke-width', 2)
        .call(
            d3.drag()
                .on('start', (event, entry) => {
                    if (!event.active) {
                        simulation.alphaTarget(0.3).restart();
                    }
                    entry.fx = entry.x;
                    entry.fy = entry.y;
                })
                .on('drag', (event, entry) => {
                    entry.fx = clamp(event.x, nodeRadius + graphPadding, width - nodeRadius - graphPadding);
                    entry.fy = clamp(event.y, nodeRadius + graphPadding, height - nodeRadius - graphPadding);
                })
                .on('end', (event, entry) => {
                    if (!event.active) {
                        simulation.alphaTarget(0);
                    }
                    entry.fx = null;
                    entry.fy = null;
                })
        );

    const label = svg.append('g')
        .selectAll('text')
        .data(nodes)
        .join('text')
        .text((entry) => entry.id)
        .attr('font-size', 12)
        .attr('dx', 18)
        .attr('dy', 4)
        .attr('fill', '#333')
        .attr('font-family', 'sans-serif');

    simulation.on('tick', () => {
        nodes.forEach(constrainNode);

        link
            .attr('x1', (edge) => edge.source.x)
            .attr('y1', (edge) => edge.source.y)
            .attr('x2', (edge) => edge.target.x)
            .attr('y2', (edge) => edge.target.y);

        node
            .attr('cx', (entry) => entry.x)
            .attr('cy', (entry) => entry.y);

        label
            .attr('x', (entry) => getLabelPlacement(entry).x)
            .attr('y', (entry) => clamp(entry.y + 4, graphPadding + 12, height - graphPadding))
            .attr('text-anchor', (entry) => getLabelPlacement(entry).anchor);
    });
}

editor.addEventListener('input', () => {
    rebuildEditor();

    if (currentAnalysis) {
        errorLayer.innerHTML = '';
        verdictBadge.textContent = 'ANALYZING...';
        verdictBadge.className = 'badge';
        btnFix.disabled = true;
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
editor.addEventListener('keydown', (event) => {
    if (event.key === 'Tab') {
        event.preventDefault();
        const start = editor.selectionStart;
        const end = editor.selectionEnd;

        editor.value = `${editor.value.substring(0, start)}    ${editor.value.substring(end)}`;
        editor.selectionStart = start + 4;
        editor.selectionEnd = start + 4;
        editor.dispatchEvent(new Event('input'));
    }
});

document.getElementById('file-upload').addEventListener('change', function (event) {
    const file = event.target.files[0];
    if (!file) {
        return;
    }

    const reader = new FileReader();
    reader.onload = (loadEvent) => {
        editor.value = loadEvent.target.result;
        rebuildEditor();
        resetAnalysis();

        if (editor.value.trim() !== '') {
            analyzePolicy();
        }

        this.value = '';
    };

    reader.readAsText(file);
});

filterError.addEventListener('change', renderIssues);
filterWarning.addEventListener('change', renderIssues);
filterRisk.addEventListener('change', renderIssues);

window.addEventListener('resize', () => {
    if (
        document.getElementById('tab-graph').classList.contains('active') &&
        currentAnalysis &&
        currentAnalysis.graph &&
        Array.isArray(currentAnalysis.graph.nodes) &&
        currentAnalysis.graph.nodes.length > 0
    ) {
        renderGraph(currentAnalysis.graph);
    }
});

rebuildEditor();
resetAnalysis();

function showRolesDetails() {
    const list = document.getElementById('roles-details-list');
    list.innerHTML = '';
    
    if (!currentAnalysis || !currentAnalysis.symbol_table) {
        list.innerHTML = '<li class="empty-state">No roles to display. Load or analyze a policy first.</li>';
    } else {
        const ObjectKeys = Object.keys(currentAnalysis.symbol_table);
        
        if (ObjectKeys.length === 0) {
            list.innerHTML = '<li class="empty-state">No roles defined in the current policy.</li>';
        } else {
            ObjectKeys.forEach(roleName => {
                const roleData = currentAnalysis.symbol_table[roleName];
                const perms = roleData.permissions || [];
                const inherits = roleData.inherits ? ` (inherits <span style="color:#666;">${escapeHtml(roleData.inherits)}</span>)` : '';
                
                list.innerHTML += `
                    <li>
                        <div class="role-name">${escapeHtml(roleName)}${inherits}</div>
                        <div class="role-perms"><strong>Permissions:</strong> ${perms.length > 0 ? escapeHtml(perms.join(', ')) : '<span style="color:#888;">None explicitly defined</span>'}</div>
                    </li>
                `;
            });
        }
    }
    
    document.getElementById('roles-modal').classList.add('active');
}

function closeRolesModal() {
    document.getElementById('roles-modal').classList.remove('active');
}

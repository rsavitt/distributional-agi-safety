/**
 * SWARM Agent Dashboard - Frontend Application
 *
 * Renders agent interaction networks as SVG flow diagrams
 * with timeline charts and detail panels.
 */

class SwarmDashboard {
  constructor() {
    this.sessions = [];
    this.activeSession = null;
    this.activeAgent = null;

    // Agent type → color mapping
    this.agentColors = {
      honest:             '#3fb950',
      opportunistic:      '#d29922',
      deceptive:          '#bc8cff',
      adversarial:        '#f85149',
      adaptive_adversary: '#ff7b72',
      diligent:           '#39d353',
      spam_bot:           '#f0883e',
      collusive:          '#db61a2',
      vandal:             '#f85149',
      llm:                '#58a6ff',
      unknown:            '#8b949e',
    };

    this.init();
  }

  async init() {
    this.bindUI();
    await this.loadSessions();
  }

  bindUI() {
    document.getElementById('panel-close').addEventListener('click', () => {
      this.closePanel();
    });
  }

  // ── Session loading ──────────────────────────────────────

  async loadSessions() {
    const listEl = document.getElementById('sessions-list');
    try {
      const resp = await fetch('/api/sessions');
      const data = await resp.json();
      this.sessions = data.sessions || [];

      if (this.sessions.length === 0) {
        listEl.innerHTML = '<div class="loading">No sessions found.<br>Run a simulation first.</div>';
        return;
      }

      listEl.innerHTML = '';
      for (const s of this.sessions) {
        const card = document.createElement('div');
        card.className = 'session-card';
        card.dataset.path = s.path;
        card.innerHTML = `
          <div class="session-name">${this.escHtml(s.session_id)}</div>
          <div class="session-meta">
            ${s.n_agents || '?'} agents &middot; ${s.n_epochs || '?'} epochs
            ${s.seed != null ? ' &middot; seed ' + s.seed : ''}
          </div>
        `;
        card.addEventListener('click', () => this.selectSession(s, card));
        listEl.appendChild(card);
      }
    } catch (err) {
      listEl.innerHTML = `<div class="loading">Error loading sessions.</div>`;
      console.error('Failed to load sessions:', err);
    }
  }

  async selectSession(meta, cardEl) {
    // Highlight active card
    document.querySelectorAll('.session-card').forEach(c => c.classList.remove('active'));
    cardEl.classList.add('active');

    // Fetch full session data
    const encoded = encodeURIComponent(meta.path);
    try {
      const resp = await fetch(`/api/sessions/${encoded}`);
      this.activeSession = await resp.json();
    } catch (err) {
      console.error('Failed to load session:', err);
      return;
    }

    // Update topbar
    document.getElementById('topbar-title').textContent = this.activeSession.session_id || 'Session';
    const metaStr = [
      this.activeSession.n_agents ? `${this.activeSession.n_agents} agents` : '',
      this.activeSession.n_epochs ? `${this.activeSession.n_epochs} epochs` : '',
      this.activeSession.seed != null ? `seed ${this.activeSession.seed}` : '',
    ].filter(Boolean).join(' · ');
    document.getElementById('topbar-meta').textContent = metaStr;

    // Render
    this.closePanel();
    this.renderFlow();
    this.renderTimeline();
  }

  // ── SVG Flow Visualization ───────────────────────────────

  renderFlow() {
    const session = this.activeSession;
    if (!session || !session.agents) return;

    const emptyState = document.getElementById('empty-state');
    const svg = document.getElementById('flow-svg');
    emptyState.style.display = 'none';
    svg.classList.add('visible');

    const agents = session.agents;
    const edges = session.edges || [];
    const agentList = Object.values(agents);

    if (agentList.length === 0) {
      emptyState.style.display = 'block';
      emptyState.textContent = 'No agents found in this session.';
      svg.classList.remove('visible');
      return;
    }

    // Layout parameters
    const nodeRadius = 28;
    const hSpacing = 160;
    const vSpacing = 100;
    const padding = 60;

    // Group agents by type for layout
    const typeGroups = {};
    for (const agent of agentList) {
      const t = agent.type || 'unknown';
      if (!typeGroups[t]) typeGroups[t] = [];
      typeGroups[t].push(agent);
    }

    const typeOrder = [
      'honest', 'diligent', 'llm', 'unknown',
      'opportunistic', 'deceptive', 'collusive',
      'adversarial', 'adaptive_adversary', 'spam_bot', 'vandal',
    ];
    const sortedTypes = typeOrder.filter(t => typeGroups[t]);

    // Position nodes in columns by type
    const positions = {};
    let col = 0;
    for (const t of sortedTypes) {
      const group = typeGroups[t];
      for (let row = 0; row < group.length; row++) {
        const agent = group[row];
        const aid = agent.agent_id;
        positions[aid] = {
          x: padding + col * hSpacing + hSpacing / 2,
          y: padding + row * vSpacing + vSpacing / 2,
        };
      }
      col++;
    }

    // Compute SVG dimensions
    const maxX = Math.max(...Object.values(positions).map(p => p.x)) + padding + nodeRadius;
    const maxY = Math.max(...Object.values(positions).map(p => p.y)) + padding + nodeRadius;
    const width = Math.max(maxX + padding, 600);
    const height = Math.max(maxY + padding, 400);

    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.innerHTML = '';

    // Define arrowhead marker
    const defs = this.svgEl('defs');
    const marker = this.svgEl('marker', {
      id: 'arrowhead', markerWidth: 8, markerHeight: 6,
      refX: 8, refY: 3, orient: 'auto', markerUnits: 'strokeWidth',
    });
    marker.appendChild(this.svgEl('polygon', {
      points: '0 0, 8 3, 0 6',
      class: 'edge-arrow',
    }));
    defs.appendChild(marker);
    svg.appendChild(defs);

    // Draw edges
    const edgeGroup = this.svgEl('g', { class: 'edges-group' });
    for (const edge of edges) {
      const srcPos = positions[edge.source];
      const tgtPos = positions[edge.target];
      if (!srcPos || !tgtPos) continue;

      const dx = tgtPos.x - srcPos.x;
      const dy = tgtPos.y - srcPos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist === 0) continue;

      // Offset start/end by node radius
      const ux = dx / dist;
      const uy = dy / dist;
      const sx = srcPos.x + ux * (nodeRadius + 2);
      const sy = srcPos.y + uy * (nodeRadius + 2);
      const ex = tgtPos.x - ux * (nodeRadius + 6);
      const ey = tgtPos.y - uy * (nodeRadius + 6);

      // Cubic bezier for curved edges
      const cx1 = sx + dx * 0.3 + dy * 0.15;
      const cy1 = sy + dy * 0.3 - dx * 0.15;
      const cx2 = ex - dx * 0.3 + dy * 0.15;
      const cy2 = ey - dy * 0.3 - dx * 0.15;

      const avgP = edge.avg_p != null ? edge.avg_p : 0.5;
      const strokeColor = this.pToColor(avgP);

      const path = this.svgEl('path', {
        d: `M ${sx} ${sy} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${ex} ${ey}`,
        class: 'edge-path',
        stroke: strokeColor,
        'marker-end': 'url(#arrowhead)',
        'data-source': edge.source,
        'data-target': edge.target,
      });
      edgeGroup.appendChild(path);

      // Edge label with count
      if (edge.count > 1) {
        const mx = (sx + ex) / 2;
        const my = (sy + ey) / 2 - 8;
        const label = this.svgEl('text', {
          x: mx, y: my, class: 'edge-label',
          'data-source': edge.source, 'data-target': edge.target,
        });
        label.textContent = `${edge.count}`;
        edgeGroup.appendChild(label);
      }
    }
    svg.appendChild(edgeGroup);

    // Draw nodes
    const nodeGroup = this.svgEl('g', { class: 'nodes-group' });
    for (const agent of agentList) {
      const aid = agent.agent_id;
      const pos = positions[aid];
      if (!pos) continue;

      const color = this.agentColors[agent.type] || this.agentColors.unknown;
      const g = this.svgEl('g', { class: 'node-group', 'data-agent': aid });

      // Circle
      const circle = this.svgEl('circle', {
        cx: pos.x, cy: pos.y, r: nodeRadius,
        fill: color + '22', stroke: color, 'stroke-width': 2,
        class: 'node-circle',
      });
      g.appendChild(circle);

      // Label (short name)
      const displayName = this.shortName(agent.name || aid);
      const label = this.svgEl('text', {
        x: pos.x, y: pos.y + 1, class: 'node-label',
      });
      label.textContent = displayName;
      g.appendChild(label);

      // Sub-label (type)
      const sublabel = this.svgEl('text', {
        x: pos.x, y: pos.y + nodeRadius + 14, class: 'node-sublabel',
      });
      sublabel.textContent = agent.type || '';
      g.appendChild(sublabel);

      // Hover/click events
      g.addEventListener('mouseenter', () => this.highlightAgent(aid));
      g.addEventListener('mouseleave', () => this.clearHighlight());
      g.addEventListener('click', () => this.openAgentPanel(aid));

      nodeGroup.appendChild(g);
    }
    svg.appendChild(nodeGroup);
  }

  highlightAgent(agentId) {
    // Dim all, highlight connected
    const svg = document.getElementById('flow-svg');

    svg.querySelectorAll('.node-group').forEach(g => {
      g.classList.toggle('dimmed', g.dataset.agent !== agentId);
      g.classList.toggle('highlighted', g.dataset.agent === agentId);
    });

    svg.querySelectorAll('.edge-path').forEach(p => {
      const isConnected = p.dataset.source === agentId || p.dataset.target === agentId;
      p.classList.toggle('dimmed', !isConnected);
      p.classList.toggle('highlighted', isConnected);

      // Undim connected nodes
      if (isConnected) {
        const otherId = p.dataset.source === agentId ? p.dataset.target : p.dataset.source;
        const otherNode = svg.querySelector(`.node-group[data-agent="${otherId}"]`);
        if (otherNode) {
          otherNode.classList.remove('dimmed');
        }
      }
    });

    svg.querySelectorAll('.edge-label').forEach(l => {
      const isConnected = l.dataset.source === agentId || l.dataset.target === agentId;
      l.classList.toggle('dimmed', !isConnected);
    });
  }

  clearHighlight() {
    const svg = document.getElementById('flow-svg');
    svg.querySelectorAll('.dimmed').forEach(el => el.classList.remove('dimmed'));
    svg.querySelectorAll('.highlighted').forEach(el => el.classList.remove('highlighted'));
  }

  // ── Timeline Chart ───────────────────────────────────────

  renderTimeline() {
    const session = this.activeSession;
    if (!session || !session.epochs || session.epochs.length === 0) {
      document.getElementById('timeline-container').classList.remove('visible');
      return;
    }

    const container = document.getElementById('timeline-container');
    const svg = document.getElementById('timeline-svg');
    container.classList.add('visible');

    const epochs = session.epochs;
    const rect = container.getBoundingClientRect();
    const width = Math.max(rect.width || 800, 400);
    const height = 180;
    const margin = { top: 24, right: 20, bottom: 30, left: 50 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;

    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.innerHTML = '';

    // Metrics to plot
    const series = [
      { key: 'toxicity_rate', label: 'Toxicity', color: '#f85149' },
      { key: 'avg_p', label: 'Avg p', color: '#58a6ff' },
      { key: 'quality_gap', label: 'Quality Gap', color: '#d29922' },
    ];

    // Compute scales
    const xMin = Math.min(...epochs.map(e => e.epoch));
    const xMax = Math.max(...epochs.map(e => e.epoch));
    const xRange = xMax - xMin || 1;

    // Y range: find min/max across all series
    let yMin = 0, yMax = 1;
    for (const s of series) {
      for (const ep of epochs) {
        const v = ep[s.key];
        if (v != null) {
          if (v < yMin) yMin = v;
          if (v > yMax) yMax = v;
        }
      }
    }
    const yPad = (yMax - yMin) * 0.1 || 0.1;
    yMin -= yPad;
    yMax += yPad;
    const yRange = yMax - yMin || 1;

    const xScale = (v) => margin.left + ((v - xMin) / xRange) * plotW;
    const yScale = (v) => margin.top + plotH - ((v - yMin) / yRange) * plotH;

    // Grid lines
    const gridGroup = this.svgEl('g', { class: 'timeline-grid' });
    for (let i = 0; i <= 4; i++) {
      const yVal = yMin + (yRange * i) / 4;
      const y = yScale(yVal);
      gridGroup.appendChild(this.svgEl('line', {
        x1: margin.left, x2: width - margin.right, y1: y, y2: y,
      }));
    }
    svg.appendChild(gridGroup);

    // Axes
    const axisGroup = this.svgEl('g', { class: 'timeline-axis' });

    // X axis
    axisGroup.appendChild(this.svgEl('line', {
      x1: margin.left, x2: width - margin.right,
      y1: height - margin.bottom, y2: height - margin.bottom,
    }));
    // X labels (every N epochs)
    const xStep = Math.max(1, Math.ceil(epochs.length / 10));
    for (let i = 0; i < epochs.length; i += xStep) {
      const ep = epochs[i];
      const x = xScale(ep.epoch);
      const label = this.svgEl('text', {
        x, y: height - margin.bottom + 14, 'text-anchor': 'middle',
      });
      label.textContent = ep.epoch;
      axisGroup.appendChild(label);
    }

    // Y axis
    axisGroup.appendChild(this.svgEl('line', {
      x1: margin.left, x2: margin.left,
      y1: margin.top, y2: height - margin.bottom,
    }));
    for (let i = 0; i <= 4; i++) {
      const yVal = yMin + (yRange * i) / 4;
      const y = yScale(yVal);
      const label = this.svgEl('text', {
        x: margin.left - 6, y: y + 3, 'text-anchor': 'end',
      });
      label.textContent = yVal.toFixed(2);
      axisGroup.appendChild(label);
    }
    svg.appendChild(axisGroup);

    // Plot lines
    for (const s of series) {
      const points = epochs
        .filter(e => e[s.key] != null)
        .map(e => `${xScale(e.epoch)},${yScale(e[s.key])}`);

      if (points.length < 2) continue;

      const line = this.svgEl('polyline', {
        points: points.join(' '),
        class: 'timeline-line',
        stroke: s.color,
      });
      svg.appendChild(line);
    }

    // Legend
    const legendGroup = this.svgEl('g', { class: 'timeline-legend' });
    let lx = margin.left + 8;
    for (const s of series) {
      const rect2 = this.svgEl('rect', {
        x: lx, y: 6, width: 12, height: 3, rx: 1, fill: s.color,
      });
      legendGroup.appendChild(rect2);
      const label = this.svgEl('text', { x: lx + 16, y: 12 });
      label.textContent = s.label;
      legendGroup.appendChild(label);
      lx += 16 + s.label.length * 6.5 + 14;
    }
    svg.appendChild(legendGroup);
  }

  // ── Agent Detail Panel ───────────────────────────────────

  openAgentPanel(agentId) {
    const session = this.activeSession;
    if (!session) return;

    const agent = session.agents[agentId];
    if (!agent) return;

    this.activeAgent = agentId;
    const panel = document.getElementById('detail-panel');
    const title = document.getElementById('panel-title');
    const body = document.getElementById('panel-body');

    title.textContent = agent.name || agentId;
    panel.classList.add('open');

    const color = this.agentColors[agent.type] || this.agentColors.unknown;
    const badgeClass = `badge-${agent.type || 'unknown'}`;

    let html = '';

    // Identity section
    html += `<div class="panel-section">
      <div class="panel-section-header expanded" onclick="dashboard.toggleSection(this)">
        Identity <span class="chevron">&#9654;</span>
      </div>
      <div class="panel-section-body expanded">
        <div class="kv-row"><span class="kv-key">ID</span><span class="kv-val">${this.escHtml(agentId)}</span></div>
        <div class="kv-row"><span class="kv-key">Name</span><span class="kv-val">${this.escHtml(agent.name || agentId)}</span></div>
        <div class="kv-row"><span class="kv-key">Type</span><span class="badge ${badgeClass}">${this.escHtml(agent.type || 'unknown')}</span></div>
      </div>
    </div>`;

    // Connections section
    const edges = (session.edges || []).filter(
      e => e.source === agentId || e.target === agentId
    );
    if (edges.length > 0) {
      let connHtml = '';
      for (const e of edges) {
        const otherId = e.source === agentId ? e.target : e.source;
        const direction = e.source === agentId ? 'sent' : 'received';
        const otherAgent = session.agents[otherId];
        const otherName = otherAgent ? (otherAgent.name || otherId) : otherId;
        const otherColor = this.agentColors[(otherAgent || {}).type] || this.agentColors.unknown;
        const pClass = (e.avg_p || 0.5) >= 0.5 ? 'good' : 'bad';

        connHtml += `<div class="interaction-item">
          <span class="agent-dot" style="background:${otherColor}"></span>
          <span class="ix-parties">${this.escHtml(otherName)}</span>
          <span style="color:var(--text-muted)"> (${direction})</span>
          <div class="ix-meta">
            ${e.count} interaction${e.count !== 1 ? 's' : ''}
            ${e.avg_p != null ? ` · avg p = <span class="${pClass}">${e.avg_p.toFixed(3)}</span>` : ''}
            ${e.accepted != null ? ` · ${e.accepted} accepted` : ''}
          </div>
        </div>`;
      }

      html += `<div class="panel-section">
        <div class="panel-section-header expanded" onclick="dashboard.toggleSection(this)">
          Connections (${edges.length}) <span class="chevron">&#9654;</span>
        </div>
        <div class="panel-section-body expanded">${connHtml}</div>
      </div>`;
    }

    // Epoch trajectory section (if agent has epoch data)
    const epochData = agent.epochs;
    if (epochData && epochData.length > 0) {
      let trajHtml = '';
      const lastEp = epochData[epochData.length - 1];
      const firstEp = epochData[0];

      trajHtml += `<div class="kv-row"><span class="kv-key">Reputation</span>
        <span class="kv-val">${(lastEp.reputation || 0).toFixed(2)}</span></div>`;
      trajHtml += `<div class="kv-row"><span class="kv-key">Resources</span>
        <span class="kv-val">${(lastEp.resources || 0).toFixed(1)}</span></div>`;
      trajHtml += `<div class="kv-row"><span class="kv-key">Total Payoff</span>
        <span class="kv-val ${lastEp.total_payoff >= 0 ? 'good' : 'bad'}">${(lastEp.total_payoff || 0).toFixed(2)}</span></div>`;
      trajHtml += `<div class="kv-row"><span class="kv-key">Avg p (initiated)</span>
        <span class="kv-val ${(lastEp.avg_p_initiated || 0.5) >= 0.5 ? 'good' : 'bad'}">${(lastEp.avg_p_initiated || 0.5).toFixed(3)}</span></div>`;

      if (lastEp.is_frozen) {
        trajHtml += `<div class="kv-row"><span class="kv-key">Status</span>
          <span class="kv-val bad">FROZEN</span></div>`;
      } else if (lastEp.is_quarantined) {
        trajHtml += `<div class="kv-row"><span class="kv-key">Status</span>
          <span class="kv-val warn">QUARANTINED</span></div>`;
      }

      // Mini reputation trajectory
      if (epochData.length > 1) {
        trajHtml += '<div style="margin-top:8px">';
        trajHtml += '<div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">Reputation over epochs:</div>';
        const maxRep = Math.max(...epochData.map(e => Math.abs(e.reputation || 0)), 1);
        for (const ep of epochData) {
          const pct = Math.max(0, ((ep.reputation || 0) / maxRep) * 100);
          const barColor = (ep.reputation || 0) >= 0 ? 'var(--green)' : 'var(--red)';
          trajHtml += `<div class="epoch-bar">
            <span style="width:24px;color:var(--text-muted)">${ep.epoch}</span>
            <div class="epoch-bar-fill">
              <div class="fill" style="width:${pct}%;background:${barColor}"></div>
            </div>
            <span style="width:40px;text-align:right">${(ep.reputation || 0).toFixed(1)}</span>
          </div>`;
        }
        trajHtml += '</div>';
      }

      html += `<div class="panel-section">
        <div class="panel-section-header expanded" onclick="dashboard.toggleSection(this)">
          Trajectory <span class="chevron">&#9654;</span>
        </div>
        <div class="panel-section-body expanded">${trajHtml}</div>
      </div>`;
    }

    // Raw interactions section (for JSONL sessions)
    const interactions = (session.interactions || []).filter(
      ix => ix.initiator === agentId || ix.counterparty === agentId
    );
    if (interactions.length > 0) {
      const shown = interactions.slice(0, 20);
      let ixHtml = '';
      for (const ix of shown) {
        const role = ix.initiator === agentId ? 'initiator' : 'counterparty';
        const otherId = role === 'initiator' ? ix.counterparty : ix.initiator;
        const pClass = (ix.p || 0.5) >= 0.5 ? 'good' : 'bad';
        const acceptStr = ix.accepted === true ? 'accepted' : ix.accepted === false ? 'rejected' : 'pending';

        ixHtml += `<div class="interaction-item">
          <span class="ix-parties">${role} → ${this.escHtml(otherId)}</span>
          <div class="ix-meta">
            p = <span class="${pClass}">${(ix.p || 0.5).toFixed(3)}</span>
            · ${acceptStr}
            ${ix.epoch != null ? ` · epoch ${ix.epoch}` : ''}
          </div>
        </div>`;
      }
      if (interactions.length > 20) {
        ixHtml += `<div style="color:var(--text-muted);font-size:10px;padding:4px">
          ... and ${interactions.length - 20} more
        </div>`;
      }

      html += `<div class="panel-section">
        <div class="panel-section-header" onclick="dashboard.toggleSection(this)">
          Interactions (${interactions.length}) <span class="chevron">&#9654;</span>
        </div>
        <div class="panel-section-body">${ixHtml}</div>
      </div>`;
    }

    body.innerHTML = html;
  }

  closePanel() {
    document.getElementById('detail-panel').classList.remove('open');
    this.activeAgent = null;
  }

  toggleSection(headerEl) {
    headerEl.classList.toggle('expanded');
    const body = headerEl.nextElementSibling;
    body.classList.toggle('expanded');
  }

  // ── Helpers ──────────────────────────────────────────────

  svgEl(tag, attrs = {}) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attrs)) {
      el.setAttribute(k, v);
    }
    return el;
  }

  pToColor(p) {
    // Map p ∈ [0,1] to a red→yellow→green gradient
    if (p >= 0.7) return '#3fb950';
    if (p >= 0.5) return '#d29922';
    if (p >= 0.3) return '#f0883e';
    return '#f85149';
  }

  shortName(name) {
    if (!name) return '?';
    // Truncate to 10 chars
    if (name.length <= 10) return name;
    return name.substring(0, 9) + '…';
  }

  escHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
}

// Initialize
const dashboard = new SwarmDashboard();

  function toggleGlobalQuery() {
    const panel = document.getElementById("global-query-panel");
    panel.style.display = panel.style.display === "none" ? "flex" : "none";
    if (panel.style.display === "flex") {
      document.getElementById("global-query-input").focus();
    }
  }
  
  async function sendGlobalQuery() {
    const input = document.getElementById("global-query-input");
    const history = document.getElementById("global-query-history");
    const modelSelect = document.getElementById("global-query-model");
    const question = input.value.trim();
    const selectedModel = modelSelect.value;
    if (!question) return;
    
    input.value = "";
    
    const userMsg = document.createElement("div");
    userMsg.innerHTML = "<strong>You:</strong> " + question;
    history.appendChild(userMsg);
    history.scrollTop = history.scrollHeight;
    
    const sender = selectedModel === 'gemini' ? 'Gemini API' : (selectedModel === 'gemini-cli' ? 'Gemini CLI' : 'Ollama');
    
    const aiMsg = document.createElement("div");
    aiMsg.innerHTML = "<strong>" + sender + ":</strong> <span style='color:#888'>Searching wiki...</span>";
    history.appendChild(aiMsg);
    history.scrollTop = history.scrollHeight;
    
    try {
      const res = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question, model: selectedModel })
      });
      
      if (res.ok) {
        const data = await res.json();
        aiMsg.innerHTML = "<strong>" + sender + ":</strong> <div class='markdown-body' style='margin-top:8px;font-size:13px;line-height:1.5;'>" + renderMarkdown(data.response) + "</div>";
      } else {
        aiMsg.innerHTML = "<strong>Error:</strong> <span style='color:red'>Server failed.</span>";
      }
    } catch (err) {
      aiMsg.innerHTML = "<strong>Error:</strong> <span style='color:red'>Connection failed.</span>";
    }
    history.scrollTop = history.scrollHeight;
  }

  async function rebuildGraph() {
    const btn = document.getElementById("btn-rebuild");
    const toast = document.getElementById("rebuild-toast");
    const toastMsg = document.getElementById("rebuild-toast-msg");

    btn.disabled = true;
    btn.style.opacity = "0.6";
    btn.textContent = "⏳ Building...";

    toast.style.display = "block";
    toastMsg.style.color = "#aaa";
    toastMsg.textContent = "Running uv run main.py graph...";

    try {
      const res = await fetch("/rebuild", { method: "POST" });
      const data = await res.json();

      if (data.success) {
        toastMsg.style.color = "#a0e0a0";
        toastMsg.textContent = "✅ Graph rebuilt! Reloading in 2s...";
        setTimeout(() => location.reload(), 2000);
      } else {
        toastMsg.style.color = "#ff8888";
        toastMsg.innerHTML = "❌ Build failed:<br><pre style='font-size:11px;margin-top:6px;white-space:pre-wrap;'>" + (data.output || "Unknown error") + "</pre>";
        btn.disabled = false;
        btn.style.opacity = "1";
        btn.textContent = "🔄 Rebuild Graph";
        setTimeout(() => { toast.style.display = "none"; }, 8000);
      }
    } catch (err) {
      toastMsg.style.color = "#ff8888";
      toastMsg.textContent = "❌ Could not reach server. Is it running?";
      btn.disabled = false;
      btn.style.opacity = "1";
      btn.textContent = "🔄 Rebuild Graph";
      setTimeout(() => { toast.style.display = "none"; }, 4000);
    }
  }

const originalNodes = window.originalNodes || [];
const originalEdges = window.originalEdges || [];
const communities = window.communities || {};
const nodes = new vis.DataSet(originalNodes);
const edges = new vis.DataSet(originalEdges);
const adjacency = new Map();
const searchInput = document.getElementById("search");
const searchResults = document.getElementById("search-results");
const stats = document.getElementById("stats");
const controls = {
  extracted: document.getElementById("cb-extracted"),
  confSlider: document.getElementById("conf-slider"),
  confValue: document.getElementById("conf-val"),
};
const nodeMap = new Map(originalNodes.map(node => [node.id, node]));
let activeNodeId = null;
let currentPathIds = null;

let minDateMs = Infinity;
let maxDateMs = -Infinity;
let currentDateMs = Infinity;
const COMMUNITY_COLORS = [
  "#E91E63", "#00BCD4", "#8BC34A", "#FF5722", "#673AB7",
  "#FFC107", "#009688", "#F44336", "#3F51B5", "#CDDC39",
];

const hiddenClusters = new Set();
let activeClusterId = null;

function toggleClusterVisibility(clusterId) {
  if (hiddenClusters.has(clusterId)) {
    hiddenClusters.delete(clusterId);
  } else {
    hiddenClusters.add(clusterId);
  }
  applyFilters();
}

function selectCluster(id) {
  // Toggle selection
  if (activeClusterId === id) {
    activeClusterId = null;
  } else {
    activeClusterId = id;
    // Clear node selection to avoid confusion
    if (network) network.selectNodes([]);
    activeNodeId = null;
    closeDrawer();
  }
  populateClusterList();
}

function toggleAllClusters(visible) {
  const checkboxes = document.querySelectorAll("#cluster-list input[type='checkbox']");
  checkboxes.forEach(cb => {
    const id = parseInt(cb.dataset.id);
    cb.checked = visible;
    if (visible) {
      hiddenClusters.delete(id);
    } else {
      hiddenClusters.add(id);
    }
  });
  applyFilters();
}

function populateClusterList() {
  const list = document.getElementById("cluster-list");
  if (!list) return;
  
  const mathIds = new Set();
  originalNodes.forEach(n => { if (n.math_id !== undefined && n.math_id !== null) mathIds.add(n.math_id); });
  const entries = Array.from(mathIds).sort((a,b) => a-b).map(id => [id, id === -1 ? "Unassigned" : `Cluster ${id}`]);
  
  if (entries.length === 0) {
    list.innerHTML = '<div style="font-style:italic; opacity:0.6;">No clusters detected</div>';
    return;
  }
  
  list.innerHTML = entries.map(([id, name]) => {
    const color = COMMUNITY_COLORS[id % COMMUNITY_COLORS.length];
    const isChecked = !hiddenClusters.has(id);
    const isSelected = activeClusterId === id;
    
    return `<div style="margin-bottom:8px; padding:4px; border-radius:4px; background:${isSelected ? 'rgba(134,200,255,0.15)' : 'transparent'}; border:1px solid ${isSelected ? 'rgba(134,200,255,0.3)' : 'transparent'}">
      <div style="display:flex; align-items:center; gap:8px;">
        <input type="checkbox" data-id="${id}" ${isChecked ? 'checked' : ''} onchange="toggleClusterVisibility(${id})" style="width:12px; height:12px; cursor:pointer; flex-shrink:0;">
        <span style="width:10px; height:10px; background:${color}; border-radius:2px; display:inline-block; flex-shrink:0;"></span>
        <span onclick="selectCluster(${id})" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:500; font-size:12px; color:${isSelected ? '#fff' : '#eee'}; cursor:pointer; flex:1;" title="Click to chat about this cluster">${name}</span>
      </div>
    </div>`;
  }).join("");
}

populateClusterList();



originalNodes.forEach(n => {
  if (n.date) {
    const ms = new Date(n.date).getTime();
    if (!isNaN(ms)) {
      minDateMs = Math.min(minDateMs, ms);
      maxDateMs = Math.max(maxDateMs, ms);
      n.ms = ms;
    }
  }
});

const timelineGroup = document.getElementById("timeline-group");
const timeSlider = document.getElementById("time-slider");
const timeVal = document.getElementById("time-val");

if (minDateMs < Infinity && minDateMs < maxDateMs) {
  timelineGroup.style.display = "block";
  timeSlider.min = minDateMs;
  timeSlider.max = maxDateMs;
  timeSlider.value = maxDateMs;
  currentDateMs = maxDateMs;
  timeVal.textContent = new Date(maxDateMs).toISOString().split('T')[0];
}

function updateTimeline() {
  currentDateMs = parseInt(timeSlider.value, 10);
  timeVal.textContent = new Date(currentDateMs).toISOString().split('T')[0];
  applyFilters();
}

function hexToRgba(color, alpha) {
  if (!color) return `rgba(255, 255, 255, ${alpha})`;
  const normalized = color.replace("#", "");
  const value = normalized.length === 3
    ? normalized.split("").map(ch => ch + ch).join("")
    : normalized;
  const intValue = Number.parseInt(value, 16);
  const r = (intValue >> 16) & 255;
  const g = (intValue >> 8) & 255;
  const b = intValue & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function escapeHtml(text) {
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function stripFrontmatter(markdown) {
  return (markdown || "").replace(/^---\n[\s\S]*?\n---\n?/, "");
}

function renderInlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink" onclick="focusNodeByLabel(\'$1\')">$1</span>');
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

function renderMarkdown(markdown) {
  const lines = stripFrontmatter(markdown).split(/\r?\n/);
  const html = [];
  let paragraph = [];
  let listType = null;
  let listItems = [];
  let quoteLines = [];
  let inCodeBlock = false;
  let codeLines = [];

  function flushParagraph() {
    if (!paragraph.length) return;
    html.push(`<p>${renderInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!listType || !listItems.length) return;
    const items = listItems.map(item => `<li>${renderInlineMarkdown(item)}</li>`).join("");
    html.push(`<${listType}>${items}</${listType}>`);
    listType = null;
    listItems = [];
  }

  function flushQuote() {
    if (!quoteLines.length) return;
    html.push(`<blockquote>${quoteLines.map(line => renderInlineMarkdown(line)).join("<br>")}</blockquote>`);
    quoteLines = [];
  }

  function flushCode() {
    if (!codeLines.length) {
      html.push("<pre><code></code></pre>");
      return;
    }
    html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/\t/g, "    ");
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      flushParagraph();
      flushList();
      flushQuote();
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(rawLine);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      flushQuote();
      const level = headingMatch[1].length;
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
      flushParagraph();
      flushList();
      flushQuote();
      html.push("<hr>");
      continue;
    }

    const quoteMatch = trimmed.match(/^>\s?(.*)$/);
    if (quoteMatch) {
      flushParagraph();
      flushList();
      quoteLines.push(quoteMatch[1]);
      continue;
    }
    flushQuote();

    const unorderedMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (unorderedMatch) {
      flushParagraph();
      if (listType && listType !== "ul") flushList();
      listType = "ul";
      listItems.push(unorderedMatch[1]);
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType && listType !== "ol") flushList();
      listType = "ol";
      listItems.push(orderedMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  if (inCodeBlock) flushCode();
  flushParagraph();
  flushList();
  flushQuote();
  return html.join("");
}

function rebuildAdjacency(filteredEdges) {
  adjacency.clear();
  for (const node of originalNodes) {
    adjacency.set(node.id, new Set());
  }
  for (const edge of filteredEdges) {
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, new Set());
    if (!adjacency.has(edge.to)) adjacency.set(edge.to, new Set());
    adjacency.get(edge.from).add(edge.to);
    adjacency.get(edge.to).add(edge.from);
  }
}

function currentEdgeState() {
  const minConf = parseInt(controls.confSlider.value, 10) / 100;
  controls.confValue.textContent = minConf.toFixed(2);
  return {
    showExtracted: controls.extracted ? controls.extracted.checked : true,
    minConf,
  };
}

function passesEdgeFilters(edge, edgeState) {
  const typeOk = (edge.type === "EXTRACTED" && edgeState.showExtracted);
  const confOk = (edge.confidence ?? 1.0) >= edgeState.minConf;
  return typeOk && confOk;
}

function searchNodes(q) {
  applyFilters(q, activeNodeId);
}

function updateSearchResults(query, inputEl, resultsEl, isPath = false) {
  const lower = query.toLowerCase().trim();
  if (!lower) {
    resultsEl.style.display = "none";
    return;
  }
  
  const matches = originalNodes.filter(n => 
    n.label.toLowerCase().includes(lower)
  ).slice(0, 40);
  
  if (matches.length === 0) {
    resultsEl.style.display = "none";
    return;
  }
  
  resultsEl.innerHTML = matches.map(n => `
    <div class="search-item" onclick="selectSearchNode('${n.id}', '${n.label.replace(/'/g, "\\'")}', '${inputEl.id}', '${resultsEl.id}', ${isPath})">
      <span>${n.label}</span>
      <span class="type-tag" style="background: ${nodeMap.get(n.id).color}">${n.type}</span>
    </div>
  `).join("");
  resultsEl.style.display = "block";
}

function selectSearchNode(id, label, inputId, resultsId, isPath) {
  const inputEl = document.getElementById(inputId);
  const resultsEl = document.getElementById(resultsId);
  inputEl.value = label;
  resultsEl.style.display = "none";
  if (!isPath) {
    focusNode(id);
  }
}

searchInput.addEventListener("input", (e) => {
  updateSearchResults(e.target.value, searchInput, searchResults);
});

const pathStart = document.getElementById("path-start");
const pathStartResults = document.getElementById("path-start-results");
const pathEnd = document.getElementById("path-end");
const pathEndResults = document.getElementById("path-end-results");

pathStart.addEventListener("input", (e) => {
  updateSearchResults(e.target.value, pathStart, pathStartResults, true);
});

pathEnd.addEventListener("input", (e) => {
  updateSearchResults(e.target.value, pathEnd, pathEndResults, true);
});

// Close all search results when clicking outside
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-container")) {
    document.querySelectorAll(".search-results").forEach(el => {
      el.style.display = "none";
    });
  }
});

document.querySelectorAll(".type-filter").forEach(btn => {
  btn.onclick = () => {
    btn.classList.toggle("active");
    applyFilters();
  };
});

document.getElementById("btn-find-path").onclick = () => {
  const startLabel = document.getElementById("path-start").value.trim();
  const endLabel = document.getElementById("path-end").value.trim();
  const startNode = originalNodes.find(n => n.label === startLabel);
  const endNode = originalNodes.find(n => n.label === endLabel);
  const resultDiv = document.getElementById("path-result");
  
  if (!startNode || !endNode) {
    resultDiv.textContent = "Please select valid start and end nodes.";
    resultDiv.style.display = "block";
    return;
  }
  
  const queue = [[startNode.id]];
  const visited = new Set([startNode.id]);
  let foundPath = null;
  
  while (queue.length > 0) {
    const path = queue.shift();
    const node = path[path.length - 1];
    if (node === endNode.id) {
      foundPath = path;
      break;
    }
    const neighbors = adjacency.get(node) || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push([...path, neighbor]);
      }
    }
  }
  
  if (foundPath) {
    currentPathIds = foundPath;
    resultDiv.textContent = `Found path with ${foundPath.length - 1} jumps.`;
    resultDiv.style.display = "block";
    activeNodeId = null;
    closeDrawer();
    applyFilters();
  } else {
    currentPathIds = null;
    resultDiv.textContent = "No path found between these nodes.";
    resultDiv.style.display = "block";
    applyFilters();
  }
};

document.getElementById("btn-clear-path").onclick = () => {
  document.getElementById("path-start").value = "";
  document.getElementById("path-end").value = "";
  document.getElementById("path-result").style.display = "none";
  currentPathIds = null;
  applyFilters();
};

document.getElementById("drawer-close").onclick = clearSelection;

function clearSelection() {
  activeNodeId = null;
  closeDrawer();
  applyFilters(searchInput.value, null);
}

function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
}

function openDrawer(node, relatedIds) {
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-title").textContent = node.label;
  const theme = (window.communityNames && node.group in window.communityNames) ? window.communityNames[node.group] : "Unclassified";
  const math = node.math_id !== undefined ? `Cluster ${node.math_id}` : "N/A";
  
  document.getElementById("drawer-meta").innerHTML = `
    <div style="display:flex; flex-direction:column; gap:4px; margin-top:8px;">
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="padding:2px 6px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); border-radius:4px; font-size:11px; color:#888;">${node.type}</span>
        <span style="font-weight:600; color:#86c8ff;">${theme}</span>
      </div>
      <div style="font-size:11px; color:#666;">Math Origin: ${math}</div>
    </div>
  `;
  document.getElementById("drawer-path").textContent = node.path;
  document.getElementById("drawer-preview").innerHTML = renderInlineMarkdown(node.preview || "");
  document.getElementById("drawer-markdown").innerHTML = renderMarkdown(node.markdown || "");

  const relatedList = document.getElementById("drawer-related-list");
  relatedList.innerHTML = "";
  const relatedNodes = originalNodes
    .filter(item => relatedIds.has(item.id) && item.id !== node.id)
    .sort((a, b) => a.label.localeCompare(b.label));

  if (relatedNodes.length === 0) {
    const empty = document.createElement("span");
    empty.textContent = "No directly connected nodes";
    relatedList.appendChild(empty);
  } else {
    for (const related of relatedNodes) {
      const chip = document.createElement("button");
      chip.className = "related-chip";
      chip.textContent = related.label;
      chip.onclick = () => focusNode(related.id);
      relatedList.appendChild(chip);
    }
  }
  
  document.getElementById("chat-history").innerHTML = "";
  document.getElementById("chat-input").value = "";
}

async function sendChat() {
  const input = document.getElementById("chat-input");
  const history = document.getElementById("chat-history");
  const modelSelect = document.getElementById("chat-model");
  const question = input.value.trim();
  const selectedModel = modelSelect.value;
  if (!question) return;
  
  let fullContext = "";
  if (activeNodeId) {
    const node = nodeMap.get(activeNodeId);
    if (!node) return;
    const clusterId = node.math_id;
    const neighbors = originalNodes
      .filter(n => n.math_id === clusterId && n.id !== node.id)
      .map(n => n.label);
      
    fullContext = `Current Context: Selected Node [[${node.label}]]\n`;
    fullContext += `This node is mathematically grouped in Cluster ${clusterId}.\n`;
    if (neighbors.length > 0) {
      fullContext += `Other nodes in this same cluster (mathematical neighbors): ${neighbors.join(", ")}.\n`;
    }
    fullContext += `\nContent of [[${node.label}]]:\n${node.markdown || "No content available."}`;
  } else if (activeClusterId !== null) {
    const clusterNodes = originalNodes.filter(n => n.math_id === activeClusterId);
    const labels = clusterNodes.map(n => n.label);
    fullContext = `Current Context: Selected Cluster ${activeClusterId}\n`;
    fullContext += `This cluster contains ${labels.length} notes: ${labels.join(", ")}\n`;
    fullContext += `\nPlease summarize the themes and connections within this specific group of notes.`;
  } else {
    fullContext = "Global Context: No specific node or cluster selected. Here is the current clustering structure:\n\n";
    const clusters = {};
    originalNodes.forEach(n => {
      const cid = n.math_id !== undefined ? n.math_id : -1;
      if (!clusters[cid]) clusters[cid] = [];
      if (clusters[cid].length < 50) clusters[cid].push(n.label);
    });
    
    Object.entries(clusters).forEach(([cid, labels]) => {
      const cidName = cid === "-1" ? "Unassigned" : `Cluster ${cid}`;
      fullContext += `- ${cidName}: ${labels.join(", ")}${labels.length >= 50 ? "..." : ""}\n`;
    });
    fullContext += "\nUse this structure to answer questions about the graph or cluster themes.";
  }

  input.value = "";
  
  const userMsg = document.createElement("div");
  userMsg.innerHTML = "<strong>You:</strong> " + question;
  history.appendChild(userMsg);
  history.scrollTop = history.scrollHeight;
  
  const sender = selectedModel === 'gemini' ? 'Gemini API' : (selectedModel === 'gemini-cli' ? 'Gemini CLI' : 'Ollama');
  
  const aiMsg = document.createElement("div");
  aiMsg.innerHTML = "<strong>" + sender + ":</strong> <span style='color:#888'>Thinking...</span>";
  history.appendChild(aiMsg);
  history.scrollTop = history.scrollHeight;
  
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, context: fullContext, model: selectedModel })
    });
    
    if (res.ok) {
      const data = await res.json();
      aiMsg.innerHTML = "<strong>" + sender + ":</strong> <div class='markdown-body' style='margin-top:8px;font-size:13px;line-height:1.5;'>" + renderMarkdown(data.response) + "</div>";
    } else {
      aiMsg.innerHTML = "<strong>AI:</strong> <span style='color:red'>Error communicating with local server. Are you running 'uv run main.py serve'?</span>";
    }
  } catch (err) {
    aiMsg.innerHTML = "<strong>AI:</strong> <span style='color:red'>Connection failed. Please run 'uv run main.py serve' and open localhost:8000.</span>";
  }
  history.scrollTop = history.scrollHeight;
}

function applyFilters(query = searchInput.value, selectedNodeId = activeNodeId) {
  const lower = (query || "").trim().toLowerCase();
  
  const activeTypes = new Set(
    Array.from(document.querySelectorAll(".type-filter.active")).map(b => b.dataset.type)
  );

  const edgeState = currentEdgeState();
  const filteredEdges = originalEdges.filter(edge => passesEdgeFilters(edge, edgeState));
  rebuildAdjacency(filteredEdges);

  const showHubs = document.getElementById("cb-hubs")?.checked;
  const showOutgoing = document.getElementById("cb-outgoing")?.checked !== false;
  const showIncoming = document.getElementById("cb-incoming")?.checked !== false;

  let hubIds = new Set();
  if (showHubs) {
    const sorted = [...originalNodes].sort((a, b) => b.value - a.value);
    hubIds = new Set(sorted.slice(0, 10).map(n => n.id));
  }

  const relatedIds = new Set();
  if (selectedNodeId) {
    relatedIds.add(selectedNodeId);
    for (const edge of filteredEdges) {
      if (edge.from === selectedNodeId && showOutgoing) relatedIds.add(edge.to);
      if (edge.to === selectedNodeId && showIncoming) relatedIds.add(edge.from);
    }
  }

  const filteredNodeIds = new Set();
  for (const edge of filteredEdges) {
    filteredNodeIds.add(edge.from);
    filteredNodeIds.add(edge.to);
  }

  let visibleNodeCount = 0;
  const nodeUpdates = originalNodes.map(node => {
    const matchesType = activeTypes.has(node.type) || (node.type === "unknown" && activeTypes.size > 0);
    const matchesSearch = !lower || node.label.toLowerCase().includes(lower);
    
    const groupId = node.math_id;
    const matchesCluster = !hiddenClusters.has(groupId);

    const isActive = selectedNodeId === node.id;
    const isConnected = filteredNodeIds.has(node.id);
    const isRelated = !selectedNodeId || relatedIds.has(node.id);
    const withinTime = !node.ms || node.ms <= currentDateMs;
    
    let hidden = !matchesType || !withinTime || !matchesCluster;
    let emphasized = matchesType && withinTime && matchesSearch && matchesCluster && isRelated && (isConnected || !!lower || isActive);
    
    const finalColor = groupId !== undefined && groupId >= 0 ? COMMUNITY_COLORS[groupId % COMMUNITY_COLORS.length] : "#888";

    if (showHubs) {
      if (!hubIds.has(node.id)) {
        hidden = true;
      } else {
        hidden = false;
        emphasized = true;
      }
    }

    if (currentPathIds) {
      hidden = !currentPathIds.includes(node.id);
      emphasized = currentPathIds.includes(node.id);
    }

    if (!hidden) {
      visibleNodeCount += 1;
    }

    return {
      id: node.id,
      hidden,
      color: {
        background: emphasized ? finalColor : hexToRgba(finalColor, hidden ? 0.05 : 0.14),
        border: emphasized ? hexToRgba(finalColor, 0.96) : hexToRgba(finalColor, hidden ? 0.08 : 0.22),
        highlight: { background: finalColor, border: hexToRgba(finalColor, 1) },
        hover: { background: finalColor, border: hexToRgba(finalColor, 1) },
      },
      font: {
        color: emphasized ? "#f2f3f8" : hidden ? "rgba(242,243,248,0.08)" : "rgba(242,243,248,0.2)",
      },
      borderWidth: isActive ? 5 : 2,
    };
  });

  const edgeUpdates = originalEdges.map(edge => {
    const enabled = passesEdgeFilters(edge, edgeState);
    if (!enabled) {
      return { id: edge.id, hidden: true };
    }

    const matchesSearch = !lower
      || nodeMap.get(edge.from)?.label.toLowerCase().includes(lower)
      || nodeMap.get(edge.to)?.label.toLowerCase().includes(lower);
    
    const touchesActive = !!selectedNodeId && (edge.from === selectedNodeId || edge.to === selectedNodeId);
    
    let edgeHidden = false;
    let edgeColor = edge.color;
    let edgeWidth = 0.6;
    let emphasized = matchesSearch;

    if (selectedNodeId) {
      const isOutgoing = edge.from === selectedNodeId;
      const isIncoming = edge.to === selectedNodeId;
      
      if (touchesActive) {
        if ((isOutgoing && !showOutgoing) || (isIncoming && !showIncoming)) {
          edgeHidden = true;
        } else {
          edgeHidden = false;
          emphasized = true;
          edgeWidth = 3.5;
          edgeColor = isOutgoing ? "#ff4d4d" : "#4dff4d"; // Red for out, Green for in
        }
      } else {
        const isRelated = relatedIds.has(edge.from) || relatedIds.has(edge.to);
        if (!isRelated) {
          edgeHidden = true;
        } else {
          emphasized = matchesSearch;
          edgeWidth = emphasized ? 1.2 : 0.6;
          edgeColor = emphasized ? edge.color : hexToRgba(edge.color, 0.08);
        }
      }
    } else {
      edgeWidth = emphasized ? 1.2 : 0.6;
      edgeColor = emphasized ? edge.color : hexToRgba(edge.color, 0.08);
    }

    if (showHubs) {
      if (!hubIds.has(edge.from) || !hubIds.has(edge.to)) return { id: edge.id, hidden: true };
      edgeHidden = false;
      emphasized = true;
      edgeWidth = 1.2;
      edgeColor = edge.color;
    }

    if (currentPathIds) {
      const idxFrom = currentPathIds.indexOf(edge.from);
      const idxTo = currentPathIds.indexOf(edge.to);
      const isPathEdge = idxFrom !== -1 && idxTo !== -1 && Math.abs(idxFrom - idxTo) === 1;
      if (!isPathEdge) return { id: edge.id, hidden: true };
      edgeHidden = false;
      emphasized = true;
      edgeWidth = 3.0;
      edgeColor = edge.color;
    }

    return {
      id: edge.id,
      hidden: edgeHidden,
      width: edgeWidth,
      color: edgeColor,
    };
  });

  nodes.update(nodeUpdates);
  edges.update(edgeUpdates);

  if (selectedNodeId) {
    const activeNode = nodeMap.get(selectedNodeId);
    if (activeNode) {
      openDrawer(activeNode, relatedIds || new Set([selectedNodeId]));
    }
  }

  const focusSuffix = selectedNodeId && nodeMap.get(selectedNodeId)
    ? ` · focused: ${nodeMap.get(selectedNodeId).label}`
    : "";
  stats.textContent = `${visibleNodeCount} nodes · ${filteredEdges.length} edges${focusSuffix}`;
}

const container = document.getElementById("graph");

// Adaptive physics based on graph size — larger graphs need more repulsion and longer springs
const nodeCount = originalNodes.length;
const gravConst = nodeCount > 80 ? -12000 : nodeCount > 30 ? -8000 : -4000;
const springLen = nodeCount > 80 ? 300 : nodeCount > 30 ? 250 : 200;

const network = new vis.Network(container, { nodes, edges }, {
  nodes: {
    shape: "dot",
    font: { color: "#ddd", size: 12, strokeWidth: 3, strokeColor: "#111" },
    borderWidth: 1.5,
    scaling: {
      min: 8,
      max: 40,
      label: { enabled: true, min: 10, max: 20, drawThreshold: 6, maxVisible: 24 },
    },
  },
  edges: {
    width: 0.8,
    smooth: { type: "continuous" },
    arrows: { to: { enabled: true, scaleFactor: 0.8 } },
    arrowStrikethrough: false,
    color: { inherit: false },
    hoverWidth: 2,
  },
  physics: {
    stabilization: { iterations: 250, updateInterval: 25, fit: true },
    barnesHut: { gravitationalConstant: gravConst, springLength: springLen, springConstant: 0.02, damping: 0.15 },
    minVelocity: 0.75,
  },
  interaction: { hover: true, tooltipDelay: 150, hideEdgesOnDrag: true, hideEdgesOnZoom: true },
});

// Auto-fit the graph to the viewport after physics settles
network.once("stabilizationIterationsDone", function () {
  network.fit({ animation: { duration: 400, easingFunction: "easeInOutQuad" } });
});

function focusNodeByLabel(label) {
  const node = originalNodes.find(n => n.label === label);
  if (node) focusNode(node.id);
}

function focusNode(nodeId) {
  activeNodeId = nodeId;
  applyFilters(searchInput.value, nodeId);
  const node = nodeMap.get(nodeId) || nodes.get(nodeId);
  const relatedIds = new Set([nodeId, ...(adjacency.get(nodeId) || [])]);
  openDrawer(node, relatedIds);
  network.focus(nodeId, {
    scale: 1.1,
    animation: { duration: 300, easingFunction: "easeInOutQuad" },
  });
}

network.on("click", params => {
  if (params.nodes.length > 0) {
    focusNode(params.nodes[0]);
  } else {
    clearSelection();
  }
});

applyFilters();

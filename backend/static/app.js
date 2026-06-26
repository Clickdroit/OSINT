// API Base Configuration
const API_BASE = "";

// Global State
let activeTargetId = null;
let activeTargetValue = "";
let activeTargetType = "";
let scanPollInterval = null;
let ingestPollInterval = null;
let chatHistory = [];

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initTargets();
    initLeaks();
    initKeywordsAndAlerts();
    initAICopilot();
    initRemediator();
    initDashboard();
    initFeeds();
});

// --- TABS CONTROLLER ---
function initTabs() {
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabContents = document.querySelectorAll(".tab-content");

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const tabId = btn.getAttribute("data-tab");
            
            navButtons.forEach(b => b.classList.remove("active"));
            tabContents.forEach(c => c.classList.remove("active"));

            btn.classList.add("active");
            document.getElementById(`tab-${tabId}`).classList.add("active");
        });
    });
}

// --- TARGETS & ALIAS SCANNER ---
function initTargets() {
    const targetForm = document.getElementById("target-form");
    const startScanBtn = document.getElementById("start-scan-btn");
    const closeResultsBtn = document.getElementById("close-results-btn");

    // Load initial targets
    fetchTargets();

    // Create target handler
    targetForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const value = document.getElementById("target-value").value.trim();
        const type = document.getElementById("target-type").value;

        try {
            const response = await fetch(`${API_BASE}/api/v1/targets`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value, type })
            });

            if (response.ok) {
                targetForm.reset();
                fetchTargets();
            } else {
                const err = await response.json();
                alert(`Erreur: ${err.detail || "Impossible de créer la cible"}`);
            }
        } catch (error) {
            console.error("Error creating target:", error);
        }
    });

    // Bulk CSV import handler
    const bulkImportForm = document.getElementById("bulk-import-form");
    const importResults = document.getElementById("import-results");
    if (bulkImportForm) {
        bulkImportForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const csvFileInput = document.getElementById("csv-file");
            if (!csvFileInput.files || csvFileInput.files.length === 0) return;

            const formData = new FormData();
            formData.append("file", csvFileInput.files[0]);

            try {
                importResults.style.display = "block";
                importResults.innerHTML = `<span class="text-muted">Importation en cours...</span>`;
                const response = await fetch(`${API_BASE}/api/v1/targets/import-csv`, {
                    method: "POST",
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    let html = `<span class="text-success" style="font-weight:600;">Importation réussie : ${data.created} cible(s) ajoutée(s).</span>`;
                    if (data.errors && data.errors.length > 0) {
                        html += `<ul style="color:var(--color-error); margin-top:5px; padding-left:15px;">`;
                        data.errors.slice(0, 5).forEach(err => {
                            html += `<li>${err}</li>`;
                        });
                        if (data.errors.length > 5) {
                            html += `<li>... et ${data.errors.length - 5} autres erreurs</li>`;
                        }
                        html += `</ul>`;
                    }
                    importResults.innerHTML = html;
                    bulkImportForm.reset();
                    fetchTargets();
                } else {
                    const err = await response.json();
                    importResults.innerHTML = `<span class="text-error">Erreur: ${err.detail || "Échec de l'importation."}</span>`;
                }
            } catch (error) {
                console.error("CSV import error:", error);
                importResults.innerHTML = `<span class="text-error">Erreur de connexion lors de l'importation.</span>`;
            }
        });
    }

    // Trigger username scan
    startScanBtn.addEventListener("click", () => {
        if (activeTargetId) {
            triggerScan(activeTargetId);
        }
    });

    // Hide scan panel
    closeResultsBtn.addEventListener("click", () => {
        document.getElementById("scan-results-card").style.display = "none";
        clearInterval(scanPollInterval);
    });

    // Wire up filter bar
    initFilterBar();

    // Wire up export CSV button
    const exportCsvBtn = document.getElementById("export-csv-btn");
    if (exportCsvBtn) exportCsvBtn.addEventListener("click", exportCSV);
}

async function fetchTargets() {
    const tbody = document.querySelector("#targets-table tbody");
    try {
        const response = await fetch(`${API_BASE}/api/v1/targets`);
        if (!response.ok) throw new Error("Failed to fetch targets");
        
        const targets = await response.json();
        
        if (targets.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Aucune cible enregistrée.</td></tr>`;
            return;
        }

        tbody.innerHTML = "";
        targets.forEach(t => {
            const tr = document.createElement("tr");
            tr.style.cursor = t.type === "username" || t.type === "domain" ? "pointer" : "default";
            
            // Format type badge
            const badgeClass = `badge badge-${t.type}`;
            const typeLabel = t.type === "username" ? "Pseudo" : t.type === "email" ? "Email" : "Domaine";
            
            // Formulate date
            const dateStr = new Date(t.created_at).toLocaleString("fr-FR");

            // Formulate notes cell
            const notesStr = t.notes || "";
            const notesSnippet = notesStr.length > 25 ? notesStr.substring(0, 22) + "..." : notesStr;
            const notesCellContent = notesStr 
                ? `<span class="target-notes-text" title="${notesStr}">${notesSnippet}</span> <button class="btn btn-secondary btn-xs edit-notes-btn" data-id="${t.id}" data-notes="${notesStr.replace(/"/g, '&quot;')}" style="padding: 2px 5px; font-size: 0.65rem;">✏️</button>` 
                : `<button class="btn btn-secondary btn-xs edit-notes-btn" data-id="${t.id}" data-notes="" style="padding: 2px 5px; font-size: 0.65rem;">+ Note</button>`;

            tr.innerHTML = `
                <td><strong>${t.value}</strong></td>
                <td><span class="${badgeClass}">${typeLabel}</span></td>
                <td>${dateStr}</td>
                <td>${notesCellContent}</td>
                <td>
                    ${(t.type === 'username' || t.type === 'domain' || t.type === 'email') ? `<button class="btn btn-primary btn-sm inspect-btn" data-id="${t.id}" data-val="${t.value}" data-type="${t.type}">Analyser</button>` : ''}
                    <button class="btn btn-danger btn-sm delete-target-btn" data-id="${t.id}">Supprimer</button>
                </td>
            `;

            // Click row to inspect target
            if (t.type === "username" || t.type === "domain" || t.type === "email") {
                tr.addEventListener("click", (e) => {
                    if (e.target.classList.contains("delete-target-btn") || e.target.classList.contains("edit-notes-btn")) return;
                    showScanPanel(t.id, t.value, t.type);
                });
            } else {
                // Delete button bindings for other types
                tr.querySelector(".delete-target-btn").addEventListener("click", (e) => {
                    e.stopPropagation();
                    deleteTarget(t.id);
                });
            }
            
            // Delete button binding for username rows
            const delBtn = tr.querySelector(".delete-target-btn");
            if (delBtn) {
                delBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    deleteTarget(t.id);
                });
            }

            // Edit notes binding
            const editNotesBtn = tr.querySelector(".edit-notes-btn");
            if (editNotesBtn) {
                editNotesBtn.addEventListener("click", async (e) => {
                    e.stopPropagation();
                    const targetId = editNotesBtn.dataset.id;
                    const currentNotes = editNotesBtn.dataset.notes;
                    const newNotes = prompt(`Modifier les notes pour cette cible :`, currentNotes);
                    if (newNotes === null) return;

                    try {
                        const res = await fetch(`${API_BASE}/api/v1/targets/${targetId}/notes`, {
                            method: "PATCH",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ notes: newNotes.trim() })
                        });
                        if (res.ok) {
                            fetchTargets();
                        } else {
                            alert("Impossible de sauvegarder la note.");
                        }
                    } catch (err) {
                        console.error("Notes update error:", err);
                    }
                });
            }

            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error("Error listing targets:", error);
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-error">Erreur lors de la récupération des cibles.</td></tr>`;
    }
}

async function deleteTarget(id) {
    if (!confirm("Voulez-vous supprimer cette cible et ses résultats de scan ?")) return;
    try {
        const response = await fetch(`${API_BASE}/api/v1/targets/${id}`, { method: "DELETE" });
        if (response.ok) {
            if (activeTargetId === id) {
                document.getElementById("scan-results-card").style.display = "none";
                clearInterval(scanPollInterval);
            }
            fetchTargets();
        }
    } catch (error) {
        console.error("Error deleting target:", error);
    }
}

function showScanPanel(targetId, targetValue, targetType) {
    activeTargetId = targetId;
    activeTargetValue = targetValue;
    activeTargetType = targetType;
    
    document.getElementById("scan-results-card").style.display = "block";
    
    let panelTitle = `Analyse d'Alias : ${targetValue}`;
    let scanBtnLabel = `Lancer la recherche (110+ sites)`;
    if (targetType === "domain") {
        panelTitle = `Audit de Sécurité Domaine : ${targetValue}`;
        scanBtnLabel = `Lancer l'audit de sécurité`;
    } else if (targetType === "email") {
        panelTitle = `Audit de Sécurité Email : ${targetValue}`;
        scanBtnLabel = `Lancer l'audit de l'adresse email`;
    }
    
    document.getElementById("results-title").innerText = panelTitle;
    document.getElementById("scan-target-name").innerText = `Cible active : ${targetValue}`;
    document.getElementById("start-scan-btn").innerText = scanBtnLabel;
    
    // Show filter bar & export only for username scans
    const filterBar = document.getElementById("scan-filter-bar");
    const exportBtn = document.getElementById("export-csv-btn");
    if (targetType === "username") {
        filterBar.style.display = "flex";
    } else {
        filterBar.style.display = "none";
        if (exportBtn) exportBtn.style.display = "none";
    }

    // Reset active filter
    document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
    const allBtn = document.querySelector(".filter-btn[data-filter='all']");
    if (allBtn) allBtn.classList.add("active");
    
    // Hide details during initialization
    document.getElementById("scan-progress-container").style.display = "none";
    document.getElementById("scan-stats").style.display = "none";
    
    clearInterval(scanPollInterval);
    
    // Load pre-existing scan results if they exist
    fetchScanResults(targetId);
}

async function fetchScanResults(targetId) {
    const grid = document.getElementById("scan-results-grid");
    grid.innerHTML = `<div class="pad-20 text-center text-muted">Chargement des scans précédents...</div>`;
    
    try {
        const response = await fetch(`${API_BASE}/api/v1/targets/${targetId}/results`);
        if (!response.ok) throw new Error();
        
        const results = await response.json();
        
        if (results.length === 0) {
            grid.innerHTML = `<div class="pad-20 text-center text-muted" style="grid-column: 1/-1;">Aucun scan lancé. Cliquez sur "Lancer la recherche" ci-dessus.</div>`;
            return;
        }

        renderResultsGrid(results);
        displayStats(results);

    } catch (error) {
        grid.innerHTML = `<div class="pad-20 text-center text-error" style="grid-column: 1/-1;">Erreur de chargement des résultats.</div>`;
    }
}

// Category display names
const CATEGORY_LABELS = {
    social: "🌐 Réseaux Sociaux",
    dev: "💻 Développement & Tech",
    gaming: "🎮 Gaming",
    creative: "🎨 Créatif & Art",
    music: "🎵 Musique & Vidéo",
    financial: "💰 Finance & Support",
    security: "🔐 Cybersécurité & CTF",
    other: "📦 Autres"
};
const CATEGORY_ORDER = ["social", "dev", "gaming", "creative", "music", "financial", "security", "other"];

let allScanResults = []; // Store full results for filtering
let activeFilter = "all";

function parseDetails(details) {
    if (!details) return { category: "other", metadata: {} };
    try {
        if (details.trim().startsWith("{") && details.trim().endsWith("}")) {
            return JSON.parse(details);
        }
    } catch (e) {
        // Fall back
    }
    return { category: details, metadata: {} };
}

function parseAIReport(reportText) {
    if (!reportText) return null;
    let score = null;
    const scoreMatch = reportText.match(/\*\*SCORE DE CONFIANCE IA\s*:\s*(\d+)%\*\*/i);
    if (scoreMatch) {
        score = parseInt(scoreMatch[1], 10);
    }
    
    let identity = null;
    const jsonMatch = reportText.match(/```json\s*([\s\S]*?)\s*```/i);
    if (jsonMatch) {
        try {
            identity = JSON.parse(jsonMatch[1].trim());
        } catch (e) {
            console.error("Failed to parse identity JSON from AI report:", e);
        }
    }
    return { score, identity };
}

function renderResultsGrid(results, filterStatus = "all") {
    allScanResults = results;
    const grid = document.getElementById("scan-results-grid");
    grid.innerHTML = "";

    const AI_PLATFORMS = ["Rapport de Sécurité IA", "Rapport OSINT IA"];

    // Separate AI report from normal results
    const aiReports = results.filter(r => AI_PLATFORMS.includes(r.platform));
    const normalResults = results.filter(r => !AI_PLATFORMS.includes(r.platform));

    // Apply status filter
    const filtered = filterStatus === "all" ? normalResults : normalResults.filter(r => r.status === filterStatus);

    // Identity Card Rendering
    const identityContainer = document.getElementById("identity-card-container");
    if (identityContainer) {
        identityContainer.style.display = "none";
        identityContainer.innerHTML = "";
    }

    if (activeTargetType === "username") {
        const osintAiReport = aiReports.find(r => r.platform === "Rapport OSINT IA");
        if (osintAiReport) {
            const parsedReport = parseAIReport(osintAiReport.details);
            if (parsedReport && (parsedReport.score !== null || parsedReport.identity)) {
                identityContainer.style.display = "block";
                const score = parsedReport.score !== null ? parsedReport.score : 0;
                const identity = parsedReport.identity || {};
                const name = identity.nom_probable || "Inconnu";
                const location = identity.localisation_probable || "Non spécifiée";
                const bio = identity.bio_synthétisée || "Aucune description synthétisée disponible.";
                const interests = identity.centres_interets || [];
                const avatar = identity.photo_profil_probable || "";

                const interestsHtml = interests.map(i => `<span class="badge badge-username">${i}</span>`).join(" ");
                const gaugeColor = score >= 75 ? "#00ff88" : score >= 40 ? "#ffaa00" : "#ff3333";

                // We extract the original target value being scanned
                const scannedUsername = document.getElementById("scan-target-name").innerText.replace("Cible: ", "").trim();

                identityContainer.innerHTML = `
                    <div class="card card-glow identity-card" style="display: flex; gap: 20px; align-items: flex-start; padding: 20px; border: 1px solid var(--accent-glow);">
                        <div class="identity-avatar-container" style="flex-shrink: 0; width: 80px; height: 80px; border-radius: 50%; overflow: hidden; border: 2px solid var(--accent); background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center;">
                            <img src="${avatar}" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='https://api.dicebear.com/7.x/identicon/svg?seed=${scannedUsername}';">
                        </div>
                        <div class="identity-info-container" style="flex-grow: 1;">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 15px; width:100%;">
                                <div>
                                    <h3 style="margin: 0; font-size: 1.25rem; color: var(--accent);">${name}</h3>
                                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">📍 ${location}</div>
                                </div>
                                <div class="identity-gauge-container" style="text-align: right; min-width: 150px;">
                                    <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase;">Confiance Identité</div>
                                    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 10px; margin-top: 5px;">
                                        <div style="width: 80px; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; overflow: hidden;">
                                            <div style="width: ${score}%; height: 100%; background: ${gaugeColor}; border-radius: 3px;"></div>
                                        </div>
                                        <span style="font-size: 1rem; font-weight: bold; color: ${gaugeColor};">${score}%</span>
                                    </div>
                                </div>
                            </div>
                            <p style="margin-top: 10px; font-size: 0.85rem; line-height: 1.5; color: var(--text-secondary);">${bio}</p>
                            ${interests.length > 0 ? `<div style="margin-top: 10px; display:flex; flex-wrap:wrap; gap:5px; align-items:center;"><span style="font-size: 0.75rem; color: var(--text-secondary); margin-right:5px;">Intérêts:</span>${interestsHtml}</div>` : ''}
                        </div>
                    </div>
                `;
            }
        }
    }

    if (activeTargetType === "username") {
        // Group by category
        const groups = {};
        filtered.forEach(res => {
            const parsed = parseDetails(res.details);
            const cat = parsed.category || "other";
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push(res);
        });

        // Render each category group
        CATEGORY_ORDER.forEach(cat => {
            if (!groups[cat] || groups[cat].length === 0) return;
            
            const header = document.createElement("div");
            header.className = "category-header";
            header.style.gridColumn = "1 / -1";
            header.innerHTML = `<span>${CATEGORY_LABELS[cat] || cat}</span><span class="category-count">${groups[cat].length} résultat${groups[cat].length > 1 ? 's' : ''}</span>`;
            grid.appendChild(header);

            groups[cat].forEach(res => grid.appendChild(buildResultCard(res)));
        });

        if (filtered.length === 0) {
            grid.innerHTML = `<div class="pad-20 text-center text-muted" style="grid-column:1/-1">Aucun résultat pour ce filtre.</div>`;
        }
    } else {
        // Domain / email: render flat list
        filtered.forEach(res => grid.appendChild(buildResultCard(res)));
        if (filtered.length === 0) {
            grid.innerHTML = `<div class="pad-20 text-center text-muted" style="grid-column:1/-1">Aucun résultat.</div>`;
        }
    }

    // Always render AI reports at the bottom, full width
    aiReports.forEach(res => {
        const reportCard = document.createElement("div");
        reportCard.className = "result-card status-found ai-report-full-width";
        reportCard.style.gridColumn = "1 / -1";
        reportCard.style.border = "1px solid var(--accent-glow)";
        const badge = res.platform === "Rapport OSINT IA" ? "Analyse OSINT IA" : "Analyse IA";
        
        // Clean out JSON code block from rendering in standard markdown to keep UI clean
        let cleanDetails = res.details;
        const jsonBlockRegex = /```json\s*[\s\S]*?\s*```/i;
        cleanDetails = cleanDetails.replace(jsonBlockRegex, "").trim();
        // Also remove score line from main markdown body if it starts with it
        cleanDetails = cleanDetails.replace(/^\*\*SCORE DE CONFIANCE IA\s*:\s*\d+%\*\*/i, "").trim();

        reportCard.innerHTML = `
            <div class="result-info" style="width: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 15px; width: 100%;">
                    <span class="result-name" style="font-size: 1.1rem; color: var(--accent); font-weight: 700;">${res.platform}</span>
                    <span class="badge badge-domain">${badge}</span>
                </div>
                <div class="markdown-body" style="font-size: 0.95rem; color: var(--text-secondary); line-height: 1.6; text-align: justify; width: 100%;">
                    ${formatAIResponseText(cleanDetails)}
                </div>
            </div>
        `;
        grid.appendChild(reportCard);
    });
}

function buildResultCard(res) {
    const card = document.createElement("div");
    const statusClass = res.status.toLowerCase();
    card.className = `result-card status-${statusClass}`;
    card.dataset.status = res.status;

    const isFound = res.status === "FOUND";
    let statusLabel = res.status === "FOUND" ? "TROUVÉ" : res.status === "NOT_FOUND" ? "ABSENT" : "ERREUR";
    if (activeTargetType === "domain") {
        statusLabel = res.status === "FOUND" ? "SÉCURISÉ" : res.status === "NOT_FOUND" ? "ALERTE" : "ERREUR";
    }

    let actionHtml = "";
    if (isFound && res.url && activeTargetType !== "username") {
        actionHtml = `<a href="${res.url}" target="_blank" class="result-link">Accéder &rarr;</a>`;
    } else if (isFound && res.url && activeTargetType === "username") {
        actionHtml = `<a href="${res.url}" target="_blank" class="btn-profile-link">Voir le profil →</a>`;
    } else if (res.status === "NOT_FOUND" && activeTargetType === "username") {
        actionHtml = ``;
    } else if (res.details && activeTargetType !== "username") {
        actionHtml = `<span class="text-muted" style="font-size:0.8rem; display:block; margin-top:5px; line-height:1.4;">${res.details}</span>`;
    } else {
        actionHtml = `<span class="text-muted" style="font-size:0.75rem;">Non détecté</span>`;
    }

    const parsed = parseDetails(res.details);
    const meta = parsed.metadata || {};
    
    let metaHtml = "";
    let avatarHtml = "";
    
    if (isFound && activeTargetType === "username") {
        const avatarUrl = meta.avatar_url || meta.image;
        if (avatarUrl) {
            avatarHtml = `
                <div class="result-avatar" style="flex-shrink: 0; width: 32px; height: 32px; border-radius: 4px; overflow: hidden; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.03); display: flex; align-items: center; justify-content: center; margin-right: 10px;">
                    <img src="${avatarUrl}" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.style.display='none';">
                </div>
            `;
        }
        
        const displayName = meta.name || meta.title;
        const displayBio = meta.bio || meta.description;
        const displayLoc = meta.location;
        const repos = meta.public_repos !== undefined ? `${meta.public_repos} repos` : "";
        const karma = meta.total_karma !== undefined ? `${meta.total_karma} karma` : "";
        const extraList = [displayLoc, repos, karma].filter(Boolean);
        const extraText = extraList.length > 0 ? `📍 ${extraList.join(" | ")}` : "";

        if (displayName || displayBio || extraText) {
            metaHtml = `
                <div class="result-meta-details" style="margin-top: 8px; font-size: 0.75rem; color: var(--text-secondary); border-top: 1px solid rgba(255,255,255,0.03); padding-top: 6px; display: flex; flex-direction: column; gap: 3px;">
                    ${displayName ? `<div style="font-weight: 600; color: var(--accent);">${displayName}</div>` : ''}
                    ${displayBio ? `<div style="font-style: italic; opacity: 0.85; line-height:1.3;">"${displayBio.length > 85 ? displayBio.substring(0, 82) + "..." : displayBio}"</div>` : ''}
                    ${extraText ? `<div style="opacity: 0.7; font-size: 0.7rem;">${extraText}</div>` : ''}
                </div>
            `;
        }
    }

    card.innerHTML = `
        <div style="display: flex; flex-direction: column; width: 100%;">
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
                <div style="display: flex; align-items: center;">
                    ${avatarHtml}
                    <div class="result-info">
                        <span class="result-name">${res.platform}</span>
                        ${actionHtml}
                    </div>
                </div>
                <span class="result-status-tag">${statusLabel}</span>
            </div>
            ${metaHtml}
        </div>
    `;
    return card;
}

function initFilterBar() {
    document.querySelectorAll(".filter-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            activeFilter = btn.dataset.filter;
            renderResultsGrid(allScanResults, activeFilter);
        });
    });
}

function exportCSV() {
    const found = allScanResults.filter(r => r.status === "FOUND" && r.url && !["Rapport OSINT IA", "Rapport de Sécurité IA"].includes(r.platform));
    if (found.length === 0) { alert("Aucun profil trouvé à exporter."); return; }
    const rows = [["Plateforme", "URL", "Pseudo"]];
    found.forEach(r => rows.push([r.platform, r.url, activeTargetValue]));
    const csv = rows.map(r => r.map(v => `"${(v||"").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `osint_${activeTargetValue}_profils.csv`;
    a.click();
}

function animateCounter(el, target) {
    const duration = 600;
    const start = parseInt(el.innerText) || 0;
    const startTime = performance.now();
    const update = (now) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        el.innerText = Math.round(start + (target - start) * progress);
        if (progress < 1) requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
}

function displayStats(results) {
    document.getElementById("scan-stats").style.display = "grid";
    
    const AI_PLATFORMS = ["Rapport de Sécurité IA", "Rapport OSINT IA"];
    const labelFound = document.querySelector("#scan-stats .stat-box:nth-child(1) .stat-label");
    const labelNotFound = document.querySelector("#scan-stats .stat-box:nth-child(2) .stat-label");
    const exportBtn = document.getElementById("export-csv-btn");
    
    // Exclude AI report rows from counts
    const countable = results.filter(r => !AI_PLATFORMS.includes(r.platform));
    const found = countable.filter(r => r.status === "FOUND").length;
    const notfound = countable.filter(r => r.status === "NOT_FOUND").length;
    const error = countable.filter(r => r.status === "ERROR").length;

    if (activeTargetType === "domain") {
        if (labelFound) labelFound.innerText = "Sécurisés / Présents";
        if (labelNotFound) labelNotFound.innerText = "Alertes / Manquants";
    } else if (activeTargetType === "email") {
        if (labelFound) labelFound.innerText = "Fuites / Profils Détectés";
        if (labelNotFound) labelNotFound.innerText = "Non détectés / Sécurisés";
    } else {
        if (labelFound) labelFound.innerText = "Profils trouvés";
        if (labelNotFound) labelNotFound.innerText = "Non trouvés";
    }

    animateCounter(document.getElementById("stat-found"), found);
    animateCounter(document.getElementById("stat-notfound"), notfound);
    animateCounter(document.getElementById("stat-error"), error);

    // Show export button only for username scans with results
    if (exportBtn && activeTargetType === "username" && found > 0) {
        exportBtn.style.display = "flex";
    } else if (exportBtn) {
        exportBtn.style.display = "none";
    }
}

// --- CELERY SCANS MANAGER (POLLING) ---
async function triggerScan(targetId) {
    const progressContainer = document.getElementById("scan-progress-container");
    const progressFill = document.getElementById("scan-progress-fill");
    const progressText = document.getElementById("scan-progress-text");
    const startScanBtn = document.getElementById("start-scan-btn");

    startScanBtn.disabled = true;
    progressContainer.style.display = "block";
    progressFill.style.width = "0%";
    progressText.innerText = "Création de la tâche de scan...";
    
    try {
        let scanUrl = `${API_BASE}/api/v1/scans/pseudo?target_id=${targetId}`;
        if (activeTargetType === "domain") {
            scanUrl = `${API_BASE}/api/v1/scans/domain?target_id=${targetId}`;
        } else if (activeTargetType === "email") {
            scanUrl = `${API_BASE}/api/v1/scans/email?target_id=${targetId}`;
        }
            
        const response = await fetch(scanUrl, { method: "POST" });
        if (!response.ok) throw new Error();
        
        const task = await response.json();
        const taskId = task.task_id;
        
        progressText.innerText = "Tâche envoyée au worker. Début de l'analyse...";
        progressFill.style.width = "10%";

        // Poll Celery status
        clearInterval(scanPollInterval);
        scanPollInterval = setInterval(() => {
            pollScanStatus(taskId, targetId);
        }, 1000);

    } catch (error) {
        startScanBtn.disabled = false;
        progressText.innerText = "Erreur lors du lancement de la tâche.";
        alert("Erreur de lancement de scan.");
    }
}

async function pollScanStatus(taskId, targetId) {
    const progressFill = document.getElementById("scan-progress-fill");
    const progressText = document.getElementById("scan-progress-text");
    const startScanBtn = document.getElementById("start-scan-btn");

    try {
        const response = await fetch(`${API_BASE}/api/v1/scans/${taskId}`);
        if (!response.ok) throw new Error();
        
        const task = await response.json();
        
        if (task.status === "PENDING" || task.status === "STARTED") {
            let statusTextMsg = "Recherche en cours sur 100+ plateformes (5s env)...";
            if (activeTargetType === "domain") {
                statusTextMsg = "Audit du certificat SSL, des en-têtes HTTP et DNS en cours...";
            } else if (activeTargetType === "email") {
                statusTextMsg = "Audit de l'adresse email (fuites locales, Gravatar, serveurs MX) en cours...";
            }
            progressText.innerText = statusTextMsg;
            // Mock incremental progress while pending
            let currentWidth = parseFloat(progressFill.style.width) || 0;
            if (currentWidth < 90) {
                progressFill.style.width = `${currentWidth + 15}%`;
            }
        } else if (task.status === "SUCCESS") {
            clearInterval(scanPollInterval);
            progressFill.style.width = "100%";
            progressText.innerText = "Scan complété avec succès !";
            startScanBtn.disabled = false;
            
            // Reload results
            fetchScanResults(targetId);
            fetchTargets();
        } else {
            // Task failed
            clearInterval(scanPollInterval);
            progressText.innerText = `Échec de l'analyse (Status: ${task.status})`;
            startScanBtn.disabled = false;
        }
    } catch (error) {
        clearInterval(scanPollInterval);
        progressText.innerText = "Erreur de communication avec le serveur.";
        startScanBtn.disabled = false;
    }
}


// --- LEAKS & INGESTION ---
function initLeaks() {
    const searchBtn = document.getElementById("search-leak-btn");
    const ingestForm = document.getElementById("ingest-form");

    searchBtn.addEventListener("click", () => searchLeaks());
    document.getElementById("leak-query").addEventListener("keypress", (e) => {
        if (e.key === "Enter") searchLeaks();
    });

    ingestForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const filePath = document.getElementById("ingest-file-path").value.trim();
        const source = document.getElementById("ingest-source").value.trim();
        const date = document.getElementById("ingest-date").value;
        
        let url = `${API_BASE}/api/v1/leaks/ingest?file_path=${encodeURIComponent(filePath)}&source=${encodeURIComponent(source)}`;
        if (date) {
            url += `&leak_date=${date}`;
        }

        try {
            const response = await fetch(url, { method: "POST" });
            if (response.ok) {
                const task = await response.json();
                ingestForm.reset();
                startIngestPolling(task.task_id);
            } else {
                alert("Erreur de lancement de l'ingestion.");
            }
        } catch (error) {
            console.error("Error starting ingestion:", error);
        }
    });
}

function startIngestPolling(taskId) {
    const banner = document.getElementById("ingest-progress-banner");
    const progressFill = document.getElementById("ingest-progress-fill");
    const progressText = document.getElementById("ingest-progress-text");
    const indicator = document.getElementById("ingest-progress-indicator");

    if (!banner) return;

    banner.style.display = "block";
    progressFill.style.width = "0%";
    progressText.innerText = "Initialisation de l'ingestion...";
    indicator.className = "status-indicator loading";

    clearInterval(ingestPollInterval);
    ingestPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/v1/scans/${taskId}`);
            if (!response.ok) throw new Error();

            const task = await response.json();

            if (task.status === "PROGRESS") {
                const info = task.result || {};
                progressText.innerText = info.status_text || "Lecture en cours...";
                progressFill.style.width = "50%";
            } else if (task.status === "SUCCESS") {
                clearInterval(ingestPollInterval);
                progressFill.style.width = "100%";
                indicator.className = "status-indicator online";
                
                const info = task.result || {};
                progressText.innerText = `Ingestion réussie ! ${info.records_inserted || 0} fuites insérées (${info.lines_processed || 0} lignes lues).`;
                setTimeout(() => {
                    banner.style.display = "none";
                }, 10000);
            } else if (task.status === "PENDING" || task.status === "STARTED") {
                progressText.innerText = "Tâche d'ingestion en attente d'exécution...";
            } else {
                clearInterval(ingestPollInterval);
                indicator.className = "status-indicator online";
                progressText.innerText = `Échec de l'ingestion ou traitement terminé (Statut: ${task.status})`;
                progressFill.style.width = "0%";
            }
        } catch (error) {
            console.error("Ingest poll error:", error);
        }
    }, 2000);
}

async function searchLeaks() {
    const query = document.getElementById("leak-query").value.trim();
    const fuzzy = document.getElementById("leak-fuzzy").checked;
    const tbody = document.querySelector("#leaks-table tbody");

    if (query.length < 3) {
        alert("Veuillez saisir au moins 3 caractères pour lancer une recherche.");
        return;
    }

    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Recherche en cours...</td></tr>`;

    try {
        const response = await fetch(`${API_BASE}/api/v1/leaks/search?q=${encodeURIComponent(query)}&fuzzy=${fuzzy}`);
        if (!response.ok) throw new Error();
        
        const results = await response.json();

        if (results.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">Aucune correspondance trouvée dans les bases de fuites.</td></tr>`;
            return;
        }

        tbody.innerHTML = "";
        results.forEach(l => {
            const tr = document.createElement("tr");
            
            const hashVal = l.password_hash || '';
            let hashHtml = '-';
            if (hashVal) {
                hashHtml = `
                    <span class="password-cell">
                        <span class="password-masked">••••••••••••••••</span>
                        <span class="password-raw" style="display:none;"><code style="font-family:var(--font-mono);font-size:0.8rem;">${hashVal}</code></span>
                        <button class="btn btn-secondary btn-sm toggle-password-btn" style="padding: 2px 6px; font-size: 0.75rem;">Afficher</button>
                    </span>
                `;
            }
            
            tr.innerHTML = `
                <td>${l.username || '<span class="text-muted">-</span>'}</td>
                <td><strong>${l.email || '<span class="text-muted">-</span>'}</strong></td>
                <td>${hashHtml}</td>
                <td><span class="badge badge-email">${l.source || 'Inconnue'}</span></td>
                <td>${l.leak_date || 'N/A'}</td>
            `;
            
            if (hashVal) {
                const toggleBtn = tr.querySelector(".toggle-password-btn");
                const maskedSpan = tr.querySelector(".password-masked");
                const rawSpan = tr.querySelector(".password-raw");
                if (toggleBtn && maskedSpan && rawSpan) {
                    toggleBtn.addEventListener("click", () => {
                        const isHidden = rawSpan.style.display === "none";
                        if (isHidden) {
                            rawSpan.style.display = "inline-block";
                            maskedSpan.style.display = "none";
                            toggleBtn.innerText = "Masquer";
                        } else {
                            rawSpan.style.display = "none";
                            maskedSpan.style.display = "inline-block";
                            toggleBtn.innerText = "Afficher";
                        }
                    });
                }
            }
            
            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error("Error searching leaks:", error);
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-error">Erreur lors de la recherche.</td></tr>`;
    }
}


// --- VEILLE CYBER, RSS & MOTS-CLES ---
function initKeywordsAndAlerts() {
    const keywordForm = document.getElementById("keyword-form");
    const triggerRssBtn = document.getElementById("trigger-rss-btn");

    fetchKeywords();
    fetchAlerts();

    // Add keyword
    keywordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const value = document.getElementById("keyword-value").value.trim();

        try {
            const response = await fetch(`${API_BASE}/api/v1/keywords`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ value })
            });

            if (response.ok) {
                document.getElementById("keyword-value").value = "";
                fetchKeywords();
            }
        } catch (error) {
            console.error("Error creating keyword:", error);
        }
    });

    // Manual scrape trigger
    triggerRssBtn.addEventListener("click", async () => {
        triggerRssBtn.disabled = true;
        triggerRssBtn.innerText = "Scraping en cours...";
        try {
            const response = await fetch(`${API_BASE}/api/v1/rss/trigger`, { method: "POST" });
            if (response.ok) {
                alert("Scraping RSS lancé en tâche de fond !");
                // Wait 4 seconds and refresh alerts
                setTimeout(() => {
                    fetchAlerts();
                    triggerRssBtn.disabled = false;
                    triggerRssBtn.innerText = "Déclencher le Scraper Manuellement";
                }, 4000);
            } else {
                triggerRssBtn.disabled = false;
                triggerRssBtn.innerText = "Déclencher le Scraper Manuellement";
            }
        } catch (error) {
            triggerRssBtn.disabled = false;
            triggerRssBtn.innerText = "Déclencher le Scraper Manuellement";
        }
    });
}

async function fetchKeywords() {
    const list = document.getElementById("keywords-list");
    try {
        const response = await fetch(`${API_BASE}/api/v1/keywords`);
        if (!response.ok) throw new Error();
        
        const keywords = await response.json();

        if (keywords.length === 0) {
            list.innerHTML = `<span class="text-muted" style="font-size:0.85rem;">Aucun mot-clé enregistré.</span>`;
            return;
        }

        list.innerHTML = "";
        keywords.forEach(k => {
            const tag = document.createElement("span");
            tag.className = "keyword-tag";
            tag.innerHTML = `
                ${k.value}
                <button class="keyword-delete" data-id="${k.id}">&times;</button>
            `;
            
            tag.querySelector(".keyword-delete").addEventListener("click", () => deleteKeyword(k.id));
            list.appendChild(tag);
        });

    } catch (error) {
        console.error("Error loading keywords:", error);
    }
}

async function deleteKeyword(id) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/keywords/${id}`, { method: "DELETE" });
        if (response.ok) {
            fetchKeywords();
        }
    } catch (error) {
        console.error("Error deleting keyword:", error);
    }
}

async function fetchAlerts() {
    const container = document.getElementById("alerts-container");
    try {
        const response = await fetch(`${API_BASE}/api/v1/alerts`);
        if (!response.ok) throw new Error();
        
        const alerts = await response.json();

        if (alerts.length === 0) {
            container.innerHTML = `<div class="text-center text-muted pad-20">Aucune alerte n'a encore été détectée dans les flux de sécurité.</div>`;
            return;
        }

        container.innerHTML = "";
        alerts.forEach(a => {
            const dateStr = new Date(a.found_at).toLocaleString("fr-FR");
            const item = document.createElement("div");
            item.className = "alert-item";

            // Title linking to source or unlinked
            const titleHtml = a.url 
                ? `<a href="${a.url}" target="_blank">${a.title} &rarr;</a>` 
                : a.title;

            item.innerHTML = `
                <div class="alert-header">
                    <h3 class="alert-title">${titleHtml}</h3>
                    <span class="alert-keyword-match">${a.keyword_value}</span>
                </div>
                <div class="alert-meta">
                    <span>Source: <span class="alert-feed-name">${a.source_feed}</span></span>
                    <span>Date d'alerte: ${dateStr}</span>
                </div>
                ${a.summary ? `<div class="alert-summary">${a.summary}</div>` : ""}
            `;
            container.appendChild(item);
        });

    } catch (error) {
        console.error("Error loading alerts:", error);
        container.innerHTML = `<div class="text-center text-error pad-20">Erreur de chargement des alertes.</div>`;
    }
}

// --- CYBER COPILOT AI CHAT CONTROLLER ---
function initAICopilot() {
    const sendBtn = document.getElementById("chat-send-btn");
    const chatInput = document.getElementById("chat-user-input");

    sendBtn.addEventListener("click", () => sendChatMessage());
    chatInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendChatMessage();
    });
}

async function sendChatMessage(customMessage = null) {
    const chatInput = document.getElementById("chat-user-input");
    const container = document.getElementById("chat-messages-container");
    const suggestionsContainer = document.getElementById("chat-suggestions-container");
    const suggestionsList = document.getElementById("chat-suggestions-list");
    const sendBtn = document.getElementById("chat-send-btn");

    const messageText = customMessage || chatInput.value.trim();
    if (!messageText) return;

    if (!customMessage) {
        chatInput.value = "";
    }

    // Append User Message to UI
    appendChatMessage("user", messageText);
    scrollChatToBottom();

    // Save user message to history
    chatHistory.push({ role: "user", content: messageText });

    // Disable input while generating
    sendBtn.disabled = true;
    chatInput.disabled = true;

    // Show AI loading indicator
    const loadingMessageId = appendChatMessage("ai", "<em>Cyber Copilot est en train d'analyser la menace...</em>");
    scrollChatToBottom();

    try {
        // Detect context type automatically to assist suggestion lists
        let contextType = "general";
        if (messageText.toLowerCase().includes("leak") || messageText.toLowerCase().includes("fuite") || messageText.toLowerCase().includes("comprom")) {
            contextType = "leaks";
        } else if (messageText.toLowerCase().includes("alert") || messageText.toLowerCase().includes("cve") || messageText.toLowerCase().includes("faille")) {
            contextType = "alerts";
        }

        const response = await fetch(`${API_BASE}/api/v1/ai/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                message: messageText, 
                context_type: contextType,
                history: chatHistory.slice(0, -1) // Exclude the current message since it is sent in 'message'
            })
        });

        if (!response.ok) throw new Error();

        const data = await response.json();

        // Save AI response to history
        chatHistory.push({ role: "assistant", content: data.response });

        // Remove loading message and append actual response
        removeChatMessage(loadingMessageId);
        
        // Render Markdown-like responses (convert backticks to HTML code blocks)
        const formattedResponse = formatAIResponseText(data.response);
        appendChatMessage("ai", formattedResponse);

        // Update suggested actions chips
        if (data.suggested_actions && data.suggested_actions.length > 0) {
            suggestionsContainer.style.display = "block";
            suggestionsList.innerHTML = "";
            data.suggested_actions.forEach(action => {
                const chip = document.createElement("button");
                chip.className = "suggestion-chip";
                chip.innerText = action;
                chip.addEventListener("click", () => {
                    sendChatMessage(`Comment mettre en œuvre : "${action}" ?`);
                });
                suggestionsList.appendChild(chip);
            });
        } else {
            suggestionsContainer.style.display = "none";
        }

    } catch (error) {
        removeChatMessage(loadingMessageId);
        appendChatMessage("ai", "<span class='text-error'>Erreur: Impossible de joindre le Cyber Copilot. Vérifiez votre connexion.</span>");
        // Remove last user message from history on error to allow retry
        chatHistory.pop();
    } finally {
        sendBtn.disabled = false;
        chatInput.disabled = false;
        chatInput.focus();
        scrollChatToBottom();
    }
}

function appendChatMessage(sender, text) {
    const container = document.getElementById("chat-messages-container");
    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-message ${sender}-message`;
    
    // Unique ID to allow replacement (loading placeholders)
    const msgId = "msg-" + Date.now() + Math.random().toString(36).substr(2, 5);
    msgDiv.id = msgId;

    const label = sender === "user" ? "Vous" : "Cyber Copilot";
    msgDiv.innerHTML = `<div class="message-content"><strong>${label}</strong> : ${text}</div>`;
    
    container.appendChild(msgDiv);
    return msgId;
}

function removeChatMessage(id) {
    const msg = document.getElementById(id);
    if (msg) msg.remove();
}

function scrollChatToBottom() {
    const container = document.getElementById("chat-messages-container");
    container.scrollTop = container.scrollHeight;
}

function formatAIResponseText(text) {
    // Simple formatter replacing markdown triple backticks with HTML pre/code elements
    let formatted = text;
    
    // Replace triple backticks code blocks
    formatted = formatted.replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>");
    
    // Replace single backticks inline code
    formatted = formatted.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    
    // Replace linebreaks with <br>
    formatted = formatted.replace(/\n/g, "<br>");
    
    return formatted;
}

// --- CODE REMEDIATION CONTROLLER ---
function initRemediator() {
    const form = document.getElementById("remediation-form");
    if (!form) return;

    const copyBtn = document.getElementById("remediation-copy-btn");
    const fixedCodeEl = document.getElementById("remediation-fixed-code");

    if (copyBtn) {
        copyBtn.addEventListener("click", () => {
            navigator.clipboard.writeText(fixedCodeEl.innerText);
            const originalText = copyBtn.innerText;
            copyBtn.innerText = "Copié !";
            copyBtn.style.background = "var(--color-success)";
            copyBtn.style.color = "var(--bg-base)";
            setTimeout(() => {
                copyBtn.innerText = originalText;
                copyBtn.style.background = "";
                copyBtn.style.color = "";
            }, 2000);
        });
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const language = document.getElementById("remediation-lang").value;
        const vulnerability_description = document.getElementById("remediation-desc").value.trim();
        const code = document.getElementById("remediation-code").value.trim();
        const submitBtn = document.getElementById("remediation-submit-btn");

        const waitingDiv = document.getElementById("remediation-waiting");
        const loadingDiv = document.getElementById("remediation-loading");
        const outputDiv = document.getElementById("remediation-output");

        const explanationEl = document.getElementById("remediation-explanation");

        if (!code) return;

        // UI transitions
        waitingDiv.style.display = "none";
        outputDiv.style.display = "none";
        loadingDiv.style.display = "block";
        submitBtn.disabled = true;
        if (copyBtn) copyBtn.style.display = "none";

        try {
            const response = await fetch(`${API_BASE}/api/v1/ai/remediate`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    code,
                    language,
                    vulnerability_description: vulnerability_description || null
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Erreur de communication avec le serveur.");
            }

            const data = await response.json();

            // Display results
            explanationEl.innerHTML = formatAIResponseText(data.explanation);
            
            // Apply Prism class and display code
            fixedCodeEl.className = `language-${language} fixed-code-block`;
            fixedCodeEl.innerText = data.fixed_code;
            if (window.Prism) {
                Prism.highlightElement(fixedCodeEl);
            }

            loadingDiv.style.display = "none";
            outputDiv.style.display = "block";
            if (copyBtn) copyBtn.style.display = "inline-block";
        } catch (error) {
            console.error("Remediation error:", error);
            loadingDiv.style.display = "none";
            waitingDiv.style.display = "block";
            waitingDiv.innerHTML = `<span class="text-error">Erreur lors de l'analyse : ${error.message || "Serveur injoignable"}</span>`;
        } finally {
            submitBtn.disabled = false;
        }
    });
}


// --- DASHBOARD CONTROLLER ---
function initDashboard() {
    fetchDashboardStats();
    fetchDashboardAlerts();

    // Refresh when clicking the dashboard tab
    const dashBtn = document.querySelector('.nav-btn[data-tab="dashboard"]');
    if (dashBtn) {
        dashBtn.addEventListener("click", () => {
            fetchDashboardStats();
            fetchDashboardAlerts();
        });
    }
}

async function fetchDashboardStats() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/stats`);
        if (!response.ok) throw new Error("Impossible de récupérer les statistiques.");
        
        const data = await response.json();
        
        // Counter variables
        const totalTargets = data.targets.total;
        const totalLeaks = data.leaks_count;
        const totalAlerts = data.alerts_count;
        const totalScans = data.scans_count;
        
        const dashTotalTargetsEl = document.getElementById("dash-total-targets");
        if (dashTotalTargetsEl) animateCounter(dashTotalTargetsEl, totalTargets);
        
        const dashBreakdownEl = document.getElementById("dash-targets-breakdown");
        if (dashBreakdownEl) {
            dashBreakdownEl.innerText = `${data.targets.usernames} pseudos | ${data.targets.emails} emails | ${data.targets.domains} domaines`;
        }
            
        const dashTotalLeaksEl = document.getElementById("dash-total-leaks");
        if (dashTotalLeaksEl) animateCounter(dashTotalLeaksEl, totalLeaks);
        
        const dashTotalAlertsEl = document.getElementById("dash-total-alerts");
        if (dashTotalAlertsEl) animateCounter(dashTotalAlertsEl, totalAlerts);
        
        const dashTotalScansEl = document.getElementById("dash-total-scans");
        if (dashTotalScansEl) animateCounter(dashTotalScansEl, totalScans);

        // Populate Activity Timeline
        const timelineContainer = document.getElementById("dash-timeline");
        if (timelineContainer) {
            const timeline = data.timeline || [];
            if (timeline.length === 0) {
                timelineContainer.innerHTML = `<div class="text-center text-muted pad-20">Aucune activité récente détectée.</div>`;
            } else {
                timelineContainer.innerHTML = "";
                timeline.forEach(item => {
                    const timeStr = new Date(item.timestamp).toLocaleString("fr-FR");
                    let icon = "📝";
                    if (item.type === "alert") icon = "🚨";
                    if (item.type === "scan") icon = "🔍";

                    const row = document.createElement("div");
                    row.className = "timeline-item";
                    row.style.display = "flex";
                    row.style.justifyContent = "space-between";
                    row.style.alignItems = "center";
                    row.style.borderBottom = "1px solid rgba(255,255,255,0.03)";
                    row.style.padding = "10px 0";
                    row.style.fontSize = "0.85rem";
                    
                    row.innerHTML = `
                        <div style="display:flex; gap:10px; align-items:center;">
                            <span>${icon}</span>
                            <span style="color:var(--text-secondary);">${item.title}</span>
                        </div>
                        <span style="font-size:0.75rem; color:var(--text-muted);">${timeStr}</span>
                    `;
                    timelineContainer.appendChild(row);
                });
            }
        }
    } catch (error) {
        console.error("Dashboard stats error:", error);
    }
}

async function fetchDashboardAlerts() {
    const container = document.getElementById("dash-recent-alerts");
    if (!container) return;
    try {
        const response = await fetch(`${API_BASE}/api/v1/alerts`);
        if (!response.ok) throw new Error();
        
        const alerts = await response.json();
        
        if (alerts.length === 0) {
            container.innerHTML = `<div class="text-center text-muted pad-20">Aucune alerte récente détectée.</div>`;
            return;
        }

        // Limit to 5 alerts for the dashboard
        const recent = alerts.slice(0, 5);
        container.innerHTML = "";
        recent.forEach(a => {
            const dateStr = new Date(a.found_at).toLocaleDateString("fr-FR");
            const item = document.createElement("div");
            item.className = "alert-item compact";
            
            const titleHtml = a.url 
                ? `<a href="${a.url}" target="_blank">${a.title} &rarr;</a>` 
                : a.title;
                
            item.innerHTML = `
                <div class="alert-header" style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:5px;">
                    <span class="alert-title" style="font-size:0.85rem; font-weight:600;">${titleHtml}</span>
                    <span class="alert-keyword-match" style="font-size:0.65rem; padding: 1px 3px;">${a.keyword_value}</span>
                </div>
                <div class="alert-meta" style="font-size: 0.7rem; display:flex; gap:10px; color:var(--text-secondary);">
                    <span>Source: <span class="alert-feed-name" style="color:var(--color-warning);">${a.source_feed}</span></span>
                    <span>Date: ${dateStr}</span>
                </div>
            `;
            container.appendChild(item);
        });
    } catch (error) {
        container.innerHTML = `<div class="text-center text-error pad-20">Erreur lors de la récupération des alertes.</div>`;
    }
}

// --- FEEDS CRUD CONTROLLER ---
function initFeeds() {
    const feedForm = document.getElementById("feed-form");
    if (!feedForm) return;

    fetchFeeds();

    feedForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = document.getElementById("feed-name").value.trim();
        const url = document.getElementById("feed-url").value.trim();

        try {
            const response = await fetch(`${API_BASE}/api/v1/feeds`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, url })
            });

            if (response.ok) {
                feedForm.reset();
                fetchFeeds();
            } else {
                const err = await response.json();
                alert(`Erreur: ${err.detail || "Impossible d'ajouter le flux RSS."}`);
            }
        } catch (error) {
            console.error("Error creating feed:", error);
        }
    });
}

async function fetchFeeds() {
    const tbody = document.querySelector("#feeds-table tbody");
    if (!tbody) return;

    try {
        const response = await fetch(`${API_BASE}/api/v1/feeds`);
        if (!response.ok) throw new Error();
        
        const feeds = await response.json();
        
        if (feeds.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Aucun flux RSS configuré.</td></tr>`;
            return;
        }

        tbody.innerHTML = "";
        feeds.forEach(f => {
            const tr = document.createElement("tr");
            
            tr.innerHTML = `
                <td><strong>${f.name}</strong></td>
                <td><span style="font-size:0.8rem; color:var(--text-secondary); word-break: break-all;">${f.url}</span></td>
                <td>
                    <button class="btn btn-danger btn-sm delete-feed-btn" data-id="${f.id}">Supprimer</button>
                </td>
            `;
            
            tr.querySelector(".delete-feed-btn").addEventListener("click", () => deleteFeed(f.id));
            tbody.appendChild(tr);
        });
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-error">Erreur lors de la récupération des flux RSS.</td></tr>`;
    }
}

async function deleteFeed(id) {
    if (!confirm("Voulez-vous supprimer ce flux RSS ?")) return;
    try {
        const response = await fetch(`${API_BASE}/api/v1/feeds/${id}`, { method: "DELETE" });
        if (response.ok) {
            fetchFeeds();
        }
    } catch (error) {
        console.error("Error deleting feed:", error);
    }
}


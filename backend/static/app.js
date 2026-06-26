// API Base Configuration
const API_BASE = "";

// Global State
let activeTargetId = null;
let activeTargetValue = "";
let scanPollInterval = null;

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initTargets();
    initLeaks();
    initKeywordsAndAlerts();
    initAICopilot();
    initRemediator();
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
}

async function fetchTargets() {
    const tbody = document.querySelector("#targets-table tbody");
    try {
        const response = await fetch(`${API_BASE}/api/v1/targets`);
        if (!response.ok) throw new Error("Failed to fetch targets");
        
        const targets = await response.json();
        
        if (targets.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Aucune cible enregistrée.</td></tr>`;
            return;
        }

        tbody.innerHTML = "";
        targets.forEach(t => {
            const tr = document.createElement("tr");
            tr.style.cursor = t.type === "username" ? "pointer" : "default";
            
            // Format type badge
            const badgeClass = `badge badge-${t.type}`;
            const typeLabel = t.type === "username" ? "Pseudo" : t.type === "email" ? "Email" : "Domaine";
            
            // Formulate date
            const dateStr = new Date(t.created_at).toLocaleString("fr-FR");

            tr.innerHTML = `
                <td><strong>${t.value}</strong></td>
                <td><span class="${badgeClass}">${typeLabel}</span></td>
                <td>${dateStr}</td>
                <td>
                    ${t.type === 'username' ? `<button class="btn btn-primary btn-sm inspect-btn" data-id="${t.id}" data-val="${t.value}">Analyser</button>` : ''}
                    <button class="btn btn-danger btn-sm delete-target-btn" data-id="${t.id}">Supprimer</button>
                </td>
            `;

            // Click row to inspect username target
            if (t.type === "username") {
                tr.addEventListener("click", (e) => {
                    if (e.target.classList.contains("delete-target-btn")) return;
                    showScanPanel(t.id, t.value);
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

            tbody.appendChild(tr);
        });

    } catch (error) {
        console.error("Error listing targets:", error);
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-error">Erreur lors de la récupération des cibles.</td></tr>`;
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

function showScanPanel(targetId, targetValue) {
    activeTargetId = targetId;
    activeTargetValue = targetValue;
    
    document.getElementById("scan-results-card").style.display = "block";
    document.getElementById("results-title").innerText = `Analyse d'Alias : ${targetValue}`;
    document.getElementById("scan-target-name").innerText = `Cible active : ${targetValue}`;
    
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

function renderResultsGrid(results) {
    const grid = document.getElementById("scan-results-grid");
    grid.innerHTML = "";
    
    results.forEach(res => {
        const card = document.createElement("div");
        const statusClass = res.status.toLowerCase(); // found, notfound, error
        card.className = `result-card status-${statusClass}`;
        
        const isFound = res.status === "FOUND";
        const statusLabel = res.status === "FOUND" ? "TROUVÉ" : res.status === "NOT_FOUND" ? "ABSENT" : "ERREUR";

        card.innerHTML = `
            <div class="result-info">
                <span class="result-name">${res.platform}</span>
                ${isFound ? `<a href="${res.url}" target="_blank" class="result-link">Accéder au profil &rarr;</a>` : `<span class="text-muted" style="font-size:0.75rem;">Non détecté</span>`}
            </div>
            <span class="result-status-tag">${statusLabel}</span>
        `;
        grid.appendChild(card);
    });
}

function displayStats(results) {
    document.getElementById("scan-stats").style.display = "grid";
    
    const found = results.filter(r => r.status === "FOUND").length;
    const notfound = results.filter(r => r.status === "NOT_FOUND").length;
    const error = results.filter(r => r.status === "ERROR").length;
    
    document.getElementById("stat-found").innerText = found;
    document.getElementById("stat-notfound").innerText = notfound;
    document.getElementById("stat-error").innerText = error;
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
        const response = await fetch(`${API_BASE}/api/v1/scans/pseudo?target_id=${targetId}`, { method: "POST" });
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
            progressText.innerText = "Recherche en cours sur 100+ plateformes (5s env)...";
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
                alert(`Ingestion démarrée ! Tâche ID: ${task.task_id}\nVous pouvez suivre les logs du worker.`);
                ingestForm.reset();
            } else {
                alert("Erreur de lancement de l'ingestion.");
            }
        } catch (error) {
            console.error("Error starting ingestion:", error);
        }
    });
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
            tr.innerHTML = `
                <td>${l.username || '<span class="text-muted">-</span>'}</td>
                <td><strong>${l.email || '<span class="text-muted">-</span>'}</strong></td>
                <td><code style="font-family:var(--font-mono);font-size:0.8rem;">${l.password_hash || '-'}</code></td>
                <td><span class="badge badge-email">${l.source || 'Inconnue'}</span></td>
                <td>${l.leak_date || 'N/A'}</td>
            `;
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
            body: JSON.stringify({ message: messageText, context_type: contextType })
        });

        if (!response.ok) throw new Error();

        const data = await response.json();

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
        const fixedCodeEl = document.getElementById("remediation-fixed-code");

        if (!code) return;

        // UI transitions
        waitingDiv.style.display = "none";
        outputDiv.style.display = "none";
        loadingDiv.style.display = "block";
        submitBtn.disabled = true;

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
            
            // Clean up code block representation
            fixedCodeEl.innerText = data.fixed_code;

            loadingDiv.style.display = "none";
            outputDiv.style.display = "block";
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


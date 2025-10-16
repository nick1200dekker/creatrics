// TikTok Competitors Management
let nicheLists = [];
let currentListId = null;
let competitors = [];
let selectedTimeframe = '30';
let isAnalyzing = false;
let searchResults = [];
let isSearching = false;
let allVideos = [];
let videosDisplayed = 25;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadNicheLists();
    loadLatestAnalysisCard();
});

// Load niche lists
async function loadNicheLists() {
    const container = document.getElementById('nicheLists');
    
    container.classList.add('loading');
    container.innerHTML = `
        <div class="sidebar-loading">
            <i class="ph ph-spinner spin"></i>
            <span>Loading lists...</span>
        </div>
    `;
    
    try {
        const response = await fetch('/tiktok/competitors/api/lists');
        const data = await response.json();

        if (data.success) {
            nicheLists = data.lists || [];
            container.classList.remove('loading');
            renderNicheLists();

            if (nicheLists.length > 0 && !currentListId) {
                await selectList(nicheLists[0].id);
            }
        }
    } catch (error) {
        console.error('Error loading niche lists:', error);
        container.classList.remove('loading');
        container.innerHTML = `
            <div class="empty-lists">
                <p class="empty-lists-text">Failed to load lists</p>
            </div>
        `;
    }
}

// Render niche lists sidebar
function renderNicheLists() {
    const container = document.getElementById('nicheLists');

    if (nicheLists.length === 0) {
        container.innerHTML = `
            <div class="empty-lists">
                <p class="empty-lists-text">No lists yet. Create one to get started!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = nicheLists.map((list, index) => `
        <div class="list-item ${currentListId === list.id ? 'active' : ''}" onclick="selectList('${list.id}')" style="animation-delay: ${index * 0.05}s">
            <div class="list-info">
                <div class="list-name">${escapeHtml(list.name)}</div>
                <div class="list-count">${list.account_count || 0} accounts</div>
            </div>
            <button class="list-delete-btn" onclick="event.stopPropagation(); deleteList('${list.id}')" title="Delete list">
                <i class="ph ph-trash"></i>
            </button>
        </div>
    `).join('');
}

// Select a list
async function selectList(listId) {
    currentListId = listId;
    renderNicheLists();

    const selectedList = nicheLists.find(l => l.id === listId);
    if (selectedList) {
        document.getElementById('currentListName').textContent = selectedList.name;
    }

    document.getElementById('setupBody').style.display = 'block';
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('viewToggle').style.display = 'block';

    switchView('list');
    await loadCompetitors();
}

// Load saved competitors
async function loadCompetitors() {
    if (!currentListId) return;

    const competitorsList = document.getElementById('competitorsList');
    
    competitorsList.classList.add('loading');
    competitorsList.innerHTML = `
        <div class="list-loading">
            <i class="ph ph-spinner spin"></i>
            <span>Loading accounts...</span>
        </div>
    `;

    try {
        const response = await fetch(`/tiktok/competitors/api/list?list_id=${currentListId}`);
        const data = await response.json();

        if (data.success) {
            competitors = data.competitors || [];
            competitorsList.classList.remove('loading');
            renderCompetitorsList();

            if (competitors.length > 0) {
                document.getElementById('analysisOptions').style.display = 'block';
            } else {
                document.getElementById('analysisOptions').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading competitors:', error);
        competitorsList.classList.remove('loading');
        competitorsList.innerHTML = `
            <div class="empty-state">
                <i class="ph ph-users-three empty-icon"></i>
                <p class="empty-text">Failed to load accounts</p>
            </div>
        `;
    }
}

// Show create list modal
function showCreateListModal() {
    document.getElementById('createListModal').style.display = 'flex';
    document.getElementById('listNameInput').value = '';
    setTimeout(() => {
        document.getElementById('listNameInput').focus();
    }, 100);
}

// Hide create list modal
function hideCreateListModal() {
    document.getElementById('createListModal').style.display = 'none';
}

// Create new list
async function createList() {
    const input = document.getElementById('listNameInput');
    const name = input.value.trim();

    if (!name) return;

    try {
        const response = await fetch('/tiktok/competitors/api/lists', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name })
        });

        const data = await response.json();

        if (data.success) {
            nicheLists.push(data.list);
            renderNicheLists();
            selectList(data.list.id);
            hideCreateListModal();
        }
    } catch (error) {
        console.error('Error creating list:', error);
    }
}

// Delete list
async function deleteList(listId) {
    const list = nicheLists.find(l => l.id === listId);
    if (!list) return;

    if (!confirm(`Delete "${list.name}" and all its accounts?`)) return;

    try {
        const response = await fetch(`/tiktok/competitors/api/lists/${listId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            nicheLists = nicheLists.filter(l => l.id !== listId);
            renderNicheLists();

            if (currentListId === listId) {
                currentListId = null;
                competitors = [];
                document.getElementById('setupBody').style.display = 'none';
                document.getElementById('emptyState').style.display = 'block';
                document.getElementById('viewToggle').style.display = 'none';

                if (nicheLists.length > 0) {
                    selectList(nicheLists[0].id);
                }
            }
        }
    } catch (error) {
        console.error('Error deleting list:', error);
    }
}

// Add competitor
async function addCompetitor() {
    if (!currentListId) return;

    const input = document.getElementById('accountUrlInput');
    const url = input.value.trim();

    if (!url) return;

    if (!url.includes('tiktok.com/') && !url.startsWith('@')) return;

    if (competitors.length >= 15) return;

    const addBtn = document.querySelector('.add-btn');
    const originalText = addBtn.innerHTML;
    addBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Adding...';
    addBtn.disabled = true;

    try {
        const response = await fetch('/tiktok/competitors/api/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                account_url: url,
                list_id: currentListId
            })
        });

        const data = await response.json();

        if (data.success) {
            competitors.push(data.account);
            input.value = '';

            const currentList = nicheLists.find(l => l.id === currentListId);
            if (currentList) {
                currentList.account_count = (currentList.account_count || 0) + 1;
                renderNicheLists();
            }

            switchView('list');
        }
    } catch (error) {
        console.error('Error adding competitor:', error);
    } finally {
        addBtn.innerHTML = originalText;
        addBtn.disabled = false;
    }
}

// Render competitors list
function renderCompetitorsList() {
    const container = document.getElementById('competitorsList');

    if (competitors.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="ph ph-users-three empty-icon"></i>
                <p class="empty-text">No competitors added yet. Add 10-15 accounts from your niche to get started.</p>
            </div>
        `;
        document.getElementById('analysisOptions').style.display = 'none';
        return;
    }

    container.innerHTML = `
        <div class="competitors-header-row">
            <span class="competitors-count">${competitors.length} ${competitors.length === 1 ? 'Account' : 'Accounts'}</span>
            ${competitors.length >= 10 ? '<span class="ready-badge">Ready to Analyze</span>' : ''}
        </div>
        <div class="competitors-grid">
            ${competitors.map(comp => {
                const avatarHTML = comp.avatar ?
                    `<img src="${comp.avatar}" alt="${escapeHtml(comp.nickname || 'Account')}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><div class="avatar-placeholder" style="display:none;">${(comp.nickname || '?')[0].toUpperCase()}</div>` :
                    `<div class="avatar-placeholder">${(comp.nickname || '?')[0].toUpperCase()}</div>`;

                return `
                    <div class="competitor-card">
                        <div class="competitor-avatar">
                            ${avatarHTML}
                        </div>
                        <div class="competitor-info">
                            <div class="competitor-title">${escapeHtml(comp.nickname || 'Unknown Account')}</div>
                            <div class="competitor-stats">
                                <span class="stat">
                                    <i class="ph ph-users"></i>
                                    ${formatTikTokCount(comp.follower_count)}
                                </span>
                            </div>
                        </div>
                        <button class="remove-btn" onclick="removeCompetitor('${comp.id}')" title="Remove">
                            <i class="ph ph-x"></i>
                        </button>
                    </div>
                `;
            }).join('')}
        </div>
    `;

    if (competitors.length > 0) {
        document.getElementById('analysisOptions').style.display = 'block';
    }
}

// Remove competitor
async function removeCompetitor(docId) {
    if (!confirm('Remove this competitor?')) return;
    if (!currentListId) return;

    try {
        const response = await fetch(`/tiktok/competitors/api/remove/${currentListId}/${docId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            competitors = competitors.filter(c => c.id !== docId);
            renderCompetitorsList();

            const currentList = nicheLists.find(l => l.id === currentListId);
            if (currentList) {
                currentList.account_count = Math.max(0, (currentList.account_count || 1) - 1);
                renderNicheLists();
            }

            if (competitors.length === 0) {
                document.getElementById('analysisOptions').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error removing competitor:', error);
    }
}

// Set timeframe
function setTimeframe(days) {
    selectedTimeframe = days;
    
    document.querySelectorAll('.timeframe-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-days') === days) {
            btn.classList.add('active');
        }
    });
}

// Analyze competitors
async function analyzeCompetitors() {
    if (isAnalyzing) return;
    if (!currentListId || competitors.length === 0) return;

    isAnalyzing = true;

    document.getElementById('setupSection').style.display = 'none';
    document.getElementById('progressSection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';

    updateProgress(0, 'Starting analysis...');

    try {
        updateProgress(20, 'Fetching videos from competitors...');

        const response = await fetch('/tiktok/competitors/api/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                timeframe: selectedTimeframe,
                list_id: currentListId,
                list_name: getListName(currentListId)
            })
        });

        updateProgress(60, 'Analyzing content patterns...');

        const data = await response.json();

        updateProgress(80, 'Generating insights...');

        if (data.success) {
            updateProgress(100, 'Analysis complete!');

            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('resultsSection').style.display = 'block';

            displayResults(data.data);

            setTimeout(() => {
                document.getElementById('resultsSection').scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }, 100);
        } else {
            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('setupSection').style.display = 'block';
        }
    } catch (error) {
        console.error('Error analyzing competitors:', error);
        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('setupSection').style.display = 'block';
    } finally {
        isAnalyzing = false;
    }
}

// Update progress bar
function updateProgress(percent, message) {
    const progressBar = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress-text');
    const progressPercent = document.querySelector('.progress-percent');
    
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressText) progressText.textContent = message;
    if (progressPercent) progressPercent.textContent = `${percent}%`;
}

// Back to setup
function backToSetup() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('setupSection').style.display = 'flex';
    document.getElementById('setupBody').style.display = 'block';
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('viewToggle').style.display = 'block';

    const mainHeader = document.querySelector('.competitors-header .header-content');
    if (mainHeader) {
        const backBtn = mainHeader.querySelector('.back-btn');
        if (backBtn) backBtn.remove();
    }

    renderCompetitorsList();

    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Display results
function displayResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const { videos, patterns, insights, timeframe_days } = data;

    allVideos = videos || [];
    videosDisplayed = 25;

    const timeframeText = timeframe_days === 1 ? '24 hours' :
                         timeframe_days === 2 ? '48 hours' :
                         `${timeframe_days} days`;

    const mainHeader = document.querySelector('.competitors-header .header-content');
    if (mainHeader) {
        const existingBackBtn = mainHeader.querySelector('.back-btn');
        if (existingBackBtn) existingBackBtn.remove();

        const backBtn = document.createElement('button');
        backBtn.className = 'back-btn header-back-btn';
        backBtn.onclick = backToSetup;
        backBtn.innerHTML = '<i class="ph ph-arrow-left"></i> Back to Setup';
        mainHeader.appendChild(backBtn);
    }

    let html = `
        <!-- Quick Stats Grid -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-video-camera"></i></div>
                <div class="stat-value">${patterns.total_videos_analyzed || 0}</div>
                <div class="stat-label">Videos Analyzed</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-eye"></i></div>
                <div class="stat-value">${formatNumber(patterns.avg_views || 0)}</div>
                <div class="stat-label">Avg Views</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-heart"></i></div>
                <div class="stat-value">${formatNumber(patterns.avg_likes || 0)}</div>
                <div class="stat-label">Avg Likes</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-users-three"></i></div>
                <div class="stat-value">${patterns.total_accounts || 0}</div>
                <div class="stat-label">Accounts</div>
            </div>
        </div>

        <!-- Results Header -->
        <div class="results-header">
            <h2 class="results-title">
                <i class="ph ph-chart-line"></i>
                Analysis Results
            </h2>
            <span class="timeframe-badge">Last ${timeframeText}</span>
        </div>
    `;

    html += generateInsightsSection(insights);
    html += generateContentOpportunitiesSection(insights);
    html += renderAccountActivity(patterns.account_performance, timeframeText);

    html += `
        <div class="videos-card" id="videosCard">
            <h3 class="section-title">
                <i class="ph ph-play-circle"></i>
                Top Performing Videos
            </h3>
            <div class="videos-table">
                <table>
                    <thead>
                        <tr>
                            <th>Video</th>
                            <th>Account</th>
                            <th>Views</th>
                            <th>Likes</th>
                            <th>Comments</th>
                        </tr>
                    </thead>
                    <tbody id="videosTableBody">
                    </tbody>
                </table>
            </div>
        </div>
        <div class="load-more-container" id="loadMoreContainer" style="display: none;">
            <button class="load-more-btn" onclick="loadMoreVideos()">
                <i class="ph ph-arrow-down"></i>
                Load More Videos
            </button>
        </div>
    `;

    resultsSection.innerHTML = html;
    renderVideos();
}

// Generate insights section
function generateInsightsSection(insights) {
    if (!insights || !insights.summary) return '';

    let html = `
        <div class="insights-card">
            <h3 class="section-title">
                <i class="ph ph-lightbulb"></i>
                Key Insights
            </h3>
            <div class="insights-content">
    `;

    const sections = insights.summary.split(/(?=##\s)/);

    sections.forEach(section => {
        if (section.includes('## Content Opportunities')) return;

        const lines = section.split('\n').filter(line => line.trim());

        lines.forEach(line => {
            const trimmed = line.trim();

            if (trimmed.startsWith('##')) {
                const headerText = trimmed.replace(/^##\s*/, '');
                html += `<h4 class="insight-section-header">${formatMarkdown(escapeHtml(headerText))}</h4>`;
            } else if (trimmed.startsWith('**') && trimmed.includes(':')) {
                html += `<p class="insight-item">${formatMarkdown(escapeHtml(trimmed))}</p>`;
            } else if (trimmed.startsWith('-') || trimmed.startsWith('•')) {
                const bulletText = trimmed.replace(/^[-•]\s*/, '');
                html += `<p class="insight-bullet">• ${formatMarkdown(escapeHtml(bulletText))}</p>`;
            } else if (trimmed) {
                html += `<p class="insight-text">${formatMarkdown(escapeHtml(trimmed))}</p>`;
            }
        });
    });

    html += `
            </div>
        </div>
    `;

    return html;
}

// Generate content opportunities section
function generateContentOpportunitiesSection(insights) {
    if (!insights || !insights.quick_wins || insights.quick_wins.length === 0) {
        return '';
    }

    let html = `
        <div class="quick-wins-card">
            <h3 class="section-title">
                <i class="ph ph-rocket-launch"></i>
                Content Opportunities
            </h3>
            <div class="content-ideas-grid">
                ${insights.quick_wins.map(win => `
                    <div class="content-idea-chip">
                        "${escapeHtml(win.title)}"
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    return html;
}

// Render account activity
function renderAccountActivity(accountPerformance, timeframeText) {
    if (!accountPerformance || Object.keys(accountPerformance).length === 0) return '';

    const accounts = Object.entries(accountPerformance)
        .map(([name, stats]) => ({
            name,
            videoCount: stats.video_count || 0,
            avgViews: stats.avg_views || 0
        }))
        .sort((a, b) => b.videoCount - a.videoCount);

    const maxCount = Math.max(...accounts.map(c => c.videoCount));

    let accountBars = '';
    accounts.forEach(account => {
        const percentage = maxCount > 0 ? (account.videoCount / maxCount) * 100 : 0;
        const intensity = maxCount > 0 ? account.videoCount / maxCount : 0;
        const colorIntensity = Math.max(0.3, intensity);

        accountBars += `
            <div class="day-bar-row">
                <div class="day-bar-label">${escapeHtml(account.name)}</div>
                <div class="day-bar-container">
                    <div class="day-bar-fill"
                         style="width: ${percentage}%; opacity: ${colorIntensity}"
                         title="${account.videoCount} video${account.videoCount !== 1 ? 's' : ''} posted">
                    </div>
                    <span class="day-bar-count">${account.videoCount}</span>
                </div>
            </div>
        `;
    });

    const totalVideos = accounts.reduce((sum, c) => sum + c.videoCount, 0);

    return `
        <div class="heatmap-card">
            <h3 class="section-title">
                <i class="ph ph-chart-bar"></i>
                Account Activity
            </h3>
            <p class="heatmap-description">${totalVideos} video${totalVideos !== 1 ? 's' : ''} posted across ${accounts.length} account${accounts.length !== 1 ? 's' : ''} in ${timeframeText}</p>
            <div class="day-bars-container">
                ${accountBars}
            </div>
        </div>
    `;
}

// Render videos table
function renderVideos() {
    const tbody = document.getElementById('videosTableBody');
    const loadMoreContainer = document.getElementById('loadMoreContainer');

    if (!tbody) return;

    const videosToShow = allVideos.slice(0, videosDisplayed);

    tbody.innerHTML = videosToShow.map(video => {
        const views = video.view_count || 0;
        const likes = video.like_count || 0;
        const comments = video.comment_count || 0;

        return `
            <tr onclick="window.open('${video.video_url}', '_blank')" style="cursor: pointer;">
                <td class="video-cell">
                    <div class="video-thumbnail-small">
                        ${video.cover ?
                            `<img src="${video.cover}" alt="${escapeHtml(video.desc)}" loading="lazy">` :
                            '<div class="thumbnail-placeholder-small"><i class="ph ph-video-camera"></i></div>'
                        }
                    </div>
                    <div class="video-title-cell">
                        ${escapeHtml(video.desc || 'No description')}
                    </div>
                </td>
                <td class="channel-cell">${escapeHtml(video.account_nickname)}</td>
                <td class="views-cell">${formatNumber(views)}</td>
                <td class="likes-cell">${formatNumber(likes)}</td>
                <td class="comments-cell">${formatNumber(comments)}</td>
            </tr>
        `;
    }).join('');

    if (loadMoreContainer) {
        if (videosDisplayed < allVideos.length && videosDisplayed < 250) {
            loadMoreContainer.style.display = 'flex';
        } else {
            loadMoreContainer.style.display = 'none';
        }
    }
}

// Load more videos
function loadMoreVideos() {
    videosDisplayed = Math.min(videosDisplayed + 25, 250, allVideos.length);
    renderVideos();
}

// View switching
function switchView(view) {
    const listViewBtn = document.getElementById('listViewBtn');
    const urlViewBtn = document.getElementById('urlViewBtn');
    const exploreViewBtn = document.getElementById('exploreViewBtn');

    const listView = document.getElementById('listView');
    const urlView = document.getElementById('urlView');
    const exploreView = document.getElementById('exploreView');

    listViewBtn.classList.remove('active');
    urlViewBtn.classList.remove('active');
    exploreViewBtn.classList.remove('active');

    listView.style.display = 'none';
    urlView.style.display = 'none';
    exploreView.style.display = 'none';

    if (view === 'list') {
        listViewBtn.classList.add('active');
        listView.style.display = 'block';
    } else if (view === 'url') {
        urlViewBtn.classList.add('active');
        urlView.style.display = 'block';
    } else if (view === 'explore') {
        exploreViewBtn.classList.add('active');
        exploreView.style.display = 'block';
    }
}

// Search for accounts
async function searchAccounts() {
    if (isSearching) return;

    const input = document.getElementById('searchInput');
    const query = input.value.trim();

    if (!query) return;

    isSearching = true;

    const searchBtn = document.querySelector('.search-btn');
    const originalText = searchBtn.innerHTML;
    searchBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Searching...';
    searchBtn.disabled = true;

    try {
        const response = await fetch(`/tiktok/competitors/api/search?query=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.success) {
            searchResults = data.accounts || [];
            renderSearchResults();
        }
    } catch (error) {
        console.error('Error searching accounts:', error);
    } finally {
        searchBtn.innerHTML = originalText;
        searchBtn.disabled = false;
        isSearching = false;
    }
}

// Render search results
function renderSearchResults() {
    const searchResultsDiv = document.getElementById('searchResults');
    const searchEmptyState = document.getElementById('searchEmptyState');
    const resultsCount = document.getElementById('resultsCount');
    const searchResultsGrid = document.getElementById('searchResultsGrid');

    if (searchResults.length === 0) {
        searchResultsDiv.style.display = 'none';
        searchEmptyState.style.display = 'block';
        searchEmptyState.innerHTML = `
            <i class="ph ph-magnifying-glass-minus empty-icon"></i>
            <p class="empty-text">No accounts found. Try a different search query.</p>
        `;
        return;
    }

    searchEmptyState.style.display = 'none';
    searchResultsDiv.style.display = 'block';

    const existingSecUids = new Set(competitors.map(c => c.sec_uid));
    const availableResults = searchResults.filter(r => !existingSecUids.has(r.sec_uid));

    availableResults.sort((a, b) => (b.follower_count || 0) - (a.follower_count || 0));

    resultsCount.textContent = `Found ${availableResults.length} accounts`;

    searchResultsGrid.innerHTML = availableResults.map(account => {
        const avatarHTML = account.avatar ?
            `<img src="${account.avatar}" alt="${escapeHtml(account.nickname || 'Account')}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><div class="avatar-placeholder" style="display:none;">${(account.nickname || '?')[0].toUpperCase()}</div>` :
            `<div class="avatar-placeholder">${(account.nickname || '?')[0].toUpperCase()}</div>`;

        const tiktokUrl = `https://www.tiktok.com/@${account.username}`;

        return `
            <div class="search-result-card">
                <div class="search-result-clickable" onclick="window.open('${tiktokUrl}', '_blank')">
                    <div class="competitor-avatar">
                        ${avatarHTML}
                    </div>
                    <div class="competitor-info">
                        <div class="competitor-title">${escapeHtml(account.nickname || 'Unknown Account')}</div>
                        ${account.username ? `<div class="channel-handle">@${escapeHtml(account.username)}</div>` : ''}
                        <div class="competitor-stats">
                            <span class="stat">
                                <i class="ph ph-users"></i>
                                ${formatTikTokCount(account.follower_count)}
                            </span>
                        </div>
                    </div>
                </div>
                <button class="add-result-btn" onclick='event.stopPropagation(); addAccountFromSearch(${JSON.stringify(account).replace(/'/g, "&#39;").replace(/"/g, "&quot;")})' ${competitors.length >= 15 ? 'disabled' : ''}>
                    <i class="ph ph-plus"></i>
                    Add
                </button>
            </div>
        `;
    }).join('');

    if (availableResults.length === 0) {
        searchResultsGrid.innerHTML = `
            <div class="empty-state">
                <i class="ph ph-check-circle empty-icon"></i>
                <p class="empty-text">All found accounts have already been added to this list.</p>
            </div>
        `;
    }
}

// Add account from search results
async function addAccountFromSearch(accountData) {
    if (!currentListId || competitors.length >= 15) return;

    try {
        const response = await fetch('/tiktok/competitors/api/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                list_id: currentListId,
                account_data: accountData
            })
        });

        const data = await response.json();

        if (data.success) {
            competitors.push(data.account);

            const currentList = nicheLists.find(l => l.id === currentListId);
            if (currentList) {
                currentList.account_count = (currentList.account_count || 0) + 1;
                renderNicheLists();
            }

            renderCompetitorsList();
            renderSearchResults();
        }
    } catch (error) {
        console.error('Error adding account from search:', error);
    }
}

// Latest Analysis Functions
async function loadLatestAnalysisCard() {
    try {
        const response = await fetch('/tiktok/competitors/api/latest-analysis');
        const data = await response.json();

        if (data.success && data.has_analysis) {
            const analysis = data.analysis;
            const section = document.getElementById('latestAnalysisSection');
            const listName = document.getElementById('latestAnalysisListName');
            const accountCount = document.getElementById('latestAnalysisAccountCount');
            const timeframe = document.getElementById('latestAnalysisTimeframe');
            const date = document.getElementById('latestAnalysisDate');

            const createdDate = new Date(analysis.created_at);
            const now = new Date();
            const diffMs = now - createdDate;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            let dateStr;
            if (diffMins < 60) {
                dateStr = `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
            } else if (diffHours < 24) {
                dateStr = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
            } else if (diffDays < 7) {
                dateStr = `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
            } else {
                dateStr = createdDate.toLocaleDateString();
            }

            listName.textContent = analysis.list_name;
            accountCount.textContent = analysis.account_count;
            timeframe.textContent = analysis.timeframe;
            date.textContent = dateStr;

            section.style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading latest analysis:', error);
    }
}

async function loadLatestAnalysis() {
    try {
        const setupSection = document.getElementById('setupSection');
        const progressSection = document.getElementById('progressSection');
        const resultsSection = document.getElementById('resultsSection');

        if (setupSection) setupSection.style.display = 'none';
        if (progressSection) {
            progressSection.style.display = 'block';
            const progressText = progressSection.querySelector('.progress-text');
            const progressPercent = progressSection.querySelector('.progress-percent');
            if (progressText) progressText.textContent = 'Loading analysis...';
            if (progressPercent) progressPercent.textContent = '';
        }
        if (resultsSection) resultsSection.style.display = 'none';

        const response = await fetch('/tiktok/competitors/api/latest-analysis');
        const data = await response.json();

        if (data.success && data.has_analysis) {
            const analysis = data.analysis;

            if (progressSection) progressSection.style.display = 'none';
            if (resultsSection) resultsSection.style.display = 'block';

            displayResults(analysis.insights);

            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } else {
            alert('No saved analysis found.');
        }
    } catch (error) {
        console.error('Error loading latest analysis:', error);
        alert('Failed to load analysis: ' + error.message);
    }
}

// Utility functions
function formatMarkdown(text) {
    if (!text) return '';
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
    return text;
}

function formatNumber(num) {
    if (!num && num !== 0) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function formatTikTokCount(count) {
    if (count >= 1000000) {
        return `${(count / 1000000).toFixed(1)}M`;
    } else if (count >= 1000) {
        return `${(count / 1000).toFixed(1)}K`;
    } else {
        return count.toString();
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.toString().replace(/[&<>"']/g, m => map[m]);
}

function getListName(listId) {
    const list = nicheLists.find(l => l.id === listId);
    return list ? list.name : 'Unknown';
}
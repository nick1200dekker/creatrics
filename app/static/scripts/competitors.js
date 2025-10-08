// Competitors Management
let nicheLists = [];
let currentListId = null;
let competitors = [];
let selectedTimeframe = '30';
let isAnalyzing = false;
let searchResults = [];
let isSearching = false;
let allVideos = [];
let videosDisplayed = 25;
let currentTimeframeDays = 30; // Store the timeframe used in analysis

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadNicheLists();
    loadLatestAnalysisCard();
});

// Load niche lists
async function loadNicheLists() {
    try {
        const response = await fetch('/api/competitors/lists');
        const data = await response.json();

        console.log('Niche lists response:', data);

        if (data.success) {
            nicheLists = data.lists || [];
            console.log('Loaded niche lists:', nicheLists);
            renderNicheLists();

            // Auto-select first list if exists
            if (nicheLists.length > 0 && !currentListId) {
                console.log('Auto-selecting first list:', nicheLists[0].id);
                await selectList(nicheLists[0].id);
            }
        }
    } catch (error) {
        console.error('Error loading niche lists:', error);
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

    container.innerHTML = nicheLists.map(list => `
        <div class="list-item ${currentListId === list.id ? 'active' : ''}" onclick="selectList('${list.id}')">
            <div class="list-info">
                <div class="list-name">${escapeHtml(list.name)}</div>
                <div class="list-count">${list.channel_count || 0} channels</div>
            </div>
            <button class="list-delete-btn" onclick="event.stopPropagation(); deleteList('${list.id}')" title="Delete list">
                <i class="ph ph-trash"></i>
            </button>
        </div>
    `).join('');
}

// Select a list
async function selectList(listId) {
    console.log('selectList called with:', listId);
    currentListId = listId;
    renderNicheLists();

    const selectedList = nicheLists.find(l => l.id === listId);
    console.log('Selected list:', selectedList);
    if (selectedList) {
        document.getElementById('currentListName').textContent = selectedList.name;
    }

    // Show the setup body and view toggle
    console.log('Showing setupBody, hiding emptyState');
    document.getElementById('setupBody').style.display = 'block';
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('viewToggle').style.display = 'block';

    // Default to list view
    switchView('list');

    // Load competitors for this list
    await loadCompetitors();
}

// Load saved competitors
async function loadCompetitors() {
    if (!currentListId) {
        console.log('No currentListId, skipping loadCompetitors');
        return;
    }

    console.log('Loading competitors for list:', currentListId);

    try {
        const response = await fetch(`/api/competitors/list?list_id=${currentListId}`);
        const data = await response.json();

        console.log('Competitors response:', data);

        if (data.success) {
            competitors = data.competitors || [];
            console.log('Loaded competitors:', competitors.length);
            renderCompetitorsList();

            // Show analysis options if we have competitors
            if (competitors.length > 0) {
                console.log('Showing analysis options');
                document.getElementById('analysisOptions').style.display = 'block';
            } else {
                console.log('Hiding analysis options');
                document.getElementById('analysisOptions').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading competitors:', error);
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

    if (!name) {
        return;
    }

    try {
        const response = await fetch('/api/competitors/lists', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
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

    if (!confirm(`Delete "${list.name}" and all its channels?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/competitors/lists/${listId}`, {
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
    if (!currentListId) {
        return;
    }

    const input = document.getElementById('channelUrlInput');
    const url = input.value.trim();

    if (!url) {
        return;
    }

    // Validate URL format
    if (!url.includes('youtube.com/') && !url.includes('youtu.be/') && !url.startsWith('@')) {
        return;
    }

    // Check if we already have 15 competitors
    if (competitors.length >= 15) {
        return;
    }

    // Show loading
    const addBtn = document.querySelector('.add-btn');
    const originalText = addBtn.innerHTML;
    addBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Adding...';
    addBtn.disabled = true;

    try {
        const response = await fetch('/api/competitors/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                channel_url: url,
                list_id: currentListId
            })
        });

        const data = await response.json();

        if (data.success) {
            competitors.push(data.channel);
            input.value = '';

            // Update list count
            const currentList = nicheLists.find(l => l.id === currentListId);
            if (currentList) {
                currentList.channel_count = (currentList.channel_count || 0) + 1;
                renderNicheLists();
            }

            // Switch to list view to show the added channel
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
                <p class="empty-text">No competitors added yet. Add 10-15 channels from your niche to get started.</p>
            </div>
        `;
        document.getElementById('analysisOptions').style.display = 'none';
        return;
    }

    container.innerHTML = `
        <div class="competitors-header-row">
            <span class="competitors-count">${competitors.length} ${competitors.length === 1 ? 'Channel' : 'Channels'}</span>
            ${competitors.length >= 10 ? '<span class="ready-badge">Ready to Analyze</span>' : ''}
        </div>
        <div class="competitors-grid">
            ${competitors.map(comp => {
                const avatarHTML = comp.avatar ?
                    `<img src="${comp.avatar}" alt="${escapeHtml(comp.title || 'Channel')}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><div class="avatar-placeholder" style="display:none;">${(comp.title || '?')[0].toUpperCase()}</div>` :
                    `<div class="avatar-placeholder">${(comp.title || '?')[0].toUpperCase()}</div>`;

                return `
                    <div class="competitor-card">
                        <div class="competitor-avatar">
                            ${avatarHTML}
                        </div>
                        <div class="competitor-info">
                            <div class="competitor-title">${escapeHtml(comp.title || 'Unknown Channel')}</div>
                            <div class="competitor-stats">
                                <span class="stat">
                                    <i class="ph ph-users"></i>
                                    ${comp.subscriber_count_text || '0'}
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

    // Show analysis options if we have competitors
    if (competitors.length > 0) {
        document.getElementById('analysisOptions').style.display = 'block';
    }
}

// Remove competitor
async function removeCompetitor(docId) {
    if (!confirm('Remove this competitor?')) {
        return;
    }

    if (!currentListId) {
        console.error('No currentListId set');
        return;
    }

    try {
        const response = await fetch(`/api/competitors/remove/${currentListId}/${docId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            competitors = competitors.filter(c => c.id !== docId);
            renderCompetitorsList();

            // Update list count
            const currentList = nicheLists.find(l => l.id === currentListId);
            if (currentList) {
                currentList.channel_count = Math.max(0, (currentList.channel_count || 1) - 1);
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

// Analyze competitors with new flow
async function analyzeCompetitors() {
    if (isAnalyzing) return;

    if (!currentListId) {
        return;
    }

    if (competitors.length === 0) {
        return;
    }

    isAnalyzing = true;

    // Hide setup section and show progress
    document.getElementById('setupSection').style.display = 'none';
    document.getElementById('progressSection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'none';

    // Reset progress
    updateProgress(0, 'Starting analysis...');

    try {
        // Simulate progress updates
        updateProgress(20, 'Fetching videos from competitors...');

        const response = await fetch('/api/competitors/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
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

            // Show results after a brief delay
            setTimeout(() => {
                displayResults(data.data);
                document.getElementById('progressSection').style.display = 'none';
                document.getElementById('resultsSection').style.display = 'block';

                // Scroll to results
                setTimeout(() => {
                    document.getElementById('resultsSection').scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }, 100);
            }, 500);
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
    document.getElementById('setupSection').style.display = 'block';

    // Remove back button from header
    const mainHeader = document.querySelector('.competitors-header .header-content');
    if (mainHeader) {
        const backBtn = mainHeader.querySelector('.back-btn');
        if (backBtn) backBtn.remove();
    }

    // Scroll to the top of the page
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Format markdown-style text
function formatMarkdown(text) {
    if (!text) return '';
    
    // Convert **bold** to <strong>
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Convert *italic* to <em>
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
    
    return text;
}

// Display results with improved formatting
function displayResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const { videos, patterns, insights, timeframe_days } = data;

    // Store all videos globally and timeframe
    allVideos = videos || [];
    videosDisplayed = 25;
    currentTimeframeDays = timeframe_days || 30;

    const timeframeText = timeframe_days === 1 ? '24 hours' :
                         timeframe_days === 2 ? '48 hours' :
                         `${timeframe_days} days`;
    
    // Build HTML with back button and stats grid first
    // Add Back button to main header
    const mainHeader = document.querySelector('.competitors-header .header-content');
    if (mainHeader) {
        // Remove existing back button if present
        const existingBackBtn = mainHeader.querySelector('.back-btn');
        if (existingBackBtn) existingBackBtn.remove();

        // Add back button
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
                <div class="stat-icon"><i class="ph ph-fire"></i></div>
                <div class="stat-value">${formatNumber(patterns.total_views || 0)}</div>
                <div class="stat-label">Total Views</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-users-three"></i></div>
                <div class="stat-value">${patterns.total_channels || 0}</div>
                <div class="stat-label">Channels</div>
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
    
    // Key Insights with clean formatting
    if (insights && insights.summary) {
        html += `
            <div class="insights-card">
                <h3 class="section-title">
                    <i class="ph ph-lightbulb"></i>
                    Key Insights
                </h3>
                <div class="insights-content">
        `;
        
        // Parse and format the markdown content, but exclude Content Opportunities section
        const sections = insights.summary.split(/(?=##\s)/);

        sections.forEach(section => {
            // Skip Content Opportunities section (it has its own styled cards)
            if (section.includes('## Content Opportunities')) {
                return;
            }

            const lines = section.split('\n').filter(line => line.trim());

            lines.forEach(line => {
                const trimmed = line.trim();

                if (trimmed.startsWith('##')) {
                    const headerText = trimmed.replace(/^##\s*/, '');
                    html += `<h4 class="insight-section-header">${formatMarkdown(escapeHtml(headerText))}</h4>`;
                } else if (trimmed.startsWith('**') && trimmed.includes(':')) {
                    // Bold label with content
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
    }
    
    // Content Opportunities (Just Titles)
    if (insights.quick_wins && insights.quick_wins.length > 0) {
        html += `
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
    }

    // Publishing Heatmap
    if (patterns.publish_heatmap && patterns.publish_heatmap.data && patterns.publish_heatmap.data.length > 0) {
        html += renderPublishHeatmap(patterns.publish_heatmap);
    }

    // Top Videos/Shorts as Table
    if (videos && videos.length > 0) {
        html += `
            <div class="videos-card" id="videosCard">
                <div class="section-header-with-toggle">
                    <h3 class="section-title">
                        <i class="ph ph-play-circle"></i>
                        <span id="contentTypeLabel">Top Performing Videos</span>
                    </h3>
                </div>
                <div class="videos-table">
                    <table>
                        <thead>
                            <tr>
                                <th><span id="contentTypeTableLabel">Video</span></th>
                                <th>Channel</th>
                                <th>Views</th>
                                <th>Published</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="videosTableBody">
                        </tbody>
                    </table>
                </div>
                <div class="load-more-container" id="loadMoreContainer" style="display: none;">
                    <button class="load-more-btn" onclick="loadMoreVideos()">
                        <i class="ph ph-arrow-down"></i>
                        <span id="loadMoreLabel">Load More Videos</span>
                    </button>
                </div>
            </div>
        `;
    }

    resultsSection.innerHTML = html;

    // Render initial videos
    if (videos && videos.length > 0) {
        renderVideos();
    }
}

// Render videos table
function renderVideos() {
    const tbody = document.getElementById('videosTableBody');
    const loadMoreContainer = document.getElementById('loadMoreContainer');

    if (!tbody) return;

    const videosToShow = allVideos.slice(0, videosDisplayed);

    tbody.innerHTML = videosToShow.map(video => {
        const views = video.view_count || 0;
        const isShort = video.is_short || false;
        const youtubeUrl = isShort
            ? `https://youtube.com/shorts/${video.video_id}`
            : `https://youtube.com/watch?v=${video.video_id}`;

        return `
            <tr>
                <td class="video-cell" onclick="window.open('${youtubeUrl}', '_blank')" style="cursor: pointer;">
                    <div class="video-thumbnail-small">
                        ${video.thumbnail ?
                            `<img src="${video.thumbnail}" alt="${escapeHtml(video.title)}" loading="lazy">` :
                            '<div class="thumbnail-placeholder-small"><i class="ph ph-video-camera"></i></div>'
                        }
                    </div>
                    <div class="video-title-cell">
                        ${escapeHtml(video.title)}
                    </div>
                </td>
                <td class="channel-cell" onclick="window.open('${youtubeUrl}', '_blank')" style="cursor: pointer;">${escapeHtml(video.channel_title)}</td>
                <td class="views-cell" onclick="window.open('${youtubeUrl}', '_blank')" style="cursor: pointer;">${formatNumber(views)}</td>
                <td class="published-cell" onclick="window.open('${youtubeUrl}', '_blank')" style="cursor: pointer;">${video.published_time || 'Recently'}</td>
                <td class="actions-cell">
                    <button class="deep-dive-btn" data-video-id="${video.video_id}" data-video-title="${escapeHtml(video.title).replace(/"/g, '&quot;')}" data-is-short="${isShort}">
                        <i class="ph ph-magnifying-glass-plus"></i>
                        Deep Dive
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    // Attach event listeners to all Deep Dive buttons
    attachDeepDiveListeners();

    // Show/hide load more button
    if (loadMoreContainer) {
        if (videosDisplayed < allVideos.length) {
            loadMoreContainer.style.display = 'block';
        } else {
            loadMoreContainer.style.display = 'none';
        }
    }
}

// Attach event listeners to Deep Dive buttons
function attachDeepDiveListeners() {
    const buttons = document.querySelectorAll('.deep-dive-btn');
    buttons.forEach(button => {
        // Remove old listener if exists
        button.replaceWith(button.cloneNode(true));
    });

    // Re-query and attach new listeners
    const newButtons = document.querySelectorAll('.deep-dive-btn');
    newButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const videoId = this.getAttribute('data-video-id');
            const videoTitle = this.getAttribute('data-video-title');
            openDeepDive.call(this, videoId, videoTitle);
        });
    });
}

// Load more videos
function loadMoreVideos() {
    videosDisplayed += 25;
    renderVideos();
}

// Format number with commas
function formatNumber(num) {
    if (!num && num !== 0) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Escape HTML to prevent XSS
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

// View switching
function switchView(view) {
    const listViewBtn = document.getElementById('listViewBtn');
    const urlViewBtn = document.getElementById('urlViewBtn');
    const exploreViewBtn = document.getElementById('exploreViewBtn');

    const listView = document.getElementById('listView');
    const urlView = document.getElementById('urlView');
    const exploreView = document.getElementById('exploreView');

    // Remove active from all buttons
    listViewBtn.classList.remove('active');
    urlViewBtn.classList.remove('active');
    exploreViewBtn.classList.remove('active');

    // Hide all views
    listView.style.display = 'none';
    urlView.style.display = 'none';
    exploreView.style.display = 'none';

    // Show selected view
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

// Search for channels
async function searchChannels() {
    if (isSearching) return;

    const input = document.getElementById('searchInput');
    const query = input.value.trim();

    if (!query) {
        return;
    }

    isSearching = true;

    // Show loading
    const searchBtn = document.querySelector('.search-btn');
    const originalText = searchBtn.innerHTML;
    searchBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Searching...';
    searchBtn.disabled = true;

    try {
        const response = await fetch(`/api/competitors/search?query=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.success) {
            searchResults = data.channels || [];
            renderSearchResults();
        }
    } catch (error) {
        console.error('Error searching channels:', error);
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
            <p class="empty-text">No channels found. Try a different search query.</p>
        `;
        return;
    }

    searchEmptyState.style.display = 'none';
    searchResultsDiv.style.display = 'block';

    // Filter out channels already added
    const existingChannelIds = new Set(competitors.map(c => c.channel_id));
    const availableResults = searchResults.filter(r => !existingChannelIds.has(r.channel_id));

    // Sort by subscriber count (high to low)
    availableResults.sort((a, b) => (b.subscriber_count || 0) - (a.subscriber_count || 0));

    resultsCount.textContent = `Found ${availableResults.length} channels`;

    searchResultsGrid.innerHTML = availableResults.map(channel => {
        const avatarHTML = channel.avatar ?
            `<img src="${channel.avatar}" alt="${escapeHtml(channel.title || 'Channel')}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><div class="avatar-placeholder" style="display:none;">${(channel.title || '?')[0].toUpperCase()}</div>` :
            `<div class="avatar-placeholder">${(channel.title || '?')[0].toUpperCase()}</div>`;

        // Construct YouTube URL
        const youtubeUrl = channel.channel_handle ?
            `https://youtube.com/${channel.channel_handle}` :
            `https://youtube.com/channel/${channel.channel_id}`;

        return `
            <div class="search-result-card">
                <div class="search-result-clickable" onclick="window.open('${youtubeUrl}', '_blank')">
                    <div class="competitor-avatar">
                        ${avatarHTML}
                    </div>
                    <div class="competitor-info">
                        <div class="competitor-title">${escapeHtml(channel.title || 'Unknown Channel')}</div>
                        ${channel.channel_handle ? `<div class="channel-handle">${escapeHtml(channel.channel_handle)}</div>` : ''}
                        <div class="competitor-stats">
                            <span class="stat">
                                <i class="ph ph-users"></i>
                                ${channel.subscriber_count_text || 'Unknown'}
                            </span>
                        </div>
                    </div>
                </div>
                <button class="add-result-btn" onclick='event.stopPropagation(); addChannelFromSearch(${JSON.stringify(channel).replace(/'/g, "&#39;").replace(/"/g, "&quot;")})' ${competitors.length >= 15 ? 'disabled' : ''}>
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
                <p class="empty-text">All found channels have already been added to this list.</p>
            </div>
        `;
    }
}

// Add channel from search results
async function addChannelFromSearch(channelData) {
    if (!currentListId) {
        return;
    }

    if (competitors.length >= 15) {
        return;
    }

    try {
        const response = await fetch('/api/competitors/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                list_id: currentListId,
                channel_data: channelData
            })
        });

        const data = await response.json();

        if (data.success) {
            competitors.push(data.channel);

            // Update list count
            const currentList = nicheLists.find(l => l.id === currentListId);
            if (currentList) {
                currentList.channel_count = (currentList.channel_count || 0) + 1;
                renderNicheLists();
            }

            // Re-render competitors list to show the newly added channel
            renderCompetitorsList();

            // Re-render search results to exclude newly added channel
            renderSearchResults();
        }
    } catch (error) {
        console.error('Error adding channel from search:', error);
    }
}

// Deep Dive functionality
function openDeepDive(videoId, videoTitle) {
    // 'this' is the button element
    const button = this;
    const originalContent = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="ph ph-spinner spin"></i> Loading...';

    // Disable all other Deep Dive buttons
    const allDeepDiveButtons = document.querySelectorAll('.deep-dive-btn');
    allDeepDiveButtons.forEach(btn => {
        if (btn !== button) {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.style.cursor = 'not-allowed';
        }
    });

    // Check if it's a short
    const isShort = button.getAttribute('data-is-short') === 'true';

    // Navigate to the deep dive page with is_short parameter if needed
    const url = isShort
        ? `/competitors/video/${videoId}/deep-dive?is_short=true`
        : `/competitors/video/${videoId}/deep-dive`;

    window.location.href = url;
}


// Helper function to get list name
function getListName(listId) {
    const list = nicheLists.find(l => l.id === listId);
    return list ? list.name : 'Unknown';
}

// Latest Analysis Functions
async function loadLatestAnalysisCard() {
    try {
        const response = await fetch('/api/competitors/latest-analysis');
        const data = await response.json();

        if (data.success && data.has_analysis) {
            const analysis = data.analysis;
            const section = document.getElementById('latestAnalysisSection');
            const listName = document.getElementById('latestAnalysisListName');
            const channelCount = document.getElementById('latestAnalysisChannelCount');
            const timeframe = document.getElementById('latestAnalysisTimeframe');
            const date = document.getElementById('latestAnalysisDate');

            // Format date
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
            channelCount.textContent = analysis.channel_count;
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
        const response = await fetch('/api/competitors/latest-analysis');
        const data = await response.json();

        console.log('Latest analysis response:', data);

        if (data.success && data.has_analysis) {
            const analysis = data.analysis;

            console.log('Loading analysis:', analysis);

            // Hide setup and progress sections
            const setupSection = document.getElementById('setupSection');
            const progressSection = document.getElementById('progressSection');
            const resultsSection = document.getElementById('resultsSection');

            if (setupSection) setupSection.style.display = 'none';
            if (progressSection) progressSection.style.display = 'none';
            if (resultsSection) resultsSection.style.display = 'block';

            // Display the saved analysis
            displayResults(analysis.insights);

            // Scroll to results
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } else {
            console.log('No analysis available or error:', data);
            alert('No saved analysis found.');
        }
    } catch (error) {
        console.error('Error loading latest analysis:', error);
        alert('Failed to load analysis: ' + error.message);
    }
}

// Filter content by timeframe
function filterByTimeframe(content, days) {
    if (!content || content.length === 0) return [];

    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    return content.filter(item => {
        // Try multiple date fields
        const pubDateStr = item.published_at || item.publishedAt || item.publish_date;

        if (!pubDateStr) {
            // No date available - exclude it
            console.debug('No date found for item:', item.title || item.video_id);
            return false;
        }

        try {
            let pubDate;

            // Parse ISO format date
            if (pubDateStr.includes('T')) {
                pubDate = new Date(pubDateStr.replace('Z', '+00:00'));
            } else {
                // Try YYYY-MM-DD format
                pubDate = new Date(pubDateStr);
            }

            // Check if date is valid and within timeframe
            if (!isNaN(pubDate.getTime())) {
                const isWithinTimeframe = pubDate >= cutoffDate;
                if (!isWithinTimeframe) {
                    console.debug('Filtering out (too old):', item.title || item.video_id, pubDateStr);
                }
                return isWithinTimeframe;
            } else {
                console.debug('Invalid date for item:', item.title || item.video_id, pubDateStr);
                return false;
            }
        } catch (e) {
            console.debug('Could not parse date:', pubDateStr, e);
            return false;
        }
    });
}

// Render Publishing Heatmap (Day of Week Distribution)
function renderPublishHeatmap(heatmapData) {
    const { data, max_count } = heatmapData;

    if (!data || data.length === 0) return '';

    const dayLabels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

    // Generate day bars
    let dayBars = '';
    data.forEach(item => {
        const percentage = max_count > 0 ? (item.count / max_count) * 100 : 0;
        const intensity = max_count > 0 ? item.count / max_count : 0;

        // Color gradient from light to dark blue based on count
        const colorIntensity = Math.max(0.3, intensity); // Minimum 30% intensity

        dayBars += `
            <div class="day-bar-row">
                <div class="day-bar-label">${dayLabels[item.day]}</div>
                <div class="day-bar-container">
                    <div class="day-bar-fill"
                         style="width: ${percentage}%; opacity: ${colorIntensity}"
                         title="${item.count} post${item.count !== 1 ? 's' : ''} on ${dayLabels[item.day]}">
                    </div>
                    <span class="day-bar-count">${item.count}</span>
                </div>
            </div>
        `;
    });

    return `
        <div class="heatmap-card">
            <h3 class="section-title">
                <i class="ph ph-calendar-dots"></i>
                Publishing Schedule
            </h3>
            <p class="heatmap-description">Which days of the week competitors post content</p>
            <div class="day-bars-container">
                ${dayBars}
            </div>
        </div>
    `;
}

// Show toast notification (removed - toasts disabled)
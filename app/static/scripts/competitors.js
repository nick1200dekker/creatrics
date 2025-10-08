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

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadNicheLists();
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
                list_id: currentListId
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
    
    // Scroll to top
    setTimeout(() => {
        document.getElementById('setupSection').scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start' 
        });
    }, 100);
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

    // Store all videos globally
    allVideos = videos || [];
    videosDisplayed = 25;

    const timeframeText = timeframe_days === 1 ? '24 hours' :
                         timeframe_days === 2 ? '48 hours' :
                         `${timeframe_days} days`;
    
    // Build HTML with back button and stats grid first
    let html = `
        <!-- Back Button -->
        <div class="back-button-container">
            <button class="back-btn" onclick="backToSetup()">
                <i class="ph ph-arrow-left"></i>
                Back to Setup
            </button>
        </div>
        
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
        
        // Parse and format the markdown content
        const sections = insights.summary.split(/(?=##\s)/);
        
        sections.forEach(section => {
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
    
    // Quick Wins
    if (insights.quick_wins && insights.quick_wins.length > 0) {
        const meaningfulWins = insights.quick_wins.filter(win => win.opportunity && win.opportunity.length > 30);
        
        if (meaningfulWins.length > 0) {
            html += `
                <div class="quick-wins-card">
                    <h3 class="section-title">
                        <i class="ph ph-rocket-launch"></i>
                        Content Opportunities
                    </h3>
                    <div class="quick-wins-list">
                        ${meaningfulWins.map(win => `
                            <div class="quick-win-item">
                                <div class="win-title">"${formatMarkdown(escapeHtml(win.title))}"</div>
                                <div class="win-opportunity">${formatMarkdown(escapeHtml(win.opportunity))}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
    }
    
    // Top Videos as Table
    if (videos && videos.length > 0) {
        html += `
            <div class="videos-card" id="videosCard">
                <h3 class="section-title">
                    <i class="ph ph-play-circle"></i>
                    Top Performing Videos (${videos.length} total)
                </h3>
                <div class="videos-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Video</th>
                                <th>Channel</th>
                                <th>Views</th>
                                <th>Published</th>
                            </tr>
                        </thead>
                        <tbody id="videosTableBody">
                        </tbody>
                    </table>
                </div>
                <div class="load-more-container" id="loadMoreContainer" style="display: none;">
                    <button class="load-more-btn" onclick="loadMoreVideos()">
                        <i class="ph ph-arrow-down"></i>
                        Load More Videos
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

        return `
            <tr onclick="window.open('https://youtube.com/watch?v=${video.video_id}', '_blank')" style="cursor: pointer;">
                <td class="video-cell">
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
                <td class="channel-cell">${escapeHtml(video.channel_title)}</td>
                <td class="views-cell">${formatNumber(views)}</td>
                <td class="published-cell">${video.published_time || 'Recently'}</td>
            </tr>
        `;
    }).join('');

    // Show/hide load more button
    if (loadMoreContainer) {
        if (videosDisplayed < allVideos.length) {
            loadMoreContainer.style.display = 'block';
        } else {
            loadMoreContainer.style.display = 'none';
        }
    }
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

// Show toast notification (removed - toasts disabled)
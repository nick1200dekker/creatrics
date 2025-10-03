// Competitors Management
let competitors = [];
let selectedTimeframe = '30';
let isAnalyzing = false;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadCompetitors();
});

// Load saved competitors
async function loadCompetitors() {
    try {
        const response = await fetch('/api/competitors/list');
        const data = await response.json();
        
        if (data.success) {
            competitors = data.competitors || [];
            renderCompetitorsList();
            
            // Show analysis options if we have competitors
            if (competitors.length > 0) {
                document.getElementById('analysisOptions').style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Error loading competitors:', error);
    }
}

// Add competitor
async function addCompetitor() {
    const input = document.getElementById('channelUrlInput');
    const url = input.value.trim();
    
    if (!url) {
        showToast('Please enter a channel URL', 'error');
        return;
    }
    
    // Validate URL format
    if (!url.includes('youtube.com/') && !url.includes('youtu.be/') && !url.startsWith('@')) {
        showToast('Please enter a valid YouTube channel URL (e.g., youtube.com/@channelname)', 'error');
        return;
    }
    
    // Check if we already have 15 competitors
    if (competitors.length >= 15) {
        showToast('Maximum 15 competitors allowed', 'error');
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
                channel_url: url
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            competitors.push(data.channel);
            renderCompetitorsList();
            input.value = '';
            showToast('Channel added successfully!', 'success');
            
            // Show analysis options
            document.getElementById('analysisOptions').style.display = 'block';
        } else {
            showToast(data.error || 'Failed to add channel', 'error');
        }
    } catch (error) {
        console.error('Error adding competitor:', error);
        showToast('Failed to add channel. Please try again.', 'error');
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
        return;
    }
    
    container.innerHTML = `
        <div class="competitors-header-row">
            <span class="competitors-count">${competitors.length} ${competitors.length === 1 ? 'Channel' : 'Channels'}</span>
            ${competitors.length >= 10 ? '<span class="ready-badge">Ready to Analyze</span>' : ''}
        </div>
        <div class="competitors-grid">
            ${competitors.map(comp => `
                <div class="competitor-card">
                    <div class="competitor-avatar">
                        ${comp.avatar ? 
                            `<img src="${comp.avatar}" alt="${comp.title}">` : 
                            `<div class="avatar-placeholder">${comp.title ? comp.title[0].toUpperCase() : '?'}</div>`
                        }
                    </div>
                    <div class="competitor-info">
                        <div class="competitor-title">${comp.title || 'Unknown Channel'}</div>
                        <div class="competitor-stats">
                            <span class="stat">
                                <i class="ph ph-users"></i>
                                ${comp.subscriber_count_text || '0'}
                            </span>
                            <span class="stat">
                                <i class="ph ph-video-camera"></i>
                                ${comp.video_count || 0} videos
                            </span>
                        </div>
                    </div>
                    <button class="remove-btn" onclick="removeCompetitor('${comp.id}')" title="Remove">
                        <i class="ph ph-x"></i>
                    </button>
                </div>
            `).join('')}
        </div>
    `;
}

// Remove competitor
async function removeCompetitor(docId) {
    if (!confirm('Remove this competitor?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/competitors/remove/${docId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            competitors = competitors.filter(c => c.id !== docId);
            renderCompetitorsList();
            showToast('Competitor removed', 'success');
            
            // Hide analysis options if no competitors left
            if (competitors.length === 0) {
                document.getElementById('analysisOptions').style.display = 'none';
            }
        } else {
            showToast(data.error || 'Failed to remove competitor', 'error');
        }
    } catch (error) {
        console.error('Error removing competitor:', error);
        showToast('Failed to remove competitor', 'error');
    }
}

// Set timeframe
function setTimeframe(days) {
    selectedTimeframe = days;
    
    // Update active button
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
    
    if (competitors.length === 0) {
        showToast('Please add some competitors first', 'error');
        return;
    }
    
    isAnalyzing = true;
    const analyzeBtn = document.getElementById('analyzeBtn');
    const originalText = analyzeBtn.innerHTML;
    analyzeBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Analyzing...';
    analyzeBtn.disabled = true;
    
    try {
        const response = await fetch('/api/competitors/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                timeframe: selectedTimeframe
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayResults(data.data);
            showToast('Analysis complete!', 'success');
        } else {
            if (data.error_type === 'insufficient_credits') {
                showToast(`Insufficient credits. Need ${data.required_credits.toFixed(2)}, have ${data.current_credits.toFixed(2)}`, 'error');
            } else {
                showToast(data.error || 'Analysis failed', 'error');
            }
        }
    } catch (error) {
        console.error('Error analyzing competitors:', error);
        showToast('Analysis failed. Please try again.', 'error');
    } finally {
        isAnalyzing = false;
        analyzeBtn.innerHTML = originalText;
        analyzeBtn.disabled = false;
    }
}

// Display results
function displayResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const { videos, patterns, insights, timeframe_days } = data;
    
    const timeframeText = timeframe_days === 1 ? '24 hours' : 
                         timeframe_days === 2 ? '48 hours' : 
                         `${timeframe_days} days`;
    
    resultsSection.innerHTML = `
        <div class="results-header">
            <h2 class="results-title">
                <i class="ph ph-chart-line"></i>
                Analysis Results
            </h2>
            <span class="timeframe-badge">Last ${timeframeText}</span>
        </div>
        
        <!-- Insights Summary -->
        <div class="insights-card">
            <h3 class="section-title">
                <i class="ph ph-lightbulb"></i>
                Key Insights
            </h3>
            <div class="insights-content">
                ${insights.summary.split('\n').map(line => 
                    line.trim() ? `<p>${line}</p>` : ''
                ).join('')}
            </div>
        </div>
        
        <!-- Quick Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-video-camera"></i></div>
                <div class="stat-value">${patterns.total_videos_analyzed}</div>
                <div class="stat-label">Videos Analyzed</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-eye"></i></div>
                <div class="stat-value">${formatNumber(patterns.avg_views)}</div>
                <div class="stat-label">Avg Views</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-fire"></i></div>
                <div class="stat-value">${formatNumber(patterns.total_views)}</div>
                <div class="stat-label">Total Views</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="ph ph-users-three"></i></div>
                <div class="stat-value">${patterns.total_channels}</div>
                <div class="stat-label">Channels</div>
            </div>
        </div>
        
        <!-- Trending Topics -->
        ${insights.trending_topics && insights.trending_topics.length > 0 ? `
            <div class="trends-card">
                <h3 class="section-title">
                    <i class="ph ph-trend-up"></i>
                    Trending Topics
                </h3>
                <div class="trends-grid">
                    ${insights.trending_topics.map(topic => `
                        <div class="trend-tag">
                            <span class="trend-name">${topic.topic}</span>
                            <span class="trend-badge">${topic.frequency}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}
        
        <!-- Quick Wins -->
        ${insights.quick_wins && insights.quick_wins.length > 0 ? `
            <div class="quick-wins-card">
                <h3 class="section-title">
                    <i class="ph ph-rocket-launch"></i>
                    Quick Win Opportunities
                </h3>
                <div class="quick-wins-list">
                    ${insights.quick_wins.map(win => `
                        <div class="quick-win-item">
                            <div class="win-header">
                                <span class="win-channel">${win.channel}</span>
                                <span class="win-views">${formatNumber(win.views)} views</span>
                            </div>
                            <div class="win-title">${win.title}</div>
                            <div class="win-opportunity">${win.opportunity}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}
        
        <!-- Top Videos -->
        <div class="videos-card">
            <h3 class="section-title">
                <i class="ph ph-play-circle"></i>
                Top Performing Videos
            </h3>
            <div class="videos-grid">
                ${videos.slice(0, 12).map(video => `
                    <div class="video-card">
                        <div class="video-thumbnail">
                            ${video.thumbnail ? 
                                `<img src="${video.thumbnail}" alt="${video.title}">` : 
                                '<div class="thumbnail-placeholder"><i class="ph ph-video-camera"></i></div>'
                            }
                            <span class="video-duration">${video.length || 'N/A'}</span>
                        </div>
                        <div class="video-info">
                            <div class="video-title">${video.title}</div>
                            <div class="video-meta">
                                <span class="video-channel">${video.channel_title}</span>
                                <span class="video-views">${formatNumber(video.view_count)} views</span>
                            </div>
                            <div class="video-published">${video.published_time || 'Recently'}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    resultsSection.style.display = 'block';
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Format number with commas
function formatNumber(num) {
    if (!num) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Show toast notification
function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast').forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="ph ph-${type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : 'info'}"></i>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
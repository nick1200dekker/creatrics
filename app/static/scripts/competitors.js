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
            // Add competitor to list immediately
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
            ${competitors.map(comp => {
                // Create avatar HTML with error handling
                const avatarHTML = comp.avatar ? 
                    `<img src="${comp.avatar}" alt="${comp.title || 'Channel'}" onerror="this.onerror=null; this.style.display='none'; this.parentElement.innerHTML='<div class=\\'avatar-placeholder\\'>${(comp.title || '?')[0].toUpperCase()}</div>';">` : 
                    `<div class="avatar-placeholder">${(comp.title || '?')[0].toUpperCase()}</div>`;
                
                return `
                    <div class="competitor-card">
                        <div class="competitor-avatar">
                            ${avatarHTML}
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
                `;
            }).join('')}
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

// Format markdown-style text
function formatMarkdown(text) {
    if (!text) return '';
    
    // Convert **bold** to <strong>
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Convert *italic* to <em>
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
    
    return text;
}

// Display results with proper formatting
function displayResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const { videos, patterns, insights, timeframe_days } = data;
    
    const timeframeText = timeframe_days === 1 ? '24 hours' : 
                         timeframe_days === 2 ? '48 hours' : 
                         `${timeframe_days} days`;
    
    let html = `
        <div class="results-header">
            <h2 class="results-title">
                <i class="ph ph-chart-line"></i>
                Analysis Results
            </h2>
            <span class="timeframe-badge">Last ${timeframeText}</span>
        </div>
    `;
    
    // Key Insights with proper formatting
    if (insights && insights.summary) {
        html += `
            <div class="insights-card">
                <h3 class="section-title">
                    <i class="ph ph-lightbulb"></i>
                    Key Insights
                </h3>
                <div class="insights-content">
        `;
        
        // Split by newlines and format each paragraph
        const paragraphs = insights.summary.split('\n').filter(line => line.trim());
        let inList = false;
        
        paragraphs.forEach(para => {
            const trimmed = para.trim();
            
            // Check if it's a header (starts with # or ##)
            if (trimmed.startsWith('##')) {
                if (inList) {
                    html += '</ul>';
                    inList = false;
                }
                const headerText = trimmed.replace(/^##\s*/, '');
                html += `<h4 style="font-weight: 600; color: var(--text-primary); margin: 1rem 0 0.5rem 0;">${formatMarkdown(escapeHtml(headerText))}</h4>`;
            } else if (trimmed.startsWith('#')) {
                if (inList) {
                    html += '</ul>';
                    inList = false;
                }
                const headerText = trimmed.replace(/^#\s*/, '');
                html += `<h3 style="font-weight: 700; color: var(--text-primary); margin: 1.25rem 0 0.75rem 0; font-size: 1.125rem;">${formatMarkdown(escapeHtml(headerText))}</h3>`;
            } else if (trimmed.startsWith('-') || trimmed.startsWith('•')) {
                // Bullet point
                const bulletText = trimmed.replace(/^[-•]\s*/, '');
                if (!inList) {
                    html += '<ul style="list-style: disc; margin-left: 1.5rem; margin-bottom: 0.75rem;">';
                    inList = true;
                }
                html += `<li style="margin-bottom: 0.375rem;">${formatMarkdown(escapeHtml(bulletText))}</li>`;
            } else if (trimmed) {
                // Close any open ul
                if (inList) {
                    html += '</ul>';
                    inList = false;
                }
                // Regular paragraph
                html += `<p>${formatMarkdown(escapeHtml(trimmed))}</p>`;
            }
        });
        
        // Close any unclosed ul
        if (inList) {
            html += '</ul>';
        }
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Quick Stats
    html += `
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
    `;
    
    // Trending Topics
    if (insights.trending_topics && insights.trending_topics.length > 0) {
        html += `
            <div class="trends-card">
                <h3 class="section-title">
                    <i class="ph ph-trend-up"></i>
                    Trending Topics
                </h3>
                <div class="trends-grid">
                    ${insights.trending_topics.map(topic => `
                        <div class="trend-tag">
                            <span class="trend-name">${escapeHtml(topic.topic)}</span>
                            <span class="trend-badge">${topic.frequency}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    // Quick Wins - Only show if they have meaningful opportunities
    if (insights.quick_wins && insights.quick_wins.length > 0) {
        // Filter out generic opportunities
        const meaningfulWins = insights.quick_wins.filter(win => {
            const opportunity = win.opportunity?.toLowerCase() || '';
            // Filter out generic "make your version" type suggestions
            return !opportunity.includes('consider creating your version') &&
                   !opportunity.includes('high-performing content') &&
                   opportunity.length > 50; // Ensure it has substantial content
        });
        
        if (meaningfulWins.length > 0) {
            html += `
                <div class="quick-wins-card">
                    <h3 class="section-title">
                        <i class="ph ph-rocket-launch"></i>
                        Quick Win Opportunities
                    </h3>
                    <div class="quick-wins-list">
                        ${meaningfulWins.map(win => `
                            <div class="quick-win-item">
                                <div class="win-header">
                                    <span class="win-channel">${escapeHtml(win.channel)}</span>
                                    <span class="win-views">${formatNumber(win.views)} views</span>
                                </div>
                                <div class="win-title">${formatMarkdown(escapeHtml(win.title))}</div>
                                <div class="win-opportunity">${formatMarkdown(escapeHtml(win.opportunity))}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
    }
    
    // Top Videos
    if (videos && videos.length > 0) {
        html += `
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
                                    `<img src="${video.thumbnail}" alt="${escapeHtml(video.title)}" loading="lazy">` : 
                                    '<div class="thumbnail-placeholder"><i class="ph ph-video-camera"></i></div>'
                                }
                                ${video.length ? `<span class="video-duration">${video.length}</span>` : ''}
                            </div>
                            <div class="video-info">
                                <div class="video-title">${escapeHtml(video.title)}</div>
                                <div class="video-meta">
                                    <span class="video-channel">${escapeHtml(video.channel_title)}</span>
                                    <span class="video-views">${formatNumber(video.view_count)} views</span>
                                </div>
                                <div class="video-published">${video.published_time || 'Recently'}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    resultsSection.innerHTML = html;
    resultsSection.style.display = 'block';
    
    // Scroll to results smoothly
    setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
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

// Show toast notification
function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast').forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const iconClass = type === 'success' ? 'ph-check-circle' : 
                     type === 'error' ? 'ph-x-circle' : 
                     'ph-info';
    
    toast.innerHTML = `
        <i class="ph ${iconClass}"></i>
        <span>${escapeHtml(message)}</span>
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
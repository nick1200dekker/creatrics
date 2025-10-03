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
                const avatarHTML = comp.avatar ? 
                    `<img src="${comp.avatar}" alt="${escapeHtml(comp.title || 'Channel')}" onerror="this.onerror=null; this.style.display='none'; this.parentElement.innerHTML='<div class=\\'avatar-placeholder\\'>${(comp.title || '?')[0].toUpperCase()}</div>';">` : 
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
    
    if (competitors.length === 0) {
        showToast('Please add some competitors first', 'error');
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
                timeframe: selectedTimeframe
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
            
            if (data.error_type === 'insufficient_credits') {
                showToast(`Insufficient credits. Need ${data.required_credits.toFixed(2)}, have ${data.current_credits.toFixed(2)}`, 'error');
            } else {
                showToast(data.error || 'Analysis failed', 'error');
            }
        }
    } catch (error) {
        console.error('Error analyzing competitors:', error);
        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('setupSection').style.display = 'block';
        showToast('Analysis failed. Please try again.', 'error');
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
            <div class="videos-card">
                <h3 class="section-title">
                    <i class="ph ph-play-circle"></i>
                    Top Performing Videos
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
                        <tbody>
                            ${videos.slice(0, 20).map(video => `
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
                                    <td class="views-cell">${formatNumber(video.view_count)}</td>
                                    <td class="published-cell">${video.published_time || 'Recently'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    resultsSection.innerHTML = html;
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
    
    setTimeout(() => toast.classList.add('show'), 10);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
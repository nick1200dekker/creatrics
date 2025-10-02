// Competitors Analysis JavaScript
(function() {
    'use strict';
    
    // State management
    let competitors = [];
    let selectedTimeframe = '30';
    let analysisData = null;
    let isAnalyzing = false;
    
    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        console.log('Competitors module initialized');
    });
    
    // Add competitor
    async function addCompetitor() {
        const input = document.getElementById('channelUrlInput');
        const url = input.value.trim();
        
        if (!url) {
            showToast('Please enter a YouTube channel URL', 'error');
            return;
        }
        
        // Check if we already have 15 competitors
        if (competitors.length >= 15) {
            showToast('Maximum 15 competitors allowed', 'error');
            return;
        }
        
        // Disable input while adding
        input.disabled = true;
        const addBtn = document.querySelector('.add-btn');
        addBtn.disabled = true;
        addBtn.innerHTML = '<i class="ph ph-spinner"></i> Adding...';
        
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
                renderCompetitors();
                input.value = '';
                showToast('Competitor added successfully!', 'success');
                
                // Show analysis options if we have competitors
                if (competitors.length > 0) {
                    document.getElementById('analysisOptions').style.display = 'block';
                }
            } else {
                showToast(data.error || 'Failed to add competitor', 'error');
            }
        } catch (error) {
            console.error('Error adding competitor:', error);
            showToast('Failed to add competitor', 'error');
        } finally {
            input.disabled = false;
            addBtn.disabled = false;
            addBtn.innerHTML = '<i class="ph ph-plus"></i> Add Channel';
        }
    }
    
    // Remove competitor
    function removeCompetitor(index) {
        competitors.splice(index, 1);
        renderCompetitors();
        
        if (competitors.length === 0) {
            document.getElementById('analysisOptions').style.display = 'none';
        }
        
        showToast('Competitor removed', 'info');
    }
    
    // Render competitors list
    function renderCompetitors() {
        const container = document.getElementById('competitorsList');
        
        if (competitors.length === 0) {
            container.innerHTML = '<div class="empty-competitors">No competitors added yet. Add channels to get started.</div>';
            return;
        }
        
        container.innerHTML = competitors.map((comp, index) => `
            <div class="competitor-card">
                <img src="${escapeHtml(comp.avatar || '/static/img/default-avatar.png')}" 
                     alt="${escapeHtml(comp.title)}" 
                     class="competitor-avatar">
                <div class="competitor-info">
                    <div class="competitor-name">${escapeHtml(comp.title)}</div>
                    <div class="competitor-stats">
                        ${formatNumber(comp.subscriber_count)} subscribers • ${formatNumber(comp.video_count)} videos
                    </div>
                </div>
                <button class="remove-competitor-btn" onclick="removeCompetitor(${index})" title="Remove competitor">
                    <i class="ph ph-x"></i>
                </button>
            </div>
        `).join('');
    }
    
    // Set timeframe
    function setTimeframe(days) {
        selectedTimeframe = days;
        
        // Update button states
        document.querySelectorAll('.timeframe-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-days') === days) {
                btn.classList.add('active');
            }
        });
    }
    
    // Analyze competitors
    async function analyzeCompetitors() {
        if (competitors.length === 0) {
            showToast('Please add at least one competitor', 'error');
            return;
        }
        
        if (isAnalyzing) return;
        
        isAnalyzing = true;
        const analyzeBtn = document.getElementById('analyzeBtn');
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = '<i class="ph ph-spinner"></i> Analyzing...';
        
        // Hide setup section and show results section with loading
        document.getElementById('setupSection').style.display = 'none';
        const resultsSection = document.getElementById('resultsSection');
        resultsSection.style.display = 'block';
        resultsSection.innerHTML = `
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <div class="loading-text">Analyzing Competitors</div>
                <div class="loading-subtext">Fetching videos, analyzing patterns, and generating insights...</div>
            </div>
        `;
        
        try {
            const channelIds = competitors.map(c => c.channel_id);
            
            const response = await fetch('/api/competitors/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    channel_ids: channelIds,
                    timeframe: selectedTimeframe
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                analysisData = data.data;
                renderResults(data.data);
                showToast('Analysis complete!', 'success');
            } else {
                // Check if it's an insufficient credits error
                if (data.error_type === 'insufficient_credits') {
                    resultsSection.innerHTML = `
                        <div class="insufficient-credits-card">
                            <div class="credit-icon-wrapper">
                                <i class="ph ph-coins"></i>
                            </div>
                            <div class="credits-title">Insufficient Credits</div>
                            <div class="credits-description">
                                You need <strong>${data.required_credits?.toFixed(2) || '0.00'}</strong> credits but only have
                                <strong>${data.current_credits?.toFixed(2) || '0.00'}</strong> credits.
                            </div>
                            <a href="/payment" class="upgrade-btn-primary">
                                <i class="ph ph-crown"></i>
                                Upgrade Plan
                            </a>
                        </div>
                    `;
                } else {
                    throw new Error(data.error || 'Analysis failed');
                }
            }
        } catch (error) {
            console.error('Error analyzing competitors:', error);
            resultsSection.innerHTML = `
                <div class="error-state">
                    <i class="ph ph-warning-circle error-icon"></i>
                    <div class="error-title">Analysis Failed</div>
                    <div class="error-text">Unable to analyze competitors. Please try again.</div>
                </div>
            `;
            showToast('Failed to analyze competitors', 'error');
        } finally {
            isAnalyzing = false;
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = '<i class="ph ph-chart-line"></i> Analyze Competitors';
        }
    }
    
    // Render analysis results
    function renderResults(data) {
        const patterns = data.patterns || {};
        const insights = data.insights || {};
        const videos = data.videos || [];
        
        let html = `
            <div class="results-header">
                <h2 class="results-title">
                    <i class="ph ph-chart-bar"></i>
                    Analysis Results
                </h2>
                <button class="back-btn" onclick="backToSetup()">
                    <i class="ph ph-arrow-left"></i>
                    Back
                </button>
            </div>
            
            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <i class="ph ph-video-camera stat-icon"></i>
                    <div class="stat-label">Videos Analyzed</div>
                    <div class="stat-value">${formatNumber(patterns.total_videos_analyzed || 0)}</div>
                </div>
                <div class="stat-card">
                    <i class="ph ph-users-three stat-icon"></i>
                    <div class="stat-label">Channels</div>
                    <div class="stat-value">${patterns.total_channels || 0}</div>
                </div>
                <div class="stat-card">
                    <i class="ph ph-eye stat-icon"></i>
                    <div class="stat-label">Average Views</div>
                    <div class="stat-value">${formatNumber(patterns.avg_views || 0)}</div>
                </div>
                <div class="stat-card">
                    <i class="ph ph-chart-line stat-icon"></i>
                    <div class="stat-label">Total Views</div>
                    <div class="stat-value">${formatNumber(patterns.total_views || 0)}</div>
                </div>
            </div>
            
            <!-- Content Grid -->
            <div class="content-grid">
                <!-- Videos Section -->
                <div class="videos-section">
                    <div class="section-header">
                        <h3 class="section-title">
                            <i class="ph ph-fire"></i>
                            Top Performing Videos
                        </h3>
                    </div>
                    <div class="videos-list">
        `;
        
        videos.forEach(video => {
            html += `
                <div class="video-item" onclick="openVideo('${escapeHtml(video.video_id)}')">
                    <img src="${escapeHtml(video.thumbnail || '')}" 
                         alt="${escapeHtml(video.title)}" 
                         class="video-thumbnail">
                    <div class="video-info">
                        <div class="video-title">${escapeHtml(video.title)}</div>
                        <div class="video-meta">
                            <span class="video-meta-item video-channel">
                                <i class="ph ph-user"></i>
                                ${escapeHtml(video.channel_title || '')}
                            </span>
                            <span class="video-meta-item">
                                <i class="ph ph-eye"></i>
                                ${formatNumber(video.view_count || 0)} views
                            </span>
                            <span class="video-meta-item">
                                <i class="ph ph-clock"></i>
                                ${escapeHtml(video.published_time || '')}
                            </span>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                    </div>
                </div>
                
                <!-- Insights Section -->
                <div class="insights-section">
                    <div class="section-header">
                        <h3 class="section-title">
                            <i class="ph ph-lightbulb"></i>
                            AI Insights
                        </h3>
                    </div>
                    <div class="insights-content">
        `;
        
        // AI Summary
        if (insights.summary) {
            html += `
                <div class="insight-card">
                    <div class="insight-header">
                        <i class="ph ph-sparkle insight-icon"></i>
                        <span class="insight-title">Summary</span>
                    </div>
                    <div class="insight-text">${escapeHtml(insights.summary)}</div>
                </div>
            `;
        }
        
        // Quick Wins
        if (insights.quick_wins && insights.quick_wins.length > 0) {
            html += `
                <div class="insight-card">
                    <div class="insight-header">
                        <i class="ph ph-lightning insight-icon"></i>
                        <span class="insight-title">Quick Win Opportunities</span>
                    </div>
                    <ul class="trending-list">
            `;
            
            insights.quick_wins.forEach(win => {
                html += `<li class="trending-item">${escapeHtml(win.title)}</li>`;
            });
            
            html += `
                    </ul>
                </div>
            `;
        }
        
        // Top Title Words
        if (patterns.top_title_words && patterns.top_title_words.length > 0) {
            html += `
                <div class="insight-card">
                    <div class="insight-header">
                        <i class="ph ph-text-aa insight-icon"></i>
                        <span class="insight-title">Popular Title Words</span>
                    </div>
                    <ul class="trending-list">
            `;
            
            patterns.top_title_words.slice(0, 5).forEach(word => {
                html += `<li class="trending-item">${escapeHtml(word.word)} (${word.count})</li>`;
            });
            
            html += `
                    </ul>
                </div>
            `;
        }
        
        html += `
                    </div>
                </div>
            </div>
        `;
        
        document.getElementById('resultsSection').innerHTML = html;
    }
    
    // Back to setup
    function backToSetup() {
        document.getElementById('resultsSection').style.display = 'none';
        document.getElementById('setupSection').style.display = 'block';
    }
    
    // Open video in new tab
    function openVideo(videoId) {
        window.open(`https://www.youtube.com/watch?v=${videoId}`, '_blank');
    }
    
    // Format number with commas
    function formatNumber(num) {
        if (!num) return '0';
        return parseInt(num).toLocaleString();
    }
    
    // Escape HTML
    function escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return String(text).replace(/[&<>"']/g, m => map[m]);
    }
    
    // Show toast notification
    function showToast(message, type = 'success') {
        // Remove existing toast
        const existingToast = document.querySelector('.toast-notification');
        if (existingToast) {
            existingToast.remove();
        }
        
        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        
        const icon = type === 'success' ? 'ph-check-circle' : 
                    type === 'error' ? 'ph-x-circle' : 
                    'ph-info';
        
        toast.innerHTML = `
            <i class="ph ${icon}"></i>
            <span class="toast-text">${message}</span>
        `;
        
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Hide toast
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // Expose functions to global scope
    window.addCompetitor = addCompetitor;
    window.removeCompetitor = removeCompetitor;
    window.setTimeframe = setTimeframe;
    window.analyzeCompetitors = analyzeCompetitors;
    window.backToSetup = backToSetup;
    window.openVideo = openVideo;
    
})();
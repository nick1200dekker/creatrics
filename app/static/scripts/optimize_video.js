/**
 * Optimize Video JavaScript
 * Handles video optimization interface and API interactions
 */

// Global state
let currentVideoId = null;

// Load videos on page load
document.addEventListener('DOMContentLoaded', function() {
    loadMyVideos();
    loadOptimizationHistory();
});

/**
 * Load user's YouTube videos
 */
async function loadMyVideos() {
    const grid = document.getElementById('myVideosGrid');
    const emptyState = document.getElementById('emptyVideos');

    try {
        // Show loading state
        grid.innerHTML = '<div class="empty-state"><i class="ph ph-spinner spin"></i><p>Loading your videos...</p></div>';
        emptyState.style.display = 'none';

        const response = await fetch('/optimize-video/api/get-my-videos');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load videos');
        }

        const videos = data.videos || [];

        if (videos.length === 0) {
            grid.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }

        // Render videos
        grid.innerHTML = videos.map(video => `
            <div class="video-card" onclick="optimizeVideo('${video.video_id}')">
                <div class="video-thumbnail">
                    <img src="${video.thumbnail}" alt="${escapeHtml(video.title)}" loading="lazy">
                </div>
                <div class="video-info">
                    <h4 class="video-title">${escapeHtml(video.title)}</h4>
                    <div class="video-meta">
                        <span><i class="ph ph-eye"></i> ${video.view_count}</span>
                        <span><i class="ph ph-clock"></i> ${video.published_time}</span>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading videos:', error);
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ph ph-warning"></i>
                <p>Failed to load videos</p>
                <span>${escapeHtml(error.message)}</span>
            </div>
        `;
    }
}

/**
 * Load optimization history
 */
async function loadOptimizationHistory() {
    const grid = document.getElementById('historyGrid');
    const emptyState = document.getElementById('emptyHistory');

    try {
        const response = await fetch('/optimize-video/api/optimization-history');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load history');
        }

        const history = data.history || [];

        if (history.length === 0) {
            grid.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }

        emptyState.style.display = 'none';

        // Render history
        grid.innerHTML = history.map(item => {
            const videoInfo = item.video_info || {};
            const optimizedAt = item.optimized_at ? new Date(item.optimized_at).toLocaleDateString() : '';

            return `
                <div class="history-item" onclick="showOptimizationResults('${item.video_id}')">
                    <div class="history-thumbnail">
                        <img src="${videoInfo.thumbnail || ''}" alt="${escapeHtml(videoInfo.title || '')}" loading="lazy">
                    </div>
                    <div class="history-info">
                        <h4 class="history-title">${escapeHtml(videoInfo.title || item.current_title || 'Untitled')}</h4>
                        <div class="history-meta">
                            <span><i class="ph ph-calendar"></i> Optimized on ${optimizedAt}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading history:', error);
        emptyState.style.display = 'block';
    }
}

/**
 * Optimize a specific video
 */
async function optimizeVideo(videoId) {
    try {
        // Store current video ID globally
        currentVideoId = videoId;

        // Hide videos list, show loading section
        document.getElementById('videosListSection').style.display = 'none';
        document.getElementById('loadingSection').style.display = 'block';
        document.getElementById('resultsSection').style.display = 'none';

        const response = await fetch(`/optimize-video/api/optimize/${videoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        console.log('Optimization complete:', data);

        if (!data.success) {
            throw new Error(data.error || 'Optimization failed');
        }

        if (!data.data) {
            throw new Error('No optimization data received from server');
        }

        // Display results immediately
        displayOptimizationResults(data.data);
        document.getElementById('loadingSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'block';

        // Scroll to results
        setTimeout(() => {
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) {
                resultsSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        }, 100);

        // Reload history
        loadOptimizationHistory();

    } catch (error) {
        console.error('Error optimizing video:', error);
        document.getElementById('loadingSection').style.display = 'none';
        document.getElementById('videosListSection').style.display = 'block';
        alert(`Failed to optimize video: ${error.message}`);
    }
}

/**
 * Display optimization results
 */
function displayOptimizationResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    const videoInfo = data.video_info || {};
    const recommendations = data.recommendations || {};
    const titleSuggestions = data.title_suggestions || [data.optimized_title];

    const html = `
        <div class="results-header">
            <div class="results-title-container">
                <h3 class="video-title-display">${escapeHtml(videoInfo.title || data.current_title || '')}</h3>
                <button class="back-btn" onclick="backToVideos()">
                    <i class="ph ph-arrow-left"></i>
                    Back to Videos
                </button>
            </div>
        </div>

        <div class="results-content">
            <!-- Video Info Card -->
            <div class="result-card video-header-card">
                <div class="video-header-content">
                    <div class="video-thumbnail-wrapper">
                        <img src="${videoInfo.thumbnail || ''}" alt="Video thumbnail" class="video-thumbnail-img">
                    </div>
                    <div class="video-meta-info">
                        <h3 class="video-title-text">${escapeHtml(videoInfo.title || data.current_title || '')}</h3>
                        <div class="video-stats">
                            <span class="stat">
                                <i class="ph ph-eye"></i>
                                ${videoInfo.view_count || '0'} views
                            </span>
                            <span class="stat">
                                <i class="ph ph-clock"></i>
                                ${videoInfo.published_time || ''}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Thumbnail Analysis -->
            ${data.thumbnail_analysis ? `
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-image"></i>
                    Thumbnail Analysis
                </h3>
                <div class="thumbnail-analysis-content">
                    <div class="recommendations-text">${formatMarkdown(data.thumbnail_analysis)}</div>
                </div>
            </div>
            ` : ''}

            <!-- Title Suggestions -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-text-aa"></i>
                    Title Suggestions
                    <button class="refresh-titles-btn" onclick="refreshTitles()" id="refreshTitlesBtn">
                        <i class="ph ph-arrows-clockwise"></i>
                        <span>Refresh</span>
                    </button>
                </h3>
                <div class="comparison-box current-box">
                    <div class="comparison-label">Current Title</div>
                    <div class="comparison-value">${escapeHtml(data.current_title || videoInfo.title || '')}</div>
                </div>
                <div class="suggestions-list" id="titleSuggestionsList">
                    ${titleSuggestions.map((title, index) => `
                        <div class="suggestion-item">
                            <div class="suggestion-number">${index + 1}</div>
                            <div class="suggestion-text">${escapeHtml(title)}</div>
                            <button class="copy-btn" onclick="copyToClipboard(this, \`${escapeHtml(title).replace(/`/g, '\\`')}\`)">
                                <i class="ph ph-copy"></i>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>

            <!-- Description Optimization -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-align-left"></i>
                    Description Optimization
                </h3>
                <div class="comparison-box current-box">
                    <div class="comparison-label">Current Description</div>
                    <div class="comparison-value description-text">${escapeHtml(data.current_description || '')}</div>
                </div>
                <div class="comparison-box optimized-box">
                    <div class="comparison-label">
                        Optimized Description
                        <button class="copy-btn-small" onclick="copyToClipboard(this, \`${escapeHtml(data.optimized_description || '').replace(/`/g, '\\`')}\`)">
                            <i class="ph ph-copy"></i>
                            Copy
                        </button>
                    </div>
                    <div class="comparison-value description-text">${escapeHtml(data.optimized_description || '')}</div>
                </div>
            </div>

            <!-- Tags Optimization -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-hash"></i>
                    Tags Optimization
                </h3>
                <div class="tags-container">
                    <div class="tags-section">
                        <div class="tags-label">Current Tags</div>
                        <div class="tags-list">
                            ${(data.current_tags || []).map(tag => `<span class="tag tag-current">${escapeHtml(tag)}</span>`).join('')}
                        </div>
                    </div>
                    <div class="tags-section">
                        <div class="tags-label">
                            Optimized Tags
                            <button class="copy-btn-small" onclick="copyAllTags()">
                                <i class="ph ph-copy"></i>
                                Copy All
                            </button>
                        </div>
                        <div class="tags-list" id="optimizedTagsList">
                            ${(data.optimized_tags || []).slice(0, 30).map(tag => `<span class="tag tag-optimized">${escapeHtml(tag)}</span>`).join('')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    resultsSection.innerHTML = html;

    // Store optimized tags globally for copying
    window.optimizedTags = data.optimized_tags || [];
}

/**
 * Back to videos list
 */
function backToVideos() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('videosListSection').style.display = 'block';
}

/**
 * Show existing optimization results
 */
async function showOptimizationResults(videoId) {
    try {
        // For simplicity, just re-optimize (it will load from cache)
        await optimizeVideo(videoId);
    } catch (error) {
        console.error('Error showing results:', error);
        alert('Failed to load optimization results');
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format markdown-like text to HTML
 */
function formatMarkdown(text) {
    if (!text) return '';

    // Escape HTML first
    let formatted = escapeHtml(text);

    // Convert **bold** to <strong>
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Convert *italic* to <em>
    formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Convert line breaks to <br>
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(button, text) {
    navigator.clipboard.writeText(text).then(() => {
        const icon = button.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'ph ph-check';
        button.style.color = '#10B981';

        setTimeout(() => {
            icon.className = originalClass;
            button.style.color = '';
        }, 2000);
    });
}

/**
 * Copy all optimized tags
 */
function copyAllTags() {
    const tags = window.optimizedTags || [];
    const tagsText = tags.join(', ');

    navigator.clipboard.writeText(tagsText).then(() => {
        const btn = event.target.closest('button');
        const icon = btn.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'ph ph-check';
        btn.style.color = '#10B981';

        setTimeout(() => {
            icon.className = originalClass;
            btn.style.color = '';
        }, 2000);
    });
}

/**
 * Refresh title suggestions
 */
async function refreshTitles() {
    if (!currentVideoId) {
        alert('No video selected');
        return;
    }

    const refreshBtn = document.getElementById('refreshTitlesBtn');
    const icon = refreshBtn.querySelector('i');
    const span = refreshBtn.querySelector('span');

    try {
        // Show loading state
        refreshBtn.disabled = true;
        icon.className = 'ph ph-spinner spin';
        span.textContent = 'Refreshing...';

        const response = await fetch(`/optimize-video/api/refresh-titles/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to refresh titles');
        }

        // Update the title suggestions list
        const titlesList = document.getElementById('titleSuggestionsList');
        const newTitles = data.title_suggestions || [];

        titlesList.innerHTML = newTitles.map((title, index) => `
            <div class="suggestion-item">
                <div class="suggestion-number">${index + 1}</div>
                <div class="suggestion-text">${escapeHtml(title)}</div>
                <button class="copy-btn" onclick="copyToClipboard(this, \`${escapeHtml(title).replace(/`/g, '\\`')}\`)">
                    <i class="ph ph-copy"></i>
                </button>
            </div>
        `).join('');

        // Show success feedback
        icon.className = 'ph ph-check';
        span.textContent = 'Refreshed!';

        setTimeout(() => {
            icon.className = 'ph ph-arrows-clockwise';
            span.textContent = 'Refresh';
            refreshBtn.disabled = false;
        }, 2000);

    } catch (error) {
        console.error('Error refreshing titles:', error);
        alert(`Failed to refresh titles: ${error.message}`);

        // Reset button state
        icon.className = 'ph ph-arrows-clockwise';
        span.textContent = 'Refresh';
        refreshBtn.disabled = false;
    }
}

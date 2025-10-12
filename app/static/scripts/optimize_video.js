/**
 * Optimize Video JavaScript
 * Handles video optimization interface and API interactions
 */

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
    const loadingModal = document.getElementById('loadingModal');

    try {
        // Show loading modal
        loadingModal.style.display = 'flex';

        const response = await fetch(`/optimize-video/api/optimize/${videoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Optimization failed');
        }

        // Hide loading modal
        loadingModal.style.display = 'none';

        // Show results
        displayOptimizationResults(data.data);

        // Reload history
        loadOptimizationHistory();

    } catch (error) {
        console.error('Error optimizing video:', error);
        loadingModal.style.display = 'none';
        alert(`Failed to optimize video: ${error.message}`);
    }
}

/**
 * Display optimization results in modal
 */
function displayOptimizationResults(data) {
    const modal = document.getElementById('resultsModal');
    const body = document.getElementById('resultsBody');

    const videoInfo = data.video_info || {};
    const recommendations = data.recommendations || {};

    body.innerHTML = `
        <!-- Video Info -->
        <div class="result-section">
            <h3><i class="ph ph-video"></i> Video Information</h3>
            <div class="comparison-box">
                <div class="comparison-label">Title</div>
                <div class="comparison-value">${escapeHtml(videoInfo.title || '')}</div>
            </div>
            <div class="video-meta">
                <span><i class="ph ph-eye"></i> ${videoInfo.view_count || '0'} views</span>
                <span><i class="ph ph-thumbs-up"></i> ${videoInfo.like_count || '0'} likes</span>
            </div>
        </div>

        <!-- Title Optimization -->
        <div class="result-section">
            <h3><i class="ph ph-text-aa"></i> Title Optimization</h3>
            <div class="comparison-box">
                <div class="comparison-label">Current Title</div>
                <div class="comparison-value">${escapeHtml(data.current_title || '')}</div>
            </div>
            <div class="comparison-box" style="border: 2px solid #10B981;">
                <div class="comparison-label" style="color: #10B981;">✨ Optimized Title</div>
                <div class="comparison-value">${escapeHtml(data.optimized_title || '')}</div>
            </div>
        </div>

        <!-- Description Optimization -->
        <div class="result-section">
            <h3><i class="ph ph-align-left"></i> Description Optimization</h3>
            <div class="comparison-box">
                <div class="comparison-label">Current Description</div>
                <div class="comparison-value" style="max-height: 100px; overflow-y: auto;">${escapeHtml((data.current_description || '').substring(0, 500))}${data.current_description && data.current_description.length > 500 ? '...' : ''}</div>
            </div>
            <div class="comparison-box" style="border: 2px solid #10B981;">
                <div class="comparison-label" style="color: #10B981;">✨ Optimized Description</div>
                <div class="comparison-value" style="max-height: 100px; overflow-y: auto;">${escapeHtml((data.optimized_description || '').substring(0, 500))}${data.optimized_description && data.optimized_description.length > 500 ? '...' : ''}</div>
            </div>
        </div>

        <!-- Tags Optimization -->
        <div class="result-section">
            <h3><i class="ph ph-hash"></i> Tags Optimization</h3>
            <div class="comparison-box">
                <div class="comparison-label">Current Tags</div>
                <div class="tags-list">
                    ${(data.current_tags || []).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                </div>
            </div>
            <div class="comparison-box" style="border: 2px solid #10B981;">
                <div class="comparison-label" style="color: #10B981;">✨ Optimized Tags</div>
                <div class="tags-list">
                    ${(data.optimized_tags || []).slice(0, 15).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                </div>
            </div>
        </div>

        <!-- Thumbnail Analysis -->
        ${data.thumbnail_analysis ? `
        <div class="result-section">
            <h3><i class="ph ph-image"></i> Thumbnail Analysis</h3>
            <div class="comparison-box">
                <div class="recommendations-text">${formatMarkdown(data.thumbnail_analysis)}</div>
            </div>
        </div>
        ` : ''}

        <!-- Overall Recommendations -->
        ${recommendations.overview ? `
        <div class="result-section">
            <h3><i class="ph ph-lightbulb"></i> Recommendations</h3>
            <div class="comparison-box">
                <div class="recommendations-text">${formatMarkdown(recommendations.overview)}</div>
            </div>
        </div>
        ` : ''}
    `;

    modal.style.display = 'flex';
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
 * Close results modal
 */
function closeResultsModal() {
    const modal = document.getElementById('resultsModal');
    modal.style.display = 'none';
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

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const resultsModal = document.getElementById('resultsModal');
    if (event.target === resultsModal) {
        closeResultsModal();
    }
});

// Close modal on Escape key
window.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeResultsModal();
    }
});

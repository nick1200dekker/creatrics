/**
 * Optimize Video JavaScript
 * Handles video optimization interface and API interactions
 */

// Global state
let currentVideoId = null;
let currentOptimizedDescription = null;
let currentInputMode = 'channel'; // 'channel' or 'url'

// Load videos on page load
document.addEventListener('DOMContentLoaded', function() {
    loadMyVideos();
    loadOptimizationHistory();

    // Check if video_id is in URL params (from homepage)
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('video_id');
    if (videoId) {
        // Auto-optimize the video
        optimizeVideo(videoId);
    }
});

/**
 * Switch between channel and URL input modes
 */
function switchInputMode(mode) {
    currentInputMode = mode;

    // Update toggle buttons
    document.getElementById('channelToggleBtn').classList.toggle('active', mode === 'channel');
    document.getElementById('urlToggleBtn').classList.toggle('active', mode === 'url');

    // Show/hide sections
    if (mode === 'channel') {
        document.getElementById('urlInputSection').style.display = 'none';
        document.getElementById('myVideosGrid').style.display = 'grid';
        document.getElementById('emptyVideos').style.display = document.getElementById('myVideosGrid').children.length === 0 ? 'flex' : 'none';
    } else {
        document.getElementById('urlInputSection').style.display = 'block';
        document.getElementById('myVideosGrid').style.display = 'none';
        document.getElementById('emptyVideos').style.display = 'none';
    }
}

/**
 * Extract video ID from URL or return as-is if already an ID
 */
function extractVideoId(input) {
    input = input.trim();

    // If it's already just an ID (11 characters, alphanumeric)
    if (/^[a-zA-Z0-9_-]{11}$/.test(input)) {
        return input;
    }

    // Try to extract from various YouTube URL formats
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/
    ];

    for (const pattern of patterns) {
        const match = input.match(pattern);
        if (match && match[1]) {
            return match[1];
        }
    }

    return null;
}

/**
 * Optimize video from URL input
 */
async function optimizeFromUrl() {
    const input = document.getElementById('videoUrlInput').value.trim();

    if (!input) {
        showToast('Please enter a YouTube URL or video ID', 'error');
        return;
    }

    const videoId = extractVideoId(input);

    if (!videoId) {
        showToast('Invalid YouTube URL or video ID', 'error');
        return;
    }

    // Optimize the video
    optimizeVideo(videoId);
}

/**
 * Format timestamp to human-readable format
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';

    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    const diffMonths = Math.floor(diffDays / 30);
    const diffYears = Math.floor(diffDays / 365);

    if (diffMins < 1) {
        return 'Just now';
    } else if (diffMins < 60) {
        return `${diffMins} min${diffMins !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
        return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
        return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 30) {
        const weeks = Math.floor(diffDays / 7);
        return `${weeks} week${weeks !== 1 ? 's' : ''} ago`;
    } else if (diffMonths < 12) {
        return `${diffMonths} month${diffMonths !== 1 ? 's' : ''} ago`;
    } else {
        return `${diffYears} year${diffYears !== 1 ? 's' : ''} ago`;
    }
}

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
            emptyState.style.display = 'flex';
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
                        <span class="stat">
                            <i class="ph ph-eye"></i>
                            ${video.view_count}
                        </span>
                        <span class="stat">
                            <i class="ph ph-clock"></i>
                            ${formatTimestamp(video.published_time)}
                        </span>
                    </div>
                </div>
            </div>
        `).join('');

        emptyState.style.display = 'none';

    } catch (error) {
        console.error('Error loading videos:', error);
        grid.innerHTML = '';
        emptyState.innerHTML = `
            <i class="ph ph-warning"></i>
            <p>Failed to load videos</p>
            <span>${escapeHtml(error.message)}</span>
        `;
        emptyState.style.display = 'flex';
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
            emptyState.style.display = 'flex';
            return;
        }

        emptyState.style.display = 'none';

        // Render history using video-card style (matching analyze_video)
        grid.innerHTML = history.map(item => {
            const videoInfo = item.video_info || {};
            const optimizedAt = item.optimized_at ? new Date(item.optimized_at) : null;
            
            // Format time ago
            let timeAgo = '';
            if (optimizedAt) {
                const now = new Date();
                const diffMs = now - optimizedAt;
                const diffMins = Math.floor(diffMs / 60000);
                const diffHours = Math.floor(diffMs / 3600000);
                const diffDays = Math.floor(diffMs / 86400000);

                if (diffMins < 1) {
                    timeAgo = 'Just now';
                } else if (diffMins < 60) {
                    timeAgo = `${diffMins} min${diffMins !== 1 ? 's' : ''} ago`;
                } else if (diffHours < 24) {
                    timeAgo = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
                } else if (diffDays < 7) {
                    timeAgo = `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
                } else {
                    // Format as "Dec 25, 2024"
                    timeAgo = optimizedAt.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                    });
                }
            }

            return `
                <div class="history-item" onclick="showOptimizationResults('${item.video_id}')">
                    <div class="history-thumbnail">
                        <img src="${videoInfo.thumbnail || ''}" alt="${escapeHtml(videoInfo.title || '')}" loading="lazy">
                    </div>
                    <div class="history-info">
                        <h4 class="history-title">${escapeHtml(videoInfo.title || item.current_title || 'Untitled')}</h4>
                        <div class="history-meta">
                            <span class="stat">
                                <i class="ph ph-calendar"></i>
                                ${timeAgo}
                            </span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading history:', error);
        emptyState.style.display = 'flex';
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
        console.log('Title suggestions received:', data.data?.title_suggestions);

        if (!data.success) {
            throw new Error(data.error || 'Optimization failed');
        }

        if (!data.data) {
            throw new Error('No optimization data received from server');
        }

        // Display results immediately
        console.log('Displaying results with titles:', data.data.title_suggestions);
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
                                ${formatTimestamp(videoInfo.published_time)}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Title Suggestions -->
            <div class="result-card">
                <div class="section-header">
                    <h3 class="section-title" style="margin: 0; padding: 0; border: none;">
                        <i class="ph ph-text-aa"></i>
                        Title Suggestions
                    </h3>
                    <button class="refresh-titles-btn" onclick="refreshTitles()" id="refreshTitlesBtn">
                        <i class="ph ph-arrows-clockwise"></i>
                        <span>Refresh</span>
                    </button>
                </div>
                <div class="comparison-box current-box">
                    <div class="comparison-label">Current Title</div>
                    <div class="comparison-value">${escapeHtml(data.current_title || videoInfo.title || '')}</div>
                </div>
                <div class="suggestions-list" id="titleSuggestionsList">
                    ${titleSuggestions.map((title, index) => `
                        <div class="suggestion-item">
                            <div class="suggestion-number">${index + 1}</div>
                            <div class="suggestion-text">${escapeHtml(title)}</div>
                            <button class="apply-btn-icon" onclick="applyTitle(this, \`${escapeHtml(title).replace(/`/g, '\\`').replace(/'/g, "\\'")}\`)" title="Apply to YouTube">
                                <i class="ph ph-youtube-logo"></i>
                            </button>
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
                        <div class="action-btns">
                            <button class="apply-btn-icon" onclick="applyDescription(this)" title="Apply to YouTube">
                                <i class="ph ph-youtube-logo"></i>
                            </button>
                            <button class="copy-btn-small" onclick="copyDescription(this)">
                                <i class="ph ph-copy"></i>
                                Copy
                            </button>
                        </div>
                    </div>
                    <div class="comparison-value description-text" id="optimizedDescription">${escapeHtml(data.optimized_description || '')}</div>
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
                            <div class="action-btns">
                                <button class="apply-btn-icon" onclick="applyTags(this)" title="Apply to YouTube">
                                    <i class="ph ph-youtube-logo"></i>
                                </button>
                                <button class="copy-btn-small" onclick="copyAllTags(this)">
                                    <i class="ph ph-copy"></i>
                                    Copy All
                                </button>
                            </div>
                        </div>
                        <div class="tags-list" id="optimizedTagsList">
                            ${(data.optimized_tags || []).slice(0, 30).map(tag => `<span class="tag tag-optimized">${escapeHtml(tag)}</span>`).join('')}
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
        </div>
    `;

    resultsSection.innerHTML = html;

    // Store optimized data globally for copying
    window.optimizedTags = data.optimized_tags || [];
    currentOptimizedDescription = data.optimized_description || '';
}

/**
 * Back to videos list
 */
function backToVideos() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('videosListSection').style.display = 'block';

    // Reload videos from RapidAPI to get fresh data
    loadMyVideos();
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
 * Show toast notification
 */
function showToast(message) {
    // Remove existing toast if any
    const existingToast = document.querySelector('.copy-toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast
    const toast = document.createElement('div');
    toast.className = 'copy-toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    // Remove after 2 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
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

        showToast('Copied to clipboard!');

        setTimeout(() => {
            icon.className = originalClass;
            button.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy');
    });
}

/**
 * Copy description to clipboard
 */
function copyDescription(button) {
    if (!currentOptimizedDescription) {
        showToast('No description to copy');
        return;
    }

    navigator.clipboard.writeText(currentOptimizedDescription).then(() => {
        const icon = button.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'ph ph-check';
        button.style.color = '#10B981';

        showToast('Description copied to clipboard!');

        setTimeout(() => {
            icon.className = originalClass;
            button.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy description');
    });
}

/**
 * Copy all optimized tags
 */
function copyAllTags(button) {
    const tags = window.optimizedTags || [];
    if (tags.length === 0) {
        showToast('No tags to copy');
        return;
    }

    const tagsText = tags.join(', ');

    navigator.clipboard.writeText(tagsText).then(() => {
        const icon = button.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'ph ph-check';
        button.style.color = '#10B981';

        showToast(`${tags.length} tags copied to clipboard!`);

        setTimeout(() => {
            icon.className = originalClass;
            button.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy tags:', err);
        showToast('Failed to copy tags');
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

        console.log('Refresh titles response:', data);

        if (!data.success) {
            throw new Error(data.error || 'Failed to refresh titles');
        }

        // Update the title suggestions list
        const titlesList = document.getElementById('titleSuggestionsList');
        if (!titlesList) {
            throw new Error('Title suggestions list element not found');
        }

        const newTitles = data.title_suggestions || [];
        console.log('New titles:', newTitles);

        if (newTitles.length === 0) {
            throw new Error('No titles received from server');
        }

        titlesList.innerHTML = newTitles.map((title, index) => `
            <div class="suggestion-item">
                <div class="suggestion-number">${index + 1}</div>
                <div class="suggestion-text">${escapeHtml(title)}</div>
                <button class="apply-btn-icon" onclick="applyTitle(this, \`${escapeHtml(title).replace(/`/g, '\\`').replace(/'/g, "\\'")}\`)" title="Apply to YouTube">
                    <i class="ph ph-youtube-logo"></i>
                </button>
                <button class="copy-btn" onclick="copyToClipboard(this, \`${escapeHtml(title).replace(/`/g, '\\`')}\`)">
                    <i class="ph ph-copy"></i>
                </button>
            </div>
        `).join('');

        console.log('Titles updated in UI');

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

/**
 * Apply title to YouTube
 */
async function applyTitle(button, title) {
    if (!currentVideoId) {
        showToast('No video selected');
        return;
    }

    const icon = button.querySelector('i');
    const originalIconClass = icon.className;

    if (!confirm(`Apply this title to YouTube?\n\n"${title}"`)) {
        return;
    }

    try {
        button.disabled = true;
        icon.className = 'ph ph-spinner spin';

        const response = await fetch(`/optimize-video/api/apply-optimizations/${currentVideoId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: title})
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to apply title');
        }

        icon.className = 'ph ph-check';
        button.style.background = '#10B981';
        button.style.color = '#fff';
        showToast('✅ Title updated on YouTube!');

        setTimeout(() => {
            button.disabled = true;
        }, 2000);

    } catch (error) {
        console.error('Error applying title:', error);
        showToast('❌ Failed to apply title: ' + error.message);
        icon.className = originalIconClass;
        button.disabled = false;
    }
}

/**
 * Apply description to YouTube
 */
async function applyDescription(button) {
    if (!currentVideoId) {
        showToast('No video selected');
        return;
    }

    if (!currentOptimizedDescription) {
        showToast('No description to apply');
        return;
    }

    const icon = button.querySelector('i');
    const originalIconClass = icon.className;

    if (!confirm('Apply this description to YouTube?')) {
        return;
    }

    try {
        button.disabled = true;
        icon.className = 'ph ph-spinner spin';

        const response = await fetch(`/optimize-video/api/apply-optimizations/${currentVideoId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({description: currentOptimizedDescription})
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to apply description');
        }

        icon.className = 'ph ph-check';
        button.style.background = '#10B981';
        button.style.color = '#fff';
        showToast('✅ Description updated on YouTube!');

        setTimeout(() => {
            button.disabled = true;
        }, 2000);

    } catch (error) {
        console.error('Error applying description:', error);
        showToast('❌ Failed to apply description: ' + error.message);
        icon.className = originalIconClass;
        button.disabled = false;
    }
}

/**
 * Apply tags to YouTube
 */
async function applyTags(button) {
    if (!currentVideoId) {
        showToast('No video selected');
        return;
    }

    const tags = window.optimizedTags || [];
    if (tags.length === 0) {
        showToast('No tags to apply');
        return;
    }

    const icon = button.querySelector('i');
    const originalIconClass = icon.className;

    if (!confirm(`Apply ${tags.length} tags to YouTube?`)) {
        return;
    }

    try {
        button.disabled = true;
        icon.className = 'ph ph-spinner spin';

        const response = await fetch(`/optimize-video/api/apply-optimizations/${currentVideoId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tags: tags})
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to apply tags');
        }

        icon.className = 'ph ph-check';
        button.style.background = '#10B981';
        button.style.color = '#fff';
        showToast('✅ Tags updated on YouTube!');

        setTimeout(() => {
            button.disabled = true;
        }, 2000);

    } catch (error) {
        console.error('Error applying tags:', error);
        showToast('❌ Failed to apply tags: ' + error.message);
        icon.className = originalIconClass;
        button.disabled = false;
    }
}
// Analyze Video Page JavaScript

// State
let currentInputView = 'search';
let currentContentType = 'videos';
let currentSortBy = 'relevance';

// Function to reset all cards
function resetAllCards() {
    const allCards = document.querySelectorAll('.video-card');
    allCards.forEach(card => {
        card.style.opacity = '1';
        card.style.pointerEvents = 'auto';

        const loadingDiv = card.querySelector('.video-card-loading');
        const contentDiv = card.querySelector('.video-card-content');

        if (loadingDiv) {
            loadingDiv.style.display = 'none';
        }
        if (contentDiv) {
            contentDiv.style.display = 'block';
        }
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadHistory();
    // Hide loading modal on page load (in case user navigated back)
    hideLoading();
    // Reset all video cards
    resetAllCards();
});

// Handle back button navigation - this fires when page is shown from cache
window.addEventListener('pageshow', function(event) {
    // If page is loaded from cache (back/forward button)
    if (event.persisted) {
        hideLoading();
        resetAllCards();
    }
});

// Switch input view (URL or Search)
function switchInputView(view) {
    currentInputView = view;

    // Update toggle buttons
    document.getElementById('urlToggleBtn').classList.toggle('active', view === 'url');
    document.getElementById('searchToggleBtn').classList.toggle('active', view === 'search');

    // Update views
    document.getElementById('urlInputView').style.display = view === 'url' ? 'block' : 'none';
    document.getElementById('searchInputView').style.display = view === 'search' ? 'block' : 'none';

    // Show/hide content type toggle (Videos/Shorts) - only for search mode
    const contentTypeToggle = document.getElementById('contentTypeToggle');
    if (view === 'search') {
        contentTypeToggle.style.display = 'block';
    } else {
        contentTypeToggle.style.display = 'none';
    }
}

// Switch content type (Videos or Shorts)
function switchContentType(type) {
    currentContentType = type;

    // Update toggle buttons
    document.getElementById('videosToggleBtn').classList.toggle('active', type === 'videos');
    document.getElementById('shortsToggleBtn').classList.toggle('active', type === 'shorts');

    // Update placeholder in search
    const searchInput = document.getElementById('searchQuery');
    if (type === 'shorts') {
        searchInput.placeholder = 'Search for shorts...';
        // Hide sort toggle for shorts since it doesn't work properly
        document.getElementById('sortToggle').style.display = 'none';
    } else {
        searchInput.placeholder = 'Search for videos...';
        // Show sort toggle for videos
        document.getElementById('sortToggle').style.display = 'flex';
    }
}

// Switch sort by (Relevance or Upload Date)
function switchSortBy(sortBy) {
    currentSortBy = sortBy;

    // Update toggle buttons
    document.getElementById('relevanceSortBtn').classList.toggle('active', sortBy === 'relevance');
    document.getElementById('dateSortBtn').classList.toggle('active', sortBy === 'date');
}

// Detect if URL is a short
function isShortUrl(url) {
    return url.includes('/shorts/') || url.includes('youtube.com/shorts');
}

// Analyze from URL
async function analyzeFromUrl() {
    const urlInput = document.getElementById('videoUrl');
    const url = urlInput.value.trim();

    if (!url) {
        alert('Please enter a YouTube URL');
        return;
    }

    try {
        // Show loading
        showLoading();

        // Detect if it's a short
        const isShort = isShortUrl(url);

        // Extract video ID from URL
        const response = await fetch('/api/analyze-video/extract-id', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url, is_short: isShort })
        });

        const data = await response.json();

        if (data.success) {
            // Navigate to analysis page with is_short parameter
            const queryParam = data.is_short ? '?is_short=true' : '';
            window.location.href = `/analyze-video/video/${data.video_id}${queryParam}`;
        } else {
            hideLoading();
            alert(data.error || 'Invalid YouTube URL');
        }
    } catch (error) {
        hideLoading();
        console.error('Error:', error);
        alert('Failed to analyze video. Please try again.');
    }
}

// Search for videos
async function searchVideos() {
    const searchInput = document.getElementById('searchQuery');
    const query = searchInput.value.trim();

    if (!query) {
        alert('Please enter a search query');
        return;
    }

    try {
        // Show loading in button
        const searchBtn = document.querySelector('.search-btn');
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Searching...';

        // Show loading state in results section
        const resultsSection = document.getElementById('searchResults');
        const resultsGrid = document.getElementById('searchResultsGrid');
        resultsSection.style.display = 'block';
        resultsGrid.innerHTML = `
            <div class="search-loading-state">
                <div class="loading-spinner">
                    <i class="ph ph-spinner spin"></i>
                    <span class="loading-text">Searching for videos...</span>
                </div>
            </div>
        `;

        // Pass content type (videos or shorts) and sort order
        const response = await fetch(`/api/analyze-video/search?query=${encodeURIComponent(query)}&type=${currentContentType}&sort_by=${currentSortBy}`);
        const data = await response.json();

        if (data.success) {
            displaySearchResults(data.videos);
        } else {
            alert(data.error || 'Search failed');
            resultsSection.style.display = 'none';
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Search failed. Please try again.');
        document.getElementById('searchResults').style.display = 'none';
    } finally {
        // Reset button
        const searchBtn = document.querySelector('.search-btn');
        searchBtn.disabled = false;
        searchBtn.innerHTML = '<i class="ph ph-magnifying-glass"></i> Search';
    }
}

// Display search results
function displaySearchResults(videos) {
    const resultsSection = document.getElementById('searchResults');
    const resultsGrid = document.getElementById('searchResultsGrid');

    if (!videos || videos.length === 0) {
        resultsSection.style.display = 'none';
        return;
    }

    resultsGrid.innerHTML = videos.map(video => `
        <div class="video-card" onclick="analyzeVideoWithLoader(this, '${video.video_id}', ${video.is_short || false})" data-video-id="${video.video_id}">
            <div class="video-card-thumbnail">
                ${video.thumbnail ?
                    `<img src="${video.thumbnail}" alt="${escapeHtml(video.title)}" loading="lazy">` :
                    '<div style="width: 100%; height: 100%; background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center;"><i class="ph ph-video" style="font-size: 3rem; color: var(--text-tertiary);"></i></div>'
                }
            </div>
            <div class="video-card-loading" style="display: none;">
                <i class="ph ph-spinner spin"></i>
                <span>Analyzing...</span>
            </div>
            <div class="video-card-content">
                <h4 class="video-card-title">${escapeHtml(video.title)}</h4>
                <p class="video-card-channel">${escapeHtml(video.channel_title)}</p>
                <div class="video-card-meta">
                    <span>${video.view_count_text}</span>
                    ${video.published_time ? `<span>${video.published_time}</span>` : ''}
                </div>
            </div>
        </div>
    `).join('');

    resultsSection.style.display = 'block';

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Analyze video with card-specific loader
async function analyzeVideoWithLoader(cardElement, videoId, isShort = false) {
    // Grey out all other cards
    const allCards = document.querySelectorAll('.video-card');
    allCards.forEach(card => {
        if (card !== cardElement) {
            card.style.opacity = '0.4';
            card.style.pointerEvents = 'none';
        }
    });

    // Show loading spinner on the clicked card
    const loadingDiv = cardElement.querySelector('.video-card-loading');
    const contentDiv = cardElement.querySelector('.video-card-content');
    if (loadingDiv && contentDiv) {
        loadingDiv.style.display = 'flex';
        contentDiv.style.display = 'none';
    }

    try {
        // Pre-check before navigating
        const response = await fetch(`/api/analyze-video/pre-check/${videoId}?is_short=${isShort}`);
        const data = await response.json();

        if (data.success && !data.can_proceed && data.reason === 'insufficient_credits') {
            // Reset cards
            resetAllCards();
            // Show insufficient credits inline
            showInsufficientCreditsInline();
            return;
        }

        // Navigate to analysis
        const queryParam = isShort ? '?is_short=true' : '';
        window.location.href = `/analyze-video/video/${videoId}${queryParam}`;
    } catch (error) {
        console.error('Error:', error);
        resetAllCards();
        alert('Failed to check analysis. Please try again.');
    }
}

// Analyze video (fallback for direct calls)
async function analyzeVideo(videoId, isShort = false) {
    showLoading();

    try {
        // Pre-check before navigating
        const response = await fetch(`/api/analyze-video/pre-check/${videoId}?is_short=${isShort}`);
        const data = await response.json();

        if (data.success && !data.can_proceed && data.reason === 'insufficient_credits') {
            hideLoading();
            showInsufficientCreditsInline();
            return;
        }

        // Navigate to analysis
        const queryParam = isShort ? '?is_short=true' : '';
        window.location.href = `/analyze-video/video/${videoId}${queryParam}`;
    } catch (error) {
        hideLoading();
        console.error('Error:', error);
        alert('Failed to check analysis. Please try again.');
    }
}

// Show insufficient credits inline
function showInsufficientCreditsInline() {
    // Hide search results if visible
    const searchResults = document.getElementById('searchResults');
    if (searchResults) {
        searchResults.style.display = 'none';
    }

    // Show in history section
    const historyGrid = document.getElementById('historyGrid');
    const emptyHistory = document.getElementById('emptyHistory');

    if (historyGrid && emptyHistory) {
        historyGrid.style.display = 'none';
        emptyHistory.style.display = 'flex';
        emptyHistory.innerHTML = `
            <div class="insufficient-credits-card" style="max-width: 500px; margin: 3rem auto;">
                <div class="credit-icon-wrapper">
                    <i class="ph ph-coins"></i>
                </div>
                <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Insufficient Credits</h3>
                <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">
                    You don't have enough credits to use this feature.
                </p>
                <a href="/payment" class="upgrade-plan-btn">
                    <i class="ph ph-crown"></i>
                    Upgrade Plan
                </a>
            </div>
        `;

        // Scroll to it
        emptyHistory.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// Load history
async function loadHistory() {
    try {
        // Show loading state
        const historyGrid = document.getElementById('historyGrid');
        const emptyHistory = document.getElementById('emptyHistory');

        historyGrid.style.display = 'grid';
        emptyHistory.style.display = 'none';
        historyGrid.innerHTML = `
            <div class="search-loading-state">
                <div class="loading-spinner">
                    <i class="ph ph-spinner spin"></i>
                    <span class="loading-text">Loading history...</span>
                </div>
            </div>
        `;

        const response = await fetch('/api/analyze-video/history');
        const data = await response.json();

        if (data.success) {
            displayHistory(data.history);
        }
    } catch (error) {
        console.error('Error loading history:', error);
        // Show empty state on error
        const historyGrid = document.getElementById('historyGrid');
        const emptyHistory = document.getElementById('emptyHistory');
        historyGrid.style.display = 'none';
        emptyHistory.style.display = 'flex';
    }
}

// Display history
function displayHistory(history) {
    const historyGrid = document.getElementById('historyGrid');
    const emptyHistory = document.getElementById('emptyHistory');

    if (!history || history.length === 0) {
        historyGrid.style.display = 'none';
        emptyHistory.style.display = 'flex';
        return;
    }

    historyGrid.style.display = 'grid';
    emptyHistory.style.display = 'none';

    historyGrid.innerHTML = history.map(item => {
        // Format time ago
        const analyzedDate = new Date(item.analyzed_at);
        const now = new Date();
        const diffMs = now - analyzedDate;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        let timeAgo;
        if (diffMins < 1) {
            timeAgo = 'Just now';
        } else if (diffMins < 60) {
            timeAgo = `${diffMins} min${diffMins !== 1 ? 's' : ''} ago`;
        } else if (diffHours < 24) {
            timeAgo = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        } else if (diffDays < 7) {
            timeAgo = `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
        } else {
            timeAgo = analyzedDate.toLocaleDateString();
        }

        return `
            <div class="video-card" onclick="analyzeVideoWithLoader(this, '${item.video_id}', ${item.is_short || false})" data-video-id="${item.video_id}">
                <div class="video-card-thumbnail">
                    ${item.thumbnail ?
                        `<img src="${item.thumbnail}" alt="${escapeHtml(item.title)}" loading="lazy">` :
                        '<div style="width: 100%; height: 100%; background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center;"><i class="ph ph-video" style="font-size: 3rem; color: var(--text-tertiary);"></i></div>'
                    }
                </div>
                <div class="video-card-loading" style="display: none;">
                    <i class="ph ph-spinner spin"></i>
                    <span>Analyzing...</span>
                </div>
                <div class="video-card-content">
                    <h4 class="video-card-title">${escapeHtml(item.title)}</h4>
                    <p class="video-card-channel">${escapeHtml(item.channel_title)}</p>
                    <div class="video-card-meta">
                        <span>${item.view_count}</span>
                        <span>${timeAgo}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Show loading modal
function showLoading() {
    document.getElementById('loadingModal').style.display = 'flex';
}

// Hide loading modal
function hideLoading() {
    document.getElementById('loadingModal').style.display = 'none';
}

// Escape HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text ? text.replace(/[&<>"']/g, m => map[m]) : '';
}

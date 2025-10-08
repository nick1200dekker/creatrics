// Analyze Video Page JavaScript

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadHistory();
});

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

        // Extract video ID from URL
        const response = await fetch('/api/analyze-video/extract-id', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (data.success) {
            // Navigate to analysis page
            window.location.href = `/analyze-video/video/${data.video_id}`;
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
        // Show loading
        const searchBtn = document.querySelector('.search-btn');
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Searching...';

        const response = await fetch(`/api/analyze-video/search?query=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (data.success) {
            displaySearchResults(data.videos);
        } else {
            alert(data.error || 'Search failed');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Search failed. Please try again.');
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
        <div class="video-card" onclick="analyzeVideo('${video.video_id}')">
            <div class="video-card-thumbnail">
                ${video.thumbnail ?
                    `<img src="${video.thumbnail}" alt="${escapeHtml(video.title)}" loading="lazy">` :
                    '<div style="width: 100%; height: 100%; background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center;"><i class="ph ph-video" style="font-size: 3rem; color: var(--text-tertiary);"></i></div>'
                }
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

// Analyze video
function analyzeVideo(videoId) {
    showLoading();
    window.location.href = `/analyze-video/video/${videoId}`;
}

// Load history
async function loadHistory() {
    try {
        const response = await fetch('/api/analyze-video/history');
        const data = await response.json();

        if (data.success) {
            displayHistory(data.history);
        }
    } catch (error) {
        console.error('Error loading history:', error);
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
            <div class="video-card" onclick="analyzeVideo('${item.video_id}')">
                <div class="video-card-thumbnail">
                    ${item.thumbnail ?
                        `<img src="${item.thumbnail}" alt="${escapeHtml(item.title)}" loading="lazy">` :
                        '<div style="width: 100%; height: 100%; background: var(--bg-tertiary); display: flex; align-items: center; justify-content: center;"><i class="ph ph-video" style="font-size: 3rem; color: var(--text-tertiary);"></i></div>'
                    }
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

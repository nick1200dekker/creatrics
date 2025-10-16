/**
 * TikTok Trend Finder JavaScript
 * Handles search, video display, and viral potential visualization
 */

// Global state
let currentSearchMode = 'top'; // 'top' or 'video'
let currentSortMode = 'views'; // 'views' or 'date'
let currentVideos = []; // Store current videos for re-sorting

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Enter key support in search input
    document.getElementById('keywordInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchTrends();
        }
    });
});

/**
 * Set search mode (top or video)
 */
function setSearchMode(mode) {
    currentSearchMode = mode;

    // Update button states
    document.getElementById('topModeBtn').classList.toggle('active', mode === 'top');
    document.getElementById('videoModeBtn').classList.toggle('active', mode === 'video');
}

/**
 * Set sort mode (views or date)
 */
function setSortMode(mode) {
    currentSortMode = mode;

    // Update button states
    document.getElementById('viewsSortBtn').classList.toggle('active', mode === 'views');
    document.getElementById('dateSortBtn').classList.toggle('active', mode === 'date');

    // Re-sort and display current videos if we have any
    if (currentVideos.length > 0) {
        const sortedVideos = sortVideos(currentVideos, mode);
        displayVideos(sortedVideos);
    }
}

/**
 * Sort videos by mode
 */
function sortVideos(videos, mode) {
    const sorted = [...videos];
    if (mode === 'date') {
        sorted.sort((a, b) => b.createTime - a.createTime);
    } else {
        sorted.sort((a, b) => b.playCount - a.playCount);
    }
    return sorted;
}

/**
 * Quick search from example chips
 */
function quickSearch(keyword) {
    document.getElementById('keywordInput').value = keyword;
    searchTrends();
}

/**
 * Main search function
 */
async function searchTrends() {
    const keyword = document.getElementById('keywordInput').value.trim();

    if (!keyword) {
        alert('Please enter a keyword');
        return;
    }

    // Show loading state
    showLoading();

    const searchBtn = document.getElementById('searchBtn');
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<i class="ph ph-spinner spin"></i><span>Analyzing...</span>';

    try {
        const response = await fetch('/trend-finder/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                keyword,
                mode: currentSearchMode,
                sort: currentSortMode
            })
        });

        if (!response.ok) {
            throw new Error('Failed to fetch trends');
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to analyze trends');
        }

        // Display results
        displayResults(data.result);

    } catch (error) {
        console.error('Search error:', error);
        alert(error.message || 'Failed to search trends');
        showEmptyState();
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = '<i class="ph ph-sparkle"></i><span>Analyze Trends</span>';
    }
}

/**
 * Display search results
 */
function displayResults(result) {
    // Hide loading and empty state
    document.getElementById('loadingContainer').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';

    // Show results section
    document.getElementById('resultsSection').style.display = 'block';

    // Update score panel
    document.getElementById('totalScoreValue').textContent = result.total_score || 0;
    document.getElementById('totalScoreBar').style.width = `${result.total_score || 0}%`;

    document.getElementById('hotScoreValue').textContent = result.hot_score || 0;
    document.getElementById('hotScoreBar').style.width = `${result.hot_score || 0}%`;

    document.getElementById('engagementScoreValue').textContent = result.engagement_score || 0;
    document.getElementById('engagementScoreBar').style.width = `${result.engagement_score || 0}%`;

    // Update trend summary
    document.getElementById('trendSummary').textContent = result.trend_summary;

    // Store and display videos
    currentVideos = result.analyzed_videos;
    displayVideos(currentVideos);

    // Scroll to results
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

/**
 * Display video cards
 */
function displayVideos(videos) {
    const grid = document.getElementById('videosGrid');
    grid.innerHTML = '';

    if (!videos || videos.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 2rem;">No videos found</p>';
        return;
    }

    videos.forEach(video => {
        const card = createVideoCard(video);
        grid.appendChild(card);
    });
}

/**
 * Create a video card element
 */
function createVideoCard(video) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.onclick = () => openVideoModal(video);

    // Determine viral score class
    let scoreClass = 'low';
    if (video.viral_potential >= 80) {
        scoreClass = 'excellent';
    } else if (video.viral_potential >= 65) {
        scoreClass = 'good';
    } else if (video.viral_potential >= 50) {
        scoreClass = 'medium';
    }

    // Format numbers
    const views = formatNumber(video.playCount);
    const likes = formatNumber(video.diggCount);
    const comments = formatNumber(video.commentCount);

    // Build hashtags HTML
    let hashtagsHTML = '';
    if (video.challenges && video.challenges.length > 0) {
        hashtagsHTML = '<div class="video-hashtags">';
        video.challenges.slice(0, 3).forEach(tag => {
            hashtagsHTML += `<span class="hashtag">#${escapeHtml(tag.title)}</span>`;
        });
        hashtagsHTML += '</div>';
    }

    card.innerHTML = `
        <div class="video-thumbnail">
            <img src="${video.video.cover}" alt="Video thumbnail">
            <div class="video-overlay">
                <div class="play-icon">
                    <i class="ph ph-play-fill"></i>
                </div>
                <div class="video-stats-overlay">
                    <div class="stat-overlay">
                        <i class="ph ph-eye"></i>
                        <span>${views}</span>
                    </div>
                    <div class="stat-overlay">
                        <i class="ph ph-heart"></i>
                        <span>${likes}</span>
                    </div>
                </div>
            </div>
        </div>
        <div class="video-content">
            <div class="video-header">
                <div class="viral-score ${scoreClass}">${video.viral_potential}/100</div>
                <div class="trend-badge ${video.trend_status}">${video.trend_status}</div>
            </div>
            <div class="video-desc">${escapeHtml(video.desc)}</div>
            <div class="video-meta">
                <div class="video-meta-row">
                    <div class="video-author">
                        <span>@${escapeHtml(video.author.uniqueId)}</span>
                    </div>
                    <span>${video.age_display}</span>
                </div>
                <div class="video-meta-row">
                    <span>${formatNumber(video.views_per_hour)} views/hr</span>
                    <span>${video.engagement_rate}% engagement</span>
                </div>
            </div>
            ${hashtagsHTML}
        </div>
    `;

    return card;
}

/**
 * Open video in modal
 */
function openVideoModal(video) {
    // Open TikTok video in new tab using video ID
    const videoId = video.id;
    const authorId = video.author.uniqueId;

    if (videoId && authorId) {
        // Open TikTok video directly on TikTok
        const tiktokUrl = `https://www.tiktok.com/@${authorId}/video/${videoId}`;
        window.open(tiktokUrl, '_blank');
    } else {
        alert('Video information not available');
    }
}

/**
 * Show loading state
 */
function showLoading() {
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('loadingContainer').style.display = 'flex';
}

/**
 * Show empty state
 */
function showEmptyState() {
    document.getElementById('loadingContainer').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    if (!num && num !== 0) return '0';
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
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
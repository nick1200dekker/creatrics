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
        const response = await fetch('/tiktok-keyword-research/api/search', {
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

    // Display aggregated insights
    displayAggregatedInsights(result.analyzed_videos);

    // Scroll to results
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

/**
 * Display aggregated insights from analyzed videos
 */
function displayAggregatedInsights(videos) {
    const container = document.getElementById('insightsContainer');

    if (!videos || videos.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 2rem;">No data available</p>';
        return;
    }

    // Calculate aggregated metrics
    const totalVideos = videos.length;
    const totalViews = videos.reduce((sum, v) => sum + (v.playCount || 0), 0);
    const totalLikes = videos.reduce((sum, v) => sum + (v.diggCount || 0), 0);
    const totalComments = videos.reduce((sum, v) => sum + (v.commentCount || 0), 0);
    const totalShares = videos.reduce((sum, v) => sum + (v.shareCount || 0), 0);

    const avgViews = Math.round(totalViews / totalVideos);
    const avgLikes = Math.round(totalLikes / totalVideos);
    const avgComments = Math.round(totalComments / totalVideos);
    const avgEngagement = videos.reduce((sum, v) => sum + (v.engagement_rate || 0), 0) / totalVideos;
    const avgViewsPerHour = videos.reduce((sum, v) => sum + (v.views_per_hour || 0), 0) / totalVideos;

    // Viral potential distribution
    const excellent = videos.filter(v => v.viral_potential >= 80).length;
    const good = videos.filter(v => v.viral_potential >= 65 && v.viral_potential < 80).length;
    const medium = videos.filter(v => v.viral_potential >= 50 && v.viral_potential < 65).length;
    const low = videos.filter(v => v.viral_potential < 50).length;

    // Trend status distribution
    const viral = videos.filter(v => v.trend_status === 'viral').length;
    const trending = videos.filter(v => v.trend_status === 'trending').length;
    const emerging = videos.filter(v => v.trend_status === 'emerging').length;
    const mature = videos.filter(v => v.trend_status === 'mature').length;

    container.innerHTML = `
        <div class="insights-grid">
            <div class="insight-card">
                <i class="ph ph-eye insight-card-icon"></i>
                <div class="insight-card-content">
                    <div class="insight-card-value">${formatNumber(avgViews)}</div>
                    <div class="insight-card-label">Avg Views</div>
                </div>
            </div>

            <div class="insight-card">
                <i class="ph ph-heart insight-card-icon"></i>
                <div class="insight-card-content">
                    <div class="insight-card-value">${formatNumber(avgLikes)}</div>
                    <div class="insight-card-label">Avg Likes</div>
                </div>
            </div>

            <div class="insight-card">
                <i class="ph ph-chat-circle insight-card-icon"></i>
                <div class="insight-card-content">
                    <div class="insight-card-value">${formatNumber(avgComments)}</div>
                    <div class="insight-card-label">Avg Comments</div>
                </div>
            </div>

            <div class="insight-card">
                <i class="ph ph-chart-line insight-card-icon"></i>
                <div class="insight-card-content">
                    <div class="insight-card-value">${avgEngagement.toFixed(2)}%</div>
                    <div class="insight-card-label">Avg Engagement</div>
                </div>
            </div>
        </div>

        <!-- Video List -->
        <div class="video-list-section">
            <h4><i class="ph ph-list-bullets"></i> Video Sample List</h4>
            <div class="video-list">
                ${videos.sort((a, b) => a.age_hours - b.age_hours).map((video, index) => `
                    <div class="video-list-item">
                        <div class="video-list-rank">#${index + 1}</div>
                        <div class="video-list-metrics">
                            <div class="video-list-stats">
                                <div class="video-stat">
                                    <i class="ph ph-eye"></i>
                                    <span>${formatNumber(video.playCount)}</span>
                                </div>
                                <div class="video-stat">
                                    <i class="ph ph-heart"></i>
                                    <span>${formatNumber(video.diggCount)}</span>
                                </div>
                                <div class="video-stat">
                                    <i class="ph ph-chat-circle"></i>
                                    <span>${formatNumber(video.commentCount)}</span>
                                </div>
                            </div>
                            <div class="video-list-performance">
                                <span class="perf-badge">${formatNumber(video.views_per_hour)} views/hr</span>
                                <span class="perf-badge">${video.engagement_rate}% engagement</span>
                                <span class="perf-badge age">${video.age_display}</span>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
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
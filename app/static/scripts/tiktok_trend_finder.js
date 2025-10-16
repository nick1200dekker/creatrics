/**
 * TikTok Trend Finder - JavaScript
 * Handles analysis and display of gaming trends
 */

let isAnalyzing = false;

// Load cached data when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadCachedAnalysis();
});

/**
 * Load cached analysis from database
 */
async function loadCachedAnalysis() {
    try {
        const response = await fetch('/tiktok-trend-finder/api/cached');

        if (!response.ok) {
            console.error('Failed to load cached analysis');
            return;
        }

        const data = await response.json();

        if (data.success && data.cached) {
            // Display cached results
            displayResults(data);
        }
    } catch (error) {
        console.error('Error loading cached analysis:', error);
    }
}

/**
 * Start the trend analysis
 */
async function startAnalysis() {
    if (isAnalyzing) {
        return;
    }

    isAnalyzing = true;

    // Show progress, hide results and empty state
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('progressSection').style.display = 'block';

    // Disable button
    const refreshBtn = document.getElementById('refreshBtn');
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<i class="ph ph-arrow-clockwise spinning"></i> Analyzing...';

    // Reset progress
    updateProgress(0, 'Starting analysis...');

    try {
        // Simulate progress updates
        updateProgress(10, 'Fetching trending hashtags...');

        // Call API
        const response = await fetch('/tiktok-trend-finder/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Failed to analyze trends');
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Analysis failed');
        }

        // Update progress
        updateProgress(100, 'Analysis complete!');

        // Wait a moment before showing results
        await new Promise(resolve => setTimeout(resolve, 500));

        // Display results
        displayResults(data);

    } catch (error) {
        console.error('Error analyzing trends:', error);
        alert('Error: ' + error.message);

        // Show empty state again
        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('emptyState').style.display = 'flex';
    } finally {
        // Re-enable button
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<i class="ph ph-arrow-clockwise"></i> Refresh Analysis';
        isAnalyzing = false;
    }
}

/**
 * Update progress bar
 */
function updateProgress(percent, text) {
    document.getElementById('progressFill').style.width = percent + '%';
    document.getElementById('progressPercent').textContent = percent + '%';
    document.getElementById('progressText').textContent = text;
}

/**
 * Display analysis results
 */
function displayResults(data) {
    // Hide progress and empty state, show results
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';

    // Update stats
    document.getElementById('totalHashtags').textContent = data.total_keywords_fetched || 0;
    document.getElementById('gamingKeywords').textContent = data.gaming_keywords_found || 0;
    document.getElementById('analyzedCount').textContent = data.keywords_analyzed || 0;

    // Populate table
    const tbody = document.getElementById('resultsTableBody');
    tbody.innerHTML = '';

    if (!data.results || data.results.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-results">No results found</td></tr>';
        return;
    }

    data.results.forEach((result, index) => {
        const row = document.createElement('tr');

        // Rank
        const rankCell = document.createElement('td');
        rankCell.className = 'rank-col';
        rankCell.textContent = index + 1;
        row.appendChild(rankCell);

        // Keyword
        const keywordCell = document.createElement('td');
        keywordCell.className = 'keyword-col';
        keywordCell.innerHTML = `<span class="keyword-tag">#${result.keyword}</span>`;
        row.appendChild(keywordCell);

        // Total Score
        const totalScoreCell = document.createElement('td');
        totalScoreCell.className = 'score-col';
        totalScoreCell.innerHTML = createScoreBadge(result.total_score, 'total');
        row.appendChild(totalScoreCell);

        // Hot Score
        const hotScoreCell = document.createElement('td');
        hotScoreCell.className = 'score-col';
        hotScoreCell.innerHTML = createScoreBadge(result.hot_score, 'hot');
        row.appendChild(hotScoreCell);

        // Engagement Score
        const engagementScoreCell = document.createElement('td');
        engagementScoreCell.className = 'score-col';
        engagementScoreCell.innerHTML = createScoreBadge(result.engagement_score, 'engagement');
        row.appendChild(engagementScoreCell);

        // Video Count
        const videosCell = document.createElement('td');
        videosCell.className = 'videos-col';
        videosCell.textContent = formatNumber(result.video_count || 0);
        row.appendChild(videosCell);

        // Avg Views
        const viewsCell = document.createElement('td');
        viewsCell.className = 'views-col';
        viewsCell.textContent = formatNumber(result.avg_views || 0);
        row.appendChild(viewsCell);

        tbody.appendChild(row);
    });
}

/**
 * Create score badge with color coding
 */
function createScoreBadge(score, type) {
    let color;
    if (score >= 80) {
        color = 'high';
    } else if (score >= 60) {
        color = 'medium';
    } else if (score >= 40) {
        color = 'low';
    } else {
        color = 'very-low';
    }

    return `<span class="score-badge ${color}">${score}</span>`;
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

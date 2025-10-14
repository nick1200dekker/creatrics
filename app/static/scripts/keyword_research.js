/**
 * Keyword Research JavaScript
 * Handles keyword exploration with autocomplete and competition analysis
 */

// Global state
let currentKeyword = '';
let keywordHistory = [];
let analysisCache = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Enter key support in search input
    document.getElementById('keywordInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            exploreKeyword();
        }
    });
});

/**
 * Quick explore from example chips
 */
function quickExplore(keyword) {
    document.getElementById('keywordInput').value = keyword;
    exploreKeyword();
}

/**
 * Main function to explore a keyword
 */
async function exploreKeyword(keyword = null) {
    // Get keyword from input or parameter
    const keywordToExplore = keyword || document.getElementById('keywordInput').value.trim();

    if (!keywordToExplore) {
        showError('Please enter a keyword to explore');
        return;
    }

    // Update current keyword
    currentKeyword = keywordToExplore;

    // Add to history if it's a new keyword
    if (!keywordHistory.includes(keywordToExplore)) {
        keywordHistory.push(keywordToExplore);
        updateBreadcrumb();
    }

    // Update input
    document.getElementById('keywordInput').value = keywordToExplore;

    // Show loading state
    showLoading();

    try {
        // Fetch autocomplete suggestions
        const autocompleteResponse = await fetch('/keyword-research/api/autocomplete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: keywordToExplore })
        });

        if (!autocompleteResponse.ok) {
            throw new Error('Failed to fetch suggestions');
        }

        const autocompleteData = await autocompleteResponse.json();

        if (!autocompleteData.success) {
            throw new Error(autocompleteData.error || 'Failed to fetch suggestions');
        }

        const suggestions = autocompleteData.suggestions || [];

        // Analyze the main keyword
        let mainAnalysis = null;

        // Check cache first
        if (analysisCache[keywordToExplore]) {
            mainAnalysis = analysisCache[keywordToExplore];
        } else {
            const analysisResponse = await fetch('/keyword-research/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ keyword: keywordToExplore })
            });

            if (analysisResponse.ok) {
                const analysisData = await analysisResponse.json();
                if (analysisData.success) {
                    mainAnalysis = analysisData.data;
                    analysisCache[keywordToExplore] = mainAnalysis;
                }
            }
        }

        // Batch analyze suggestions (limit to first 15)
        const suggestionsToAnalyze = suggestions.slice(0, 15);
        let analyzedSuggestions = [];

        if (suggestionsToAnalyze.length > 0) {
            const batchResponse = await fetch('/keyword-research/api/batch-analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ keywords: suggestionsToAnalyze })
            });

            if (batchResponse.ok) {
                const batchData = await batchResponse.json();
                if (batchData.success) {
                    analyzedSuggestions = batchData.results;
                    // Cache the results
                    analyzedSuggestions.forEach(result => {
                        analysisCache[result.keyword] = result;
                    });
                }
            }
        }

        // Display results
        displayResults(keywordToExplore, mainAnalysis, analyzedSuggestions);

    } catch (error) {
        console.error('Error exploring keyword:', error);
        showError('Failed to analyze keyword. Please try again.');
    }
}

/**
 * Display results
 */
function displayResults(keyword, mainAnalysis, suggestions) {
    // Hide loading and empty state
    document.getElementById('loadingContainer').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';

    // Show results section
    document.getElementById('resultsSection').style.display = 'block';

    // Display main keyword analysis
    displayMainAnalysis(keyword, mainAnalysis);

    // Display related keywords
    displayRelatedKeywords(suggestions);
}

/**
 * Display main keyword analysis
 */
function displayMainAnalysis(keyword, analysis) {
    document.getElementById('analyzedKeyword').textContent = keyword;

    if (analysis) {
        // Competition level
        const competitionBadges = {
            'low': { text: 'Low Competition', class: 'low' },
            'medium': { text: 'Medium Competition', class: 'medium' },
            'high': { text: 'High Competition', class: 'high' }
        };
        const compBadge = competitionBadges[analysis.competition_level] || competitionBadges.medium;
        document.getElementById('competitionLevel').textContent = compBadge.text;

        // Interest level
        const interestBadges = {
            'high': '🔥 High Interest',
            'medium': '📊 Medium Interest',
            'low': '📉 Low Interest',
            'very_low': '⚠️ Very Low Interest'
        };
        document.getElementById('interestLevel').textContent = interestBadges[analysis.interest_level] || 'Unknown';

        // Opportunity score
        document.getElementById('opportunityScore').textContent = analysis.opportunity_score;

        // Opportunity badge
        const opportunityBadge = document.getElementById('opportunityBadge');
        if (analysis.opportunity_score >= 70) {
            opportunityBadge.textContent = '🔥 Excellent Opportunity';
            opportunityBadge.className = 'opportunity-badge high';
        } else if (analysis.opportunity_score >= 50) {
            opportunityBadge.textContent = '✓ Good Opportunity';
            opportunityBadge.className = 'opportunity-badge medium';
        } else {
            opportunityBadge.textContent = '⚠ Low Opportunity';
            opportunityBadge.className = 'opportunity-badge low';
        }
    } else {
        // No analysis available
        document.getElementById('competitionLevel').textContent = '-';
        document.getElementById('interestLevel').textContent = '-';
        document.getElementById('opportunityScore').textContent = '-';
        document.getElementById('opportunityBadge').textContent = 'Analyzing...';
        document.getElementById('opportunityBadge').className = 'opportunity-badge medium';
    }
}

/**
 * Display related keywords grid
 */
function displayRelatedKeywords(keywords) {
    const grid = document.getElementById('keywordsGrid');
    grid.innerHTML = '';

    if (!keywords || keywords.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-secondary);">No related keywords found</p>';
        return;
    }

    // Sort by competition level (low competition first)
    const compOrder = { 'low': 0, 'medium': 1, 'high': 2 };
    keywords.sort((a, b) => compOrder[a.competition_level] - compOrder[b.competition_level]);

    keywords.forEach(kw => {
        const card = createKeywordCard(kw);
        grid.appendChild(card);
    });
}

/**
 * Create a keyword card element
 */
function createKeywordCard(keyword) {
    const card = document.createElement('div');
    card.className = 'keyword-card';
    card.onclick = () => exploreKeyword(keyword.keyword);

    // Competition level label
    const compLabels = {
        'low': 'Low Competition',
        'medium': 'Medium Competition',
        'high': 'High Competition'
    };

    card.innerHTML = `
        <div class="keyword-header">
            <div class="keyword-text">${escapeHtml(keyword.keyword)}</div>
        </div>
        <div class="keyword-stats">
            <div class="keyword-stat">
                <span class="stat-value">${compLabels[keyword.competition_level] || 'Unknown'}</span>
            </div>
        </div>
    `;

    return card;
}

/**
 * Update breadcrumb trail
 */
function updateBreadcrumb() {
    const trail = document.getElementById('breadcrumbTrail');
    const items = document.getElementById('breadcrumbItems');

    if (keywordHistory.length === 0) {
        trail.style.display = 'none';
        return;
    }

    trail.style.display = 'block';
    items.innerHTML = '';

    keywordHistory.forEach((keyword, index) => {
        const item = document.createElement('div');
        item.className = 'breadcrumb-item';

        if (index === keywordHistory.length - 1) {
            // Current keyword (not clickable)
            item.innerHTML = `<span>${escapeHtml(keyword)}</span>`;
        } else {
            // Previous keywords (clickable)
            item.innerHTML = `
                <a class="breadcrumb-link" onclick="navigateToBreadcrumb(${index})">${escapeHtml(keyword)}</a>
                <span class="breadcrumb-separator">›</span>
            `;
        }

        items.appendChild(item);
    });
}

/**
 * Navigate to a keyword from breadcrumb
 */
function navigateToBreadcrumb(index) {
    // Remove keywords after this index
    keywordHistory = keywordHistory.slice(0, index + 1);
    updateBreadcrumb();

    // Explore this keyword
    const keyword = keywordHistory[index];
    exploreKeyword(keyword);
}

/**
 * Show loading state
 */
function showLoading() {
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('loadingContainer').style.display = 'block';
}

/**
 * Show error message
 */
function showError(message) {
    document.getElementById('loadingContainer').style.display = 'none';
    alert(message);
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    if (!num && num !== 0) return '-';
    return num.toLocaleString();
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

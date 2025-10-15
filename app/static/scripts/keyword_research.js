/**
 * Keyword Research JavaScript
 * Handles keyword exploration with autocomplete and competition analysis
 */

// Global state
let currentKeyword = '';
let keywordHistory = [];
let analysisCache = {};
let currentMode = 'manual'; // 'manual' or 'ai'

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
 * Main function to explore a keyword - supports both Manual and AI modes
 */
async function exploreKeyword(keyword = null) {
    const keywordToExplore = keyword || document.getElementById('keywordInput').value.trim();

    if (!keywordToExplore) {
        showError('Please enter a ' + (currentMode === 'ai' ? 'topic' : 'keyword'));
        return;
    }

    // Disable explore button
    const exploreBtn = document.getElementById('exploreBtn');
    exploreBtn.disabled = true;

    if (currentMode === 'ai') {
        exploreBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Generating...';
        await exploreWithAI(keywordToExplore);
    } else {
        exploreBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Analyzing...';
        await exploreManual(keywordToExplore);
    }

    exploreBtn.disabled = false;
}

/**
 * Manual exploration (original functionality)
 */
async function exploreManual(keywordToExplore) {
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

    const exploreBtn = document.getElementById('exploreBtn');
    const originalBtnText = '<i class="ph ph-sparkle"></i><span id="exploreBtnText">Explore</span>';

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
        console.error('Exploration error:', error);
        showError(error.message || 'Failed to explore keyword');
        document.getElementById('emptyState').style.display = 'block';
    } finally {
        document.getElementById('loadingContainer').style.display = 'none';
        exploreBtn.innerHTML = originalBtnText;
    }
}

/**
 * AI-powered keyword exploration
 */
async function exploreWithAI(topic) {
    const count = 50; // Always generate 50 keywords

    // Show loading with AI-specific message
    document.getElementById('loadingContainer').style.display = 'flex';
    document.querySelector('.loading-text').textContent = `AI is generating ${count} keywords for "${topic}"...`;
    document.getElementById('emptyState').style.display = 'none';

    try {
        const response = await fetch('/keyword-research/api/ai-keyword-explore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                topic: topic,
                count: count
            })
        });

        if (!response.ok) {
            throw new Error('Failed to generate keywords');
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to generate keywords');
        }

        // Display AI results
        displayAIResults(data);

    } catch (error) {
        console.error('AI exploration error:', error);
        showError(error.message || 'Failed to explore topic with AI');
        document.getElementById('emptyState').style.display = 'block';
    } finally {
        document.getElementById('loadingContainer').style.display = 'none';
        const exploreBtn = document.getElementById('exploreBtn');
        exploreBtn.innerHTML = '<i class="ph ph-sparkle"></i><span id="exploreBtnText">Generate & Analyze</span>';
    }
}

// Removed - duplicate function moved to line 663

/**
 * Switch between Manual and AI Explorer mode
 */
function switchMode(mode) {
    currentMode = mode;

    // Update active button
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.mode === mode) {
            btn.classList.add('active');
        }
    });

    // Update UI elements
    const searchIcon = document.getElementById('searchIcon');
    const keywordInput = document.getElementById('keywordInput');
    const exploreBtnText = document.getElementById('exploreBtnText');

    if (mode === 'ai') {
        searchIcon.className = 'ph ph-magic-wand search-icon';
        keywordInput.placeholder = 'Enter a topic (e.g., Fortnite, Yoga, AI Video Models)';
        exploreBtnText.textContent = 'Generate & Analyze';
    } else {
        searchIcon.className = 'ph ph-magnifying-glass search-icon';
        keywordInput.placeholder = 'Enter a keyword to research (e.g., clash royale, minecraft, cooking)';
        exploreBtnText.textContent = 'Explore';
    }

    // Clear results
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
    keywordHistory = [];
    updateBreadcrumb();
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

    // Scroll to results
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
            'high': 'High Interest',
            'medium': 'Medium Interest',
            'low': 'Low Interest',
            'very_low': 'Very Low Interest'
        };
        document.getElementById('interestLevel').textContent = interestBadges[analysis.interest_level] || 'Unknown';

        // Opportunity score
        document.getElementById('opportunityScore').textContent = analysis.opportunity_score;

        // Opportunity badge
        const opportunityBadge = document.getElementById('opportunityBadge');
        if (analysis.opportunity_score >= 70) {
            opportunityBadge.textContent = 'Excellent Opportunity';
            opportunityBadge.className = 'opportunity-badge high';
        } else if (analysis.opportunity_score >= 50) {
            opportunityBadge.textContent = 'Good Opportunity';
            opportunityBadge.className = 'opportunity-badge medium';
        } else {
            opportunityBadge.textContent = 'Low Opportunity';
            opportunityBadge.className = 'opportunity-badge low';
        }

        // Show quality warning if present
        const qualityWarningDiv = document.getElementById('qualityWarning');
        console.log('Quality warning check:', analysis.quality_warning);
        if (analysis.quality_warning) {
            qualityWarningDiv.style.display = 'flex';
            qualityWarningDiv.innerHTML = `
                <i class="ph ph-warning"></i>
                <span>${escapeHtml(analysis.quality_warning)}</span>
            `;
        } else {
            qualityWarningDiv.style.display = 'none';
        }
    } else {
        // No analysis available
        document.getElementById('competitionLevel').textContent = '-';
        document.getElementById('interestLevel').textContent = '-';
        document.getElementById('opportunityScore').textContent = '-';
        document.getElementById('opportunityBadge').textContent = 'Analyzing...';
        document.getElementById('opportunityBadge').className = 'opportunity-badge medium';

        // Hide quality warning
        const qualityWarningDiv = document.getElementById('qualityWarning');
        if (qualityWarningDiv) {
            qualityWarningDiv.style.display = 'none';
        }
    }
}

/**
 * Display related keywords grid
 */
function displayRelatedKeywords(keywords) {
    const grid = document.getElementById('keywordsGrid');
    grid.innerHTML = '';

    if (!keywords || keywords.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-secondary); padding: 2rem;">No related keywords found</p>';
        return;
    }

    // Sort by opportunity score (descending)
    keywords.sort((a, b) => b.opportunity_score - a.opportunity_score);

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

    // Determine score class
    let scoreClass = 'low';
    if (keyword.opportunity_score >= 70) {
        scoreClass = 'excellent';
    } else if (keyword.opportunity_score >= 50) {
        scoreClass = 'good';
    } else if (keyword.opportunity_score >= 30) {
        scoreClass = 'medium';
    }

    // Competition level label
    const compLabels = {
        'low': 'Low Competition',
        'medium': 'Medium Competition',
        'high': 'High Competition'
    };

    // Interest level label
    const interestLabels = {
        'high': 'High Interest',
        'medium': 'Medium Interest',
        'low': 'Low Interest',
        'very_low': 'Very Low Interest'
    };

    // Add quality warning icon in header if present (tooltip on hover)
    const qualityWarningIcon = keyword.quality_warning ?
        `<div class="keyword-quality-icon">
            <i class="ph ph-warning"></i>
            <span class="keyword-quality-tooltip">${escapeHtml(keyword.quality_warning)}</span>
        </div>` : '';

    card.innerHTML = `
        <div class="keyword-header">
            <div class="keyword-text">${escapeHtml(keyword.keyword)}</div>
            <div class="keyword-header-right">
                ${qualityWarningIcon}
                <div class="keyword-score ${scoreClass}">${keyword.opportunity_score}/100</div>
            </div>
        </div>
        <div class="keyword-stats">
            <div class="keyword-stat">
                <span class="stat-label">Competition:</span>
                <span class="stat-value">${compLabels[keyword.competition_level] || 'Unknown'}</span>
            </div>
            <div class="keyword-stat">
                <span class="stat-label">Interest:</span>
                <span class="stat-value">${interestLabels[keyword.interest_level] || 'Unknown'}</span>
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
    document.getElementById('loadingContainer').style.display = 'flex';
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

/**
 * Switch between Manual and AI Explorer mode
 */
/**
 * AI-powered keyword exploration
 */
async function exploreWithAI(topic) {
    const count = 50; // Always generate 50 keywords

    // Show loading with AI-specific message
    document.getElementById('loadingContainer').style.display = 'flex';
    document.querySelector('.loading-text').textContent = `AI is generating ${count} keywords for "${topic}"...`;
    document.getElementById('emptyState').style.display = 'none';

    try {
        const response = await fetch('/keyword-research/api/ai-keyword-explore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                topic: topic,
                count: count
            })
        });

        if (!response.ok) {
            throw new Error('Failed to generate keywords');
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to generate keywords');
        }

        // Display AI results
        displayAIResults(data);

    } catch (error) {
        console.error('AI exploration error:', error);
        showError(error.message || 'Failed to explore topic with AI');
        document.getElementById('emptyState').style.display = 'block';
    } finally {
        document.getElementById('loadingContainer').style.display = 'none';
        const exploreBtn = document.getElementById('exploreBtn');
        exploreBtn.disabled = false;
        exploreBtn.innerHTML = '<i class="ph ph-sparkle"></i><span id="exploreBtnText">Generate & Analyze</span>';
    }
}

/**
 * Display AI exploration results
 */
function displayAIResults(data) {
    // Hide empty state and loading
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('loadingContainer').style.display = 'none';

    // Show results section
    const resultsSection = document.getElementById('resultsSection');
    resultsSection.style.display = 'block';

    // Hide current analysis card (not relevant in AI mode)
    document.getElementById('currentAnalysis').style.display = 'none';

    // Show and populate AI insights card
    const insightsCard = document.getElementById('aiInsightsCard');
    insightsCard.style.display = 'block';

    const insightsMeta = document.getElementById('insightsMeta');
    insightsMeta.innerHTML = `
        <span class="insights-badge">
            <i class="ph ph-target"></i>
            ${data.keywords_analyzed} keywords analyzed
        </span>
        <span class="insights-badge">
            <i class="ph ph-brain"></i>
            ${data.detected_context.domain}
        </span>
    `;

    const insightsContent = document.getElementById('insightsContent');
    insightsContent.innerHTML = formatInsights(data.insights);

    // Update keywords grid with table
    const keywordsGrid = document.getElementById('keywordsGrid');

    // Update section header
    const sectionHeader = document.getElementById('keywordsTitle');
    sectionHeader.innerHTML = `
        <i class="ph ph-lightbulb"></i>
        Top ${data.results.length} Keyword Opportunities for "${data.topic}"
    `;

    // Create table
    keywordsGrid.innerHTML = `
        <div class="keywords-table-wrapper">
            <table class="keywords-table">
                <thead>
                    <tr>
                        <th>Keyword</th>
                        <th>Score</th>
                        <th>Competition</th>
                        <th>Interest</th>
                    </tr>
                </thead>
                <tbody id="keywordsTableBody">
                </tbody>
            </table>
        </div>
    `;

    // Populate table rows
    const tbody = document.getElementById('keywordsTableBody');
    data.results.forEach(keyword => {
        const row = createKeywordTableRow(keyword);
        tbody.appendChild(row);
    });
}

/**
 * Format AI insights text (convert to structured HTML)
 */
function formatInsights(text) {
    if (!text) return '';

    // Remove any leading markdown title (# Title)
    text = text.replace(/^#\s+.*?\n/, '');

    // Split by major sections (##)
    const sections = text.split(/\n##\s+/);
    let html = '';

    sections.forEach((section, index) => {
        const trimmed = section.trim();
        if (!trimmed) return;

        // Split into lines
        const lines = trimmed.split('\n');
        const title = lines[0].replace(/^##\s*/, '').trim();
        const contentLines = lines.slice(1);

        if (!title) return;

        html += `<div class="insight-section">`;
        html += `<h4>${title}</h4>`;

        // Process content line by line
        let inList = false;
        let listHtml = '';

        contentLines.forEach(line => {
            line = line.trim();
            if (!line) return;

            // Check if it's a list item
            if (line.startsWith('- ')) {
                if (!inList) {
                    inList = true;
                    listHtml = '<ul>';
                }
                const content = line.substring(2).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                listHtml += `<li>${content}</li>`;
            } else if (line.match(/^\d+\.\s+/)) {
                if (!inList) {
                    inList = true;
                    listHtml = '<ul>';
                }
                const content = line.replace(/^\d+\.\s+/, '').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                listHtml += `<li>${content}</li>`;
            } else {
                // Close list if we were in one
                if (inList) {
                    listHtml += '</ul>';
                    html += listHtml;
                    inList = false;
                    listHtml = '';
                }
                // Regular paragraph
                const content = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                html += `<p>${content}</p>`;
            }
        });

        // Close any open list
        if (inList) {
            listHtml += '</ul>';
            html += listHtml;
        }

        html += `</div>`;
    });

    return html;
}

/**
 * Create a table row for a keyword
 */
function createKeywordTableRow(keyword) {
    const row = document.createElement('tr');
    row.className = 'keyword-row';

    // Determine competition class
    let competitionClass = 'competition-low';
    if (keyword.competition_level === 'high') competitionClass = 'competition-high';
    else if (keyword.competition_level === 'medium') competitionClass = 'competition-medium';

    // Determine interest class
    let interestClass = 'interest-low';
    if (keyword.interest_level === 'high') interestClass = 'interest-high';
    else if (keyword.interest_level === 'medium') interestClass = 'interest-medium';

    // Map interest levels to display text
    const interestLabels = {
        'high': 'High Interest',
        'medium': 'Medium Interest',
        'low': 'Low Interest',
        'very_low': 'Very Low Interest'
    };

    // Map competition levels to display text
    const competitionLabels = {
        'low': 'Low Competition',
        'medium': 'Medium Competition',
        'high': 'High Competition'
    };

    row.innerHTML = `
        <td class="keyword-cell">${keyword.keyword}</td>
        <td class="score-cell">
            <span class="opportunity-score-badge">${keyword.opportunity_score}/100</span>
        </td>
        <td class="competition-cell">
            <span class="competition-badge ${competitionClass}">
                ${competitionLabels[keyword.competition_level] || 'Unknown Competition'}
            </span>
        </td>
        <td class="interest-cell">
            <span class="interest-badge ${interestClass}">
                ${interestLabels[keyword.interest_level] || 'Unknown Interest'}
            </span>
        </td>
    `;

    return row;
}

// Additional AI functions are defined above near switchMode()
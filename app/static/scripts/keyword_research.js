/**
 * Keyword Research JavaScript
 * Handles keyword exploration with autocomplete and competition analysis
 */

// Global state
let currentKeyword = '';
let keywordHistory = [];
let analysisCache = {};
let currentMode = 'manual'; // 'manual' or 'ai'
let currentAIResults = null; // Store current AI results for refinement

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    // Check for ongoing AI keyword research
    const ongoingAIResearch = sessionStorage.getItem('ai_keyword_research_ongoing');
    if (ongoingAIResearch) {
        const researchData = JSON.parse(ongoingAIResearch);
        const currentTime = Date.now();

        // If research started less than 2 minutes ago, check if it's already complete
        if (currentTime - researchData.startTime < 120000) {
            console.log('Ongoing AI keyword research detected:', researchData.keyword);

            // First check if this research is already saved
            try {
                const response = await fetch('/keyword-research/api/latest-research');
                const data = await response.json();

                if (data.success && data.has_research && data.research.topic === researchData.keyword) {
                    // Research is already complete! Just load it
                    console.log('Research already complete, loading saved results');
                    sessionStorage.removeItem('ai_keyword_research_ongoing');

                    if (currentMode === 'ai') {
                        loadLatestResearchCard();
                    }
                } else {
                    // Research not complete yet, show loading and poll
                    showAILoading(researchData.keyword);
                    checkAIResearchStatus(researchData.keyword);
                }
            } catch (error) {
                console.error('Error checking research status:', error);
                // Fallback to polling
                showAILoading(researchData.keyword);
                checkAIResearchStatus(researchData.keyword);
            }
        } else {
            // Research timed out, clear it
            sessionStorage.removeItem('ai_keyword_research_ongoing');
            // Load normal latest research card (only shows in AI mode)
            if (currentMode === 'ai') {
                loadLatestResearchCard();
            }
        }
    } else {
        // No ongoing research, load latest research card if in AI mode
        if (currentMode === 'ai') {
            loadLatestResearchCard();
        }
    }

    // Enter key support in search inputs
    document.getElementById('manualKeywordInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            exploreKeyword();
        }
    });

    document.getElementById('aiKeywordInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            exploreKeyword();
        }
    });
});

/**
 * Quick explore from example chips
 */
function quickExplore(keyword) {
    if (currentMode === 'ai') {
        document.getElementById('aiKeywordInput').value = keyword;
    } else {
        document.getElementById('manualKeywordInput').value = keyword;
    }
    exploreKeyword();
}

/**
 * Main function to explore a keyword - supports both Manual and AI modes
 */
async function exploreKeyword(keyword = null) {
    const inputField = currentMode === 'ai' ? document.getElementById('aiKeywordInput') : document.getElementById('manualKeywordInput');
    const keywordToExplore = keyword || inputField.value.trim();

    if (!keywordToExplore) {
        showError('Please enter a ' + (currentMode === 'ai' ? 'topic' : 'keyword'));
        return;
    }

    if (currentMode === 'ai') {
        await exploreWithAI(keywordToExplore);
    } else {
        await exploreManual(keywordToExplore);
    }
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
    document.getElementById('manualKeywordInput').value = keywordToExplore;

    // Show loading state for MANUAL mode only
    showManualLoading();

    // Disable explore button
    const exploreBtn = document.getElementById('manualExploreBtn');
    exploreBtn.disabled = true;
    exploreBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Analyzing...';

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

        // Display results in manual section
        displayManualResults(keywordToExplore, mainAnalysis, analyzedSuggestions);

    } catch (error) {
        console.error('Exploration error:', error);
        showError(error.message || 'Failed to explore keyword');
        if (currentMode === 'manual') {
            document.getElementById('manualEmptyState').style.display = 'block';
        }
    } finally {
        if (currentMode === 'manual') {
            document.getElementById('manualLoadingContainer').style.display = 'none';
            exploreBtn.disabled = false;
            exploreBtn.innerHTML = '<i class="ph ph-sparkle"></i><span>Explore</span>';
        }
    }
}

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

    // Show/hide appropriate sections
    const manualSection = document.getElementById('manualSection');
    const aiSection = document.getElementById('aiSection');

    if (mode === 'ai') {
        // Show AI section, hide manual section
        manualSection.style.display = 'none';
        aiSection.style.display = 'block';

        // Check for ongoing AI research
        const ongoingAIResearch = sessionStorage.getItem('ai_keyword_research_ongoing');
        if (ongoingAIResearch) {
            const researchData = JSON.parse(ongoingAIResearch);
            if (Date.now() - researchData.startTime < 120000) {
                showAILoading(researchData.keyword);
                checkAIResearchStatus(researchData.keyword);
            } else {
                loadLatestResearchCard();
            }
        } else {
            loadLatestResearchCard();
        }
    } else {
        // Manual mode
        // Show manual section, hide AI section
        manualSection.style.display = 'block';
        aiSection.style.display = 'none';

        // Hide latest research card in manual mode
        document.getElementById('latestResearchSection').style.display = 'none';
    }
}

/**
 * Display manual mode results
 */
function displayManualResults(keyword, mainAnalysis, suggestions) {
    // Hide loading and empty state
    document.getElementById('manualLoadingContainer').style.display = 'none';
    document.getElementById('manualEmptyState').style.display = 'none';

    // Show results section
    document.getElementById('manualResultsSection').style.display = 'block';

    // Display main keyword analysis
    displayMainAnalysis(keyword, mainAnalysis);

    // Display related keywords
    displayRelatedKeywords(suggestions);

    // Scroll to results
    document.getElementById('manualResultsSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
        document.getElementById('qualityWarning').style.display = 'none';
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
 * Show loading state for manual mode
 */
function showManualLoading() {
    document.getElementById('manualEmptyState').style.display = 'none';
    document.getElementById('manualResultsSection').style.display = 'none';
    document.getElementById('manualLoadingContainer').style.display = 'flex';
}

/**
 * Show loading state for AI mode
 */
function showAILoading(topic) {
    document.getElementById('aiEmptyState').style.display = 'none';
    document.getElementById('aiResultsSection').style.display = 'none';
    document.getElementById('aiLoadingContainer').style.display = 'flex';
    document.querySelector('#aiLoadingContainer .loading-text').textContent = `Analyzing "${topic}"...`;

    // Set button to generating state
    const aiBtn = document.getElementById('aiExploreBtn');
    if (aiBtn) {
        aiBtn.disabled = true;
        aiBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Generating...';
    }
}

/**
 * Show error message
 */
function showError(message) {
    alert(message);
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
 * AI-powered keyword exploration
 */
async function exploreWithAI(topic) {
    const count = 50; // Always generate 50 keywords

    // Clear any existing ongoing research (allows re-searching same keyword)
    sessionStorage.removeItem('ai_keyword_research_ongoing');

    // Mark as ongoing in sessionStorage
    sessionStorage.setItem('ai_keyword_research_ongoing', JSON.stringify({
        keyword: topic,
        startTime: Date.now()
    }));

    // Show loading with AI-specific message
    showAILoading(topic);

    // Disable explore button
    const exploreBtn = document.getElementById('aiExploreBtn');
    exploreBtn.disabled = true;
    exploreBtn.innerHTML = '<i class="ph ph-spinner spin"></i> Generating...';

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

        const data = await response.json();

        if (!response.ok || !data.success) {
            // Check for insufficient credits error
            if (data.error_type === 'insufficient_credits') {
                showInsufficientCreditsError(data);
                return;
            }
            throw new Error(data.error || 'Failed to generate keywords');
        }

        // Display AI results
        displayAIResults(data);

    } catch (error) {
        console.error('AI exploration error:', error);
        sessionStorage.removeItem('ai_keyword_research_ongoing');
        showError(error.message || 'Failed to explore topic with AI');
        if (currentMode === 'ai') {
            document.getElementById('aiEmptyState').style.display = 'block';
        }
    } finally {
        if (currentMode === 'ai') {
            document.getElementById('aiLoadingContainer').style.display = 'none';
            exploreBtn.disabled = false;
            exploreBtn.innerHTML = '<i class="ph ph-sparkle"></i><span>Generate & Analyze</span>';
        }
    }
}

/**
 * Display AI exploration results
 */
function displayAIResults(data) {
    // Store current results for refinement
    currentAIResults = data;

    // Clear ongoing research flag - research complete!
    sessionStorage.removeItem('ai_keyword_research_ongoing');

    // Hide empty state and loading
    document.getElementById('aiEmptyState').style.display = 'none';
    document.getElementById('aiLoadingContainer').style.display = 'none';

    // Reset button state
    const aiBtn = document.getElementById('aiExploreBtn');
    if (aiBtn) {
        aiBtn.disabled = false;
        aiBtn.innerHTML = '<i class="ph ph-sparkle"></i><span>Generate & Analyze</span>';
    }

    // Show refine keywords button
    const refineBtn = document.getElementById('refineKeywordsBtn');
    if (refineBtn) {
        refineBtn.style.display = 'flex';
    }

    // Show results section
    document.getElementById('aiResultsSection').style.display = 'block';

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

    // Don't show the latest research card when we just completed the analysis
    // (user is already viewing the latest results)
    // Hide it if it's visible
    document.getElementById('latestResearchSection').style.display = 'none';

    const insightsContent = document.getElementById('insightsContent');
    insightsContent.innerHTML = formatInsights(data.insights);

    // Update keywords grid with table
    const keywordsGrid = document.getElementById('aiKeywordsGrid');

    // Update section header
    const sectionHeader = document.getElementById('aiKeywordsTitle');
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
                        <th>Relevance</th>
                    </tr>
                </thead>
                <tbody id="aiKeywordsTableBody">
                </tbody>
            </table>
        </div>
    `;

    // Populate table rows
    const tbody = document.getElementById('aiKeywordsTableBody');
    data.results.forEach(keyword => {
        const row = createKeywordTableRow(keyword);
        tbody.appendChild(row);
    });

    // Scroll to results
    document.getElementById('aiResultsSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

    // Determine relevance class and label
    const relevance = keyword.relevance_percentage || 0;
    let relevanceClass = 'relevance-high';
    let relevanceLabel = 'High';

    if (relevance < 60) {
        relevanceClass = 'relevance-poor';
        relevanceLabel = 'Poor';
    } else if (relevance < 70) {
        relevanceClass = 'relevance-fair';
        relevanceLabel = 'Fair';
    } else if (relevance < 85) {
        relevanceClass = 'relevance-good';
        relevanceLabel = 'Good';
    }

    // Add quality warning tooltip if present
    const relevanceTooltip = keyword.quality_warning ?
        `<span class="relevance-tooltip">${escapeHtml(keyword.quality_warning)}</span>` : '';

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
        <td class="relevance-cell">
            <div class="relevance-wrapper">
                <span class="relevance-badge ${relevanceClass}">
                    ${relevance}%
                </span>
                ${relevanceTooltip}
            </div>
        </td>
    `;

    return row;
}

/**
 * Show insufficient credits error with nice UI
 */
function showInsufficientCreditsError(data) {
    // Clear the ongoing research flag
    sessionStorage.removeItem('ai_keyword_research_ongoing');

    document.getElementById('aiLoadingContainer').style.display = 'none';
    document.getElementById('aiEmptyState').style.display = 'none';

    const resultsSection = document.getElementById('aiResultsSection');
    resultsSection.style.display = 'block';
    resultsSection.innerHTML = `
        <div class="insufficient-credits-card" style="max-width: 500px; margin: 3rem auto;">
            <div class="credit-icon-wrapper">
                <i class="ph ph-coins"></i>
            </div>
            <h3 style="color: var(--text-primary); margin-bottom: 0.5rem; font-size: 1.25rem; font-weight: 700;">Insufficient Credits</h3>
            <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">
                You don't have enough credits to use this feature.
            </p>
            <a href="/payment" class="upgrade-plan-btn">
                <i class="ph ph-crown"></i>
                Upgrade Plan
            </a>
        </div>
    `;
}

/**
 * Check if AI keyword research is complete by polling the backend
 */
async function checkAIResearchStatus(keyword) {
    const maxAttempts = 60; // Poll for up to 2 minutes
    let attempts = 0;

    const pollInterval = setInterval(async () => {
        attempts++;

        try {
            // Check if the research is saved in Firebase
            const response = await fetch('/keyword-research/api/latest-research');
            const data = await response.json();

            if (data.success && data.has_research) {
                const research = data.research;
                // Check if this is the research we're waiting for
                if (research.topic === keyword) {
                    console.log('AI keyword research complete for:', keyword);
                    sessionStorage.removeItem('ai_keyword_research_ongoing');
                    clearInterval(pollInterval);

                    // Hide loading only if we're in AI mode
                    if (currentMode === 'ai') {
                        document.getElementById('aiLoadingContainer').style.display = 'none';
                        // Display the results
                        displayAIResults(research.results);
                    }

                    return;
                }
            }
        } catch (error) {
            console.error('Error checking research status:', error);
        }

        // If max attempts reached, stop polling
        if (attempts >= maxAttempts) {
            console.log('AI keyword research polling timed out');
            sessionStorage.removeItem('ai_keyword_research_ongoing');
            clearInterval(pollInterval);
            
            if (currentMode === 'ai') {
                document.getElementById('aiLoadingContainer').style.display = 'none';
                // Try to load latest research even on timeout
                await loadLatestResearchCard();
                alert('Research is taking longer than expected. Please try again.');
            }
        }
    }, 2000); // Poll every 2 seconds
}

/**
 * Load latest research card (shows on AI mode)
 */
async function loadLatestResearchCard() {
    try {
        const response = await fetch('/keyword-research/api/latest-research');
        const data = await response.json();

        if (data.success && data.has_research) {
            const research = data.research;
            const section = document.getElementById('latestResearchSection');
            const topic = document.getElementById('latestResearchTopic');
            const keywordCount = document.getElementById('latestResearchKeywordCount');
            const date = document.getElementById('latestResearchDate');

            // Format date
            const createdDate = new Date(research.created_at);
            const now = new Date();
            const diffMs = now - createdDate;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            let dateStr;
            if (diffMins < 60) {
                dateStr = `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
            } else if (diffHours < 24) {
                dateStr = `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
            } else if (diffDays < 7) {
                dateStr = `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
            } else {
                dateStr = createdDate.toLocaleDateString();
            }

            topic.textContent = research.topic;
            keywordCount.textContent = research.keyword_count;
            date.textContent = dateStr;

            // Restore click handler
            const card = section.querySelector('.latest-analysis-card');
            if (card) {
                card.style.cursor = 'pointer';
                card.onclick = loadLatestResearch;
            }

            // Only show in AI mode
            if (currentMode === 'ai') {
                section.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Error loading latest research:', error);
    }
}

/**
 * Load and display latest research
 */
async function loadLatestResearch() {
    try {
        // Show loading
        showAILoading('previous research');

        const response = await fetch('/keyword-research/api/latest-research');
        const data = await response.json();

        if (data.success && data.has_research) {
            const research = data.research;

            // Hide loading
            document.getElementById('aiLoadingContainer').style.display = 'none';

            // Display the saved research
            displayAIResults(research.results);
        } else {
            document.getElementById('aiLoadingContainer').style.display = 'none';
            showError('No saved research found.');
            document.getElementById('aiEmptyState').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading latest research:', error);
        document.getElementById('aiLoadingContainer').style.display = 'none';
        showError('Failed to load research: ' + error.message);
        document.getElementById('aiEmptyState').style.display = 'block';
    }
}

/**
 * Refine current keywords - keep high-performing ones and generate new ones
 */
async function refineKeywords() {
    if (!currentAIResults || !currentAIResults.results || currentAIResults.results.length === 0) {
        showError('No keywords to refine. Please generate keywords first.');
        return;
    }

    const refineBtn = document.getElementById('refineKeywordsBtn');
    refineBtn.disabled = true;
    refineBtn.innerHTML = '<i class="ph ph-arrows-clockwise spin"></i> Refining...';

    try {
        // Separate keywords into high-performing (>=75) and low-performing (<75)
        const highPerforming = currentAIResults.results.filter(kw => kw.opportunity_score >= 75);
        const lowPerforming = currentAIResults.results.filter(kw => kw.opportunity_score < 75);

        // Calculate how many new keywords to generate
        const newKeywordsNeeded = 50;

        const response = await fetch('/keyword-research/api/refine-keywords', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                topic: currentAIResults.topic,
                high_performing: highPerforming,
                low_performing: lowPerforming,
                count: newKeywordsNeeded
            })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            if (data.error_type === 'insufficient_credits') {
                showInsufficientCreditsError(data);
                return;
            }
            throw new Error(data.error || 'Failed to refine keywords');
        }

        // Display refined results
        displayAIResults(data);

    } catch (error) {
        console.error('Refine keywords error:', error);
        showError(error.message || 'Failed to refine keywords');
    } finally {
        refineBtn.disabled = false;
        refineBtn.innerHTML = '<i class="ph ph-arrows-clockwise"></i> Refine Keywords';
    }
}
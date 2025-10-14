/**
 * Video Title & Tags Generator JavaScript
 * Handles all functionality for generating titles, descriptions, and tags
 */

// State management
let currentVideoType = 'long';
let currentTitles = [];
let currentTags = [];
let currentDescription = '';
let isGenerating = false;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateCharCount();
    updateRefDescCharCount();
});

// Set video type
function setVideoType(type) {
    currentVideoType = type;
    document.querySelectorAll('.type-btn').forEach(btn => btn.classList.remove('active'));
    if (type === 'long') {
        document.getElementById('longFormBtn').classList.add('active');
    } else {
        document.getElementById('shortFormBtn').classList.add('active');
    }
}

// Update character count for main input
function updateCharCount() {
    const input = document.getElementById('videoInput');
    const count = input.value.length;
    document.getElementById('charCount').textContent = `${count} / 5000`;
}

// Update character count for reference description
function updateRefDescCharCount() {
    const input = document.getElementById('referenceDescription');
    const count = input.value.length;
    document.getElementById('refDescCharCount').textContent = `${count} / 5000`;
}

// Toggle reference section
function toggleReferenceSection() {
    const content = document.getElementById('referenceContent');
    const toggle = document.getElementById('referenceToggle');

    if (content.classList.contains('show')) {
        content.classList.remove('show');
        toggle.innerHTML = '<i class="ph ph-plus"></i> Add Reference';
    } else {
        content.classList.add('show');
        toggle.innerHTML = '<i class="ph ph-minus"></i> Remove Reference';
    }
}

// Main generate function
async function generateContent() {
    const input = document.getElementById('videoInput').value.trim();
    const keyword = document.getElementById('keywordInput').value.trim();
    const referenceDescription = document.getElementById('referenceDescription').value.trim();
    const generateTitles = document.getElementById('generateTitlesCheck').checked;
    const generateDescription = document.getElementById('generateDescriptionCheck').checked;
    const generateTags = document.getElementById('generateTagsCheck').checked;

    // Validation
    if (!input) {
        showToast('Please enter your video description or script', 'error');
        return;
    }

    if (!generateTitles && !generateDescription && !generateTags) {
        showToast('Please select at least one option to generate', 'error');
        return;
    }

    if (isGenerating) return;

    isGenerating = true;
    const generateBtn = document.getElementById('generateBtn');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="ph ph-spinner"></i> Generating...';

    // Prepare loading message
    let loadingParts = [];
    if (generateTitles) loadingParts.push('titles');
    if (generateDescription) loadingParts.push('description');
    if (generateTags) loadingParts.push('tags');
    const loadingText = loadingParts.join(', ').replace(/, ([^,]*)$/, ' and $1');

    // Show loading state
    document.getElementById('resultsContainer').innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"></div>
            <div class="loading-text">Creating Your Content</div>
            <div class="loading-subtext">Generating ${loadingText}...</div>
        </div>
    `;

    try {
        let titlesData = null;
        let descriptionData = null;
        let tagsData = null;

        // Prepare input with keyword if provided
        let enhancedInput = input;
        if (keyword) {
            enhancedInput = `CRITICAL: You MUST start with this EXACT keyword: "${keyword}"\n\nVIDEO CONTENT:\n${input}`;
        }

        // Generate titles if requested
        if (generateTitles) {
            const titleResponse = await fetch('/api/generate-video-titles', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    input: enhancedInput,
                    type: currentVideoType
                })
            });
            titlesData = await titleResponse.json();

            if (!titlesData.success) {
                throw new Error(titlesData.error || 'Failed to generate titles');
            }
        }

        // Generate description if requested
        if (generateDescription) {
            const descResponse = await fetch('/api/generate-video-description', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    input: enhancedInput,
                    type: currentVideoType,
                    reference_description: referenceDescription
                })
            });
            descriptionData = await descResponse.json();

            if (!descriptionData.success) {
                throw new Error(descriptionData.error || 'Failed to generate description');
            }
        }

        // Generate tags if requested
        if (generateTags) {
            const tagsResponse = await fetch('/api/generate-video-tags', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    input: enhancedInput
                })
            });
            tagsData = await tagsResponse.json();

            if (!tagsData.success) {
                throw new Error(tagsData.error || 'Failed to generate tags');
            }
        }

        // Display results
        displayCombinedResults(titlesData, descriptionData, tagsData);
        showToast('Content generated successfully!', 'success');

    } catch (error) {
        console.error('Error generating content:', error);
        document.getElementById('resultsContainer').innerHTML = `
            <div class="error-state">
                <i class="ph ph-warning-circle error-icon"></i>
                <div class="error-title">Generation Failed</div>
                <div class="error-text">${error.message || 'Unable to generate content. Please try again.'}</div>
            </div>
        `;
        showToast('Failed to generate content', 'error');
    } finally {
        isGenerating = false;
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="ph ph-sparkle"></i> Generate';
    }
}

// Display combined results
function displayCombinedResults(titlesData, descriptionData, tagsData) {
    let html = '';

    const hasTitles = titlesData && titlesData.titles && titlesData.titles.length > 0;
    const hasDescription = descriptionData && descriptionData.description;
    const hasTags = tagsData && tagsData.tags && tagsData.tags.length > 0;
    const showTabs = (hasTitles && hasDescription) || (hasTitles && hasTags) || (hasDescription && hasTags);

    // Add tabs if multiple content types
    if (showTabs) {
        html += '<div class="results-tabs">';
        if (hasTitles) {
            html += `
                <button class="results-tab-btn active" onclick="switchTab('titles')">
                    <i class="ph ph-sparkle"></i> Titles
                </button>
            `;
        }
        if (hasDescription) {
            html += `
                <button class="results-tab-btn ${!hasTitles ? 'active' : ''}" onclick="switchTab('description')">
                    <i class="ph ph-file-text"></i> Description
                </button>
            `;
        }
        if (hasTags) {
            html += `
                <button class="results-tab-btn ${!hasTitles && !hasDescription ? 'active' : ''}" onclick="switchTab('tags')">
                    <i class="ph ph-hash"></i> Tags
                </button>
            `;
        }
        html += '</div>';
    }

    // Display Titles
    if (hasTitles) {
        currentTitles = titlesData.titles;
        html += renderTitlesSection(titlesData.titles, !showTabs || hasTitles);
    }

    // Display Description
    if (hasDescription) {
        currentDescription = descriptionData.description;
        html += renderDescriptionSection(descriptionData.description, !showTabs || (!hasTitles && hasDescription));
    }

    // Display Tags
    if (hasTags) {
        currentTags = tagsData.tags;
        html += renderTagsSection(tagsData.tags, !showTabs || (!hasTitles && !hasDescription && hasTags));
    }

    document.getElementById('resultsContainer').innerHTML = html;
}

// Render titles section
function renderTitlesSection(titles, visible) {
    return `
        <div class="results-section tab-content-section" id="titlesSection" style="margin-bottom: 2rem; ${visible ? 'display: block;' : 'display: none;'}">
            <div class="results-header">
                <h3 class="results-title">
                    <i class="ph ph-sparkle"></i>
                    Generated Titles (${titles.length})
                </h3>
                <div class="results-actions">
                    <button class="action-btn" onclick="copyAllTitles()" title="Copy all titles">
                        <i class="ph ph-copy"></i> Copy All
                    </button>
                </div>
            </div>
            <div class="titles-content">
                <div class="titles-list">
                    ${titles.map((title, index) => `
                        <div class="title-item" id="title-item-${index}">
                            <span class="title-number">${index + 1}</span>
                            <span class="title-text">${escapeHtml(title)}</span>
                            <div class="title-actions">
                                <button class="title-action-btn" onclick="copyTitle(${index})" title="Copy title">
                                    <i class="ph ph-copy"></i>
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;
}

// Render description section
function renderDescriptionSection(description, visible) {
    return `
        <div class="results-section tab-content-section" id="descriptionSection" style="margin-bottom: 2rem; ${visible ? 'display: block;' : 'display: none;'}">
            <div class="results-header">
                <h3 class="results-title">
                    <i class="ph ph-file-text"></i>
                    Generated Description
                </h3>
                <div class="results-actions">
                    <button class="action-btn" onclick="copyDescription()" title="Copy description">
                        <i class="ph ph-copy"></i> Copy
                    </button>
                </div>
            </div>
            <div style="margin-top: 1rem; padding: 1.25rem; border: 1px solid var(--border-primary); border-radius: 8px; background: var(--bg-secondary);">
                <div style="color: var(--text-primary); line-height: 1.6; white-space: pre-wrap;" id="generatedDescription">${escapeHtml(description)}</div>
                <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-primary); color: var(--text-secondary); font-size: 0.875rem;">
                    ${description.length} characters
                </div>
            </div>
        </div>
    `;
}

// Render tags section
function renderTagsSection(tags, visible) {
    const totalChars = tags.join(', ').length;
    return `
        <div class="results-section tab-content-section" id="tagsSection" style="${visible ? 'display: block;' : 'display: none;'}">
            <div class="results-header">
                <h3 class="results-title">
                    <i class="ph ph-hash"></i>
                    Generated Tags (${tags.length})
                </h3>
                <div class="results-actions">
                    <button class="action-btn" onclick="copyGeneratedTags()" title="Copy tags">
                        <i class="ph ph-copy"></i> Copy
                    </button>
                </div>
            </div>
            <div class="tags-display-container">
                <div class="tags-display-wrapper">
                    ${tags.map(tag => `
                        <span class="tag-badge">${escapeHtml(tag)}</span>
                    `).join('')}
                </div>
                <div class="tags-display-info">
                    Total: ${totalChars} / 500 characters
                </div>
            </div>
        </div>
    `;
}

// Switch between result tabs
function switchTab(tabName) {
    // Hide all tab content sections
    document.querySelectorAll('.tab-content-section').forEach(section => {
        section.style.display = 'none';
    });

    // Remove active class from all tab buttons
    document.querySelectorAll('.results-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab content
    const sectionId = tabName + 'Section';
    const section = document.getElementById(sectionId);
    if (section) {
        section.style.display = 'block';
    }

    // Add active class to clicked button
    event.target.closest('.results-tab-btn').classList.add('active');
}

// Copy single title
async function copyTitle(index) {
    const title = currentTitles[index];
    try {
        await navigator.clipboard.writeText(title);
        showToast('Title copied to clipboard!', 'success');
    } catch (err) {
        console.error('Failed to copy:', err);
        showToast('Failed to copy title', 'error');
    }
}

// Copy all titles
async function copyAllTitles() {
    if (currentTitles && currentTitles.length > 0) {
        const allTitles = currentTitles.map((title, index) => `${index + 1}. ${title}`).join('\n');
        try {
            await navigator.clipboard.writeText(allTitles);
            showToast('All titles copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy titles', 'error');
        }
    }
}

// Copy description
function copyDescription() {
    const desc = currentDescription || document.getElementById('generatedDescription')?.textContent;
    if (desc) {
        navigator.clipboard.writeText(desc).then(() => {
            showToast('Description copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy description', 'error');
        });
    }
}

// Copy generated tags
function copyGeneratedTags() {
    if (currentTags && currentTags.length > 0) {
        const tagsText = currentTags.join(', ');
        navigator.clipboard.writeText(tagsText).then(() => {
            showToast('Tags copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy tags', 'error');
        });
    }
}

// Show toast notification
function showToast(message, type = 'success') {
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;

    let icon = 'ph-check-circle';
    if (type === 'error') icon = 'ph-x-circle';
    else if (type === 'info') icon = 'ph-info';

    toast.innerHTML = `
        <i class="ph ${icon}"></i>
        <span class="toast-text">${message}</span>
    `;

    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 100);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
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
    return text.replace(/[&<>"']/g, m => map[m]);
}
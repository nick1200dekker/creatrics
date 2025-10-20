/**
 * TikTok Titles & Hashtags Generator JavaScript
 * Handles generation of TikTok titles with hooks and hashtags
 */

// State management
let currentTitles = [];
let isGenerating = false;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateCharCount();
});

// Update character count
function updateCharCount() {
    const input = document.getElementById('videoInput');
    if (input) {
        const count = input.value.length;
        document.getElementById('charCount').textContent = `${count} / 3000`;
    }
}

// Main generate function
async function generateTitles() {
    const keywords = document.getElementById('keywordsInput').value.trim();
    const videoInput = document.getElementById('videoInput').value.trim();

    // Validation
    if (!keywords) {
        showToast('Please enter at least one target keyword', 'error');
        return;
    }

    if (isGenerating) return;

    isGenerating = true;
    const generateBtn = document.getElementById('generateBtn');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="ph ph-spinner"></i> Generating...';

    // Show loading state
    document.getElementById('resultsContainer').innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"></div>
            <div class="loading-text">Creating Your TikTok Content</div>
            <div class="loading-subtext">Generating titles with hooks and hashtags...</div>
        </div>
    `;

    try {
        // Call API to generate titles
        const response = await fetch('/tiktok/titles-hashtags/api/generate-tiktok-titles', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                keywords: keywords,
                video_input: videoInput
            })
        });

        const data = await response.json();

        if (!data.success) {
            // Check for insufficient credits
            if (data.error_type === 'insufficient_credits') {
                document.getElementById('resultsContainer').innerHTML = `
                    <div class="insufficient-credits-card">
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
                return;
            }
            throw new Error(data.error || 'Failed to generate titles');
        }

        // Display results
        displayResults(data.titles);
        showToast('Titles generated successfully!', 'success');

    } catch (error) {
        console.error('Error generating titles:', error);
        document.getElementById('resultsContainer').innerHTML = `
            <div class="error-state">
                <i class="ph ph-warning-circle error-icon"></i>
                <div class="error-title">Generation Failed</div>
                <div class="error-text">${error.message || 'Unable to generate titles. Please try again.'}</div>
            </div>
        `;
        showToast('Failed to generate titles', 'error');
    } finally {
        isGenerating = false;
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="ph ph-sparkle"></i> Generate Titles & Hashtags';
    }
}

// Display results
function displayResults(titles) {
    currentTitles = titles;

    let html = `
        <div class="results-section">
            <div class="results-header">
                <h3 class="results-title">
                    <i class="ph ph-hash"></i>
                    Generated TikTok Titles (${titles.length})
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

    document.getElementById('resultsContainer').innerHTML = html;
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

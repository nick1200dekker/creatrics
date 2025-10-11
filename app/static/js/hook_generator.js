// TikTok Hook Generator JavaScript
(function() {
    'use strict';

    // Initialize namespace
    window.CreatorPal = window.CreatorPal || {};
    window.CreatorPal.HookGenerator = window.CreatorPal.HookGenerator || {};

    // Check if already initialized
    if (window.CreatorPal.HookGenerator.initialized) {
        console.log('Hook Generator already initialized, skipping...');
        return;
    }

    // State management
    let currentHooks = [];
    let isGenerating = false;

    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        updateCharCount();
        window.CreatorPal.HookGenerator.initialized = true;
        console.log('Hook Generator initialized');
    });

    // Update character count
    function updateCharCount() {
        const input = document.getElementById('contentInput');
        const count = input.value.length;
        document.getElementById('charCount').textContent = `${count} / 5000`;
    }

    // Generate hooks
    async function generateHooks() {
        const input = document.getElementById('contentInput').value.trim();

        if (!input) {
            showToast('Please enter your video script, concept or content idea', 'error');
            return;
        }

        if (isGenerating) return;

        isGenerating = true;
        const generateBtn = document.getElementById('generateBtn');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="ph ph-spinner"></i> Generating Hooks...';

        // Show loading state
        document.getElementById('resultsContainer').innerHTML = `
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <div class="loading-text">Creating Powerful Hooks</div>
                <div class="loading-subtext">Analyzing your content to generate attention-grabbing hooks that keep viewers watching...</div>
            </div>
        `;

        try {
            const response = await fetch('/api/generate-tiktok-hooks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: input
                })
            });

            const data = await response.json();

            if (data.success) {
                currentHooks = data.hooks;
                displayResults(data.hooks);
                showToast('Hooks generated successfully!', 'success');
            } else {
                // Check if it's an insufficient credits error
                if (data.error_type === 'insufficient_credits') {
                    document.getElementById('resultsContainer').innerHTML = `
                        <div class="insufficient-credits-card">
                            <div class="credit-icon-wrapper">
                                <i class="ph ph-coins"></i>
                            </div>
                            <div class="credits-title">Insufficient Credits</div>
                            <div class="credits-description">
                                You need <strong>${data.required_credits?.toFixed(2) || '0.00'}</strong> credits but only have
                                <strong>${data.current_credits?.toFixed(2) || '0.00'}</strong> credits.
                            </div>
                            <a href="/payment" class="upgrade-btn-primary">
                                <i class="ph ph-crown"></i>
                                Upgrade Plan
                            </a>
                        </div>
                    `;
                } else {
                    throw new Error(data.error || 'Failed to generate hooks');
                }
            }
        } catch (error) {
            console.error('Error generating hooks:', error);
            document.getElementById('resultsContainer').innerHTML = `
                <div class="error-state">
                    <i class="ph ph-warning-circle error-icon"></i>
                    <div class="error-title">Generation Failed</div>
                    <div class="error-text">Unable to generate hooks. Please try again.</div>
                </div>
            `;
            showToast('Failed to generate hooks', 'error');
        } finally {
            isGenerating = false;
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="ph ph-sparkle"></i> Generate 10 Hooks';
        }
    }

    // Display results
    function displayResults(hooks) {
        let html = `
            <div class="results-header">
                <h3 class="results-title">
                    <i class="ph ph-check-circle"></i>
                    Generated Hooks (${hooks.length})
                </h3>
                <div class="results-actions">
                    <button class="action-btn" onclick="copyAllHooks()" title="Copy all hooks to clipboard">
                        <i class="ph ph-copy"></i> Copy All
                    </button>
                </div>
            </div>

            <div class="hooks-content">
                <div class="hooks-list">
        `;

        hooks.forEach((hookData, index) => {
            // Handle both old format (string) and new format (object with hook and emotion)
            const hookText = typeof hookData === 'string' ? hookData : hookData.hook;
            const emotion = typeof hookData === 'object' ? hookData.emotion : 'Curiosity';

            html += `
                <div class="hook-item">
                    <span class="hook-number">${index + 1}</span>
                    <div class="hook-content">
                        <span class="hook-text" id="hook-${index}">${escapeHtml(hookText)}</span>
                        <span class="emotion-badge">${escapeHtml(emotion)}</span>
                    </div>
                    <div class="hook-actions">
                        <button class="hook-action-btn copy" onclick="copyHook(${index})" title="Copy hook">
                            <i class="ph ph-copy"></i>
                        </button>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;

        document.getElementById('resultsContainer').innerHTML = html;
    }

    // Copy single hook
    async function copyHook(index) {
        const hookData = currentHooks[index];
        const hookText = typeof hookData === 'string' ? hookData : hookData.hook;

        try {
            await navigator.clipboard.writeText(hookText);
            showToast('Hook copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy hook', 'error');
        }
    }

    // Copy all hooks
    async function copyAllHooks() {
        if (currentHooks && currentHooks.length > 0) {
            const allHooks = currentHooks.map((hookData, index) => {
                const hookText = typeof hookData === 'string' ? hookData : hookData.hook;
                return `${index + 1}. ${hookText}`;
            }).join('\n\n');

            try {
                await navigator.clipboard.writeText(allHooks);
                showToast('All hooks copied to clipboard!', 'success');
            } catch (err) {
                console.error('Failed to copy:', err);
                showToast('Failed to copy hooks', 'error');
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

    // Expose functions to global scope for onclick handlers
    window.updateCharCount = updateCharCount;
    window.generateHooks = generateHooks;
    window.copyHook = copyHook;
    window.copyAllHooks = copyAllHooks;

})();

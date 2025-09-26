// Video Script Generator JavaScript
(function() {
    'use strict';
    
    // Initialize namespace
    window.CreatorPal = window.CreatorPal || {};
    window.CreatorPal.VideoScript = window.CreatorPal.VideoScript || {};
    
    // Check if already initialized
    if (window.CreatorPal.VideoScript.initialized) {
        console.log('Video Script Generator already initialized, skipping...');
        return;
    }

    // State management
    let currentVideoType = 'long';
    let currentScriptFormat = 'full';
    let currentScript = '';
    let isGenerating = false;
    let currentDuration = 10; // Default duration for long form (minutes)
    let targetDurationMode = false; // Default is best effort (AI decides)
    let isEditing = false;
    let scriptVersions = []; // Store all generated scripts
    let savedScripts = [];
    let scrollInterval = null;

    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        updateCharCount();
        // Start with best effort mode (slider hidden)
        const targetCheckbox = document.getElementById('targetDurationCheckbox');
        if (targetCheckbox) targetCheckbox.checked = false;

        const durationWrapper = document.getElementById('durationWrapper');
        if (durationWrapper) durationWrapper.classList.remove('active');

        // Load saved scripts
        loadSavedScripts();

        // Close modal when clicking outside
        const saveModal = document.getElementById('saveScriptModal');
        if (saveModal) {
            saveModal.addEventListener('click', function(e) {
                if (e.target === this) {
                    closeSaveModal();
                }
            });
        }

        // Allow Enter key to save in modal
        const titleInput = document.getElementById('scriptTitleInput');
        if (titleInput) {
            titleInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    saveScript();
                }
            });
        }

        window.CreatorPal.VideoScript.initialized = true;
        console.log('Video Script Generator initialized');
    });

    // Set video type
    function setVideoType(type) {
        currentVideoType = type;
        document.querySelectorAll('#longVideoBtn, #shortVideoBtn').forEach(btn => btn.classList.remove('active'));
        const slider = document.getElementById('durationSlider');
        const valueDisplay = document.getElementById('durationValue');

        if (type === 'long') {
            const longBtn = document.getElementById('longVideoBtn');
            if (longBtn) longBtn.classList.add('active');

            // Set slider for long form (1-20 minutes)
            if (slider) {
                slider.min = 1;
                slider.max = 20;
                slider.value = 10;
            }
            currentDuration = 10;
            if (valueDisplay) valueDisplay.textContent = '10 minutes';
        } else {
            const shortBtn = document.getElementById('shortVideoBtn');
            if (shortBtn) shortBtn.classList.add('active');

            // Set slider for shorts (1-60 seconds)
            if (slider) {
                slider.min = 1;
                slider.max = 60;
                slider.value = 30;
            }
            currentDuration = 30;
            if (valueDisplay) valueDisplay.textContent = '30 seconds';
        }
    }

    // Update duration display
    function updateDuration(value) {
        currentDuration = parseInt(value);
        const valueDisplay = document.getElementById('durationValue');

        if (currentVideoType === 'long') {
            valueDisplay.textContent = `${value} minute${value > 1 ? 's' : ''}`;
        } else {
            valueDisplay.textContent = `${value} second${value > 1 ? 's' : ''}`;
        }
    }

    // Set script format
    function setScriptFormat(format) {
        currentScriptFormat = format;
        document.querySelectorAll('#fullScriptBtn, #bulletPointsBtn').forEach(btn => btn.classList.remove('active'));
        if (format === 'full') {
            document.getElementById('fullScriptBtn').classList.add('active');
        } else {
            document.getElementById('bulletPointsBtn').classList.add('active');
        }
    }

    // Update character count
    function updateCharCount() {
        const input = document.getElementById('conceptInput');
        const count = input.value.length;
        document.getElementById('charCount').textContent = `${count} / 5000`;
    }

    // Toggle target duration mode
    function toggleTargetDuration() {
        targetDurationMode = document.getElementById('targetDurationCheckbox').checked;
        const wrapper = document.getElementById('durationWrapper');

        if (targetDurationMode) {
            // Show slider
            wrapper.classList.add('active');
            updateDuration(document.getElementById('durationSlider').value);
        } else {
            // Hide slider - use best effort
            wrapper.classList.remove('active');
        }
    }

    // Generate script
    async function generateScript() {
        const input = document.getElementById('conceptInput').value.trim();

        if (!input) {
            showToast('Please enter your video concept', 'error');
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
                <div class="loading-text">Creating Your Script</div>
                <div class="loading-subtext">Our AI is crafting your video script based on your concept. This may take a moment...</div>
            </div>
        `;

        try {
            const response = await fetch('/api/generate-video-script', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    concept: input,
                    videoType: currentVideoType,
                    scriptFormat: currentScriptFormat,
                    duration: targetDurationMode ? currentDuration : null
                })
            });

            const data = await response.json();

            if (data.success) {
                currentScript = data.script;
                scriptVersions.push(currentScript); // Store the script version
                displayScript(data.script);
                showToast('Script generated successfully!', 'success');
            } else {
                throw new Error(data.error || 'Failed to generate script');
            }
        } catch (error) {
            console.error('Error generating script:', error);
            document.getElementById('resultsContainer').innerHTML = `
                <div class="error-state">
                    <i class="ph ph-warning-circle error-icon"></i>
                    <div class="error-title">Generation Failed</div>
                    <div class="error-text">Unable to generate script. Please try again.</div>
                </div>
            `;
            showToast('Failed to generate script', 'error');
        } finally {
            isGenerating = false;
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="ph ph-magic-wand"></i> Generate Script';
        }
    }

    // Display script
    function displayScript(script) {
        let html = `
            <div class="results-header">
                <h3 class="results-title">
                    <i class="ph ph-check-circle"></i>
                    Generated Script
                </h3>
                <div class="actions-dropdown" id="actionsDropdown">
                    <button class="actions-dropdown-btn" onclick="toggleDropdown()">
                        <i class="ph ph-dots-three"></i>
                        Actions
                    </button>
                    <div class="actions-dropdown-menu">
                        <button class="dropdown-item" onclick="toggleEditMode()">
                            <i class="ph ph-pencil"></i>
                            ${isEditing ? 'Save Edits' : 'Edit Script'}
                        </button>
                        <button class="dropdown-item" onclick="saveScriptDialog()">
                            <i class="ph ph-floppy-disk"></i>
                            Save Script
                        </button>
                        <button class="dropdown-item" onclick="openFullscreen()">
                            <i class="ph ph-arrows-out"></i>
                            Teleprompter
                        </button>
                        <div class="dropdown-divider"></div>
                        <button class="dropdown-item" onclick="undoLastChange()" ${scriptVersions.length <= 1 ? 'disabled' : ''}>
                            <i class="ph ph-arrow-counter-clockwise"></i>
                            Undo
                        </button>
                        <div class="dropdown-divider"></div>
                        <button class="dropdown-item" onclick="copyScript()">
                            <i class="ph ph-copy"></i>
                            Copy Script
                        </button>
                        <button class="dropdown-item" onclick="downloadScript()">
                            <i class="ph ph-download"></i>
                            Download
                        </button>
                    </div>
                </div>
            </div>
            <div class="script-content" id="scriptContent">
        `;

        if (isEditing) {
            // Edit mode
            let editText = '';
            if (typeof script === 'string') {
                editText = script;
            } else if (script.bullets) {
                editText = script.bullets.join('\n\n');
            }

            html += `<textarea class="edit-mode-textarea" id="editableScript" oninput="updateCurrentScript(this.value)">${escapeHtml(editText)}</textarea>`;
        } else {
            // Normal display
            if (typeof script === 'string') {
                html += formatScriptText(script);
            } else if (script && Array.isArray(script.bullets)) {
                html += '<ul class="bullet-list">';
                script.bullets.forEach(bullet => {
                    html += `<li class="bullet-item">${escapeHtml(bullet)}</li>`;
                });
                html += '</ul>';
            } else {
                // Fallback for any unexpected format
                html += formatScriptText('Error: Could not display script. Please try generating again.');
            }
        }

        html += '</div>';

        // Add AI Agent section
        html += `
            <div class="ai-agent-section">
                <div class="ai-agent-header">
                    <h4 class="ai-agent-title">
                        <i class="ph ph-robot"></i>
                        AI Agent - Modify Your Script
                    </h4>
                </div>
                <div class="ai-agent-content">
                    <div class="ai-prompt-group">
                        <input type="text"
                               id="aiModifyInput"
                               class="ai-modify-input"
                               placeholder="e.g., 'make it shorter', 'add more humor', 'change tone to professional', 'focus more on benefits'"
                               onkeypress="if(event.key === 'Enter') modifyScriptWithAI()"/>
                        <button class="ai-modify-btn" onclick="modifyScriptWithAI()" id="aiModifyBtn">
                            <i class="ph ph-magic-wand"></i>
                            Modify
                        </button>
                    </div>
                    <div class="ai-suggestions">
                        <span class="suggestion-label">Quick actions:</span>
                        <button class="suggestion-chip" onclick="setAIPrompt('Make it 30% shorter')">
                            <i class="ph ph-scissors"></i> Shorten
                        </button>
                        <button class="suggestion-chip" onclick="setAIPrompt('Make it more engaging and energetic')">
                            <i class="ph ph-lightning"></i> More Energy
                        </button>
                        <button class="suggestion-chip" onclick="setAIPrompt('Add a strong hook at the beginning')">
                            <i class="ph ph-hook"></i> Better Hook
                        </button>
                        <button class="suggestion-chip" onclick="setAIPrompt('Make the tone more casual and conversational')">
                            <i class="ph ph-chat-circle"></i> Casual Tone
                        </button>
                        <button class="suggestion-chip" onclick="setAIPrompt('Add a clear call-to-action')">
                            <i class="ph ph-megaphone"></i> Add CTA
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.getElementById('resultsContainer').innerHTML = html;
    }

    // Format script text with line breaks
    function formatScriptText(text) {
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    // Toggle dropdown
    function toggleDropdown() {
        const dropdown = document.getElementById('actionsDropdown');
        dropdown.classList.toggle('open');
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function closeDropdown(e) {
            if (!dropdown.contains(e.target)) {
                dropdown.classList.remove('open');
                document.removeEventListener('click', closeDropdown);
            }
        });
        
        event.stopPropagation();
    }

    // Toggle edit mode
    function toggleEditMode() {
        isEditing = !isEditing;
        if (currentScript) {
            displayScript(currentScript);
        }
        
        // Close dropdown after action
        document.getElementById('actionsDropdown').classList.remove('open');
    }

    // Update current script when editing
    function updateCurrentScript(newText) {
        // Store the edited text as current script
        currentScript = newText;
    }

    // Utility functions continue below

    // Open fullscreen teleprompter
    function openFullscreen() {
        // Close dropdown first
        document.getElementById('actionsDropdown').classList.remove('open');
        
        // Get the most current version of the script
        let textToDisplay = '';
        
        // Check if we're in edit mode first and get the edited text
        const editableScript = document.getElementById('editableScript');
        if (isEditing && editableScript) {
            textToDisplay = editableScript.value;
        } else if (typeof currentScript === 'string') {
            textToDisplay = currentScript;
        } else if (currentScript && currentScript.bullets) {
            textToDisplay = currentScript.bullets.join('\n\n');
        }

        // Make sure we have text to display
        if (!textToDisplay) {
            showToast('No script available to display', 'error');
            return;
        }

        const fullscreenHTML = `
            <div class="fullscreen-container active" id="fullscreenContainer">
                <div class="fullscreen-header">
                    <div class="fullscreen-controls">
                        <button class="fullscreen-btn" onclick="closeFullscreen()">
                            <i class="ph ph-x"></i> Close
                        </button>
                        <button class="fullscreen-btn" onclick="toggleScroll()" id="scrollBtn">
                            <i class="ph ph-play"></i> Auto-scroll
                        </button>
                        <button class="fullscreen-btn" onclick="toggleTeleprompterTheme()" id="themeBtn">
                            <i class="ph ph-sun"></i> Light Mode
                        </button>
                        <div class="scroll-speed-control">
                            <label>Speed:</label>
                            <input type="range" class="scroll-speed-slider" id="scrollSpeed" min="1" max="10" value="5">
                        </div>
                    </div>
                </div>
                <div class="fullscreen-content" id="fullscreenContent">
                    <div class="teleprompter-fullscreen" id="teleprompterText">
                        ${escapeHtml(textToDisplay).replace(/\n/g, '<br>')}
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', fullscreenHTML);
        
        // Reset scroll to top
        document.getElementById('fullscreenContent').scrollTop = 0;
    }

    // Close fullscreen
    function closeFullscreen() {
        const container = document.getElementById('fullscreenContainer');
        if (container) {
            if (scrollInterval) {
                clearInterval(scrollInterval);
                scrollInterval = null;
            }
            container.remove();
        }
    }

    // Toggle teleprompter theme
    function toggleTeleprompterTheme() {
        const container = document.getElementById('fullscreenContainer');
        const themeBtn = document.getElementById('themeBtn');
        
        if (container.classList.contains('light-mode')) {
            // Switch to dark mode
            container.classList.remove('light-mode');
            themeBtn.innerHTML = '<i class="ph ph-sun"></i> Light Mode';
        } else {
            // Switch to light mode
            container.classList.add('light-mode');
            themeBtn.innerHTML = '<i class="ph ph-moon"></i> Dark Mode';
        }
    }

    // Auto-scroll functionality
    function toggleScroll() {
        const btn = document.getElementById('scrollBtn');
        const content = document.getElementById('fullscreenContent');

        if (scrollInterval) {
            clearInterval(scrollInterval);
            scrollInterval = null;
            btn.innerHTML = '<i class="ph ph-play"></i> Auto-scroll';
        } else {
            const speed = document.getElementById('scrollSpeed').value;
            scrollInterval = setInterval(() => {
                content.scrollTop += speed / 2;
            }, 50);
            btn.innerHTML = '<i class="ph ph-pause"></i> Pause';
        }
    }

    // Copy script
    async function copyScript() {
        let textToCopy = '';

        // Get the current text (edited or original)
        if (isEditing) {
            const editableScript = document.getElementById('editableScript');
            if (editableScript) {
                textToCopy = editableScript.value;
            }
        } else if (typeof currentScript === 'string') {
            textToCopy = currentScript;
        } else if (currentScript.bullets) {
            textToCopy = currentScript.bullets.map(bullet => `• ${bullet}`).join('\n');
        }

        try {
            await navigator.clipboard.writeText(textToCopy);
            showToast('Script copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy script', 'error');
        }
        
        // Close dropdown after action
        document.getElementById('actionsDropdown').classList.remove('open');
    }

    // Download script
    function downloadScript() {
        let textToDownload = '';

        if (isEditing) {
            const editableScript = document.getElementById('editableScript');
            if (editableScript) {
                textToDownload = editableScript.value;
            }
        } else if (typeof currentScript === 'string') {
            textToDownload = currentScript;
        } else if (currentScript.bullets) {
            textToDownload = currentScript.bullets.map(bullet => `• ${bullet}`).join('\n');
        }

        const blob = new Blob([textToDownload], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `video-script-${currentVideoType}-${currentScriptFormat}-${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('Script downloaded successfully!', 'success');
        
        // Close dropdown after action
        document.getElementById('actionsDropdown').classList.remove('open');
    }

    // Show toast notification
    function showToast(message, type = 'success') {
        // Remove existing toast
        const existingToast = document.querySelector('.toast-notification');
        if (existingToast) {
            existingToast.remove();
        }

        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        
        const icon = type === 'success' ? 'ph-check-circle' : type === 'error' ? 'ph-x-circle' : 'ph-info';
        
        toast.innerHTML = `
            <i class="ph ${icon}"></i>
            <span class="toast-text">${message}</span>
        `;

        document.body.appendChild(toast);

        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);

        // Hide toast
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

    // Save script modal functions
    function saveScriptDialog() {
        const modal = document.getElementById('saveScriptModal');
        modal.classList.add('active');

        // Focus on title input
        setTimeout(() => {
            document.getElementById('scriptTitleInput').focus();
        }, 100);

        // Close dropdown
        document.getElementById('actionsDropdown').classList.remove('open');
    }

    function closeSaveModal() {
        const modal = document.getElementById('saveScriptModal');
        modal.classList.remove('active');

        // Clear inputs
        document.getElementById('scriptTitleInput').value = '';
        document.getElementById('scriptDescriptionInput').value = '';
    }

    // Save script functionality
    async function saveScript() {
        const title = document.getElementById('scriptTitleInput').value.trim();
        const description = document.getElementById('scriptDescriptionInput').value.trim();

        if (!title) {
            showToast('Please enter a title for your script', 'info');
            document.getElementById('scriptTitleInput').focus();
            return;
        }

        const saveBtn = document.getElementById('modalSaveBtn');
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="ph ph-spinner"></i> Saving...';

        try {
            const scriptToSave = isEditing ? document.getElementById('editableScript').value : currentScript;

            const response = await fetch('/api/video-script/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: title,
                    description: description,
                    script: scriptToSave,
                    videoType: currentVideoType,
                    scriptFormat: currentScriptFormat,
                    duration: targetDurationMode ? currentDuration : null,
                    concept: document.getElementById('conceptInput').value
                })
            });

            const data = await response.json();
            if (data.success) {
                showToast('Script saved successfully!', 'success');
                loadSavedScripts(); // Refresh the saved scripts list
                closeSaveModal(); // Close the modal
            } else {
                showToast('Failed to save script', 'error');
            }
        } catch (error) {
            console.error('Error saving script:', error);
            showToast('Failed to save script', 'error');
        } finally {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<i class="ph ph-floppy-disk"></i> Save Script';
        }
    }

    // Load saved scripts
    async function loadSavedScripts() {
        try {
            const response = await fetch('/api/video-script/list');
            const data = await response.json();

            if (data.success) {
                savedScripts = data.scripts;
                displaySavedScripts(savedScripts);
            }
        } catch (error) {
            console.error('Error loading saved scripts:', error);
        }
    }

    // Display saved scripts
    function displaySavedScripts(scripts) {
        const grid = document.getElementById('savedScriptsGrid');

        if (scripts.length === 0) {
            grid.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 2rem;">No saved scripts yet</p>';
            return;
        }

        grid.innerHTML = scripts.map(script => {
            const preview = typeof script.script === 'string'
                ? script.script.substring(0, 80)
                : script.script.bullets ? script.script.bullets[0] : '';

            const date = new Date(script.created_at).toLocaleDateString();
            const type = script.video_type === 'short' ? '📱 Short' : '🎬 Long';
            const format = script.script_format === 'bullet' ? 'Bullets' : 'Full';

            return `
                <div class="saved-script-card" onclick="loadScript('${script.id}')">
                    <div class="saved-script-title">${escapeHtml(script.title)}</div>
                    <div class="saved-script-meta">
                        <span>${type} • ${format}</span>
                        <span>${date}</span>
                    </div>
                    <div class="saved-script-preview">${escapeHtml(preview)}...</div>
                    <div class="saved-script-actions">
                        <button class="saved-script-btn" onclick="event.stopPropagation(); loadScript('${script.id}')">
                            <i class="ph ph-folder-open"></i> Load
                        </button>
                        <button class="saved-script-btn" onclick="event.stopPropagation(); deleteScript('${script.id}')">
                            <i class="ph ph-trash"></i> Delete
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Load a specific script
    async function loadScript(scriptId) {
        try {
            const response = await fetch(`/api/video-script/${scriptId}`);
            const data = await response.json();

            if (data.success) {
                const script = data.script;

                // Update the UI with loaded script
                currentScript = script.script;
                currentVideoType = script.video_type;
                currentScriptFormat = script.script_format;

                // Update the concept input if available
                if (script.concept) {
                    document.getElementById('conceptInput').value = script.concept;
                    updateCharCount();
                }

                // Update video type buttons
                setVideoType(currentVideoType);

                // Update script format buttons
                setScriptFormat(currentScriptFormat);

                // Update duration if available
                if (script.duration) {
                    document.getElementById('targetDurationCheckbox').checked = true;
                    toggleTargetDuration();
                    document.getElementById('durationSlider').value = script.duration;
                    updateDuration(script.duration);
                }

                // Display the loaded script
                displayScript(currentScript);

                // Add to versions for undo
                scriptVersions = [currentScript];

                showToast('Script loaded successfully!', 'success');
            }
        } catch (error) {
            console.error('Error loading script:', error);
            showToast('Failed to load script', 'error');
        }
    }

    // Delete script
    async function deleteScript(scriptId) {
        if (!confirm('Are you sure you want to delete this script?')) return;

        try {
            const response = await fetch(`/api/video-script/${scriptId}`, {
                method: 'DELETE'
            });

            const data = await response.json();
            if (data.success) {
                showToast('Script deleted successfully!', 'success');
                loadSavedScripts(); // Refresh the list
            }
        } catch (error) {
            console.error('Error deleting script:', error);
            showToast('Failed to delete script', 'error');
        }
    }

    // Search scripts
    function searchScripts() {
        const searchTerm = document.getElementById('scriptSearchInput').value.toLowerCase();

        if (!searchTerm) {
            displaySavedScripts(savedScripts);
            return;
        }

        const filtered = savedScripts.filter(script => {
            const titleMatch = script.title.toLowerCase().includes(searchTerm);
            const contentMatch = typeof script.script === 'string'
                ? script.script.toLowerCase().includes(searchTerm)
                : script.script.bullets && script.script.bullets.some(b => b.toLowerCase().includes(searchTerm));

            return titleMatch || contentMatch;
        });

        displaySavedScripts(filtered);
    }

    // Toggle saved scripts section
    function toggleSavedScripts() {
        const grid = document.getElementById('savedScriptsGrid');
        const search = document.getElementById('savedScriptsSearch');
        const btn = document.querySelector('.toggle-saved-btn i');

        if (!grid || !search || !btn) return;

        if (grid.style.display === 'none' || grid.style.display === '') {
            grid.style.display = 'block';
            search.style.display = 'block';
            btn.className = 'ph ph-caret-up';
        } else {
            grid.style.display = 'none';
            search.style.display = 'none';
            btn.className = 'ph ph-caret-down';
        }
    }

    // Set AI prompt from suggestion chips
    function setAIPrompt(prompt) {
        document.getElementById('aiModifyInput').value = prompt;
        document.getElementById('aiModifyInput').focus();
    }

    // AI Modification
    async function modifyScriptWithAI() {
        const modifyInput = document.getElementById('aiModifyInput');
        const modification = modifyInput.value.trim();

        if (!modification) {
            showToast('Please enter a modification request', 'info');
            modifyInput.focus();
            return;
        }

        const scriptToModify = isEditing ? document.getElementById('editableScript').value : currentScript;

        // Disable the button and show loading state
        const modifyBtn = document.getElementById('aiModifyBtn');
        modifyBtn.disabled = true;
        modifyBtn.innerHTML = '<i class="ph ph-spinner"></i> Modifying...';

        // Show loading state
        showToast('Modifying script with AI...', 'info');

        try {
            // For now, we'll call the generate endpoint with the modification request
            // In the future, this could be a dedicated endpoint
            const modificationPrompt = `Please modify the following script according to this request: "${modification}"\n\nOriginal Script:\n${typeof scriptToModify === 'string' ? scriptToModify : scriptToModify.bullets.join('\n')}`;

            const response = await fetch('/api/generate-video-script', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    concept: modificationPrompt,
                    videoType: currentVideoType,
                    scriptFormat: currentScriptFormat,
                    duration: targetDurationMode ? currentDuration : null
                })
            });

            const data = await response.json();

            if (data.success) {
                // Store current version for undo
                scriptVersions.push(currentScript);

                // Update with modified script
                currentScript = data.script;
                displayScript(currentScript);
                showToast('Script modified successfully!', 'success');

                // Clear the input
                modifyInput.value = '';
            } else {
                showToast('Failed to modify script', 'error');
            }
        } catch (error) {
            console.error('Error modifying script:', error);
            showToast('Failed to modify script', 'error');
        } finally {
            // Re-enable the button
            modifyBtn.disabled = false;
            modifyBtn.innerHTML = '<i class="ph ph-magic-wand"></i> Modify';
        }
    }

    // Undo last change
    function undoLastChange() {
        if (scriptVersions.length <= 1) {
            showToast('No previous version to undo to', 'info');
            return;
        }

        // Remove current version
        scriptVersions.pop();

        // Get previous version
        currentScript = scriptVersions[scriptVersions.length - 1];

        // Display the previous version
        displayScript(currentScript);

        showToast('Reverted to previous version', 'success');

        // Close dropdown
        document.getElementById('actionsDropdown').classList.remove('open');
    }

    // Expose functions to global scope for onclick handlers
    window.setVideoType = setVideoType;
    window.updateDuration = updateDuration;
    window.setScriptFormat = setScriptFormat;
    window.updateCharCount = updateCharCount;
    window.toggleTargetDuration = toggleTargetDuration;
    window.generateScript = generateScript;
    window.toggleDropdown = toggleDropdown;
    window.toggleEditMode = toggleEditMode;
    window.updateCurrentScript = updateCurrentScript;
    window.openFullscreen = openFullscreen;
    window.closeFullscreen = closeFullscreen;
    window.toggleTeleprompterTheme = toggleTeleprompterTheme;
    window.toggleScroll = toggleScroll;
    window.copyScript = copyScript;
    window.downloadScript = downloadScript;
    window.saveScriptDialog = saveScriptDialog;
    window.closeSaveModal = closeSaveModal;
    window.saveScript = saveScript;
    window.loadScript = loadScript;
    window.deleteScript = deleteScript;
    window.searchScripts = searchScripts;
    window.toggleSavedScripts = toggleSavedScripts;
    window.setAIPrompt = setAIPrompt;
    window.modifyScriptWithAI = modifyScriptWithAI;
    window.undoLastChange = undoLastChange;

})();

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
let selectedVideoFile = null;
let selectedThumbnailFile = null;
let selectedTitle = null;
let hasYouTubeConnected = false;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateCharCount();
    updateRefDescCharCount();
    updateChannelKeywordsCharCount();
    loadChannelKeywords();
    loadReferenceDescription();
    checkYouTubeConnection();
});

/**
 * Check if user has YouTube connected
 */
async function checkYouTubeConnection() {
    try {
        const response = await fetch('/api/check-youtube-connection');
        const data = await response.json();

        hasYouTubeConnected = data.connected;

        if (!data.connected) {
            // Show connection notice and hide upload section
            const uploadSection = document.getElementById('videoUploadSection');
            if (uploadSection) {
                uploadSection.innerHTML = `
                    <label class="form-label">
                        <i class="ph ph-upload"></i>
                        Upload Video
                    </label>
                    <div style="padding: 1rem; background: var(--bg-tertiary); border: 1px solid var(--border-primary); border-radius: 8px; text-align: center;">
                        <i class="ph ph-youtube-logo" style="font-size: 2rem; color: var(--text-tertiary); margin-bottom: 0.5rem; display: block;"></i>
                        <div style="color: var(--text-secondary); margin-bottom: 0.75rem;">Connect your YouTube account to upload videos</div>
                        <a href="/accounts/social-accounts" style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; background: var(--primary); color: white; border-radius: 6px; text-decoration: none; font-weight: 500;">
                            <i class="ph ph-link"></i>
                            Connect YouTube
                        </a>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.log('Could not check YouTube connection:', error);
        hasYouTubeConnected = false;
    }
}

/**
 * Trigger video file upload
 */
function triggerVideoUpload() {
    const fileInput = document.getElementById('videoFileInput');
    if (fileInput) {
        fileInput.click();
    }
}

/**
 * Handle video file selection
 */
function handleVideoSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Check if YouTube is connected
    if (!hasYouTubeConnected) {
        showToast('Please connect your YouTube account first', 'error');
        event.target.value = '';
        return;
    }

    // Validate file type
    if (!file.type.startsWith('video/')) {
        showToast('Please select a valid video file', 'error');
        return;
    }

    // Store the file
    selectedVideoFile = file;

    // Auto-select all generation options (titles, description, tags)
    const titlesCard = document.getElementById('titlesCard');
    const descriptionCard = document.getElementById('descriptionCard');
    const tagsCard = document.getElementById('tagsCard');

    if (!titlesCard.classList.contains('active')) {
        toggleGenerationCard(titlesCard, 'titles');
    }
    if (!descriptionCard.classList.contains('active')) {
        toggleGenerationCard(descriptionCard, 'description');
    }
    if (!tagsCard.classList.contains('active')) {
        toggleGenerationCard(tagsCard, 'tags');
    }

    // Update UI to show selected file
    const uploadContent = document.getElementById('uploadContent');
    const uploadProgress = document.getElementById('uploadProgress');
    const fileName = document.getElementById('uploadFileName');
    const fileSize = document.getElementById('uploadFileSize');

    uploadContent.style.display = 'none';
    uploadProgress.style.display = 'flex';
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);

    showToast('Video selected! All content types auto-selected.', 'success');
}

/**
 * Remove selected video
 */
function removeVideo(event) {
    event.stopPropagation();

    selectedVideoFile = null;
    const fileInput = document.getElementById('videoFileInput');
    if (fileInput) {
        fileInput.value = '';
    }

    const uploadContent = document.getElementById('uploadContent');
    const uploadProgress = document.getElementById('uploadProgress');

    uploadContent.style.display = 'flex';
    uploadProgress.style.display = 'none';
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

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

// Update character count for channel keywords
function updateChannelKeywordsCharCount() {
    const input = document.getElementById('channelKeywords');
    const count = input.value.length;
    document.getElementById('channelKeywordsCharCount').textContent = `${count} / 2000`;
}

// Toggle reference section
function toggleReferenceSection() {
    const content = document.getElementById('referenceContent');
    const toggle = document.getElementById('referenceToggle');

    if (content.classList.contains('show')) {
        content.classList.remove('show');
        toggle.innerHTML = '<i class="ph ph-caret-down"></i>';
    } else {
        content.classList.add('show');
        toggle.innerHTML = '<i class="ph ph-caret-up"></i>';
    }
}

// Toggle channel keywords section
function toggleChannelKeywordsSection() {
    const content = document.getElementById('channelKeywordsContent');
    const toggle = document.getElementById('channelKeywordsToggle');

    if (content.classList.contains('show')) {
        content.classList.remove('show');
        toggle.innerHTML = '<i class="ph ph-caret-down"></i>';
    } else {
        content.classList.add('show');
        toggle.innerHTML = '<i class="ph ph-caret-up"></i>';
    }
}

// Clear reference description
function clearReferenceDescription() {
    const refDesc = document.getElementById('referenceDescription');
    refDesc.value = '';
    updateRefDescCharCount();
    showToast('Reference description cleared', 'info');
}

// Save reference description to backend
async function saveReferenceDescription() {
    const refDesc = document.getElementById('referenceDescription').value.trim();

    if (!refDesc) {
        showToast('No reference description to save', 'error');
        return;
    }

    const saveBtn = document.getElementById('saveRefDescBtn');
    const originalContent = saveBtn.innerHTML;

    try {
        const response = await fetch('/api/save-reference-description', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ reference_description: refDesc })
        });

        const data = await response.json();

        if (data.success) {
            // Change button to "Saved" with checkmark
            saveBtn.innerHTML = '<i class="ph ph-check"></i> Saved';
            showToast('Reference description saved successfully!', 'success');

            // Revert back to "Save" after 2 seconds
            setTimeout(() => {
                saveBtn.innerHTML = originalContent;
            }, 2000);
        } else {
            showToast('Failed to save reference description', 'error');
        }
    } catch (error) {
        console.error('Error saving reference description:', error);
        showToast('Failed to save reference description', 'error');
    }
}

// Clear channel keywords
function clearChannelKeywords() {
    const keywords = document.getElementById('channelKeywords');
    keywords.value = '';
    updateChannelKeywordsCharCount();
    showToast('Channel keywords cleared', 'info');
}

// Save channel keywords to backend
async function saveChannelKeywords() {
    const keywordsInput = document.getElementById('channelKeywords').value.trim();

    if (!keywordsInput) {
        showToast('No channel keywords to save', 'error');
        return;
    }

    // Parse keywords (comma-separated)
    const keywords = keywordsInput.split(',').map(k => k.trim()).filter(k => k);

    const saveBtn = document.getElementById('saveKeywordsBtn');
    const originalContent = saveBtn.innerHTML;

    try {
        const response = await fetch('/api/save-channel-keywords', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ keywords: keywords })
        });

        const data = await response.json();

        if (data.success) {
            // Change button to "Saved" with checkmark
            saveBtn.innerHTML = '<i class="ph ph-check"></i> Saved';
            showToast('Channel keywords saved successfully!', 'success');

            // Revert back to "Save" after 2 seconds
            setTimeout(() => {
                saveBtn.innerHTML = originalContent;
            }, 2000);
        } else {
            showToast('Failed to save channel keywords', 'error');
        }
    } catch (error) {
        console.error('Error saving channel keywords:', error);
        showToast('Failed to save channel keywords', 'error');
    }
}

// Load channel keywords from backend
async function loadChannelKeywords() {
    try {
        const response = await fetch('/api/get-channel-keywords', {
            method: 'GET',
            headers: {'Content-Type': 'application/json'}
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success && data.keywords && data.keywords.length > 0) {
                const keywordsInput = document.getElementById('channelKeywords');
                keywordsInput.value = data.keywords.join(', ');
                updateChannelKeywordsCharCount();
            }
        }
    } catch (error) {
        console.log('Could not load channel keywords:', error);
    }
}

// Load reference description from backend
async function loadReferenceDescription() {
    try {
        const response = await fetch('/api/get-reference-description', {
            method: 'GET',
            headers: {'Content-Type': 'application/json'}
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success && data.reference_description) {
                const refDescInput = document.getElementById('referenceDescription');
                refDescInput.value = data.reference_description;
                updateRefDescCharCount();
            }
        }
    } catch (error) {
        console.log('Could not load reference description:', error);
    }
}

// Toggle generation card selection
function toggleGenerationCard(card, type) {
    card.classList.toggle('active');

    // Show/hide reference description section based on Description card selection
    if (type === 'description') {
        const referenceSection = document.getElementById('referenceDescriptionSection');
        if (card.classList.contains('active')) {
            referenceSection.style.display = 'block';
        } else {
            referenceSection.style.display = 'none';
        }
    }

    // Show/hide channel keywords section based on Tags card selection
    if (type === 'tags') {
        const channelKeywordsSection = document.getElementById('channelKeywordsSection');
        if (card.classList.contains('active')) {
            channelKeywordsSection.style.display = 'block';
        } else {
            channelKeywordsSection.style.display = 'none';
        }
    }
}

// Main generate function
async function generateContent() {
    const input = document.getElementById('videoInput').value.trim();
    const keyword = document.getElementById('keywordInput').value.trim();
    const referenceDescription = document.getElementById('referenceDescription').value.trim();
    const generateTitles = document.getElementById('titlesCard').classList.contains('active');
    const generateDescription = document.getElementById('descriptionCard').classList.contains('active');
    const generateTags = document.getElementById('tagsCard').classList.contains('active');

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
            <div class="loading-spinner"><i class="ph ph-spinner"></i></div>
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
            enhancedInput = `CRITICAL: You MUST start titles with this keyword: "${keyword}"\nIMPORTANT: Capitalize the keyword appropriately for a professional title (brand names, proper nouns, etc.)\n\nVIDEO CONTENT:\n${input}`;
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
                if (titlesData.error_type === 'insufficient_credits') {
                    showInsufficientCreditsError();
                    return;
                }
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
                    reference_description: referenceDescription,
                    keyword: keyword
                })
            });
            descriptionData = await descResponse.json();

            if (!descriptionData.success) {
                if (descriptionData.error_type === 'insufficient_credits') {
                    showInsufficientCreditsError();
                    return;
                }
                throw new Error(descriptionData.error || 'Failed to generate description');
            }
        }

        // Generate tags if requested
        if (generateTags) {
            // Get channel keywords from input (user can override)
            const channelKeywordsInput = document.getElementById('channelKeywords').value.trim();
            const channelKeywords = channelKeywordsInput
                ? channelKeywordsInput.split(',').map(k => k.trim()).filter(k => k)
                : [];

            const tagsResponse = await fetch('/api/generate-video-tags', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    input: enhancedInput,
                    keyword: keyword,
                    channel_keywords: channelKeywords
                })
            });
            tagsData = await tagsResponse.json();

            if (!tagsData.success) {
                if (tagsData.error_type === 'insufficient_credits') {
                    showInsufficientCreditsError();
                    return;
                }
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
        if (selectedVideoFile && hasYouTubeConnected) {
            html += `
                <button class="results-tab-btn" onclick="switchTab('upload')">
                    <i class="ph ph-upload"></i> Upload
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

    // Display Upload Section (only if YouTube connected)
    if (selectedVideoFile && hasYouTubeConnected) {
        html += renderUploadSection(!showTabs);
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
            ${selectedVideoFile && hasYouTubeConnected ? `
                <div class="title-selection-notice">
                    <i class="ph ph-info"></i>
                    <span>Click on a title below to select it for your video</span>
                </div>
            ` : ''}
            <div class="titles-content">
                <div class="titles-list">
                    ${titles.map((title, index) => `
                        <div class="title-item ${selectedTitle === index ? 'selected' : ''}" id="title-item-${index}" ${selectedVideoFile && hasYouTubeConnected ? `onclick="selectTitle(${index})"` : ''}>
                            <span class="title-number">${index + 1}</span>
                            <div class="title-text" contenteditable="false" id="title-text-${index}">${escapeHtml(title)}</div>
                            <div class="title-actions">
                                ${hasYouTubeConnected ? `
                                    <button class="title-action-btn edit-title-btn" onclick="toggleEditTitleItem(event, ${index})" title="Edit title">
                                        <i class="ph ph-pencil-simple"></i>
                                    </button>
                                ` : ''}
                                <button class="title-action-btn" onclick="copyTitle(${index}, event)" title="Copy title">
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

/**
 * Select a title for upload
 */
function selectTitle(index) {
    selectedTitle = index;

    // Update UI - highlight selected title
    document.querySelectorAll('.title-item').forEach((item, i) => {
        if (i === index) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });

    // Enable upload button
    const uploadBtn = document.getElementById('uploadBtn');
    if (uploadBtn) {
        uploadBtn.disabled = false;
        uploadBtn.style.opacity = '1';
        uploadBtn.style.cursor = 'pointer';
    }
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
                    ${hasYouTubeConnected ? `
                        <button class="action-btn edit-desc-btn" onclick="toggleEditDescription()" title="Edit description" id="editDescBtn">
                            <i class="ph ph-pencil-simple"></i> Edit
                        </button>
                    ` : ''}
                    <button class="action-btn" onclick="copyDescription()" title="Copy description">
                        <i class="ph ph-copy"></i> Copy
                    </button>
                </div>
            </div>
            <div style="margin-top: 1rem; padding: 1.25rem; border: 1px solid var(--border-primary); border-radius: 8px; background: var(--bg-secondary);">
                <textarea style="width: 100%; color: var(--text-primary); line-height: 1.6; white-space: pre-wrap; background: transparent; border: none; outline: none; resize: vertical; min-height: 150px; font-family: inherit;" id="generatedDescription" readonly>${escapeHtml(description)}</textarea>
                <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-primary); color: var(--text-secondary); font-size: 0.875rem;" id="descCharCount">
                    ${description.length} characters
                </div>
            </div>
        </div>
    `;
}

// Render tags section
function renderTagsSection(tags, visible) {
    const totalChars = tags.join(', ').length;

    // If YouTube not connected, show simple tags display
    if (!hasYouTubeConnected) {
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

    // If YouTube connected, show editable tags
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
            <div class="tags-editor-container">
                <div class="tags-list-editable" id="editableTagsList">
                    ${tags.map((tag, index) => `
                        <span class="tag tag-editable">
                            ${escapeHtml(tag)}
                            <button class="tag-delete-btn" onclick="deleteGeneratedTag(${index})" title="Remove tag">
                                <i class="ph ph-x"></i>
                            </button>
                        </span>
                    `).join('')}
                </div>
                <div class="tag-input-wrapper">
                    <input type="text" class="tag-input" id="newTagInput" placeholder="Type tag and press Enter to add..." onkeypress="handleTagInputKeypress(event)"/>
                </div>
                <div class="char-count-section">
                    <div class="char-count-header">
                        <span class="char-count-label">Character Usage</span>
                        <span class="char-count-value" id="tagsCharCount">${totalChars} / 500</span>
                    </div>
                    <div class="char-count-progress">
                        <div class="char-count-fill ${totalChars > 500 ? 'error' : totalChars > 450 ? 'warning' : totalChars >= 400 ? 'good' : ''}" id="tagsCharFill" style="width: ${Math.min((totalChars / 500) * 100, 100)}%"></div>
                    </div>
                    <div class="char-count-info">
                        <span class="tag-count">Tags: <strong id="tagsCountValue">${tags.length}</strong></span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Render upload section
function renderUploadSection(visible) {
    const titleSelected = selectedTitle !== null;
    return `
        <div class="results-section tab-content-section" id="uploadSection" style="${visible ? 'display: block;' : 'display: none;'}">
            <div class="upload-section-content">
                ${!titleSelected ? `
                    <div class="upload-warning">
                        <i class="ph ph-warning"></i>
                        <span>Please select a title from the Titles tab before uploading</span>
                    </div>
                ` : ''}

                <div class="upload-options-grid">
                    <!-- Privacy Status -->
                    <div class="upload-option-card">
                        <label class="upload-option-label">
                            <i class="ph ph-lock-key"></i>
                            Privacy Status
                        </label>
                        <select class="privacy-select" id="privacySelect">
                            <option value="private">Private</option>
                            <option value="unlisted">Unlisted</option>
                            <option value="public">Public</option>
                        </select>
                    </div>

                    <!-- Thumbnail Upload -->
                    <div class="upload-option-card">
                        <label class="upload-option-label">
                            <i class="ph ph-image"></i>
                            Thumbnail (Optional)
                        </label>
                        <button class="thumbnail-upload-btn" onclick="selectThumbnail()">
                            <i class="ph ph-upload-simple"></i>
                            <span id="thumbnailBtnText">Choose File</span>
                        </button>
                        <input type="file" id="thumbnailFileInput" accept="image/jpeg,image/jpg,image/png" style="display: none;" onchange="handleThumbnailSelect(event)">
                    </div>
                </div>

                <div id="thumbnailPreview" style="display: none;" class="thumbnail-preview-card">
                    <img id="thumbnailImg" class="thumbnail-preview-img">
                    <div class="thumbnail-preview-info">
                        <div id="thumbnailName" class="thumbnail-preview-name"></div>
                        <button onclick="removeThumbnail()" class="thumbnail-remove-btn">
                            <i class="ph ph-x"></i> Remove
                        </button>
                    </div>
                </div>

                <button class="upload-video-btn" onclick="uploadToYouTube()" id="uploadBtn" ${!titleSelected ? 'disabled' : ''}>
                    <i class="ph ph-youtube-logo"></i>
                    Upload to YouTube
                </button>
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

/**
 * Toggle edit mode for title item
 */
function toggleEditTitleItem(event, index) {
    event.stopPropagation();

    const textEl = document.getElementById(`title-text-${index}`);
    const button = event.currentTarget;
    const icon = button.querySelector('i');

    if (textEl.getAttribute('contenteditable') === 'false') {
        // Enter edit mode
        textEl.setAttribute('contenteditable', 'true');
        textEl.focus();
        icon.className = 'ph ph-check';
        button.title = 'Save';
        textEl.style.outline = '2px solid #3B82F6';
        textEl.style.padding = '0.25rem';
        textEl.style.borderRadius = '4px';
    } else {
        // Exit edit mode and update the title
        textEl.setAttribute('contenteditable', 'false');
        icon.className = 'ph ph-pencil-simple';
        button.title = 'Edit';
        textEl.style.outline = 'none';
        textEl.style.padding = '0';

        // Update currentTitles array
        currentTitles[index] = textEl.textContent.trim();
    }
}

/**
 * Toggle edit mode for description
 */
function toggleEditDescription() {
    const textarea = document.getElementById('generatedDescription');
    const button = document.getElementById('editDescBtn');
    const icon = button.querySelector('i');
    const span = button.querySelector('span') || button;

    if (textarea.hasAttribute('readonly')) {
        // Enter edit mode
        textarea.removeAttribute('readonly');
        textarea.focus();
        icon.className = 'ph ph-check';
        if (span.tagName === 'SPAN') span.textContent = 'Save';
        textarea.style.outline = '2px solid #3B82F6';
    } else {
        // Exit edit mode
        textarea.setAttribute('readonly', 'true');
        icon.className = 'ph ph-pencil-simple';
        if (span.tagName === 'SPAN') span.textContent = 'Edit';
        textarea.style.outline = 'none';

        // Update current description
        currentDescription = textarea.value;

        // Update character count
        const charCount = document.getElementById('descCharCount');
        if (charCount) {
            charCount.textContent = `${currentDescription.length} characters`;
        }
    }
}

/**
 * Delete a generated tag
 */
function deleteGeneratedTag(index) {
    currentTags.splice(index, 1);
    updateTagsDisplay();
}

/**
 * Handle tag input keypress
 */
function handleTagInputKeypress(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        const input = document.getElementById('newTagInput');
        const newTag = input.value.trim();

        if (newTag) {
            currentTags.push(newTag);
            input.value = '';
            updateTagsDisplay();
        }
    }
}

/**
 * Update tags display after changes
 */
function updateTagsDisplay() {
    const tagsList = document.getElementById('editableTagsList');
    const totalChars = currentTags.join(', ').length;

    tagsList.innerHTML = currentTags.map((tag, index) => `
        <span class="tag tag-editable">
            ${escapeHtml(tag)}
            <button class="tag-delete-btn" onclick="deleteGeneratedTag(${index})" title="Remove tag">
                <i class="ph ph-x"></i>
            </button>
        </span>
    `).join('');

    // Update counts
    document.getElementById('tagsCharCount').textContent = `${totalChars} / 500`;
    document.getElementById('tagsCountValue').textContent = currentTags.length;

    // Update progress bar
    const fill = document.getElementById('tagsCharFill');
    fill.style.width = `${Math.min((totalChars / 500) * 100, 100)}%`;
    fill.className = `char-count-fill ${totalChars > 500 ? 'error' : totalChars > 450 ? 'warning' : totalChars >= 400 ? 'good' : ''}`;
}

/**
 * Select thumbnail file
 */
function selectThumbnail() {
    const fileInput = document.getElementById('thumbnailFileInput');
    if (fileInput) {
        fileInput.click();
    }
}

/**
 * Handle thumbnail file selection
 */
function handleThumbnailSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    if (!['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)) {
        showToast('Only JPG and PNG images are supported', 'error');
        return;
    }

    // Validate file size (2MB limit for YouTube)
    if (file.size > 2 * 1024 * 1024) {
        showToast('Image must be smaller than 2MB', 'error');
        return;
    }

    selectedThumbnailFile = file;

    // Update button text
    const btnText = document.getElementById('thumbnailBtnText');
    if (btnText) {
        btnText.textContent = file.name.length > 20 ? file.name.substring(0, 20) + '...' : file.name;
    }

    // Show preview
    const preview = document.getElementById('thumbnailPreview');
    const img = document.getElementById('thumbnailImg');
    const name = document.getElementById('thumbnailName');

    const reader = new FileReader();
    reader.onload = function(e) {
        img.src = e.target.result;
        name.textContent = file.name;
        preview.style.display = 'flex';
    };
    reader.readAsDataURL(file);
}

/**
 * Remove thumbnail
 */
function removeThumbnail() {
    selectedThumbnailFile = null;
    const fileInput = document.getElementById('thumbnailFileInput');
    if (fileInput) {
        fileInput.value = '';
    }

    const btnText = document.getElementById('thumbnailBtnText');
    if (btnText) {
        btnText.textContent = 'Choose File';
    }

    const preview = document.getElementById('thumbnailPreview');
    if (preview) {
        preview.style.display = 'none';
    }
}

/**
 * Upload video to YouTube
 */
async function uploadToYouTube() {
    if (!selectedVideoFile) {
        showToast('Please select a video file', 'error');
        return;
    }

    if (selectedTitle === null) {
        showToast('Please select a title from the Titles tab', 'error');
        return;
    }

    const title = currentTitles[selectedTitle];
    const description = currentDescription || '';
    const tags = currentTags || [];

    // Get privacy status
    const privacySelect = document.getElementById('privacySelect');
    const privacyStatus = privacySelect ? privacySelect.value : 'private';

    const uploadBtn = document.getElementById('uploadBtn');
    const originalContent = uploadBtn.innerHTML;

    try {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="ph ph-spinner"></i> Uploading...';

        // Create FormData
        const formData = new FormData();
        formData.append('video', selectedVideoFile);
        formData.append('title', title);
        formData.append('description', description);
        formData.append('tags', JSON.stringify(tags));
        formData.append('privacy_status', privacyStatus);

        if (selectedThumbnailFile) {
            formData.append('thumbnail', selectedThumbnailFile);
        }

        // Upload video
        const response = await fetch('/api/upload-youtube-video', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to upload video');
        }

        showToast('Video uploaded successfully to YouTube!', 'success');

        const privacyLabel = privacyStatus.charAt(0).toUpperCase() + privacyStatus.slice(1);

        // Show success message with video link
        const resultsContainer = document.getElementById('resultsContainer');
        resultsContainer.innerHTML = `
            <div style="text-align: center; padding: 3rem;">
                <div style="font-size: 4rem; color: #10B981; margin-bottom: 1rem;">
                    <i class="ph ph-check-circle"></i>
                </div>
                <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Video Uploaded Successfully!</h3>
                <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">
                    Your video has been uploaded to YouTube as ${privacyLabel}.
                </p>
                <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                    <a href="https://studio.youtube.com/video/${data.video_id}/edit" target="_blank" class="generate-btn">
                        <i class="ph ph-youtube-logo"></i> View in YouTube Studio
                    </a>
                    <button class="action-btn" onclick="location.reload()">
                        <i class="ph ph-arrow-counter-clockwise"></i> Upload Another
                    </button>
                </div>
            </div>
        `;

        // Reset state
        selectedVideoFile = null;
        selectedThumbnailFile = null;
        selectedTitle = null;

    } catch (error) {
        console.error('Error uploading video:', error);
        showToast('Failed to upload video: ' + error.message, 'error');
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalContent;
    }
}

// Copy single title
async function copyTitle(index, event) {
    if (event) event.stopPropagation();

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

/**
 * Show insufficient credits error
 */
function showInsufficientCreditsError() {
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
}
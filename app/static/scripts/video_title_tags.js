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
let uploadedVideoPath = null; // Server path to uploaded video
let uploadedThumbnailPath = null; // Server path to uploaded thumbnail

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
                    <div style="padding: 0 1.5rem 1.5rem 1.5rem; background: transparent; border: 1px solid var(--border-primary); border-radius: 10px; text-align: center;">
                        <img src="/static/img/templates/yt_icon_red_digital.png" alt="YouTube" style="width: 64px; height: auto; margin: -0.5rem auto -1rem auto; display: block;">
                        <div style="color: var(--text-primary); margin-bottom: 1rem; font-size: 0.875rem; font-weight: 500;">Connect your YouTube account to upload videos<br>Or generate titles, description & tags and upload manual</div>
                        <a href="/accounts/" class="secondary-button">
                            <i class="ph ph-link"></i>
                            <span>Connect YouTube</span>
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
async function handleVideoSelect(event) {
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

    // Update UI to show file info
    const uploadContent = document.getElementById('uploadContent');
    const uploadProgress = document.getElementById('uploadProgress');
    const fileName = document.getElementById('uploadFileName');
    const fileSize = document.getElementById('uploadFileSize');

    uploadContent.style.display = 'none';
    uploadProgress.style.display = 'flex';
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);

    // Start uploading to server immediately
    await uploadVideoToServer(file);
}

/**
 * Remove selected video
 */
async function removeVideo(event) {
    event.stopPropagation();

    // Delete video from server if it was uploaded
    if (uploadedVideoPath) {
        try {
            await fetch('/api/delete-temp-video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    video_path: uploadedVideoPath
                })
            });
        } catch (error) {
            console.error('Error deleting temp video:', error);
        }
    }

    selectedVideoFile = null;
    uploadedVideoPath = null;

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

/**
 * Store video file reference for later upload to YouTube
 */
async function uploadVideoToServer(file) {
    const progressContainer = document.getElementById('videoUploadProgressContainer');

    try {
        // Just store the file reference - no upload yet
        // Upload will happen directly to YouTube when user clicks "Upload to YouTube"
        uploadedVideoPath = null; // No intermediate storage needed
        selectedVideoFile = file; // Keep file reference for direct YouTube upload

        // Hide progress bar - we don't need it for file selection
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }

        showToast('Video selected! Generate titles/tags and click "Upload to YouTube"', 'success');

    } catch (error) {
        console.error('Error selecting video:', error);
        showToast('Failed to select video: ' + error.message, 'error');

        // Hide progress and reset
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }

        // Re-enable remove button
        if (removeBtn) {
            removeBtn.disabled = false;
            removeBtn.style.opacity = '1';
        }

        // Reset file input
        const fileInput = document.getElementById('videoFileInput');
        if (fileInput) {
            fileInput.value = '';
        }

        // Hide upload progress section
        const uploadContent = document.getElementById('uploadContent');
        const uploadProgress = document.getElementById('uploadProgress');
        if (uploadContent && uploadProgress) {
            uploadContent.style.display = 'flex';
            uploadProgress.style.display = 'none';
        }
    }
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

    // Switch reference description textarea
    const refLong = document.getElementById('referenceDescriptionLong');
    const refShort = document.getElementById('referenceDescriptionShort');
    const refLabel = document.getElementById('refDescLabel');

    if (type === 'long') {
        if (refLong) refLong.style.display = 'block';
        if (refShort) refShort.style.display = 'none';
        if (refLabel) refLabel.textContent = 'Reference Description (Long Form)';
    } else {
        if (refLong) refLong.style.display = 'none';
        if (refShort) refShort.style.display = 'block';
        if (refLabel) refLabel.textContent = 'Reference Description (Shorts)';
    }

    // Update character count for visible textarea
    updateRefDescCharCount();
}

// Update character count for main input
function updateCharCount() {
    const input = document.getElementById('videoInput');
    const count = input.value.length;
    document.getElementById('charCount').textContent = `${count} / 5000`;
}

// Update character count for reference description
function updateRefDescCharCount() {
    const refLong = document.getElementById('referenceDescriptionLong');
    const refShort = document.getElementById('referenceDescriptionShort');
    const charCountEl = document.getElementById('refDescCharCount');

    if (!charCountEl) return;

    // Count based on currently visible textarea
    if (currentVideoType === 'long' && refLong) {
        const count = refLong.value.length;
        charCountEl.textContent = `${count} / 5000`;
    } else if (currentVideoType === 'short' && refShort) {
        const count = refShort.value.length;
        charCountEl.textContent = `${count} / 5000`;
    }
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
    const refLong = document.getElementById('referenceDescriptionLong');
    const refShort = document.getElementById('referenceDescriptionShort');

    if (currentVideoType === 'long' && refLong) {
        refLong.value = '';
    } else if (currentVideoType === 'short' && refShort) {
        refShort.value = '';
    }

    updateRefDescCharCount();
    showToast('Reference description cleared', 'info');
}

// Save reference description to backend
async function saveReferenceDescription() {
    const refLong = document.getElementById('referenceDescriptionLong');
    const refShort = document.getElementById('referenceDescriptionShort');

    const refDescLongValue = refLong ? refLong.value.trim() : '';
    const refDescShortValue = refShort ? refShort.value.trim() : '';

    if (!refDescLongValue && !refDescShortValue) {
        showToast('No reference description to save', 'error');
        return;
    }

    const saveBtn = document.getElementById('saveRefDescBtn');
    const originalContent = saveBtn.innerHTML;

    try {
        const response = await fetch('/api/save-reference-description', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                reference_description_long: refDescLongValue,
                reference_description_short: refDescShortValue
            })
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
            if (data.success) {
                const refLongInput = document.getElementById('referenceDescriptionLong');
                const refShortInput = document.getElementById('referenceDescriptionShort');

                if (data.reference_description_long && refLongInput) {
                    refLongInput.value = data.reference_description_long;
                }
                if (data.reference_description_short && refShortInput) {
                    refShortInput.value = data.reference_description_short;
                }

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

    // Get correct reference description based on video type
    const refLong = document.getElementById('referenceDescriptionLong');
    const refShort = document.getElementById('referenceDescriptionShort');
    const referenceDescription = (currentVideoType === 'long' && refLong) ? refLong.value.trim() : (refShort ? refShort.value.trim() : '');

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
            <div style="margin-top: 1rem; padding: 1.25rem; border: 1px solid var(--border-primary); border-radius: 10px; background: var(--bg-secondary);">
                <textarea style="width: 100%; color: var(--text-primary); line-height: 1.6; white-space: pre-wrap; background: transparent; border: none; resize: vertical; font-family: inherit;" id="generatedDescription" readonly>${escapeHtml(description)}</textarea>
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
    return `
        <div class="results-section tab-content-section" id="uploadSection" style="${visible ? 'display: block;' : 'display: none;'}">
            <div class="upload-section-content">
                <div class="upload-options-grid">
                    <!-- Language -->
                    <div class="upload-option-card" style="grid-column: 1;">
                        <label class="upload-option-label">
                            <i class="ph ph-globe"></i>
                            Language
                        </label>
                        <select class="privacy-select" id="languageSelect">
                            <option value="en" selected>English</option>
                            <option value="es">Spanish (Español)</option>
                            <option value="fr">French (Français)</option>
                            <option value="de">German (Deutsch)</option>
                            <option value="it">Italian (Italiano)</option>
                            <option value="pt">Portuguese (Português)</option>
                            <option value="nl">Dutch (Nederlands)</option>
                            <option value="ru">Russian (Русский)</option>
                            <option value="ja">Japanese (日本語)</option>
                            <option value="ko">Korean (한국어)</option>
                            <option value="zh-CN">Chinese Simplified (简体中文)</option>
                            <option value="zh-TW">Chinese Traditional (繁體中文)</option>
                            <option value="ar">Arabic (العربية)</option>
                            <option value="hi">Hindi (हिन्दी)</option>
                            <option value="pl">Polish (Polski)</option>
                            <option value="tr">Turkish (Türkçe)</option>
                        </select>
                    </div>

                    <!-- Thumbnail Upload -->
                    <div class="upload-option-card" style="grid-column: 2;">
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

                    <!-- Privacy Status -->
                    <div class="upload-option-card" id="statusCard" style="grid-column: 1;">
                        <label class="upload-option-label">
                            <i class="ph ph-lock-key"></i>
                            Status
                        </label>
                        <select class="privacy-select" id="privacySelect" onchange="handleStatusChange()">
                            <option value="private" selected>Private</option>
                            <option value="unlisted">Unlisted</option>
                            <option value="public">Public</option>
                            <option value="scheduled">Schedule</option>
                        </select>
                    </div>

                    <!-- Schedule Date/Time (appears when scheduled is selected) -->
                    <div class="upload-option-card" id="scheduleDateTime" style="grid-column: 2; display: none;">
                        <label class="upload-option-label schedule-label">
                            <i class="ph ph-calendar"></i>
                            Publish Date & Time
                        </label>
                        <input type="datetime-local" class="privacy-select schedule-datetime-input" id="scheduleInput" onclick="this.showPicker()">
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

                <button class="upload-video-btn" onclick="uploadToYouTube()" id="uploadBtn">
                    <i class="ph ph-upload"></i>
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
        
        // Store the original styling
        textEl.dataset.originalBg = textEl.style.background || '';
        
        // Light highlight for edit mode
        textEl.style.background = 'var(--bg-tertiary)';
        textEl.style.padding = '0.25rem 0.5rem';
        textEl.style.borderRadius = '6px';
    } else {
        // Exit edit mode and update the title
        textEl.setAttribute('contenteditable', 'false');
        icon.className = 'ph ph-pencil-simple';
        button.title = 'Edit';
        
        // Restore original styling
        textEl.style.background = textEl.dataset.originalBg || '';
        textEl.style.padding = '0';
        textEl.style.borderRadius = '0';

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
    } else {
        // Exit edit mode
        textarea.setAttribute('readonly', 'true');
        icon.className = 'ph ph-pencil-simple';
        if (span.tagName === 'SPAN') span.textContent = 'Edit';

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
async function handleThumbnailSelect(event) {
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

    // Upload thumbnail to server immediately
    await uploadThumbnailToServer(file);
}

/**
 * Upload thumbnail to server
 */
async function uploadThumbnailToServer(file) {
    try {
        const formData = new FormData();
        formData.append('thumbnail', file);

        const response = await fetch('/api/upload-thumbnail-temp', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to upload thumbnail');
        }

        // Store the uploaded thumbnail path
        uploadedThumbnailPath = data.thumbnail_path;
        console.log('Thumbnail uploaded to server:', uploadedThumbnailPath);

    } catch (error) {
        console.error('Error uploading thumbnail:', error);
        showToast('Failed to upload thumbnail: ' + error.message, 'error');
        uploadedThumbnailPath = null;
    }
}

/**
 * Remove thumbnail
 */
function removeThumbnail() {
    selectedThumbnailFile = null;
    uploadedThumbnailPath = null;

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
 * Handle status change (show/hide schedule datetime)
 */
function handleStatusChange() {
    const privacySelect = document.getElementById('privacySelect');
    const scheduleDateTime = document.getElementById('scheduleDateTime');
    const scheduleInput = document.getElementById('scheduleInput');

    if (privacySelect && scheduleDateTime) {
        if (privacySelect.value === 'scheduled') {
            scheduleDateTime.style.display = 'block';

            // Set default to tomorrow at 12:00 if not already set
            if (scheduleInput && !scheduleInput.value) {
                const tomorrow = new Date();
                tomorrow.setDate(tomorrow.getDate() + 1);
                tomorrow.setHours(12, 0, 0, 0);

                // Format as datetime-local (YYYY-MM-DDTHH:mm)
                const year = tomorrow.getFullYear();
                const month = String(tomorrow.getMonth() + 1).padStart(2, '0');
                const day = String(tomorrow.getDate()).padStart(2, '0');
                const hours = String(tomorrow.getHours()).padStart(2, '0');
                const minutes = String(tomorrow.getMinutes()).padStart(2, '0');

                scheduleInput.value = `${year}-${month}-${day}T${hours}:${minutes}`;
            }
        } else {
            scheduleDateTime.style.display = 'none';
        }
    }
}

/**
 * Upload video to YouTube
 */
async function uploadToYouTube() {
    if (!selectedVideoFile) {
        showToast('Please select a video file first', 'error');
        return;
    }

    if (selectedTitle === null) {
        showToast('Please select a title from the Titles tab', 'error');
        return;
    }

    const title = currentTitles[selectedTitle];
    const description = currentDescription || '';
    const tags = currentTags || [];

    // Get privacy status and language
    const privacySelect = document.getElementById('privacySelect');
    const privacyStatus = privacySelect ? privacySelect.value : 'private';

    const languageSelect = document.getElementById('languageSelect');
    const language = languageSelect ? languageSelect.value : 'en';

    // Get scheduled date/time if status is scheduled
    let scheduledTime = null;
    if (privacyStatus === 'scheduled') {
        const scheduleInput = document.getElementById('scheduleInput');
        if (!scheduleInput || !scheduleInput.value) {
            showToast('Please select a publish date and time', 'error');
            return;
        }
        scheduledTime = scheduleInput.value;
    }

    const uploadBtn = document.getElementById('uploadBtn');
    const originalContent = uploadBtn.innerHTML;

    // Show upload progress modal
    showUploadProgressModal();

    try {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="ph ph-spinner"></i> Uploading...';

        // Update progress modal
        updateUploadProgress('Preparing upload...', 'uploading');

        // Get target keyword if provided
        const keywordInput = document.getElementById('keywordInput');
        const targetKeyword = keywordInput && keywordInput.value.trim() ? keywordInput.value.trim() : '';

        // Step 1: Get YouTube upload URL from backend
        const initResponse = await fetch('/api/init-youtube-upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: title,
                description: description,
                tags: tags,
                privacy_status: privacyStatus === 'scheduled' ? 'private' : privacyStatus,
                language: language,
                scheduled_time: scheduledTime,
                target_keyword: targetKeyword,
                file_size: selectedVideoFile.size,
                mime_type: selectedVideoFile.type
            })
        });

        const initData = await initResponse.json();

        if (!initData.success) {
            throw new Error(initData.error || 'Failed to initialize upload');
        }

        // Step 2: Upload video directly to YouTube with progress tracking
        updateUploadProgress('Uploading video to YouTube...', 'uploading');

        const uploadXHR = new XMLHttpRequest();

        // Track upload progress
        uploadXHR.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                updateUploadProgress(`Uploading to YouTube... ${percentComplete}%`, 'uploading');
            }
        });

        // Upload the file
        await new Promise((resolve, reject) => {
            uploadXHR.onload = () => {
                // Upload succeeded if we get 200 or 201
                // Note: We can't read responseText due to CORS, but upload worked!
                if (uploadXHR.status >= 200 && uploadXHR.status < 300) {
                    resolve();
                } else {
                    reject(new Error(`Upload failed with status ${uploadXHR.status}`));
                }
            };
            uploadXHR.onerror = () => reject(new Error('Network error'));

            uploadXHR.open('PUT', initData.upload_url);
            uploadXHR.setRequestHeader('Authorization', `Bearer ${initData.access_token}`);
            uploadXHR.setRequestHeader('Content-Type', selectedVideoFile.type);
            uploadXHR.send(selectedVideoFile);
        });

        // Get video ID from backend (extract from upload URL or query recent uploads)
        updateUploadProgress('Retrieving video information...', 'processing');

        const videoIdResponse = await fetch('/api/get-uploaded-video-id', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                upload_url: initData.upload_url,
                title: title
            })
        });

        const videoIdData = await videoIdResponse.json();

        if (!videoIdData.success || !videoIdData.video_id) {
            throw new Error(videoIdData.error || 'Failed to get video ID');
        }

        const videoId = videoIdData.video_id;

        // Step 3: Finalize upload (save metadata, handle thumbnail)
        updateUploadProgress('Finalizing upload...', 'processing');

        const finalizeData = {
            video_id: videoId,
            thumbnail_path: uploadedThumbnailPath,
            target_keyword: targetKeyword
        };

        const finalizeResponse = await fetch('/api/finalize-youtube-upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(finalizeData)
        });

        const finalData = await finalizeResponse.json();

        if (!finalData.success) {
            throw new Error(finalData.error || 'Failed to finalize upload');
        }

        // Update progress to processing
        updateUploadProgress('Processing video on YouTube...', 'processing');

        // Small delay to show processing state
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Hide progress modal
        hideUploadProgressModal();

        const data = { success: true, video_id: videoId };

        showToast('Video uploaded successfully to YouTube!', 'success');

        const privacyLabel = privacyStatus.charAt(0).toUpperCase() + privacyStatus.slice(1);

        // Show success message with video link
        const resultsContainer = document.getElementById('resultsContainer');
        resultsContainer.innerHTML = `
            <div style="max-width: 500px; margin: 2rem auto; text-align: center; padding: 2.5rem; background: var(--bg-secondary); border: 1px solid var(--border-primary); border-radius: 12px;">
                <div style="width: 64px; height: 64px; margin: 0 auto 1.5rem; background: linear-gradient(135deg, #10B981 0%, #059669 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);">
                    <i class="ph-fill ph-check" style="font-size: 2rem; color: white;"></i>
                </div>
                <h3 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1.5rem; font-weight: 600;">Upload Complete!</h3>
                <p style="color: var(--text-secondary); margin-bottom: 2rem; font-size: 0.9375rem; line-height: 1.6;">
                    Your video is now live on YouTube as <strong style="color: var(--text-primary);">${privacyLabel}</strong>
                </p>
                <div style="display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 1.5rem;">
                    <a href="https://studio.youtube.com/video/${data.video_id}/edit" target="_blank" style="display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.75rem 1.5rem; background: var(--primary); color: white; border-radius: 8px; text-decoration: none; font-weight: 500; transition: all 0.2s ease; font-size: 0.9375rem;">
                        <i class="ph ph-arrow-square-out"></i> Open in YouTube Studio
                    </a>
                    <button onclick="location.reload()" style="display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.75rem 1.5rem; background: transparent; color: var(--text-secondary); border: 1px solid var(--border-primary); border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s ease; font-size: 0.9375rem;">
                        <i class="ph ph-arrow-counter-clockwise"></i> Upload Another Video
                    </button>
                </div>
                <div style="padding-top: 1.5rem; border-top: 1px solid var(--border-primary);">
                    <p style="color: var(--text-tertiary); font-size: 0.8125rem; margin: 0;">
                        Video ID: <code style="padding: 0.125rem 0.375rem; background: var(--bg-tertiary); border-radius: 4px; font-size: 0.75rem; color: var(--text-secondary);">${data.video_id}</code>
                    </p>
                </div>
            </div>
        `;

        // Reset state
        selectedVideoFile = null;
        selectedThumbnailFile = null;
        selectedTitle = null;
        uploadedVideoPath = null;
        uploadedThumbnailPath = null;

    } catch (error) {
        console.error('Error uploading video:', error);
        hideUploadProgressModal();

        // Check for quota exceeded error
        const errorMessage = error.message || '';
        if (errorMessage.includes('quota') || errorMessage.includes('Quota') || errorMessage.includes('quotaExceeded')) {
            showQuotaExceededModal();
        } else {
            showToast('Failed to upload video: ' + error.message, 'error');
        }

        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalContent;
    }
}

/**
 * Show quota exceeded modal with clean "Try Tomorrow" message
 */
function showQuotaExceededModal() {
    // Remove existing modals if any
    const existingModals = document.querySelectorAll('.upload-progress-modal, .quota-exceeded-modal-overlay');
    existingModals.forEach(modal => modal.remove());

    // Create modal
    const modal = document.createElement('div');
    modal.className = 'quota-exceeded-modal-overlay';
    modal.innerHTML = `
        <div class="quota-exceeded-modal">
            <div class="quota-modal-header">
                <i class="ph ph-clock"></i>
                <h3>YouTube API Quota Exceeded</h3>
            </div>
            <div class="quota-modal-content">
                <p class="quota-message">Daily YouTube API quota limit hit.</p>
                <p class="quota-submessage">We've requested more quota from YouTube. Resets at <strong>midnight Pacific Time</strong>.</p>
            </div>
            <div class="quota-modal-actions">
                <button class="quota-modal-btn" onclick="this.closest('.quota-exceeded-modal-overlay').remove()">Got It, Try Tomorrow</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Show with animation
    setTimeout(() => modal.classList.add('show'), 10);

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        }
    });
}

/**
 * Show upload progress modal
 */
function showUploadProgressModal() {
    // Remove existing modal if any
    const existingModal = document.getElementById('uploadProgressModal');
    if (existingModal) {
        existingModal.remove();
    }

    const modal = document.createElement('div');
    modal.id = 'uploadProgressModal';
    modal.className = 'upload-progress-modal';
    modal.innerHTML = `
        <div class="upload-progress-overlay"></div>
        <div class="upload-progress-content">
            <div class="upload-spinner-container">
                <i class="ph ph-spinner upload-spinner-icon"></i>
            </div>
            <h3 id="uploadProgressTitle" style="color: var(--text-primary); margin: 1.5rem 0 0.5rem; font-size: 1.25rem; font-weight: 600;">Uploading to YouTube</h3>
            <p id="uploadProgressMessage" style="color: var(--text-secondary); margin: 0 0 1rem; font-size: 0.9375rem;">Please wait while we upload your video to YouTube</p>

            <div style="margin: 1rem 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="color: var(--text-tertiary); font-size: 0.8125rem;">Progress</span>
                    <span id="uploadProgressPercent" style="color: var(--text-primary); font-size: 0.875rem; font-weight: 600;">0%</span>
                </div>
                <div style="width: 100%; height: 6px; background: var(--bg-tertiary); border-radius: 3px; overflow: hidden; border: 1px solid var(--border-primary);">
                    <div id="uploadProgressFill" style="height: 100%; width: 0%; background: #3B82F6; transition: width 0.3s ease;"></div>
                </div>
            </div>

            <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 1rem; margin: 1.5rem 0 1rem;">
                <div style="display: flex; align-items: start; gap: 0.75rem;">
                    <i class="ph-fill ph-warning-circle" style="color: #F59E0B; font-size: 1.5rem; margin-top: 0.125rem; flex-shrink: 0;"></i>
                    <div style="flex: 1;">
                        <p style="color: var(--text-primary); font-size: 0.875rem; font-weight: 600; margin: 0 0 0.5rem;">Don't close this page</p>
                        <p style="color: var(--text-secondary); font-size: 0.8125rem; margin: 0 0 1rem; line-height: 1.5;">Keep this tab open while uploading. Want to keep working?</p>
                        <button onclick="window.open('/', '_blank')" style="display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.625rem 1.25rem; background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem; font-weight: 600; transition: all 0.2s ease; box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);" onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 4px 12px rgba(59, 130, 246, 0.4)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(59, 130, 246, 0.3)'">
                            <i class="ph-fill ph-plus-circle" style="font-size: 1.125rem;"></i> Open Creatrics in New Tab
                        </button>
                    </div>
                </div>
            </div>

            <p style="color: var(--text-tertiary); font-size: 0.75rem; margin: 0; text-align: center;">
                Large videos may take several minutes to upload
            </p>
        </div>
    `;
    document.body.appendChild(modal);

    // Trigger animation
    setTimeout(() => modal.classList.add('show'), 10);
}

/**
 * Update upload progress
 */
function updateUploadProgress(message, stage) {
    const titleEl = document.getElementById('uploadProgressTitle');
    const messageEl = document.getElementById('uploadProgressMessage');
    const percentEl = document.getElementById('uploadProgressPercent');
    const fillEl = document.getElementById('uploadProgressFill');

    if (titleEl) {
        if (stage === 'uploading') {
            titleEl.textContent = 'Uploading to YouTube';
        } else if (stage === 'processing') {
            titleEl.textContent = 'Processing Video';
        }
    }

    if (messageEl) {
        messageEl.textContent = message;
    }

    // Extract percentage from message if present
    const percentMatch = message.match(/(\d+)%/);
    if (percentMatch && percentEl && fillEl) {
        const percent = parseInt(percentMatch[1]);
        percentEl.textContent = `${percent}%`;
        fillEl.style.width = `${percent}%`;
    } else if (stage === 'processing') {
        // Show indeterminate progress for processing
        if (fillEl) {
            fillEl.style.width = '100%';
        }
        if (percentEl) {
            percentEl.textContent = 'Processing...';
        }
    }
}

/**
 * Hide upload progress modal
 */
function hideUploadProgressModal() {
    const modal = document.getElementById('uploadProgressModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);
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
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

    // Set up connect/disconnect button listeners
    const connectBtn = document.getElementById('connectBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectToYouTube);
    }

    const disconnectBtn = document.getElementById('disconnectBtn');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectFromYouTube);
    }
});

/**
 * Check if user has YouTube connected via Late.dev
 */
async function checkYouTubeConnection() {
    try {
        const response = await fetch('/video-title-tags/api/youtube-latedev-status');
        const data = await response.json();

        hasYouTubeConnected = data.connected;
        updateConnectionUI(data);

        // Hide video upload section if not connected (connection status card handles messaging)
        const uploadSection = document.getElementById('videoUploadSection');
        if (uploadSection) {
            uploadSection.style.display = data.connected ? 'block' : 'none';
        }
    } catch (error) {
        console.log('Could not check YouTube connection:', error);
        hasYouTubeConnected = false;
    }
}

/**
 * Connect to YouTube via Late.dev
 */
function connectToYouTube() {
    window.location.href = '/video-title-tags/connect';
}

/**
 * Disconnect from YouTube
 */
async function disconnectFromYouTube() {
    if (!confirm('Are you sure you want to disconnect your YouTube account from the upload studio?')) {
        return;
    }

    try {
        const response = await fetch('/video-title-tags/disconnect', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast('YouTube account disconnected successfully', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast('Failed to disconnect: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error disconnecting:', error);
        showToast('Failed to disconnect from YouTube', 'error');
    }
}

/**
 * Update connection UI based on YouTube status
 */
function updateConnectionUI(data) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');
    const connectBtn = document.getElementById('connectBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const channelInfo = document.getElementById('channelInfo');
    const buttonSkeleton = document.getElementById('buttonSkeleton');
    const connectionButtons = document.getElementById('connectionButtons');

    // Remove loading state
    if (statusDot) statusDot.classList.remove('loading');

    // Hide skeleton, show actual buttons
    if (buttonSkeleton) buttonSkeleton.style.display = 'none';
    if (connectionButtons) connectionButtons.style.display = 'block';

    if (data.connected && data.user_info) {
        // Connected state
        if (statusDot) statusDot.classList.remove('disconnected');
        if (statusText) statusText.textContent = 'Connected to YouTube';
        if (connectBtn) connectBtn.style.display = 'none';
        if (disconnectBtn) disconnectBtn.style.display = 'inline-flex';

        // Show user info
        if (channelInfo) {
            channelInfo.style.display = 'flex';

            const thumbnailEl = document.getElementById('channelThumbnail');
            const nameEl = document.getElementById('channelName');
            const idEl = document.getElementById('channelId');

            if (thumbnailEl && data.user_info.avatar_url) {
                thumbnailEl.src = data.user_info.avatar_url;
                thumbnailEl.style.display = 'block';
            } else if (thumbnailEl) {
                thumbnailEl.style.display = 'none';
            }

            if (nameEl) {
                nameEl.textContent = data.user_info.display_name || 'YouTube User';
            }

            // Show username if available
            if (idEl && data.user_info.username) {
                idEl.textContent = '@' + data.user_info.username;
                idEl.style.display = 'block';
            } else if (idEl) {
                idEl.style.display = 'none';
            }
        }
    } else {
        // Disconnected state
        if (statusDot) statusDot.classList.add('disconnected');
        if (statusText) statusText.textContent = 'Not Connected';
        if (connectBtn) connectBtn.style.display = 'inline-flex';
        if (disconnectBtn) disconnectBtn.style.display = 'none';
        if (channelInfo) channelInfo.style.display = 'none';
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

    // Detect if this is a short video (≤60s OR <100MB)
    selectedVideoFile = file;
    const isShort = await detectIfShort(file);

    // Start uploading to server immediately
    await uploadVideoToServer(file, isShort);
}

/**
 * Upload short video to Firebase Storage for future multi-platform posting
 */
async function uploadShortToFirebase(file) {
    try {
        const formData = new FormData();
        formData.append('video', file);

        // Add keywords and description for content library
        const keywordInput = document.getElementById('keywordInput');
        const videoInput = document.getElementById('videoInput');
        if (keywordInput && keywordInput.value.trim()) {
            formData.append('keywords', keywordInput.value.trim());
        }
        if (videoInput && videoInput.value.trim()) {
            formData.append('content_description', videoInput.value.trim());
        }

        const response = await fetch('/api/upload-short-to-firebase', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            console.log('Short video uploaded to Firebase:', data.firebase_url);
            // Store the Firebase URL for later use
            window.shortVideoFirebaseUrl = data.firebase_url;
        } else {
            console.error('Failed to upload short to Firebase:', data.error);
        }
    } catch (error) {
        console.error('Error uploading short to Firebase:', error);
        // Don't block the main flow - this is just for future use
    }
}

/**
 * Detect if video is a short (≤60s duration OR <100MB file size)
 */
async function detectIfShort(file) {
    // Check file size first (quick check)
    const maxSizeBytes = 100 * 1024 * 1024; // 100MB
    if (file.size < maxSizeBytes) {
        return true;
    }

    // Check duration (requires loading video metadata)
    return new Promise((resolve) => {
        const video = document.createElement('video');
        video.preload = 'metadata';

        video.onloadedmetadata = function() {
            window.URL.revokeObjectURL(video.src);
            const duration = video.duration;
            console.log(`Video duration: ${duration}s`);
            resolve(duration <= 60);
        };

        video.onerror = function() {
            // If we can't read metadata, fall back to file size
            window.URL.revokeObjectURL(video.src);
            resolve(false);
        };

        video.src = URL.createObjectURL(file);
    });
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
 * If it's a short, also upload to Firebase Storage for future multi-platform posting
 */
async function uploadVideoToServer(file, isShort = false) {
    const progressContainer = document.getElementById('videoUploadProgressContainer');

    try {
        // Keep file reference for direct YouTube upload
        uploadedVideoPath = null;
        selectedVideoFile = file;

        // If this is a short video, also upload to Firebase Storage
        if (isShort) {
            console.log('Uploading short video to Firebase Storage for future multi-platform posting...');
            await uploadShortToFirebase(file);
        }

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
                            Publish Date & Time <span class="utc-indicator" id="timezoneIndicator">(Local Time)</span>
                        </label>
                        <div class="schedule-datetime-grid">
                            <select id="scheduleDateSelect" class="privacy-select">
                                <option value="">Select date</option>
                            </select>
                            <select id="scheduleTimeSelect" class="privacy-select">
                                <option value="">Select time</option>
                            </select>
                        </div>
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
 * Populate schedule date dropdown (365 days)
 */
function populateScheduleDateDropdown() {
    const dateSelect = document.getElementById('scheduleDateSelect');
    if (!dateSelect) return;

    // Clear existing options except first
    dateSelect.innerHTML = '<option value="">Select date</option>';

    const today = new Date();
    for (let i = 0; i < 365; i++) {
        const date = new Date(today);
        date.setDate(today.getDate() + i);

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const value = `${year}-${month}-${day}`;

        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
        const monthName = date.toLocaleDateString('en-US', { month: 'short' });
        const label = `${dayName}, ${monthName} ${day}, ${year}`;

        const option = document.createElement('option');
        option.value = value;

        // Add "Today" or "Tomorrow" prefix
        if (i === 0) {
            option.textContent = `Today - ${label}`;
        } else if (i === 1) {
            option.textContent = `Tomorrow - ${label}`;
        } else {
            option.textContent = label;
        }

        dateSelect.appendChild(option);
    }

    // Set default to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;
    dateSelect.value = tomorrowStr;
}

/**
 * Populate schedule time dropdown (15-minute intervals)
 */
function populateScheduleTimeDropdown() {
    const timeSelect = document.getElementById('scheduleTimeSelect');
    if (!timeSelect) return;

    // Clear existing options except first
    timeSelect.innerHTML = '<option value="">Select time</option>';

    for (let hour = 0; hour < 24; hour++) {
        for (let minute = 0; minute < 60; minute += 15) {
            const hourStr = String(hour).padStart(2, '0');
            const minuteStr = String(minute).padStart(2, '0');
            const value = `${hourStr}:${minuteStr}`;

            const hour12 = hour % 12 || 12;
            const ampm = hour < 12 ? 'AM' : 'PM';
            const label = `${hour12}:${minuteStr} ${ampm}`;

            const option = document.createElement('option');
            option.value = value;
            option.textContent = label;
            timeSelect.appendChild(option);
        }
    }

    // Set default to 12:00 PM
    timeSelect.value = '12:00';
}

/**
 * Handle status change (show/hide schedule datetime)
 */
function handleStatusChange() {
    const privacySelect = document.getElementById('privacySelect');
    const scheduleDateTime = document.getElementById('scheduleDateTime');
    const scheduleDateSelect = document.getElementById('scheduleDateSelect');
    const scheduleTimeSelect = document.getElementById('scheduleTimeSelect');

    if (privacySelect && scheduleDateTime) {
        if (privacySelect.value === 'scheduled') {
            scheduleDateTime.style.display = 'block';

            // Update timezone indicator
            const timezoneIndicator = document.getElementById('timezoneIndicator');
            if (timezoneIndicator) {
                const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                const tzAbbr = new Date().toLocaleTimeString('en-us', {timeZoneName:'short'}).split(' ')[2];
                timezoneIndicator.textContent = `(${tzAbbr || userTimezone})`;
            }

            // Populate dropdowns if not already done
            if (scheduleDateSelect && scheduleDateSelect.options.length === 1) {
                populateScheduleDateDropdown();
            }
            if (scheduleTimeSelect && scheduleTimeSelect.options.length === 1) {
                populateScheduleTimeDropdown();
            }

            // Set default to tomorrow at 12:00 if not already set
            if (scheduleDateSelect && !scheduleDateSelect.value) {
                const tomorrow = new Date();
                tomorrow.setDate(tomorrow.getDate() + 1);
                const year = tomorrow.getFullYear();
                const month = String(tomorrow.getMonth() + 1).padStart(2, '0');
                const day = String(tomorrow.getDate()).padStart(2, '0');
                scheduleDateSelect.value = `${year}-${month}-${day}`;
            }
            if (scheduleTimeSelect && !scheduleTimeSelect.value) {
                scheduleTimeSelect.value = '12:00';
            }
        } else {
            scheduleDateTime.style.display = 'none';
        }
    }
}

/**
 * Upload video to YouTube via Late.dev
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

    // Get privacy status
    const privacySelect = document.getElementById('privacySelect');
    const privacyStatus = privacySelect ? privacySelect.value : 'private';

    // Get scheduled date/time if status is scheduled
    let scheduledTime = null;
    if (privacyStatus === 'scheduled') {
        const scheduleDateSelect = document.getElementById('scheduleDateSelect');
        const scheduleTimeSelect = document.getElementById('scheduleTimeSelect');

        if (!scheduleDateSelect || !scheduleDateSelect.value || !scheduleTimeSelect || !scheduleTimeSelect.value) {
            showToast('Please select a publish date and time', 'error');
            return;
        }

        // Combine date and time in user's local timezone
        const dateTime = `${scheduleDateSelect.value}T${scheduleTimeSelect.value}:00`;
        const localDateTime = new Date(dateTime);

        // Validate that schedule time is in the future
        if (localDateTime <= new Date()) {
            showToast('Schedule time must be in the future', 'error');
            return;
        }

        // Convert to ISO string
        scheduledTime = localDateTime.toISOString();
    }

    const uploadBtn = document.getElementById('uploadBtn');
    const originalContent = uploadBtn.innerHTML;
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Uploading...';

    try {
        // Get keywords and description
        const keywordInput = document.getElementById('keywordInput');
        const targetKeyword = keywordInput && keywordInput.value.trim() ? keywordInput.value.trim() : '';
        const videoInput = document.getElementById('videoInput');
        const contentDescription = videoInput ? videoInput.value.trim() : '';

        // Step 1: Upload video to Firebase if not already uploaded
        let firebaseUrl = window.shortVideoFirebaseUrl;
        if (!firebaseUrl) {
            const formData = new FormData();
            formData.append('video', selectedVideoFile);
            formData.append('keywords', targetKeyword);
            formData.append('content_description', contentDescription);

            uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Uploading to storage...';

            const uploadResponse = await fetch('/api/upload-video-to-firebase', {
                method: 'POST',
                body: formData
            });

            const uploadData = await uploadResponse.json();

            if (!uploadData.success) {
                throw new Error(uploadData.error || 'Failed to upload video');
            }

            firebaseUrl = uploadData.firebase_url;
            window.shortVideoFirebaseUrl = firebaseUrl;
            console.log('Video uploaded to Firebase:', firebaseUrl);
        }

        // Step 2: Post to YouTube via Late.dev
        uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Posting to YouTube...';

        const postPayload = {
            firebase_url: firebaseUrl,
            title: title,
            description: description,
            tags: tags,
            visibility: privacyStatus === 'scheduled' ? 'private' : privacyStatus,
            scheduled_time: scheduledTime,
            thumbnail_url: null, // TODO: Upload thumbnail to Firebase if needed
            keywords: targetKeyword,
            content_description: contentDescription
        };

        const postResponse = await fetch('/api/upload-to-youtube', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(postPayload)
        });

        const postData = await postResponse.json();

        if (!postData.success) {
            // Check if it's a quota error
            if (postData.error && postData.error.toLowerCase().includes('quota exceeded')) {
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = originalContent;
                showQuotaExceededModal();
                return;
            }
            throw new Error(postData.error || 'Failed to upload to YouTube');
        }

        // Show success message
        let message = 'Video uploaded to YouTube successfully!';
        if (scheduledTime) {
            message = 'Video scheduled on YouTube successfully!';
        }
        showToast(message, 'success');

        // Reset state
        selectedVideoFile = null;
        selectedThumbnailFile = null;
        selectedTitle = null;
        uploadedVideoPath = null;
        uploadedThumbnailPath = null;
        window.shortVideoFirebaseUrl = null;

        // Reset button
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalContent;

        // Optionally reload to clear form
        setTimeout(() => location.reload(), 1500);

    } catch (error) {
        console.error('Error uploading video:', error);
        showToast('Failed to upload video: ' + error.message, 'error');

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
                <h3>YouTube Upload Limit Reached</h3>
            </div>
            <div class="quota-modal-content">
                <p class="quota-message">Daily YouTube upload limit reached.</p>
                <p class="quota-submessage">Please try again later or schedule your video for tomorrow.</p>
            </div>
            <div class="quota-modal-actions">
                <button class="quota-modal-btn" onclick="this.closest('.quota-exceeded-modal-overlay').remove()">Got It</button>
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
            <h3 id="uploadProgressTitle">Uploading to YouTube</h3>
            <p id="uploadProgressMessage">Preparing upload...</p>

            <div class="progress-section">
                <div class="progress-header">
                    <span class="progress-label">Progress</span>
                    <span id="uploadProgressPercent" class="progress-percent">0%</span>
                </div>
                <div class="progress-bar-container">
                    <div id="uploadProgressFill" class="progress-bar-fill"></div>
                </div>
            </div>

            <div class="upload-warning">
                <div class="upload-warning-content">
                    <i class="ph-fill ph-warning-circle warning-icon"></i>
                    <div class="upload-warning-text">
                        <p class="warning-title">Don't close this page</p>
                        <p class="warning-description">Keep this tab open while uploading</p>
                        <button class="open-tab-btn" onclick="window.open('/', '_blank')">
                            <i class="ph-fill ph-arrow-square-out"></i>
                            <span>Open Creatrics in New Tab</span>
                        </button>
                    </div>
                </div>
            </div>

            <p class="upload-footer-text">Large videos may take several minutes to upload</p>
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
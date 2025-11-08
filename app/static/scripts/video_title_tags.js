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
let youtubeRepostModal = null;  // Repost modal instance
let uploadMode = 'upload';  // 'upload' or 'repost'
let repostContent = null;  // Selected content from repost modal
let repostScheduledDate = null;  // Scheduled date from repost content

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateCharCount();
    updateRefDescCharCount();
    updateChannelKeywordsCharCount();
    loadChannelKeywords();
    loadReferenceDescription();
    checkYouTubeConnection();
    initializeRepostModal();

    // Initialize status to trigger default scheduled setup (wait for DOM to be fully ready)
    setTimeout(() => {
        handleStatusChange();
    }, 100);

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
 * Initialize the repost modal
 */
function initializeRepostModal() {
    if (typeof RepostModal === 'undefined') {
        console.error('RepostModal not loaded');
        return;
    }

    youtubeRepostModal = new RepostModal({
        mediaTypeFilter: 'video',  // YouTube only supports videos
        platform: 'youtube',
        onSelect: function(content) {
            handleContentSelection(content);
        },
        onClose: function() {
            // Switch back to upload mode ONLY if no content was selected
            if (uploadMode === 'repost' && !repostContent) {
                switchMode('upload');
            }
        }
    });
}

/**
 * Handle mode switching between upload and repost
 */
function switchMode(mode) {
    uploadMode = mode;

    // Update toggle button states
    const toggleBtns = document.querySelectorAll('.toggle-btn');
    toggleBtns.forEach(btn => {
        if (btn.dataset.mode === mode) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    if (mode === 'repost') {
        // Open repost modal
        if (youtubeRepostModal) {
            youtubeRepostModal.open();
        }
    } else {
        // Reset to upload mode
        repostContent = null;
        repostScheduledDate = null;
    }
}

/**
 * Handle content selection from repost modal
 */
function handleContentSelection(content) {
    repostContent = content;

    // Pre-fill keywords (Target Keyword field)
    const keywordInput = document.getElementById('keywordInput');
    if (keywordInput && content.keywords) {
        keywordInput.value = content.keywords;
    }

    // Pre-fill video description
    const videoInput = document.getElementById('videoInput');
    if (videoInput && content.content_description) {
        videoInput.value = content.content_description;
        updateCharCount();
    }

    // Auto-select all generation options (Titles, Description, Tags)
    const titlesCard = document.getElementById('titlesCard');
    const descriptionCard = document.getElementById('descriptionCard');
    const tagsCard = document.getElementById('tagsCard');

    // Activate all cards if they're not already active
    if (titlesCard && !titlesCard.classList.contains('active')) {
        titlesCard.classList.add('active');
    }
    if (descriptionCard && !descriptionCard.classList.contains('active')) {
        descriptionCard.classList.add('active');
        // Show reference description section
        const referenceSection = document.getElementById('referenceDescriptionSection');
        if (referenceSection) referenceSection.style.display = 'block';
    }
    if (tagsCard && !tagsCard.classList.contains('active')) {
        tagsCard.classList.add('active');
        // Show channel keywords section
        const channelKeywordsSection = document.getElementById('channelKeywordsSection');
        if (channelKeywordsSection) channelKeywordsSection.style.display = 'block';
    }

    // Check if this content has any platform's scheduled post date
    const platforms = content.platforms_posted || {};
    console.log('Content platforms_posted:', platforms);

    // Check all platforms for a scheduled date (prioritize YouTube, then check others)
    repostScheduledDate = null;  // Reset
    const platformOrder = ['youtube', 'tiktok', 'instagram', 'x'];

    for (const platform of platformOrder) {
        const platformData = platforms[platform];
        console.log(`Checking ${platform}:`, platformData);
        if (platformData && platformData.scheduled_for) {
            const date = new Date(platformData.scheduled_for);
            const now = new Date();
            console.log(`${platform} scheduled_for: ${platformData.scheduled_for}, parsed date: ${date}, now: ${now}, is future: ${date > now}`);
            // Check if the scheduled time is in the future
            if (date > new Date()) {
                repostScheduledDate = date;
                console.log('Found scheduled date from', platform, ':', repostScheduledDate);
                break;
            }
        }
    }

    // Auto-select video type based on duration (< 3 minutes = Short)
    if (content.duration) {
        if (content.duration < 180) {
            setVideoType('short');
        } else {
            setVideoType('long');
        }
        console.log(`Auto-selected video type based on ${content.duration}s duration`);
    }

    // Display the video in the upload area
    displayRepostVideo(content);

    console.log('Content selected for reposting:', content);
    console.log('Scheduled date will be applied after content generation');
}

/**
 * Display repost video in the upload area
 */
function displayRepostVideo(content) {
    const uploadContent = document.getElementById('uploadContent');
    const uploadProgress = document.getElementById('uploadProgress');
    const fileName = document.getElementById('uploadFileName');
    const fileSize = document.getElementById('uploadFileSize');

    if (uploadContent) uploadContent.style.display = 'none';
    if (uploadProgress) uploadProgress.style.display = 'flex';

    // Extract filename from URL
    const urlParts = content.media_url.split('/');
    const fullFilename = urlParts[urlParts.length - 1];

    if (fileName) fileName.textContent = decodeURIComponent(fullFilename);
    if (fileSize) fileSize.textContent = 'From library';
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

    // Detect if this is a short video (< 3 minutes)
    selectedVideoFile = file;
    const isShort = await detectIfShort(file);
    console.log(`Video detected as: ${isShort ? 'Short' : 'Long Form'}`);

    // Auto-select video type based on duration
    if (isShort) {
        console.log('Auto-selecting Short video type');
        setVideoType('short');
    } else {
        console.log('Auto-selecting Long Form video type');
        setVideoType('long');
    }

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
 * Detect if video is a short (< 3 minutes duration)
 */
async function detectIfShort(file) {
    // Check duration (requires loading video metadata)
    return new Promise((resolve) => {
        const video = document.createElement('video');
        video.preload = 'metadata';

        video.onloadedmetadata = function() {
            window.URL.revokeObjectURL(video.src);
            const duration = video.duration;
            const minutes = Math.floor(duration / 60);
            const seconds = Math.floor(duration % 60);
            console.log(`Video duration: ${minutes}m ${seconds}s`);
            resolve(duration < 180); // Less than 3 minutes = Short
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

        // Note: We no longer pre-upload short videos to Firebase
        // The video will be uploaded when the user clicks "Upload to YouTube"
        // This avoids redundant uploads and timeout issues

        // Hide progress bar - we don't need it for file selection
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }

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
        <div class="loading-container premium-loading">
            <div class="premium-spinner">
                <div class="spinner-ring"></div>
                <div class="spinner-ring"></div>
                <div class="spinner-ring"></div>
                <div class="spinner-core">
                    <i class="ph ph-sparkle"></i>
                </div>
            </div>
            <div class="loading-text">Creating Your Content</div>
            <div class="loading-subtext">Generating ${loadingText}<span class="loading-dots"><span>.</span><span>.</span><span>.</span></span></div>
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
        if ((selectedVideoFile || repostContent) && hasYouTubeConnected) {
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
    if ((selectedVideoFile || repostContent) && hasYouTubeConnected) {
        html += renderUploadSection(!showTabs);
    }

    document.getElementById('resultsContainer').innerHTML = html;

    // Initialize status after rendering HTML (to show schedule card and populate defaults)
    if ((selectedVideoFile || repostContent) && hasYouTubeConnected) {
        handleStatusChange();
    }

    // Apply repost scheduled date if available (after HTML is rendered)
    if (repostScheduledDate) {
        setTimeout(() => {
            applyRepostScheduledDate();
        }, 300);
    }
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
                        <div class="title-item ${selectedTitle === index ? 'selected' : ''}" id="title-item-${index}" ${(selectedVideoFile || repostContent) && hasYouTubeConnected ? `onclick="selectTitle(${index})"` : ''}>
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

                    <!-- Content Calendar -->
                    <div class="upload-option-card" style="grid-column: 1 / -1;">
                        <label class="upload-option-label">
                            <i class="ph ph-calendar-check"></i>
                            Content Calendar
                        </label>
                        <select class="privacy-select" id="contentCalendarSelect" onchange="handleContentCalendarChange()">
                            <option value="create_new" selected>Create New Calendar Item</option>
                            <option value="link_existing">Link to Existing Calendar Item</option>
                        </select>
                    </div>

                    <!-- Privacy Status -->
                    <div class="upload-option-card" id="statusCard" style="grid-column: 1;">
                        <label class="upload-option-label">
                            <i class="ph ph-lock-key"></i>
                            Status
                        </label>
                        <select class="privacy-select" id="privacySelect" onchange="handleStatusChange()">
                            <option value="private">Private</option>
                            <option value="unlisted">Unlisted</option>
                            <option value="public">Public</option>
                            <option value="scheduled" selected>Schedule</option>
                        </select>
                    </div>

                    <!-- Schedule Date/Time (appears when scheduled is selected) -->
                    <div class="upload-option-card" id="scheduleDateTime" style="grid-column: 2;">
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

                <!-- Upload Progress Bar -->
                <div id="uploadProgressBar" class="upload-progress-bar" style="display: none;">
                    <div class="upload-progress-info">
                        <span class="upload-progress-status">Uploading...</span>
                        <span class="upload-progress-percent">0%</span>
                    </div>
                    <div class="upload-progress-track">
                        <div class="upload-progress-fill" id="uploadProgressFill"></div>
                    </div>
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
 * Apply scheduled date from repost content
 */
function applyRepostScheduledDate() {
    if (!repostScheduledDate) return;

    console.log('Applying repost scheduled date:', repostScheduledDate);

    // Switch to scheduled mode
    const privacySelect = document.getElementById('privacySelect');
    if (privacySelect) {
        privacySelect.value = 'scheduled';
        // Trigger change event to show schedule inputs and populate dropdowns
        handleStatusChange();
    }

    // Need to wait longer for handleStatusChange to populate dropdowns
    setTimeout(() => {
        const dateSelect = document.getElementById('scheduleDateSelect');
        const timeSelect = document.getElementById('scheduleTimeSelect');

        if (dateSelect && timeSelect) {
            // Format date as YYYY-MM-DD
            const year = repostScheduledDate.getFullYear();
            const month = String(repostScheduledDate.getMonth() + 1).padStart(2, '0');
            const day = String(repostScheduledDate.getDate()).padStart(2, '0');
            const dateValue = `${year}-${month}-${day}`;

            // Format time as HH:MM
            const hours = String(repostScheduledDate.getHours()).padStart(2, '0');
            const minutes = String(repostScheduledDate.getMinutes()).padStart(2, '0');
            const timeValue = `${hours}:${minutes}`;

            // Set the select values (force set even if they have defaults)
            dateSelect.value = dateValue;
            timeSelect.value = timeValue;

            console.log('Set schedule to:', dateValue, timeValue);

            // Verify the values were set correctly
            if (dateSelect.value !== dateValue || timeSelect.value !== timeValue) {
                console.warn('Failed to set schedule values correctly');
                console.warn('Date - Expected:', dateValue, 'Actual:', dateSelect.value);
                console.warn('Time - Expected:', timeValue, 'Actual:', timeSelect.value);
            }
        } else {
            console.warn('Schedule dropdowns not found');
        }
    }, 200);
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
 * Upload FormData with progress tracking via XMLHttpRequest
 */
async function uploadWithProgress(url, formData, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        // Track upload progress
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                if (onProgress) {
                    onProgress(percentComplete);
                }
            }
        });

        // Handle completion
        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                console.log('Upload completed');
                resolve(xhr);
            } else {
                console.error('Upload failed:', xhr.status, xhr.responseText);
                reject(new Error(`Upload failed with status ${xhr.status}`));
            }
        });

        // Handle errors
        xhr.addEventListener('error', () => {
            console.error('Upload error');
            reject(new Error('Network error during upload'));
        });

        xhr.addEventListener('abort', () => {
            console.error('Upload aborted');
            reject(new Error('Upload aborted'));
        });

        // Open POST request to URL
        xhr.open('POST', url, true);

        // Don't set Content-Type - browser will set it with boundary for multipart/form-data

        // Send the FormData
        xhr.send(formData);
    });
}

/**
 * Upload video to YouTube via Late.dev
 */
async function uploadToYouTube() {
    // Check if we have either a selected file (upload mode) or repost content (repost mode)
    if (!selectedVideoFile && !(uploadMode === 'repost' && repostContent)) {
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

    // Check if calendar item is linked - if so, use its publish date
    const linkedCalendarItem = CalendarLinkModal.getLinkedItem();
    let scheduledTime = null;
    let privacyStatus = 'private';

    if (linkedCalendarItem && linkedCalendarItem.publish_date) {
        // Use the linked calendar item's publish date
        scheduledTime = linkedCalendarItem.publish_date;
        privacyStatus = 'scheduled';
        console.log('Using linked calendar item publish date:', scheduledTime);
    } else {
        // Get privacy status from form
        const privacySelect = document.getElementById('privacySelect');
        privacyStatus = privacySelect ? privacySelect.value : 'private';

        // Get scheduled date/time if status is scheduled
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
    }

    const uploadBtn = document.getElementById('uploadBtn');
    const originalContent = uploadBtn.innerHTML;
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Uploading...';

    // Show progress bar
    const progressBar = document.getElementById('uploadProgressBar');
    const progressFill = document.getElementById('uploadProgressFill');
    const progressStatus = document.querySelector('.upload-progress-status');
    const progressPercent = document.querySelector('.upload-progress-percent');

    if (progressBar) {
        progressBar.style.display = 'block';
        progressFill.style.width = '0%';
        progressStatus.textContent = 'Preparing...';
        progressPercent.textContent = '0%';
    }

    try {
        // Get keywords and description
        const keywordInput = document.getElementById('keywordInput');
        const targetKeyword = keywordInput && keywordInput.value.trim() ? keywordInput.value.trim() : '';
        const videoInput = document.getElementById('videoInput');
        const contentDescription = videoInput ? videoInput.value.trim() : '';

        // Step 1: Get media URL (either from uploaded file or repost content)
        let firebaseUrl;
        let contentId;

        if (uploadMode === 'repost' && repostContent) {
            // Use existing media URL from content library
            firebaseUrl = repostContent.media_url;
            contentId = repostContent.id;
            console.log('Reposting existing content:', firebaseUrl);

            // Update progress for repost
            if (progressBar) {
                progressFill.style.width = '30%';
                progressStatus.textContent = 'Preparing to post...';
                progressPercent.textContent = '30%';
            }
        } else {
            // Upload video to Firebase if not already uploaded
            firebaseUrl = window.shortVideoFirebaseUrl;
            if (!firebaseUrl) {
                // Update progress - initializing upload
                if (progressBar) {
                    progressFill.style.width = '5%';
                    progressStatus.textContent = 'Preparing upload...';
                    progressPercent.textContent = '5%';
                }

                uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Preparing upload...';

                // Step 1: Initialize upload and create calendar item
                const initPayload = {
                    title: title,
                    description: description,
                    tags: tags,
                    visibility: privacyStatus === 'scheduled' ? 'private' : privacyStatus,
                    scheduled_time: scheduledTime,
                    keywords: targetKeyword,
                    content_description: contentDescription,
                    filename: selectedVideoFile.name,
                    content_type: selectedVideoFile.type || 'video/mp4'
                };

                // Add linked calendar event ID if user linked to an existing calendar item
                const linkedItem = CalendarLinkModal.getLinkedItem();
                if (linkedItem) {
                    initPayload.calendar_event_id = linkedItem.id;
                }

                const initResponse = await fetch('/api/init-youtube-upload', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(initPayload)
                });

                const initData = await initResponse.json();

                if (!initData.success) {
                    throw new Error(initData.error || 'Failed to initialize upload');
                }

                console.log('Upload initialized. Calendar item created.');

                // Step 2: Upload video to Firebase via server (streaming, no size limit)
                uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Uploading video...';

                if (progressBar) {
                    progressFill.style.width = '10%';
                    progressStatus.textContent = 'Uploading video...';
                    progressPercent.textContent = '10%';
                }

                // Upload with progress tracking via FormData
                const uploadFormData = new FormData();
                uploadFormData.append('video', selectedVideoFile);
                uploadFormData.append('content_id', initData.content_id);
                uploadFormData.append('file_path', initData.file_path);

                const uploadResponse = await uploadWithProgress(
                    '/api/upload-video-chunk',
                    uploadFormData,
                    (percent) => {
                        if (progressBar) {
                            // Map upload progress to 10-50% of total progress
                            const totalPercent = 10 + (percent * 0.4);
                            progressFill.style.width = `${totalPercent}%`;
                            progressStatus.textContent = `Uploading video...`;
                            progressPercent.textContent = `${Math.round(totalPercent)}%`;
                        }
                    }
                );

                // Parse JSON from XHR response
                const uploadResult = JSON.parse(uploadResponse.responseText);

                if (!uploadResult.success) {
                    throw new Error(uploadResult.error || 'Failed to upload video');
                }

                firebaseUrl = uploadResult.firebase_url;
                contentId = initData.content_id;
                const calendarEventId = initData.calendar_event_id;
                window.shortVideoFirebaseUrl = firebaseUrl;
                console.log('Video uploaded to Firebase:', firebaseUrl);

                // Update progress after video upload
                if (progressBar) {
                    progressFill.style.width = '50%';
                    progressStatus.textContent = 'Video uploaded';
                    progressPercent.textContent = '50%';
                }

                // Step 3: Complete upload - post to YouTube
                uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Posting to YouTube...';

                if (progressBar) {
                    progressFill.style.width = '60%';
                    progressStatus.textContent = 'Posting to YouTube...';
                    progressPercent.textContent = '60%';
                }

                const completePayload = {
                    firebase_url: firebaseUrl,
                    content_id: contentId,
                    calendar_event_id: calendarEventId,
                    title: title,
                    description: description,
                    tags: tags,
                    visibility: privacyStatus === 'scheduled' ? 'private' : privacyStatus,
                    scheduled_time: scheduledTime,
                    thumbnail_url: null // TODO: Upload thumbnail to Firebase if needed
                };

                const completeResponse = await fetch('/api/complete-youtube-upload', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(completePayload)
                });

                const completeData = await completeResponse.json();

                if (!completeData.success) {
                    throw new Error(completeData.error || 'Failed to post to YouTube');
                }

                console.log('Posted to YouTube:', completeData.post_id);

                // Update final progress
                if (progressBar) {
                    progressFill.style.width = '100%';
                    progressStatus.textContent = scheduledTime ? 'Scheduled!' : 'Uploaded!';
                    progressPercent.textContent = '100%';
                }

                // Show success state on button
                uploadBtn.innerHTML = '<i class="ph ph-check-circle"></i> ' + (scheduledTime ? 'Scheduled!' : 'Uploaded!');

                // Show success message
                let message = 'Video uploaded to YouTube successfully!';
                if (scheduledTime) {
                    message = 'Video scheduled on YouTube successfully!';
                }
                const finalLinkedItem = CalendarLinkModal.getLinkedItem();
                if (finalLinkedItem) {
                    message += ' Calendar item updated.';
                }
                showToast(message, 'success');

                // Wait 2 seconds to show success state, then refresh page
                setTimeout(() => {
                    location.reload();
                }, 2000);

                return; // Exit early since we handled the full flow
            }
        }

        // Step 2: Post to YouTube via Late.dev
        if (progressBar) {
            progressFill.style.width = '60%';
            progressStatus.textContent = 'Posting to YouTube...';
            progressPercent.textContent = '60%';
        }

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

        // Add content_id if we have it (from repost or upload)
        if (contentId) {
            postPayload.content_id = contentId;
        }

        // Add linked calendar event ID if user linked to an existing calendar item
        const linkedItem = CalendarLinkModal.getLinkedItem();
        if (linkedItem) {
            postPayload.calendar_event_id = linkedItem.id;
        }

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
                if (progressBar) progressBar.style.display = 'none';
                showQuotaExceededModal();
                return;
            }
            throw new Error(postData.error || 'Failed to upload to YouTube');
        }

        // Note: The backend now handles updating the linked calendar item
        // No need to update it here again

        // Complete progress
        if (progressBar) {
            progressFill.style.width = '100%';
            progressStatus.textContent = 'Complete!';
            progressPercent.textContent = '100%';
        }

        // Show success state on button
        uploadBtn.innerHTML = '<i class="ph ph-check-circle"></i> ' + (scheduledTime ? 'Scheduled!' : 'Uploaded!');

        // Show success message
        let message = 'Video uploaded to YouTube successfully!';
        if (scheduledTime) {
            message = 'Video scheduled on YouTube successfully!';
        }
        const finalLinkedItem = CalendarLinkModal.getLinkedItem();
        if (finalLinkedItem) {
            message += ' Calendar item updated.';
        }
        showToast(message, 'success');

        // Wait 2 seconds to show success state, then refresh page
        setTimeout(() => {
            location.reload();
        }, 2000);

    } catch (error) {
        console.error('Error uploading video:', error);
        showToast('Failed to upload video: ' + error.message, 'error');

        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalContent;

        // Hide progress bar on error
        if (progressBar) {
            progressBar.style.display = 'none';
        }
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

// Content Calendar Integration
// Initialize the calendar link modal for YouTube
document.addEventListener('DOMContentLoaded', function() {
    CalendarLinkModal.init('YouTube', function(item) {
        // Update the select dropdown to show it's linked
        const select = document.getElementById('contentCalendarSelect');
        if (select) {
            // Add custom option to show linked item
            const existingOption = select.querySelector('option[value="linked"]');
            if (existingOption) {
                existingOption.remove();
            }

            const option = document.createElement('option');
            option.value = 'linked';
            option.selected = true;
            option.textContent = `Linked: ${item.title || 'Untitled'}`;
            select.appendChild(option);
        }

        // If the linked item has a publish_date, auto-populate the schedule fields
        if (item.publish_date) {
            // Switch to scheduled mode
            const privacySelect = document.getElementById('privacySelect');
            if (privacySelect) {
                privacySelect.value = 'scheduled';
                // Trigger change to show schedule date/time fields
                handleStatusChange();
            }

            // Wait for dropdowns to be populated, then set the values
            setTimeout(() => {
                const scheduleDateSelect = document.getElementById('scheduleDateSelect');
                const scheduleTimeSelect = document.getElementById('scheduleTimeSelect');

                if (scheduleDateSelect && scheduleTimeSelect) {
                    const date = new Date(item.publish_date);

                    // Format date as YYYY-MM-DD
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    const dateValue = `${year}-${month}-${day}`;

                    // Format time as HH:MM
                    const hours = String(date.getHours()).padStart(2, '0');
                    const minutes = String(date.getMinutes()).padStart(2, '0');
                    const timeValue = `${hours}:${minutes}`;

                    scheduleDateSelect.value = dateValue;
                    scheduleTimeSelect.value = timeValue;

                    console.log('Auto-populated schedule from linked calendar item:', dateValue, timeValue);
                }
            }, 200);
        }
    });
});

function handleContentCalendarChange() {
    const select = document.getElementById("contentCalendarSelect");
    const value = select.value;

    if (value === "link_existing") {
        CalendarLinkModal.open();
    } else if (value === "create_new") {
        // Clear any previously linked item
        CalendarLinkModal.clearLinkedItem();
    }
}

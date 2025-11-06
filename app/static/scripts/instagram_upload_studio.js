/**
 * Instagram Upload Studio JavaScript
 * Handles OAuth connection, title generation, and video upload
 */

let selectedFile = null;
let isConnected = false;
let currentCaptions = [];
let isGeneratingCaptions = false;
let isCheckingConnection = true;
let selectedCaptionIndex = null;
let hasPremium = window.hasPremium || false;  // Premium subscription status from backend

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Instagram Upload Studio initialized');

    // Set initial loading state
    setLoadingState();

    // Check connection status
    checkConnectionStatus();

    // Setup event listeners
    setupEventListeners();

    // Handle URL parameters (success/error messages)
    handleUrlParams();
});

/**
 * Set loading state while checking connection
 */
function setLoadingState() {
    // Loading state is already set in HTML
    // Just ensure elements are in loading state
    const buttonSkeleton = document.getElementById('buttonSkeleton');
    const connectionButtons = document.getElementById('connectionButtons');

    if (buttonSkeleton) buttonSkeleton.style.display = 'block';
    if (connectionButtons) connectionButtons.style.display = 'none';
}

/**
 * Check if user is connected to Instagram
 */
async function checkConnectionStatus() {
    try {
        const response = await fetch('/instagram-upload-studio/api/status');
        const data = await response.json();

        if (data.success) {
            isConnected = data.connected;
            updateConnectionUI(data);
        }
    } catch (error) {
        console.error('Error checking connection status:', error);
    }
}

/**
 * Update UI based on connection status
 */
function updateConnectionUI(data) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');
    const connectBtn = document.getElementById('connectBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const userInfo = document.getElementById('userInfo');
    const videoUploadSection = document.getElementById('videoUploadSectionStatic');
    const buttonSkeleton = document.getElementById('buttonSkeleton');
    const connectionButtons = document.getElementById('connectionButtons');
    const premiumNotice = document.getElementById('premiumNotice');

    // Remove loading state
    statusDot.classList.remove('loading');
    isCheckingConnection = false;

    // Hide skeleton, show actual buttons
    if (buttonSkeleton) buttonSkeleton.style.display = 'none';
    if (connectionButtons) connectionButtons.style.display = 'block';

    // Check premium status first
    if (!hasPremium && !data.connected) {
        // Show premium required notice for free users
        statusDot.classList.add('disconnected');
        statusText.textContent = 'Premium Required';
        connectBtn.style.display = 'none';  // Hide connect button
        disconnectBtn.style.display = 'none';
        userInfo.style.display = 'none';

        if (premiumNotice) premiumNotice.style.display = 'flex';
        if (videoUploadSection) videoUploadSection.style.display = 'none';

        return;  // Exit early
    }

    // Hide premium notice for premium users
    if (premiumNotice) premiumNotice.style.display = 'none';

    if (data.connected) {
        // Connected state
        statusDot.classList.remove('disconnected');
        statusText.textContent = 'Connected to Instagram';
        connectBtn.style.display = 'none';
        disconnectBtn.style.display = 'inline-flex';

        // Show video upload section
        if (videoUploadSection) videoUploadSection.style.display = 'block';

        // Show user info if available
        if (data.account_info) {
            userInfo.style.display = 'flex';
            document.getElementById('userAvatar').src = data.account_info.profile_picture || '/static/img/default-avatar.png';
            document.getElementById('userName').textContent = data.account_info.username || 'Instagram User';
            document.getElementById('userOpenId').textContent = '@' + (data.account_info.username || '');
            document.getElementById('userOpenId').style.display = 'block';
        }
    } else {
        // Disconnected state (but has premium)
        statusDot.classList.add('disconnected');
        statusText.textContent = 'Not Connected';
        connectBtn.style.display = 'inline-flex';
        disconnectBtn.style.display = 'none';
        userInfo.style.display = 'none';

        // Hide video upload section
        if (videoUploadSection) videoUploadSection.style.display = 'none';
    }
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Connect button
    const connectBtn = document.getElementById('connectBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectToInstagram);
    }

    // Disconnect button
    const disconnectBtn = document.getElementById('disconnectBtn');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectFromInstagram);
    }
}

/**
 * Connect to Instagram
 */
function connectToInstagram() {
    window.location.href = '/instagram-upload-studio/connect';
}

/**
 * Disconnect from Instagram
 */
async function disconnectFromInstagram() {
    if (!confirm('Are you sure you want to disconnect your Instagram account?')) {
        return;
    }

    try {
        const response = await fetch('/instagram-upload-studio/disconnect', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast('Instagram account disconnected successfully', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast('Failed to disconnect: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error disconnecting:', error);
        showToast('Failed to disconnect from Instagram', 'error');
    }
}

/**
 * Update character count for video concept input
 */
function updateCharCount() {
    const input = document.getElementById('videoConceptInput');
    if (input) {
        const count = input.value.length;
        document.getElementById('charCount').textContent = `${count} / 3000`;
    }
}

/**
 * Generate captions and hashtags
 */
async function generateCaptions() {
    const keywords = document.getElementById('keywordsInput').value.trim();
    const videoInput = document.getElementById('videoConceptInput').value.trim();

    // Validation
    if (!keywords) {
        showToast('Please enter at least one target keyword', 'error');
        return;
    }

    if (isGeneratingCaptions) return;

    isGeneratingCaptions = true;
    const generateBtn = document.getElementById('generateCaptionsBtn');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="ph ph-spinner"></i> Generating...';

    // Show loading state
    document.getElementById('resultsContainer').innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"><i class="ph ph-spinner"></i></div>
            <div class="loading-text">Creating Your Content</div>
            <div class="loading-subtext">Generating captions and hashtags...</div>
        </div>
    `;

    try {
        // Call API to generate captions
        const response = await fetch('/instagram-upload-studio/api/generate-captions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                keywords: keywords,
                content_description: videoInput
            })
        });

        const data = await response.json();

        if (!data.success) {
            // Check for insufficient credits
            if (data.error_type === 'insufficient_credits') {
                showInsufficientCreditsError();
                return;
            }
            throw new Error(data.error || 'Failed to generate captions');
        }

        // Display results
        displayResults(data.captions);
        showToast('Captions generated successfully!', 'success');

    } catch (error) {
        console.error('Error generating captions:', error);
        document.getElementById('resultsContainer').innerHTML = `
            <div class="empty-results">
                <i class="ph ph-warning-circle" style="color: #EF4444; opacity: 0.5; font-size: 4rem; margin-bottom: 1.5rem;"></i>
                <div class="empty-title">Generation Failed</div>
                <div class="empty-text">${error.message || 'Unable to generate content. Please try again.'}</div>
            </div>
        `;
        showToast('Failed to generate captions', 'error');
    } finally {
        isGeneratingCaptions = false;
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="ph ph-sparkle"></i> Generate Captions & Hashtags';
    }
}

/**
 * Display generated captions
 */
function displayResults(captions) {
    currentCaptions = captions;

    let html = '';

    // Add tabs
    html += '<div class="results-tabs">';
    html += `
        <button class="results-tab-btn active" onclick="switchTab('captions')">
            <i class="ph ph-sparkle"></i> Captions
        </button>
    `;
    if (isConnected) {
        html += `
            <button class="results-tab-btn" onclick="switchTab('upload')">
                <i class="ph ph-upload"></i> Upload
            </button>
        `;
    }
    html += '</div>';

    // Captions section
    html += renderCaptionsSection(captions, true);

    // Upload section (only if connected)
    if (isConnected) {
        html += renderUploadSection(false);
    }

    document.getElementById('resultsContainer').innerHTML = html;
}

/**
 * Render captions section
 */
function renderCaptionsSection(captions, visible) {
    return `
        <div class="results-section tab-content-section" id="captionsSection" style="${visible ? 'display: block;' : 'display: none;'}">
            <div class="results-header">
                <h3 class="results-title">
                    <i class="ph ph-sparkle"></i>
                    Generated Captions (${captions.length})
                </h3>
            </div>
            ${isConnected ? `
                <div style="padding: 0.75rem 1.5rem; font-size: 0.8125rem; color: var(--text-tertiary); font-style: italic; display: flex; align-items: center; gap: 0.5rem; border-bottom: 1px solid var(--border-primary);">
                    <i class="ph ph-info"></i>
                    <span>Click on a caption below to select it for your post</span>
                </div>
            ` : ''}
            <div class="title-cards-grid">
                ${captions.map((captionObj, index) => {
                    const isSelected = selectedCaptionIndex === index;
                    return `
                        <div class="title-card ${isSelected ? 'selected' : ''}" onclick="selectCaption(${index})">
                            <div class="title-card-header">
                                <div class="title-card-number">Caption ${index + 1}</div>
                                <button class="title-copy-btn" onclick="copyCaption(event, ${index})" title="Copy caption">
                                    <i class="ph ph-copy"></i>
                                </button>
                            </div>
                            <div class="title-text">${escapeHtml(captionObj.caption || '')}</div>
                            ${captionObj.hashtags ? `<div class="hashtags-text">${escapeHtml(captionObj.hashtags)}</div>` : ''}
                            ${isSelected ? '<div class="selected-badge"><i class="ph ph-check"></i> Selected</div>' : ''}
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

/**
 * Render upload section (Right panel - without video upload, just options)
 */
function renderUploadSection(visible) {
    return `
        <div class="results-section tab-content-section" id="uploadSection" style="${visible ? 'display: block;' : 'display: none;'}">
            <div class="upload-section-content">
                <form id="uploadForm" enctype="multipart/form-data">
                    <!-- Upload Options Grid -->
                    <div class="upload-options-grid">
                        <!-- Status Selection -->
                        <div class="upload-option-card">
                            <label class="upload-option-label">
                                <i class="ph ph-lock-key"></i>
                                Status
                            </label>
                            <select class="privacy-select" id="statusSelect" onchange="handleStatusChange()">
                                <option value="public" selected>Publish Now</option>
                                <option value="scheduled">Schedule</option>
                            </select>
                        </div>

                        <!-- Schedule Date/Time (appears when scheduled is selected) -->
                        <div class="upload-option-card" id="scheduleDateTime" style="display: none;">
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

                    <!-- Upload Button -->
                    <button type="submit" id="uploadBtn" class="btn-primary">
                        <i class="ph ph-instagram-logo"></i>
                        <span id="uploadBtnText">Publish to Instagram</span>
                    </button>
                </form>
            </div>
        </div>
    `;
}

/**
 * Switch between result tabs
 */
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

    // Setup upload form if switching to upload tab
    if (tabName === 'upload') {
        setupUploadForm();
    }
}

/**
 * Setup upload form event listeners
 */
function setupUploadForm() {
    const videoUploadArea = document.getElementById('videoUploadArea');
    const fileInput = document.getElementById('videoFileInput');
    const uploadForm = document.getElementById('uploadForm');

    if (fileInput) {
        // File input change
        fileInput.addEventListener('change', handleFileSelect);
    }

    if (videoUploadArea && fileInput) {
        // Drag and drop
        videoUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            videoUploadArea.style.borderColor = 'var(--primary)';
            videoUploadArea.style.background = 'rgba(59, 130, 246, 0.02)';
        });

        videoUploadArea.addEventListener('dragleave', () => {
            videoUploadArea.style.borderColor = '';
            videoUploadArea.style.background = '';
        });

        videoUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            videoUploadArea.style.borderColor = '';
            videoUploadArea.style.background = '';

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect({ target: { files } });
            }
        });
    }

    // Upload form
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    // Instagram doesn't need mode selection - just status dropdown
}

/**
 * Select a title for upload
 */
function selectCaption(index) {
    selectedCaptionIndex = index;

    // Update UI - highlight selected caption
    document.querySelectorAll('.title-card').forEach((item, i) => {
        if (i === index) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });

    showToast('Caption selected! Switch to Upload tab when ready.', 'success');
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
 * Remove selected video file
 */
function removeVideoFile(event) {
    event.stopPropagation();
    clearSelectedFile();
}

/**
 * Copy all captions
 */
async function copyAllCaptions() {
    if (currentCaptions && currentCaptions.length > 0) {
        const allCaptions = currentCaptions.map((title, index) => `${index + 1}. ${title}`).join('\n');
        try {
            await navigator.clipboard.writeText(allCaptions);
            showToast('All captions copied to clipboard!', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showToast('Failed to copy captions', 'error');
        }
    }
}

/**
 * Handle file selection
 */
function handleFileSelect(e) {
    const files = e.target.files;

    if (files.length === 0) {
        return;
    }

    const file = files[0];

    // Validate file type
    if (!file.type.startsWith('video/')) {
        showToast('Please select a video file', 'error');
        return;
    }

    // Validate file size (max 4GB)
    const maxSize = 4 * 1024 * 1024 * 1024; // 4GB
    if (file.size > maxSize) {
        showToast('Video file is too large (max 4GB)', 'error');
        return;
    }

    selectedFile = file;
    displaySelectedFile(file);
}

/**
 * Display selected file info
 */
function displaySelectedFile(file) {
    const uploadContent = document.getElementById('uploadContent');
    const uploadProgress = document.getElementById('uploadProgress');

    // Hide upload area, show selected file
    uploadContent.style.display = 'none';
    uploadProgress.style.display = 'flex';

    // Update file details
    document.getElementById('uploadFileName').textContent = file.name;
    document.getElementById('uploadFileSize').textContent = formatFileSize(file.size);
}

/**
 * Clear selected file
 */
function clearSelectedFile() {
    selectedFile = null;
    document.getElementById('videoFileInput').value = '';
    
    const uploadContent = document.getElementById('uploadContent');
    const uploadProgress = document.getElementById('uploadProgress');
    
    if (uploadContent && uploadProgress) {
        uploadContent.style.display = 'flex';
        uploadProgress.style.display = 'none';
    }
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
 * Handle mode change - show/hide privacy options
 */
function handleModeChange() {
    const mode = document.querySelector('input[name="mode"]:checked')?.value;
    const privacyCard = document.getElementById('privacyCard');

    if (privacyCard) {
        if (mode === 'inbox') {
            privacyCard.style.display = 'none';
        } else {
            privacyCard.style.display = 'block';
        }
    }
}

/**
 * Handle video upload (async with progress tracking)
 */
async function handleUpload(e) {
    e.preventDefault();

    if (!selectedFile) {
        showToast('Please select a media file', 'error');
        return;
    }

    if (selectedCaptionIndex === null) {
        showToast('Please select a caption from the Captions tab', 'error');
        return;
    }

    const captionObj = currentCaptions[selectedCaptionIndex];
    const caption = `${captionObj.caption}\n\n${captionObj.hashtags || ''}`;
    const statusSelect = document.getElementById('statusSelect');
    const scheduleDateSelect = document.getElementById('scheduleDateSelect');
    const scheduleTimeSelect = document.getElementById('scheduleTimeSelect');

    let scheduleTime = null;
    let userTimezone = 'UTC';

    if (statusSelect && statusSelect.value === 'scheduled') {
        const dateValue = scheduleDateSelect ? scheduleDateSelect.value : null;
        const timeValue = scheduleTimeSelect ? scheduleTimeSelect.value : null;

        if (!dateValue || !timeValue) {
            showToast('Please select both date and time for scheduling', 'error');
            return;
        }

        // Get user's local timezone
        userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        // Combine date and time in user's local timezone
        // Create a date object in user's timezone, then convert to ISO
        const localDateTime = new Date(`${dateValue}T${timeValue}:00`);
        scheduleTime = localDateTime.toISOString();
    }

    // Disable upload button
    const uploadBtn = document.getElementById('uploadBtn');
    const uploadBtnText = uploadBtn.querySelector('span') || uploadBtn;
    const uploadBtnIcon = uploadBtn.querySelector('i');
    const originalBtnContent = uploadBtn.innerHTML;
    
    uploadBtn.disabled = true;
    if (uploadBtnIcon) uploadBtnIcon.className = 'ph ph-spinner spinning';
    uploadBtnText.textContent = 'Uploading to Firebase...';

    try {
        // Step 1: Upload file to Firebase Storage
        const formData = new FormData();
        formData.append('media', selectedFile);

        uploadBtnText.textContent = `Uploading ${selectedFile.name}...`;

        const uploadResponse = await fetch('/instagram-upload-studio/api/upload-media', {
            method: 'POST',
            body: formData
        });

        const uploadData = await uploadResponse.json();
        if (!uploadData.success) {
            throw new Error(uploadData.error || 'Failed to upload media');
        }

        // Step 2: Post to Instagram via Late.dev
        uploadBtnText.textContent = 'Posting to Instagram...';

        const postResponse = await fetch('/instagram-upload-studio/api/upload', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                media_url: uploadData.media_url,
                caption: caption,
                schedule_time: scheduleTime,
                timezone: userTimezone  // Use user's local timezone
            })
        });

        const postData = await postResponse.json();

        if (postData.success) {
            // Show success state
            if (uploadBtnIcon) uploadBtnIcon.className = 'ph ph-check-circle';
            uploadBtnText.textContent = postData.scheduled_for ? 'Scheduled!' : 'Posted!';

            const message = postData.scheduled_for ? 'Post scheduled successfully!' : 'Posted to Instagram successfully!';
            showToast(message, 'success');

            // Wait a moment to show success state
            setTimeout(() => {
                // Reset form
                selectedFile = null;
                selectedCaptionIndex = null;
                clearSelectedFile();

                // Reset button
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = originalBtnContent;

                // Refresh to show empty state
                checkConnectionStatus();
            }, 2000);
        } else {
            throw new Error(postData.error || 'Failed to post');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Failed to upload: ' + error.message, 'error');
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalBtnContent;
    }
}


/**
 * Show upload progress notification
 */
function showUploadProgress(uploadId) {
    // Remove existing progress notification
    const existing = document.getElementById('uploadProgressNotification');
    if (existing) {
        existing.remove();
    }

    // Create progress notification
    const notification = document.createElement('div');
    notification.id = 'uploadProgressNotification';
    notification.className = 'upload-progress-notification';
    notification.innerHTML = `
        <div class="upload-progress-content">
            <div class="upload-progress-header">
                <i class="ph ph-upload-simple"></i>
                <span>Uploading to Instagram...</span>
            </div>
            <div class="upload-progress-bar">
                <div class="upload-progress-fill" id="uploadProgressFill" style="width: 0%"></div>
            </div>
            <div class="upload-progress-text" id="uploadProgressText">Initializing...</div>
        </div>
    `;

    document.body.appendChild(notification);

    // Fade in
    setTimeout(() => notification.classList.add('show'), 100);
}

/**
 * Poll upload progress
 */
async function pollUploadProgress(uploadId, mode, uploadBtn, originalBtnContent) {
    const maxAttempts = 120; // Poll for up to 10 minutes
    let attempt = 0;

    const poll = async () => {
        attempt++;

        try {
            const response = await fetch(`/instagram-upload-studio/api/upload-status/${uploadId}`);
            const data = await response.json();

            if (!data.success) {
                updateUploadProgress('failed', 0, 'Upload failed');
                // Re-enable button on failure
                if (uploadBtn) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = originalBtnContent;
                }
                return;
            }

            const upload = data.upload;
            const status = upload.status;
            const progress = upload.progress || 0;

            // Update UI
            updateUploadProgress(status, progress, getStatusMessage(status, mode));

            // Check if complete or failed
            if (status === 'completed') {
                setTimeout(() => hideUploadProgress(), 3000);

                // Re-enable button on completion
                if (uploadBtn) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = originalBtnContent;
                }

                // Show success in results panel
                const message = upload.message || 'Video uploaded successfully!';
                document.getElementById('resultsContainer').innerHTML = `
                    <div style="max-width: 500px; margin: 2rem auto; text-align: center; padding: 2.5rem; background: var(--bg-secondary); border: 1px solid var(--border-primary); border-radius: 12px;">
                        <div style="width: 64px; height: 64px; margin: 0 auto 1.5rem; background: linear-gradient(135deg, #10B981 0%, #059669 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);">
                            <i class="ph-fill ph-check" style="font-size: 2rem; color: white;"></i>
                        </div>
                        <h3 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1.5rem; font-weight: 600;">Upload Complete!</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 2rem; font-size: 0.9375rem; line-height: 1.6;">
                            ${message}
                        </p>
                        <button onclick="location.reload()" style="display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.75rem 1.5rem; background: transparent; color: var(--text-secondary); border: 1px solid var(--border-primary); border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s ease; font-size: 0.9375rem;">
                            <i class="ph ph-arrow-counter-clockwise"></i> Upload Another Video
                        </button>
                    </div>
                `;

                // Reset state
                selectedFile = null;
                selectedCaptionIndex = null;
                return;

            } else if (status === 'failed') {
                setTimeout(() => hideUploadProgress(), 5000);
                showToast('Upload failed: ' + (upload.error || 'Unknown error'), 'error');

                // Re-enable button on failure
                if (uploadBtn) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = originalBtnContent;
                }
                return;
            }

            // Continue polling
            if (attempt < maxAttempts) {
                setTimeout(poll, 2000); // Poll every 2 seconds
            } else {
                updateUploadProgress('failed', 0, 'Upload timeout');
                // Re-enable button on timeout
                if (uploadBtn) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = originalBtnContent;
                }
            }

        } catch (error) {
            console.error('Error polling upload progress:', error);
            updateUploadProgress('failed', 0, 'Error checking status');
            // Re-enable button on error
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = originalBtnContent;
            }
        }
    };

    poll();
}

/**
 * Update upload progress UI
 */
function updateUploadProgress(status, progress, message) {
    const progressFill = document.getElementById('uploadProgressFill');
    const progressText = document.getElementById('uploadProgressText');
    const notification = document.getElementById('uploadProgressNotification');

    if (!progressFill || !progressText || !notification) return;

    progressFill.style.width = `${progress}%`;
    progressText.textContent = message;

    // Update colors based on status
    if (status === 'completed') {
        notification.classList.add('success');
        notification.classList.remove('error');
    } else if (status === 'failed') {
        notification.classList.add('error');
        notification.classList.remove('success');
    }
}

/**
 * Hide upload progress notification
 */
function hideUploadProgress() {
    const notification = document.getElementById('uploadProgressNotification');
    if (notification) {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }
}

/**
 * Get status message for display
 */
function getStatusMessage(status, mode) {
    switch (status) {
        case 'completed':
            return mode === 'inbox' ? 'Uploaded to inbox!' : 'Published successfully!';
        case 'failed':
            return 'Upload failed';
        default:
            return 'Uploading to Instagram...';
    }
}

/**
 * Show toast notification
 */
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

/**
 * Handle URL parameters (success/error messages from OAuth)
 */
function handleUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has('success')) {
        const success = urlParams.get('success');
        if (success === 'connected') {
            showToast('Successfully connected to Instagram!', 'success');
        }
    }

    if (urlParams.has('error')) {
        const error = urlParams.get('error');
        const errorMessages = {
            'oauth_init_failed': 'Failed to start Instagram connection',
            'oauth_denied': 'Instagram connection was denied',
            'invalid_callback': 'Invalid callback from Instagram',
            'callback_failed': 'Failed to complete Instagram connection'
        };

        showToast(errorMessages[error] || 'An error occurred', 'error');
    }

    // Clean URL
    if (urlParams.has('success') || urlParams.has('error')) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

/**
 * Static upload area handlers (left panel)
 */
function triggerVideoUploadStatic() {
    const fileInput = document.getElementById('videoFileInputStatic');
    if (fileInput) {
        fileInput.click();
    }
}

function handleVideoSelectStatic(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Store the selected file globally
    selectedFile = file;

    // Update static UI
    const uploadContent = document.getElementById('uploadContentStatic');
    const uploadProgress = document.getElementById('uploadProgressStatic');
    const fileName = document.getElementById('uploadFileNameStatic');
    const fileSize = document.getElementById('uploadFileSizeStatic');

    if (uploadContent) uploadContent.style.display = 'none';
    if (uploadProgress) uploadProgress.style.display = 'flex';
    if (fileName) fileName.textContent = file.name;
    if (fileSize) fileSize.textContent = formatFileSize(file.size);

    showToast('Video ready to upload', 'success');
}

function removeVideoStatic(event) {
    event.stopPropagation();
    event.preventDefault();

    selectedFile = null;

    const uploadContent = document.getElementById('uploadContentStatic');
    const uploadProgress = document.getElementById('uploadProgressStatic');
    const fileInput = document.getElementById('videoFileInputStatic');

    if (uploadContent) uploadContent.style.display = 'flex';
    if (uploadProgress) uploadProgress.style.display = 'none';
    if (fileInput) fileInput.value = '';

    showToast('Video removed', 'info');
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


/**
 * Handle status change (show/hide schedule datetime)
 */
function handleStatusChange() {
    const statusSelect = document.getElementById('statusSelect');
    const scheduleDateTime = document.getElementById('scheduleDateTime');
    const scheduleDateSelect = document.getElementById('scheduleDateSelect');
    const scheduleTimeSelect = document.getElementById('scheduleTimeSelect');
    const uploadBtnText = document.getElementById('uploadBtnText');
    const timezoneIndicator = document.getElementById('timezoneIndicator');

    if (statusSelect && scheduleDateTime) {
        if (statusSelect.value === 'scheduled') {
            scheduleDateTime.style.display = 'block';

            // Update timezone indicator
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

            // Set default to tomorrow at 12:00 in user's local time
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

            // Update button text
            if (uploadBtnText) {
                uploadBtnText.textContent = 'Schedule Post';
            }
        } else {
            scheduleDateTime.style.display = 'none';

            // Update button text
            if (uploadBtnText) {
                uploadBtnText.textContent = 'Publish to Instagram';
            }
        }
    }
}

/**
 * Populate schedule date dropdown (365 days)
 */
function populateScheduleDateDropdown() {
    const dateSelect = document.getElementById('scheduleDateSelect');
    if (!dateSelect) return;

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
 * Escape HTML to prevent XSS
 */
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
 * Copy a specific caption
 */
function copyCaption(event, index) {
    event.stopPropagation();
    
    const caption = currentCaptions[index];
    const fullText = `${caption.caption}\n\n${caption.hashtags || ''}`;
    
    navigator.clipboard.writeText(fullText).then(() => {
        showToast('Caption copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy caption', 'error');
    });
}

/**
 * TikTok Upload Studio JavaScript
 * Handles OAuth connection, title generation, and video upload
 */

let selectedFile = null;
let isConnected = false;
let currentTitles = [];
let isGeneratingTitles = false;
let isCheckingConnection = true;
let selectedTitleIndex = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('TikTok Upload Studio initialized');

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
 * Check if user is connected to TikTok
 */
async function checkConnectionStatus() {
    try {
        const response = await fetch('/tiktok-upload-studio/api/status');
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
    const uploadFlow = document.querySelector('.upload-flow');
    const buttonSkeleton = document.getElementById('buttonSkeleton');
    const connectionButtons = document.getElementById('connectionButtons');
    const infoNotice = document.getElementById('infoNotice');

    // Remove loading state
    statusDot.classList.remove('loading');
    isCheckingConnection = false;

    // Hide skeleton, show actual buttons
    if (buttonSkeleton) buttonSkeleton.style.display = 'none';
    if (connectionButtons) connectionButtons.style.display = 'block';

    if (data.connected) {
        // Connected state
        statusDot.classList.remove('disconnected');
        statusText.textContent = 'Connected to TikTok';
        connectBtn.style.display = 'none';
        disconnectBtn.style.display = 'inline-flex';

        // Hide info notice
        if (infoNotice) infoNotice.style.display = 'none';

        if (uploadFlow) {
            uploadFlow.classList.add('enabled');
        }

        // Show user info if available
        if (data.user_info) {
            userInfo.style.display = 'flex';
            document.getElementById('userAvatar').src = data.user_info.avatar_url || '/static/img/default-avatar.png';
            document.getElementById('userName').textContent = data.user_info.display_name || 'TikTok User';
            document.getElementById('userOpenId').textContent = `@${data.user_info.open_id}`;
        }
    } else {
        // Disconnected state
        statusDot.classList.add('disconnected');
        statusText.textContent = 'Not Connected';
        connectBtn.style.display = 'inline-flex';
        disconnectBtn.style.display = 'none';
        userInfo.style.display = 'none';

        // Show info notice
        if (infoNotice) infoNotice.style.display = 'flex';

        if (uploadFlow) {
            uploadFlow.classList.remove('enabled');
        }
    }
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Connect button
    const connectBtn = document.getElementById('connectBtn');
    if (connectBtn) {
        connectBtn.addEventListener('click', connectToTikTok);
    }

    // Disconnect button
    const disconnectBtn = document.getElementById('disconnectBtn');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectFromTikTok);
    }
}

/**
 * Connect to TikTok
 */
function connectToTikTok() {
    window.location.href = '/tiktok-upload-studio/connect';
}

/**
 * Disconnect from TikTok
 */
async function disconnectFromTikTok() {
    if (!confirm('Are you sure you want to disconnect your TikTok account?')) {
        return;
    }

    try {
        const response = await fetch('/tiktok-upload-studio/disconnect', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast('TikTok account disconnected successfully', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast('Failed to disconnect: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error disconnecting:', error);
        showToast('Failed to disconnect from TikTok', 'error');
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
 * Generate titles and hashtags
 */
async function generateTitles() {
    const keywords = document.getElementById('keywordsInput').value.trim();
    const videoInput = document.getElementById('videoConceptInput').value.trim();

    // Validation
    if (!keywords) {
        showToast('Please enter at least one target keyword', 'error');
        return;
    }

    if (isGeneratingTitles) return;

    isGeneratingTitles = true;
    const generateBtn = document.getElementById('generateTitlesBtn');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="ph ph-spinner"></i> Generating...';

    // Show loading state
    document.getElementById('resultsContainer').innerHTML = `
        <div class="loading-container">
            <div class="loading-spinner"><i class="ph ph-spinner"></i></div>
            <div class="loading-text">Creating Your Content</div>
            <div class="loading-subtext">Generating titles and hashtags...</div>
        </div>
    `;

    try {
        // Call API to generate titles
        const response = await fetch('/tiktok-upload-studio/api/generate-titles', {
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
                showInsufficientCreditsError();
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
            <div class="empty-results">
                <i class="ph ph-warning-circle" style="color: #EF4444; opacity: 0.5; font-size: 4rem; margin-bottom: 1.5rem;"></i>
                <div class="empty-title">Generation Failed</div>
                <div class="empty-text">${error.message || 'Unable to generate content. Please try again.'}</div>
            </div>
        `;
        showToast('Failed to generate titles', 'error');
    } finally {
        isGeneratingTitles = false;
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="ph ph-sparkle"></i> Generate Titles & Hashtags';
    }
}

/**
 * Display generated titles
 */
function displayResults(titles) {
    currentTitles = titles;

    let html = '';

    // Add tabs
    html += '<div class="results-tabs">';
    html += `
        <button class="results-tab-btn active" onclick="switchTab('titles')">
            <i class="ph ph-sparkle"></i> Titles
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

    // Titles section
    html += renderTitlesSection(titles, true);

    // Upload section (only if connected)
    if (isConnected) {
        html += renderUploadSection(false);
    }

    document.getElementById('resultsContainer').innerHTML = html;
}

/**
 * Render titles section
 */
function renderTitlesSection(titles, visible) {
    return `
        <div class="results-section tab-content-section" id="titlesSection" style="${visible ? 'display: block;' : 'display: none;'}">
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
            ${isConnected ? `
                <div style="padding: 0.75rem 1.5rem; font-size: 0.8125rem; color: var(--text-tertiary); font-style: italic; display: flex; align-items: center; gap: 0.5rem; border-bottom: 1px solid var(--border-primary);">
                    <i class="ph ph-info"></i>
                    <span>Click on a title below to select it for your video</span>
                </div>
            ` : ''}
            <div class="titles-content">
                <div class="titles-list">
                    ${titles.map((title, index) => `
                        <div class="title-item ${selectedTitleIndex === index ? 'selected' : ''}" id="title-item-${index}" onclick="selectTitle(${index})">
                            <span class="title-number">${index + 1}</span>
                            <div class="title-text">${escapeHtml(title)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;
}

/**
 * Render upload section
 */
function renderUploadSection(visible) {
    return `
        <div class="results-section tab-content-section" id="uploadSection" style="${visible ? 'display: block;' : 'display: none;'}">
            <div class="upload-section-content">
                <form id="uploadForm" enctype="multipart/form-data">
                    <!-- Video File Upload -->
                    <div class="form-group">
                        <label class="form-label">
                            <i class="ph ph-upload"></i>
                            Upload Video
                        </label>
                        <div class="video-upload-area" id="videoUploadArea" onclick="triggerVideoUpload()">
                            <input type="file" id="videoFileInput" accept="video/*" style="display: none;">
                            <div class="upload-content" id="uploadContent">
                                <i class="ph ph-cloud-arrow-up" style="font-size: 2rem; color: var(--text-tertiary); margin-bottom: 0.25rem;"></i>
                                <div style="color: var(--text-primary); font-weight: 500; margin-bottom: 0.125rem; font-size: 0.9375rem;">Click to upload video</div>
                                <div style="color: var(--text-tertiary); font-size: 0.8125rem;">MP4, WebM, or MOV (max 4GB)</div>
                            </div>
                            <div class="upload-progress" id="uploadProgress" style="display: none;">
                                <div class="upload-file-info">
                                    <i class="ph ph-video" style="font-size: 2rem; color: var(--primary);"></i>
                                    <div style="flex: 1;">
                                        <div id="uploadFileName" style="color: var(--text-primary); font-weight: 500;"></div>
                                        <div id="uploadFileSize" style="color: var(--text-tertiary); font-size: 0.875rem;"></div>
                                    </div>
                                </div>
                                <button class="remove-video-btn" onclick="removeVideoFile(event)" type="button" title="Remove video">
                                    <i class="ph ph-x"></i>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Upload Options Grid -->
                    <div class="upload-options-grid">
                        <!-- Upload Mode -->
                        <div class="upload-option-card">
                            <label class="upload-option-label">
                                <i class="ph ph-lightning"></i>
                                Upload Mode
                            </label>
                            <div class="radio-group">
                                <label class="radio-option">
                                    <input type="radio" name="mode" id="modeDirect" value="direct" checked>
                                    <div class="radio-content">
                                        <i class="ph ph-lightning"></i>
                                        <div>
                                            <div class="option-title">Direct Post</div>
                                            <div class="option-desc">Post immediately</div>
                                        </div>
                                    </div>
                                </label>

                                <label class="radio-option">
                                    <input type="radio" name="mode" id="modeInbox" value="inbox">
                                    <div class="radio-content">
                                        <i class="ph ph-pencil-simple"></i>
                                        <div>
                                            <div class="option-title">Save to Inbox</div>
                                            <div class="option-desc">Edit before posting</div>
                                        </div>
                                    </div>
                                </label>
                            </div>
                        </div>

                        <!-- Privacy Level -->
                        <div class="upload-option-card">
                            <label class="upload-option-label">
                                <i class="ph ph-lock-key"></i>
                                Who can view
                            </label>
                            <div class="radio-group">
                                <label class="radio-option">
                                    <input type="radio" name="privacy" id="privacyPublic" value="PUBLIC_TO_EVERYONE" checked>
                                    <div class="radio-content">
                                        <i class="ph ph-globe"></i>
                                        <div>
                                            <div class="option-title">Public</div>
                                            <div class="option-desc">Everyone</div>
                                        </div>
                                    </div>
                                </label>

                                <label class="radio-option">
                                    <input type="radio" name="privacy" id="privacyFollowers" value="FOLLOWER_OF_CREATOR">
                                    <div class="radio-content">
                                        <i class="ph ph-users"></i>
                                        <div>
                                            <div class="option-title">Followers</div>
                                            <div class="option-desc">Followers only</div>
                                        </div>
                                    </div>
                                </label>

                                <label class="radio-option">
                                    <input type="radio" name="privacy" id="privacyPrivate" value="SELF_ONLY">
                                    <div class="radio-content">
                                        <i class="ph ph-lock"></i>
                                        <div>
                                            <div class="option-title">Private</div>
                                            <div class="option-desc">Only you</div>
                                        </div>
                                    </div>
                                </label>
                            </div>
                        </div>
                    </div>

                    <!-- Upload Button -->
                    <button type="submit" id="uploadBtn" class="btn-primary">
                        <i class="ph ph-tiktok-logo"></i>
                        Upload to TikTok
                    </button>
                </form>

                <!-- Info Notice -->
                <div class="info-notice" style="margin-top: 1rem;">
                    <i class="ph ph-info"></i>
                    <div>
                        <strong>Note:</strong> TikTok API doesn't support adding music during upload. Include audio in your video file or edit in TikTok app after uploading to inbox.
                    </div>
                </div>
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

    // Mode selection - show/hide privacy based on mode
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    modeRadios.forEach(radio => {
        radio.addEventListener('change', handleModeChange);
    });
}

/**
 * Select a title for upload
 */
function selectTitle(index) {
    selectedTitleIndex = index;

    // Update UI - highlight selected title
    document.querySelectorAll('.title-item').forEach((item, i) => {
        if (i === index) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });

    showToast('Title selected! Switch to Upload tab when ready.', 'success');
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
 * Copy all titles
 */
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
    const privacyGroup = document.querySelector('.form-group:has(input[name="privacy"])');

    if (privacyGroup) {
        if (mode === 'inbox') {
            privacyGroup.style.display = 'none';
        } else {
            privacyGroup.style.display = 'block';
        }
    }
}

/**
 * Handle video upload
 */
async function handleUpload(e) {
    e.preventDefault();

    if (!selectedFile) {
        showToast('Please select a video file', 'error');
        return;
    }

    if (selectedTitleIndex === null) {
        showToast('Please select a title from the Titles tab', 'error');
        return;
    }

    const title = currentTitles[selectedTitleIndex];
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const privacyLevel = mode === 'inbox' ? 'SELF_ONLY' : document.querySelector('input[name="privacy"]:checked').value;

    // Disable upload button
    const uploadBtn = document.getElementById('uploadBtn');
    const originalBtnContent = uploadBtn.innerHTML;
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="ph ph-spinner"></i> Uploading...';

    try {
        // Create form data
        const formData = new FormData();
        formData.append('video', selectedFile);
        formData.append('title', title);
        formData.append('privacy_level', privacyLevel);
        formData.append('mode', mode);

        console.log('Uploading video to TikTok...');

        const response = await fetch('/tiktok-upload-studio/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message || 'Video uploaded successfully!', 'success');

            // Show success message
            document.getElementById('resultsContainer').innerHTML = `
                <div style="max-width: 500px; margin: 2rem auto; text-align: center; padding: 2.5rem; background: var(--bg-secondary); border: 1px solid var(--border-primary); border-radius: 12px;">
                    <div style="width: 64px; height: 64px; margin: 0 auto 1.5rem; background: linear-gradient(135deg, #10B981 0%, #059669 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);">
                        <i class="ph-fill ph-check" style="font-size: 2rem; color: white;"></i>
                    </div>
                    <h3 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1.5rem; font-weight: 600;">Upload Complete!</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 2rem; font-size: 0.9375rem; line-height: 1.6;">
                        Your video has been successfully uploaded to TikTok
                    </p>
                    <button onclick="location.reload()" style="display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.75rem 1.5rem; background: transparent; color: var(--text-secondary); border: 1px solid var(--border-primary); border-radius: 8px; cursor: pointer; font-weight: 500; transition: all 0.2s ease; font-size: 0.9375rem;">
                        <i class="ph ph-arrow-counter-clockwise"></i> Upload Another Video
                    </button>
                </div>
            `;

            // Reset state
            selectedFile = null;
            selectedTitleIndex = null;
        } else {
            showToast('Upload failed: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Failed to upload video', 'error');
    } finally {
        // Re-enable button
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalBtnContent;
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
            showToast('Successfully connected to TikTok!', 'success');
        }
    }

    if (urlParams.has('error')) {
        const error = urlParams.get('error');
        const errorMessages = {
            'oauth_init_failed': 'Failed to start TikTok connection',
            'oauth_denied': 'TikTok connection was denied',
            'invalid_callback': 'Invalid callback from TikTok',
            'callback_failed': 'Failed to complete TikTok connection'
        };

        showToast(errorMessages[error] || 'An error occurred', 'error');
    }

    // Clean URL
    if (urlParams.has('success') || urlParams.has('error')) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }
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
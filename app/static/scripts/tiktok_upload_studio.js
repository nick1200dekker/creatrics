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
let hasPremium = window.hasPremium || false;  // Premium subscription status from backend
let tiktokRepostModal = null;  // Repost modal instance
let uploadMode = 'upload';  // 'upload' or 'repost'
let repostContent = null;  // Selected content from repost modal
let repostScheduledDate = null;  // Scheduled date from repost content

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

    // Initialize repost modal
    initializeRepostModal();

    // Initialize calendar link modal
    initializeCalendarModal();

    // Initialize mode to trigger default scheduled setup (wait for DOM to be fully ready)
    setTimeout(() => {
        handleModeChange();
    }, 100);
});

/**
 * Initialize the repost modal
 */
function initializeRepostModal() {
    if (typeof RepostModal === 'undefined') {
        console.error('RepostModal not loaded');
        return;
    }

    tiktokRepostModal = new RepostModal({
        mediaTypeFilter: 'video',  // TikTok only supports videos
        platform: 'tiktok',
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
 * Initialize the calendar link modal
 */
function initializeCalendarModal() {
    if (typeof CalendarLinkModal === 'undefined') {
        console.error('CalendarLinkModal not loaded');
        return;
    }

    CalendarLinkModal.init('TikTok', function(item) {
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
            const scheduledRadio = document.getElementById('modeScheduled');
            if (scheduledRadio) {
                scheduledRadio.checked = true;
                handleModeChange();
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
}

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
        if (tiktokRepostModal) {
            tiktokRepostModal.open();
        }
    } else {
        // Reset to upload mode
        repostContent = null;
    }
}

/**
 * Handle content selection from repost modal
 */
function handleContentSelection(content) {
    repostContent = content;

    // Pre-fill keywords
    const keywordsInput = document.getElementById('keywordsInput');
    if (keywordsInput && content.keywords) {
        keywordsInput.value = content.keywords;
    }

    // Pre-fill description
    const videoConceptInput = document.getElementById('videoConceptInput');
    if (videoConceptInput && content.content_description) {
        videoConceptInput.value = content.content_description;
        updateCharCount();
    }

    // Check if this content has any platform's scheduled post date
    const platforms = content.platforms_posted || {};

    // Check all platforms for a scheduled date (prioritize TikTok, then check others)
    repostScheduledDate = null;  // Reset
    const platformOrder = ['tiktok', 'instagram', 'youtube', 'x'];

    for (const platform of platformOrder) {
        const platformData = platforms[platform];
        if (platformData && platformData.scheduled_for) {
            const date = new Date(platformData.scheduled_for);
            // Check if the scheduled time is in the future
            if (date > new Date()) {
                repostScheduledDate = date;
                console.log('Found scheduled date from', platform, ':', repostScheduledDate);
                break;
            }
        }
    }

    // Note: We'll apply the scheduled date when the upload form is rendered (after generating titles)

    // Set the video URL (we'll use this during upload)
    // Display the video in the upload area
    displayRepostVideo(content);

    console.log('Content selected for reposting:', content);
}

/**
 * Display repost video in the upload area
 */
function displayRepostVideo(content) {
    const uploadContent = document.getElementById('uploadContentStatic');
    const uploadProgress = document.getElementById('uploadProgressStatic');
    const fileName = document.getElementById('uploadFileNameStatic');
    const fileSize = document.getElementById('uploadFileSizeStatic');

    if (uploadContent) uploadContent.style.display = 'none';
    if (uploadProgress) uploadProgress.style.display = 'flex';

    // Extract filename from URL
    const urlParts = content.media_url.split('/');
    const fullFilename = urlParts[urlParts.length - 1];

    if (fileName) fileName.textContent = decodeURIComponent(fullFilename);
    if (fileSize) fileSize.textContent = 'From library';
}

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
        statusText.textContent = 'Connected to TikTok';
        connectBtn.style.display = 'none';
        disconnectBtn.style.display = 'inline-flex';

        // Show video upload section
        if (videoUploadSection) videoUploadSection.style.display = 'block';

        // Show user info if available
        if (data.user_info) {
            console.log('TikTok user info:', data.user_info);
            userInfo.style.display = 'flex';

            const avatarEl = document.getElementById('userAvatar');
            if (data.user_info.avatar_url) {
                avatarEl.src = data.user_info.avatar_url;
                avatarEl.style.display = 'block';
            } else {
                // Hide the avatar if not available
                avatarEl.style.display = 'none';
            }

            document.getElementById('userName').textContent = data.user_info.display_name || 'TikTok User';

            // Show username if available
            const userOpenIdEl = document.getElementById('userOpenId');
            if (data.user_info.username) {
                userOpenIdEl.textContent = '@' + data.user_info.username;
                userOpenIdEl.style.display = 'block';
            } else {
                userOpenIdEl.style.display = 'none';
            }
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

    // Initialize mode after rendering HTML
    if (isConnected) {
        handleModeChange();
    }
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
 * Render upload section (Right panel - without video upload, just options)
 */
function renderUploadSection(visible) {
    return `
        <div class="results-section tab-content-section" id="uploadSection" style="${visible ? 'display: block;' : 'display: none;'}">
            <div class="upload-section-content">
                <form id="uploadForm" enctype="multipart/form-data">
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
                                    <input type="radio" name="mode" id="modeDirect" value="direct" onchange="handleModeChange()">
                                    <div class="radio-content">
                                        <i class="ph ph-lightning"></i>
                                        <div>
                                            <div class="option-title">Direct Post</div>
                                            <div class="option-desc">Post immediately</div>
                                        </div>
                                    </div>
                                </label>

                                <label class="radio-option">
                                    <input type="radio" name="mode" id="modeInbox" value="inbox" onchange="handleModeChange()">
                                    <div class="radio-content">
                                        <i class="ph ph-pencil-simple"></i>
                                        <div>
                                            <div class="option-title">Save to Inbox</div>
                                            <div class="option-desc">Edit before posting</div>
                                        </div>
                                    </div>
                                </label>

                                <label class="radio-option">
                                    <input type="radio" name="mode" id="modeScheduled" value="scheduled" checked onchange="handleModeChange()">
                                    <div class="radio-content">
                                        <i class="ph ph-clock"></i>
                                        <div>
                                            <div class="option-title">Schedule</div>
                                            <div class="option-desc">Post at specific time</div>
                                        </div>
                                    </div>
                                </label>
                            </div>
                        </div>

                        <!-- Schedule Time (shown when scheduled mode is selected) -->
                        <div class="upload-option-card" id="scheduleCard">
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

                        <!-- Privacy Level -->
                        <div class="upload-option-card" id="privacyCard">
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

                        <!-- Content Calendar Integration -->
                        <div class="upload-option-card">
                            <label class="upload-option-label">
                                <i class="ph ph-calendar-check"></i>
                                Content Calendar
                            </label>
                            <select id="contentCalendarSelect" class="privacy-select" onchange="handleContentCalendarChange()">
                                <option value="create_new">Create New Calendar Item</option>
                                <option value="link_existing">Link to Existing Item</option>
                            </select>
                        </div>
                    </div>

                    <!-- Upload Button -->
                    <button type="submit" id="uploadBtn" class="btn-primary">
                        <i class="ph ph-upload"></i>
                        Upload to TikTok
                    </button>
                </form>

                <!-- Upload Progress Bar -->
                <div id="uploadProgressBar" class="upload-progress-bar" style="display: none; margin-top: 1rem;">
                    <div class="upload-progress-info">
                        <span class="upload-progress-status">Uploading...</span>
                        <span class="upload-progress-percent">0%</span>
                    </div>
                    <div class="upload-progress-track">
                        <div class="upload-progress-fill" id="uploadProgressFill"></div>
                    </div>
                </div>

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

    // Apply repost scheduled date if available
    if (repostScheduledDate) {
        applyRepostScheduledDate();
    }
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
 * Handle mode change - show/hide privacy options and schedule card
 */
function handleModeChange() {
    const mode = document.querySelector('input[name="mode"]:checked')?.value;
    const privacyCard = document.getElementById('privacyCard');
    const scheduleCard = document.getElementById('scheduleCard');

    // Privacy card: hide for inbox and scheduled (inbox=draft, scheduled=always public)
    if (privacyCard) {
        if (mode === 'inbox' || mode === 'scheduled') {
            privacyCard.style.display = 'none';
        } else {
            privacyCard.style.display = 'block';
        }
    }

    // Schedule card: only show for scheduled mode
    if (scheduleCard) {
        if (mode === 'scheduled') {
            scheduleCard.style.display = 'block';

            // Update timezone indicator
            const timezoneIndicator = document.getElementById('timezoneIndicator');
            if (timezoneIndicator) {
                const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                const tzAbbr = new Date().toLocaleTimeString('en-us', {timeZoneName:'short'}).split(' ')[2];
                timezoneIndicator.textContent = `(${tzAbbr || userTimezone})`;
            }

            // Populate dropdowns if not already done
            const scheduleDateSelect = document.getElementById('scheduleDateSelect');
            const scheduleTimeSelect = document.getElementById('scheduleTimeSelect');

            if (scheduleDateSelect && scheduleDateSelect.options.length === 1) {
                populateScheduleDateDropdown();
            }
            if (scheduleTimeSelect && scheduleTimeSelect.options.length === 1) {
                populateScheduleTimeDropdown();
            }

            // Set default to tomorrow at 12:00
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
            scheduleCard.style.display = 'none';
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
 * Apply scheduled date from repost content
 */
function applyRepostScheduledDate() {
    if (!repostScheduledDate) return;

    console.log('Applying repost scheduled date:', repostScheduledDate);

    // Switch to scheduled mode
    const scheduledModeRadio = document.querySelector('input[name="mode"][value="scheduled"]');
    if (scheduledModeRadio) {
        scheduledModeRadio.checked = true;
        // Trigger change event to show schedule inputs and populate dropdowns
        handleModeChange();
    }

    // Need to wait a bit for handleModeChange to populate dropdowns
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

            // Set the select values
            dateSelect.value = dateValue;
            timeSelect.value = timeValue;

            console.log('Set schedule to:', dateValue, timeValue);
        }
    }, 100);
}

/**
 * Handle video upload (via Firebase Storage + Late.dev)
 */
async function handleUpload(e) {
    e.preventDefault();

    // Check if we have either a selected file (upload mode) or repost content (repost mode)
    if (!selectedFile && !(uploadMode === 'repost' && repostContent)) {
        showToast('Please select a video file', 'error');
        return;
    }

    if (selectedTitleIndex === null) {
        showToast('Please select a title from the Titles tab', 'error');
        return;
    }

    const title = currentTitles[selectedTitleIndex];
    const mode = document.querySelector('input[name="mode"]:checked').value;

    // Privacy level: inbox=SELF_ONLY, scheduled=PUBLIC, direct=PUBLIC (or user selected)
    let privacyLevel;
    if (mode === 'inbox') {
        privacyLevel = 'SELF_ONLY';
    } else if (mode === 'scheduled') {
        privacyLevel = 'PUBLIC_TO_EVERYONE';  // Scheduled posts are always public
    } else {
        // Direct post: always public (simplest option)
        privacyLevel = 'PUBLIC_TO_EVERYONE';
    }

    // Check if calendar item is linked - if so, use its publish date
    const linkedCalendarItem = CalendarLinkModal.getLinkedItem();
    let scheduleTime = null;
    let userTimezone = 'UTC';

    if (linkedCalendarItem && linkedCalendarItem.publish_date) {
        // Use the linked calendar item's publish date
        scheduleTime = linkedCalendarItem.publish_date;
        userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        console.log('Using linked calendar item publish date:', scheduleTime);
    } else if (mode === 'scheduled') {
        // Only use form fields if NOT linked to calendar item
        const scheduleDateSelect = document.getElementById('scheduleDateSelect');
        const scheduleTimeSelect = document.getElementById('scheduleTimeSelect');

        const dateValue = scheduleDateSelect ? scheduleDateSelect.value : null;
        const timeValue = scheduleTimeSelect ? scheduleTimeSelect.value : null;

        if (!dateValue || !timeValue) {
            showToast('Please select both date and time for scheduling', 'error');
            return;
        }

        // Get user's local timezone
        userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        // Combine date and time in user's local timezone
        const localDateTime = new Date(`${dateValue}T${timeValue}:00`);

        // Validate that schedule time is in the future
        if (localDateTime <= new Date()) {
            showToast('Schedule time must be in the future', 'error');
            return;
        }

        // Convert to ISO format
        scheduleTime = localDateTime.toISOString();
    }

    // Disable upload button and show progress bar
    const uploadBtn = document.getElementById('uploadBtn');
    const originalBtnContent = uploadBtn.innerHTML;
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
        let mediaUrl, contentId;

        // Check if we're reposting existing content or uploading new
        if (uploadMode === 'repost' && repostContent) {
            // Use existing media URL from content library
            mediaUrl = repostContent.media_url;
            contentId = repostContent.id;
            console.log('Reposting existing content:', mediaUrl);
            uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Posting to TikTok...';

            // Update progress for repost
            if (progressBar) {
                progressFill.style.width = '30%';
                progressStatus.textContent = 'Preparing to post...';
                progressPercent.textContent = '30%';
            }
        } else {
            // Step 1: Upload media to Firebase Storage
            if (progressBar) {
                progressFill.style.width = '10%';
                progressStatus.textContent = 'Uploading video...';
                progressPercent.textContent = '10%';
            }

            const formData = new FormData();
            formData.append('media', selectedFile);

            // Add keywords and description to be saved in content library
            const keywordsInput = document.getElementById('keywordsInput');
            const videoConceptInput = document.getElementById('videoConceptInput');
            if (keywordsInput && keywordsInput.value) {
                formData.append('keywords', keywordsInput.value);
            }
            if (videoConceptInput && videoConceptInput.value) {
                formData.append('content_description', videoConceptInput.value);
            }

            const uploadResponse = await fetch('/tiktok-upload-studio/api/upload-media', {
                method: 'POST',
                body: formData
            });

            const uploadData = await uploadResponse.json();

            if (!uploadData.success) {
                throw new Error(uploadData.error || 'Failed to upload media');
            }

            mediaUrl = uploadData.media_url;
            contentId = uploadData.content_id;
            console.log('Media uploaded to Firebase:', mediaUrl);

            // Update progress after media upload
            if (progressBar) {
                progressFill.style.width = '50%';
                progressStatus.textContent = 'Video uploaded';
                progressPercent.textContent = '50%';
            }

            uploadBtn.innerHTML = '<i class="ph ph-circle-notch spinning"></i> Posting to TikTok...';
        }

        // Step 2: Post to TikTok via Late.dev using the Firebase URL
        if (progressBar) {
            progressFill.style.width = '60%';
            progressStatus.textContent = 'Posting to TikTok...';
            progressPercent.textContent = '60%';
        }
        // Get keywords and description for content library
        const keywordsInput = document.getElementById('keywordsInput');
        const videoConceptInput = document.getElementById('videoConceptInput');
        const keywords = keywordsInput ? keywordsInput.value.trim() : '';
        const contentDescription = videoConceptInput ? videoConceptInput.value.trim() : '';

        // Check if calendar item is linked
        const linkedCalendarItem = CalendarLinkModal.getLinkedItem();

        const postPayload = {
            title: title,
            media_url: mediaUrl,
            mode: mode,
            privacy_level: privacyLevel,
            keywords: keywords,
            content_description: contentDescription
        };

        // Add content_id if we have it
        if (contentId) {
            postPayload.content_id = contentId;
        }

        // Add calendar_event_id if linked
        if (linkedCalendarItem && linkedCalendarItem.id) {
            postPayload.calendar_event_id = linkedCalendarItem.id;
        }

        if (mode === 'scheduled') {
            postPayload.schedule_time = scheduleTime;
            postPayload.timezone = userTimezone;
        }

        const postResponse = await fetch('/tiktok-upload-studio/api/upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(postPayload)
        });

        const postData = await postResponse.json();

        if (postData.success) {
            // Complete progress
            if (progressBar) {
                progressFill.style.width = '100%';
                progressStatus.textContent = 'Complete!';
                progressPercent.textContent = '100%';
            }

            // Show success state on button
            uploadBtn.innerHTML = '<i class="ph ph-check-circle"></i> ' + (mode === 'scheduled' ? 'Scheduled!' : 'Posted!');

            let message = 'TikTok post successful!';
            if (mode === 'inbox') {
                message = 'Video saved to TikTok inbox!';
            } else if (mode === 'scheduled') {
                message = 'TikTok post scheduled successfully!';
            }
            showToast(message, 'success');

            // Wait 2 seconds to show success state, then refresh page
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            throw new Error(postData.error || 'TikTok post failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Upload failed: ' + error.message, 'error');
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalBtnContent;

        // Hide progress bar on error
        if (progressBar) {
            progressBar.style.display = 'none';
        }
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
                <span>Uploading to TikTok...</span>
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
            const response = await fetch(`/tiktok-upload-studio/api/upload-status/${uploadId}`);
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
                selectedTitleIndex = null;
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
            return 'Uploading to TikTok...';
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
}

function removeVideoStatic(event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }

    selectedFile = null;
    repostContent = null;  // Reset selected content from repost

    const uploadContent = document.getElementById('uploadContentStatic');
    const uploadProgress = document.getElementById('uploadProgressStatic');
    const fileInput = document.getElementById('videoFileInputStatic');

    if (uploadContent) uploadContent.style.display = 'flex';
    if (uploadProgress) uploadProgress.style.display = 'none';
    if (fileInput) fileInput.value = '';

    // Switch back to upload mode if in repost mode
    if (uploadMode === 'repost') {
        switchMode('upload');
    }

    // Only show toast if user manually clicked remove (event exists)
    if (event) {
        showToast('Video removed', 'info');
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
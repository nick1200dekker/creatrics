/**
 * TikTok Upload Studio JavaScript
 * Handles OAuth connection, file upload, and video posting
 */

let selectedFile = null;
let isConnected = false;
let currentTitles = [];
let isGeneratingTitles = false;
let isCheckingConnection = true;

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
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.querySelector('.status-text');

    if (statusDot && statusText) {
        statusDot.classList.remove('disconnected');
        statusDot.classList.add('loading');
        statusText.textContent = 'Checking connection...';
    }
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

    // Remove loading state
    statusDot.classList.remove('loading');
    isCheckingConnection = false;

    if (data.connected) {
        // Connected state
        statusDot.classList.remove('disconnected');
        statusText.textContent = 'Connected to TikTok';
        connectBtn.style.display = 'none';
        disconnectBtn.style.display = 'inline-flex';

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

    // File upload area
    const fileUploadArea = document.getElementById('fileUploadArea');
    const fileInput = document.getElementById('videoFileInput');

    if (fileUploadArea && fileInput) {
        // Click to upload
        fileUploadArea.addEventListener('click', () => fileInput.click());

        // File input change
        fileInput.addEventListener('change', handleFileSelect);

        // Drag and drop
        fileUploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            fileUploadArea.classList.add('dragover');
        });

        fileUploadArea.addEventListener('dragleave', () => {
            fileUploadArea.classList.remove('dragover');
        });

        fileUploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            fileUploadArea.classList.remove('dragover');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelect({ target: { files } });
            }
        });
    }

    // Remove file button
    const removeFileBtn = document.getElementById('removeFile');
    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            clearSelectedFile();
        });
    }

    // Upload form
    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    // Mode selection - show/hide privacy based on mode
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    modeRadios.forEach(radio => {
        radio.addEventListener('change', handleModeChange);
    });

    // Initialize privacy visibility based on default mode
    handleModeChange();
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
            showAlert('TikTok account disconnected successfully', 'success');
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showAlert('Failed to disconnect: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error disconnecting:', error);
        showAlert('Failed to disconnect from TikTok', 'error');
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
        showAlert('Please select a video file', 'error');
        return;
    }

    // Validate file size (max 4GB)
    const maxSize = 4 * 1024 * 1024 * 1024; // 4GB
    if (file.size > maxSize) {
        showAlert('Video file is too large (max 4GB)', 'error');
        return;
    }

    selectedFile = file;
    displaySelectedFile(file);
}

/**
 * Display selected file info
 */
function displaySelectedFile(file) {
    const fileUploadArea = document.getElementById('fileUploadArea');
    const selectedFileDiv = document.getElementById('selectedFile');

    // Hide upload area, show selected file
    fileUploadArea.style.display = 'none';
    selectedFileDiv.style.display = 'flex';

    // Update file details
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
}

/**
 * Clear selected file
 */
function clearSelectedFile() {
    selectedFile = null;
    document.getElementById('videoFileInput').value = '';
    document.getElementById('fileUploadArea').style.display = 'block';
    document.getElementById('selectedFile').style.display = 'none';
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
        showAlert('Please select a video file', 'error');
        return;
    }

    const title = document.getElementById('videoTitle').value.trim();
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const privacyLevel = mode === 'inbox' ? 'SELF_ONLY' : document.querySelector('input[name="privacy"]:checked').value;

    if (!title) {
        showAlert('Please enter a title/caption', 'error');
        return;
    }

    // Disable upload button
    const uploadBtn = document.getElementById('uploadBtn');
    const originalBtnContent = uploadBtn.innerHTML;
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<div class="spinner"></div> Uploading...';

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
            showAlert(data.message || 'Video uploaded successfully!', 'success');

            // Reset form
            document.getElementById('uploadForm').reset();
            clearSelectedFile();
        } else {
            showAlert('Upload failed: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showAlert('Failed to upload video', 'error');
    } finally {
        // Re-enable button
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = originalBtnContent;
    }
}

/**
 * Show alert message
 */
function showAlert(message, type) {
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.alert');
    existingAlerts.forEach(alert => alert.remove());

    // Create new alert
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;

    const icon = type === 'success' ? 'ph-check-circle' : 'ph-warning-circle';

    alert.innerHTML = `
        <i class="ph ${icon}"></i>
        <span>${message}</span>
    `;

    // Insert at top of container
    const container = document.querySelector('.generator-content');
    if (container) {
        container.insertBefore(alert, container.firstChild);
    }

    // Auto-remove after 5 seconds
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

/**
 * Handle URL parameters (success/error messages from OAuth)
 */
function handleUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has('success')) {
        const success = urlParams.get('success');
        if (success === 'connected') {
            showAlert('Successfully connected to TikTok!', 'success');
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

        showAlert(errorMessages[error] || 'An error occurred', 'error');
    }

    // Clean URL
    if (urlParams.has('success') || urlParams.has('error')) {
        window.history.replaceState({}, document.title, window.location.pathname);
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
        showAlert('Please enter at least one target keyword', 'error');
        return;
    }

    if (isGeneratingTitles) return;

    isGeneratingTitles = true;
    const generateBtn = document.getElementById('generateTitlesBtn');
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<i class="ph ph-spinner"></i> Generating...';

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
                showAlert('Insufficient credits. Please upgrade your plan.', 'error');
                return;
            }
            throw new Error(data.error || 'Failed to generate titles');
        }

        // Display results
        displayGeneratedTitles(data.titles);
        showAlert('Titles generated successfully! Click a title to use it.', 'success');

    } catch (error) {
        console.error('Error generating titles:', error);
        showAlert('Failed to generate titles: ' + error.message, 'error');
    } finally {
        isGeneratingTitles = false;
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="ph ph-sparkle"></i> Generate Titles & Hashtags';
    }
}

/**
 * Display generated titles
 */
function displayGeneratedTitles(titles) {
    currentTitles = titles;

    const container = document.getElementById('titlesResultsContainer');
    const titlesList = document.getElementById('titlesList');

    let html = titles.map((title, index) => `
        <div class="title-item" onclick="useTitle(${index})">
            <span class="title-number">${index + 1}</span>
            <span class="title-text">${escapeHtml(title)}</span>
            <button class="use-title-btn" onclick="useTitle(${index}); event.stopPropagation();">
                <i class="ph ph-arrow-down"></i> Use
            </button>
        </div>
    `).join('');

    titlesList.innerHTML = html;
    container.style.display = 'block';
}

/**
 * Use a generated title in the caption field
 */
function useTitle(index) {
    const title = currentTitles[index];
    const captionField = document.getElementById('videoTitle');

    captionField.value = title;
    captionField.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Highlight the caption field briefly
    captionField.style.border = '2px solid var(--primary-color)';
    setTimeout(() => {
        captionField.style.border = '';
    }, 1500);

    showAlert('Title added to caption field!', 'success');
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

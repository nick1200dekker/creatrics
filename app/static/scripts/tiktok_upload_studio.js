/**
 * TikTok Upload Studio JavaScript
 * Handles OAuth connection, file upload, and video posting
 */

let selectedFile = null;
let isConnected = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('TikTok Upload Studio initialized');

    // Check connection status
    checkConnectionStatus();

    // Setup event listeners
    setupEventListeners();

    // Handle URL parameters (success/error messages)
    handleUrlParams();
});

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
    const uploadSection = document.querySelector('.upload-section');

    if (data.connected) {
        // Connected state
        statusDot.classList.remove('disconnected');
        statusText.textContent = 'Connected to TikTok';
        connectBtn.style.display = 'none';
        disconnectBtn.style.display = 'inline-flex';
        uploadSection.classList.add('enabled');

        // Show user info if available
        if (data.user_info) {
            userInfo.style.display = 'flex';
            document.getElementById('userAvatar').src = data.user_info.avatar_url || '/static/img/default-avatar.png';
            document.getElementById('userName').textContent = data.user_info.display_name || 'TikTok User';
            document.getElementById('userOpenId').textContent = `ID: ${data.user_info.open_id}`;
        }
    } else {
        // Disconnected state
        statusDot.classList.add('disconnected');
        statusText.textContent = 'Not Connected';
        connectBtn.style.display = 'inline-flex';
        disconnectBtn.style.display = 'none';
        userInfo.style.display = 'none';
        uploadSection.classList.remove('enabled');
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
 * Handle video upload
 */
async function handleUpload(e) {
    e.preventDefault();

    if (!selectedFile) {
        showAlert('Please select a video file', 'error');
        return;
    }

    const title = document.getElementById('videoTitle').value.trim();
    const privacyLevel = document.querySelector('input[name="privacy"]:checked').value;

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
    const container = document.querySelector('.tiktok-studio-container');
    container.insertBefore(alert, container.firstChild);

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

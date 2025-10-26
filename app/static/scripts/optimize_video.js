/**
 * Optimize Video JavaScript
 * Handles video optimization interface and API interactions
 */

// Global state
let currentVideoId = null;
let currentOptimizedDescription = null;
let currentInputMode = 'public'; // 'public', 'private', or 'url'
let hasYouTubeConnected = false; // Track if YouTube is connected
let currentOptimizationData = null; // Store current optimization data to prevent loss when generating additional optimizations

// Load videos on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check for ongoing optimization
    const ongoingOptimization = sessionStorage.getItem('optimize_video_ongoing');
    if (ongoingOptimization) {
        const optimizationData = JSON.parse(ongoingOptimization);
        const currentTime = Date.now();

        // If optimization started less than 3 minutes ago, show loading
        if (currentTime - optimizationData.startTime < 180000) {
            console.log('Ongoing optimization detected for video:', optimizationData.videoId);
            currentVideoId = optimizationData.videoId;

            // Hide videos list, show loading section
            document.getElementById('videosListSection').style.display = 'none';
            document.getElementById('loadingSection').style.display = 'block';
            document.getElementById('resultsSection').style.display = 'none';

            // Poll for completion
            checkOptimizationStatus(optimizationData.videoId);
        } else {
            // Optimization timed out, clear it
            sessionStorage.removeItem('optimize_video_ongoing');
        }
    }

    loadMyVideos();

    // Check if video_id is in URL params (from homepage)
    const urlParams = new URLSearchParams(window.location.search);
    const videoId = urlParams.get('video_id');
    if (videoId) {
        // Auto-optimize the video
        optimizeVideo(videoId);
    }
});

/**
 * Switch between public, private, and URL input modes
 */
function switchInputMode(mode) {
    currentInputMode = mode;

    // Update toggle buttons
    document.getElementById('publicToggleBtn').classList.toggle('active', mode === 'public');
    document.getElementById('privateToggleBtn').classList.toggle('active', mode === 'private');
    document.getElementById('urlToggleBtn').classList.toggle('active', mode === 'url');

    // Hide all sections first
    document.getElementById('urlInputSection').style.display = 'none';
    document.getElementById('myVideosGrid').style.display = 'none';
    document.getElementById('myShortsSection').style.display = 'none';
    document.getElementById('privateVideosContent').style.display = 'none';
    document.getElementById('emptyVideos').style.display = 'none';

    // Show appropriate section
    if (mode === 'public') {
        // Show public videos and shorts
        const videosGrid = document.getElementById('myVideosGrid');
        const shortsSection = document.getElementById('myShortsSection');
        const shortsGrid = document.getElementById('myShortsGrid');

        videosGrid.style.display = 'grid';
        if (shortsGrid.children.length > 0) {
            shortsSection.style.display = 'block';
        }

        // Show empty state if no videos
        if (videosGrid.children.length === 0) {
            document.getElementById('emptyVideos').style.display = 'flex';
        }
    } else if (mode === 'private') {
        // Show private videos content
        document.getElementById('privateVideosContent').style.display = 'block';

        // Auto-load private videos if not already loaded
        const privateVideosGrid = document.getElementById('privateVideosGrid');

        // Check if grid is empty or only has loading/empty state
        const hasVideos = privateVideosGrid.querySelector('.video-card');
        if (!hasVideos) {
            loadPrivateVideos();
        }
    } else if (mode === 'url') {
        // Show URL input
        document.getElementById('urlInputSection').style.display = 'block';
    }
}

/**
 * Extract video ID from URL or return as-is if already an ID
 */
function extractVideoId(input) {
    input = input.trim();

    // If it's already just an ID (11 characters, alphanumeric)
    if (/^[a-zA-Z0-9_-]{11}$/.test(input)) {
        return input;
    }

    // Try to extract from various YouTube URL formats
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/  // Handle shorts URLs
    ];

    for (const pattern of patterns) {
        const match = input.match(pattern);
        if (match && match[1]) {
            return match[1];
        }
    }

    return null;
}

/**
 * Optimize video from URL input
 */
async function optimizeFromUrl() {
    const input = document.getElementById('videoUrlInput').value.trim();

    if (!input) {
        showToast('Please enter a YouTube URL or video ID', 'error');
        return;
    }

    const videoId = extractVideoId(input);

    if (!videoId) {
        showToast('Invalid YouTube URL or video ID', 'error');
        return;
    }

    // Optimize the video
    optimizeVideo(videoId);
}

/**
 * Format timestamp to human-readable format
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';

    // If it's already a human-readable string from RapidAPI (e.g., "2 days ago"), return it
    if (typeof timestamp === 'string' && timestamp.includes('ago')) {
        return timestamp;
    }

    // Try to parse as date
    const date = new Date(timestamp);

    // Check if date is invalid
    if (isNaN(date.getTime())) {
        return timestamp; // Return original if can't parse
    }

    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    const diffMonths = Math.floor(diffDays / 30);
    const diffYears = Math.floor(diffDays / 365);

    if (diffMins < 1) {
        return 'Just now';
    } else if (diffMins < 60) {
        return `${diffMins} min${diffMins !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
        return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 7) {
        return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 30) {
        const weeks = Math.floor(diffDays / 7);
        return `${weeks} week${weeks !== 1 ? 's' : ''} ago`;
    } else if (diffMonths < 12) {
        return `${diffMonths} month${diffMonths !== 1 ? 's' : ''} ago`;
    } else {
        return `${diffYears} year${diffYears !== 1 ? 's' : ''} ago`;
    }
}

/**
 * Load user's YouTube videos
 */
async function loadMyVideos() {
    const videosGrid = document.getElementById('myVideosGrid');
    const shortsSection = document.getElementById('myShortsSection');
    const shortsGrid = document.getElementById('myShortsGrid');
    const emptyState = document.getElementById('emptyVideos');

    try {
        // Show loading state
        videosGrid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 2rem;"><div style="font-size: 2rem; color: #3B82F6; margin-bottom: 0.5rem;"><i class="ph ph-spinner" style="animation: spin 1s linear infinite; display: inline-block;"></i></div><p style="color: var(--text-tertiary); margin: 0;">Loading your videos...</p></div>';
        emptyState.style.display = 'none';
        shortsSection.style.display = 'none';

        // Fetch videos and optimization history in parallel (with cache busting)
        const timestamp = Date.now();
        const [videosResponse, historyResponse] = await Promise.all([
            fetch(`/optimize-video/api/get-my-videos?_t=${timestamp}`),
            fetch(`/optimize-video/api/optimization-history?_t=${timestamp}`)
        ]);

        const videosData = await videosResponse.json();
        const historyData = await historyResponse.json();

        if (!videosData.success) {
            throw new Error(videosData.error || 'Failed to load videos');
        }

        const allVideos = videosData.videos || [];
        const history = historyData.history || [];

        // Check if YouTube is connected (has videos or channel name)
        hasYouTubeConnected = allVideos.length > 0 || videosData.channel_name;
        updateToggleButtonsVisibility();

        // Create a set of optimized video IDs for quick lookup
        const optimizedVideoIds = new Set(history.map(h => h.video_id));

        // Debug: Log optimization data for public videos
        console.log('[PUBLIC] Optimization history count:', history.length);
        console.log('[PUBLIC] Optimized video IDs:', Array.from(optimizedVideoIds));
        console.log('[PUBLIC] Total videos fetched:', allVideos.length);
        if (allVideos.length > 0) {
            console.log('[PUBLIC] First video ID:', allVideos[0].video_id);
            console.log('[PUBLIC] Is first video optimized?', optimizedVideoIds.has(allVideos[0].video_id));
        }

        // Separate videos and shorts
        const allRegularVideos = allVideos.filter(v => !v.is_short);
        const allShorts = allVideos.filter(v => v.is_short);

        // Sort to show optimized videos first
        const sortByOptimized = (videos) => {
            return videos.sort((a, b) => {
                const aOptimized = optimizedVideoIds.has(a.video_id) ? 1 : 0;
                const bOptimized = optimizedVideoIds.has(b.video_id) ? 1 : 0;
                return bOptimized - aOptimized; // Optimized first
            });
        };

        // Sort and limit to 8 each
        const regularVideos = sortByOptimized(allRegularVideos).slice(0, 8);
        const shorts = sortByOptimized(allShorts).slice(0, 8);

        // Helper function to create video card HTML
        const createVideoCard = (video, isPrivate = false) => {
            const isOptimized = optimizedVideoIds.has(video.video_id);
            const thumbnailUrl = video.thumbnail || `https://i.ytimg.com/vi/${video.video_id}/maxresdefault.jpg`;

            // Build menu items based on video privacy status
            const menuItems = `
                ${!isOptimized ? `
                <button class="menu-item" onclick="optimizeVideoFromMenu(event, '${video.video_id}')">
                    <i class="ph ph-magic-wand"></i>
                    Optimize Video
                </button>
                ` : ''}
                <button class="menu-item" onclick="uploadThumbnail(event, '${video.video_id}')">
                    <i class="ph ph-image"></i>
                    Change Thumbnail
                </button>
                ${isPrivate ? `
                <button class="menu-item" onclick="setVideoPublic(event, '${video.video_id}')">
                    <i class="ph ph-globe"></i>
                    Set to Public
                </button>
                ` : `
                <button class="menu-item" onclick="setVideoPrivate(event, '${video.video_id}')">
                    <i class="ph ph-lock-key"></i>
                    Set to Private
                </button>
                `}
                <button class="menu-item menu-item-danger" onclick="deleteVideo(event, '${video.video_id}')">
                    <i class="ph ph-trash"></i>
                    Delete Video
                </button>
            `;

            return `
                <div class="video-card ${isOptimized ? 'optimized' : ''}" data-video-id="${video.video_id}">
                    <div class="video-thumbnail" onclick="handleVideoClick('${video.video_id}', ${isOptimized})">
                        <img src="${thumbnailUrl}" alt="${escapeHtml(video.title)}" loading="lazy" onerror="this.onerror=null; this.src='https://i.ytimg.com/vi/${video.video_id}/hqdefault.jpg'">
                        ${isOptimized ? '<span class="optimized-badge"><i class="ph ph-check-circle"></i></span>' : ''}
                        ${video.is_short ? '<span class="short-badge"><i class="ph ph-device-mobile"></i> Short</span>' : ''}
                    </div>
                    <div class="video-info" onclick="handleVideoClick('${video.video_id}', ${isOptimized})">
                        <h4 class="video-title">${escapeHtml(video.title)}</h4>
                        <div class="video-meta">
                            <span class="stat">
                                <i class="ph ph-eye"></i>
                                ${video.view_count}
                            </span>
                            ${!video.is_short ? `<span class="stat"><i class="ph ph-clock"></i> ${formatTimestamp(video.published_time)}</span>` : ''}
                        </div>
                    </div>
                    <div class="video-card-menu">
                        <button class="video-menu-btn" onclick="toggleVideoMenu(event, '${video.video_id}')" title="More options">
                            <i class="ph ph-dots-three-vertical"></i>
                        </button>
                        <div class="video-menu-dropdown" id="menu-${video.video_id}">
                            ${menuItems}
                        </div>
                    </div>
                </div>
            `;
        };

        // Render regular videos
        if (regularVideos.length === 0) {
            videosGrid.innerHTML = '';
            emptyState.style.display = 'flex';
        } else {
            videosGrid.innerHTML = regularVideos.map(createVideoCard).join('');
            emptyState.style.display = 'none';
        }

        // Render shorts if any exist
        if (shorts.length > 0) {
            shortsSection.style.display = 'block';
            shortsGrid.innerHTML = shorts.map(createVideoCard).join('');
        }

    } catch (error) {
        console.error('Error loading videos:', error);
        videosGrid.innerHTML = '';

        // Check if error is about missing YouTube connection
        const isNoChannelError = error.message.includes('No YouTube channel') ||
                                 error.message.includes('not connected') ||
                                 error.message.includes('channel connected');

        if (isNoChannelError) {
            emptyState.innerHTML = `
                <i class="ph ph-youtube-logo"></i>
                <p>No YouTube Channel Connected</p>
                <span>Connect your YouTube account in Social Accounts or <strong>use the URL option above</strong> to optimize any video</span>
            `;
        } else {
            emptyState.innerHTML = `
                <i class="ph ph-warning"></i>
                <p>Failed to load videos</p>
                <span>${escapeHtml(error.message)}</span>
            `;
        }
        emptyState.style.display = 'flex';
    }
}

/**
 * Update toggle buttons visibility based on YouTube connection
 */
function updateToggleButtonsVisibility() {
    const publicToggle = document.getElementById('publicToggleBtn');
    const privateToggle = document.getElementById('privateToggleBtn');
    const urlToggle = document.getElementById('urlToggleBtn');
    const sectionHeader = document.querySelector('.section-header');

    if (!hasYouTubeConnected) {
        // Hide public and private toggles, show only URL
        if (publicToggle) publicToggle.style.display = 'none';
        if (privateToggle) privateToggle.style.display = 'none';

        // Auto-switch to URL mode if not already
        if (currentInputMode !== 'url') {
            currentInputMode = 'url';
            switchInputMode('url');
        }

        // Add banner if it doesn't exist
        if (!document.getElementById('youtubeConnectBanner')) {
            const banner = document.createElement('div');
            banner.id = 'youtubeConnectBanner';
            banner.className = 'youtube-connect-banner';
            banner.innerHTML = `
                <div class="banner-content">
                    <i class="ph ph-youtube-logo"></i>
                    <div class="banner-text">
                        <strong>Connect your YouTube account</strong>
                        <span>Get access to all features including public and private video optimization</span>
                    </div>
                    <a href="/accounts/social-accounts" class="banner-btn">
                        <i class="ph ph-link"></i>
                        Connect YouTube
                    </a>
                </div>
            `;
            sectionHeader.insertAdjacentElement('afterend', banner);
        }
    } else {
        // Show all toggles
        if (publicToggle) publicToggle.style.display = 'flex';
        if (privateToggle) privateToggle.style.display = 'flex';

        // Remove banner if it exists
        const banner = document.getElementById('youtubeConnectBanner');
        if (banner) banner.remove();
    }
}

/**
 * Handle video card click - optimize if not optimized, show results if already optimized
 */
async function handleVideoClick(videoId, isOptimized) {
    if (isOptimized) {
        // Video already optimized, load and show results directly
        await showOptimizationResults(videoId);
    } else {
        // Video not optimized, start optimization
        await optimizeVideo(videoId);
    }
}

/**
 * Optimize a specific video - Show selection screen first
 */
async function optimizeVideo(videoId) {
    try {
        // Store current video ID globally
        currentVideoId = videoId;

        // Fetch basic video info first
        const videoInfo = await fetchVideoInfo(videoId);

        if (!videoInfo) {
            throw new Error('Failed to fetch video information');
        }

        // Show selection screen
        showOptimizationSelection(videoId, videoInfo);

    } catch (error) {
        console.error('Error starting optimization:', error);
        alert(`Failed to start optimization: ${error.message}`);
    }
}

/**
 * Fetch video info without optimizing
 */
async function fetchVideoInfo(videoId) {
    try {
        const response = await fetch(`/optimize-video/api/video-info/${videoId}`);
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to fetch video info');
        }

        return data.data;
    } catch (error) {
        console.error('Error fetching video info:', error);
        return null;
    }
}

/**
 * Show optimization selection screen
 */
function showOptimizationSelection(videoId, videoInfo) {
    const selectionSection = document.getElementById('selectionSection');

    const html = `
        <div class="selection-header">
            <div class="selection-title-container">
                <h3 class="video-title-display">${escapeHtml(videoInfo.title || '')}</h3>
                <button class="back-btn" onclick="backToVideosFromSelection()">
                    <i class="ph ph-arrow-left"></i>
                    Back to Videos
                </button>
            </div>
        </div>

        <div class="selection-content">
            <div class="video-header-card result-card" style="margin-bottom: 2rem;">
                <div class="video-header-content">
                    <div class="video-thumbnail-wrapper">
                        <img src="${videoInfo.thumbnail || ''}" alt="Video thumbnail" class="video-thumbnail-img">
                    </div>
                    <div class="video-meta-info">
                        <h3 class="video-title-text">${escapeHtml(videoInfo.title || '')}</h3>
                        <div class="video-stats">
                            <span class="stat">
                                <i class="ph ph-eye"></i>
                                ${videoInfo.view_count || '0'} views
                            </span>
                            <span class="stat">
                                <i class="ph ph-clock"></i>
                                ${formatTimestamp(videoInfo.published_time)}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="selection-panel">
                <div class="selection-panel-header">
                    <h3 class="selection-panel-title">
                        <i class="ph ph-magic-wand"></i>
                        Select Optimizations to Generate
                    </h3>
                    <p class="selection-panel-subtitle">
                        Choose which aspects of your video you'd like to optimize. You'll be able to preview and edit everything before applying to YouTube.
                    </p>
                </div>

                <div class="optimization-grid">
                <div class="optimization-card selected" onclick="toggleOptimization(this, 'title')" data-optimization="title">
                    <div class="optimization-card-header">
                        <div class="optimization-checkbox">
                            <i class="ph-fill ph-check"></i>
                        </div>
                        <div class="optimization-icon">
                            <i class="ph ph-text-aa"></i>
                        </div>
                        <div class="optimization-info">
                            <div class="optimization-name">Title</div>
                            <div class="optimization-description">10 AI-generated title options optimized for SEO</div>
                        </div>
                    </div>
                </div>

                <div class="optimization-card selected" onclick="toggleOptimization(this, 'description')" data-optimization="description">
                    <div class="optimization-card-header">
                        <div class="optimization-checkbox">
                            <i class="ph-fill ph-check"></i>
                        </div>
                        <div class="optimization-icon">
                            <i class="ph ph-align-left"></i>
                        </div>
                        <div class="optimization-info">
                            <div class="optimization-name">Description</div>
                            <div class="optimization-description">SEO-optimized description (includes chapters for videos under 60 min)</div>
                        </div>
                    </div>
                </div>

                <div class="optimization-card selected" onclick="toggleOptimization(this, 'tags')" data-optimization="tags">
                    <div class="optimization-card-header">
                        <div class="optimization-checkbox">
                            <i class="ph-fill ph-check"></i>
                        </div>
                        <div class="optimization-icon">
                            <i class="ph ph-hash"></i>
                        </div>
                        <div class="optimization-info">
                            <div class="optimization-name">Tags</div>
                            <div class="optimization-description">Keyword-optimized tags for better discoverability</div>
                        </div>
                    </div>
                </div>

                <div class="optimization-card ${!hasYouTubeConnected ? 'disabled' : ''}" onclick="${!hasYouTubeConnected ? '' : 'toggleOptimization(this, \'captions\')'}" data-optimization="captions" ${!hasYouTubeConnected ? 'title="Requires YouTube account connection"' : ''}>
                    <div class="optimization-card-header">
                        <div class="optimization-checkbox">
                            <i class="ph-fill ph-check"></i>
                        </div>
                        <div class="optimization-icon">
                            <i class="ph ph-closed-captioning"></i>
                        </div>
                        <div class="optimization-info">
                            <div class="optimization-name">Captions ${!hasYouTubeConnected ? '<i class="ph ph-lock-simple" style="font-size: 0.875rem; margin-left: 0.25rem;"></i>' : ''}</div>
                            <div class="optimization-description">${!hasYouTubeConnected ? 'Requires YouTube account connection' : 'AI grammar & punctuation correction'}</div>
                        </div>
                    </div>
                </div>

                <div class="optimization-card ${!hasYouTubeConnected ? 'disabled' : ''}" onclick="${!hasYouTubeConnected ? '' : 'toggleOptimization(this, \'pinned_comment\')'}" data-optimization="pinned_comment" ${!hasYouTubeConnected ? 'title="Requires YouTube account connection"' : ''}>
                    <div class="optimization-card-header">
                        <div class="optimization-checkbox">
                            <i class="ph-fill ph-check"></i>
                        </div>
                        <div class="optimization-icon">
                            <i class="ph ph-push-pin"></i>
                        </div>
                        <div class="optimization-info">
                            <div class="optimization-name">Pinned Comment ${!hasYouTubeConnected ? '<i class="ph ph-lock-simple" style="font-size: 0.875rem; margin-left: 0.25rem;"></i>' : ''}</div>
                            <div class="optimization-description">${!hasYouTubeConnected ? 'Requires YouTube account connection' : 'Engagement-boosting pinned comment'}</div>
                        </div>
                    </div>
                </div>
                </div>

                <div class="selection-actions">
                <button class="selection-btn selection-btn-secondary" onclick="backToVideosFromSelection()">
                    <i class="ph ph-x"></i>
                    Cancel
                </button>
                <button class="selection-btn selection-btn-primary" onclick="runSelectedOptimizations('${videoId}')" id="runOptimizationsBtn">
                    <i class="ph ph-magic-wand"></i>
                    Generate Optimizations
                </button>
                </div>
            </div>
        </div>
    `;

    // Hide videos list, show selection section
    document.getElementById('videosListSection').style.display = 'none';
    document.getElementById('loadingSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    selectionSection.innerHTML = html;
    selectionSection.style.display = 'block';

    // Scroll to selection section
    setTimeout(() => {
        selectionSection.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }, 100);
}

/**
 * Toggle optimization selection
 */
function toggleOptimization(card, optimizationType) {
    card.classList.toggle('selected');
    updateOptimizationsButton();
}

/**
 * Update the "Generate Optimizations" button state
 */
function updateOptimizationsButton() {
    const selectedCards = document.querySelectorAll('.optimization-card.selected');
    const button = document.getElementById('runOptimizationsBtn');

    if (selectedCards.length === 0) {
        button.disabled = true;
        button.innerHTML = '<i class="ph ph-warning"></i> Select at least one optimization';
    } else {
        button.disabled = false;
        button.innerHTML = `<i class="ph ph-magic-wand"></i> Generate ${selectedCards.length} Optimization${selectedCards.length > 1 ? 's' : ''}`;
    }
}

/**
 * Back to videos from selection screen
 */
function backToVideosFromSelection() {
    document.getElementById('selectionSection').style.display = 'none';
    document.getElementById('videosListSection').style.display = 'block';

    // Re-apply the current input mode to ensure correct sections are displayed
    setTimeout(() => {
        switchInputMode(currentInputMode);
    }, 100);
}

/**
 * Run selected optimizations
 */
async function runSelectedOptimizations(videoId) {
    try {
        // Get selected optimizations
        const selectedCards = document.querySelectorAll('.optimization-card.selected');
        const selectedOptimizations = Array.from(selectedCards).map(card => card.dataset.optimization);

        if (selectedOptimizations.length === 0) {
            showToast('Please select at least one optimization');
            return;
        }

        // Store current video ID globally
        currentVideoId = videoId;

        // Mark as ongoing in sessionStorage
        sessionStorage.setItem('optimize_video_ongoing', JSON.stringify({
            videoId: videoId,
            startTime: Date.now()
        }));

        // Hide selection, show loading section
        document.getElementById('selectionSection').style.display = 'none';
        document.getElementById('loadingSection').style.display = 'block';
        document.getElementById('resultsSection').style.display = 'none';

        const response = await fetch(`/optimize-video/api/optimize/${videoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selected_optimizations: selectedOptimizations
            })
        });

        const data = await response.json();

        console.log('Optimization complete:', data);
        console.log('Title suggestions received:', data.data?.title_suggestions);

        if (!data.success) {
            // Clear ongoing optimization flag
            sessionStorage.removeItem('optimize_video_ongoing');

            // Check for insufficient credits
            if (data.error_type === 'insufficient_credits') {
                document.getElementById('loadingSection').style.display = 'none';
                document.getElementById('resultsSection').style.display = 'block';
                document.getElementById('resultsSection').innerHTML = `
                    <div class="insufficient-credits-card" style="max-width: 500px; margin: 3rem auto;">
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
                return;
            }

            // Check for transcript unavailable
            if (data.error_type === 'transcript_unavailable') {
                document.getElementById('loadingSection').style.display = 'none';
                document.getElementById('resultsSection').style.display = 'block';
                document.getElementById('resultsSection').innerHTML = `
                    <div class="transcript-unavailable-card" style="max-width: 600px; margin: 3rem auto;">
                        <div class="error-icon-wrapper" style="width: 80px; height: 80px; background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%); border-radius: 20px; display: flex; align-items: center; justify-content: center; margin: 0 auto 2rem;">
                            <i class="ph ph-clock-countdown" style="font-size: 2.5rem; color: #F59E0B;"></i>
                        </div>
                        <h3 style="color: var(--text-primary); margin-bottom: 0.5rem; font-size: 1.5rem; font-weight: 700; text-align: center;">Transcript Not Available Yet</h3>
                        <p style="color: var(--text-secondary); margin-bottom: 1.5rem; text-align: center; line-height: 1.6;">
                            ${escapeHtml(data.message || 'YouTube typically generates transcripts 15-30 minutes after upload. Please try again later.')}
                        </p>
                        <div style="display: flex; gap: 1rem; justify-content: center;">
                            <button onclick="backToVideos()" class="selection-btn selection-btn-secondary">
                                <i class="ph ph-arrow-left"></i>
                                Back to Videos
                            </button>
                            <button onclick="runSelectedOptimizations('${currentVideoId}')" class="selection-btn selection-btn-primary">
                                <i class="ph ph-arrow-clockwise"></i>
                                Try Again
                            </button>
                        </div>
                    </div>
                `;
                return;
            }

            throw new Error(data.error || 'Optimization failed');
        }

        if (!data.data) {
            throw new Error('No optimization data received from server');
        }

        // Clear ongoing optimization flag - optimization complete!
        sessionStorage.removeItem('optimize_video_ongoing');

        // Display results immediately
        console.log('Displaying results with titles:', data.data.title_suggestions);
        displayOptimizationResults(data.data);
        document.getElementById('loadingSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'block';

        // Scroll to results
        setTimeout(() => {
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) {
                resultsSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        }, 100);

    } catch (error) {
        console.error('Error optimizing video:', error);
        document.getElementById('loadingSection').style.display = 'none';
        document.getElementById('videosListSection').style.display = 'block';
        alert(`Failed to optimize video: ${error.message}`);
    }
}

/**
 * Display optimization results
 */
function displayOptimizationResults(data) {
    // Store current optimization data globally to prevent loss when generating additional optimizations
    currentOptimizationData = data;

    const resultsSection = document.getElementById('resultsSection');
    const videoInfo = data.video_info || {};
    const recommendations = data.recommendations || {};
    const titleSuggestions = data.title_suggestions || [data.optimized_title];

    // Determine which optimizations were generated (have data)
    const hasTitle = titleSuggestions && titleSuggestions.length > 0 && titleSuggestions[0];
    const hasDescription = data.optimized_description && data.optimized_description.trim().length > 0;
    // Only show tags if they were actually generated (not just current tags)
    const hasTags = data.optimized_tags && data.optimized_tags.length > 0 &&
                   JSON.stringify(data.optimized_tags) !== JSON.stringify(data.current_tags);
    const hasCaptions = data.corrected_captions && data.corrected_captions.corrected_srt;
    const hasPinnedComment = data.pinned_comment && data.pinned_comment.comment_text;

    const html = `
        <div class="results-header">
            <div class="results-title-container">
                <h3 class="video-title-display">${escapeHtml(videoInfo.title || data.current_title || '')}</h3>
                <button class="back-btn" onclick="backToVideos()">
                    <i class="ph ph-arrow-left"></i>
                    Back to Videos
                </button>
            </div>
        </div>

        <div class="results-content">
            <!-- Video Info Card -->
            <div class="result-card video-header-card">
                <div class="video-header-content">
                    <div class="video-thumbnail-wrapper">
                        <img src="${videoInfo.thumbnail || ''}" alt="Video thumbnail" class="video-thumbnail-img">
                    </div>
                    <div class="video-meta-info">
                        <h3 class="video-title-text">${escapeHtml(videoInfo.title || data.current_title || '')}</h3>
                        <div class="video-stats">
                            <span class="stat">
                                <i class="ph ph-eye"></i>
                                ${videoInfo.view_count || '0'} views
                            </span>
                            <span class="stat">
                                <i class="ph ph-clock"></i>
                                ${formatTimestamp(videoInfo.published_time)}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            ${hasTitle ? `
            <!-- Title Suggestions -->
            <div class="result-card">
                <div class="section-header">
                    <h3 class="section-title" style="margin: 0; padding: 0; border: none;">
                        <i class="ph ph-text-aa"></i>
                        Title Suggestions
                    </h3>
                    <button class="refresh-titles-btn" onclick="refreshTitles()" id="refreshTitlesBtn">
                        <i class="ph ph-arrows-clockwise"></i>
                        <span>Refresh</span>
                    </button>
                </div>
                <div class="comparison-box current-box">
                    <div class="comparison-label">Current Title</div>
                    <div class="comparison-value">${escapeHtml(data.current_title || videoInfo.title || '')}</div>
                </div>
                <div class="suggestions-list" id="titleSuggestionsList">
                    ${titleSuggestions.map((title, index) => `
                        <div class="suggestion-item" data-index="${index}">
                            <div class="suggestion-number">${index + 1}</div>
                            <div class="suggestion-text" contenteditable="false">${escapeHtml(title)}</div>
                            <button class="edit-btn" onclick="toggleEditTitle(this, ${index})" title="Edit">
                                <i class="ph ph-pencil-simple"></i>
                            </button>
                            <button class="apply-btn-icon" onclick="applyTitleFromElement(this)" title="Apply to YouTube">
                                <i class="ph ph-youtube-logo"></i>
                            </button>
                            <button class="copy-btn" onclick="copyTitleFromElement(this)">
                                <i class="ph ph-copy"></i>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}

            ${hasDescription ? `
            <!-- Description Optimization -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-align-left"></i>
                    Description Optimization
                </h3>
                <div class="comparison-box current-box">
                    <div class="comparison-label">Current Description</div>
                    <div class="comparison-value description-text">${escapeHtml(data.current_description || '')}</div>
                </div>
                <div class="comparison-box optimized-box">
                    <div class="comparison-label">
                        Optimized Description
                        <div class="action-btns">
                            <button class="edit-btn" onclick="toggleEditDescription(this)" title="Edit">
                                <i class="ph ph-pencil-simple"></i>
                            </button>
                            <button class="apply-btn-icon" onclick="applyDescription(this)" title="Apply to YouTube">
                                <i class="ph ph-youtube-logo"></i>
                            </button>
                            <button class="copy-btn-small" onclick="copyDescription(this)">
                                <i class="ph ph-copy"></i>
                                Copy
                            </button>
                        </div>
                    </div>
                    <textarea class="comparison-value description-text" id="optimizedDescription" readonly>${escapeHtml(data.optimized_description || '')}</textarea>
                </div>
            </div>
            ` : ''}

            ${hasTags ? `
            <!-- Tags Optimization -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-hash"></i>
                    Tags Optimization
                </h3>
                <div class="tags-container">
                    <div class="tags-section">
                        <div class="tags-label">Current Tags</div>
                        <div class="tags-list">
                            ${(data.current_tags || []).map(tag => `<span class="tag tag-current">${escapeHtml(tag)}</span>`).join('')}
                        </div>
                    </div>
                    <div class="tags-section">
                        <div class="tags-label">
                            Optimized Tags
                            <div class="action-btns">
                                <button class="apply-btn-icon" onclick="applyTags(this)" title="Apply to YouTube">
                                    <i class="ph ph-youtube-logo"></i>
                                </button>
                                <button class="copy-btn-small" onclick="copyAllTags(this)">
                                    <i class="ph ph-copy"></i>
                                    Copy All
                                </button>
                            </div>
                        </div>
                        <div class="tags-editor" id="tagsEditor">
                            <div class="tags-list-editable" id="optimizedTagsList">
                                ${(data.optimized_tags || []).map((tag, index) => `
                                    <span class="tag tag-editable">
                                        ${escapeHtml(tag)}
                                        <button class="tag-delete-btn" onclick="deleteTag(${index})" title="Remove tag">
                                            <i class="ph ph-x"></i>
                                        </button>
                                    </span>
                                `).join('')}
                            </div>
                            <div class="tag-input-wrapper">
                                <input type="text" class="tag-input" id="tagInput" placeholder="Type tag and press Enter to add..." />
                            </div>
                            <div class="char-count-section">
                                <div class="char-count-header">
                                    <span class="char-count-label">Character Usage</span>
                                    <span class="char-count-value" id="charCountValue">0 / 500</span>
                                </div>
                                <div class="char-count-progress">
                                    <div class="char-count-fill" id="charCountFill" style="width: 0%"></div>
                                </div>
                                <div class="char-count-info">
                                    <span class="tag-count">Tags: <strong id="tagCountValue">0</strong></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            ` : ''}

            ${(!hasTitle || !hasDescription || !hasTags) ? `
            <!-- Generate Missing Optimizations -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-plus-circle"></i>
                    Generate Additional Optimizations
                </h3>
                <div class="advanced-actions-grid">
                    ${!hasTitle ? `
                    <button class="advanced-action-btn" onclick="generateMissingOptimization('title')">
                        <i class="ph ph-text-aa"></i>
                        <div class="action-info">
                            <div class="action-title">Title Suggestions</div>
                            <div class="action-desc">Generate 10 optimized titles</div>
                        </div>
                    </button>
                    ` : ''}
                    ${!hasDescription ? `
                    <button class="advanced-action-btn" onclick="generateMissingOptimization('description')">
                        <i class="ph ph-align-left"></i>
                        <div class="action-info">
                            <div class="action-title">Description</div>
                            <div class="action-desc">SEO-optimized description with chapters</div>
                        </div>
                    </button>
                    ` : ''}
                    ${!hasTags ? `
                    <button class="advanced-action-btn" onclick="generateMissingOptimization('tags')">
                        <i class="ph ph-hash"></i>
                        <div class="action-info">
                            <div class="action-title">Tags</div>
                            <div class="action-desc">Keyword-optimized tags for discovery</div>
                        </div>
                    </button>
                    ` : ''}
                </div>
            </div>
            ` : ''}

            ${(hasCaptions || hasPinnedComment) ? `
            <!-- Generated Advanced Optimizations -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-sparkle"></i>
                    Advanced Optimizations
                </h3>
                ${hasCaptions ? `
                <div class="advanced-result-box">
                    <div class="captions-header">
                        <h4><i class="ph ph-subtitles"></i> Corrected Captions</h4>
                        <div class="captions-controls">
                            <div class="toggle-view-btns">
                                <button class="toggle-view-btn active" onclick="toggleCaptionsView('diff')" id="diffViewBtn">
                                    <i class="ph ph-git-diff"></i>
                                    Diff View
                                </button>
                                <button class="toggle-view-btn" onclick="toggleCaptionsView('corrected')" id="correctedViewBtn">
                                    <i class="ph ph-file-text"></i>
                                    Corrected Only
                                </button>
                            </div>
                            <button class="edit-btn" onclick="toggleEditCaptions(this)" title="Edit" id="editCaptionsBtn">
                                <i class="ph ph-pencil-simple"></i>
                            </button>
                        </div>
                    </div>
                    <div id="captionsDiffView" class="captions-diff-view">
                        ${generateCaptionsDiff(data.corrected_captions.original_srt || '', data.corrected_captions.corrected_srt || '')}
                    </div>
                    <textarea class="caption-preview" id="captionsTextarea" style="display: none;">${escapeHtml(data.corrected_captions.corrected_srt || '')}</textarea>
                    <button class="apply-btn" onclick="applyCaptions()">
                        <i class="ph ph-youtube-logo"></i>
                        Apply to YouTube
                    </button>
                </div>
                ` : ''}
                ${hasPinnedComment ? `
                <div class="advanced-result-box">
                    <div class="captions-header">
                        <h4><i class="ph ph-chat-circle"></i> Pinned Comment</h4>
                        <button class="edit-btn" onclick="toggleEditPinnedComment(this)" title="Edit" id="editPinnedCommentBtn">
                            <i class="ph ph-pencil-simple"></i>
                        </button>
                    </div>
                    <textarea class="comment-preview" id="pinnedCommentPreview" readonly>${escapeHtml(data.pinned_comment.comment_text || '')}</textarea>
                    <button class="apply-btn" onclick="applyPinnedComment()">
                        <i class="ph ph-youtube-logo"></i>
                        Post to YouTube
                    </button>
                </div>
                ` : ''}
            </div>
            ` : ''}

            ${(!hasCaptions || !hasPinnedComment) ? `
            <!-- Advanced Optimizations Actions -->
            <div class="result-card">
                <h3 class="section-title">
                    <i class="ph ph-sparkle"></i>
                    Advanced Optimizations
                </h3>
                <div class="advanced-actions-grid">
                    ${!hasCaptions ? `
                    <button class="advanced-action-btn" onclick="correctCaptions()" id="correctCaptionsBtn">
                        <i class="ph ph-subtitles"></i>
                        <div class="action-info">
                            <div class="action-title">Correct Captions</div>
                            <div class="action-desc">Fix grammar & remove filler words</div>
                        </div>
                    </button>
                    ` : ''}
                    ${!hasPinnedComment ? `
                    <button class="advanced-action-btn" onclick="postPinnedComment()" id="postPinnedCommentBtn">
                        <i class="ph ph-chat-circle"></i>
                        <div class="action-info">
                            <div class="action-title">Post Pinned Comment</div>
                            <div class="action-desc">Boost engagement with AI comment</div>
                        </div>
                    </button>
                    ` : ''}
                </div>
                <div id="advancedOptimizationResult" class="advanced-result" style="display: none;"></div>
            </div>
            ` : ''}
        </div>
    `;

    resultsSection.innerHTML = html;

    // Store optimized data globally for copying
    window.optimizedTags = data.optimized_tags || [];
    currentOptimizedDescription = data.optimized_description || '';

    // Setup tag input listener
    setupTagInput();

    // Auto-resize description textarea to fit content
    autoResizeDescriptionTextarea();

    // Initialize character count
    updateCharacterCount();
}

/**
 * Generate missing optimization (title, description, or tags)
 */
async function generateMissingOptimization(type) {
    // Find the button that was clicked using event.target
    const clickedButton = event ? event.currentTarget : null;

    try {
        // Disable button and add spinner
        if (clickedButton) {
            clickedButton.disabled = true;
            const icon = clickedButton.querySelector('i');
            if (icon) {
                icon.className = 'ph ph-spinner spin';
            }
        }

        showToast(`Generating ${type}...`);

        const response = await fetch(`/optimize-video/api/optimize/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selected_optimizations: [type]
            })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || `Failed to generate ${type}`);
        }

        // Merge new data with existing data to prevent losing previously generated optimizations
        const mergedData = {
            ...currentOptimizationData, // Existing data
            ...data.data,              // New data (overwrites matching keys)
            // Preserve video_info from existing if not in new data
            video_info: data.data.video_info || currentOptimizationData?.video_info || {}
        };

        // Display merged results
        showToast(`✅ ${type.charAt(0).toUpperCase() + type.slice(1)} generated!`);
        displayOptimizationResults(mergedData);

    } catch (error) {
        console.error(`Error generating ${type}:`, error);
        showToast(`❌ Failed to generate ${type}`);

        // Re-enable button on error
        if (clickedButton) {
            clickedButton.disabled = false;
            const icon = clickedButton.querySelector('i');
            if (icon) {
                icon.classList.remove('spin');
                // Restore original icon based on type
                if (type === 'title') icon.className = 'ph ph-text-aa';
                else if (type === 'description') icon.className = 'ph ph-align-left';
                else if (type === 'tags') icon.className = 'ph ph-hash';
            }
        }
    }
}

/**
 * Apply captions to YouTube
 */
async function applyCaptions() {
    try {
        const captionPreview = document.getElementById('captionsTextarea');
        const correctedSrt = captionPreview ? captionPreview.value : null;

        if (!correctedSrt) {
            showToast('❌ No caption data available');
            return;
        }

        showToast('Uploading captions to YouTube...');

        const response = await fetch(`/optimize-video/api/apply-captions/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                corrected_srt: correctedSrt
            })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to apply captions');
        }

        showToast('✅ Captions uploaded to YouTube!');

    } catch (error) {
        console.error('Error applying captions:', error);
        showToast(`❌ ${error.message}`);
    }
}

/**
 * Apply pinned comment to YouTube
 */
async function applyPinnedComment() {
    try {
        const commentPreview = document.getElementById('pinnedCommentPreview');
        const commentText = commentPreview ? commentPreview.value : null;

        if (!commentText) {
            showToast('❌ No comment text available');
            return;
        }

        showToast('Posting comment to YouTube...');

        const response = await fetch(`/optimize-video/api/apply-pinned-comment/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                comment_text: commentText
            })
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to post comment');
        }

        showToast('✅ Comment posted to YouTube! Remember to pin it in YouTube Studio.');

    } catch (error) {
        console.error('Error posting comment:', error);
        showToast(`❌ ${error.message}`);
    }
}

/**
 * Back to videos list
 */
async function backToVideos() {
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('videosListSection').style.display = 'block';

    // Small delay to ensure Firestore has finished writing optimization data
    await new Promise(resolve => setTimeout(resolve, 500));

    // Always reload videos to get fresh optimization status (to show checkmarks)
    if (currentInputMode === 'private') {
        await loadPrivateVideos();
    } else if (currentInputMode === 'public') {
        await loadMyVideos();
    }

    // Re-apply the current input mode to ensure correct sections are displayed
    setTimeout(() => {
        switchInputMode(currentInputMode);
    }, 200);
}

/**
 * Show existing optimization results
 */
async function showOptimizationResults(videoId) {
    try {
        // Store current video ID globally
        currentVideoId = videoId;

        // Hide videos list, show loading briefly
        document.getElementById('videosListSection').style.display = 'none';
        document.getElementById('loadingSection').style.display = 'block';
        document.getElementById('resultsSection').style.display = 'none';

        // Fetch the cached optimization
        const response = await fetch(`/optimize-video/api/optimize/${videoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                selected_optimizations: []  // Empty array to just retrieve cached data
            })
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch optimization: ${response.status}`);
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Failed to load optimization');
        }

        // Hide loading, show results
        document.getElementById('loadingSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'block';

        // Display the results
        displayOptimizationResults(result.data);

        // Scroll to results
        setTimeout(() => {
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection) {
                resultsSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        }, 100);

    } catch (error) {
        console.error('Error showing results:', error);
        document.getElementById('loadingSection').style.display = 'none';
        document.getElementById('videosListSection').style.display = 'block';
        alert('Failed to load optimization results');
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format markdown-like text to HTML
 */
function formatMarkdown(text) {
    if (!text) return '';

    // Escape HTML first
    let formatted = escapeHtml(text);

    // Convert **bold** to <strong>
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Convert *italic* to <em>
    formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Convert line breaks to <br>
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

/**
 * Parse SRT content into structured segments
 */
function parseSRT(srtContent) {
    if (!srtContent) return [];

    const segments = [];
    const blocks = srtContent.trim().split('\n\n');

    for (const block of blocks) {
        const lines = block.trim().split('\n');
        if (lines.length >= 3) {
            const index = lines[0];
            const timestamp = lines[1];
            const text = lines.slice(2).join(' ');

            segments.push({
                index,
                timestamp,
                text: text.trim()
            });
        }
    }

    return segments;
}

/**
 * Simple diff algorithm to highlight changes between two strings
 */
function highlightDiff(original, corrected) {
    const originalWords = original.split(/\s+/);
    const correctedWords = corrected.split(/\s+/);

    let result = '';
    let i = 0, j = 0;

    while (i < correctedWords.length) {
        if (i < originalWords.length && originalWords[i] === correctedWords[i]) {
            // No change
            result += correctedWords[i] + ' ';
            i++;
            j++;
        } else {
            // Changed/added word
            result += `<span class="diff-changed">${correctedWords[i]}</span> `;
            i++;
        }
    }

    return result.trim();
}

/**
 * Generate captions diff view HTML
 */
function generateCaptionsDiff(originalSRT, correctedSRT) {
    const originalSegments = parseSRT(originalSRT);
    const correctedSegments = parseSRT(correctedSRT);

    if (originalSegments.length === 0 || correctedSegments.length === 0) {
        return '<div class="diff-empty">No captions to compare</div>';
    }

    let html = '<div class="diff-container">';

    // Show side-by-side comparison for first 20 segments as preview
    const previewCount = Math.min(20, Math.min(originalSegments.length, correctedSegments.length));

    for (let i = 0; i < previewCount; i++) {
        const original = originalSegments[i];
        const corrected = correctedSegments[i];

        // Check if text changed
        const hasChange = original.text !== corrected.text;

        html += `
            <div class="diff-row ${hasChange ? 'has-change' : ''}">
                <div class="diff-timestamp">${escapeHtml(corrected.timestamp)}</div>
                <div class="diff-comparison">
                    <div class="diff-original">
                        <div class="diff-label">Original</div>
                        <div class="diff-text">${escapeHtml(original.text)}</div>
                    </div>
                    <div class="diff-corrected">
                        <div class="diff-label">Corrected</div>
                        <div class="diff-text">${hasChange ? highlightDiff(original.text, corrected.text) : escapeHtml(corrected.text)}</div>
                    </div>
                </div>
            </div>
        `;
    }

    if (correctedSegments.length > previewCount) {
        html += `<div class="diff-more">... and ${correctedSegments.length - previewCount} more segments</div>`;
    }

    html += '</div>';
    return html;
}

/**
 * Toggle between diff view and corrected-only view for captions
 */
function toggleCaptionsView(view) {
    const diffView = document.getElementById('captionsDiffView');
    const textarea = document.getElementById('captionsTextarea');
    const diffBtn = document.getElementById('diffViewBtn');
    const correctedBtn = document.getElementById('correctedViewBtn');

    if (view === 'diff') {
        diffView.style.display = 'block';
        textarea.style.display = 'none';
        diffBtn.classList.add('active');
        correctedBtn.classList.remove('active');
    } else {
        diffView.style.display = 'none';
        textarea.style.display = 'block';
        textarea.readOnly = true;
        diffBtn.classList.remove('active');
        correctedBtn.classList.add('active');
    }
}

/**
 * Toggle edit mode for captions
 */
function toggleEditCaptions(button) {
    const textarea = document.getElementById('captionsTextarea');
    const icon = button.querySelector('i');

    // Switch to corrected view if in diff view
    toggleCaptionsView('corrected');

    if (textarea.readOnly) {
        textarea.readOnly = false;
        textarea.focus();
        icon.className = 'ph ph-check';
        button.title = 'Save';
        button.classList.add('editing');
    } else {
        textarea.readOnly = true;
        icon.className = 'ph ph-pencil-simple';
        button.title = 'Edit';
        button.classList.remove('editing');
        showToast('✓ Changes saved');
    }
}

/**
 * Toggle edit mode for pinned comment
 */
function toggleEditPinnedComment(button) {
    const textarea = document.getElementById('pinnedCommentPreview');
    const icon = button.querySelector('i');

    if (textarea.readOnly) {
        textarea.readOnly = false;
        textarea.focus();
        icon.className = 'ph ph-check';
        button.title = 'Save';
        button.classList.add('editing');
    } else {
        textarea.readOnly = true;
        icon.className = 'ph ph-pencil-simple';
        button.title = 'Edit';
        button.classList.remove('editing');
        showToast('✓ Changes saved');
    }
}

/**
 * Show toast notification
 */
function showToast(message) {
    // Toast messages disabled per user request
    // All notifications now handled via modals or inline UI feedback
    return;
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(button, text) {
    navigator.clipboard.writeText(text).then(() => {
        const icon = button.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'ph ph-check';
        button.style.color = '#10B981';

        showToast('Copied to clipboard!');

        setTimeout(() => {
            icon.className = originalClass;
            button.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy');
    });
}

/**
 * Copy description to clipboard
 */
function copyDescription(button) {
    if (!currentOptimizedDescription) {
        showToast('No description to copy');
        return;
    }

    navigator.clipboard.writeText(currentOptimizedDescription).then(() => {
        const icon = button.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'ph ph-check';
        button.style.color = '#10B981';

        showToast('Description copied to clipboard!');

        setTimeout(() => {
            icon.className = originalClass;
            button.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Failed to copy description');
    });
}

/**
 * Copy all optimized tags
 */
function copyAllTags(button) {
    const tags = window.optimizedTags || [];
    if (tags.length === 0) {
        showToast('No tags to copy');
        return;
    }

    const tagsText = tags.join(', ');

    navigator.clipboard.writeText(tagsText).then(() => {
        const icon = button.querySelector('i');
        const originalClass = icon.className;
        icon.className = 'ph ph-check';
        button.style.color = '#10B981';

        showToast(`${tags.length} tags copied to clipboard!`);

        setTimeout(() => {
            icon.className = originalClass;
            button.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy tags:', err);
        showToast('Failed to copy tags');
    });
}

/**
 * Refresh title suggestions
 */
async function refreshTitles() {
    if (!currentVideoId) {
        alert('No video selected');
        return;
    }

    const refreshBtn = document.getElementById('refreshTitlesBtn');
    const icon = refreshBtn.querySelector('i');
    const span = refreshBtn.querySelector('span');

    try {
        // Show loading state
        refreshBtn.disabled = true;
        icon.className = 'ph ph-spinner spin';
        span.textContent = 'Refreshing...';

        const response = await fetch(`/optimize-video/api/refresh-titles/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        console.log('Refresh titles response:', data);

        if (!data.success) {
            throw new Error(data.error || 'Failed to refresh titles');
        }

        // Update the title suggestions list
        const titlesList = document.getElementById('titleSuggestionsList');
        if (!titlesList) {
            throw new Error('Title suggestions list element not found');
        }

        const newTitles = data.title_suggestions || [];
        console.log('New titles:', newTitles);

        if (newTitles.length === 0) {
            throw new Error('No titles received from server');
        }

        titlesList.innerHTML = newTitles.map((title, index) => `
            <div class="suggestion-item">
                <div class="suggestion-number">${index + 1}</div>
                <div class="suggestion-text">${escapeHtml(title)}</div>
                <button class="apply-btn-icon" onclick="applyTitle(this, \`${escapeHtml(title).replace(/`/g, '\\`').replace(/'/g, "\\'")}\`)" title="Apply to YouTube">
                    <i class="ph ph-youtube-logo"></i>
                </button>
                <button class="copy-btn" onclick="copyToClipboard(this, \`${escapeHtml(title).replace(/`/g, '\\`')}\`)">
                    <i class="ph ph-copy"></i>
                </button>
            </div>
        `).join('');

        console.log('Titles updated in UI');

        // Show success feedback
        icon.className = 'ph ph-check';
        span.textContent = 'Refreshed!';

        setTimeout(() => {
            icon.className = 'ph ph-arrows-clockwise';
            span.textContent = 'Refresh';
            refreshBtn.disabled = false;
        }, 2000);

    } catch (error) {
        console.error('Error refreshing titles:', error);
        alert(`Failed to refresh titles: ${error.message}`);

        // Reset button state
        icon.className = 'ph ph-arrows-clockwise';
        span.textContent = 'Refresh';
        refreshBtn.disabled = false;
    }
}

/**
 * Show confirmation modal
 */
/**
 * Show error modal
 */
function showErrorModal(title, message) {
    // Remove existing modal if any
    const existingModal = document.querySelector('.confirm-modal-overlay');
    if (existingModal) {
        existingModal.remove();
    }

    // Create modal
    const modal = document.createElement('div');
    modal.className = 'confirm-modal-overlay';
    modal.innerHTML = `
        <div class="confirm-modal error-modal">
            <div class="confirm-modal-header error-header">
                <i class="ph ph-warning-circle"></i>
                <h3 class="confirm-modal-title">${escapeHtml(title)}</h3>
            </div>
            <div class="confirm-modal-content">${escapeHtml(message)}</div>
            <div class="confirm-modal-actions">
                <button class="confirm-modal-btn confirm-modal-btn-confirm">OK</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Show with animation
    setTimeout(() => modal.classList.add('show'), 10);

    // Handle OK button
    const okBtn = modal.querySelector('.confirm-modal-btn-confirm');
    okBtn.addEventListener('click', () => {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);
    });

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        }
    });
}

function showConfirmModal(title, message, onConfirm) {
    // Remove existing modal if any
    const existingModal = document.querySelector('.confirm-modal-overlay');
    if (existingModal) {
        existingModal.remove();
    }

    // Create modal
    const modal = document.createElement('div');
    modal.className = 'confirm-modal-overlay';
    modal.innerHTML = `
        <div class="confirm-modal">
            <div class="confirm-modal-header">
                <i class="ph ph-youtube-logo"></i>
                <h3 class="confirm-modal-title">${escapeHtml(title)}</h3>
            </div>
            <div class="confirm-modal-content">${escapeHtml(message)}</div>
            <div class="confirm-modal-actions">
                <button class="confirm-modal-btn confirm-modal-btn-cancel">Cancel</button>
                <button class="confirm-modal-btn confirm-modal-btn-confirm">Apply to YouTube</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    // Show with animation
    setTimeout(() => modal.classList.add('show'), 10);

    // Handle cancel
    const cancelBtn = modal.querySelector('.confirm-modal-btn-cancel');
    cancelBtn.onclick = () => {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 200);
    };

    // Handle confirm
    const confirmBtn = modal.querySelector('.confirm-modal-btn-confirm');
    confirmBtn.onclick = () => {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 200);
        onConfirm();
    };

    // Close on overlay click
    modal.onclick = (e) => {
        if (e.target === modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 200);
        }
    };
}

/**
 * Apply title to YouTube
 */
async function applyTitle(button, title) {
    if (!currentVideoId) {
        showToast('No video selected');
        return;
    }

    const icon = button.querySelector('i');
    const originalIconClass = icon.className;

    showConfirmModal('Apply Title', `Apply this title to YouTube?\n\n"${title}"`, async () => {
        try {
            button.disabled = true;
            icon.className = 'ph ph-spinner spin';

            const response = await fetch(`/optimize-video/api/apply-optimizations/${currentVideoId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title: title})
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to apply title');
            }

            icon.className = 'ph ph-check';
            button.style.background = '#10B981';
            button.style.color = '#fff';
            showToast('✅ Title updated on YouTube!');

            setTimeout(() => {
                button.disabled = true;
            }, 2000);

        } catch (error) {
            console.error('Error applying title:', error);
            showToast('❌ Failed to apply title: ' + error.message);
            icon.className = originalIconClass;
            button.disabled = false;
        }
    });
}

/**
 * Apply description to YouTube
 */
async function applyDescription(button) {
    if (!currentVideoId) {
        showToast('No video selected');
        return;
    }

    if (!currentOptimizedDescription) {
        showToast('No description to apply');
        return;
    }

    const icon = button.querySelector('i');
    const originalIconClass = icon.className;

    const preview = currentOptimizedDescription.length > 100
        ? currentOptimizedDescription.substring(0, 100) + '...'
        : currentOptimizedDescription;

    showConfirmModal('Apply Description', `Apply this description to YouTube?\n\n"${preview}"`, async () => {
        try {
            button.disabled = true;
            icon.className = 'ph ph-spinner spin';

            const response = await fetch(`/optimize-video/api/apply-optimizations/${currentVideoId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({description: currentOptimizedDescription})
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to apply description');
            }

            icon.className = 'ph ph-check';
            button.style.background = '#10B981';
            button.style.color = '#fff';
            showToast('✅ Description updated on YouTube!');

            setTimeout(() => {
                button.disabled = true;
            }, 2000);

        } catch (error) {
            console.error('Error applying description:', error);

            // Check for specific error types
            let errorMessage = error.message;
            if (errorMessage.includes('quota') || errorMessage.includes('Quota')) {
                showErrorModal('YouTube API Quota Exceeded',
                    'You have exceeded your daily YouTube API quota. The quota resets at midnight Pacific Time. Please try again tomorrow or consider upgrading your plan for higher limits.');
            } else if (errorMessage.includes('403') || errorMessage.includes('not own') || errorMessage.includes('permission')) {
                showErrorModal('Video Access Denied',
                    'You do not have permission to edit this video. Make sure you are the owner of this video and your YouTube account is properly connected.');
            } else {
                showToast('❌ Failed to apply description: ' + errorMessage);
            }

            icon.className = originalIconClass;
            button.disabled = false;
        }
    });
}

/**
 * Apply tags to YouTube
 */
async function applyTags(button) {
    if (!currentVideoId) {
        showToast('No video selected');
        return;
    }

    const tags = window.optimizedTags || [];
    if (tags.length === 0) {
        showToast('No tags to apply');
        return;
    }

    const icon = button.querySelector('i');
    const originalIconClass = icon.className;

    const preview = tags.slice(0, 5).join(', ') + (tags.length > 5 ? '...' : '');

    showConfirmModal('Apply Tags', `Apply ${tags.length} tags to YouTube?\n\n${preview}`, async () => {
        try {
            button.disabled = true;
            icon.className = 'ph ph-spinner spin';

            const response = await fetch(`/optimize-video/api/apply-optimizations/${currentVideoId}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tags: tags})
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to apply tags');
            }

            icon.className = 'ph ph-check';
            button.style.background = '#10B981';
            button.style.color = '#fff';
            showToast('✅ Tags updated on YouTube!');

            setTimeout(() => {
                button.disabled = true;
            }, 2000);

        } catch (error) {
            console.error('Error applying tags:', error);
            showToast('❌ Failed to apply tags: ' + error.message);
            icon.className = originalIconClass;
            button.disabled = false;
        }
    });
}

/**
 * Toggle edit mode for title
 */
function toggleEditTitle(button, index) {
    const item = button.closest('.suggestion-item');
    const textEl = item.querySelector('.suggestion-text');
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
        // Exit edit mode
        textEl.setAttribute('contenteditable', 'false');
        icon.className = 'ph ph-pencil-simple';
        button.title = 'Edit';
        textEl.style.outline = 'none';
        textEl.style.padding = '0';
    }
}

/**
 * Apply title from element (after possible editing)
 */
function applyTitleFromElement(button) {
    const item = button.closest('.suggestion-item');
    const textEl = item.querySelector('.suggestion-text');
    const title = textEl.textContent.trim();
    applyTitle(button, title);
}

/**
 * Copy title from element (after possible editing)
 */
function copyTitleFromElement(button) {
    const item = button.closest('.suggestion-item');
    const textEl = item.querySelector('.suggestion-text');
    const title = textEl.textContent.trim();
    copyToClipboard(button, title);
}

/**
 * Auto-resize description textarea to fit content
 */
function autoResizeDescriptionTextarea() {
    const textarea = document.getElementById('optimizedDescription');
    if (!textarea) return;

    // Use setTimeout to ensure DOM has rendered
    setTimeout(() => {
        // Remove overflow to get accurate scrollHeight
        textarea.style.overflow = 'hidden';

        // Reset height to auto to get the correct scrollHeight
        textarea.style.height = 'auto';
        // Set height to scrollHeight to fit all content (add small buffer for padding)
        textarea.style.height = (textarea.scrollHeight + 4) + 'px';

        console.log('Resized optimized description to:', textarea.scrollHeight + 4);
    }, 10);

    // Add input listener to resize on edit (only once)
    if (!textarea.dataset.resizeListenerAdded) {
        textarea.addEventListener('input', function() {
            this.style.overflow = 'hidden';
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight + 4) + 'px';
        });
        textarea.dataset.resizeListenerAdded = 'true';
    }
}

/**
 * Toggle edit mode for description
 */
function toggleEditDescription(button) {
    const textarea = document.getElementById('optimizedDescription');
    const icon = button.querySelector('i');

    if (textarea.hasAttribute('readonly')) {
        // Enter edit mode
        textarea.removeAttribute('readonly');
        textarea.focus();
        icon.className = 'ph ph-check';
        button.title = 'Save';
        textarea.style.outline = '2px solid #3B82F6';
    } else {
        // Exit edit mode
        textarea.setAttribute('readonly', 'true');
        icon.className = 'ph ph-pencil-simple';
        button.title = 'Edit';
        textarea.style.outline = 'none';

        // Update global variable with edited content
        currentOptimizedDescription = textarea.value;

        // Resize after editing
        autoResizeDescriptionTextarea();
    }
}

/**
 * Setup tag input listener for Enter key
 */
function setupTagInput() {
    const tagInput = document.getElementById('tagInput');
    if (!tagInput) return;

    tagInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const newTag = tagInput.value.trim();
            if (newTag) {
                addTag(newTag);
                tagInput.value = '';
            }
        }
    });
}

/**
 * Add a new tag
 */
function addTag(tagText) {
    if (!tagText || !tagText.trim()) return;

    // Add to global tags array
    if (!window.optimizedTags) {
        window.optimizedTags = [];
    }
    window.optimizedTags.push(tagText.trim());

    // Update display
    renderTags();
}

/**
 * Delete a tag
 */
function deleteTag(index) {
    if (!window.optimizedTags) return;

    // Remove from array
    window.optimizedTags.splice(index, 1);

    // Update display
    renderTags();
}

/**
 * Render tags in the editor
 */
function renderTags() {
    const tagsList = document.getElementById('optimizedTagsList');
    if (!tagsList) return;

    const tags = window.optimizedTags || [];
    tagsList.innerHTML = tags.map((tag, index) => `
        <span class="tag tag-editable">
            ${escapeHtml(tag)}
            <button class="tag-delete-btn" onclick="deleteTag(${index})" title="Remove tag">
                <i class="ph ph-x"></i>
            </button>
        </span>
    `).join('');

    // Update character count
    updateCharacterCount();
}

/**
 * Update character count display
 */
function updateCharacterCount() {
    const tags = window.optimizedTags || [];
    const tagCountEl = document.getElementById('tagCountValue');
    const charCountEl = document.getElementById('charCountValue');
    const charFillEl = document.getElementById('charCountFill');

    if (!tagCountEl || !charCountEl || !charFillEl) return;

    // Calculate total characters (tags + commas + spaces)
    const totalChars = tags.join(', ').length;
    const percentage = (totalChars / 500) * 100;

    // Update displays
    tagCountEl.textContent = tags.length;
    charCountEl.textContent = `${totalChars} / 500`;

    // Update progress bar
    charFillEl.style.width = `${Math.min(percentage, 100)}%`;

    // Update color based on usage
    charFillEl.className = 'char-count-fill';
    if (totalChars > 500) {
        charFillEl.classList.add('error');
        charCountEl.style.color = '#EF4444';
    } else if (totalChars > 450) {
        charFillEl.classList.add('warning');
        charCountEl.style.color = '#F59E0B';
    } else if (totalChars >= 400) {
        charFillEl.classList.add('good');
        charCountEl.style.color = '#10B981';
    } else {
        charCountEl.style.color = 'var(--text-secondary)';
    }
}

/**
 * Check if optimization is complete by polling the history
 */
async function checkOptimizationStatus(videoId) {
    const maxAttempts = 90; // Poll for up to 3 minutes (90 * 2 seconds)
    let attempts = 0;

    const pollInterval = setInterval(async () => {
        attempts++;

        try {
            // Check if the optimization exists in history
            const response = await fetch('/optimize-video/api/optimization-history');
            const data = await response.json();

            if (data.success && data.history) {
                const optimization = data.history.find(item => item.video_id === videoId);

                if (optimization) {
                    // Optimization complete! Clear sessionStorage and show results
                    console.log('Optimization complete for video:', videoId);
                    sessionStorage.removeItem('optimize_video_ongoing');
                    clearInterval(pollInterval);

                    // Load and display the optimization
                    showOptimizationResults(videoId);
                    return;
                }
            }

            // If max attempts reached, stop polling
            if (attempts >= maxAttempts) {
                console.log('Optimization polling timed out');
                sessionStorage.removeItem('optimize_video_ongoing');
                clearInterval(pollInterval);
                document.getElementById('optimizationResults').innerHTML = `
                    <div class="error-card">
                        <p>Optimization is taking longer than expected. Please try again.</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error checking optimization status:', error);
            // Continue polling even on error
        }
    }, 2000); // Poll every 2 seconds
}

/**
 * Load private/unlisted videos using YouTube API
 */
async function loadPrivateVideos(forceRefresh = false) {
    const privateVideosGrid = document.getElementById('privateVideosGrid');
    const privateShortsSection = document.getElementById('privateShortsSection');
    const privateShortsGrid = document.getElementById('privateShortsGrid');
    const noticeDiv = document.getElementById('privateVideosNotice');

    try {
        // Show loading in grid
        privateVideosGrid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 2rem;"><div style="font-size: 2rem; color: #3B82F6; margin-bottom: 0.5rem;"><i class="ph ph-spinner" style="animation: spin 1s linear infinite; display: inline-block;"></i></div><p style="color: var(--text-tertiary); margin: 0;">Fetching private videos from YouTube API...</p></div>';
        privateShortsSection.style.display = 'none';

        // Add timestamp for cache busting
        const timestamp = Date.now();
        const url = forceRefresh
            ? `/optimize-video/api/get-private-videos?refresh=true&_t=${timestamp}`
            : `/optimize-video/api/get-private-videos?_t=${timestamp}`;

        // Fetch videos and optimization history in parallel
        const [videosResponse, historyResponse] = await Promise.all([
            fetch(url),
            fetch(`/optimize-video/api/optimization-history?_t=${timestamp}`)
        ]);

        const data = await videosResponse.json();
        const historyData = await historyResponse.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to load private videos');
        }

        const allVideos = data.videos || [];
        const history = historyData.history || [];
        const fromCache = data.from_cache || false;

        // Create a set of optimized video IDs for quick lookup
        const optimizedVideoIds = new Set(history.map(h => h.video_id));

        // Split videos and shorts
        const regularVideos = allVideos.filter(v => !v.is_short);
        const shorts = allVideos.filter(v => v.is_short);

        // Hide notice
        if (noticeDiv) noticeDiv.style.display = 'none';

        // Render regular private videos
        if (regularVideos.length === 0 && shorts.length === 0) {
            privateVideosGrid.innerHTML = `
                <div style="grid-column: 1 / -1;" class="empty-state">
                    <i class="ph ph-lock-key"></i>
                    <p>No private or unlisted videos found</p>
                    <span>All your videos are public</span>
                </div>
            `;
        } else {
            privateVideosGrid.innerHTML = regularVideos.map(video => {
                const isOptimized = optimizedVideoIds.has(video.video_id);
                return createPrivateVideoCard(video, isOptimized, optimizedVideoIds);
            }).join('');

            // Render private shorts if any exist
            if (shorts.length > 0) {
                privateShortsSection.style.display = 'block';
                privateShortsGrid.innerHTML = shorts.map(video => {
                    const isOptimized = optimizedVideoIds.has(video.video_id);
                    // Mark as short for the badge
                    video.is_short = true;
                    return createPrivateVideoCard(video, isOptimized, optimizedVideoIds);
                }).join('');
            }
        }

        console.log(`Loaded ${regularVideos.length} private videos and ${shorts.length} private shorts${fromCache ? ' (from cache)' : ''}`);

    } catch (error) {
        console.error('Error loading private videos:', error);
        privateVideosGrid.innerHTML = `
            <div style="grid-column: 1 / -1;" class="empty-state">
                <i class="ph ph-warning"></i>
                <p>Failed to load private videos</p>
                <span>${error.message}</span>
            </div>
        `;
    }
}

/**
 * Create private video card HTML
 */
function createPrivateVideoCard(video, isOptimized, optimizedVideoIds) {
    const thumbnailUrl = video.thumbnail || `https://i.ytimg.com/vi/${video.video_id}/mqdefault.jpg`;
    const privacyLabel = video.privacy_status === 'unlisted' ? 'Unlisted' : 'Private';
    const privacyIcon = video.privacy_status === 'unlisted' ? 'ph-eye-slash' : 'ph-lock-key';

    // Build menu items for private videos
    const menuItems = `
        ${!isOptimized ? `
        <button class="menu-item" onclick="optimizeVideoFromMenu(event, '${video.video_id}')">
            <i class="ph ph-magic-wand"></i>
            Optimize Video
        </button>
        ` : ''}
        <button class="menu-item" onclick="uploadThumbnail(event, '${video.video_id}')">
            <i class="ph ph-image"></i>
            Change Thumbnail
        </button>
        <button class="menu-item" onclick="setVideoPublic(event, '${video.video_id}')">
            <i class="ph ph-globe"></i>
            Set to Public
        </button>
        <button class="menu-item menu-item-danger" onclick="deleteVideo(event, '${video.video_id}')">
            <i class="ph ph-trash"></i>
            Delete Video
        </button>
    `;

    return `
        <div class="video-card ${isOptimized ? 'optimized' : ''}" data-video-id="${video.video_id}">
            <div class="video-thumbnail" onclick="handleVideoClick('${video.video_id}', ${isOptimized})">
                <img src="${thumbnailUrl}" alt="${escapeHtml(video.title)}" loading="lazy" onerror="this.src='https://i.ytimg.com/vi/${video.video_id}/default.jpg'">
                ${isOptimized ? '<span class="optimized-badge"><i class="ph ph-check-circle"></i></span>' : ''}
                <span class="privacy-badge">
                    <i class="ph ${privacyIcon}"></i>
                    ${privacyLabel}
                </span>
                ${video.is_short ? '<span class="short-badge"><i class="ph ph-device-mobile"></i> Short</span>' : ''}
            </div>
            <div class="video-info" onclick="handleVideoClick('${video.video_id}', ${isOptimized})">
                <h4 class="video-title">${escapeHtml(video.title)}</h4>
                <div class="video-meta">
                    <span class="stat">
                        <i class="ph ph-clock"></i>
                        ${formatTimestamp(video.published_time)}
                    </span>
                </div>
            </div>
            <div class="video-card-menu">
                <button class="video-menu-btn" onclick="toggleVideoMenu(event, '${video.video_id}')" title="More options">
                    <i class="ph ph-dots-three-vertical"></i>
                </button>
                <div class="video-menu-dropdown" id="menu-${video.video_id}">
                    ${menuItems}
                </div>
            </div>
        </div>
    `;
}

/**
 * Toggle video card menu dropdown
 */
function toggleVideoMenu(event, videoId) {
    event.stopPropagation();

    // Close all other open menus
    document.querySelectorAll('.video-menu-dropdown').forEach(menu => {
        if (menu.id !== `menu-${videoId}`) {
            menu.classList.remove('show');
        }
    });

    // Toggle current menu
    const menu = document.getElementById(`menu-${videoId}`);
    if (menu) {
        menu.classList.toggle('show');
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.closest('.video-card-menu')) {
        document.querySelectorAll('.video-menu-dropdown').forEach(menu => {
            menu.classList.remove('show');
        });
    }
});

/**
 * Upload thumbnail for a video
 */
async function uploadThumbnail(event, videoId) {
    event.stopPropagation();

    // Close menu
    document.getElementById(`menu-${videoId}`)?.classList.remove('show');

    // Create file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/jpeg,image/jpg,image/png';

    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // Validate file size (2MB limit for YouTube)
        if (file.size > 2 * 1024 * 1024) {
            showToast('Image must be smaller than 2MB');
            return;
        }

        // Validate file type
        if (!['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)) {
            showToast('Only JPG and PNG images are supported');
            return;
        }

        try {
            showToast('Uploading thumbnail...');

            const formData = new FormData();
            formData.append('thumbnail', file);

            const response = await fetch(`/optimize-video/api/upload-thumbnail/${videoId}`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to upload thumbnail');
            }

            showToast('✅ Thumbnail updated successfully!');

            // Refresh the video thumbnail in the UI
            const videoCard = document.querySelector(`[data-video-id="${videoId}"]`);
            if (videoCard) {
                const img = videoCard.querySelector('.video-thumbnail img');
                if (img) {
                    // Add cache buster to force reload
                    img.src = `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg?t=${Date.now()}`;
                }
            }

        } catch (error) {
            console.error('Error uploading thumbnail:', error);
            showToast('❌ Failed to upload thumbnail: ' + error.message);
        }
    };

    input.click();
}

/**
 * Optimize video from menu
 */
async function optimizeVideoFromMenu(event, videoId) {
    event.stopPropagation();

    // Get the button element and show loading spinner
    const button = event.currentTarget;
    const icon = button.querySelector('i');
    const originalIconClass = icon.className;
    const originalButtonContent = button.innerHTML;

    // Show spinner
    icon.className = 'ph ph-spinner spin';
    button.disabled = true;

    // Close menu
    document.getElementById(`menu-${videoId}`)?.classList.remove('show');

    try {
        // Start optimization
        await optimizeVideo(videoId);
    } catch (error) {
        // Restore button on error
        button.innerHTML = originalButtonContent;
        button.disabled = false;
        throw error;
    } finally {
        // Reset button when selection screen is shown
        // (The selection screen will replace the content anyway)
        button.disabled = false;
    }
}

/**
 * Set video to public
 */
async function setVideoPublic(event, videoId) {
    event.stopPropagation();

    // Close menu
    document.getElementById(`menu-${videoId}`)?.classList.remove('show');

    showConfirmModal(
        'Set Video to Public',
        'Are you sure you want to make this video public? This will make it visible to everyone on YouTube.',
        async () => {
            try {
                showToast('Updating video visibility...');

                const response = await fetch(`/optimize-video/api/set-video-public/${videoId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (!data.success) {
                    throw new Error(data.error || 'Failed to update video visibility');
                }

                showToast('✅ Video is now public!');

                // Remove the video from private section if currently viewing private videos
                if (currentInputMode === 'private') {
                    const videoCard = document.querySelector(`[data-video-id="${videoId}"]`);
                    if (videoCard) {
                        videoCard.remove();
                    }
                }

            } catch (error) {
                console.error('Error setting video to public:', error);
                showToast('❌ Failed to update visibility: ' + error.message);
            }
        }
    );
}

/**
 * Set video to private
 */
async function setVideoPrivate(event, videoId) {
    event.stopPropagation();

    // Close menu
    document.getElementById(`menu-${videoId}`)?.classList.remove('show');

    showConfirmModal(
        'Set Video to Private',
        'Are you sure you want to make this video private? This will hide it from public view on YouTube.',
        async () => {
            try {
                showToast('Updating video visibility...');

                const response = await fetch(`/optimize-video/api/set-video-private/${videoId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (!data.success) {
                    throw new Error(data.error || 'Failed to update video visibility');
                }

                showToast('✅ Video is now private!');

                // Remove the video from public section if currently viewing public videos
                if (currentInputMode === 'public') {
                    const videoCard = document.querySelector(`[data-video-id="${videoId}"]`);
                    if (videoCard) {
                        videoCard.remove();
                    }
                }

            } catch (error) {
                console.error('Error setting video to private:', error);
                showToast('❌ Failed to update visibility: ' + error.message);
            }
        }
    );
}

/**
 * Delete video
 */
async function deleteVideo(event, videoId) {
    event.stopPropagation();

    // Close menu
    document.getElementById(`menu-${videoId}`)?.classList.remove('show');

    showConfirmModal(
        'Delete Video',
        'Are you sure you want to permanently delete this video? This action cannot be undone and will remove the video from YouTube.',
        async () => {
            try {
                showToast('Deleting video...');

                const response = await fetch(`/optimize-video/api/delete-video/${videoId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (!data.success) {
                    throw new Error(data.error || 'Failed to delete video');
                }

                showToast('✅ Video deleted successfully!');

                // Remove the video card from UI
                const videoCard = document.querySelector(`[data-video-id="${videoId}"]`);
                if (videoCard) {
                    videoCard.remove();
                }

            } catch (error) {
                console.error('Error deleting video:', error);
                showToast('❌ Failed to delete video: ' + error.message);
            }
        }
    );
}

/**
 * Correct English captions
 */
async function correctCaptions() {
    if (!currentVideoId) {
        showToast('❌ No video selected');
        return;
    }

    const btn = document.getElementById('correctCaptionsBtn');
    const resultDiv = document.getElementById('advancedOptimizationResult');

    // Disable button and show loading
    btn.disabled = true;
    btn.innerHTML = '<i class="ph ph-spinner"></i><div class="action-info"><div class="action-title">Processing...</div><div class="action-desc">This may take a minute</div></div>';
    resultDiv.style.display = 'none';

    try {
        const response = await fetch(`/optimize-video/api/correct-captions/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!data.success) {
            // Handle specific error types
            if (data.error_type === 'no_captions') {
                throw new Error('No captions found. YouTube may still be processing them.');
            } else if (data.error_type === 'no_english_captions') {
                throw new Error('No English captions found for this video.');
            } else {
                throw new Error(data.error || 'Failed to correct captions');
            }
        }

        // Show success message
        resultDiv.innerHTML = `
            <div class="success-message">
                <i class="ph ph-check-circle"></i>
                <strong>Captions Corrected!</strong>
                <p>English captions have been corrected and uploaded as a new track: "English (Corrected)"</p>
                <p class="quota-note">YouTube API Quota Used: ${data.quota_used} units</p>
            </div>
        `;
        resultDiv.style.display = 'block';
        showToast('✅ Captions corrected successfully!');

    } catch (error) {
        console.error('Error correcting captions:', error);
        resultDiv.innerHTML = `
            <div class="error-message">
                <i class="ph ph-warning-circle"></i>
                <strong>Failed</strong>
                <p>${error.message}</p>
            </div>
        `;
        resultDiv.style.display = 'block';
        showToast('❌ ' + error.message);
    } finally {
        // Reset button
        btn.disabled = false;
        btn.innerHTML = '<i class="ph ph-subtitles"></i><div class="action-info"><div class="action-title">Correct Captions</div><div class="action-desc">Fix grammar & remove filler words</div></div>';
    }
}

/**
 * Generate chapters/timestamps
 */
async function generateChapters() {
    if (!currentVideoId) {
        showToast('❌ No video selected');
        return;
    }

    const btn = document.getElementById('generateChaptersBtn');
    const resultDiv = document.getElementById('advancedOptimizationResult');

    // Disable button and show loading
    btn.disabled = true;
    btn.innerHTML = '<i class="ph ph-spinner"></i><div class="action-info"><div class="action-title">Generating...</div><div class="action-desc">Analyzing transcript</div></div>';
    resultDiv.style.display = 'none';

    try {
        const response = await fetch(`/optimize-video/api/generate-chapters/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!data.success) {
            if (data.error_type === 'no_transcript') {
                throw new Error('No transcript available. YouTube typically generates transcripts 15-30 minutes after upload.');
            } else {
                throw new Error(data.error || 'Failed to generate chapters');
            }
        }

        // Show success with chapters
        const chaptersHtml = data.chapters.map(ch => `<div class="chapter-item"><strong>${ch.timestamp}</strong> ${escapeHtml(ch.title)}</div>`).join('');

        resultDiv.innerHTML = `
            <div class="success-message">
                <i class="ph ph-check-circle"></i>
                <strong>Chapters Generated!</strong>
                <p>Generated ${data.num_chapters} chapters. Copy the text below and add to your video description:</p>
                <div class="chapters-output">
                    <textarea class="chapters-textarea" readonly>${escapeHtml(data.description_format)}</textarea>
                    <button class="copy-btn-small" onclick="copyChaptersToClipboard()">
                        <i class="ph ph-copy"></i>
                        Copy All
                    </button>
                </div>
                <div class="chapters-preview">
                    ${chaptersHtml}
                </div>
            </div>
        `;
        resultDiv.style.display = 'block';

        // Store chapters globally for copying
        window.generatedChapters = data.description_format;

        showToast('✅ Chapters generated successfully!');

    } catch (error) {
        console.error('Error generating chapters:', error);
        resultDiv.innerHTML = `
            <div class="error-message">
                <i class="ph ph-warning-circle"></i>
                <strong>Failed</strong>
                <p>${error.message}</p>
            </div>
        `;
        resultDiv.style.display = 'block';
        showToast('❌ ' + error.message);
    } finally {
        // Reset button
        btn.disabled = false;
        btn.innerHTML = '<i class="ph ph-list-bullets"></i><div class="action-info"><div class="action-title">Generate Chapters</div><div class="action-desc">Create timestamped chapters</div></div>';
    }
}

/**
 * Copy chapters to clipboard
 */
function copyChaptersToClipboard() {
    if (!window.generatedChapters) return;

    navigator.clipboard.writeText(window.generatedChapters).then(() => {
        showToast('✅ Chapters copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy chapters:', err);
        showToast('❌ Failed to copy chapters');
    });
}

/**
 * Post pinned comment
 */
async function postPinnedComment() {
    if (!currentVideoId) {
        showToast('❌ No video selected');
        return;
    }

    const btn = document.getElementById('postPinnedCommentBtn');
    const resultDiv = document.getElementById('advancedOptimizationResult');

    // Disable button and show loading
    btn.disabled = true;
    btn.innerHTML = '<i class="ph ph-spinner"></i><div class="action-info"><div class="action-title">Posting...</div><div class="action-desc">Generating comment</div></div>';
    resultDiv.style.display = 'none';

    try {
        const response = await fetch(`/optimize-video/api/post-pinned-comment/${currentVideoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || 'Failed to post comment');
        }

        // Show success with comment text
        resultDiv.innerHTML = `
            <div class="success-message">
                <i class="ph ph-check-circle"></i>
                <strong>Comment Posted!</strong>
                <p>Posted engagement-boosting comment to your video:</p>
                <div class="comment-preview">
                    <div class="comment-text">"${escapeHtml(data.comment_text)}"</div>
                </div>
                <p class="note-text">
                    <i class="ph ph-info"></i>
                    ${data.note}
                </p>
                <p class="quota-note">YouTube API Quota Used: ${data.quota_used} units</p>
            </div>
        `;
        resultDiv.style.display = 'block';
        showToast('✅ Comment posted successfully!');

    } catch (error) {
        console.error('Error posting comment:', error);
        resultDiv.innerHTML = `
            <div class="error-message">
                <i class="ph ph-warning-circle"></i>
                <strong>Failed</strong>
                <p>${error.message}</p>
            </div>
        `;
        resultDiv.style.display = 'block';
        showToast('❌ ' + error.message);
    } finally {
        // Reset button
        btn.disabled = false;
        btn.innerHTML = '<i class="ph ph-chat-circle"></i><div class="action-info"><div class="action-title">Post Pinned Comment</div><div class="action-desc">Boost engagement with AI comment</div></div>';
    }
}
// Define all available features per platform
const platformFeatures = {
    youtube: [
        { icon: 'ph-scroll', title: 'Create Script', desc: 'AI-powered scripts', url: '/video-script' },
        { icon: 'ph-sparkle', title: 'Title & More', desc: 'Titles, descriptions & tags', url: '/video-title-tags' },
        { icon: 'ph-image', title: 'Design Thumbnail', desc: 'Eye-catching thumbnails', url: '/thumbnail' },
        { icon: 'ph-video', title: 'Analyze Video', desc: 'Performance insights', url: '/analyze-video' },
        { icon: 'ph-magic-wand', title: 'Optimize Video', desc: 'Improve your videos', url: '/optimize-video' },
        { icon: 'ph-users-three', title: 'Track Competitors', desc: 'Monitor competition', url: '/competitors' },
        { icon: 'ph-chart-line-up', title: 'Growth Analytics', desc: 'Track your progress', url: '/analytics?platform=youtube' }
    ],
    x: [
        { icon: 'ph-pencil-simple', title: 'Write Posts', desc: 'Create viral threads', url: '/x-post-editor' },
        { icon: 'ph-chat-circle-text', title: 'Generate Replies', desc: 'Smart reply suggestions', url: '/reply-guy' },
        { icon: 'ph-scissors', title: 'Clip Spaces', desc: 'Extract key moments', url: '/clip-spaces' },
        { icon: 'ph-compass', title: 'Find Trends', desc: 'Discover hot topics', url: '/niche' },
        { icon: 'ph-chart-line-up', title: 'Track Performance', desc: 'Monitor engagement', url: '/analytics?platform=x' }
    ],
    tiktok: [
        { icon: 'ph-trend-up', title: 'Discover Trends', desc: 'Viral content ideas', url: '/trend-finder' },
        { icon: 'ph-magnifying-glass', title: 'Keyword Research', desc: 'Analyze keywords', url: '/tiktok-keyword-research' },
        { icon: 'ph-users-three', title: 'Analyze Competitors', desc: 'Track top creators', url: '/tiktok-competitors' },
        { icon: 'ph-fish-simple', title: 'Create Hooks', desc: 'Viral opening lines', url: '/hook-generator' },
        { icon: 'ph-hash', title: 'Generate Hashtags', desc: 'Trending hashtags', url: '/titles-hashtags' },
        { icon: 'ph-chart-line-up', title: 'View Analytics', desc: 'Track performance', url: '/analytics?platform=tiktok' }
    ],
    general: [
        { icon: 'ph-brain', title: 'Brain Dump', desc: 'Capture all ideas', url: '/brain-dump' },
        { icon: 'ph-git-branch', title: 'Mind Map', desc: 'Visualize concepts', url: '/mind-map' },
        { icon: 'ph-book-open', title: 'Content Wiki', desc: 'Knowledge base', url: '/content-wiki' },
        { icon: 'ph-calendar-check', title: 'Content Calendar', desc: 'Plan & schedule', url: '/content-calendar' }
    ]
};

// Format numbers for display
function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
}

// Format watch time hours
function formatWatchTime(minutes) {
    const hours = Math.floor(minutes / 60);
    if (hours >= 1000) return (hours / 1000).toFixed(1) + 'K hrs';
    return hours + ' hrs';
}

// Carousel functionality

function startAutoScroll() {
    const track = document.getElementById('carousel-track');
    if (!track) return;

    // Get original items
    const items = Array.from(track.children);
    const itemCount = items.length;

    // Clone items many times for a very long seamless scroll
    // Duplicate 5-6 times to create a long track
    const cloneCount = Math.max(5, Math.ceil(40 / itemCount));

    for (let i = 0; i < cloneCount; i++) {
        items.forEach(item => {
            const clone = item.cloneNode(true);
            track.appendChild(clone);
        });
    }

    track.classList.add('auto-scrolling');
}

function stopAutoScroll() {
    const track = document.getElementById('carousel-track');
    if (track) {
        track.classList.remove('auto-scrolling');
    }
}

function loadQuickActions(connectedPlatforms) {
    const track = document.getElementById('carousel-track');
    if (!track) return;

    let allFeatures = [];

    // Add features for connected platforms
    if (connectedPlatforms.youtube) {
        allFeatures.push(...platformFeatures.youtube.map(f => ({...f, platform: 'youtube'})));
    }
    if (connectedPlatforms.x) {
        allFeatures.push(...platformFeatures.x.map(f => ({...f, platform: 'x'})));
    }
    if (connectedPlatforms.tiktok) {
        allFeatures.push(...platformFeatures.tiktok.map(f => ({...f, platform: 'tiktok'})));
    }

    // Always add general features
    allFeatures.push(...platformFeatures.general.map(f => ({...f, platform: 'general'})));

    // Shuffle array to randomize card order
    for (let i = allFeatures.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [allFeatures[i], allFeatures[j]] = [allFeatures[j], allFeatures[i]];
    }

    // Generate HTML for action cards
    track.innerHTML = allFeatures.map(feature => {
        let platformIcon = '';
        if (feature.platform && feature.platform !== 'general') {
            if (feature.platform === 'youtube') {
                platformIcon = '<img src="/static/img/templates/yt_icon_almostblack_digital.png" alt="YouTube" style="width: 24px; height: 24px;">';
            } else {
                const iconType = feature.platform === 'x' ? 'x' : 'tiktok';
                platformIcon = `<i class="ph ph-${iconType}-logo"></i>`;
            }
        }

        return `
        <a href="${feature.url}" class="action-card">
            ${feature.platform && feature.platform !== 'general' ?
                `<div class="platform-badge ${feature.platform}">
                    ${platformIcon}
                </div>` : ''
            }
            <div class="action-icon-wrapper">
                <i class="ph ${feature.icon}"></i>
            </div>
            <div class="action-card-title">${feature.title}</div>
            <div class="action-card-desc">${feature.desc}</div>
        </a>
    `;
    }).join('');

    // Start auto-scroll after a delay
    setTimeout(startAutoScroll, 2000);
}

document.addEventListener('DOMContentLoaded', async function() {
    // Check if user is logged in (this will be rendered by Flask)
    const isLoggedIn = document.getElementById('username-display') !== null;

    if (isLoggedIn) {

    // Load dashboard data
    try {
        const response = await fetch('/api/dashboard-data');
        const data = await response.json();

        // Update username
        const usernameDisplay = document.getElementById('username-display');
        if (usernameDisplay && data.username) {
            usernameDisplay.textContent = data.username;
        }

        // Load credits and streak
        const statsResponse = await fetch('/api/dashboard-stats');
        const stats = await statsResponse.json();

        // Update credits
        const creditsDisplay = document.getElementById('credits-display');
        if (creditsDisplay) {
            creditsDisplay.textContent = stats.credits?.toLocaleString() || '0';
        }

        // Update streak
        const streakDisplay = document.getElementById('streak-display');
        if (streakDisplay) {
            streakDisplay.textContent = stats.login_streak || '0';
        }

        // Track connected platforms
        const connectedPlatforms = {
            youtube: false,
            x: false,
            tiktok: false
        };

        // Show/hide channel cards based on connections
        let hasConnections = false;

        // YouTube Card
        if (data.youtube_connected) {
            hasConnections = true;
            connectedPlatforms.youtube = true;
            document.getElementById('youtube-card').style.display = 'block';
            document.getElementById('youtube-username').textContent = '@' + data.youtube_account;

            // Load YouTube analytics if available
            if (data.youtube_analytics) {
                const metrics = document.getElementById('youtube-metrics');
                metrics.innerHTML = `
                    <div class="metric-item">
                        <div class="metric-value">${formatNumber(data.youtube_analytics.views || 0)}</div>
                        <div class="metric-label">Views</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">+${formatNumber(data.youtube_analytics.subscribers_gained || 0)}</div>
                        <div class="metric-label">Subscribers</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">${formatWatchTime(data.youtube_analytics.watch_time_minutes || 0)}</div>
                        <div class="metric-label">Watch Time</div>
                    </div>
                `;
            }
        } else {
            document.getElementById('connect-youtube').style.display = 'block';
        }

        // X Card
        if (data.x_connected) {
            hasConnections = true;
            connectedPlatforms.x = true;
            document.getElementById('x-card').style.display = 'block';
            document.getElementById('x-username').textContent = '@' + data.x_account;

            // Load X analytics if available
            if (data.x_analytics) {
                const metrics = document.getElementById('x-metrics');
                metrics.innerHTML = `
                    <div class="metric-item">
                        <div class="metric-value">${formatNumber(data.x_analytics.followers || 0)}</div>
                        <div class="metric-label">Followers</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">${formatNumber(data.x_analytics.avg_views || 0)}</div>
                        <div class="metric-label">Avg Views</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">${data.x_analytics.engagement_rate_display || '0%'}</div>
                        <div class="metric-label">Engagement</div>
                    </div>
                `;
            }
        } else {
            document.getElementById('connect-x').style.display = 'block';
        }

        // TikTok Card
        if (data.tiktok_connected) {
            hasConnections = true;
            connectedPlatforms.tiktok = true;
            document.getElementById('tiktok-card').style.display = 'block';
            document.getElementById('tiktok-username').textContent = '@' + data.tiktok_account;

            // Load TikTok analytics if available from dashboard-data
            if (data.tiktok_analytics) {
                const metrics = document.getElementById('tiktok-metrics');
                const tiktokData = data.tiktok_analytics;

                // Get engagement rate
                let engagementRate = tiktokData.engagement_rate || 0;

                // If engagement_rate is 0 but we have the raw data, calculate it
                if (engagementRate === 0 && tiktokData.total_views_35 > 0) {
                    const totalEngagement = (tiktokData.total_likes_35 || 0) +
                                          (tiktokData.total_comments_35 || 0) +
                                          (tiktokData.total_shares_35 || 0);
                    engagementRate = (totalEngagement / tiktokData.total_views_35) * 100;
                }

                const displayEngagement = engagementRate === 0 ? '0%' : `${engagementRate.toFixed(1)}%`;

                metrics.innerHTML = `
                    <div class="metric-item">
                        <div class="metric-value">${formatNumber(tiktokData.followers || 0)}</div>
                        <div class="metric-label">Followers</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">${formatNumber(tiktokData.likes || 0)}</div>
                        <div class="metric-label">Total Likes</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value">${displayEngagement}</div>
                        <div class="metric-label">Engagement</div>
                    </div>
                `;
            }
        } else {
            document.getElementById('connect-tiktok').style.display = 'block';
        }

        // Always show Analytics section (either with connected platforms or connect cards)
        const analyticsSection = document.getElementById('analytics-section');
        if (analyticsSection) {
            analyticsSection.style.display = 'block';
        }

        // Load Quick Actions based on connected platforms
        const quickActionsSection = document.getElementById('quick-actions-section');
        if (quickActionsSection) {
            quickActionsSection.style.display = 'block';
            loadQuickActions(connectedPlatforms);
        }

        // Always show calendar section for logged in users
        const calendarSection = document.getElementById('calendar-section');
        const eventsContainer = document.getElementById('calendar-events');

        // Show calendar section
        calendarSection.style.display = 'block';

        // Show loading state initially
        eventsContainer.innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <div class="loading-spinner" style="font-size: 1.5rem; color: #3B82F6; margin-bottom: 0.25rem;">
                    <i class="ph ph-spinner" style="animation: spin 1s linear infinite; display: inline-block;"></i>
                </div>
                <p style="color: var(--text-tertiary);">Loading calendar events...</p>
            </div>
        `;

        try {
            const calendarResponse = await fetch('/content-calendar/api/events/date-range?' +
                new URLSearchParams({
                    start_date: new Date().toISOString().split('T')[0],
                    end_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
                    limit: 5
                })
            );

            const events = await calendarResponse.json();

            // Clear loading state
            if (events && events.length > 0) {
                // Show the events
                eventsContainer.innerHTML = events.map(event => {
                    const eventDate = new Date(event.publish_date);
                    const statusClass = `status-${event.status || 'draft'}`;
                    const statusText = event.status ? event.status.replace('-', ' ') : 'draft';

                    return `
                        <div class="calendar-event">
                            <div class="event-date">
                                <div class="event-day">${eventDate.getDate()}</div>
                                <div class="event-month">${eventDate.toLocaleDateString('en', { month: 'short' })}</div>
                            </div>
                            <div class="event-details">
                                <div class="event-title">${event.title}</div>
                                <div class="event-platform">${event.platform || 'Not specified'}</div>
                            </div>
                            <div class="event-status ${statusClass}">${statusText}</div>
                        </div>
                    `;
                }).join('');
            } else {
                // Show the empty state with call-to-action when no events
                eventsContainer.innerHTML = `
                    <div class="empty-calendar">
                        <i class="ph ph-calendar-plus"></i>
                        <h4>Start Planning Your Content</h4>
                        <p>Schedule your posts, track deadlines, and never miss an upload again</p>
                        <a href="/content-calendar" class="plan-content-btn">
                            <i class="ph ph-plus"></i>
                            Plan Content
                        </a>
                    </div>
                `;
            }
        } catch (e) {
            console.error('Error loading calendar events:', e);
            // Show empty state on error
            eventsContainer.innerHTML = `
                <div class="empty-calendar">
                    <i class="ph ph-calendar-plus"></i>
                    <h4>Start Planning Your Content</h4>
                    <p>Schedule your posts, track deadlines, and never miss an upload again</p>
                    <a href="/content-calendar" class="plan-content-btn">
                        <i class="ph ph-plus"></i>
                        Plan Content
                    </a>
                </div>
            `;
        }

        // Load X Post Suggestions if user has X connected
        if (data.x_connected) {
            loadXSuggestions();
        }

        // Load Optimize Videos if user has YouTube connected
        if (data.youtube_connected) {
            loadUnoptimizedVideos();
        }

    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }

    }
});

// Load X Post Suggestions
async function loadXSuggestions(forceRefresh = false) {
    const suggestionsSection = document.getElementById('x-suggestions-section');
    const suggestionsContainer = document.getElementById('x-suggestions-container');
    const refreshBtn = document.getElementById('refresh-suggestions-btn');

    if (!suggestionsSection || !suggestionsContainer) return;

    // Show section and loading state
    suggestionsSection.style.display = 'block';

    // Disable refresh button during load
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.style.opacity = '0.5';
    }

    suggestionsContainer.innerHTML = `
        <div style="text-align: center; padding: 2rem;">
            <div class="loading-spinner" style="font-size: 1.5rem; color: #3B82F6; margin: 0 auto 0.25rem;">
                <i class="ph ph-spinner" style="animation: spin 1s linear infinite; display: inline-block;"></i>
            </div>
            <p style="color: var(--text-tertiary);">Loading suggestions...</p>
        </div>
    `;

    try {
        const url = forceRefresh ? '/api/x-content-suggestions?refresh=true' : '/api/x-content-suggestions';
        const response = await fetch(url);
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to load suggestions');
        }

        const suggestions = result.suggestions || [];

        if (suggestions.length === 0) {
            suggestionsContainer.innerHTML = `
                <div class="suggestions-empty">
                    <i class="ph ph-lightning-slash"></i>
                    <h4>No Suggestions Available</h4>
                    <p>We need more posts to analyze. Connect your X account and ensure you have at least 5 posts.</p>
                </div>
            `;
            return;
        }

        // Render suggestions in a compact list
        let suggestionsHtml = '<div class="suggestions-list">';

        suggestions.forEach((suggestion, index) => {
            const contentId = `suggestion-content-${index}`;
            const hookTypeDisplay = formatHookType(suggestion.hook_type);
            suggestionsHtml += `
                <div class="suggestion-card" onclick="toggleSuggestion(${index})">
                    <div class="suggestion-collapsed">
                        <div class="suggestion-title-row">
                            <div class="suggestion-number">${index + 1}</div>
                            <div class="suggestion-title">${suggestion.title}</div>
                            <div class="hook-badge">${hookTypeDisplay}</div>
                        </div>
                        <i class="ph ph-caret-down expand-icon"></i>
                    </div>

                    <div class="suggestion-expanded">
                        <div class="suggestion-content" id="${contentId}">${suggestion.content}</div>

                        <div class="suggestion-actions">
                            <button class="suggestion-btn btn-use" onclick="event.stopPropagation(); useInEditorById('${contentId}')">
                                <i class="ph ph-pencil-simple"></i>
                                Use in Editor
                            </button>
                            <button class="suggestion-btn btn-copy" onclick="event.stopPropagation(); copySuggestionById('${contentId}', this)">
                                <i class="ph ph-copy"></i>
                                Copy
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        suggestionsHtml += '</div>';
        suggestionsContainer.innerHTML = suggestionsHtml;

    } catch (error) {
        console.error('Error loading X suggestions:', error);

        // Hide the entire section when there's an error (e.g., no credits, API error)
        if (suggestionsSection) {
            suggestionsSection.style.display = 'none';
        }
    } finally {
        // Re-enable refresh button
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.style.opacity = '1';
        }
    }
}

// Toggle suggestion card expansion
function toggleSuggestion(index) {
    const cards = document.querySelectorAll('.suggestion-card');
    if (cards[index]) {
        cards[index].classList.toggle('expanded');
    }
}

// Format hook type for display
function formatHookType(hookType) {
    const formatted = {
        'question': 'Question',
        'stat': 'Stat',
        'story': 'Story',
        'hot_take': 'Hot Take',
        'thread': 'Thread'
    };
    return formatted[hookType] || hookType;
}

// Helper function to get icon for hook type
function getHookIcon(hookType) {
    const icons = {
        'question': 'ph-question',
        'stat': 'ph-chart-line-up',
        'story': 'ph-book-open',
        'hot_take': 'ph-fire',
        'thread': 'ph-list-bullets'
    };
    return icons[hookType] || 'ph-chat-circle-text';
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, '&#39;');
}

// Use suggestion in editor by element ID
function useInEditorById(contentId) {
    const contentElement = document.getElementById(contentId);
    if (!contentElement) {
        console.error('Content element not found:', contentId);
        return;
    }

    const content = contentElement.textContent;

    // Store in sessionStorage to pass to editor
    sessionStorage.setItem('x_post_suggestion', content);

    // Navigate to editor
    window.location.href = '/x-post-editor';
}

// Copy suggestion to clipboard by element ID
async function copySuggestionById(contentId, button) {
    try {
        const contentElement = document.getElementById(contentId);
        if (!contentElement) {
            console.error('Content element not found:', contentId);
            return;
        }

        const content = contentElement.textContent;
        await navigator.clipboard.writeText(content);

        // Update button text temporarily
        const originalHtml = button.innerHTML;
        button.innerHTML = '<i class="ph ph-check"></i> Copied!';
        button.style.background = 'rgba(16, 185, 129, 0.1)';
        button.style.color = '#10B981';
        button.style.borderColor = 'rgba(16, 185, 129, 0.3)';

        setTimeout(() => {
            button.innerHTML = originalHtml;
            button.style.background = '';
            button.style.color = '';
            button.style.borderColor = '';
        }, 2000);

    } catch (error) {
        console.error('Failed to copy:', error);
        alert('Failed to copy to clipboard');
    }
}

// Pause auto-scroll when hovering
document.addEventListener('DOMContentLoaded', function() {
    const track = document.getElementById('carousel-track');
    if (track) {
        track.addEventListener('mouseenter', () => {
            track.style.animationPlayState = 'paused';
        });

        track.addEventListener('mouseleave', () => {
            track.style.animationPlayState = 'running';
        });
    }
});

// Load Unoptimized Videos
async function loadUnoptimizedVideos() {
    const section = document.getElementById('optimize-videos-section');
    const container = document.getElementById('optimize-videos-container');

    if (!section || !container) return;

    // Show section and loading state
    section.style.display = 'block';

    container.innerHTML = `
        <div style="text-align: center; padding: 2rem;">
            <div class="loading-spinner" style="font-size: 1.5rem; color: #3B82F6; margin: 0 auto 0.25rem;">
                <i class="ph ph-spinner" style="animation: spin 1s linear infinite; display: inline-block;"></i>
            </div>
            <p style="color: var(--text-tertiary);">Loading videos...</p>
        </div>
    `;

    try {
        const response = await fetch('/optimize-video/api/get-unoptimized-videos');
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Failed to load videos');
        }

        const videos = result.videos || [];

        if (videos.length === 0) {
            container.innerHTML = `
                <div class="optimize-videos-empty">
                    <i class="ph ph-check-circle"></i>
                    <h4>All Videos Optimized!</h4>
                    <p>Great work! All your recent videos have been optimized. Keep creating awesome content!</p>
                </div>
            `;
            return;
        }

        // Render videos in grid
        let videosHtml = '<div class="optimize-videos-grid">';

        videos.forEach(video => {
            videosHtml += `
                <a href="/optimize-video?video_id=${video.video_id}" class="optimize-video-card">
                    <img src="${video.thumbnail}" alt="${escapeHtml(video.title)}" class="optimize-video-thumbnail" loading="lazy">
                    <div class="optimize-video-info">
                        <div class="optimize-video-title">${escapeHtml(video.title)}</div>
                    </div>
                </a>
            `;
        });

        videosHtml += '</div>';
        container.innerHTML = videosHtml;

    } catch (error) {
        console.error('Error loading unoptimized videos:', error);
        container.innerHTML = `
            <div class="optimize-videos-empty">
                <i class="ph ph-warning-circle"></i>
                <h4>Unable to load videos</h4>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// Welcome Modal for New Users
async function checkAndShowWelcomeModal() {
    try {
        // Fetch user data to check if they've seen the welcome modal
        const response = await fetch('/api/dashboard-stats');
        const data = await response.json();

        const hasSeenWelcome = data.has_seen_welcome || false;

        if (!hasSeenWelcome) {
            const modal = document.getElementById('welcomeModal');
            if (modal) {
                setTimeout(() => {
                    modal.classList.add('visible');
                }, 500); // Show after 500ms delay for better UX
            }
        }
    } catch (error) {
        console.error('Error checking welcome modal status:', error);
    }
}

async function closeWelcomeModal() {
    const modal = document.getElementById('welcomeModal');
    if (modal) {
        modal.classList.remove('visible');

        // Save to Firebase that user has seen the welcome modal
        try {
            await fetch('/api/user/update-welcome-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ has_seen_welcome: true })
            });
        } catch (error) {
            console.error('Error saving welcome status:', error);
        }
    }
}

// Check for new user on page load
document.addEventListener('DOMContentLoaded', checkAndShowWelcomeModal);

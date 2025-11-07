/**
 * Repost Modal - Shared component for cross-platform content reposting
 * Used across TikTok, Instagram, YouTube, and X upload studios
 */

class RepostModal {
    constructor(options = {}) {
        this.onSelect = options.onSelect || null; // Callback when content is selected
        this.onClose = options.onClose || null; // Callback when modal is closed
        this.mediaTypeFilter = options.mediaTypeFilter || null; // 'video', 'image', or null for all
        this.currentPlatform = options.platform || null; // Current platform to show which are already posted
        this.modalElement = null;
        this.contentData = [];
        this.init();
    }

    init() {
        // Create modal HTML if it doesn't exist
        if (!document.getElementById('repostModal')) {
            this.createModal();
        }
        this.modalElement = document.getElementById('repostModal');
        this.bindEvents();
    }

    createModal() {
        const modalHTML = `
            <div id="repostModal" class="repost-modal-overlay">
                <div class="repost-modal">
                    <div class="repost-modal-header">
                        <h2 class="repost-modal-title">
                            <i class="ph ph-recycle"></i>
                            Repost Recent Content
                        </h2>
                        <button class="repost-modal-close" id="repostModalCloseBtn">
                            <i class="ph ph-x"></i>
                        </button>
                    </div>
                    <div class="repost-modal-body">
                        <div class="repost-modal-filters">
                            <button class="repost-filter-btn active" data-filter="all">
                                <i class="ph ph-stack"></i>
                                All Content
                            </button>
                            <button class="repost-filter-btn" data-filter="video">
                                <i class="ph ph-video"></i>
                                Videos Only
                            </button>
                            <button class="repost-filter-btn" data-filter="image">
                                <i class="ph ph-image"></i>
                                Images Only
                            </button>
                        </div>
                        <div id="repostContentContainer">
                            <div class="repost-loading">
                                <div class="loading-spinner"><i class="ph ph-spinner"></i></div>
                                <p>Loading recent content...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    bindEvents() {
        // Close button
        const closeBtn = document.getElementById('repostModalCloseBtn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.close();
            });
        }

        // Close on overlay click
        this.modalElement.addEventListener('click', (e) => {
            if (e.target === this.modalElement) {
                this.close();
            }
        });

        // Filter buttons
        const filterBtns = this.modalElement.querySelectorAll('.repost-filter-btn');
        filterBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                filterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const filter = btn.dataset.filter;
                this.filterContent(filter);
            });
        });

        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modalElement.classList.contains('active')) {
                this.close();
            }
        });
    }

    async open() {
        this.modalElement.classList.add('active');
        document.body.style.overflow = 'hidden';
        await this.loadContent();
    }

    close() {
        this.modalElement.classList.remove('active');
        document.body.style.overflow = '';

        // Call onClose callback if provided
        if (this.onClose) {
            this.onClose();
        }
    }

    async loadContent() {
        const container = document.getElementById('repostContentContainer');
        container.innerHTML = `
            <div class="repost-loading">
                <div class="loading-spinner"><i class="ph ph-spinner"></i></div>
                <p>Loading recent content...</p>
            </div>
        `;

        try {
            // Build query params
            let queryParams = '?hours=24'; // Last 24 hours
            if (this.mediaTypeFilter) {
                queryParams += `&media_type=${this.mediaTypeFilter}`;
            }

            const response = await fetch(`/api/content-library${queryParams}`, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to load content');
            }

            const data = await response.json();
            this.contentData = data.content || [];
            this.renderContent(this.contentData);
        } catch (error) {
            console.error('Error loading content:', error);
            container.innerHTML = `
                <div class="repost-content-empty">
                    <i class="ph ph-warning-circle"></i>
                    <h3>Error Loading Content</h3>
                    <p>${error.message}</p>
                </div>
            `;
        }
    }

    filterContent(filter) {
        let filtered = this.contentData;
        if (filter === 'video') {
            filtered = this.contentData.filter(item => item.media_type === 'video');
        } else if (filter === 'image') {
            filtered = this.contentData.filter(item => item.media_type === 'image');
        }
        this.renderContent(filtered);
    }

    renderContent(content) {
        const container = document.getElementById('repostContentContainer');

        if (!content || content.length === 0) {
            container.innerHTML = `
                <div class="repost-content-empty">
                    <i class="ph ph-folder-open"></i>
                    <h3>No Recent Content</h3>
                    <p>Upload some content first, then you can repost it to other platforms!</p>
                </div>
            `;
            return;
        }

        const tableHTML = `
            <table class="repost-content-table">
                <thead>
                    <tr>
                        <th>Media</th>
                        <th>Keywords & Description</th>
                        <th>Platform</th>
                        <th>Status</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    ${content.map(item => this.renderContentRow(item)).join('')}
                </tbody>
            </table>
        `;

        container.innerHTML = tableHTML;

        // Make rows clickable
        container.querySelectorAll('.repost-content-row').forEach(row => {
            row.addEventListener('click', () => {
                const contentId = row.dataset.contentId;
                const content = this.contentData.find(c => c.id === contentId);
                if (content && this.onSelect) {
                    this.onSelect(content);
                    this.close();
                }
            });
        });
    }

    renderContentRow(item) {
        const platforms = item.platforms_posted || {};
        const platformInfo = this.getPlatformStatusInfo(platforms);
        const isVideo = item.media_type === 'video';

        // Truncate keywords and description
        const keywords = (item.keywords || 'No keywords').substring(0, 50);
        const description = (item.content_description || 'No description').substring(0, 100);

        return `
            <tr class="repost-content-row" data-content-id="${item.id}">
                <td class="repost-thumbnail-cell">
                    <div class="repost-thumbnail-wrapper">
                        ${isVideo ?
                            `<video class="repost-thumbnail" muted playsinline>
                                <source src="${item.media_url}" type="video/mp4">
                                <div class="repost-thumbnail-placeholder">
                                    <i class="ph ph-video"></i>
                                </div>
                            </video>` :
                            (item.thumbnail_url || item.media_url ?
                                `<img src="${item.thumbnail_url || item.media_url}" alt="Content thumbnail" class="repost-thumbnail" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
                                 <div class="repost-thumbnail-placeholder" style="display:none;">
                                    <i class="ph ph-image"></i>
                                 </div>` :
                                `<div class="repost-thumbnail-placeholder">
                                    <i class="ph ph-image"></i>
                                 </div>`)
                        }
                    </div>
                </td>
                <td class="repost-info-cell">
                    <div class="repost-keywords">${this.escapeHtml(keywords)}</div>
                    <div class="repost-description">${this.escapeHtml(description)}</div>
                </td>
                <td class="repost-platform-cell">
                    ${platformInfo.platforms}
                </td>
                <td class="repost-status-cell">
                    ${platformInfo.statuses}
                </td>
                <td class="repost-time-cell">
                    ${platformInfo.times}
                </td>
            </tr>
        `;
    }

    getPlatformStatusInfo(platforms) {
        const platformNames = {
            youtube: 'YouTube',
            tiktok: 'TikTok',
            instagram: 'Instagram',
            x: 'X'
        };

        const allPlatforms = ['youtube', 'tiktok', 'instagram', 'x'];
        const platformLabels = [];
        const statusLabels = [];
        const timeLabels = [];

        for (const platform of allPlatforms) {
            const data = platforms[platform];
            const name = platformNames[platform];

            if (data && data.status) {
                // Platform name
                platformLabels.push(`<div class="platform-row">${name}</div>`);

                // Status - check if scheduled_for is in the future
                let status = 'Posted';
                if (data.scheduled_for) {
                    const scheduleDate = new Date(data.scheduled_for);
                    if (scheduleDate > new Date()) {
                        status = 'Scheduled';
                    }
                }
                statusLabels.push(`<div class="status-row ${status.toLowerCase()}">${status}</div>`);

                // Time
                let timeStr = '';
                if (data.scheduled_for) {
                    const scheduleDate = new Date(data.scheduled_for);
                    if (scheduleDate > new Date()) {
                        // Future - show "in X days/hours"
                        timeStr = `in ${this.formatScheduledDateShort(scheduleDate)}`;
                    } else {
                        // Past - show "X ago"
                        timeStr = this.getTimeAgo(data.posted_at || data.scheduled_for);
                    }
                } else if (data.posted_at) {
                    timeStr = this.getTimeAgo(data.posted_at);
                }
                timeLabels.push(`<div class="time-row">${timeStr}</div>`);
            }
        }

        if (platformLabels.length === 0) {
            return {
                platforms: '<div class="no-platforms">Not posted yet</div>',
                statuses: '-',
                times: '-'
            };
        }

        return {
            platforms: platformLabels.join(''),
            statuses: statusLabels.join(''),
            times: timeLabels.join('')
        };
    }

    getDateInfo(item, platforms) {
        // Show status for each platform that has been posted/scheduled
        const platformNames = {
            youtube: 'YouTube',
            tiktok: 'TikTok',
            instagram: 'Instagram',
            x: 'X'
        };

        const statuses = [];

        for (const [platform, data] of Object.entries(platforms || {})) {
            if (data && data.status) {
                const name = platformNames[platform] || platform;

                if (data.scheduled_for) {
                    const scheduleDate = new Date(data.scheduled_for);
                    if (scheduleDate > new Date()) {
                        // Future schedule
                        const timeStr = this.formatScheduledDateShort(scheduleDate);
                        statuses.push(`${name}: Scheduled in ${timeStr}`);
                    } else {
                        // Past schedule (posted)
                        statuses.push(`${name}: Posted`);
                    }
                } else {
                    // No schedule date, just posted
                    statuses.push(`${name}: Posted`);
                }
            }
        }

        if (statuses.length > 0) {
            return statuses.join('<br>');
        } else {
            // No platforms posted yet
            return `Uploaded ${this.getTimeAgo(item.created_at)}`;
        }
    }

    formatScheduledDateShort(date) {
        const now = new Date();
        const diff = date - now;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor(diff / (1000 * 60 * 60));

        if (days > 0) {
            return `${days}d`;
        } else if (hours > 0) {
            return `${hours}h`;
        } else {
            return 'soon';
        }
    }

    formatScheduledDate(date) {
        const now = new Date();
        const diff = date - now;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor(diff / (1000 * 60 * 60));

        if (days > 0) {
            return `Scheduled in ${days}d`;
        } else if (hours > 0) {
            return `Scheduled in ${hours}h`;
        } else {
            return 'Scheduled soon';
        }
    }

    renderPlatformBadges(platforms) {
        const platformNames = {
            youtube: 'YouTube',
            tiktok: 'TikTok',
            instagram: 'Instagram',
            x: 'X'
        };

        const allPlatforms = ['youtube', 'tiktok', 'instagram', 'x'];

        return allPlatforms.map(platform => {
            const platformData = platforms[platform];
            const isPosted = platformData && platformData.status;
            const badgeClass = isPosted ? 'posted' : 'not-posted';
            const name = platformNames[platform];

            // Check if scheduled for future
            let scheduledInfo = '';
            if (platformData && platformData.scheduled_for) {
                const scheduleDate = new Date(platformData.scheduled_for);
                if (scheduleDate > new Date()) {
                    scheduledInfo = this.formatScheduledDate(scheduleDate);
                }
            }

            return `
                <div class="repost-platform-badge-wrapper">
                    <span class="repost-platform-badge ${badgeClass}">
                        ${name}
                    </span>
                    ${scheduledInfo ? `<div class="platform-schedule-time">${scheduledInfo}</div>` : ''}
                </div>
            `;
        }).join('');
    }

    getTimeAgo(timestamp) {
        if (!timestamp) return 'Unknown';

        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;

        return date.toLocaleDateString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
let repostModal = null;

// Initialize function to be called from each upload studio
function initRepostModal(options) {
    repostModal = new RepostModal(options);
    return repostModal;
}

/**
 * Calendar Link Modal - Reusable component for linking uploads to calendar items
 * Usage: Include this file and calendar-link-modal.css, then call CalendarLinkModal.init(platform, onSelect)
 */

const CalendarLinkModal = {
    linkedCalendarItem: null,
    platform: null,
    onSelectCallback: null,

    /**
     * Initialize the calendar link modal
     * @param {string} platform - Platform name ('YouTube', 'TikTok', 'X', 'Instagram')
     * @param {function} onSelect - Callback function when item is selected, receives (item)
     */
    init(platform, onSelect) {
        this.platform = platform;
        this.onSelectCallback = onSelect;
    },

    /**
     * Open the modal
     */
    open() {
        console.log("Opening calendar modal for platform:", this.platform);

        // Create modal HTML
        const modalHTML = `
            <div id="link-calendar-modal" class="calendar-link-modal-overlay">
                <div class="calendar-link-modal">
                    <div class="calendar-link-modal-header">
                        <h2>Link to Calendar Item</h2>
                        <button class="calendar-link-modal-close" onclick="CalendarLinkModal.close()">
                            <i class="ph ph-x"></i>
                        </button>
                    </div>
                    <div class="calendar-link-modal-body">
                        <div class="calendar-items-loading">
                            <i class="ph ph-spinner" style="animation: spin 1s linear infinite;"></i>
                            <span>Loading calendar items...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Insert modal into DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Show modal with animation
        setTimeout(() => {
            const overlay = document.getElementById('link-calendar-modal');
            if (overlay) {
                overlay.classList.add('show');
            }
        }, 10);

        // Load calendar items
        this.loadItems();
    },

    /**
     * Close the modal
     */
    close() {
        const modal = document.getElementById('link-calendar-modal');
        if (modal) {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        }
    },

    /**
     * Fetch calendar items from API
     */
    async fetchItems() {
        try {
            const response = await fetch('/content-calendar/api/events');
            const data = await response.json();

            // Get current time in user's local timezone
            const now = new Date();

            // Filter to only show items that are NOT scheduled (no clock icon)
            // i.e., items without youtube_video_id, instagram_post_id, tiktok_post_id, x_post_id
            // Also filter out items with publish_date in the past (in user's local timezone)
            const unscheduledItems = data.filter(item => {
                // Check if already scheduled on any platform
                const isScheduled = item.youtube_video_id ||
                    item.instagram_post_id ||
                    item.tiktok_post_id ||
                    item.x_post_id;

                if (isScheduled) return false;

                // Check platform match
                const platformMatch = item.platform === this.platform || item.platform === 'Not set';
                if (!platformMatch) return false;

                // Check if publish_date is in the future (or no date set)
                if (item.publish_date) {
                    const publishDate = new Date(item.publish_date);
                    if (publishDate < now) return false; // Filter out past dates
                }

                return true;
            });

            return unscheduledItems;
        } catch (error) {
            console.error('Error fetching calendar items:', error);
            return [];
        }
    },

    /**
     * Load and render calendar items
     */
    async loadItems() {
        const items = await this.fetchItems();
        const modalBody = document.querySelector('.calendar-link-modal-body');

        if (items.length === 0) {
            modalBody.innerHTML = `
                <div class="calendar-items-empty">
                    <i class="ph ph-calendar-x"></i>
                    <h3>No Available Items</h3>
                    <p>No unscheduled ${this.platform} content found in your calendar.</p>
                    <button class="btn-secondary" onclick="CalendarLinkModal.close()">Close</button>
                </div>
            `;
            return;
        }

        // Sort items by publish date (earliest first)
        items.sort((a, b) => {
            if (!a.publish_date) return 1;
            if (!b.publish_date) return -1;
            return new Date(a.publish_date) - new Date(b.publish_date);
        });

        // Render calendar items as table
        const tableRows = items.map((item, index) => {
            const date = item.publish_date ? new Date(item.publish_date).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
            }) : 'No date';

            const platform = item.platform || 'Not set';

            // Truncate title to 50 characters
            const title = item.title || 'Untitled';
            const truncatedTitle = title.length > 50 ? title.substring(0, 50) + '...' : title;

            return `
                <tr class="calendar-table-row" data-item-id="${item.id}">
                    <td class="calendar-table-cell" title="${this.escapeHtml(title)}">${this.escapeHtml(truncatedTitle)}</td>
                    <td class="calendar-table-cell">${this.escapeHtml(platform)}</td>
                    <td class="calendar-table-cell">${date}</td>
                </tr>
            `;
        }).join('');

        modalBody.innerHTML = `
            <div class="calendar-items-list">
                <div class="calendar-items-header">
                    <p>Select a calendar item to link with this upload:</p>
                </div>
                <table class="calendar-items-table">
                    <thead>
                        <tr>
                            <th>Title</th>
                            <th>Platform</th>
                            <th>Publish Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tableRows}
                    </tbody>
                </table>
            </div>
        `;

        // Store items for selection
        this.items = items;

        // Add click event listeners to rows
        const rows = modalBody.querySelectorAll('.calendar-table-row');
        rows.forEach(row => {
            row.addEventListener('click', () => {
                const itemId = row.getAttribute('data-item-id');
                this.selectItem(itemId);
            });
        });
    },

    /**
     * Select a calendar item
     */
    selectItem(itemId) {
        console.log("selectItem called with ID:", itemId);
        console.log("Available items:", this.items);
        const item = this.items ? this.items.find(i => String(i.id) === String(itemId)) : null;
        if (!item) {
            console.error("Item not found with ID:", itemId);
            console.error("Item IDs in array:", this.items ? this.items.map(i => i.id) : 'no items');
            return;
        }

        this.linkedCalendarItem = item;

        // Call the callback if provided
        if (this.onSelectCallback) {
            this.onSelectCallback(item);
        }

        this.close();
        this.showNotification('Calendar item linked successfully!');
    },

    /**
     * Get the currently linked calendar item
     */
    getLinkedItem() {
        return this.linkedCalendarItem;
    },

    /**
     * Clear the linked item
     */
    clearLinkedItem() {
        this.linkedCalendarItem = null;
    },

    /**
     * Update a calendar item with platform post ID after successful upload
     * @param {string} itemId - Calendar item ID
     * @param {string} platformPostId - Platform post ID (e.g., YouTube video ID)
     * @param {object} metadata - Optional metadata (title, description, tags)
     */
    async updateCalendarItem(itemId, platformPostId, metadata = {}) {
        if (!itemId || !platformPostId) return;

        try {
            const platformField = this.getPlatformFieldName();
            const updatePayload = {
                [platformField]: platformPostId,
                platform: this.platform
            };

            // Add metadata if provided (title, description, tags)
            if (metadata.title) {
                updatePayload.title = metadata.title;
            }
            if (metadata.description) {
                updatePayload.description = metadata.description;
            }
            if (metadata.tags) {
                // Store tags as comma-separated string
                const tagsString = Array.isArray(metadata.tags)
                    ? metadata.tags.join(', ')
                    : metadata.tags;
                updatePayload.tags = tagsString;
            }

            const updateResponse = await fetch(`/content-calendar/api/event/${itemId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatePayload)
            });

            const updateData = await updateResponse.json();
            if (updateData.success) {
                console.log(`Calendar item updated with ${this.platform} post ID and metadata:`, platformPostId);
                return true;
            }
            return false;
        } catch (error) {
            console.error('Error updating calendar item:', error);
            return false;
        }
    },

    /**
     * Get platform-specific field name for post ID
     */
    getPlatformFieldName() {
        const fieldMap = {
            'YouTube': 'youtube_video_id',
            'TikTok': 'tiktok_post_id',
            'X': 'x_post_id',
            'Instagram': 'instagram_post_id'
        };
        return fieldMap[this.platform] || 'youtube_video_id';
    },

    /**
     * Show notification toast
     */
    showNotification(message) {
        const notification = document.createElement('div');
        notification.className = 'calendar-link-notification';
        notification.innerHTML = `
            <i class="ph ph-check-circle"></i>
            <span>${message}</span>
        `;

        document.body.appendChild(notification);

        setTimeout(() => notification.classList.add('show'), 10);

        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Make it globally available
window.CalendarLinkModal = CalendarLinkModal;

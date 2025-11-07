/**
 * Content Event Modal
 */

class ContentEventModal {
    constructor() {
        this.modal = null;
        this.currentEvent = null;
        this.onSave = null;
        this.onDelete = null;
        this.comments = [];
        this.init();
    }

    init() {
        this.createModal();
        // Use setTimeout to ensure DOM elements are available
        setTimeout(() => {
            this.attachEventListeners();
            this.populateDateDropdown();
            this.populateTimeDropdown();
        }, 0);
    }

    createModal() {
        const modalHTML = `
            <div id="content-event-modal" class="event-modal-overlay">
                <div class="event-modal">
                    <button class="event-modal-close" id="close-btn">
                        <i class="ph ph-x"></i>
                    </button>

                    <div class="event-modal-body">
                        <!-- Left Side -->
                        <div class="event-modal-main">
                            <!-- Tabbed Content Section -->
                            <div class="content-tabs-wrapper">
                                <!-- Tab Headers -->
                                <div class="content-tabs-header">
                                    <button class="content-tab active" data-tab="original">
                                        <i class="ph ph-note"></i>
                                        <span>Content Info</span>
                                    </button>
                                    <button class="content-tab" data-tab="youtube" id="youtube-tab-btn" style="display: none;">
                                        <i class="ph ph-youtube-logo"></i>
                                        <span>YouTube Metadata</span>
                                    </button>
                                </div>

                                <!-- Tab Content -->
                                <div class="content-tabs-body">
                                    <!-- Content Info Tab -->
                                    <div class="content-tab-panel active" data-panel="original">
                                        <div class="form-group">
                                            <label>Requirements</label>
                                            <textarea id="content-field" class="form-control" rows="4" placeholder="Enter requirements..."></textarea>
                                        </div>
                                    </div>

                                    <!-- YouTube Metadata Tab -->
                                    <div class="content-tab-panel" data-panel="youtube">
                                        <div class="form-group">
                                            <label>Video Title</label>
                                            <textarea id="youtube-title-field" class="form-control" rows="2" readonly disabled></textarea>
                                        </div>
                                        <div class="form-group">
                                            <label>Description</label>
                                            <textarea id="youtube-description-field" class="form-control" rows="8" readonly disabled></textarea>
                                        </div>
                                        <div class="form-group">
                                            <label>Tags</label>
                                            <div id="youtube-tags-container" class="youtube-tags-container"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Platform -->
                            <div class="form-group" id="platform-form-group">
                                <label>Platform</label>
                                <select id="platform-select" class="form-control">
                                    <option value="Not set" selected>Not set</option>
                                    <option value="YouTube">YouTube</option>
                                    <option value="Instagram">Instagram</option>
                                    <option value="TikTok">TikTok</option>
                                    <option value="X">X</option>
                                </select>
                            </div>

                            <!-- Status & Type -->
                            <div class="form-row">
                                <div class="form-group">
                                    <label>Status</label>
                                    <select id="status-select" class="form-control">
                                        <option value="draft" selected>Draft</option>
                                        <option value="in_progress">In Progress</option>
                                        <option value="review">Review</option>
                                        <option value="ready">Ready</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Type</label>
                                    <select id="type-select" class="form-control">
                                        <option value="organic" selected>Organic</option>
                                        <option value="sponsored">Sponsored</option>
                                    </select>
                                </div>
                            </div>

                            <!-- Scheduled Tab (only visible when scheduled) -->
                            <div id="scheduled-tab" style="display: none;">
                                <div class="scheduled-header">
                                    <i class="ph ph-calendar-check"></i>
                                    <span>Publish Date</span>
                                </div>
                                <div class="form-row">
                                    <div class="form-group">
                                        <label>Date</label>
                                        <select id="schedule-date" class="form-control"></select>
                                    </div>
                                    <div class="form-group">
                                        <label>Time</label>
                                        <select id="schedule-time" class="form-control"></select>
                                    </div>
                                </div>
                            </div>

                            <!-- Actions -->
                            <div class="modal-actions">
                                <button class="btn-delete" id="delete-btn">Delete Content</button>
                                <button class="btn-save" id="save-btn">Save</button>
                            </div>
                        </div>

                        <!-- Right Side - Comments -->
                        <div class="event-modal-sidebar">
                            <div class="comments-header">
                                <i class="ph ph-chat-dots"></i>
                                <span>Comments</span>
                            </div>
                            <div class="comments-list" id="comments-list"></div>
                            <div class="comment-input-box">
                                <textarea id="comment-input" placeholder="Add a comment..."></textarea>
                                <button id="send-comment">
                                    <i class="ph ph-paper-plane-right"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('content-event-modal');
    }

    attachEventListeners() {
        console.log('Attaching event listeners...');

        const closeBtn = document.getElementById('close-btn');
        const saveBtn = document.getElementById('save-btn');
        const deleteBtn = document.getElementById('delete-btn');
        const statusSelect = document.getElementById('status-select');
        const sendComment = document.getElementById('send-comment');
        const commentInput = document.getElementById('comment-input');

        console.log('Delete button found:', deleteBtn);

        if (closeBtn) closeBtn.onclick = () => this.close();
        if (this.modal) {
            this.modal.onclick = (e) => {
                if (e.target === this.modal) this.close();
            };
        }

        if (statusSelect) statusSelect.onchange = () => this.handleStatusChange();
        if (saveBtn) {
            saveBtn.onclick = () => {
                console.log('Save button clicked!');
                this.save();
            };
        }
        if (deleteBtn) {
            console.log('Setting up delete button click handler');
            deleteBtn.addEventListener('click', (e) => {
                console.log('Delete button clicked!', e);
                e.preventDefault();
                e.stopPropagation();
                this.deleteContent();
            });
        }

        if (sendComment) {
            sendComment.addEventListener('click', (e) => {
                console.log('Send comment button clicked!');
                e.preventDefault();
                e.stopPropagation();
                this.addComment();
            });
        }
        if (commentInput) {
            commentInput.onkeydown = (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.addComment();
                }
            };
        }

        // Tab switching
        const tabButtons = document.querySelectorAll('.content-tab');
        tabButtons.forEach(btn => {
            btn.onclick = () => this.switchTab(btn.dataset.tab);
        });

        console.log('Event listeners attached');
    }

    switchTab(tabName) {
        console.log('Switching to tab:', tabName);

        // Update tab buttons
        document.querySelectorAll('.content-tab').forEach(tab => {
            if (tab.dataset.tab === tabName) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Update tab panels - REMOVE all active classes first, then add to the correct one
        document.querySelectorAll('.content-tab-panel').forEach(panel => {
            panel.classList.remove('active');
            console.log('Removed active from panel:', panel.dataset.panel);
        });

        const activePanel = document.querySelector(`.content-tab-panel[data-panel="${tabName}"]`);
        if (activePanel) {
            activePanel.classList.add('active');
            console.log('Added active to panel:', tabName);
        }

        // Show/hide elements below tabs based on active tab
        const platformGroup = document.getElementById('platform-form-group');
        const statusTypeRow = document.querySelector('#status-select')?.closest('.form-row');
        const scheduledTab = document.getElementById('scheduled-tab');
        const modalActions = document.querySelector('.modal-actions');

        if (tabName === 'youtube') {
            // Hide elements when YouTube tab is active for better readability
            if (platformGroup) platformGroup.style.display = 'none';
            if (statusTypeRow) statusTypeRow.style.display = 'none';
            if (scheduledTab) scheduledTab.style.display = 'none';
            if (modalActions) modalActions.style.display = 'none';
        } else {
            // Show elements when Content Info tab is active
            // But respect the original visibility rules from populateFields
            const isActuallyScheduledOnYouTube = this.currentEvent?.youtube_video_id;

            if (isActuallyScheduledOnYouTube) {
                // Keep them hidden if actually scheduled on YouTube
                if (platformGroup) platformGroup.style.display = 'none';
                if (statusTypeRow) statusTypeRow.style.display = 'none';
                if (scheduledTab) scheduledTab.style.display = 'none';
                if (modalActions) modalActions.style.display = 'none';
            } else {
                // Show for regular content
                if (platformGroup) platformGroup.style.display = '';
                if (statusTypeRow) statusTypeRow.style.display = '';
                if (scheduledTab) scheduledTab.style.display = 'block';
                if (modalActions) modalActions.style.display = '';
            }
        }
    }

    handleStatusChange() {
        const scheduledTab = document.getElementById('scheduled-tab');
        const platformSelect = document.getElementById('platform-select');

        // Only hide scheduled tab if actually scheduled on YouTube (has video ID)
        const isActuallyScheduledOnYouTube = this.currentEvent && this.currentEvent.youtube_video_id;

        console.log('handleStatusChange called:', {
            currentEvent: this.currentEvent,
            isActuallyScheduledOnYouTube: isActuallyScheduledOnYouTube,
            scheduledTabExists: !!scheduledTab
        });

        // Show/hide scheduled tab based on whether it's actually scheduled on YouTube
        if (isActuallyScheduledOnYouTube) {
            // Hide for actually scheduled YouTube posts (they're in read-only mode)
            console.log('Hiding scheduled tab for scheduled YouTube post');
            scheduledTab.style.display = 'none';
        } else {
            // Always show the Publish Date tab for regular items (acts as deadline/target date for all statuses)
            console.log('Showing scheduled tab for regular content');
            scheduledTab.style.display = 'block';
        }

        // Lock platform ONLY if it's actually scheduled on the platform (has platform post ID - the "clock" icon)
        const isActuallyScheduled = this.currentEvent && (
            this.currentEvent.youtube_video_id ||
            this.currentEvent.instagram_post_id ||
            this.currentEvent.tiktok_post_id ||
            this.currentEvent.x_post_id
        );

        if (isActuallyScheduled) {
            platformSelect.disabled = true;
        } else {
            platformSelect.disabled = false;
        }
    }

    async addComment() {
        console.log('addComment called');
        const input = document.getElementById('comment-input');
        const text = input.value.trim();
        console.log('Comment text:', text);
        if (!text) return;

        // Add to beginning (newest first)
        this.comments.unshift({
            text: text,
            timestamp: new Date().toISOString()
        });

        console.log('Comments array:', this.comments);
        this.renderComments();
        input.value = '';

        // Auto-save comments if editing existing event
        if (this.currentEvent && this.currentEvent.id) {
            console.log('Auto-saving comment to event:', this.currentEvent.id);
            const eventData = {
                id: this.currentEvent.id,
                title: this.currentEvent.title,
                description: this.currentEvent.description || '',
                tags: this.currentEvent.tags || '',
                platform: this.currentEvent.platform,
                content_type: this.currentEvent.content_type,
                status: this.currentEvent.status,
                publish_date: this.currentEvent.publish_date,
                notes: JSON.stringify(this.comments)
            };

            if (this.onSave) {
                await this.onSave(eventData);
                console.log('Comment auto-saved');
            }
        }
    }

    renderComments() {
        const container = document.getElementById('comments-list');

        if (this.comments.length === 0) {
            container.innerHTML = '';
            return;
        }

        container.innerHTML = this.comments.map((comment, index) => {
            const date = new Date(comment.timestamp);
            const time = date.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            return `
                <div class="comment-item">
                    <div class="comment-content">
                        <div class="comment-time">${time}</div>
                        <div class="comment-text">${this.escapeHtml(comment.text)}</div>
                    </div>
                    <button class="comment-delete-btn" data-index="${index}">
                        <i class="ph ph-x"></i>
                    </button>
                </div>
            `;
        }).join('');

        // Attach delete handlers
        container.querySelectorAll('.comment-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt(e.currentTarget.dataset.index);
                this.deleteComment(index);
            });
        });
    }

    async deleteComment(index) {
        console.log('Deleting comment at index:', index);
        this.comments.splice(index, 1);
        this.renderComments();

        // Auto-save after deleting comment
        if (this.currentEvent && this.currentEvent.id) {
            console.log('Auto-saving after comment delete');
            const eventData = {
                id: this.currentEvent.id,
                title: this.currentEvent.title,
                description: this.currentEvent.description || '',
                tags: this.currentEvent.tags || '',
                platform: this.currentEvent.platform,
                content_type: this.currentEvent.content_type,
                status: this.currentEvent.status,
                publish_date: this.currentEvent.publish_date,
                notes: JSON.stringify(this.comments)
            };

            if (this.onSave) {
                await this.onSave(eventData);
                console.log('Comment deletion auto-saved');
            }
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    open(options = {}) {
        this.currentEvent = options.event || null;
        this.onSave = options.onSave || null;
        this.onDelete = options.onDelete || null;

        // Reset buttons to default state
        const saveBtn = document.getElementById('save-btn');
        const deleteBtn = document.getElementById('delete-btn');
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save';
        }
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = 'Delete Content';
        }

        if (this.currentEvent) {
            this.populateFields(this.currentEvent);
        } else {
            this.resetFields();
        }

        this.modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    close() {
        this.modal.classList.remove('active');
        document.body.style.overflow = '';

        // Reset all UI visibility states BEFORE clearing currentEvent
        const youtubeTabBtn = document.getElementById('youtube-tab-btn');
        const platformGroup = document.getElementById('platform-form-group');
        const statusTypeRow = document.querySelector('#status-select').closest('.form-row');
        const scheduledTab = document.getElementById('scheduled-tab');
        const modalActions = document.querySelector('.modal-actions');

        if (youtubeTabBtn) youtubeTabBtn.style.display = 'none';
        if (platformGroup) platformGroup.style.display = '';
        if (statusTypeRow) statusTypeRow.style.display = '';
        if (scheduledTab) scheduledTab.style.display = 'block';  // Explicitly show for new items
        if (modalActions) modalActions.style.display = '';

        // Reset to Content Info tab
        this.switchTab('original');

        // Clear currentEvent last
        this.currentEvent = null;
    }

    resetFields() {
        document.getElementById('platform-select').value = 'Not set';
        document.getElementById('platform-select').disabled = false;
        document.getElementById('content-field').value = '';
        document.getElementById('status-select').value = 'draft';
        document.getElementById('type-select').value = 'organic';
        this.comments = [];
        this.renderComments();

        // Ensure scheduled tab is visible for new items
        const scheduledTab = document.getElementById('scheduled-tab');
        if (scheduledTab) scheduledTab.style.display = 'block';

        this.handleStatusChange();
    }

    populateFields(event) {
        document.getElementById('platform-select').value = event.platform || 'Not set';
        document.getElementById('content-field').value = event.title || '';
        document.getElementById('status-select').value = event.status || 'ready';
        document.getElementById('type-select').value = event.content_type || 'organic';

        // Handle YouTube tab visibility and UI adjustments
        const youtubeTabBtn = document.getElementById('youtube-tab-btn');
        const youtubeTitleField = document.getElementById('youtube-title-field');
        const youtubeDescriptionField = document.getElementById('youtube-description-field');
        const youtubeTagsContainer = document.getElementById('youtube-tags-container');
        const platformGroup = document.getElementById('platform-form-group');
        const statusTypeRow = document.querySelector('#status-select').closest('.form-row');
        const scheduledTab = document.getElementById('scheduled-tab');
        const modalActions = document.querySelector('.modal-actions');

        // Show YouTube tab if YouTube metadata is available
        const hasYouTubeMetadata = !!(event.description || event.tags);

        if (hasYouTubeMetadata) {
            // Show YouTube tab
            youtubeTabBtn.style.display = 'flex';

            // Only hide UI elements if it's actually scheduled on YouTube (has video ID)
            const isActuallyScheduledOnYouTube = event.youtube_video_id;
            if (isActuallyScheduledOnYouTube) {
                if (platformGroup) platformGroup.style.display = 'none';
                if (statusTypeRow) statusTypeRow.style.display = 'none';
                if (scheduledTab) scheduledTab.style.display = 'none';
                if (modalActions) modalActions.style.display = 'none';
            }

            // Parse the video title from the description (format: "Video Title: <title>\n\n<description>")
            let videoTitle = event.title || '';
            let videoDescription = event.description || '';

            if (videoDescription.startsWith('Video Title: ')) {
                const parts = videoDescription.split('\n\n');
                videoTitle = parts[0].replace('Video Title: ', '');
                videoDescription = parts.slice(1).join('\n\n');
            }

            if (youtubeTitleField) youtubeTitleField.value = videoTitle;
            if (youtubeDescriptionField) youtubeDescriptionField.value = videoDescription;

            // Render tags as chips
            if (youtubeTagsContainer && event.tags) {
                const tagsArray = event.tags.split(',').map(tag => tag.trim()).filter(tag => tag);
                youtubeTagsContainer.innerHTML = tagsArray.map(tag =>
                    `<span class="youtube-tag-chip">${this.escapeHtml(tag)}</span>`
                ).join('');
            } else if (youtubeTagsContainer) {
                youtubeTagsContainer.innerHTML = '<span class="no-tags">No tags</span>';
            }
        } else {
            // Hide YouTube tab for regular items
            youtubeTabBtn.style.display = 'none';
            // Show all UI elements for non-scheduled posts
            if (platformGroup) platformGroup.style.display = '';
            if (statusTypeRow) statusTypeRow.style.display = '';
            if (scheduledTab) scheduledTab.style.display = 'block';  // Explicitly show
            if (modalActions) modalActions.style.display = '';
            // Make sure Original Info tab is active
            this.switchTab('original');
        }

        this.handleStatusChange();

        // Force disable platform field if actually scheduled (belt and suspenders approach)
        const isScheduledOnPlatform = !!(event.youtube_video_id ||
            event.instagram_post_id ||
            event.tiktok_post_id ||
            event.x_post_id);

        const platformSelectField = document.getElementById('platform-select');
        if (platformSelectField) {
            if (isScheduledOnPlatform) {
                platformSelectField.disabled = true;
                console.log('FORCE DISABLED platform select for scheduled post');
            } else {
                platformSelectField.disabled = false;
                console.log('Platform select enabled for non-scheduled post');
            }
        }

        if (event.publish_date) {
            console.log('Populating date from event.publish_date:', event.publish_date);
            const date = new Date(event.publish_date);
            const dateStr = date.toISOString().split('T')[0];
            const timeStr = date.toTimeString().slice(0, 5);
            console.log('Parsed dateStr:', dateStr, 'timeStr:', timeStr);

            setTimeout(() => {
                const dateSelect = document.getElementById('schedule-date');
                const timeSelect = document.getElementById('schedule-time');

                if (dateSelect) dateSelect.value = dateStr;
                if (timeSelect) timeSelect.value = timeStr;
                console.log('Set date select value:', dateSelect?.value, 'time select value:', timeSelect?.value);
            }, 100);
        }

        try {
            console.log('Loading comments from event.notes:', event.notes);
            if (event.notes) {
                // Try to parse as JSON (new format)
                const parsed = JSON.parse(event.notes);
                // Check if it's an array (comments format)
                if (Array.isArray(parsed)) {
                    this.comments = parsed;
                } else {
                    // Not an array, ignore old format
                    this.comments = [];
                }
            } else {
                this.comments = [];
            }
            console.log('Parsed comments:', this.comments);
        } catch (e) {
            // Not valid JSON, probably old format - ignore and start fresh
            console.log('Notes field contains old format, starting fresh');
            this.comments = [];
        }
        this.renderComments();
    }

    async save() {
        const platform = document.getElementById('platform-select').value;

        const content = document.getElementById('content-field').value.trim();
        if (!content) {
            alert('Please enter content');
            return;
        }

        const status = document.getElementById('status-select').value;
        let publishDate = null;

        // Check if publish date is set (optional for all statuses)
        const dateInput = document.getElementById('schedule-date');
        const timeInput = document.getElementById('schedule-time');

        if (dateInput.value && timeInput.value) {
            publishDate = `${dateInput.value}T${timeInput.value}`;
        }

        const eventData = {
            id: this.currentEvent?.id || null,
            title: content,
            description: '',
            tags: '',
            platform: platform,
            content_type: document.getElementById('type-select').value,
            status: status,
            publish_date: publishDate,
            notes: JSON.stringify(this.comments)
        };

        console.log('Saving event with comments:', this.comments);
        console.log('Event data:', eventData);

        const saveBtn = document.getElementById('save-btn');
        const originalText = saveBtn.textContent;

        // Show loading spinner
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<svg class="save-spinner" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" opacity="0.75"/></svg><span>Saving...</span>';

        try {
            if (this.onSave) {
                await this.onSave(eventData);
            }
            this.close();
        } catch (error) {
            console.error('Error saving:', error);
            // Restore button on error
            saveBtn.disabled = false;
            saveBtn.textContent = originalText;
        }
    }

    async deleteContent() {
        console.log('deleteContent called', this.currentEvent);

        if (!this.currentEvent || !this.currentEvent.id) {
            console.log('No current event or ID');
            alert('No content to delete');
            return;
        }

        const deleteBtn = document.getElementById('delete-btn');
        const originalText = deleteBtn.textContent;

        // Show loading spinner
        deleteBtn.disabled = true;
        deleteBtn.innerHTML = '<svg class="delete-spinner" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" opacity="0.25"/><path d="M12 2a10 10 0 0 1 10 10" opacity="0.75"/></svg><span>Deleting...</span>';

        console.log('Calling onDelete with ID:', this.currentEvent.id);
        try {
            if (this.onDelete) {
                await this.onDelete(this.currentEvent.id);
            } else {
                console.log('No onDelete handler');
            }
            this.close();
        } catch (error) {
            console.error('Error deleting:', error);
            // Restore button on error
            deleteBtn.disabled = false;
            deleteBtn.textContent = originalText;
        }
    }

    populateDateDropdown() {
        const select = document.getElementById('schedule-date');
        if (!select) return;

        select.innerHTML = '<option value="">Select Date</option>';

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

            const option = document.createElement('option');
            option.value = value;

            if (i === 0) {
                option.textContent = `Today - ${dayName}, ${monthName} ${day}`;
            } else if (i === 1) {
                option.textContent = `Tomorrow - ${dayName}, ${monthName} ${day}`;
            } else {
                option.textContent = `${dayName}, ${monthName} ${day}`;
            }

            select.appendChild(option);
        }
    }

    populateTimeDropdown() {
        const select = document.getElementById('schedule-time');
        if (!select) return;

        select.innerHTML = '<option value="">Select Time</option>';

        for (let hour = 0; hour < 24; hour++) {
            for (let minute = 0; minute < 60; minute += 15) {
                const hourStr = String(hour).padStart(2, '0');
                const minuteStr = String(minute).padStart(2, '0');
                const value = `${hourStr}:${minuteStr}`;

                const hour12 = hour % 12 || 12;
                const ampm = hour < 12 ? 'AM' : 'PM';

                const option = document.createElement('option');
                option.value = value;
                option.textContent = `${hour12}:${minuteStr} ${ampm}`;
                select.appendChild(option);
            }
        }
    }
}

window.ContentEventModal = ContentEventModal;

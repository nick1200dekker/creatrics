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
        this.isSubmittingComment = false;
        this.youtubeTags = [];
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
                                    <button class="content-tab" data-tab="tiktok" id="tiktok-tab-btn" style="display: none;">
                                        <i class="ph ph-tiktok-logo"></i>
                                        <span>TikTok Metadata</span>
                                    </button>
                                    <button class="content-tab" data-tab="x" id="x-tab-btn" style="display: none;">
                                        <i class="ph ph-x-logo"></i>
                                        <span>X Metadata</span>
                                    </button>
                                    <button class="content-tab" data-tab="instagram" id="instagram-tab-btn" style="display: none;">
                                        <i class="ph ph-instagram-logo"></i>
                                        <span>Instagram Metadata</span>
                                    </button>
                                </div>

                                <!-- Tab Content -->
                                <div class="content-tabs-body">
                                    <!-- Content Info Tab -->
                                    <div class="content-tab-panel active" data-panel="original">
                                        <div class="form-group">
                                            <label>Details</label>
                                            <textarea id="content-field" class="form-control" rows="4" placeholder="Enter details..."></textarea>
                                        </div>
                                    </div>

                                    <!-- YouTube Metadata Tab -->
                                    <div class="content-tab-panel" data-panel="youtube">
                                        <div class="form-group" id="youtube-video-preview" style="display: none;">
                                            <label>Video Preview</label>
                                            <video id="youtube-video-element" class="youtube-video-preview" controls></video>
                                        </div>
                                        <div class="form-group">
                                            <label>Video Title <span id="youtube-title-count" style="color: var(--text-tertiary); font-size: 0.875rem; font-weight: 400;"></span></label>
                                            <textarea id="youtube-title-field" class="form-control" rows="2" placeholder="Enter video title..." maxlength="100"></textarea>
                                        </div>
                                        <div class="form-group">
                                            <label>Description <span id="youtube-desc-count" style="color: var(--text-tertiary); font-size: 0.875rem; font-weight: 400;"></span></label>
                                            <textarea id="youtube-description-field" class="form-control" rows="8" placeholder="Enter video description..." maxlength="5000"></textarea>
                                        </div>
                                        <div class="form-group">
                                            <label>Tags <span id="youtube-tags-counter" style="color: var(--text-secondary); font-weight: 400; font-size: 0.8rem;">(0/500)</span></label>
                                            <div id="youtube-tags-container" class="youtube-tags-container"></div>
                                            <input type="text" id="youtube-tag-input" class="form-control" placeholder="Type a tag and press Enter..." style="margin-top: 0.5rem;">
                                        </div>
                                    </div>

                                    <!-- TikTok Metadata Tab -->
                                    <div class="content-tab-panel" data-panel="tiktok">
                                        <div class="form-group" id="tiktok-video-preview" style="display: none;">
                                            <label>Video Preview</label>
                                            <video id="tiktok-video-element" class="tiktok-video-preview" controls></video>
                                        </div>
                                        <div class="form-group">
                                            <label>Video Title / Caption</label>
                                            <textarea id="tiktok-title-field" class="form-control" rows="6" placeholder="Enter caption..."></textarea>
                                        </div>
                                    </div>

                                    <!-- X/Twitter Post Tab -->
                                    <div class="content-tab-panel" data-panel="x">
                                        <div class="form-group" id="x-media-gallery" style="display: none;">
                                            <label>Media Preview</label>
                                            <div id="x-media-container" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.375rem;"></div>
                                        </div>
                                        <div class="form-group">
                                            <label>Post Text</label>
                                            <textarea id="x-post-field" class="form-control" rows="8" readonly disabled></textarea>
                                        </div>
                                        <div class="form-group">
                                            <a href="#" id="x-edit-link" class="platform-edit-link" target="_blank" style="display: none;">
                                                <i class="ph ph-pencil-simple"></i>
                                                Edit in X Post Editor
                                            </a>
                                        </div>
                                    </div>

                                    <!-- Instagram Post Tab -->
                                    <div class="content-tab-panel" data-panel="instagram">
                                        <div class="form-group" id="instagram-media-gallery" style="display: none;">
                                            <label>Media Preview</label>
                                            <div id="instagram-media-container" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.375rem;"></div>
                                        </div>
                                        <div class="form-group">
                                            <label>Caption</label>
                                            <textarea id="instagram-caption-field" class="form-control" rows="8" placeholder="Enter caption..."></textarea>
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
                                    <span>Publish Date & Time</span>
                                    <span id="timezone-label" style="color: var(--text-tertiary); font-size: 0.875rem; font-weight: 400; margin-left: 0.5rem;"></span>
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
                                <input type="file" id="comment-image-input" accept="image/*" style="display: none;" />
                                <div class="comment-input-actions">
                                    <button id="attach-image-btn" class="comment-action-btn" title="Attach image">
                                        <i class="ph ph-image"></i>
                                    </button>
                                    <button id="send-comment" class="comment-send-btn">
                                        <i class="ph ph-paper-plane-right"></i>
                                    </button>
                                </div>
                            </div>
                            <div id="comment-image-preview" class="comment-image-preview" style="display: none;">
                                <img id="comment-preview-img" />
                                <button id="remove-comment-image" class="remove-preview-btn">
                                    <i class="ph ph-x"></i>
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
        const attachImageBtn = document.getElementById('attach-image-btn');
        const commentImageInput = document.getElementById('comment-image-input');
        const removeCommentImage = document.getElementById('remove-comment-image');

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

        // Image attachment handlers
        if (attachImageBtn) {
            attachImageBtn.onclick = () => {
                commentImageInput.click();
            };
        }
        if (commentImageInput) {
            commentImageInput.onchange = (e) => {
                this.handleImageSelect(e.target.files[0]);
            };
        }
        if (removeCommentImage) {
            removeCommentImage.onclick = () => {
                this.clearCommentImage();
            };
        }

        // Tab switching
        const tabButtons = document.querySelectorAll('.content-tab');
        tabButtons.forEach(btn => {
            btn.onclick = () => this.switchTab(btn.dataset.tab);
        });

        // YouTube tag input
        const youtubeTagInput = document.getElementById('youtube-tag-input');
        if (youtubeTagInput) {
            youtubeTagInput.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const tag = youtubeTagInput.value.trim();
                    if (tag) {
                        this.addYoutubeTag(tag);
                        youtubeTagInput.value = '';
                    }
                }
            };
        }

        // YouTube character counters
        const youtubeTitleField = document.getElementById('youtube-title-field');
        const youtubeDescField = document.getElementById('youtube-description-field');
        const youtubeTitleCount = document.getElementById('youtube-title-count');
        const youtubeDescCount = document.getElementById('youtube-desc-count');

        if (youtubeTitleField && youtubeTitleCount) {
            youtubeTitleField.oninput = () => {
                const count = youtubeTitleField.value.length;
                youtubeTitleCount.textContent = `(${count}/100)`;
            };
        }

        if (youtubeDescField && youtubeDescCount) {
            youtubeDescField.oninput = () => {
                const count = youtubeDescField.value.length;
                youtubeDescCount.textContent = `(${count}/5000)`;
            };
        }

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

        if (tabName === 'youtube' || tabName === 'tiktok' || tabName === 'x' || tabName === 'instagram') {
            // Hide elements when platform metadata tab is active for better readability
            if (platformGroup) platformGroup.style.display = 'none';
            if (statusTypeRow) statusTypeRow.style.display = 'none';
            if (scheduledTab) scheduledTab.style.display = 'none';
            if (modalActions) modalActions.style.display = 'none';
        } else {
            // Show elements when Content Info tab is active (for all posts, scheduled or not)
            if (platformGroup) platformGroup.style.display = '';
            if (statusTypeRow) statusTypeRow.style.display = '';
            if (scheduledTab) scheduledTab.style.display = 'block';
            if (modalActions) modalActions.style.display = '';
        }
    }

    handleStatusChange() {
        const scheduledTab = document.getElementById('scheduled-tab');
        const platformSelect = document.getElementById('platform-select');

        console.log('handleStatusChange called:', {
            currentEvent: this.currentEvent,
            scheduledTabExists: !!scheduledTab
        });

        // Always show the Publish Date tab for all posts (scheduled or not)
        console.log('Showing scheduled tab');
        if (scheduledTab) scheduledTab.style.display = 'block';

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

    handleImageSelect(file) {
        if (!file) return;

        // Validate file type
        if (!file.type.startsWith('image/')) {
            alert('Please select an image file');
            return;
        }

        // Validate file size (5MB limit)
        if (file.size > 5 * 1024 * 1024) {
            alert('Image must be smaller than 5MB');
            return;
        }

        this.selectedCommentImage = file;

        // Show preview
        const preview = document.getElementById('comment-image-preview');
        const previewImg = document.getElementById('comment-preview-img');

        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            preview.style.display = 'flex';
        };
        reader.readAsDataURL(file);
    }

    clearCommentImage() {
        this.selectedCommentImage = null;
        const preview = document.getElementById('comment-image-preview');
        const imageInput = document.getElementById('comment-image-input');

        preview.style.display = 'none';
        if (imageInput) imageInput.value = '';
    }

    async uploadCommentImage(file) {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('event_id', this.currentEvent.id);

        const response = await fetch('/content-calendar/api/upload-comment-image', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to upload image');
        }

        return data.image_url;
    }

    async addComment() {
        console.log('addComment called');

        // Prevent multiple submissions
        if (this.isSubmittingComment) {
            console.log('Comment submission already in progress');
            return;
        }

        const input = document.getElementById('comment-input');
        const text = input.value.trim();
        console.log('Comment text:', text);

        // Allow empty text if image is attached
        if (!text && !this.selectedCommentImage) return;

        // Set submitting state
        this.isSubmittingComment = true;

        // Disable send button and show loading state
        const sendBtn = document.getElementById('send-comment');
        const originalContent = sendBtn.innerHTML;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="ph ph-spinner" style="animation: spin 1s linear infinite;"></i>';

        let imageUrl = null;

        try {
            // Upload image if attached
            if (this.selectedCommentImage) {
                try {
                    imageUrl = await this.uploadCommentImage(this.selectedCommentImage);
                    console.log('Image uploaded:', imageUrl);
                } catch (error) {
                    console.error('Error uploading image:', error);
                    alert('Failed to upload image: ' + error.message);
                    return;
                }
            }

            // Add to beginning (newest first)
            this.comments.unshift({
                text: text,
                timestamp: new Date().toISOString(),
                image_url: imageUrl
            });

            console.log('Comments array:', this.comments);
            this.renderComments();
            input.value = '';
            this.clearCommentImage();

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
                    publish_date: this.getCurrentPublishDate(),
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    notes: JSON.stringify(this.comments)
                };

                if (this.onSave) {
                    await this.onSave(eventData);
                    console.log('Comment auto-saved');
                }
            }
        } finally {
            // Re-enable send button and restore icon
            this.isSubmittingComment = false;
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.innerHTML = originalContent;
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

            const imageHtml = comment.image_url
                ? `<div class="comment-image-wrapper"><img src="${comment.image_url}" class="comment-image" /></div>`
                : '';

            return `
                <div class="comment-item">
                    <div class="comment-content">
                        <div class="comment-time">${time}</div>
                        ${comment.text ? `<div class="comment-text">${this.escapeHtml(comment.text)}</div>` : ''}
                        ${imageHtml}
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
                publish_date: this.getCurrentPublishDate(),
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
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

    // Helper function to get current publish_date from inputs
    getCurrentPublishDate() {
        const dateInput = document.getElementById('schedule-date');
        const timeInput = document.getElementById('schedule-time');

        console.log('🔍 getCurrentPublishDate called:');
        console.log('  - dateInput:', dateInput);
        console.log('  - dateInput.value:', dateInput?.value);
        console.log('  - timeInput:', timeInput);
        console.log('  - timeInput.value:', timeInput?.value);

        if (dateInput && timeInput && dateInput.value && timeInput.value) {
            const result = `${dateInput.value}T${timeInput.value}`;
            console.log('  ✅ Returning from inputs:', result);
            return result;
        }

        const fallback = this.currentEvent?.publish_date || null;
        console.log('  ⚠️ Falling back to currentEvent.publish_date:', fallback);
        return fallback;
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

        // Update timezone display
        this.updateTimezoneLabel();

        this.modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    updateTimezoneLabel() {
        const timezoneLabel = document.getElementById('timezone-label');
        if (timezoneLabel) {
            const now = new Date();
            const offsetMinutes = -now.getTimezoneOffset();
            const offsetHours = Math.floor(Math.abs(offsetMinutes) / 60);
            const offsetMins = Math.abs(offsetMinutes) % 60;
            const offsetSign = offsetMinutes >= 0 ? '+' : '-';
            const offsetString = `GMT${offsetSign}${offsetHours}${offsetMins > 0 ? ':' + String(offsetMins).padStart(2, '0') : ''}`;
            timezoneLabel.textContent = `(${offsetString})`;
        }
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

        // Populate publish date FIRST (before tab visibility logic)
        if (event.publish_date) {
            console.log('Populating date from event.publish_date:', event.publish_date);
            const date = new Date(event.publish_date);
            const dateStr = date.toISOString().split('T')[0];
            const timeStr = date.toTimeString().slice(0, 5);
            console.log('Parsed dateStr:', dateStr, 'timeStr:', timeStr);

            const dateSelect = document.getElementById('schedule-date');
            const timeSelect = document.getElementById('schedule-time');

            if (dateSelect) dateSelect.value = dateStr;
            if (timeSelect) timeSelect.value = timeStr;
            console.log('Set date select value:', dateSelect?.value, 'time select value:', timeSelect?.value);
        }

        // Handle YouTube tab visibility and UI adjustments
        const youtubeTabBtn = document.getElementById('youtube-tab-btn');
        const youtubeTitleField = document.getElementById('youtube-title-field');
        const youtubeDescriptionField = document.getElementById('youtube-description-field');
        const youtubeTagsContainer = document.getElementById('youtube-tags-container');
        const platformGroup = document.getElementById('platform-form-group');
        const statusTypeRow = document.querySelector('#status-select').closest('.form-row');
        const scheduledTab = document.getElementById('scheduled-tab');
        const modalActions = document.querySelector('.modal-actions');

        // Show YouTube tab if YouTube post ID exists OR if it has YouTube-specific metadata
        const hasYouTubeMetadata = !!event.youtube_video_id || (event.platform === 'YouTube' && (event.description || event.tags));

        if (hasYouTubeMetadata) {
            // Show YouTube tab
            youtubeTabBtn.style.display = 'flex';

            // Parse the video title from the description (format: "Video Title: <title>\n\n<description>")
            let videoTitle = event.title || '';
            let videoDescription = event.description || '';

            if (videoDescription.startsWith('Video Title: ')) {
                const parts = videoDescription.split('\n\n');
                videoTitle = parts[0].replace('Video Title: ', '');
                videoDescription = parts.slice(1).join('\n\n');
            }

            if (youtubeTitleField) {
                youtubeTitleField.value = videoTitle;
                // Trigger character counter
                const titleCount = document.getElementById('youtube-title-count');
                if (titleCount) titleCount.textContent = `(${videoTitle.length}/100)`;
            }
            if (youtubeDescriptionField) {
                youtubeDescriptionField.value = videoDescription;
                // Trigger character counter
                const descCount = document.getElementById('youtube-desc-count');
                if (descCount) descCount.textContent = `(${videoDescription.length}/5000)`;
            }

            // Show video preview if media_url is available
            const videoPreview = document.getElementById('youtube-video-preview');
            const videoElement = document.getElementById('youtube-video-element');
            if (event.media_url && videoPreview && videoElement) {
                videoElement.src = event.media_url;
                videoPreview.style.display = 'block';
            } else if (videoPreview) {
                videoPreview.style.display = 'none';
            }

            // Load tags into editable tag list
            if (event.tags) {
                this.youtubeTags = event.tags.split(',').map(tag => tag.trim()).filter(tag => tag);
            } else {
                this.youtubeTags = [];
            }
            this.renderYoutubeTags();
        } else {
            // Hide YouTube tab for regular items
            youtubeTabBtn.style.display = 'none';
        }

        // Handle TikTok tab - similar to YouTube
        const tiktokTabBtn = document.getElementById('tiktok-tab-btn');
        const tiktokTitleField = document.getElementById('tiktok-title-field');

        // Show TikTok tab if TikTok post ID exists
        const hasTikTokMetadata = !!event.tiktok_post_id;

        if (hasTikTokMetadata) {
            // Show TikTok tab
            if (tiktokTabBtn) tiktokTabBtn.style.display = 'flex';

            // Populate TikTok metadata
            const tiktokTitle = event.description ? event.description.replace('Video Title: ', '') : '';
            if (tiktokTitleField) tiktokTitleField.value = tiktokTitle;

            // Show video preview if media_url is available
            const tiktokVideoPreview = document.getElementById('tiktok-video-preview');
            const tiktokVideoElement = document.getElementById('tiktok-video-element');
            if (event.media_url && tiktokVideoPreview && tiktokVideoElement) {
                tiktokVideoElement.src = event.media_url;
                tiktokVideoPreview.style.display = 'block';
            } else if (tiktokVideoPreview) {
                tiktokVideoPreview.style.display = 'none';
            }
        } else {
            // Hide TikTok tab for regular items
            if (tiktokTabBtn) tiktokTabBtn.style.display = 'none';
        }

        // Handle X/Twitter tab
        const xTabBtn = document.getElementById('x-tab-btn');
        const xPostField = document.getElementById('x-post-field');

        // Show X tab if X post ID exists
        const hasXMetadata = !!event.x_post_id;

        if (hasXMetadata) {
            // Show X tab
            if (xTabBtn) xTabBtn.style.display = 'flex';

            // Populate X metadata
            const xPostText = event.description ? event.description.replace('Post Text: ', '') : '';
            if (xPostField) xPostField.value = xPostText;

            // Set up edit link to X Post Editor
            const xEditLink = document.getElementById('x-edit-link');
            if (xEditLink) {
                // Check if notes contains Draft ID (string format)
                let draftId = null;
                if (event.notes && typeof event.notes === 'string' && event.notes.includes('Draft ID:')) {
                    const draftIdMatch = event.notes.match(/Draft ID:\s*(\S+)/);
                    if (draftIdMatch) {
                        draftId = draftIdMatch[1];
                    }
                }

                if (draftId) {
                    xEditLink.href = `/x_post_editor?draft=${draftId}`;
                    xEditLink.style.display = 'inline-flex';
                    console.log('X Post Editor link set to:', xEditLink.href);
                } else {
                    console.log('No draft ID found in notes:', event.notes);
                }
            }

            // Check if we have media_metadata (multiple media with types)
            let mediaItems = [];
            if (event.media_metadata) {
                try {
                    mediaItems = JSON.parse(event.media_metadata);
                } catch (e) {
                    console.error('Failed to parse media_metadata:', e);
                }
            }

            const xMediaGallery = document.getElementById('x-media-gallery');
            const xMediaContainer = document.getElementById('x-media-container');

            if (mediaItems.length > 0) {
                // Show media gallery with all media items
                if (xMediaGallery && xMediaContainer) {
                    xMediaContainer.innerHTML = '';

                    mediaItems.forEach(media => {
                        let mediaElement;
                        if (media.type === 'video') {
                            mediaElement = document.createElement('video');
                            mediaElement.controls = true;
                            mediaElement.style.width = '100%';
                            mediaElement.style.maxHeight = '300px';
                            mediaElement.style.borderRadius = '10px';
                            mediaElement.style.objectFit = 'contain';
                        } else {
                            mediaElement = document.createElement('img');
                            mediaElement.style.width = '100%';
                            mediaElement.style.maxHeight = '300px';
                            mediaElement.style.borderRadius = '10px';
                            mediaElement.style.objectFit = 'contain';
                        }
                        mediaElement.src = media.url;
                        xMediaContainer.appendChild(mediaElement);
                    });

                    xMediaGallery.style.display = 'block';
                    console.log(`X post showing ${mediaItems.length} media items`);
                }
            } else if (event.media_url && event.media_url.trim() !== '') {
                // Fallback to old media_url for backward compatibility
                console.log('X media_url (legacy):', event.media_url);
                if (xMediaGallery && xMediaContainer) {
                    xMediaContainer.innerHTML = '';

                    const isVideo = /\.(mp4|mov|avi|webm)(\?|$)/i.test(event.media_url);
                    let mediaElement;

                    if (isVideo) {
                        mediaElement = document.createElement('video');
                        mediaElement.controls = true;
                    } else {
                        mediaElement = document.createElement('img');
                    }

                    mediaElement.src = event.media_url;
                    mediaElement.style.width = '100%';
                    mediaElement.style.maxHeight = '300px';
                    mediaElement.style.borderRadius = '10px';
                    mediaElement.style.objectFit = 'contain';
                    xMediaContainer.appendChild(mediaElement);
                    xMediaGallery.style.display = 'block';
                }
            } else {
                if (xMediaGallery) xMediaGallery.style.display = 'none';
            }
        } else {
            // Hide X tab for regular items
            if (xTabBtn) xTabBtn.style.display = 'none';
        }

        // Handle Instagram tab
        const instagramTabBtn = document.getElementById('instagram-tab-btn');
        const instagramCaptionField = document.getElementById('instagram-caption-field');

        // Show Instagram tab if Instagram post ID exists
        const hasInstagramMetadata = !!event.instagram_post_id;

        if (hasInstagramMetadata) {
            // Show Instagram tab
            if (instagramTabBtn) instagramTabBtn.style.display = 'flex';

            // Populate Instagram metadata
            const instagramCaption = event.description ? event.description.replace('Caption: ', '') : '';
            if (instagramCaptionField) instagramCaptionField.value = instagramCaption;

            // Show media preview if media_metadata or media_url is available
            const instagramMediaGallery = document.getElementById('instagram-media-gallery');
            const instagramMediaContainer = document.getElementById('instagram-media-container');

            // Try to parse media_metadata first (new format)
            if (event.media_metadata) {
                console.log('Instagram media_metadata:', event.media_metadata);
                let mediaItems = [];
                try {
                    mediaItems = JSON.parse(event.media_metadata);
                } catch (e) {
                    console.error('Error parsing Instagram media_metadata:', e);
                }

                if (mediaItems.length > 0 && instagramMediaGallery && instagramMediaContainer) {
                    instagramMediaContainer.innerHTML = '';

                    mediaItems.forEach(media => {
                        let mediaElement;
                        if (media.type === 'video') {
                            mediaElement = document.createElement('video');
                            mediaElement.controls = true;
                        } else {
                            mediaElement = document.createElement('img');
                        }

                        mediaElement.src = media.url;
                        mediaElement.style.width = '100%';
                        mediaElement.style.maxHeight = '300px';
                        mediaElement.style.borderRadius = '10px';
                        mediaElement.style.objectFit = 'contain';
                        instagramMediaContainer.appendChild(mediaElement);
                    });

                    instagramMediaGallery.style.display = 'block';
                    console.log(`Instagram showing ${mediaItems.length} media items`);
                }
            } else if (event.media_url && event.media_url.trim() !== '') {
                // Fallback to old media_url for backward compatibility
                console.log('Instagram media_url (legacy):', event.media_url);
                if (instagramMediaGallery && instagramMediaContainer) {
                    instagramMediaContainer.innerHTML = '';

                    const isVideo = /\.(mp4|mov|avi|webm)(\?|$)/i.test(event.media_url);
                    let mediaElement;

                    if (isVideo) {
                        mediaElement = document.createElement('video');
                        mediaElement.controls = true;
                    } else {
                        mediaElement = document.createElement('img');
                    }

                    mediaElement.src = event.media_url;
                    mediaElement.style.width = '100%';
                    mediaElement.style.maxHeight = '300px';
                    mediaElement.style.borderRadius = '10px';
                    mediaElement.style.objectFit = 'contain';
                    instagramMediaContainer.appendChild(mediaElement);
                    instagramMediaGallery.style.display = 'block';
                }
            } else {
                if (instagramMediaGallery) instagramMediaGallery.style.display = 'none';
            }
        } else {
            // Hide Instagram tab for regular items
            if (instagramTabBtn) instagramTabBtn.style.display = 'none';
        }

        // Always show UI elements in Content Info tab
        // The switchTab function will hide them when viewing metadata tabs
        if (platformGroup) platformGroup.style.display = '';
        if (statusTypeRow) statusTypeRow.style.display = '';
        if (scheduledTab) scheduledTab.style.display = 'block';
        if (modalActions) modalActions.style.display = '';

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

    addYoutubeTag(tag) {
        if (!this.youtubeTags.includes(tag)) {
            this.youtubeTags.push(tag);
            this.renderYoutubeTags();
        }
    }

    removeYoutubeTag(tag) {
        this.youtubeTags = this.youtubeTags.filter(t => t !== tag);
        this.renderYoutubeTags();
    }

    renderYoutubeTags() {
        const container = document.getElementById('youtube-tags-container');
        if (!container) return;

        container.innerHTML = '';

        this.youtubeTags.forEach(tag => {
            const tagEl = document.createElement('span');
            tagEl.className = 'youtube-tag';

            const tagText = document.createTextNode(tag);
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'remove-tag';
            removeBtn.innerHTML = '<i class="ph ph-x"></i>';
            removeBtn.onclick = () => this.removeYoutubeTag(tag);

            tagEl.appendChild(tagText);
            tagEl.appendChild(removeBtn);
            container.appendChild(tagEl);
        });

        // Update character counter
        const totalChars = this.youtubeTags.join(',').length;
        const counter = document.getElementById('youtube-tags-counter');
        if (counter) {
            counter.textContent = `(${totalChars}/500)`;
            // Change color if approaching or exceeding limit
            if (totalChars > 500) {
                counter.style.color = '#ef4444'; // Red
            } else if (totalChars > 400) {
                counter.style.color = '#f59e0b'; // Orange
            } else {
                counter.style.color = 'var(--text-secondary)';
            }
        }
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
            console.log('📅 Modal publishDate created:', publishDate);
            console.log('  - dateInput.value:', dateInput.value);
            console.log('  - timeInput.value:', timeInput.value);
        }

        // Gather metadata from platform-specific tabs
        let description = '';
        let tags = '';

        // Check which platform has metadata and build description accordingly
        const youtubeTitle = document.getElementById('youtube-title-field')?.value.trim();
        const youtubeDescription = document.getElementById('youtube-description-field')?.value.trim();
        const tiktokCaption = document.getElementById('tiktok-title-field')?.value.trim();
        const instagramCaption = document.getElementById('instagram-caption-field')?.value.trim();

        if (youtubeTitle || youtubeDescription) {
            description = `Title: ${youtubeTitle}\nDescription: ${youtubeDescription}`;
            tags = this.youtubeTags.join(',');
        } else if (tiktokCaption) {
            description = `Caption: ${tiktokCaption}`;
        } else if (instagramCaption) {
            description = `Caption: ${instagramCaption}`;
        }
        // Note: X post text is read-only, edit in X Post Editor

        // Preserve Draft ID in notes if it exists
        let notesValue = JSON.stringify(this.comments);
        if (this.currentEvent && this.currentEvent.notes && typeof this.currentEvent.notes === 'string' && this.currentEvent.notes.includes('Draft ID:')) {
            // Keep the original notes with Draft ID for X posts
            notesValue = this.currentEvent.notes;
        }

        // Get user's timezone
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        const eventData = {
            id: this.currentEvent?.id || null,
            title: content,
            description: description,
            tags: tags,
            platform: platform,
            content_type: document.getElementById('type-select').value,
            status: status,
            publish_date: publishDate,
            timezone: userTimezone,
            notes: notesValue
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

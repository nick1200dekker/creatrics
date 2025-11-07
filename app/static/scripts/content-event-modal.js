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
                            <!-- Platform -->
                            <div class="form-group">
                                <label>Platform</label>
                                <select id="platform-select" class="form-control">
                                    <option value="">Select Platform</option>
                                    <option value="YouTube">YouTube</option>
                                    <option value="Instagram">Instagram</option>
                                    <option value="TikTok">TikTok</option>
                                    <option value="X">X</option>
                                </select>
                            </div>

                            <!-- Content -->
                            <div class="form-group">
                                <label>Requirements</label>
                                <textarea id="content-field" class="form-control" rows="4" placeholder="Enter requirements..."></textarea>
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

        console.log('Event listeners attached');
    }

    handleStatusChange() {
        const scheduledTab = document.getElementById('scheduled-tab');
        const platformSelect = document.getElementById('platform-select');

        // Always show the Publish Date tab (acts as deadline/target date for all statuses)
        scheduledTab.style.display = 'block';

        // Lock platform if it's a scheduled post (has publish_date)
        if (this.currentEvent && this.currentEvent.publish_date) {
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
            container.innerHTML = '<div class="no-comments">No comments yet</div>';
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
        this.currentEvent = null;
    }

    resetFields() {
        document.getElementById('platform-select').value = '';
        document.getElementById('platform-select').disabled = false;
        document.getElementById('content-field').value = '';
        document.getElementById('status-select').value = 'draft';
        document.getElementById('type-select').value = 'organic';
        this.comments = [];
        this.renderComments();
        this.handleStatusChange();
    }

    populateFields(event) {
        document.getElementById('platform-select').value = event.platform || '';
        document.getElementById('content-field').value = event.title || '';
        document.getElementById('status-select').value = event.status || 'ready';
        document.getElementById('type-select').value = event.content_type || 'organic';

        this.handleStatusChange();

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
        if (!platform) {
            alert('Please select a platform');
            return;
        }

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

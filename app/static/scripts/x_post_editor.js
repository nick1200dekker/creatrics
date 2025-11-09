// Keep the entire existing JavaScript from the original implementation
// Just copy-pasted from the original second document
(function() {
    'use strict';
    
    // Initialize namespace
    window.CreatorPal = window.CreatorPal || {};
    window.CreatorPal.PostEditor = window.CreatorPal.PostEditor || {};
    
    // Check if already initialized
    if (window.CreatorPal.PostEditor.initialized) {
        console.log('Post Editor already initialized, skipping...');
        return;
    }

    // File type configuration
    const SUPPORTED_MEDIA_TYPES = {
        image: {
            mimeTypes: ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'],
            maxSize: 10 * 1024 * 1024, // 10MB
            icon: 'ph-image',
            label: 'Image'
        },
        video: {
            mimeTypes: ['video/mp4', 'video/webm', 'video/quicktime', 'video/x-msvideo'],
            maxSize: 100 * 1024 * 1024, // 100MB
            icon: 'ph-video',
            label: 'Video'
        },
        gif: {
            mimeTypes: ['image/gif'],
            maxSize: 25 * 1024 * 1024, // 25MB
            icon: 'ph-gif',
            label: 'GIF'
        }
    };

    // App state
    const state = {
        enhancementPreset: 'keyword',
        additionalInstructions: '',
        postCount: 1,
        currentDraftId: null,
        hasUnsavedChanges: false,
        undoStack: [],
        maxUndoSteps: 20,
        saveTimeout: null,
        isLoadingDraft: false,
        currentOffset: 0,
        loadedCount: 0,
        isXConnected: false,
        xAccountInfo: null,
        hasPremium: window.hasPremium || false,
        totalCount: 0,
        hasMore: false,
        isLoadingMore: false,
        isCreatingDraft: false
    };

    // Schedule button retry counter
    let scheduleButtonRetryCount = 0;

    // Initialize function
    function initialize() {
        console.log('Initializing Post Editor...');

        // Start with fresh editor (no draft created yet)
        state.currentDraftId = null;
        state.hasUnsavedChanges = false;
        state.postCount = 0; // Reset post count to ensure we start with "Post" not "Post 2"

        setupEventListeners();
        setupInitialPost();
        setupKeyboardShortcuts();
        loadDraftsWithSpinner();

        // Initialize voice tone dropdown and its event listeners
        initializeVoiceTone().catch(console.error);
        setupVoiceToneEventListener();

        // Check for suggestion from dashboard
        checkForSuggestion();

        // Check for draft ID in URL parameters (e.g., ?draft=abc123)
        checkForDraftInUrl();

        updateStatusMessage('Ready to create content');

        window.CreatorPal.PostEditor.initialized = true;
        console.log('Post Editor initialized with fresh post');
    }

    // Check for draft ID in URL and load it
    function checkForDraftInUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        const draftId = urlParams.get('draft');

        if (draftId) {
            console.log(`Found draft ID in URL: ${draftId}, loading...`);
            // Wait a bit for drafts list to load, then select the draft
            setTimeout(() => {
                loadDraft(draftId);
                // Also highlight it in the drafts list
                const draftItem = document.querySelector(`[data-id="${draftId}"]`);
                if (draftItem) {
                    document.querySelectorAll('.draft-item').forEach(el => el.classList.remove('active'));
                    draftItem.classList.add('active');
                }
            }, 500);  // 500ms delay to ensure drafts list is loaded
        }
    }

    // Check for suggestion from dashboard
    function checkForSuggestion() {
        const suggestion = sessionStorage.getItem('x_post_suggestion');
        if (suggestion) {
            // Clear the storage
            sessionStorage.removeItem('x_post_suggestion');

            // Set the text in the first post
            setTimeout(() => {
                const firstTextarea = document.querySelector('.post-item textarea');
                if (firstTextarea) {
                    firstTextarea.value = suggestion;
                    // Trigger input event to update character count
                    firstTextarea.dispatchEvent(new Event('input', { bubbles: true }));
                    console.log('Loaded suggestion from dashboard');
                }
            }, 100);
        }
    }

    // Load drafts with spinner
    async function loadDraftsWithSpinner() {
        const draftsList = document.getElementById('draftsList');
        if (!draftsList) return;
        
        try {
            const response = await fetch('/x_post_editor/drafts?limit=10');
            const data = await response.json();
            
            if (data.success) {
                console.log('Drafts API response:', {
                    loaded_count: data.loaded_count,
                    total_count: data.total_count,
                    has_more: data.has_more,
                    drafts_length: data.drafts?.length || 0
                });
                
                state.currentOffset = data.loaded_count;
                state.loadedCount = data.loaded_count;
                state.totalCount = data.total_count;
                state.hasMore = data.has_more;
                
                renderDrafts(data.drafts || []);
                updateLoadMoreButton(); // Add this to show the button after initial load
            } else {
                console.log('Drafts API failed:', data);
                renderEmptyState();
            }
        } catch (error) {
            console.error('Error loading drafts:', error);
            renderEmptyState();
        }
    }

    // Render drafts
    function renderDrafts(drafts, append = false) {
        const draftsList = document.getElementById('draftsList');
        if (!draftsList) return;
        
        if (!drafts || drafts.length === 0) {
            if (!append) {
                renderEmptyState();
            }
            return;
        }

        let draftsHTML = '';
        drafts.forEach(draft => {
            const isActive = draft.id === state.currentDraftId;
            // Extract preview from posts - truncate to ~35 chars
            let preview = '';
            if (draft.posts && draft.posts.length > 0) {
                preview = draft.posts[0].text || '';
                // Truncate to first 35 characters
                if (preview.length > 35) {
                    preview = preview.substring(0, 35).trim() + '...';
                }
            }

            // Add scheduled icon if draft is scheduled
            const scheduledIcon = draft.is_scheduled ? '<i class="ph ph-clock draft-scheduled-icon" title="Scheduled"></i>' : '';

            // Don't show delete button for scheduled drafts
            const deleteButton = draft.is_scheduled ? '' : `
                <button class="draft-delete-btn" title="Delete Draft">
                    <i class="ph ph-trash"></i>
                </button>
            `;

            draftsHTML += `
                <div class="draft-item ${isActive ? 'active' : ''}" data-id="${draft.id}" data-scheduled="${draft.is_scheduled || false}">
                    <div class="draft-content">
                        <div class="draft-title">
                            ${scheduledIcon}
                            ${draft.title || 'Untitled Draft'}
                        </div>
                        ${preview ? `<div class="draft-preview">${escapeHtml(preview)}</div>` : ''}
                    </div>
                    ${deleteButton}
                </div>
            `;
        });
        
        if (append) {
            draftsList.insertAdjacentHTML('beforeend', draftsHTML);
        } else {
            draftsList.innerHTML = draftsHTML;
        }
        
        attachDraftEventListeners();
        updateLoadMoreButton();
    }

    // Load more drafts
    async function loadMoreDrafts() {
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        const loadMoreText = loadMoreBtn.querySelector('.load-more-text');
        const loadMoreSpinner = loadMoreBtn.querySelector('.load-more-spinner');
        
        try {
            // Show loading state
            loadMoreBtn.disabled = true;
            loadMoreText.style.display = 'none';
            loadMoreSpinner.style.display = 'flex';
            
            const response = await fetch(`/x_post_editor/drafts?offset=${state.loadedCount}&limit=10`);
            const data = await response.json();
            
            if (data.success && data.drafts && data.drafts.length > 0) {
                // Update state
                state.loadedCount = data.loaded_count;
                state.hasMore = data.has_more;
                
                // Append new drafts
                renderDrafts(data.drafts, true);
            }
        } catch (error) {
            console.error('Error loading more drafts:', error);
        } finally {
            // Reset loading state
            loadMoreBtn.disabled = false;
            loadMoreText.style.display = 'inline';
            loadMoreSpinner.style.display = 'none';
        }
    }
    
    // Update load more button visibility and text
    function updateLoadMoreButton() {
        const loadMoreContainer = document.getElementById('loadMoreContainer');
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        const loadMoreText = loadMoreBtn?.querySelector('.load-more-text');
        
        console.log('updateLoadMoreButton called - hasMore:', state.hasMore, 'loadedCount:', state.loadedCount, 'totalCount:', state.totalCount);
        
        if (!loadMoreContainer || !loadMoreBtn || !loadMoreText) {
            console.log('Missing elements for load more button');
            return;
        }
        
        if (state.hasMore && state.loadedCount > 0) {
            loadMoreContainer.style.display = 'block';
            loadMoreText.textContent = 'Load More';
            console.log('Showing load more button');
        } else {
            loadMoreContainer.style.display = 'none';
            console.log('Hiding load more button');
        }
    }

    // Render empty state
    function renderEmptyState() {
        const draftsList = document.getElementById('draftsList');
        if (!draftsList) return;
        
        draftsList.innerHTML = `
            <div class="drafts-empty">
                <i class="ph ph-files"></i>
                <div style="margin-bottom: 0.5rem; color: #6b7280;">No drafts yet</div>
            </div>
        `;
        
        // Hide load more button when empty
        const loadMoreContainer = document.getElementById('loadMoreContainer');
        if (loadMoreContainer) {
            loadMoreContainer.style.display = 'none';
        }
    }

    // Attach draft event listeners
    function attachDraftEventListeners() {
        document.querySelectorAll('.draft-item').forEach(item => {
            const draftId = item.dataset.id;

            // Click to load draft
            item.onclick = (e) => {
                if (e.target.closest('.draft-delete-btn')) return;

                // Prevent clicking when editing a scheduled post
                if (state.isEditingScheduled) {
                    showToast('Please finish editing or reload the page', 'warning');
                    return;
                }

                document.querySelectorAll('.draft-item').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                state.currentDraftId = draftId;

                loadDraft(draftId);
            };

            // Delete button
            const deleteBtn = item.querySelector('.draft-delete-btn');
            if (deleteBtn) {
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();

                    // Prevent deleting when editing a scheduled post
                    if (state.isEditingScheduled) {
                        showToast('Please finish editing or reload the page', 'warning');
                        return;
                    }

                    deleteDraft(draftId, item);
                };
            }

            // Add disabled styling when in edit mode
            if (state.isEditingScheduled) {
                item.style.opacity = '0.5';
                item.style.pointerEvents = 'none';
            } else {
                item.style.opacity = '';
                item.style.pointerEvents = '';
            }
        });
    }

    // Setup initial post
    function setupInitialPost() {
        const postsContainer = document.getElementById('postsContainer');
        if (postsContainer) {
            // Clear any existing posts first
            postsContainer.innerHTML = '';
            state.postCount = 0;
            // Add exactly one post
            addNewPost();
        }
    }

    /**
     * Update action buttons visibility based on:
     * - Single post: Show both schedule and "Post to X" buttons
     * - Thread (multiple posts): Show only schedule button on last post
     * - If any post > 280 chars: Show only "Post to X" button (hide schedule)
     * - Schedule button requires: premium, connected, all posts <= 280 chars
     */
    function updateActionButtons() {
        const posts = document.querySelectorAll('.post-item');
        const totalPosts = posts.length;

        // Check if any post exceeds 280 characters
        let anyPostOver280 = false;
        posts.forEach(post => {
            const textarea = post.querySelector('.post-editor-textarea');
            if (textarea && textarea.value.length > 280) {
                anyPostOver280 = true;
            }
        });

        // Hide all buttons first
        posts.forEach(post => {
            const scheduleBtn = post.querySelector('.schedule-x-btn');
            const postToXBtn = post.querySelector('.post-to-x-btn');
            if (scheduleBtn) scheduleBtn.style.display = 'none';
            if (postToXBtn) postToXBtn.style.display = 'none';
        });

        // Show buttons only on the last post
        const lastPost = posts[posts.length - 1];
        if (!lastPost) return;

        const scheduleBtn = lastPost.querySelector('.schedule-x-btn');
        const postToXBtn = lastPost.querySelector('.post-to-x-btn');

        // Single post (not a thread)
        if (totalPosts === 1) {
            // Show "Post to X" button
            if (postToXBtn) postToXBtn.style.display = 'inline-flex';

            // Show schedule button only if no post over 280 chars
            if (scheduleBtn && !anyPostOver280) {
                scheduleBtn.style.display = 'inline-flex';
                // Check premium and connection status
                updateScheduleButtonVisibility();
            }
        }
        // Thread (multiple posts)
        else {
            // Never show "Post to X" button in threads
            if (postToXBtn) postToXBtn.style.display = 'none';

            // Show schedule button only if no post over 280 chars
            if (scheduleBtn && !anyPostOver280) {
                scheduleBtn.style.display = 'inline-flex';
                // Check premium and connection status
                updateScheduleButtonVisibility();
            }
        }
    }

    // Add new post
    function addNewPost() {
        const postsContainer = document.getElementById('postsContainer');
        if (!postsContainer) return;

        state.postCount++;
        const isFirstPost = state.postCount === 1;

        const newPost = document.createElement('div');
        newPost.className = 'post-item';
        newPost.innerHTML = `
            <div class="post-item-header">
                <div class="post-type">
                    <i class="ph ph-note-pencil"></i>
                    <span>${isFirstPost ? 'Post' : `Post ${state.postCount}`}</span>
                </div>
                <div class="post-actions">
                    ${isFirstPost ? `
                    <button class="post-action repost-trigger" title="Repost Content">
                        <i class="ph ph-recycle"></i>
                    </button>
                    <button class="post-action media-upload-trigger" title="Add Media">
                        <i class="ph ph-paperclip"></i>
                    </button>` : ''}
                    ${!isFirstPost ? `
                    <button class="post-action delete-post" title="Delete">
                        <i class="ph ph-trash"></i>
                    </button>` : ''}
                </div>
            </div>
            <div class="post-editor-content">
                <textarea class="post-editor-textarea" placeholder="${isFirstPost ? 'Start typing your post here...' : 'Continue your thread...'}"></textarea>
                <div class="post-media"></div>
                ${isFirstPost ? `<input type="file" class="hidden-file-input" accept="image/*,video/*,.gif">` : ''}
            </div>
            <div class="post-footer">
                <div class="character-count">
                    <span class="character-count-text">0/280</span>
                    <div class="add-post-icon">
                        <i class="ph ph-plus"></i>
                    </div>
                </div>
                <div class="post-footer-actions">
                    <button class="schedule-x-btn" style="display: none;">
                        <i class="ph ph-calendar-plus"></i>
                        Schedule
                    </button>
                    <button class="post-to-x-btn" style="display: none;">
                        <i class="ph ph-paper-plane-right"></i>
                        Post to X
                    </button>
                </div>
            </div>
        `;

        postsContainer.appendChild(newPost);
        setupPostEventListeners(newPost);
        updateActionButtons();

        return newPost;
    }

    // Setup post event listeners
    function setupPostEventListeners(postElement) {
        const textarea = postElement.querySelector('.post-editor-textarea');
        const fileInput = postElement.querySelector('.hidden-file-input');
        const uploadTrigger = postElement.querySelector('.media-upload-trigger');
        const repostTrigger = postElement.querySelector('.repost-trigger');
        const deleteBtn = postElement.querySelector('.delete-post');
        const addPostIcon = postElement.querySelector('.add-post-icon');
        
        if (textarea) {
            textarea.oninput = function() {
                updateCharacterCount(this);
                if (!state.isLoadingDraft) {
                    markAsChanged();
                }
            };
        }
        
        if (fileInput && uploadTrigger) {
            uploadTrigger.onclick = () => fileInput.click();
            fileInput.onchange = async function() {
                if (this.files && this.files[0]) {
                    await handleFileUpload(this.files[0], postElement.querySelector('.post-media'));
                    this.value = '';
                    markAsChanged();
                }
            };
        }

        if (repostTrigger) {
            repostTrigger.onclick = () => {
                openRepostModal();
            };
        }

        if (deleteBtn) {
            deleteBtn.onclick = () => {
                postElement.remove();
                reorderPosts();
                markAsChanged();
            };
        }
        
        if (addPostIcon) {
            addPostIcon.onclick = () => {
                const newPost = addNewPost();
                const newTextarea = newPost.querySelector('.post-editor-textarea');
                if (newTextarea) newTextarea.focus();
                markAsChanged();
            };
        }
    }

    // Setup event listeners
    function setupEventListeners() {
        // Search
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', function(e) {
                filterDrafts(e.target.value);
            });
        }

        // Load More button
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        if (loadMoreBtn) {
            loadMoreBtn.addEventListener('click', loadMoreDrafts);
        }

        // Category buttons (Create/Improve/Correct)
        const categoryBtns = document.querySelectorAll('.category-btn');
        categoryBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const category = this.getAttribute('data-category');

                // Update active category button
                categoryBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                // Show relevant options container
                document.querySelectorAll('.options-container').forEach(container => {
                    container.classList.remove('active');
                });
                const activeContainer = document.querySelector(`.options-container[data-category="${category}"]`);
                if (activeContainer) {
                    activeContainer.classList.add('active');

                    // Auto-select first visible option
                    const firstOption = activeContainer.querySelector('.option-btn:not([style*="display: none"])');
                    if (firstOption) {
                        // Remove active from all options
                        document.querySelectorAll('.option-btn').forEach(opt => opt.classList.remove('active'));
                        firstOption.classList.add('active');
                        state.enhancementPreset = firstOption.getAttribute('data-preset');
                        markAsChanged();
                    }
                }
            });
        });

        // Option buttons (Braindump, Hook, Storytelling, etc.)
        const optionBtns = document.querySelectorAll('.option-btn');
        optionBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const preset = this.getAttribute('data-preset');

                // Update active option button
                optionBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                state.enhancementPreset = preset;
                markAsChanged();
            });
        });
        
        // Context modal
        const contextButton = document.getElementById('context-button');
        const contextModal = document.getElementById('context-modal');
        const contextModalClose = document.getElementById('context-modal-close');
        const contextTextarea = document.getElementById('context-textarea');
        const contextCancelButton = document.getElementById('context-cancel-button');
        const contextSaveButton = document.getElementById('context-save-button');
        
        if (contextButton) {
            contextButton.onclick = () => {
                if (contextModal) contextModal.style.display = 'flex';
            };
        }
        
        if (contextModalClose) {
            contextModalClose.onclick = () => {
                if (contextModal) contextModal.style.display = 'none';
            };
        }
        
        if (contextCancelButton) {
            contextCancelButton.onclick = () => {
                if (contextModal) contextModal.style.display = 'none';
            };
        }
        
        if (contextSaveButton) {
            contextSaveButton.onclick = () => {
                if (contextTextarea) {
                    state.additionalInstructions = contextTextarea.value;
                }
                if (contextModal) contextModal.style.display = 'none';
                markAsChanged();
                
                if (contextButton && state.additionalInstructions.trim() !== '') {
                    contextButton.classList.add('active');
                } else if (contextButton) {
                    contextButton.classList.remove('active');
                }
            };
        }
        
        // Generate button
        const generateButton = document.getElementById('generate-button');
        if (generateButton) {
            generateButton.onclick = handleGenerate;
        }
        
        // Revert button
        const revertButton = document.getElementById('revert-button');
        if (revertButton) {
            revertButton.onclick = performUndo;
        }
        
        // New Draft Button
        const newDraftButton = document.getElementById('new-draft-button');
        if (newDraftButton) {
            newDraftButton.onclick = createNewDraft;
        }
        

        // Close modal on background click
        if (contextModal) {
            contextModal.onclick = (e) => {
                if (e.target === contextModal) {
                    contextModal.style.display = 'none';
                }
            };
        }
    }

    // All other functions remain exactly the same as in the original
    // Just copy all the remaining functions from the original implementation
    
    // Load draft
    async function loadDraft(draftId) {
        // Prevent draft switching when editing a scheduled post
        if (state.isEditingScheduled) {
            showToast('Please finish editing or reload the page', 'warning');
            return;
        }

        state.isLoadingDraft = true;

        try {
            const response = await fetch(`/x_post_editor/drafts/${draftId}`);
            const data = await response.json();

            if (data.success) {
                const draft = data.draft;

                // Store current voice tone before clearing
                const savedVoiceTone = currentVoiceTone;

                // Clear and load posts
                clearEditor();

                // Clear any edit mode state
                state.isEditingScheduled = false;

                // Remove any existing banners
                const scheduledBanner = document.getElementById('scheduledBanner');
                if (scheduledBanner) {
                    scheduledBanner.remove();
                }
                const editingBanner = document.getElementById('editingScheduledBanner');
                if (editingBanner) {
                    editingBanner.remove();
                }

                if (draft.posts && Array.isArray(draft.posts)) {
                    loadPostsArray(draft.posts);
                }

                state.enhancementPreset = draft.preset || 'storytelling';
                state.additionalInstructions = draft.additional_context || '';

                // Store scheduled info in state
                state.isScheduled = draft.is_scheduled || draft.scheduled || false;
                state.calendarEventId = draft.calendar_event_id || null;
                state.scheduledPostId = draft.late_dev_post_id || draft.scheduled_post_id || null;
                state.scheduledTime = draft.scheduled_time || null;

                // Debug logging
                console.log('📋 Loading draft scheduled info:', {
                    is_scheduled: draft.is_scheduled,
                    late_dev_post_id: draft.late_dev_post_id,
                    scheduled_post_id: draft.scheduled_post_id,
                    scheduled_time: draft.scheduled_time,
                    final_scheduledPostId: state.scheduledPostId
                });

                // Check if draft is scheduled
                if (state.isScheduled) {
                    showScheduledDraftUI(draft);
                }

                // Update UI
                updateUIFromState();

                // Restore voice tone after UI update
                if (savedVoiceTone) {
                    selectVoiceTone(savedVoiceTone);
                }

                updateStatusMessage(`Loaded: "${draft.title || 'Untitled'}"`);
                state.hasUnsavedChanges = false;
            }
        } catch (error) {
            console.error('Error loading draft:', error);
            showToast('Failed to load draft', 'error');
        } finally {
            state.isLoadingDraft = false;
        }
    }

    // Create new draft
    async function createNewDraft() {
        if (state.hasUnsavedChanges) {
            await saveContent();
        }

        try {
            const response = await fetch('/x_post_editor/drafts/new', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'New Draft' })
            });

            const data = await response.json();

            if (data.success) {
                state.currentDraftId = data.draft_id;

                // Reset scheduled state
                state.isScheduled = false;
                state.scheduledTime = null;
                state.calendarEventId = null;
                state.isEditingScheduled = false;

                // Remove scheduled/editing banners
                const scheduledBanner = document.getElementById('scheduledBanner');
                if (scheduledBanner) scheduledBanner.remove();
                const editingBanner = document.getElementById('editingScheduledBanner');
                if (editingBanner) editingBanner.remove();

                clearEditor();
                setupInitialPost();

                document.querySelectorAll('.draft-item').forEach(item => item.classList.remove('active'));

                updateStatusMessage('New draft created');
                loadDraftsWithSpinner();
            }
        } catch (error) {
            console.error('Error creating draft:', error);
            showToast('Failed to create new draft', 'error');
        }
    }

    // Create new draft silently (without UI changes)
    async function createNewDraftSilently() {
        try {
            const response = await fetch('/x_post_editor/drafts/new', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'New Draft' })
            });
            
            const data = await response.json();
            
            if (data.success) {
                state.currentDraftId = data.draft_id;
                updateStatusMessage('Auto-saved as new draft');
                
                // Refresh drafts list to show the new draft
                loadDraftsWithSpinner();
                
                return true;
            }
        } catch (error) {
            console.error('Error creating draft silently:', error);
            return false;
        }
        return false;
    }

    // Delete draft
    async function deleteDraft(draftId, draftItem) {
        try {
            const response = await fetch(`/x_post_editor/drafts/${draftId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                draftItem.remove();
                
                if (state.currentDraftId === draftId) {
                    state.currentDraftId = null;
                    clearEditor();
                    updateStatusMessage('Ready to create content');
                }
                
                // Check if we need to show empty state in drafts list
                const remainingDrafts = document.querySelectorAll('.draft-item');
                if (remainingDrafts.length === 0) {
                    renderEmptyState();
                }
                
                showToast('Draft deleted', 'success');
            }
        } catch (error) {
            console.error('Error deleting draft:', error);
            showToast('Failed to delete draft', 'error');
        }
    }

    // Handle generate
    async function handleGenerate() {
        const brandVoiceToggle = document.getElementById('use-brand-voice');
        const posts = gatherPostData();
        
        if (!posts.some(post => post.text.trim() !== '')) {
            showToast('Please enter some content to enhance', 'error');
            return;
        }
        
        saveUndoState();
        
        const generateButton = document.getElementById('generate-button');
        const buttonIcon = generateButton?.querySelector('.button-icon');
        const buttonSpinner = generateButton?.querySelector('.button-spinner');
        const buttonText = generateButton?.querySelector('.button-text');

        if (generateButton) {
            generateButton.disabled = true;
            generateButton.style.opacity = '0.7';
            generateButton.style.cursor = 'not-allowed';
            if (buttonIcon) buttonIcon.style.display = 'none';
            if (buttonSpinner) buttonSpinner.style.display = 'inline-block';
            if (buttonText) buttonText.textContent = 'Enhancing...';
        }
        
        try {
            const response = await fetch('/x_post_editor/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    posts: posts,
                    preset: state.enhancementPreset,
                    additional_context: state.additionalInstructions,
                    voice_tone: getSelectedVoiceTone(),
                    custom_voice_posts: getCustomVoiceData()
                })
            });
            
            const data = await response.json();

            if (data.success) {
                const postItems = document.querySelectorAll('.post-item');
                data.enhanced_posts.forEach((enhancedText, index) => {
                    if (postItems[index]) {
                        const textarea = postItems[index].querySelector('.post-editor-textarea');
                        if (textarea) {
                            textarea.value = enhancedText;
                            updateCharacterCount(textarea);
                        }
                    }
                });

                markAsChanged();
                updateStatusMessage('Enhanced successfully');
                showToast('Content enhanced! ✨', 'success');
            } else {
                // Check for insufficient credits
                if (data.error_type === 'insufficient_credits') {
                    showInsufficientCreditsModal();
                    return;
                }
                showToast('Enhancement failed: ' + data.error, 'error');
            }
        } catch (error) {
            console.error('Generate error:', error);
            showToast('Failed to enhance content', 'error');
        } finally {
            if (generateButton) {
                generateButton.disabled = false;
                generateButton.style.opacity = '';
                generateButton.style.cursor = '';
                if (buttonIcon) buttonIcon.style.display = 'inline-block';
                if (buttonSpinner) buttonSpinner.style.display = 'none';
                if (buttonText) buttonText.textContent = 'Enhance';
            }
        }
    }

    // Voice Tone Management - Custom Dropdown
    let voiceToneTrigger = null;
    let voiceToneMenu = null;
    let selectedVoiceTone = null;
    let customVoices = [];
    let connectedUsername = (window.userXAccount || '').replace('@', '') || null;
    let currentVoiceTone = 'standard';
    let voiceEventListenersSetup = false;

    console.log('Connected username:', connectedUsername); // Debug log

    // Load custom voices from Firebase
    async function loadCustomVoices() {
        try {
            const response = await fetch('/x_post_editor/custom-voices');
            const data = await response.json();
            if (data.success) {
                customVoices = data.voices || [];
            } else {
                customVoices = [];
            }
        } catch (error) {
            console.error('Error loading custom voices:', error);
            customVoices = [];
        }
    }

    // Initialize voice tone dropdown
    async function initializeVoiceTone() {
        console.log('Initializing voice tone dropdown...'); // Debug log

        // Get DOM elements
        voiceToneTrigger = document.getElementById('voice-tone-trigger');
        voiceToneMenu = document.getElementById('voice-tone-menu');
        selectedVoiceTone = document.getElementById('selected-voice-tone');

        if (!voiceToneMenu || !voiceToneTrigger || !selectedVoiceTone) {
            console.error('Voice tone dropdown elements not found!'); // Debug log
            return;
        }

        // Load custom voices first
        await loadCustomVoices();
        console.log('Loaded custom voices:', customVoices); // Debug log

        // Clear existing options
        voiceToneMenu.innerHTML = '';

        // Add standard option
        const standardOption = createDropdownOption('standard', 'Creatrics');
        voiceToneMenu.appendChild(standardOption);

        // Add connected account option if available
        if (connectedUsername) {
            console.log('Adding connected username:', connectedUsername); // Debug log
            const connectedOption = createDropdownOption('connected', connectedUsername);
            voiceToneMenu.appendChild(connectedOption);
        }

        // Add custom voice options
        customVoices.forEach(voice => {
            console.log('Adding custom voice:', voice.username); // Debug log
            const customOption = createDropdownOption(`custom:${voice.username}`, voice.username);
            voiceToneMenu.appendChild(customOption);
        });

        // Add divider if there are custom options
        if (customVoices.length > 0 || connectedUsername) {
            const divider = document.createElement('div');
            divider.className = 'dropdown-divider';
            voiceToneMenu.appendChild(divider);
        }

        // Add "Add Custom Voice" option
        const addOption = createDropdownOption('add_custom', '+ Add Custom Voice');
        addOption.classList.add('add-custom');
        voiceToneMenu.appendChild(addOption);

        // Add remove options for each custom voice
        customVoices.forEach(voice => {
            const removeOption = createDropdownOption(`remove:${voice.username}`, `🗑️ Remove ${voice.username}`);
            removeOption.classList.add('remove-voice');
            voiceToneMenu.appendChild(removeOption);
        });

        // Restore selected value (but not if it's an action)
        const savedTone = localStorage.getItem('selectedVoiceTone') || 'standard';
        if (!savedTone.startsWith('add_custom') && !savedTone.startsWith('remove:')) {
            selectVoiceTone(savedTone);
            // Initialize Mimic button visibility
            toggleMimicButton(savedTone);
        }

        console.log('Voice tone dropdown initialized'); // Debug log
    }

    // Helper function to create dropdown option
    function createDropdownOption(value, text) {
        const option = document.createElement('div');
        option.className = 'dropdown-option';
        option.dataset.value = value;
        option.textContent = text;
        return option;
    }

    // Helper function to select a voice tone
    function selectVoiceTone(value) {
        currentVoiceTone = value;

        // Update selected text
        const allOptions = voiceToneMenu.querySelectorAll('.dropdown-option');
        allOptions.forEach(opt => {
            if (opt.dataset.value === value) {
                opt.classList.add('selected');
                selectedVoiceTone.textContent = opt.textContent.replace('🗑️ Remove ', '');
            } else {
                opt.classList.remove('selected');
            }
        });

        // Close dropdown
        voiceToneTrigger.classList.remove('active');
        voiceToneMenu.classList.remove('active');
    }

    // Show custom voice modal
    function showCustomVoiceModal() {
        // Remove any existing modal first to prevent duplicates
        const existingModal = document.querySelector('.custom-voice-modal');
        if (existingModal) {
            existingModal.remove();
        }

        const modal = document.createElement('div');
        modal.className = 'custom-voice-modal show';
        modal.innerHTML = `
            <div class="custom-voice-content">
                <div class="custom-voice-header">
                    <h3>Add Custom Voice</h3>
                </div>
                <div class="custom-voice-body">
                    <label class="form-label">X Username</label>
                    <input type="text"
                           class="custom-voice-input"
                           id="custom-voice-username"
                           placeholder="username (without @)"
                           value="">
                </div>
                <div class="custom-voice-footer">
                    <button class="modal-btn cancel" id="cancel-voice-modal">Cancel</button>
                    <button class="modal-btn save" id="save-voice-modal">Save Voice</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        const input = document.getElementById('custom-voice-username');
        input.focus();

        // Add cancel button click handler
        const cancelBtn = document.getElementById('cancel-voice-modal');
        if (cancelBtn) {
            cancelBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                modal.remove();
            };
        }

        // Add save button click handler
        const saveBtn = document.getElementById('save-voice-modal');
        if (saveBtn) {
            saveBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                saveCustomVoice();
            };
        }

        // Add Enter key support
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                saveCustomVoice();
            }
        });

        // Add Escape key support
        modal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                e.stopPropagation();
                modal.remove();
            }
        });

        // Add click outside to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    // Save custom voice
    async function saveCustomVoice() {
        const modal = document.querySelector('.custom-voice-modal');
        const input = document.getElementById('custom-voice-username');
        
        if (!input) {
            showToast('Input field not found', 'error');
            return;
        }
        
        const username = input.value.trim().replace('@', '');

        if (!username || username.length === 0) {
            showToast('Please enter a username', 'error');
            input.focus();
            return;
        }

        // Disable the save button to prevent double clicks
        const saveBtn = modal.querySelector('.modal-btn.save');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving...';
        }

        // Fetch and save posts
        const success = await fetchCustomVoicePosts(username);
        if (success) {
            localStorage.setItem('selectedVoiceTone', `custom:${username}`);
            await initializeVoiceTone();
            modal.remove();
            showToast(`Added ${username} as custom voice`, 'success');
        } else {
            // Re-enable button on failure
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Save Voice';
            }
        }
    }

    // Fetch custom voice posts
    async function fetchCustomVoicePosts(username) {
        try {
            const response = await fetch('/x_post_editor/fetch-x-posts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username })
            });

            const data = await response.json();
            if (data.success && data.posts) {
                return true;
            } else {
                showToast(data.error || 'Failed to fetch posts', 'error');
                return false;
            }
        } catch (error) {
            console.error('Error fetching custom voice posts:', error);
            showToast('Failed to fetch posts', 'error');
            return false;
        }
    }

    // Delete custom voice
    async function deleteCustomVoice(username) {
        try {
            const response = await fetch(`/x_post_editor/custom-voices/${username}`, {
                method: 'DELETE'
            });

            const data = await response.json();
            if (data.success) {
                // Reset selection if this voice was selected
                const currentSelection = localStorage.getItem('selectedVoiceTone');
                if (currentSelection === `custom:${username}`) {
                    localStorage.setItem('selectedVoiceTone', 'standard');
                }
                
                await initializeVoiceTone();
                showToast(`Removed ${username} from voice options`, 'success');
            } else {
                showToast(data.error || 'Failed to delete voice', 'error');
            }
        } catch (error) {
            console.error('Error deleting custom voice:', error);
            showToast('Failed to delete voice', 'error');
        }
    }

    // Get selected voice tone
    function getSelectedVoiceTone() {
        // Handle different voice tone formats
        if (currentVoiceTone.startsWith('custom:')) {
            return 'custom';
        } else if (currentVoiceTone === 'connected') {
            return 'connected';
        } else {
            return currentVoiceTone || 'standard';
        }
    }

    // Get custom voice data
    function getCustomVoiceData() {
        // If custom voice is selected, return the username
        if (currentVoiceTone.startsWith('custom:')) {
            return currentVoiceTone.replace('custom:', '');
        }

        return null;
    }

    // Setup voice tone event listeners
    function setupVoiceToneEventListener() {
        // Prevent duplicate listener setup
        if (voiceEventListenersSetup) return;
        voiceEventListenersSetup = true;

        // Dropdown toggle
        if (voiceToneTrigger) {
            voiceToneTrigger.addEventListener('click', (e) => {
                e.stopPropagation();
                voiceToneTrigger.classList.toggle('active');
                voiceToneMenu.classList.toggle('active');
            });
        }

        // Option click handler
        if (voiceToneMenu) {
            voiceToneMenu.addEventListener('click', async (e) => {
                const option = e.target.closest('.dropdown-option');
                if (!option) return;

                const selectedValue = option.dataset.value;

                if (selectedValue === 'add_custom') {
                    // Show modal to add custom voice
                    showCustomVoiceModal();
                    // Close dropdown
                    voiceToneTrigger.classList.remove('active');
                    voiceToneMenu.classList.remove('active');
                } else if (selectedValue.startsWith('remove:')) {
                    // Remove custom voice with confirmation
                    const username = selectedValue.replace('remove:', '');
                    if (confirm(`Remove ${username} from voice options?`)) {
                        await deleteCustomVoice(username);
                    }
                    // Close dropdown
                    voiceToneTrigger.classList.remove('active');
                    voiceToneMenu.classList.remove('active');
                } else {
                    // Save valid selection
                    localStorage.setItem('selectedVoiceTone', selectedValue);
                    selectVoiceTone(selectedValue);
                    markAsChanged();
                    // Toggle Mimic button visibility
                    toggleMimicButton(selectedValue);
                }
            });
        }

        // Close dropdown when clicking outside - only add once
        document.addEventListener('click', (e) => {
            if (!voiceToneTrigger?.contains(e.target) && !voiceToneMenu?.contains(e.target)) {
                voiceToneTrigger?.classList.remove('active');
                voiceToneMenu?.classList.remove('active');
            }
        });
    }

    // Toggle Mimic option visibility based on voice selection
    function toggleMimicButton(selectedVoice) {
        const mimicBtn = document.getElementById('mimic-btn');

        if (mimicBtn) {
            // Show Mimic button only when a custom voice is selected (not 'creatrics')
            if (selectedVoice && selectedVoice !== 'creatrics' && selectedVoice !== 'standard') {
                mimicBtn.style.display = 'flex';
            } else {
                mimicBtn.style.display = 'none';
                // If mimic was active, switch to storytelling
                if (state.enhancementPreset === 'mimic') {
                    const storytellingBtn = document.querySelector('.option-btn[data-preset="storytelling"]');
                    if (storytellingBtn) {
                        document.querySelectorAll('.option-btn').forEach(btn => btn.classList.remove('active'));
                        storytellingBtn.classList.add('active');
                        state.enhancementPreset = 'storytelling';
                    }
                }
            }
        }
    }

    // File upload handling
    async function handleFileUpload(file, mediaContainer) {
        const mediaType = getMediaType(file);
        if (!mediaType) {
            showToast('Unsupported file type', 'error');
            return;
        }

        // Check existing media in this post
        const existingMedia = mediaContainer.querySelectorAll('.media-preview-container');
        const hasVideo = Array.from(existingMedia).some(container =>
            container.querySelector('video')
        );
        const imageCount = Array.from(existingMedia).filter(container =>
            container.querySelector('img')
        ).length;

        // X/Twitter rules: max 4 images OR 1 video (no mixing)
        if (mediaType === 'video') {
            if (existingMedia.length > 0) {
                showToast('Only 1 video allowed per post', 'error');
                return;
            }
        } else {
            // Image
            if (hasVideo) {
                showToast('Cannot mix images and video', 'error');
                return;
            }
            if (imageCount >= 4) {
                showToast('Maximum 4 images per post', 'error');
                return;
            }
        }

        try {
            const reader = new FileReader();
            reader.onload = async (e) => {
                try {
                    const response = await fetch('/x_post_editor/upload-media', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            media_data: e.target.result,
                            filename: `${Date.now()}_${file.name}`,
                            media_type: mediaType,
                            file_size: file.size,
                            mime_type: file.type
                        })
                    });

                    const data = await response.json();

                    if (data.success) {
                        const mediaElement = createMediaElement({
                            url: data.media_url,
                            filename: data.filename,
                            media_type: mediaType,
                            file_size: file.size,
                            mime_type: file.type
                        });
                        mediaContainer.appendChild(mediaElement);
                        showToast('Media uploaded', 'success');

                        // Mark as changed and save draft with media
                        markAsChanged();
                    } else {
                        showToast('Upload failed: ' + data.error, 'error');
                    }
                } catch (uploadError) {
                    showToast('Upload error: ' + uploadError.message, 'error');
                }
            };
            reader.readAsDataURL(file);
        } catch (error) {
            showToast('File reading error: ' + error.message, 'error');
        }
    }

    // Utility functions
    function getMediaType(file) {
        for (const [type, config] of Object.entries(SUPPORTED_MEDIA_TYPES)) {
            if (config.mimeTypes.includes(file.type)) {
                return type;
            }
        }
        return null;
    }

    function createMediaElement(mediaData) {
        const container = document.createElement('div');
        container.className = 'media-preview-container';
        
        let mediaElement;
        if (mediaData.media_type === 'video') {
            mediaElement = document.createElement('video');
            mediaElement.controls = true;
            mediaElement.muted = true;
        } else {
            mediaElement = document.createElement('img');
            // Handle broken images
            mediaElement.onerror = () => {
                console.warn('Failed to load media:', mediaData.url);
                container.remove();
                markAsChanged();
            };
        }
        
        mediaElement.src = mediaData.url;
        
        // Store metadata as data attributes for later retrieval
        mediaElement.setAttribute('data-filename', mediaData.filename || '');
        mediaElement.setAttribute('data-media-type', mediaData.media_type || 'image');
        mediaElement.setAttribute('data-file-size', mediaData.file_size || 0);
        mediaElement.setAttribute('data-mime-type', mediaData.mime_type || '');
        
        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-btn';
        removeBtn.innerHTML = '<i class="ph ph-x"></i>';
        removeBtn.onclick = () => {
            container.remove();
            markAsChanged();
        };
        
        container.appendChild(mediaElement);
        container.appendChild(removeBtn);
        
        return container;
    }


    function reorderPosts() {
        const posts = document.querySelectorAll('.post-item');
        state.postCount = 0;

        posts.forEach((post, index) => {
            state.postCount++;
            const labelElement = post.querySelector('.post-type span');
            if (labelElement) {
                labelElement.textContent = index === 0 ? 'Post' : `Post ${index + 1}`;
            }
        });

        updateActionButtons();
    }

    function updateCharacterCount(textarea) {
        const count = textarea.value.length;
        const countElement = textarea.closest('.post-item').querySelector('.character-count');

        if (countElement) {
            const countText = countElement.querySelector('.character-count-text');
            if (countText) {
                countText.textContent = `${count}/280`;
            }

            if (count > 280) {
                countElement.classList.add('over-limit');
            } else {
                countElement.classList.remove('over-limit');
            }

            // Update action buttons when character count changes
            updateActionButtons();
        }
    }

    function postToX() {
        const posts = document.querySelectorAll('.post-item');
        if (posts.length !== 1) return;
        
        const textarea = posts[0].querySelector('.post-editor-textarea');
        if (!textarea) return;
        
        const postText = textarea.value.trim();
        
        if (!postText) {
            showToast('Please enter some content to post', 'error');
            return;
        }
        
        const encodedText = encodeURIComponent(postText);
        const twitterUrl = `https://twitter.com/intent/tweet?text=${encodedText}`;
        window.open(twitterUrl, '_blank');
    }

    function gatherPostData() {
        const posts = [];
        document.querySelectorAll('.post-item').forEach(postItem => {
            const textarea = postItem.querySelector('.post-editor-textarea');

            const postData = {
                text: textarea ? textarea.value : '',
                media: []
            };

            // Get media from .media-preview-container elements
            const mediaContainers = postItem.querySelectorAll('.media-preview-container');
            mediaContainers.forEach(container => {
                const mediaElement = container.querySelector('img, video');
                if (mediaElement) {
                    postData.media.push({
                        url: mediaElement.src,
                        filename: mediaElement.getAttribute('data-filename') || '',
                        media_type: mediaElement.getAttribute('data-media-type') || (mediaElement.tagName.toLowerCase() === 'video' ? 'video' : 'image'),
                        file_size: parseInt(mediaElement.getAttribute('data-file-size')) || 0,
                        mime_type: mediaElement.getAttribute('data-mime-type') || ''
                    });
                }
            });

            posts.push(postData);
        });

        return posts;
    }

    function clearEditor() {
        const postsContainer = document.getElementById('postsContainer');
        if (postsContainer) {
            postsContainer.innerHTML = '';
        }
        state.postCount = 0;
        state.hasUnsavedChanges = false;
        state.undoStack = [];

        // Reset to keyword mode (Create category)
        state.enhancementPreset = 'keyword';
        state.additionalInstructions = '';

        // Activate Create category
        document.querySelectorAll('.category-btn').forEach(btn => btn.classList.remove('active'));
        const createBtn = document.querySelector('.category-btn[data-category="create"]');
        if (createBtn) createBtn.classList.add('active');

        // Show Create options
        document.querySelectorAll('.options-container').forEach(c => c.classList.remove('active'));
        const createContainer = document.querySelector('.options-container[data-category="create"]');
        if (createContainer) createContainer.classList.add('active');

        // Activate Keyword option
        document.querySelectorAll('.option-btn').forEach(btn => btn.classList.remove('active'));
        const keywordBtn = document.querySelector('.option-btn[data-preset="keyword"]');
        if (keywordBtn) keywordBtn.classList.add('active');

        const contextButton = document.getElementById('context-button');
        const contextTextarea = document.getElementById('context-textarea');
        if (contextButton) contextButton.classList.remove('active');
        if (contextTextarea) contextTextarea.value = '';
    }

    function loadPostsArray(posts) {
        const postsContainer = document.getElementById('postsContainer');
        if (!postsContainer) return;
        
        postsContainer.innerHTML = '';
        state.postCount = 0;
        
        if (posts.length === 0) {
            addNewPost();
        } else {
            posts.forEach((postData, index) => {
                const postElement = addNewPost();
                const textarea = postElement.querySelector('.post-editor-textarea');
                const mediaContainer = postElement.querySelector('.post-media');
                
                if (textarea) {
                    textarea.value = postData.text || '';
                    updateCharacterCount(textarea);
                }
                
                if (mediaContainer && postData.media && postData.media.length > 0) {
                    postData.media.forEach(media => {
                        // Only create media element if URL is valid
                        if (media.url && media.url.trim() !== '') {
                            const mediaElement = createMediaElement(media);
                            mediaContainer.appendChild(mediaElement);
                        } else {
                            console.warn('Skipping media with invalid URL:', media);
                        }
                    });
                }
            });
        }

        updateActionButtons();
    }

    function updateUIFromState() {
        // Find and activate the correct option button
        const activeOptionBtn = document.querySelector(`.option-btn[data-preset="${state.enhancementPreset}"]`);
        if (activeOptionBtn) {
            // Remove active from all option buttons
            document.querySelectorAll('.option-btn').forEach(btn => btn.classList.remove('active'));
            activeOptionBtn.classList.add('active');

            // Find which category this belongs to and activate it
            const container = activeOptionBtn.closest('.options-container');
            if (container) {
                const category = container.getAttribute('data-category');

                // Activate the category button
                document.querySelectorAll('.category-btn').forEach(btn => btn.classList.remove('active'));
                const categoryBtn = document.querySelector(`.category-btn[data-category="${category}"]`);
                if (categoryBtn) {
                    categoryBtn.classList.add('active');
                }

                // Show the options container
                document.querySelectorAll('.options-container').forEach(c => c.classList.remove('active'));
                container.classList.add('active');
            }
        }

        const contextButton = document.getElementById('context-button');
        const contextTextarea = document.getElementById('context-textarea');
        if (state.additionalInstructions.trim() !== '') {
            contextButton?.classList.add('active');
            if (contextTextarea) contextTextarea.value = state.additionalInstructions;
        } else {
            contextButton?.classList.remove('active');
            if (contextTextarea) contextTextarea.value = '';
        }
    }

    async function markAsChanged() {
        state.hasUnsavedChanges = true;

        // Don't auto-save if we're editing a scheduled post
        if (state.isEditingScheduled) {
            console.log('⏸️ Auto-save skipped - editing scheduled post');
            return;
        }

        // If no current draft and user is typing content, create a new draft first
        if (!state.currentDraftId && !state.isCreatingDraft) {
            const posts = gatherPostData();
            const hasContent = posts.some(post => post.text.trim() !== '');

            if (hasContent) {
                state.isCreatingDraft = true;
                const success = await createNewDraftSilently();
                state.isCreatingDraft = false;

                // If draft creation failed, don't try to save
                if (!success) {
                    return;
                }
            }
        }

        // Only save if we have a current draft
        if (state.currentDraftId) {
            debouncedSave();
        }
    }

    function updateStatusMessage(message) {
        // Don't show status messages anymore - toast only shows when saving
        return;
    }

    function updateSaveStatus(status) {
        const statusEl = document.getElementById('saveStatus');
        if (!statusEl) return;

        const statusText = statusEl.querySelector('span');
        const statusIcon = statusEl.querySelector('i');

        switch(status) {
            case 'typing':
                // Don't show anything for typing
                statusEl.style.display = 'none';
                break;
            case 'saving':
                statusIcon.className = 'ph ph-spinner';
                statusText.textContent = 'Saving...';
                statusEl.style.display = 'flex';
                break;
            case 'saved':
                // Hide the toast after saving completes
                statusEl.style.display = 'none';
                break;
            case 'error':
                statusIcon.className = 'ph ph-warning-circle';
                statusText.textContent = 'Error saving';
                statusEl.style.display = 'flex';
                // Auto-hide error after 3 seconds
                setTimeout(() => {
                    statusEl.style.display = 'none';
                }, 3000);
                break;
        }
    }

    // Auto-save with debouncing
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    const debouncedSave = debounce(saveContent, 1000);

    // Save content
    async function saveContent() {
        if (!state.currentDraftId) {
            state.currentDraftId = 'new';
        }

        const posts = gatherPostData();

        if (posts.every(post => !post.text.trim() && (!post.media || post.media.length === 0))) {
            return { success: false, error: 'No content to save' };
        }

        let title = "Untitled Draft";
        if (posts.length > 0 && posts[0].text) {
            const firstLine = posts[0].text.trim().split('\n')[0];
            title = firstLine.slice(0, 30);
            if (firstLine.length > 30) {
                title += '...';
            }
        }

        const saveData = {
            draft_id: state.currentDraftId,
            posts: posts,
            preset: state.enhancementPreset,
            additional_context: state.additionalInstructions,
            title: title
        };

        updateSaveStatus('saving');

        try {
            const response = await fetch('/x_post_editor/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(saveData)
            });

            const data = await response.json();

            if (data.success) {
                if (data.draft_id && state.currentDraftId === 'new') {
                    state.currentDraftId = data.draft_id;
                }

                state.hasUnsavedChanges = false;
                updateSaveStatus('saved');

                // Update draft title in sidebar and move to top
                updateCurrentDraftTitle(title);
                moveCurrentDraftToTop();
            } else {
                updateSaveStatus('error');
            }

            // Return response data for external callers
            return data;
        } catch (error) {
            console.error('Save error:', error);
            updateSaveStatus('error');
            return { success: false, error: error.message };
        }
    }

    // Update current draft title in sidebar
    function updateCurrentDraftTitle(title) {
        if (state.currentDraftId) {
            const currentDraftElement = document.querySelector(`[data-id="${state.currentDraftId}"] .draft-title`);
            if (currentDraftElement && currentDraftElement.textContent !== title) {
                currentDraftElement.textContent = title;
            }
        }
    }

    // Move current draft to top of the list (like Brain Dump)
    function moveCurrentDraftToTop() {
        if (!state.currentDraftId) return;
        
        const draftsList = document.getElementById('draftsList');
        const currentDraftElement = document.querySelector(`[data-id="${state.currentDraftId}"]`);
        
        if (draftsList && currentDraftElement) {
            // Remove from current position
            currentDraftElement.remove();
            
            // Add to the top of the list
            const firstChild = draftsList.firstChild;
            if (firstChild) {
                draftsList.insertBefore(currentDraftElement, firstChild);
            } else {
                draftsList.appendChild(currentDraftElement);
            }
            
            // Ensure it stays active/selected
            currentDraftElement.classList.add('active');
        }
    }

    // Filter drafts
    async function filterDrafts(query) {
        const search = query.toLowerCase().trim();
        
        if (!search) {
            // If no search query, reload the initial 10 drafts
            await loadDraftsWithSpinner();
            return;
        }
        
        // For search, load all drafts to search through them
        try {
            const response = await fetch(`/x_post_editor/drafts?limit=1000`); // Load all drafts for search
            const data = await response.json();
            
            if (data.success && data.drafts) {
                // Filter drafts based on search query
                const filteredDrafts = data.drafts.filter(draft => {
                    const title = (draft.title || '').toLowerCase();
                    const preview = draft.posts && draft.posts[0] ? (draft.posts[0].text || '').toLowerCase() : '';
                    return title.includes(search) || preview.includes(search);
                });
                
                // Update state for search results
                state.loadedCount = filteredDrafts.length;
                state.totalCount = filteredDrafts.length;
                state.hasMore = false; // No load more during search
                
                // Render filtered results
                renderDrafts(filteredDrafts, false);
            }
        } catch (error) {
            console.error('Error searching drafts:', error);
            // Fall back to local filtering if API fails
            const drafts = document.querySelectorAll('.draft-item');
            drafts.forEach(draft => {
                const title = draft.querySelector('.draft-title').textContent.toLowerCase();
                const preview = draft.querySelector('.draft-preview')?.textContent.toLowerCase() || '';
                
                if (title.includes(search) || preview.includes(search)) {
                    draft.style.display = '';
                } else {
                    draft.style.display = 'none';
                }
            });
        }
    }

    // Keyboard shortcuts
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            const isModifierPressed = e.ctrlKey || e.metaKey;
            
            if (isModifierPressed && e.key === 's') {
                e.preventDefault();
                if (state.currentDraftId) saveContent();
            }
            
            if (isModifierPressed && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                performUndo();
            }
        });
    }

    // Undo functionality
    function saveUndoState() {
        const currentState = {
            posts: gatherPostData(),
            preset: state.enhancementPreset,
            instructions: state.additionalInstructions
        };
        
        state.undoStack.push(currentState);
        if (state.undoStack.length > state.maxUndoSteps) {
            state.undoStack.shift();
        }
    }

    function performUndo() {
        if (state.undoStack.length === 0) {
            updateStatusMessage('Nothing to undo');
            return;
        }
        
        const previousState = state.undoStack.pop();
        
        // Restore posts
        loadPostsArray(previousState.posts);
        
        // Restore settings
        state.enhancementPreset = previousState.preset;
        state.additionalInstructions = previousState.instructions;
        
        // Update UI
        updateUIFromState();
        
        updateStatusMessage('Undone');
        markAsChanged();
    }

    // Utility functions
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    // Toast notification - disabled
    window.showToast = function(message, type = 'success') {
        // Toast messages disabled
    };

    // Expose functions and state
    window.CreatorPal.PostEditor.initialize = initialize;
    window.CreatorPal.PostEditor.state = state;
    window.CreatorPal.PostEditor.postToX = postToX;
    window.CreatorPal.PostEditor.clearEditor = clearEditor;
    window.CreatorPal.PostEditor.renderDrafts = renderDrafts;
    window.CreatorPal.PostEditor.setupInitialPost = setupInitialPost;
    window.CreatorPal.PostEditor.saveDraft = saveContent;
    window.CreatorPal.PostEditor.attachDraftEventListeners = attachDraftEventListeners;
    window.CreatorPal.PostEditor.loadDraft = loadDraft;

    // Auto-initialize if on post editor page
    if (document.getElementById('postsContainer')) {
        initialize();
    }

})();

// ===== REPOST MODAL INTEGRATION =====

let repostModalInstance = null;
let currentRepostContent = null;

function openRepostModal() {
    if (!repostModalInstance) {
        repostModalInstance = new RepostModal({
            platform: 'x',
            mediaTypeFilter: null, // Allow both images and videos
            onSelect: (content) => {
                handleRepostContentSelect(content);
            }
        });
    }
    repostModalInstance.open();
}

function handleRepostContentSelect(content) {
    console.log('Selected content for repost:', content);
    currentRepostContent = content;

    // Get the first post textarea
    const postsContainer = document.getElementById('postsContainer');
    const firstPost = postsContainer.querySelector('.post-item');
    if (!firstPost) return;

    const textarea = firstPost.querySelector('.post-editor-textarea');
    if (!textarea) return;

    // Pre-fill the textarea with keywords and description
    let text = '';
    if (content.keywords) {
        text += content.keywords;
    }
    if (content.content_description) {
        if (text) text += '\n\n';
        text += content.content_description;
    }

    if (text) {
        textarea.value = text;
        // Trigger input event to update character count
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // Handle media if present
    if (content.media_url) {
        const postMedia = firstPost.querySelector('.post-media');
        if (postMedia) {
            const mediaType = content.media_type || 'video';
            let mediaHTML = '';

            if (mediaType === 'video') {
                mediaHTML = `
                    <div class="media-preview-container">
                        <video src="${content.media_url}" controls data-media-type="video" data-filename=""></video>
                        <button class="remove-media-btn">
                            <i class="ph ph-x"></i>
                        </button>
                    </div>
                `;
            } else if (mediaType === 'image') {
                mediaHTML = `
                    <div class="media-preview-container">
                        <img src="${content.media_url}" alt="Media" data-media-type="image" data-filename="">
                        <button class="remove-media-btn">
                            <i class="ph ph-x"></i>
                        </button>
                    </div>
                `;
            }

            postMedia.innerHTML = mediaHTML;

            // Add remove button handler
            const removeBtn = postMedia.querySelector('.remove-media-btn');
            if (removeBtn) {
                removeBtn.onclick = () => {
                    postMedia.innerHTML = '';
                    currentRepostContent = null;
                };
            }
        }
    }

    // Show schedule card and pre-fill date/time
    // Check if ANY platform has a scheduled_for date (prefer the first one we find)
    let scheduledDate = null;

    if (content.platforms_posted) {
        console.log('Checking platforms_posted:', content.platforms_posted);

        // Check X first
        if (content.platforms_posted.x && content.platforms_posted.x.scheduled_for) {
            scheduledDate = content.platforms_posted.x.scheduled_for;
            console.log('Found X scheduled date:', scheduledDate);
        }
        // Otherwise check other platforms
        else {
            const platforms = ['youtube', 'tiktok', 'instagram'];
            for (const platform of platforms) {
                if (content.platforms_posted[platform] && content.platforms_posted[platform].scheduled_for) {
                    scheduledDate = content.platforms_posted[platform].scheduled_for;
                    console.log(`Found ${platform} scheduled date:`, scheduledDate);
                    break;
                }
            }
        }
    }

    if (scheduledDate) {
        console.log('Pre-filling schedule with date:', scheduledDate);
        const scheduledFor = new Date(scheduledDate);
        showScheduleCardWithDate(scheduledFor);
    } else {
        console.log('No scheduled date found in repost content');
    }
}

function showScheduleCardWithDate(date = null) {
    const scheduleCard = document.getElementById('scheduleCard');
    if (!scheduleCard) {
        console.log('Schedule card element not found');
        return;
    }

    console.log('Showing schedule card with date:', date);
    scheduleCard.style.display = 'block';

    // Get timezone abbreviation
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const tzAbbr = new Date().toLocaleTimeString('en-us', { timeZoneName: 'short' }).split(' ')[2];

    // Update timezone indicator
    const tzIndicator = document.getElementById('timezoneIndicator');
    if (tzIndicator) {
        tzIndicator.textContent = `(${tzAbbr || 'Local Time'})`;
    }

    // Pre-fill the dropdowns
    const dateSelect = document.getElementById('scheduleDateSelect');
    const timeSelect = document.getElementById('scheduleTimeSelect');

    console.log('Date select element:', dateSelect);
    console.log('Time select element:', timeSelect);

    // Check if dropdowns are already populated (more than just the placeholder)
    const needsPopulation = dateSelect.options.length <= 1 || timeSelect.options.length <= 1;

    if (needsPopulation) {
        console.log('Populating schedule dropdowns...');

        // Clear existing options
        dateSelect.innerHTML = '<option value="">Select date</option>';
        timeSelect.innerHTML = '<option value="">Select time</option>';

        // Populate date options (next 365 days)
        const today = new Date();
        for (let i = 0; i < 365; i++) {
            const optionDate = new Date(today);
            optionDate.setDate(today.getDate() + i);

            const year = optionDate.getFullYear();
            const month = String(optionDate.getMonth() + 1).padStart(2, '0');
            const day = String(optionDate.getDate()).padStart(2, '0');
            const value = `${year}-${month}-${day}`;

            const dayName = optionDate.toLocaleDateString('en-US', { weekday: 'short' });
            const monthName = optionDate.toLocaleDateString('en-US', { month: 'short' });
            const label = `${dayName}, ${monthName} ${day}, ${year}`;

            const option = document.createElement('option');
            option.value = value;

            if (i === 0) {
                option.textContent = `Today - ${label}`;
            } else if (i === 1) {
                option.textContent = `Tomorrow - ${label}`;
            } else {
                option.textContent = label;
            }

            dateSelect.appendChild(option);
        }

        // Populate time options (every 15 minutes)
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
    }

    // Set the date/time values
    if (date) {
        // The date object is already in local time after parsing the UTC string
        // Extract local date components
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const dateStr = `${year}-${month}-${day}`;

        // Extract local time components
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const timeStr = `${hours}:${minutes}`;

        console.log('Looking for date:', dateStr, 'time:', timeStr);

        // Set the date
        dateSelect.value = dateStr;
        console.log('Set date to:', dateSelect.value, '(found:', dateSelect.value !== '' ? 'yes' : 'no', ')');

        // Set the time
        timeSelect.value = timeStr;
        console.log('Set time to:', timeSelect.value, '(found:', timeSelect.value !== '' ? 'yes' : 'no', ')');
    } else {
        // Default to tomorrow at 12 PM
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;

        dateSelect.value = tomorrowStr;
        timeSelect.value = '12:00';
    }
}

// ===== X CONNECTION & SCHEDULING =====

/**
 * Check X connection status via Late.dev
 */
async function checkXConnectionStatus() {
    try {
        const response = await fetch('/x_post_editor/x-connection-status');
        const data = await response.json();

        if (window.CreatorPal && window.CreatorPal.PostEditor) {
            const state = window.CreatorPal.PostEditor.state;
            if (state) {
                state.isXConnected = data.connected;
                state.xAccountInfo = data.account_info;
            }
        }

        updateXConnectionUI(data.connected, data.account_info);
        updateScheduleButtonVisibility();
    } catch (error) {
        console.error('Error checking X connection:', error);
    }
}

/**
 * Update X connection UI
 */
function updateXConnectionUI(isConnected, accountInfo) {
    const compactStatus = document.getElementById('compactConnectionStatus');
    const fullCard = document.querySelector('.connection-card');
    const statusDot = document.querySelector('.connection-card .status-dot');
    const statusText = document.querySelector('.status-text');
    const connectBtn = document.getElementById('connectXBtn');
    const disconnectBtn = document.getElementById('disconnectXBtn');
    const userInfo = document.getElementById('userInfo');
    const buttonSkeleton = document.getElementById('buttonSkeleton');
    const connectionButtons = document.getElementById('connectionButtons');
    const premiumNotice = document.getElementById('premiumNotice');
    const hasPremium = window.hasPremium || false;

    console.log('=== updateXConnectionUI Debug ===');
    console.log('isConnected:', isConnected);
    console.log('hasPremium:', hasPremium);
    console.log('accountInfo:', accountInfo);
    console.log('=== End Debug ===');

    // Remove loading state
    if (statusDot) statusDot.classList.remove('loading');

    // Hide skeleton, show actual buttons
    if (buttonSkeleton) buttonSkeleton.style.display = 'none';
    if (connectionButtons) connectionButtons.style.display = 'block';

    // Check premium and connection status
    if (!hasPremium && !isConnected) {
        // Free user, not connected - show full card with premium notice
        if (compactStatus) compactStatus.style.display = 'none';
        if (fullCard) fullCard.style.display = 'block';
        if (statusDot) statusDot.classList.add('disconnected');
        if (statusText) statusText.textContent = 'Premium Required';
        if (connectBtn) connectBtn.style.display = 'none';
        if (disconnectBtn) disconnectBtn.style.display = 'none';
        if (userInfo) userInfo.style.display = 'none';
        if (premiumNotice) premiumNotice.style.display = 'flex';
        if (connectionButtons) connectionButtons.style.display = 'none';
        return;
    }

    // Hide premium notice for premium users
    if (premiumNotice) premiumNotice.style.display = 'none';

    if (isConnected && accountInfo) {
        // Connected - show compact status with username
        if (fullCard) fullCard.style.display = 'none';
        if (compactStatus) {
            compactStatus.style.display = 'flex';
            const compactDot = compactStatus.querySelector('.status-dot');
            const compactStatusText = compactStatus.querySelector('.compact-status-text');
            const compactDisconnectBtn = document.getElementById('compactDisconnectBtn');

            if (compactDot) {
                compactDot.classList.remove('disconnected');
                compactDot.classList.remove('loading');
            }
            if (compactStatusText) compactStatusText.innerHTML = `Connected as <strong id="compactUsername">@${accountInfo.username || ''}</strong>`;
            if (compactDisconnectBtn) {
                compactDisconnectBtn.style.display = 'flex';
                compactDisconnectBtn.innerHTML = '<i class="ph ph-plug"></i> Disconnect';
                compactDisconnectBtn.dataset.action = 'disconnect';
            }
        }
    } else {
        // Not connected but has premium - show compact status with connect button
        if (fullCard) fullCard.style.display = 'none';
        if (compactStatus) {
            compactStatus.style.display = 'flex';
            const compactDot = compactStatus.querySelector('.status-dot');
            const compactStatusText = compactStatus.querySelector('.compact-status-text');
            const compactDisconnectBtn = document.getElementById('compactDisconnectBtn');

            if (compactDot) {
                compactDot.classList.remove('loading');
                compactDot.classList.add('disconnected');
            }
            if (compactStatusText) compactStatusText.innerHTML = 'Not connected to X';
            if (compactDisconnectBtn) {
                compactDisconnectBtn.style.display = 'flex';
                compactDisconnectBtn.innerHTML = '<i class="ph ph-link"></i> Connect X';
                compactDisconnectBtn.dataset.action = 'connect';
            }
        }
    }
}

/**
 * Check if any post exceeds 280 characters
 */
function hasPostsOverLimit() {
    const posts = document.querySelectorAll('.post-item');
    for (const post of posts) {
        const textarea = post.querySelector('.post-editor-textarea');
        if (textarea && textarea.value.length > 280) {
            return true;
        }
    }
    return false;
}

/**
 * Update schedule button visibility (premium/connection check only)
 * Called from updateActionButtons() which handles the main visibility logic
 */
function updateScheduleButtonVisibility() {
    const state = window.CreatorPal?.PostEditor?.state;
    if (!state) {
        if (scheduleButtonRetryCount < 10) {
            scheduleButtonRetryCount++;
            setTimeout(updateScheduleButtonVisibility, 500);
        }
        return;
    }

    scheduleButtonRetryCount = 0;

    // If editing a scheduled post, keep buttons hidden
    if (state.isEditingScheduled || state.isScheduled) {
        const scheduleButtons = document.querySelectorAll('.schedule-x-btn');
        const postToXButtons = document.querySelectorAll('.post-to-x-btn');
        scheduleButtons.forEach(btn => btn.style.display = 'none');
        postToXButtons.forEach(btn => btn.style.display = 'none');
        return;
    }

    // Find ALL schedule buttons (one per post)
    const scheduleButtons = document.querySelectorAll('.schedule-x-btn');

    // Check if user has premium and is connected
    const canSchedule = state.hasPremium && state.isXConnected;

    // Hide schedule button if not premium or not connected
    scheduleButtons.forEach(btn => {
        if (!canSchedule && btn.style.display !== 'none') {
            btn.style.display = 'none';
        }
    });
}

/**
 * Handle X connect button click
 */
async function handleConnectX() {
    try {
        const response = await fetch('/x_post_editor/connect-x', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.success && data.auth_url) {
            window.location.href = data.auth_url;
        } else {
            alert(data.error || 'Failed to initiate X connection');
        }
    } catch (error) {
        console.error('Error connecting X:', error);
        alert('Failed to connect X account');
    }
}

/**
 * Handle X disconnect button click
 */
async function handleDisconnectX() {
    try {
        const response = await fetch('/x_post_editor/disconnect-x', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.success) {
            const state = window.CreatorPal?.PostEditor?.state;
            if (state) {
                state.isXConnected = false;
                state.xAccountInfo = null;
            }
            updateXConnectionUI(false, null);
            updateScheduleButtonVisibility();
        } else {
            alert(data.error || 'Failed to disconnect');
        }
    } catch (error) {
        console.error('Error disconnecting X:', error);
        alert('Failed to disconnect X account');
    }
}

/**
 * Show UI for scheduled draft
 * Grey out editor and show Edit/Reschedule buttons
 */
function showScheduledDraftUI(draft) {
    const postsContainer = document.getElementById('postsContainer');

    if (!postsContainer) return;

    // Make posts read-only and grey them out
    const textareas = postsContainer.querySelectorAll('.post-editor-textarea');
    textareas.forEach(textarea => {
        textarea.setAttribute('readonly', 'readonly');
        textarea.style.opacity = '0.6';
        textarea.style.cursor = 'not-allowed';
    });

    // Disable delete buttons, media upload buttons, and add post icons
    const deleteButtons = postsContainer.querySelectorAll('.delete-post');
    deleteButtons.forEach(btn => {
        btn.style.pointerEvents = 'none';
        btn.style.opacity = '0.4';
    });

    const mediaButtons = postsContainer.querySelectorAll('.media-upload-trigger');
    mediaButtons.forEach(btn => {
        btn.style.pointerEvents = 'none';
        btn.style.opacity = '0.4';
    });

    const addPostIcons = postsContainer.querySelectorAll('.add-post-icon');
    addPostIcons.forEach(icon => {
        icon.style.pointerEvents = 'none';
        icon.style.opacity = '0.4';
    });

    // Hide ALL Schedule and Post to X buttons (using class selectors)
    const scheduleButtons = document.querySelectorAll('.schedule-x-btn');
    const postToXButtons = document.querySelectorAll('.post-to-x-btn');
    scheduleButtons.forEach(btn => btn.style.display = 'none');
    postToXButtons.forEach(btn => btn.style.display = 'none');
    console.log('🚫 Hidden Schedule and Post to X buttons');

    // Add scheduled banner if not already present
    if (!document.getElementById('scheduledBanner')) {
        const banner = document.createElement('div');
        banner.id = 'scheduledBanner';
        banner.className = 'scheduled-banner';

        // Format scheduled time without seconds
        let scheduledTime = 'Unknown';
        if (draft.scheduled_time) {
            const date = new Date(draft.scheduled_time);
            const dateStr = date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
            const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
            scheduledTime = `${dateStr}, ${timeStr}`;
        }

        banner.innerHTML = `
            <div class="scheduled-info">
                <i class="ph ph-clock"></i>
                <span>This draft is scheduled for ${scheduledTime}</span>
            </div>
            <div class="scheduled-actions">
                <button class="action-btn btn-edit-scheduled" id="editScheduledBtn">
                    <i class="ph ph-pencil"></i>
                    Edit
                </button>
                <button class="action-btn btn-unschedule" id="unscheduleBtn">
                    <i class="ph ph-trash"></i>
                    Unschedule
                </button>
            </div>
        `;

        postsContainer.insertAdjacentElement('beforebegin', banner);

        // Add event listeners
        document.getElementById('editScheduledBtn')?.addEventListener('click', enableDraftEditing);
        document.getElementById('unscheduleBtn')?.addEventListener('click', unschedulePost);
    }
}

/**
 * Enable editing for scheduled draft
 */
function enableDraftEditing() {
    const postsContainer = document.getElementById('postsContainer');
    const scheduledBanner = document.getElementById('scheduledBanner');
    const state = window.CreatorPal?.PostEditor?.state;

    if (!postsContainer || !state) return;

    // Set flag to disable auto-save while editing scheduled post
    state.isEditingScheduled = true;
    console.log('📝 Entered scheduled post edit mode - auto-save disabled');

    // Remove readonly and restore opacity
    const textareas = postsContainer.querySelectorAll('.post-editor-textarea');
    textareas.forEach(textarea => {
        textarea.removeAttribute('readonly');
        textarea.style.opacity = '1';
        textarea.style.cursor = 'text';
    });

    // Re-enable delete buttons, media upload buttons, and add post icons
    const deleteButtons = postsContainer.querySelectorAll('.delete-post');
    deleteButtons.forEach(btn => {
        btn.style.pointerEvents = '';
        btn.style.opacity = '';
    });

    const mediaButtons = postsContainer.querySelectorAll('.media-upload-trigger');
    mediaButtons.forEach(btn => {
        btn.style.pointerEvents = '';
        btn.style.opacity = '';
    });

    const addPostIcons = postsContainer.querySelectorAll('.add-post-icon');
    addPostIcons.forEach(icon => {
        icon.style.pointerEvents = '';
        icon.style.opacity = '';
    });

    // Hide Schedule and Post to X buttons during editing
    const scheduleButtons = document.querySelectorAll('.schedule-x-btn');
    const postToXButtons = document.querySelectorAll('.post-to-x-btn');
    scheduleButtons.forEach(btn => btn.style.display = 'none');
    postToXButtons.forEach(btn => btn.style.display = 'none');

    // Replace banner with editing banner showing Update button
    if (scheduledBanner) {
        scheduledBanner.innerHTML = `
            <div class="scheduled-info">
                <i class="ph ph-pencil"></i>
                <span>Editing scheduled post</span>
            </div>
            <div class="scheduled-actions">
                <button class="action-btn btn-update-scheduled" id="updateScheduledBtn">
                    <i class="ph ph-check"></i>
                    Update
                </button>
            </div>
        `;

        // Add event listener for Update button
        document.getElementById('updateScheduledBtn')?.addEventListener('click', async () => {
            await updateScheduledPost();
        });
    }

    // Update draft list styling to show disabled state
    window.CreatorPal.PostEditor.attachDraftEventListeners();

    // Keep schedule buttons hidden while editing
    updateScheduleButtonVisibility();
}

/**
 * Update scheduled post on Late.dev
 */
async function updateScheduledPost() {
    console.log('🔄 updateScheduledPost called');
    const state = window.CreatorPal?.PostEditor?.state;
    console.log('State:', state);
    console.log('scheduledPostId:', state?.scheduledPostId);

    if (!state || !state.scheduledPostId) {
        console.error('❌ No scheduled post ID found');
        showToast('Error: No scheduled post found', 'error');
        return;
    }

    const updateBtn = document.getElementById('updateScheduledBtn');
    console.log('Update button:', updateBtn);
    if (!updateBtn) {
        console.error('❌ Update button not found');
        return;
    }

    // Disable button and show loading
    updateBtn.disabled = true;
    updateBtn.innerHTML = '<i class="ph ph-spinner" style="animation: spin 1s linear infinite;"></i> Updating...';
    console.log('✅ Button disabled, spinner showing');

    try {
        // STEP 1: Save the draft first (handles media upload/changes)
        console.log('📝 Step 1: Saving draft to Firebase...');
        const saveResponse = await window.CreatorPal.PostEditor.saveDraft();

        if (!saveResponse || !saveResponse.success) {
            throw new Error('Failed to save draft');
        }
        console.log('✅ Draft saved successfully');

        // STEP 2: Get updated post data from the saved draft
        const posts = [];
        const postItems = document.querySelectorAll('.post-item');
        console.log('Found post items:', postItems.length);

        postItems.forEach(postItem => {
            const textarea = postItem.querySelector('.post-editor-textarea');
            const text = textarea ? textarea.value : '';

            // Get media
            const media = [];
            const mediaContainers = postItem.querySelectorAll('.media-preview-container');
            mediaContainers.forEach(container => {
                const mediaElement = container.querySelector('img, video');
                if (mediaElement) {
                    media.push({
                        url: mediaElement.src,
                        media_type: mediaElement.getAttribute('data-media-type') || (mediaElement.tagName === 'VIDEO' ? 'video' : 'image'),
                        filename: mediaElement.getAttribute('data-filename') || ''
                    });
                }
            });

            posts.push({ text, media });
        });

        // STEP 3: Update Late.dev with the saved content
        console.log('📤 Step 2: Updating Late.dev...');
        // Get user's local timezone
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        console.log('Sending update request:', {
            late_dev_post_id: state.scheduledPostId,
            posts_count: posts.length,
            scheduled_time: state.scheduledTime,
            timezone: userTimezone,
            draft_id: state.currentDraftId
        });

        const response = await fetch('/x_post_editor/update-scheduled-post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                late_dev_post_id: state.scheduledPostId,
                posts: posts,
                scheduled_time: state.scheduledTime,
                timezone: userTimezone,
                draft_id: state.currentDraftId
            })
        });

        console.log('📥 Response status:', response.status);
        const data = await response.json();
        console.log('📥 Response data:', data);

        if (data.success) {
            console.log('✅ Update successful, returning to read-only view');
            console.log('Current state before restore:', {
                isEditingScheduled: state.isEditingScheduled,
                scheduledTime: state.scheduledTime,
                scheduledPostId: state.scheduledPostId
            });
            showToast('Post updated successfully!', 'success');

            // Clear editing flag
            state.isEditingScheduled = false;

            // Remove both banners to ensure clean state
            const editingBanner = document.getElementById('editingScheduledBanner');
            if (editingBanner) {
                editingBanner.remove();
            }
            const scheduledBanner = document.getElementById('scheduledBanner');
            if (scheduledBanner) {
                scheduledBanner.remove();
            }

            // Show the scheduled UI again (read-only with Edit button)
            const draftData = {
                scheduled_time: state.scheduledTime,
                is_scheduled: true
            };
            showScheduledDraftUI(draftData);

            // Re-enable all drafts
            const draftItems = document.querySelectorAll('.draft-item');
            draftItems.forEach(item => {
                item.style.opacity = '';
                item.style.pointerEvents = '';
            });

            // Refresh drafts list to update any changed titles/previews
            const draftsResponse = await fetch('/x_post_editor/drafts?offset=0&limit=20');
            const draftsData = await draftsResponse.json();
            if (draftsData.success) {
                window.CreatorPal.PostEditor.renderDrafts(draftsData.drafts || []);

                // Ensure the current draft shows the scheduled icon
                if (state.currentDraftId) {
                    const draftItem = document.querySelector(`.draft-item[data-id="${state.currentDraftId}"]`);
                    if (draftItem) {
                        // Make sure it has the scheduled icon
                        if (!draftItem.querySelector('.draft-scheduled-icon')) {
                            const draftTitle = draftItem.querySelector('.draft-title');
                            if (draftTitle) {
                                const scheduledIcon = document.createElement('i');
                                scheduledIcon.className = 'ph ph-clock draft-scheduled-icon';
                                scheduledIcon.title = 'Scheduled';
                                draftTitle.appendChild(scheduledIcon);
                            }
                        }
                        draftItem.setAttribute('data-scheduled', 'true');
                    }
                }
            }
        } else {
            showToast(data.error || 'Failed to update post', 'error');
            // Re-enable editing on failure
            state.isEditingScheduled = false;
            updateBtn.disabled = false;
            updateBtn.innerHTML = '<i class="ph ph-check"></i> Update';
        }
    } catch (error) {
        console.error('❌ Error updating scheduled post:', error);
        showToast('Failed to update post. Please try again.', 'error');

        // Re-enable editing on error
        state.isEditingScheduled = false;

        // Remove editing banner and restore scheduled banner
        const editingBanner = document.getElementById('editingScheduledBanner');
        if (editingBanner) editingBanner.remove();

        const scheduledBanner = document.getElementById('scheduledBanner');
        if (scheduledBanner) scheduledBanner.remove();

        // Show scheduled UI again
        if (state.scheduledTime) {
            const draftData = {
                scheduled_time: state.scheduledTime,
                is_scheduled: true
            };
            showScheduledDraftUI(draftData);
        }

        // Reset button
        updateBtn.disabled = false;
        updateBtn.innerHTML = '<i class="ph ph-check"></i> Update';
    }
}

/**
 * Unschedule a post - delete from Late.dev and clear scheduled status
 */
async function unschedulePost() {
    const state = window.CreatorPal?.PostEditor?.state;

    console.log('🗑️ Unschedule clicked, state:', {
        scheduledPostId: state?.scheduledPostId,
        currentDraftId: state?.currentDraftId,
        isScheduled: state?.isScheduled
    });

    if (!state || !state.scheduledPostId) {
        console.error('❌ No scheduled post ID found');
        showToast('Error: No scheduled post found', 'error');
        return;
    }

    const unscheduleBtn = document.getElementById('unscheduleBtn');
    if (unscheduleBtn) {
        unscheduleBtn.disabled = true;
        unscheduleBtn.innerHTML = '<i class="ph ph-spinner" style="animation: spin 1s linear infinite;"></i> Unscheduling...';
    }

    try {
        console.log('📤 Sending unschedule request:', {
            late_dev_post_id: state.scheduledPostId,
            draft_id: state.currentDraftId
        });

        const response = await fetch('/x_post_editor/unschedule-post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                late_dev_post_id: state.scheduledPostId,
                draft_id: state.currentDraftId
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Post unscheduled successfully!', 'success');

            // Clear scheduled state
            state.isScheduled = false;
            state.scheduledPostId = null;
            state.scheduledTime = null;
            state.calendarEventId = null;

            // Remove scheduled banner
            const scheduledBanner = document.getElementById('scheduledBanner');
            if (scheduledBanner) {
                scheduledBanner.remove();
            }

            // Make posts editable again
            const postsContainer = document.getElementById('postsContainer');
            if (postsContainer) {
                const textareas = postsContainer.querySelectorAll('.post-editor-textarea');
                textareas.forEach(textarea => {
                    textarea.removeAttribute('readonly');
                    textarea.style.opacity = '';
                    textarea.style.cursor = '';
                });

                // Re-enable delete buttons, media upload buttons, and add post icons
                const deleteButtons = postsContainer.querySelectorAll('.delete-post');
                deleteButtons.forEach(btn => {
                    btn.style.pointerEvents = '';
                    btn.style.opacity = '';
                });

                const mediaButtons = postsContainer.querySelectorAll('.media-upload-trigger');
                mediaButtons.forEach(btn => {
                    btn.style.pointerEvents = '';
                    btn.style.opacity = '';
                });

                const addPostIcons = postsContainer.querySelectorAll('.add-post-icon');
                addPostIcons.forEach(icon => {
                    icon.style.pointerEvents = '';
                    icon.style.opacity = '';
                });
            }

            // Show Schedule and Post buttons again
            const scheduleButtons = document.querySelectorAll('.schedule-x-btn');
            const postToXButtons = document.querySelectorAll('.post-to-x-btn');
            scheduleButtons.forEach(btn => btn.style.display = '');
            postToXButtons.forEach(btn => btn.style.display = '');

            updateScheduleButtonVisibility();

            // Remove scheduled icon from current draft in sidebar
            if (state.currentDraftId) {
                const draftItem = document.querySelector(`.draft-item[data-id="${state.currentDraftId}"]`);
                if (draftItem) {
                    const scheduledIcon = draftItem.querySelector('.draft-scheduled-icon');
                    if (scheduledIcon) scheduledIcon.remove();
                    // Also update the data attribute
                    draftItem.setAttribute('data-scheduled', 'false');
                }
            }

            // Refresh drafts list
            const draftsResponse = await fetch('/x_post_editor/drafts?offset=0&limit=20');
            const draftsData = await draftsResponse.json();
            if (draftsData.success) {
                window.CreatorPal.PostEditor.renderDrafts(draftsData.drafts || []);
            }
        } else {
            showToast(data.error || 'Failed to unschedule post', 'error');
            if (unscheduleBtn) {
                unscheduleBtn.disabled = false;
                unscheduleBtn.innerHTML = '<i class="ph ph-trash"></i> Unschedule';
            }
        }
    } catch (error) {
        console.error('Error unscheduling post:', error);
        showToast('Failed to unschedule post. Please try again.', 'error');
        if (unscheduleBtn) {
            unscheduleBtn.disabled = false;
            unscheduleBtn.innerHTML = '<i class="ph ph-trash"></i> Unschedule';
        }
    }
}

// ============================================================================
// CALENDAR INTEGRATION
// ============================================================================

/**
 * Initialize the calendar link modal
 */
function initializeCalendarModal() {
    if (typeof CalendarLinkModal === 'undefined') {
        console.error('CalendarLinkModal not loaded');
        return;
    }

    CalendarLinkModal.init('X', function(item) {
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (window.CreatorPal && window.CreatorPal.PostEditor && document.getElementById('postsContainer')) {
        window.CreatorPal.PostEditor.initialize();
    }

    // Check X connection status
    checkXConnectionStatus();

    // Check for ongoing uploads
    checkForOngoingUploads();

    // Setup X connection buttons
    const connectBtn = document.getElementById('connectXBtn');
    const disconnectBtn = document.getElementById('disconnectXBtn');

    if (connectBtn) {
        connectBtn.addEventListener('click', handleConnectX);
    }

    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', handleDisconnectX);
    }

    // Setup compact disconnect button (handles both connect and disconnect)
    const compactDisconnectBtn = document.getElementById('compactDisconnectBtn');
    if (compactDisconnectBtn) {
        compactDisconnectBtn.addEventListener('click', (e) => {
            const action = e.currentTarget.dataset.action;
            if (action === 'disconnect') {
                handleDisconnectX();
            } else if (action === 'connect') {
                handleConnectX();
            }
        });
    }

    // Initialize calendar link modal
    initializeCalendarModal();

    // Setup schedule button (delegated event for dynamically created buttons in post boxes)
    document.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('schedule-x-btn')) {
            const btn = e.target;
            const originalHTML = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<i class="ph ph-spinner" style="animation: spin 1s linear infinite;"></i> Loading...';

            // Show inline schedule card and restore button
            setTimeout(() => {
                showScheduleCard();
                btn.disabled = false;
                btn.innerHTML = originalHTML;
            }, 300);
        }

        // Setup Post to X button (delegated event)
        if (e.target && e.target.classList.contains('post-to-x-btn')) {
            window.CreatorPal.PostEditor.postToX();
        }

        // Setup confirm schedule button (delegated event)
        if (e.target && e.target.id === 'confirmScheduleBtn') {
            handleScheduleConfirm();
        }

        // Setup close schedule card button (delegated event)
        if (e.target && (e.target.id === 'scheduleCloseBtn' || e.target.closest('#scheduleCloseBtn'))) {
            const scheduleCard = document.getElementById('scheduleCard');
            if (scheduleCard) scheduleCard.style.display = 'none';
        }
    });

    // Debug: Log premium status
    console.log('Window hasPremium:', window.hasPremium);
    console.log('Connect button exists:', !!connectBtn);
    console.log('Disconnect button exists:', !!disconnectBtn);
});

/**
 * Show inline schedule card for date/time selection
 */
function showScheduleCard() {
    const scheduleCard = document.getElementById('scheduleCard');
    if (!scheduleCard) return;

    // Show the schedule card
    scheduleCard.style.display = 'block';

    // Scroll to it smoothly
    scheduleCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Get timezone abbreviation
    const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const tzAbbr = new Date().toLocaleTimeString('en-us', { timeZoneName: 'short' }).split(' ')[2];

    // Update timezone indicator
    const tzIndicator = document.getElementById('timezoneIndicator');
    if (tzIndicator) {
        tzIndicator.textContent = `(${tzAbbr || 'Local Time'})`;
    }

    // Populate date options (next 365 days with Today/Tomorrow labels)
    const dateSelect = document.getElementById('scheduleDateSelect');
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

    // Populate time options (every 15 minutes)
    const timeSelect = document.getElementById('scheduleTimeSelect');
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

    // Set default to tomorrow at 12 PM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;

    dateSelect.value = tomorrowStr;
    timeSelect.value = '12:00';
}

/**
 * Handle schedule confirmation
 */
async function handleScheduleConfirm() {
    // Check if calendar item is linked - if so, use its publish date
    const linkedCalendarItem = CalendarLinkModal.getLinkedItem();
    let scheduledTime;

    if (linkedCalendarItem && linkedCalendarItem.publish_date) {
        // Use the linked calendar item's publish date
        scheduledTime = linkedCalendarItem.publish_date;
        console.log('Using linked calendar item publish date:', scheduledTime);
    } else {
        // Use form fields if NOT linked to calendar item
        const dateValue = document.getElementById('scheduleDateSelect').value;
        const timeValue = document.getElementById('scheduleTimeSelect').value;

        if (!dateValue || !timeValue) {
            alert('Please select both date and time');
            return;
        }

        // Combine date and time in local timezone
        const [hours, minutes] = timeValue.split(':').map(Number);
        const scheduledDate = new Date(dateValue);
        scheduledDate.setHours(hours, minutes, 0, 0);

        // Convert to ISO 8601 format
        scheduledTime = scheduledDate.toISOString();
    }

    // Get all posts
    const posts = [];
    const postItems = document.querySelectorAll('.post-item');

    postItems.forEach(postItem => {
        const textarea = postItem.querySelector('.post-editor-textarea');
        const text = textarea ? textarea.value : '';

        // Get media for this post - media is stored in .media-preview-container
        const media = [];
        const mediaContainers = postItem.querySelectorAll('.media-preview-container');
        mediaContainers.forEach(container => {
            const mediaElement = container.querySelector('img, video');
            if (mediaElement) {
                media.push({
                    url: mediaElement.src,
                    media_type: mediaElement.getAttribute('data-media-type') || (mediaElement.tagName === 'VIDEO' ? 'video' : 'image'),
                    filename: mediaElement.getAttribute('data-filename') || ''
                });
            }
        });

        posts.push({ text, media });
    });

    console.log('📤 Sending posts to schedule:', posts);

    // Hide Schedule and Post to X buttons
    const scheduleButtons = document.querySelectorAll('.schedule-x-btn');
    const postToXButtons = document.querySelectorAll('.post-to-x-btn');
    scheduleButtons.forEach(btn => btn.style.display = 'none');
    postToXButtons.forEach(btn => btn.style.display = 'none');

    // Disable button and show loading
    const confirmBtn = document.getElementById('confirmScheduleBtn');
    if (!confirmBtn) {
        console.error('Schedule button not found');
        return;
    }
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<i class="ph ph-spinner" style="animation: spin 1s linear infinite;"></i> Scheduling...';

    try {
        // Access state via global
        const state = window.CreatorPal?.PostEditor?.state;
        if (!state) {
            alert('Editor state not available. Please refresh the page.');
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="ph ph-calendar-check"></i> Schedule Post';
            return;
        }

        // Get user's local timezone
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        // Add calendar_event_id if linked
        const requestPayload = {
            posts: posts,
            scheduled_time: scheduledTime,
            timezone: userTimezone,
            draft_id: state.currentDraftId || '',
            content_id: currentRepostContent ? currentRepostContent.id : null
        };

        if (linkedCalendarItem && linkedCalendarItem.id) {
            requestPayload.calendar_event_id = linkedCalendarItem.id;
        }

        const response = await fetch('/x_post_editor/schedule-post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestPayload)
        });

        const data = await response.json();

        if (data.success) {
            // Mark current draft as scheduled if we have a draft ID
            if (state.currentDraftId) {
                try {
                    await fetch(`/x_post_editor/drafts/${state.currentDraftId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            is_scheduled: true,
                            scheduled_time: scheduledTime,
                            late_dev_post_id: data.post_id,
                            calendar_event_id: data.calendar_event_id
                        })
                    });

                    // Update state
                    state.isScheduled = true;
                    state.calendarEventId = data.calendar_event_id;
                    state.scheduledPostId = data.post_id;
                    state.scheduledTime = scheduledTime;

                    // Hide schedule card
                    const scheduleCard = document.getElementById('scheduleCard');
                    if (scheduleCard) scheduleCard.style.display = 'none';

                    // Refresh drafts list to show clock icon
                    const draftsResponse = await fetch('/x_post_editor/drafts?offset=0&limit=20');
                    const draftsData = await draftsResponse.json();
                    if (draftsData.success) {
                        window.CreatorPal.PostEditor.renderDrafts(draftsData.drafts || []);
                    }

                    // Show scheduled draft UI
                    const draftData = {
                        scheduled_time: scheduledTime
                    };
                    showScheduledDraftUI(draftData);

                    // Show success message
                    showToast('Post scheduled successfully!', 'success');
                } catch (e) {
                    console.error('Error updating draft scheduled status:', e);
                }
            }
        } else {
            showToast(data.error || 'Failed to schedule post', 'error');
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="ph ph-calendar-check"></i> Schedule Post';
        }
    } catch (error) {
        console.error('Error scheduling post:', error);
        showToast('Failed to schedule post. Please try again.', 'error');
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '<i class="ph ph-calendar-check"></i> Schedule Post';
    }
}

// Add CSS animation for spinner
const style = document.createElement('style');
style.textContent = `
@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
`;
document.head.appendChild(style);

/**
 * Show insufficient credits modal
 */
function showInsufficientCreditsModal() {
    // Create modal overlay
    const modalHTML = `
        <div class="insufficient-credits-modal-overlay" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center;">
            <div class="insufficient-credits-card" style="max-width: 500px; margin: auto;">
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
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Close on click outside
    document.querySelector('.insufficient-credits-modal-overlay').addEventListener('click', function(e) {
        if (e.target === this) {
            this.remove();
        }
    });
}

/**
 * Check for ongoing uploads
 */
async function checkForOngoingUploads() {
    try {
        const response = await fetch('/x-post-editor/api/check-ongoing-uploads');
        const data = await response.json();

        if (data.has_ongoing_uploads) {
            showOngoingUploadBanner(data.uploads);
        }
    } catch (error) {
        console.log('Could not check for ongoing uploads:', error);
    }
}

/**
 * Show banner for ongoing uploads
 */
function showOngoingUploadBanner(uploads) {
    // Remove existing banner if present
    const existingBanner = document.getElementById('ongoingUploadBanner');
    if (existingBanner) {
        existingBanner.remove();
    }

    const banner = document.createElement('div');
    banner.id = 'ongoingUploadBanner';
    banner.style.cssText = `
        position: fixed;
        top: 70px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        font-size: 14px;
        max-width: 600px;
        min-width: 400px;
    `;

    const count = uploads.length;
    const uploadText = count === 1 ? '1 post upload' : `${count} post uploads`;

    // Build upload list HTML
    const uploadListHTML = uploads.map(upload => {
        const title = upload.title || 'Untitled';
        const truncatedTitle = title.length > 50 ? title.substring(0, 50) + '...' : title;
        return `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-top: 1px solid rgba(255,255,255,0.2);">
                <span style="flex: 1;">${truncatedTitle}</span>
                <button onclick="cancelUpload('${upload.content_id}')"
                        style="background: rgba(255,100,100,0.8); border: none; color: white; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                    Cancel
                </button>
            </div>
        `;
    }).join('');

    banner.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
            <i class="ph ph-circle-notch spinning" style="font-size: 18px;"></i>
            <span><strong>${uploadText} in progress...</strong> You can safely navigate away.</span>
            <button onclick="document.getElementById('ongoingUploadBanner').remove()"
                    style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 4px 12px; border-radius: 4px; cursor: pointer; margin-left: auto; font-size: 12px;">
                Dismiss
            </button>
        </div>
        ${uploadListHTML}
    `;

    document.body.appendChild(banner);

    // Auto-refresh to check status every 30 seconds
    setTimeout(() => {
        checkForOngoingUploads();
    }, 30000);
}

/**
 * Cancel an upload
 */
async function cancelUpload(contentId) {
    if (!confirm('Are you sure you want to cancel this upload? The calendar item will be removed.')) {
        return;
    }

    try {
        const response = await fetch('/x-post-editor/api/cancel-upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content_id: contentId })
        });

        const data = await response.json();

        if (data.success) {
            // Remove the banner immediately (don't wait for refresh)
            const banner = document.getElementById('ongoingUploadBanner');
            if (banner) {
                banner.remove();
            }

            // Refresh after a short delay to show updated list (if any other uploads exist)
            setTimeout(() => {
                checkForOngoingUploads();
            }, 500);
        } else {
            alert('Failed to cancel upload: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error cancelling upload:', error);
        alert('Failed to cancel upload');
    }
}

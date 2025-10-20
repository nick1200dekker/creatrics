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
        enhancementPreset: 'braindump',
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
        totalCount: 0,
        hasMore: false,
        isLoadingMore: false,
        isCreatingDraft: false
    };

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
        updatePostToXButtonVisibility();
        loadDraftsWithSpinner();

        // Initialize voice tone dropdown and its event listeners
        initializeVoiceTone().catch(console.error);
        setupVoiceToneEventListener();

        // Check for suggestion from dashboard
        checkForSuggestion();

        updateStatusMessage('Ready to create content');

        window.CreatorPal.PostEditor.initialized = true;
        console.log('Post Editor initialized with fresh post');
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

            draftsHTML += `
                <div class="draft-item ${isActive ? 'active' : ''}" data-id="${draft.id}">
                    <div class="draft-content">
                        <div class="draft-title">${draft.title || 'Untitled Draft'}</div>
                        ${preview ? `<div class="draft-preview">${escapeHtml(preview)}</div>` : ''}
                    </div>
                    <button class="draft-delete-btn" title="Delete Draft">
                        <i class="ph ph-trash"></i>
                    </button>
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
            const remaining = state.totalCount - state.loadedCount;
            loadMoreText.textContent = `Load More (${remaining} remaining)`;
            console.log('Showing load more button with', remaining, 'remaining');
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
                    const title = item.querySelector('.draft-title').textContent;
                    if (confirm(`Delete draft "${title}"?`)) {
                        deleteDraft(draftId, item);
                    }
                };
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

    // Add new post
    function addNewPost() {
        const postsContainer = document.getElementById('postsContainer');
        if (!postsContainer) return;
        
        state.postCount++;
        
        const newPost = document.createElement('div');
        newPost.className = 'post-item';
        newPost.innerHTML = `
            <div class="post-item-header">
                <div class="post-type">
                    <i class="ph ph-note-pencil"></i>
                    <span>${state.postCount === 1 ? 'Post' : `Post ${state.postCount}`}</span>
                </div>
                <div class="post-actions">
                    <button class="post-action media-upload-trigger" title="Add Media">
                        <i class="ph ph-paperclip"></i>
                    </button>
                    ${state.postCount > 1 ? `
                    <button class="post-action delete-post" title="Delete">
                        <i class="ph ph-trash"></i>
                    </button>` : ''}
                </div>
            </div>
            <div class="post-editor-content">
                <textarea class="post-editor-textarea" placeholder="${state.postCount === 1 ? 'Start typing your post here...' : 'Continue your thread...'}"></textarea>
                <div class="post-media"></div>
                <input type="file" class="hidden-file-input" accept="image/*,video/*,.gif">
            </div>
            <div class="post-footer">
                <div class="character-count">
                    <span class="character-count-text">0/280</span>
                    <div class="add-post-icon">
                        <i class="ph ph-plus"></i>
                    </div>
                </div>
                ${state.postCount === 1 ? `
                <button id="post-to-x-btn" class="post-action-btn">
                    <i class="ph ph-paper-plane-right"></i>
                    Post to X
                </button>` : ''}
            </div>
        `;
        
        postsContainer.appendChild(newPost);
        setupPostEventListeners(newPost);
        updatePostToXButtonVisibility();
        
        return newPost;
    }

    // Setup post event listeners
    function setupPostEventListeners(postElement) {
        const textarea = postElement.querySelector('.post-editor-textarea');
        const fileInput = postElement.querySelector('.hidden-file-input');
        const uploadTrigger = postElement.querySelector('.media-upload-trigger');
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
        
        // Tool selection
        const grammarTool = document.getElementById('grammar-tool');
        const storytellingTool = document.getElementById('storytelling-tool');
        const hookStoryPunchTool = document.getElementById('hook-story-punch-tool');
        const braindumpTool = document.getElementById('braindump-tool');
        const mimicTool = document.getElementById('mimic-tool');

        if (grammarTool) {
            grammarTool.onclick = () => {
                resetToolsActive();
                grammarTool.classList.add('active');
                state.enhancementPreset = 'grammar';
                markAsChanged();
            };
        }
        
        if (storytellingTool) {
            storytellingTool.onclick = () => {
                resetToolsActive();
                storytellingTool.classList.add('active');
                state.enhancementPreset = 'storytelling';
                markAsChanged();
            };
        }
        
        if (hookStoryPunchTool) {
            hookStoryPunchTool.onclick = () => {
                resetToolsActive();
                hookStoryPunchTool.classList.add('active');
                state.enhancementPreset = 'hook_story_punch';
                markAsChanged();
            };
        }

        if (braindumpTool) {
            braindumpTool.onclick = () => {
                resetToolsActive();
                braindumpTool.classList.add('active');
                state.enhancementPreset = 'braindump';
                markAsChanged();
            };
        }

        if (mimicTool) {
            mimicTool.onclick = () => {
                resetToolsActive();
                mimicTool.classList.add('active');
                state.enhancementPreset = 'mimic';
                markAsChanged();
            };
        }
        
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

                if (draft.posts && Array.isArray(draft.posts)) {
                    loadPostsArray(draft.posts);
                }

                state.enhancementPreset = draft.preset || 'storytelling';
                state.additionalInstructions = draft.additional_context || '';

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
        if (generateButton) {
            generateButton.disabled = true;
            generateButton.style.opacity = '0.7';
            generateButton.style.cursor = 'not-allowed';
            const buttonText = generateButton.querySelector('.button-text');
            if (buttonText) {
                buttonText.textContent = 'Enhancing...';
            }
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
                const buttonText = generateButton.querySelector('.button-text');
                if (buttonText) {
                    buttonText.textContent = 'Enhance';
                }
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

    // Toggle Mimic button visibility based on voice selection
    function toggleMimicButton(selectedVoice) {
        const mimicButton = document.getElementById('mimic-tool');
        if (mimicButton) {
            // Show Mimic button only when a custom voice is selected (not 'creatrics')
            if (selectedVoice && selectedVoice !== 'creatrics' && selectedVoice !== 'standard') {
                mimicButton.style.display = 'flex';
            } else {
                mimicButton.style.display = 'none';
                // If mimic was active, switch to storytelling
                if (mimicButton.classList.contains('active')) {
                    mimicButton.classList.remove('active');
                    const storytellingTool = document.getElementById('storytelling-tool');
                    if (storytellingTool) {
                        storytellingTool.classList.add('active');
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
                            media_type: mediaType
                        });
                        mediaContainer.appendChild(mediaElement);
                        showToast('Media uploaded', 'success');
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

    function resetToolsActive() {
        document.querySelectorAll('.ai-tool').forEach(tool => {
            if (tool.id !== 'context-button') {
                tool.classList.remove('active');
            }
        });
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
        
        updatePostToXButtonVisibility();
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
        }
    }

    function updatePostToXButtonVisibility() {
        const posts = document.querySelectorAll('.post-item');
        const postToXButton = document.getElementById('post-to-x-btn');
        
        if (postToXButton) {
            if (posts.length === 1) {
                postToXButton.classList.remove('hidden');
                postToXButton.onclick = postToX;
            } else {
                postToXButton.classList.add('hidden');
            }
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
            const mediaContainer = postItem.querySelector('.post-media');
            
            const postData = {
                text: textarea ? textarea.value : '',
                media: []
            };
            
            if (mediaContainer) {
                const mediaElements = mediaContainer.querySelectorAll('img, video');
                mediaElements.forEach(element => {
                    postData.media.push({
                        url: element.src,
                        filename: element.getAttribute('data-filename') || '',
                        media_type: element.getAttribute('data-media-type') || (element.tagName.toLowerCase() === 'video' ? 'video' : 'image'),
                        file_size: parseInt(element.getAttribute('data-file-size')) || 0,
                        mime_type: element.getAttribute('data-mime-type') || ''
                    });
                });
            }
            
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

        resetToolsActive();
        document.getElementById('braindump-tool')?.classList.add('active');
        state.enhancementPreset = 'braindump';
        state.additionalInstructions = '';
        
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
        
        updatePostToXButtonVisibility();
    }

    function updateUIFromState() {
        resetToolsActive();
        if (state.enhancementPreset === 'grammar') {
            document.getElementById('grammar-tool')?.classList.add('active');
        } else if (state.enhancementPreset === 'storytelling') {
            document.getElementById('storytelling-tool')?.classList.add('active');
        } else if (state.enhancementPreset === 'hook_story_punch') {
            document.getElementById('hook-story-punch-tool')?.classList.add('active');
        } else if (state.enhancementPreset === 'braindump') {
            document.getElementById('braindump-tool')?.classList.add('active');
        } else if (state.enhancementPreset === 'mimic') {
            document.getElementById('mimic-tool')?.classList.add('active');
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
        const statusElement = document.getElementById('saveStatus');
        if (statusElement) {
            const statusText = statusElement.querySelector('span');
            const statusIcon = statusElement.querySelector('i');
            
            if (statusText) statusText.textContent = message;
            if (statusIcon) statusIcon.className = 'ph ph-check-circle';
        }
    }

    function updateSaveStatus(status) {
        const statusEl = document.getElementById('saveStatus');
        if (!statusEl) return;
        
        const statusText = statusEl.querySelector('span');
        const statusIcon = statusEl.querySelector('i');
        
        statusEl.className = 'save-status ' + status;
        
        switch(status) {
            case 'typing':
                statusIcon.className = 'ph ph-circle';
                statusText.textContent = 'Typing...';
                break;
            case 'saving':
                statusIcon.className = 'ph ph-spinner spin';
                statusText.textContent = 'Saving...';
                break;
            case 'saved':
                statusIcon.className = 'ph ph-check-circle';
                statusText.textContent = 'Saved';
                break;
            case 'error':
                statusIcon.className = 'ph ph-warning-circle';
                statusText.textContent = 'Error';
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
            return;
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
        } catch (error) {
            console.error('Save error:', error);
            updateSaveStatus('error');
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

    // Toast notification
    window.showToast = function(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        
        const icon = type === 'success' ? 'ph-check-circle' : 'ph-x-circle';
        
        toast.innerHTML = `
            <i class="ph ${icon}"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 100);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // Expose functions
    window.CreatorPal.PostEditor.initialize = initialize;

    // Auto-initialize if on post editor page
    if (document.getElementById('grammar-tool')) {
        initialize();
    }

    // Beforeunload handler
    window.addEventListener('beforeunload', (e) => {
        if (state.hasUnsavedChanges) {
            const message = 'You have unsaved changes. Are you sure you want to leave?';
            e.returnValue = message;
            return message;
        }
    });

})();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    if (window.CreatorPal && window.CreatorPal.PostEditor && document.getElementById('grammar-tool')) {
        window.CreatorPal.PostEditor.initialize();
    }

});

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

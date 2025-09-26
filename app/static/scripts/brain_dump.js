// State
let currentNoteId = null;
let notes = [];
let autoSaveTimer = null;
let currentNoteTags = [];
let currentShareUrl = null;

// Preset tags data
const PRESET_TAGS_MAP = {
    'video-idea': { emoji: '🎥', label: 'Video Idea' },
    'content-idea': { emoji: '💡', label: 'Content Idea' },
    'draft': { emoji: '📝', label: 'Draft' },
    'important': { emoji: '⭐', label: 'Important' },
    'research': { emoji: '🔍', label: 'Research' },
    'script': { emoji: '📜', label: 'Script' },
    'social-media': { emoji: '📱', label: 'Social Media' },
    'tutorial': { emoji: '📚', label: 'Tutorial' }
};

function getPresetTag(tagName) {
    return PRESET_TAGS_MAP[tagName] || null;
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    initializeEditor();
    loadNotes();
    setupEventListeners();

    // Start with empty editor ready (like Post Editor)
    showEmptyEditor();
});

function initializeEditor() {
    const editor = document.getElementById('editor');
    if (!editor) return;
    
    // Handle paste to strip formatting
    editor.addEventListener('paste', function(e) {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData('text/plain');
        document.execCommand('insertText', false, text);
    });
    
    // Auto-save on content change
    editor.addEventListener('input', function() {
        clearTimeout(autoSaveTimer);
        updateSaveStatus('typing');

        autoSaveTimer = setTimeout(async () => {
            // Create note if needed (like Post Editor)
            if (!currentNoteId) {
                await createNoteIfNeeded();
            }
            if (currentNoteId) {
                saveNote(true); // Silent auto-save
            }
        }, 800); // Faster auto-save after 0.8 seconds
    });
}

function setupEventListeners() {
    // Search
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            filterNotes(e.target.value);
        });
    }
    
    // Title auto-save
    const titleInput = document.getElementById('noteTitle');
    if (titleInput) {
        titleInput.addEventListener('input', function() {
            clearTimeout(autoSaveTimer);
            updateSaveStatus('typing');

            autoSaveTimer = setTimeout(async () => {
                // Create note if needed (like Post Editor)
                if (!currentNoteId) {
                    await createNoteIfNeeded();
                }
                if (currentNoteId) {
                    saveNote(true);
                }
            }, 500); // Even faster for title
        });
    }
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + S to save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            if (currentNoteId) saveNote();
        }
        
        // Ctrl/Cmd + B for bold
        if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
            e.preventDefault();
            formatText('bold');
        }
        
        // Ctrl/Cmd + I for italic
        if ((e.ctrlKey || e.metaKey) && e.key === 'i') {
            e.preventDefault();
            formatText('italic');
        }
        
        // Ctrl/Cmd + U for underline
        if ((e.ctrlKey || e.metaKey) && e.key === 'u') {
            e.preventDefault();
            formatText('underline');
        }
        
        // Handle special keys in editor
        const editor = document.getElementById('editor');
        if (document.activeElement === editor) {
            // If we're in a code block and user presses Enter, exit the code block
            if (e.key === 'Enter') {
                const selection = window.getSelection();
                const parentElement = selection.anchorNode.parentElement;
                
                if (parentElement && parentElement.tagName === 'CODE') {
                    e.preventDefault();
                    // Insert a space after the code block to exit it
                    const range = selection.getRangeAt(0);
                    range.setStartAfter(parentElement);
                    range.setEndAfter(parentElement);
                    selection.removeAllRanges();
                    selection.addRange(range);
                    document.execCommand('insertHTML', false, '<br>');
                }
            }
        }
    });
}

// Format text
function formatText(command, value = null) {
    // Handle lists specially - they toggle on/off
    if (command === 'insertUnorderedList' || command === 'insertOrderedList') {
        document.execCommand(command, false, null);
    } else {
        document.execCommand(command, false, value);
    }
    document.getElementById('editor').focus();
}

// Insert code
function insertCode() {
    const selection = window.getSelection();
    const text = selection.toString();
    
    if (text) {
        // Wrap selected text in code tags
        document.execCommand('insertHTML', false, `<code>${text}</code>`);
    } else {
        // Insert code with a space after to allow easy exit
        document.execCommand('insertHTML', false, '<code>code</code>&nbsp;');
        
        // Move cursor after the code block
        const sel = window.getSelection();
        sel.collapseToEnd();
    }
    
    document.getElementById('editor').focus();
}

// Insert link
function insertLink() {
    const url = prompt('Enter URL:');
    if (url) {
        document.execCommand('createLink', false, url);
    }
    document.getElementById('editor').focus();
}

// Load notes
async function loadNotes() {
    try {
        const response = await fetch('/api/brain-dump/notes');
        const data = await response.json();
        
        if (data.success) {
            notes = data.notes || [];
            displayNotes(notes);
            
            // Update empty state button text based on whether notes exist
            const buttonText = document.getElementById('emptyStateButtonText');
            if (buttonText) {
                buttonText.textContent = notes.length > 0 ? 'Create Note' : 'Create Your First Note';
            }
        }
    } catch (error) {
        console.error('Error loading notes:', error);
        displayNotes([]);
    }
}

// Display notes
function displayNotes(notesToShow) {
    const notesList = document.getElementById('notesList');
    if (!notesList) return;
    
    if (notesToShow.length === 0) {
        notesList.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: #9ca3af;">
                <i class="ph ph-note-blank" style="font-size: 2rem; margin-bottom: 0.5rem; display: block;"></i>
                <p style="font-size: 0.875rem;">No notes yet</p>
            </div>
        `;
        return;
    }
    
    notesList.innerHTML = notesToShow.map(note => {
        const preview = stripHtml(note.content || '').substring(0, 100);
        const tags = note.tags || [];

        // Create tags HTML - show only emojis for preset tags
        const tagsHtml = tags.slice(0, 3).map(tag => {
            const presetTag = getPresetTag(tag);
            if (presetTag) {
                return `<span class="note-item-tag">${presetTag.emoji}</span>`;
            }
            return '';
        }).filter(t => t).join('');

        const moreTags = tags.length > 3 ? `<span class="note-item-tag">+${tags.length - 3}</span>` : '';

        // Add share indicator if note is shared
        const shareIndicator = note.is_shared ? '<span class="note-item-shared" title="Shared"><i class="ph ph-share-network"></i></span>' : '';

        return `
            <div class="note-item ${note.id === currentNoteId ? 'active' : ''}"
                 data-note-id="${note.id}"
                 onclick="selectNote('${note.id}')">
                <div class="note-item-content">
                    <div class="note-item-header">
                        <div class="note-item-title">${escapeHtml(note.title || 'Untitled')}</div>
                        <div class="note-item-badges">
                            ${shareIndicator}
                            ${tags.length > 0 ? `<div class="note-item-tags">${tagsHtml}${moreTags}</div>` : ''}
                        </div>
                    </div>
                    <div class="note-item-preview">${escapeHtml(preview || 'No content')}</div>
                </div>
                <button class="note-delete-btn" onclick="event.stopPropagation(); deleteNote('${note.id}')" title="Delete note">
                    <i class="ph ph-trash"></i>
                </button>
            </div>
        `;
    }).join('');
}

// Show empty editor for new note (without creating in database yet)
function showEmptyEditor() {
    // Clear current note ID to indicate unsaved state
    currentNoteId = null;

    // Show editor area
    document.getElementById('emptyStateContainer').style.display = 'none';
    document.getElementById('editorArea').style.display = 'flex';

    // Clear the editor
    document.getElementById('noteTitle').value = '';
    document.getElementById('editor').innerHTML = '';

    // Update placeholder
    document.getElementById('noteTitle').placeholder = 'Untitled Note';

    // Clear active selection
    document.querySelectorAll('.note-item').forEach(item => {
        item.classList.remove('active');
    });

    // Update save status
    updateSaveStatus('saved');
}

// Create note when user starts typing
async function createNoteIfNeeded() {
    if (currentNoteId) return currentNoteId;

    // Get title and content
    const title = document.getElementById('noteTitle').value.trim();
    const content = document.getElementById('editor').innerHTML.trim();

    // Don't create if both are empty
    if (!title && !content) return null;

    try {
        const response = await fetch('/api/brain-dump/notes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: title || 'Untitled',
                content: content || ''
            })
        });

        const data = await response.json();

        if (data.note) {
            currentNoteId = data.note.id;
            notes.unshift(data.note);
            displayNotes(notes);

            // Highlight the new note
            setTimeout(() => {
                const newItem = document.querySelector(`[data-note-id="${data.note.id}"]`);
                if (newItem) newItem.classList.add('active');
            }, 100);

            return data.note.id;
        }
    } catch (error) {
        console.error('Error creating note:', error);
        showToast('Failed to create note', 'error');
    }

    return null;
}

// Create new note (for button click)
async function createNewNote() {
    showEmptyEditor();
}

// Old create function that posts immediately (if needed)
async function createNewNoteOld() {
    try {
        const response = await fetch('/api/brain-dump/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: '',
                content: '',
                tags: []
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.note) {
            notes.unshift(data.note);
            displayNotes(notes);
            selectNote(data.note.id);
            
            // Focus title
            setTimeout(() => {
                const titleInput = document.getElementById('noteTitle');
                if (titleInput) {
                    titleInput.focus();
                    titleInput.select();
                }
            }, 100);
            
            showToast('Note created', 'success');
        }
    } catch (error) {
        console.error('Error creating note:', error);
        showToast('Failed to create note', 'error');
    }
}

// Select note
function selectNote(noteId) {
    currentNoteId = noteId;
    const note = notes.find(n => n.id === noteId);
    
    if (!note) return;
    
    // Hide empty state container and show editor area
    document.getElementById('emptyStateContainer').style.display = 'none';
    document.getElementById('editorArea').style.display = 'flex';
    
    // Update active state
    document.querySelectorAll('.note-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeItem = document.querySelector(`[data-note-id="${noteId}"]`);
    if (activeItem) activeItem.classList.add('active');
    
    // Load content
    document.getElementById('noteTitle').value = note.title || '';
    document.getElementById('editor').innerHTML = note.content || '';
    
    // Update favorite button
    const favoriteBtn = document.getElementById('favoriteBtn');
    const favoriteIcon = favoriteBtn.querySelector('i');
    if (note.is_favorite) {
        favoriteIcon.className = 'ph ph-star-fill';
        favoriteBtn.classList.add('active');
    } else {
        favoriteIcon.className = 'ph ph-star';
        favoriteBtn.classList.remove('active');
    }
    
    // Update tags UI
    updateTagsUI(note.tags || []);

    // Update share button
    const shareBtn = document.getElementById('shareBtn');
    if (note.is_shared) {
        shareBtn.classList.add('shared');
        currentShareUrl = note.share_url;
    } else {
        shareBtn.classList.remove('shared');
        currentShareUrl = null;
    }
    
    updateSaveStatus('saved');
}

// Save note
async function saveNote(silent = false) {
    if (!currentNoteId) return;
    
    const title = document.getElementById('noteTitle').value || 'Untitled';
    const content = document.getElementById('editor').innerHTML;
    
    updateSaveStatus('saving');
    
    try {
        const response = await fetch(`/api/brain-dump/notes/${currentNoteId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, content, tags: currentNoteTags || [] })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update local note
            const noteIndex = notes.findIndex(n => n.id === currentNoteId);
            if (noteIndex !== -1 && data.note) {
                // Remove the note from its current position
                notes.splice(noteIndex, 1);
                // Add it to the beginning (most recent)
                notes.unshift(data.note);
                displayNotes(notes);
                
                // Re-select the current note by ID to maintain selection
                setTimeout(() => {
                    const activeItem = document.querySelector(`[data-note-id="${currentNoteId}"]`);
                    if (activeItem) activeItem.classList.add('active');
                }, 10);
            }
            
            updateSaveStatus('saved');
            
            if (!silent) {
                showToast('Note saved', 'success');
            }
        } else {
            updateSaveStatus('error');
            if (!silent) {
                showToast('Failed to save', 'error');
            }
        }
    } catch (error) {
        console.error('Error saving note:', error);
        updateSaveStatus('error');
        if (!silent) {
            showToast('Failed to save', 'error');
        }
    }
}

// Delete note
async function deleteNote(noteId) {
    // If no noteId provided, use current note (for backwards compatibility)
    const idToDelete = noteId || currentNoteId;
    if (!idToDelete) return;

    // Get note title for confirmation
    const noteToDelete = notes.find(n => n.id === idToDelete);
    const noteTitle = noteToDelete ? noteToDelete.title || 'Untitled' : 'this note';

    if (!confirm(`Delete "${noteTitle}"? This cannot be undone.`)) return;

    try {
        const response = await fetch(`/api/brain-dump/notes/${idToDelete}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            notes = notes.filter(n => n.id !== idToDelete);
            displayNotes(notes);

            // If we deleted the current note, clear editor
            if (idToDelete === currentNoteId) {
                currentNoteId = null;
                // Hide editor and show empty state
                document.getElementById('editorArea').style.display = 'none';
                document.getElementById('emptyStateContainer').style.display = 'flex';
            }

            showToast('Note deleted', 'success');
        }
    } catch (error) {
        console.error('Error deleting note:', error);
        showToast('Failed to delete', 'error');
    }
}

// Change text color
function changeTextColor(color) {
    document.execCommand('foreColor', false, color);
    document.getElementById('editor').focus();
}

// Toggle favorite
async function toggleFavorite() {
    if (!currentNoteId) return;
    
    const note = notes.find(n => n.id === currentNoteId);
    if (!note) return;
    
    try {
        const response = await fetch(`/api/brain-dump/notes/${currentNoteId}/favorite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_favorite: !note.is_favorite })
        });
        
        const data = await response.json();
        
        if (data.success) {
            note.is_favorite = !note.is_favorite;
            
            const favoriteBtn = document.getElementById('favoriteBtn');
            const favoriteIcon = favoriteBtn.querySelector('i');
            
            if (note.is_favorite) {
                favoriteIcon.className = 'ph ph-star-fill';
                favoriteBtn.classList.add('active');
            } else {
                favoriteIcon.className = 'ph ph-star';
                favoriteBtn.classList.remove('active');
            }
            
            displayNotes(notes);
        }
    } catch (error) {
        console.error('Error toggling favorite:', error);
    }
}

// Filter notes by search
function filterNotes(query) {
    let filtered = notes;

    // Apply search filter
    if (query) {
        const search = query.toLowerCase();
        filtered = filtered.filter(note => {
            return (note.title || '').toLowerCase().includes(search) ||
                   stripHtml(note.content || '').toLowerCase().includes(search);
        });
    }

    displayNotes(filtered);
}

// Update save status
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
            statusIcon.className = 'ph ph-circle-notch';
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

// Utilities
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function stripHtml(html) {
    const tmp = document.createElement('div');
    tmp.innerHTML = html || '';
    return tmp.textContent || tmp.innerText || '';
}

function formatDate(date) {
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (seconds < 60) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
    });
}

function showToast(message, type = 'success') {
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
}

// Tags functionality
function toggleTag(tagName) {
    const tagBtn = document.querySelector(`[data-tag="${tagName}"]`);
    if (!tagBtn) return;

    if (currentNoteTags.includes(tagName)) {
        // Remove tag
        currentNoteTags = currentNoteTags.filter(t => t !== tagName);
        tagBtn.classList.remove('active');
    } else {
        // Add tag
        currentNoteTags.push(tagName);
        tagBtn.classList.add('active');
    }

    // Auto-save
    if (currentNoteId) {
        clearTimeout(autoSaveTimer);
        updateSaveStatus('saving');
        autoSaveTimer = setTimeout(() => saveNote(true), 500);
    }
}

function addCustomTag() {
    const tagName = prompt('Enter tag name:');
    if (!tagName || !tagName.trim()) return;

    const cleanTag = tagName.trim().toLowerCase().replace(/\s+/g, '-');

    if (!currentNoteTags.includes(cleanTag)) {
        currentNoteTags.push(cleanTag);

        // Add custom tag button to UI
        const tagsContainer = document.getElementById('tagsContainer');
        const addBtn = tagsContainer.querySelector('.tag-add');

        const customTag = document.createElement('button');
        customTag.className = 'custom-tag active';
        customTag.setAttribute('data-tag', cleanTag);
        customTag.innerHTML = `
            ${tagName}
            <span class="remove-tag" onclick="removeCustomTag('${cleanTag}', event)">×</span>
        `;
        customTag.onclick = function(e) {
            if (!e.target.classList.contains('remove-tag')) {
                toggleTag(cleanTag);
            }
        };

        tagsContainer.insertBefore(customTag, addBtn);

        // Auto-save
        if (currentNoteId) {
            clearTimeout(autoSaveTimer);
            updateSaveStatus('saving');
            autoSaveTimer = setTimeout(() => saveNote(true), 500);
        }
    }
}

function removeCustomTag(tagName, event) {
    event.stopPropagation();

    currentNoteTags = currentNoteTags.filter(t => t !== tagName);

    const tagBtn = document.querySelector(`[data-tag="${tagName}"]`);
    if (tagBtn && tagBtn.classList.contains('custom-tag')) {
        tagBtn.remove();
    }

    // Auto-save
    if (currentNoteId) {
        clearTimeout(autoSaveTimer);
        updateSaveStatus('saving');
        autoSaveTimer = setTimeout(() => saveNote(true), 500);
    }
}

function updateTagsUI(tags) {
    currentNoteTags = tags || [];

    // Reset all preset tags
    document.querySelectorAll('.tag-preset').forEach(btn => {
        const tagName = btn.getAttribute('data-tag');
        if (currentNoteTags.includes(tagName)) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Remove existing custom tags
    document.querySelectorAll('.custom-tag').forEach(btn => btn.remove());

    // Add custom tags
    const tagsContainer = document.getElementById('tagsContainer');
    const addBtn = tagsContainer.querySelector('.tag-add');

    currentNoteTags.forEach(tag => {
        // Skip if it's a preset tag
        if (document.querySelector(`.tag-preset[data-tag="${tag}"]`)) return;

        const customTag = document.createElement('button');
        customTag.className = 'custom-tag active';
        customTag.setAttribute('data-tag', tag);
        customTag.innerHTML = `
            ${tag}
            <span class="remove-tag" onclick="removeCustomTag('${tag}', event)">×</span>
        `;
        customTag.onclick = function(e) {
            if (!e.target.classList.contains('remove-tag')) {
                toggleTag(tag);
            }
        };

        tagsContainer.insertBefore(customTag, addBtn);
    });
}

// Share functionality
function toggleShare() {
    const modal = document.getElementById('shareModal');
    modal.classList.add('active');

    // Check if note is already shared
    const note = notes.find(n => n.id === currentNoteId);
    if (note && note.is_shared && note.share_url) {
        currentShareUrl = note.share_url;
        document.getElementById('shareLinkInput').value = currentShareUrl;
        document.getElementById('shareLinkContainer').style.display = 'block';
        document.getElementById('createShareBtn').style.display = 'none';
        document.getElementById('unshareBtn').style.display = 'inline-block';
        document.getElementById('shareStatus').textContent = 'Your note is publicly shared:';

        // Update share button
        const shareBtn = document.getElementById('shareBtn');
        shareBtn.classList.add('shared');
    } else {
        document.getElementById('shareLinkContainer').style.display = 'none';
        document.getElementById('createShareBtn').style.display = 'inline-block';
        document.getElementById('unshareBtn').style.display = 'none';
        document.getElementById('shareStatus').textContent = 'Click "Create Share Link" to generate a public URL for this note.';
    }
}

async function createShareLink() {
    if (!currentNoteId) return;

    // Get selected permission
    const permission = document.querySelector('input[name="sharePermission"]:checked').value;

    try {
        const response = await fetch(`/api/brain-dump/notes/${currentNoteId}/share`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ permission })
        });

        const data = await response.json();

        if (data.success) {
            currentShareUrl = data.share_url;
            document.getElementById('shareLinkInput').value = currentShareUrl;
            document.getElementById('shareLinkContainer').style.display = 'block';
            document.getElementById('createShareBtn').style.display = 'none';
            document.getElementById('unshareBtn').style.display = 'inline-block';
            document.getElementById('shareStatus').textContent = 'Your note is publicly shared:';

            // Update share button
            const shareBtn = document.getElementById('shareBtn');
            shareBtn.classList.add('shared');

            // Update note in local state
            const note = notes.find(n => n.id === currentNoteId);
            if (note) {
                note.is_shared = true;
                note.share_url = currentShareUrl;
            }

            showToast('Share link created!', 'success');
        }
    } catch (error) {
        console.error('Error creating share link:', error);
        showToast('Failed to create share link', 'error');
    }
}

async function unshareNote() {
    if (!currentNoteId) return;

    if (confirm('Are you sure you want to remove the public share link?')) {
        try {
            const response = await fetch(`/api/brain-dump/notes/${currentNoteId}/unshare`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (data.success) {
                currentShareUrl = null;
                document.getElementById('shareLinkContainer').style.display = 'none';
                document.getElementById('createShareBtn').style.display = 'inline-block';
                document.getElementById('unshareBtn').style.display = 'none';
                document.getElementById('shareStatus').textContent = 'Click "Create Share Link" to generate a public URL for this note.';

                // Update share button
                const shareBtn = document.getElementById('shareBtn');
                shareBtn.classList.remove('shared');

                // Update note in local state
                const note = notes.find(n => n.id === currentNoteId);
                if (note) {
                    note.is_shared = false;
                    note.share_url = null;
                }

                showToast('Share link removed', 'success');
            }
        } catch (error) {
            console.error('Error removing share link:', error);
            showToast('Failed to remove share link', 'error');
        }
    }
}

function copyShareLink() {
    const input = document.getElementById('shareLinkInput');
    input.select();
    document.execCommand('copy');

    const btn = document.getElementById('copyLinkBtn');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');

    setTimeout(() => {
        btn.textContent = 'Copy';
        btn.classList.remove('copied');
    }, 2000);

    showToast('Link copied to clipboard!', 'success');
}

function closeShareModal() {
    const modal = document.getElementById('shareModal');
    modal.classList.remove('active');
}

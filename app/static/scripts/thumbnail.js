// Thumbnail Generator JavaScript
(function() {
    'use strict';
    
    // Initialize namespace
    window.CreatorPal = window.CreatorPal || {};
    window.CreatorPal.Thumbnail = window.CreatorPal.Thumbnail || {};
    
    // Check if already initialized
    if (window.CreatorPal.Thumbnail.initialized) {
        console.log('Thumbnail Generator already initialized, skipping...');
        return;
    }

    // Global variables
    let selectedModel = 'nano-banana';
    let uploadedFiles = [null, null, null, null];
    let generationHistory = [];
    let numImages = 1;
    let currentPage = 1;
    const itemsPerPage = 16;

    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        loadHistory();
        window.CreatorPal.Thumbnail.initialized = true;
        console.log('Thumbnail Generator initialized');
    });

    // Model selection and UI functions
    function selectModel(model) {
        selectedModel = model;
        document.querySelectorAll('.model-card').forEach(card => {
            card.classList.remove('selected');
            if (card.dataset.model === model) {
                card.classList.add('selected');
            }
        });
        updateCreditDisplay();

        // Switch preset prompts based on selected model (only if presets are visible)
        const canvasPresets = document.getElementById('canvasPresets');
        const photoPresets = document.getElementById('photoPresets');
        const isPresetsExpanded = canvasPresets.style.display !== 'none' || photoPresets.style.display !== 'none';

        if (isPresetsExpanded) {
            if (model === 'nano-banana') {
                canvasPresets.style.display = 'flex';
                photoPresets.style.display = 'none';
            } else {
                canvasPresets.style.display = 'none';
                photoPresets.style.display = 'flex';
            }
        }
    }

    function togglePresets() {
        const canvasPresets = document.getElementById('canvasPresets');
        const photoPresets = document.getElementById('photoPresets');
        const toggleIcon = document.getElementById('presetToggleIcon');
        const currentModel = selectedModel;

        // Check if either preset is currently visible
        const isExpanded = canvasPresets.style.display !== 'none' || photoPresets.style.display !== 'none';

        if (isExpanded) {
            // Collapse
            canvasPresets.style.display = 'none';
            photoPresets.style.display = 'none';
            toggleIcon.style.transform = 'rotate(0deg)';
        } else {
            // Expand and show correct presets based on model
            if (currentModel === 'nano-banana') {
                canvasPresets.style.display = 'flex';
                photoPresets.style.display = 'none';
            } else if (currentModel === 'seeddream') {
                canvasPresets.style.display = 'none';
                photoPresets.style.display = 'flex';
            }
            toggleIcon.style.transform = 'rotate(90deg)';
        }
    }

    function applyPreset(prompt) {
        document.getElementById('promptInput').value = prompt;
        updateCharCount();
        showToast('Preset applied', 'success');
    }

    // Number of images controls
    function increaseNumImages() {
        if (numImages < 4) {
            numImages++;
            updateNumImagesDisplay();
        }
    }

    function decreaseNumImages() {
        if (numImages > 1) {
            numImages--;
            updateNumImagesDisplay();
        }
    }

    function updateNumImagesDisplay() {
        document.getElementById('numImagesDisplay').textContent = numImages;

        // Update button states
        document.getElementById('decreaseBtn').disabled = numImages === 1;
        document.getElementById('increaseBtn').disabled = numImages === 4;

        updateCreditDisplay();
    }

    function updateCreditDisplay() {
        const baseCost = selectedModel === 'nano-banana' ? 5 : 4;
        const totalCost = baseCost * numImages;

        // Update the credit display in the model cards
        if (selectedModel === 'nano-banana') {
            document.getElementById('nano-cost').textContent = totalCost;
            document.getElementById('seed-cost').textContent = '4';
        } else {
            document.getElementById('nano-cost').textContent = '5';
            document.getElementById('seed-cost').textContent = totalCost;
        }

        // Update improve prompt cost based on number of uploaded images
        updateImprovePromptCost();
    }

    function updateImprovePromptCost() {
        // Count uploaded images
        const imageCount = uploadedFiles.filter(f => f !== null).length;

        // Calculate cost: 0 photos: 0.2, 1: 0.5, 2: 0.7, 3: 0.9, 4: 1.0
        let cost;
        if (imageCount === 0) cost = 0.2;
        else if (imageCount === 1) cost = 0.5;
        else if (imageCount === 2) cost = 0.7;
        else if (imageCount === 3) cost = 0.9;
        else cost = 1.0;

        // Update the display
        const costSpan = document.getElementById('improveCost');
        if (costSpan) {
            costSpan.innerHTML = `<i class="ph ph-coin" style="font-size: 0.75rem;"></i> ${cost}`;
        }
    }

    function updateCharCount() {
        const prompt = document.getElementById('promptInput');
        const count = prompt.value.length;
        document.getElementById('charCount').textContent = `${count} / 1000`;
    }

    // File upload functions
    function triggerUpload(index) {
        if (event.target.classList.contains('remove-btn')) {
            return;
        }
        document.getElementById(`file${index}`).click();
    }

    function handleUpload(index, input) {
        const file = input.files[0];
        if (file) {
            if (file.size > 10 * 1024 * 1024) {
                showToast('Image must be less than 10MB', 'error');
                return;
            }

            const reader = new FileReader();
            reader.onload = function(e) {
                const slot = document.querySelectorAll('.upload-slot')[index];
                slot.classList.add('has-image');
                slot.innerHTML = `
                    <span class="upload-number">${index + 1}</span>
                    <img src="${e.target.result}" alt="Uploaded image ${index + 1}">
                    <button class="remove-btn" onclick="removeImage(${index}, event)">
                        <i class="ph ph-x"></i>
                    </button>
                    <input type="file" id="file${index}" accept="image/*" onchange="handleUpload(${index}, this)" style="display: none;">
                `;
                uploadedFiles[index] = file;
                updateImprovePromptCost();
            };
            reader.readAsDataURL(file);
        }
    }

    function removeImage(index, event) {
        event.stopPropagation();
        uploadedFiles[index] = null;
        const slot = document.querySelectorAll('.upload-slot')[index];
        slot.classList.remove('has-image');
        slot.innerHTML = `
            <span class="upload-number">${index + 1}</span>
            <input type="file" id="file${index}" accept="image/*" onchange="handleUpload(${index}, this)" style="display: none;">
            <div class="upload-placeholder">
                <i class="ph ph-upload upload-icon"></i>
                <div class="upload-text">Click to upload</div>
            </div>
        `;
        updateImprovePromptCost();
    }

    // Generation function
    async function generateThumbnail() {
        const prompt = document.getElementById('promptInput').value.trim();
        const generateBtn = document.getElementById('generateBtn');
        const resultContainer = document.getElementById('resultContainer');

        // Validate
        if (!prompt) {
            showToast('Please enter a prompt', 'error');
            return;
        }

        const hasImages = uploadedFiles.some(f => f !== null);
        if (!hasImages) {
            showToast('Please upload at least one image', 'error');
            return;
        }

        // Prepare form data
        const formData = new FormData();
        formData.append('prompt', prompt);
        formData.append('model', selectedModel);
        formData.append('num_images', numImages);

        uploadedFiles.forEach(file => {
            if (file) {
                formData.append('images', file);
            }
        });

        // Show loading
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span style="display: inline-flex; align-items: center; gap: 0.5rem;"><div class="loading-spinner" style="width: 16px; height: 16px; border-width: 2px;"></div> Generating...</span>';
        
        resultContainer.classList.remove('has-result');
        resultContainer.innerHTML = `
            <div class="loading-overlay">
                <div class="loading-spinner"></div>
                <div class="loading-text">Creating your thumbnail...</div>
            </div>
        `;

        try {
            const response = await fetch('/thumbnail/generate', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                const result = data.result;
                let imageUrls = [];

                // Extract all image URLs from the response
                if (result.images && result.images.length > 0) {
                    imageUrls = result.images.map(img => img.url || img);
                } else if (result.image) {
                    imageUrls = [result.image.url || result.image];
                } else if (result.output) {
                    imageUrls = [result.output];
                }

                if (imageUrls.length > 0) {
                    resultContainer.classList.add('has-result');

                    // If multiple images, show grid
                    if (imageUrls.length > 1) {
                        let gridHtml = '<div class="result-grid">';
                        imageUrls.forEach((url, index) => {
                            gridHtml += `
                                <div class="result-grid-item">
                                    <img src="${url}" alt="Generated thumbnail ${index + 1}" onclick="openLightbox('${url}')">
                                    <div class="result-item-actions">
                                        <button class="action-btn" onclick="editImage('${url}')" title="Edit">
                                            <i class="ph ph-pencil"></i>
                                        </button>
                                        <button class="action-btn" onclick="downloadImage('${url}', ${index + 1})" title="Download">
                                            <i class="ph ph-download"></i>
                                        </button>
                                        <button class="action-btn" onclick="upscaleImage('${url}')" title="Upscale (10 credits)">
                                            <i class="ph ph-arrows-out"></i>
                                        </button>
                                    </div>
                                </div>
                            `;
                        });
                        gridHtml += '</div>';
                        resultContainer.innerHTML = gridHtml;
                    } else {
                        // Single image display
                        resultContainer.innerHTML = `
                            <div class="result-image">
                                <img src="${imageUrls[0]}" alt="Generated thumbnail" onclick="openLightbox('${imageUrls[0]}')">
                                <div class="result-actions">
                                    <button class="action-btn" onclick="editImage('${imageUrls[0]}')">
                                        <i class="ph ph-pencil"></i>
                                        Edit
                                    </button>
                                    <button class="action-btn" onclick="downloadImage('${imageUrls[0]}')">
                                        <i class="ph ph-download"></i>
                                        Download
                                    </button>
                                    <button class="action-btn" onclick="upscaleImage('${imageUrls[0]}')">
                                        <i class="ph ph-arrows-out"></i>
                                        Upscale (10 credits)
                                    </button>
                                </div>
                            </div>
                        `;
                    }

                    // Refresh history to show new thumbnails
                    loadHistory();
                }
            } else {
                if (data.error_type === 'insufficient_credits') {
                    resultContainer.innerHTML = `
                        <div class="insufficient-credits-card">
                            <div class="credit-icon-wrapper">
                                <i class="ph ph-coins"></i>
                            </div>
                            <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Insufficient Credits</h3>
                            <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">
                                You need <strong>${data.required_credits}</strong> credits but only have
                                <strong>${data.current_credits?.toFixed(2)}</strong> credits.
                            </p>
                            <a href="/payment" class="upgrade-plan-btn">
                                <i class="ph ph-crown"></i>
                                Upgrade Plan
                            </a>
                        </div>
                    `;
                } else {
                    throw new Error(data.error || 'Generation failed');
                }
            }
        } catch (error) {
            console.error('Error:', error);
            resultContainer.innerHTML = `
                <div class="error-message">
                    <i class="ph ph-warning"></i>
                    Error: ${error.message}
                </div>
            `;
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="ph ph-magic-wand"></i> Generate';
        }
    }

    // History management functions
    async function loadHistory() {
        try {
            const response = await fetch('/thumbnail/history?limit=100', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('authToken')}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch history');
            }

            const data = await response.json();

            if (data.success) {
                generationHistory = data.thumbnails || [];
                console.log(`Loaded ${generationHistory.length} items from server`);
                renderHistory();
            } else {
                generationHistory = [];
                renderEmptyHistory();
            }
        } catch (error) {
            console.error('Error loading history:', error);
            generationHistory = [];
            renderEmptyHistory();
        }
    }

    function renderHistory() {
        const container = document.getElementById('historyContainer');

        if (generationHistory.length === 0) {
            renderEmptyHistory();
            return;
        }

        // Calculate pagination
        const totalItems = generationHistory.length;
        const totalPages = Math.ceil(totalItems / itemsPerPage);
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = Math.min(startIndex + itemsPerPage, totalItems);
        const pageItems = generationHistory.slice(startIndex, endIndex);

        let html = '<div class="history-grid">';
        pageItems.forEach((item, relativeIndex) => {
            const actualIndex = startIndex + relativeIndex;
            const date = new Date(item.created_at || item.timestamp);
            const timeAgo = getTimeAgo(date);
            const modelDisplay = item.model === 'nano-banana' ? 'Canvas Editor' :
                               item.model === 'topaz-upscale' ? 'Upscaled' : 'Photo Editor';

            html += `
                <div class="history-item">
                    <button class="delete-history-btn" onclick="deleteHistoryItem(${actualIndex}, event)" title="Delete">
                        <i class="ph ph-trash"></i>
                    </button>
                    <div class="history-thumbnail" onclick="openLightbox('${item.url}')">
                        <img src="${item.url}" alt="${item.prompt}">
                    </div>
                    <div class="history-info">
                        <div class="history-prompt">${item.prompt}</div>
                        <div class="history-meta">
                            <span>${timeAgo}</span>
                            <span class="history-model">${modelDisplay}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        // Add pagination controls
        html += `
            <div class="pagination-controls">
                <button class="pagination-btn" onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
                    <i class="ph ph-caret-left"></i>
                </button>
                <div class="pagination-info">
                    Page ${currentPage} of ${totalPages}
                </div>
                <button class="pagination-btn" onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
                    <i class="ph ph-caret-right"></i>
                </button>
            </div>
        `;

        container.innerHTML = html;
    }

    function changePage(page) {
        const totalPages = Math.ceil(generationHistory.length / itemsPerPage);
        if (page >= 1 && page <= totalPages) {
            currentPage = page;
            renderHistory();
            document.querySelector('.history-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function renderEmptyHistory() {
        const container = document.getElementById('historyContainer');
        container.innerHTML = `
            <div class="empty-state">
                <i class="ph ph-image-square"></i>
                <p>No generations yet</p>
                <p style="font-size: 0.875rem; font-weight: 400;">Your thumbnails will appear here</p>
            </div>
        `;
    }

    function openLightbox(url) {
        const resultContainer = document.getElementById('resultContainer');
        resultContainer.classList.add('has-result');
        resultContainer.innerHTML = `
            <div class="result-image">
                <img src="${url}" alt="Selected thumbnail">
                <div class="result-actions">
                    <button class="action-btn" onclick="editImage('${url}')">
                        <i class="ph ph-pencil"></i>
                        Edit
                    </button>
                    <button class="action-btn" onclick="downloadImage('${url}')">
                        <i class="ph ph-download"></i>
                        Download
                    </button>
                    <button class="action-btn" onclick="upscaleImage('${url}')">
                        <i class="ph ph-arrows-out"></i>
                        Upscale (10 credits)
                    </button>
                </div>
            </div>
        `;
        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    async function deleteHistoryItem(index, event) {
        event.stopPropagation();
        const item = generationHistory[index];
        if (!item || !item.id) {
            showToast('Cannot delete this item', 'error');
            return;
        }

        try {
            const response = await fetch(`/thumbnail/history/${item.id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('authToken')}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to delete thumbnail');
            }

            const data = await response.json();
            if (data.success) {
                generationHistory.splice(index, 1);
                const totalPages = Math.ceil(generationHistory.length / itemsPerPage);
                if (currentPage > totalPages && totalPages > 0) {
                    currentPage = totalPages;
                }
                renderHistory();
                showToast('Thumbnail removed from history', 'success');
            } else {
                showToast(data.error || 'Failed to delete thumbnail', 'error');
            }
        } catch (error) {
            console.error('Error deleting thumbnail:', error);
            showToast('Failed to delete thumbnail', 'error');
        }
    }

    // Utility functions
    function getTimeAgo(date) {
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        if (seconds < 60) return 'Just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
        return date.toLocaleDateString();
    }

    async function downloadImage(url, index = null) {
        try {
            const response = await fetch(url);
            const blob = await response.blob();
            const blobUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            const timestamp = Date.now();
            const filename = index ? `thumbnail-${timestamp}-${index}.png` : `thumbnail-${timestamp}.png`;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(blobUrl);
            showToast('Download started', 'success');
        } catch (error) {
            console.error('Download error:', error);
            const a = document.createElement('a');
            a.href = url;
            const timestamp = Date.now();
            const filename = index ? `thumbnail-${timestamp}-${index}.png` : `thumbnail-${timestamp}.png`;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast('Download started', 'success');
        }
    }

    async function editImage(url) {
        try {
            const response = await fetch(url);
            const blob = await response.blob();
            const file = new File([blob], 'edit-image.jpg', { type: blob.type });
            uploadedFiles = [null, null, null, null];
            uploadedFiles[0] = file;
            const slot = document.querySelector('.upload-slot');
            const reader = new FileReader();
            reader.onload = (e) => {
                slot.classList.add('has-image');
                slot.innerHTML = `
                    <span class="upload-number">1</span>
                    <img src="${e.target.result}" alt="Uploaded image">
                    <button class="remove-btn" onclick="removeImage(0, event)">
                        <i class="ph ph-x"></i>
                    </button>
                    <input type="file" id="file0" accept="image/*" onchange="handleUpload(0, this)" style="display: none;">
                `;
            };
            reader.readAsDataURL(file);
            document.querySelector('.input-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
            showToast('Image loaded for editing', 'success');
        } catch (error) {
            console.error('Error loading image for edit:', error);
            showToast('Failed to load image for editing', 'error');
        }
    }

    async function upscaleImage(url) {
        try {
            const resultContainer = document.getElementById('resultContainer');
            resultContainer.classList.add('has-result');
            resultContainer.innerHTML = `
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <p class="loading-text">Upscaling your image...</p>
                    <p class="loading-subtext">This may take a few moments</p>
                </div>
            `;
            resultContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
            showToast('Starting upscale process...', 'info');

            let imageData = url;
            let mimeType = 'image/jpeg';

            if (!url.startsWith('data:')) {
                const response = await fetch(url);
                const blob = await response.blob();
                mimeType = blob.type || 'image/jpeg';
                const reader = new FileReader();
                const base64Promise = new Promise((resolve) => {
                    reader.onloadend = () => resolve(reader.result);
                });
                reader.readAsDataURL(blob);
                imageData = await base64Promise;
            }

            const upscaleResponse = await fetch('/thumbnail/upscale', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('authToken')}`
                },
                body: JSON.stringify({
                    image_data: imageData,
                    mime_type: mimeType
                })
            });

            if (!upscaleResponse.ok) {
                const error = await upscaleResponse.json();
                resultContainer.innerHTML = '';
                resultContainer.classList.remove('has-result');
                if (error.error_type === 'insufficient_credits') {
                    showToast(`Insufficient credits. You need ${error.required_credits} credits but have ${error.current_credits.toFixed(2)}`, 'error');
                } else {
                    showToast(error.error || 'Failed to upscale image', 'error');
                }
                return;
            }

            const result = await upscaleResponse.json();
            if (result.success && result.result) {
                let upscaledUrl = null;
                if (result.result.image && result.result.image.url) {
                    upscaledUrl = result.result.image.url;
                } else if (result.result.image) {
                    upscaledUrl = result.result.image;
                } else if (result.result.url) {
                    upscaledUrl = result.result.url;
                } else if (typeof result.result === 'string') {
                    upscaledUrl = result.result;
                }

                if (!upscaledUrl) {
                    console.error('Unexpected result structure:', result);
                    resultContainer.innerHTML = '';
                    resultContainer.classList.remove('has-result');
                    showToast('Failed to get upscaled image URL', 'error');
                    return;
                }

                resultContainer.innerHTML = `
                    <div class="result-image">
                        <img src="${upscaledUrl}" alt="Upscaled image">
                        <div class="result-actions">
                            <button class="action-btn" onclick="editImage('${upscaledUrl}')">
                                <i class="ph ph-pencil"></i>
                                Edit
                            </button>
                            <button class="action-btn" onclick="downloadImage('${upscaledUrl}')">
                                <i class="ph ph-download"></i>
                                Download Upscaled
                            </button>
                        </div>
                    </div>
                `;
                loadHistory();
                showToast(`Image upscaled successfully! Used ${result.credits_used} credits`, 'success');
                resultContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                resultContainer.innerHTML = '';
                resultContainer.classList.remove('has-result');
                showToast('Failed to get upscaled image', 'error');
            }
        } catch (error) {
            console.error('Upscale error:', error);
            const resultContainer = document.getElementById('resultContainer');
            resultContainer.innerHTML = '';
            resultContainer.classList.remove('has-result');
            showToast('Failed to upscale image', 'error');
        }
    }

    async function improvePrompt() {
        const prompt = document.getElementById('promptInput').value.trim();
        const improveBtn = document.getElementById('improveBtn');

        if (!prompt) {
            showToast('Please enter a prompt to improve', 'error');
            return;
        }

        const hasImages = uploadedFiles.some(f => f !== null);
        let allImagesData = [];

        if (hasImages) {
            for (let file of uploadedFiles) {
                if (file) {
                    const reader = new FileReader();
                    const imageDataWithMime = await new Promise(resolve => {
                        reader.onloadend = () => {
                            const dataUrl = reader.result;
                            const [header, base64] = dataUrl.split(',');
                            const mimeType = header.match(/data:(.+);base64/)[1];
                            resolve({
                                base64: base64,
                                mimeType: mimeType
                            });
                        };
                        reader.readAsDataURL(file);
                    });
                    allImagesData.push(imageDataWithMime);
                }
            }
        }

        improveBtn.disabled = true;
        improveBtn.innerHTML = '<i class="ph ph-spinner"></i> Improving...';

        try {
            const response = await fetch('/thumbnail/improve-prompt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt: prompt,
                    model: selectedModel,
                    image_data: allImagesData.length > 0 ? allImagesData[0].base64 : null,
                    all_images_with_types: allImagesData
                })
            });

            const data = await response.json();
            if (data.success) {
                document.getElementById('promptInput').value = data.improved_prompt;
                updateCharCount();
                showToast('Prompt improved!', 'success');
            } else {
                showToast(data.error || 'Failed to improve prompt', 'error');
            }
        } catch (error) {
            console.error('Error improving prompt:', error);
            showToast('Error improving prompt', 'error');
        } finally {
            improveBtn.disabled = false;
            improveBtn.innerHTML = '<i class="ph ph-magic-wand"></i> Improve Prompt';
        }
    }

    function showToast(message, type = 'info') {
        if (window.BaseApp && window.BaseApp.showToast) {
            window.BaseApp.showToast(message, type);
        }
    }

    // Expose functions to global scope for onclick handlers
    window.selectModel = selectModel;
    window.togglePresets = togglePresets;
    window.applyPreset = applyPreset;
    window.increaseNumImages = increaseNumImages;
    window.decreaseNumImages = decreaseNumImages;
    window.triggerUpload = triggerUpload;
    window.handleUpload = handleUpload;
    window.removeImage = removeImage;
    window.updateCharCount = updateCharCount;
    window.generateThumbnail = generateThumbnail;
    window.changePage = changePage;
    window.openLightbox = openLightbox;
    window.deleteHistoryItem = deleteHistoryItem;
    window.downloadImage = downloadImage;
    window.editImage = editImage;
    window.upscaleImage = upscaleImage;
    window.improvePrompt = improvePrompt;

})();

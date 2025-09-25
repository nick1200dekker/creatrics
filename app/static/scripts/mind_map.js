// Mind Map Application - Clean JavaScript
// Global variables
let selectedNode = null;
let connectionMode = false;
let firstConnectionNode = null;
let connections = [];
let nodeCounter = 0;
let currentMapId = 'map1';
let currentZoom = 1;
let panX = 0;
let panY = 0;
let maps = {
    'map1': {
        id: 'map1',
        name: 'Map 1',
        nodes: [],
        connections: [],
        created: new Date().toISOString(),
        updated: new Date().toISOString()
    }
};

// Initialize mind map when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing Mind Map...');
    
    // Load existing data from Firebase
    loadFromFirebase();
    
    // Setup zoom controls
    setupZoomControls();
    
    // Get canvas reference
    const canvas = document.getElementById('mindMapCanvas');
    const svg = document.getElementById('connectionsSvg');
    
    // Initialize SVG dimensions - keep it simple
    if (svg && canvas) {
        svg.style.width = '100%';
        svg.style.height = '100%';
        svg.removeAttribute('viewBox'); // Remove viewBox to use pixel coordinates
    }
    
    // Add mouse wheel zoom
    if (canvas) {
        canvas.addEventListener('wheel', function(e) {
            e.preventDefault();
            
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
            const newZoom = Math.min(Math.max(currentZoom * zoomFactor, 0.3), 3);
            
            if (newZoom !== currentZoom) {
                // Zoom towards mouse position
                const zoomChange = newZoom / currentZoom;
                panX = mouseX - (mouseX - panX) * zoomChange;
                panY = mouseY - (mouseY - panY) * zoomChange;
                
                currentZoom = newZoom;
                applyZoom();
            }
        });
        
        // Add canvas panning
        let isPanning = false;
        let panStartX, panStartY;
        let panStartPanX, panStartPanY;
        
        canvas.addEventListener('mousedown', function(e) {
            if (e.target === canvas && e.button === 0) { // Left mouse button on empty canvas
                isPanning = true;
                panStartX = e.clientX;
                panStartY = e.clientY;
                panStartPanX = panX;
                panStartPanY = panY;
                canvas.style.cursor = 'grabbing';
            }
        });
        
        document.addEventListener('mousemove', function(e) {
            if (isPanning) {
                panX = panStartPanX + (e.clientX - panStartX);
                panY = panStartPanY + (e.clientY - panStartY);
                applyZoom();
            }
        });
        
        document.addEventListener('mouseup', function(e) {
            if (isPanning) {
                isPanning = false;
                canvas.style.cursor = 'grab';
                
                // If we didn't move much, treat it as a click to deselect
                const moveDistance = Math.abs(e.clientX - panStartX) + Math.abs(e.clientY - panStartY);
                if (moveDistance < 5 && e.target === canvas) { // Less than 5px movement = click on canvas
                    // Deselect all nodes
                    document.querySelectorAll('.mind-node').forEach(n => n.classList.remove('selected'));
                    selectedNode = null;
                    
                    // Clear properties panel
                    const textArea = document.getElementById('nodeText');
                    if (textArea) textArea.value = '';
                    
                    console.log('Deselected all nodes');
                }
            }
        });
    }
});

// Zoom functions
function setupZoomControls() {
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const zoomResetBtn = document.getElementById('zoomResetBtn');
    
    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', () => zoomIn());
    }
    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', () => zoomOut());
    }
    if (zoomResetBtn) {
        zoomResetBtn.addEventListener('click', () => resetZoom());
    }
    
    updateZoomDisplay();
}

function zoomIn() {
    currentZoom = Math.min(currentZoom * 1.2, 3);
    applyZoom();
}

function zoomOut() {
    currentZoom = Math.max(currentZoom / 1.2, 0.3);
    applyZoom();
}

function resetZoom() {
    currentZoom = 1;
    panX = 0;
    panY = 0;
    applyZoom();
}

function applyZoom() {
    const container = document.getElementById('canvasContainer');
    const svg = document.getElementById('connectionsSvg');
    
    if (container) {
        container.style.transform = `translate(${panX}px, ${panY}px) scale(${currentZoom})`;
    }
    
    // DON'T transform the SVG - keep it fixed to the canvas
    if (svg) {
        svg.style.transform = 'none';
    }
    
    updateZoomDisplay();
    updateConnections();
}

function updateZoomDisplay() {
    const zoomLevel = document.getElementById('zoomLevel');
    if (zoomLevel) {
        zoomLevel.textContent = Math.round(currentZoom * 100) + '%';
    }
}

// Node management functions
function addNewNode() {
    const container = document.getElementById('canvasContainer');
    if (!container) return;
    
    nodeCounter++;
    const x = 200 + Math.random() * 400;
    const y = 150 + Math.random() * 300;
    
    const node = document.createElement('div');
    node.className = 'mind-node';
    node.id = 'node_' + nodeCounter;
    node.style.left = x + 'px';
    node.style.top = y + 'px';
    node.style.width = '180px';
    node.style.height = 'auto';
    
    const nodeText = document.createElement('div');
    nodeText.className = 'node-text';
    nodeText.textContent = 'New Node';
    
    node.appendChild(nodeText);
    container.appendChild(node);
    
    makeDraggable(node);
    addNodeClickHandlers(node);
    
    console.log('Added node:', node.id, 'at', x, y);
    return node;
}

// Connection functions
function updateConnections() {
    connections.forEach(conn => {
        const node1 = document.getElementById(conn.from);
        const node2 = document.getElementById(conn.to);
        
        if (node1 && node2 && conn.element) {
            // Get node positions in container coordinates
            const node1X = parseInt(node1.style.left) || 0;
            const node1Y = parseInt(node1.style.top) || 0;
            const node2X = parseInt(node2.style.left) || 0;
            const node2Y = parseInt(node2.style.top) || 0;
            
            // Get node centers
            const x1 = node1X + node1.offsetWidth/2;
            const y1 = node1Y + node1.offsetHeight/2;
            const x2 = node2X + node2.offsetWidth/2;
            const y2 = node2Y + node2.offsetHeight/2;
            
            // Calculate edge points (where line should start/end)
            const angle = Math.atan2(y2 - y1, x2 - x1);
            
            // Start point (edge of first node)
            const startX = x1 + Math.cos(angle) * (node1.offsetWidth/2 + 5);
            const startY = y1 + Math.sin(angle) * (node1.offsetHeight/2 + 5);
            
            // End point (edge of second node)  
            const endX = x2 - Math.cos(angle) * (node2.offsetWidth/2 + 15);
            const endY = y2 - Math.sin(angle) * (node2.offsetHeight/2 + 15);
            
            // Transform coordinates for zoom and pan
            const transformedStartX = startX * currentZoom + panX;
            const transformedStartY = startY * currentZoom + panY;
            const transformedEndX = endX * currentZoom + panX;
            const transformedEndY = endY * currentZoom + panY;
            
            conn.element.setAttribute('x1', transformedStartX);
            conn.element.setAttribute('y1', transformedStartY);
            conn.element.setAttribute('x2', transformedEndX);
            conn.element.setAttribute('y2', transformedEndY);
        }
    });
}

// Node interaction functions
function makeDraggable(node) {
    let isDragging = false;
    let isResizing = false;
    let startX, startY, initialX, initialY, initialWidth, initialHeight;
    
    node.addEventListener('mousedown', function(e) {
        if (e.target.contentEditable === 'true') return;
        
        const rect = node.getBoundingClientRect();
        const isResizeArea = (e.clientX > rect.right - 15) && (e.clientY > rect.bottom - 15);
        
        if (isResizeArea) {
            isResizing = true;
            startX = e.clientX;
            startY = e.clientY;
            initialWidth = node.offsetWidth;
            initialHeight = node.offsetHeight;
            node.style.cursor = 'nw-resize';
        } else {
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            initialX = parseInt(node.style.left) || 0;
            initialY = parseInt(node.style.top) || 0;
            node.style.cursor = 'grabbing';
        }
        
        e.preventDefault();
        e.stopPropagation();
    });
    
    document.addEventListener('mousemove', function(e) {
        if (isDragging) {
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            node.style.left = (initialX + deltaX) + 'px';
            node.style.top = (initialY + deltaY) + 'px';
            
            updateConnections();
        } else if (isResizing) {
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            const newWidth = Math.max(120, initialWidth + deltaX);
            const newHeight = Math.max(60, initialHeight + deltaY);
            
            node.style.width = newWidth + 'px';
            node.style.height = newHeight + 'px';
            
            // For shaped nodes, maintain aspect ratio
            if (node.classList.contains('shape-circle')) {
                const size = Math.max(newWidth, newHeight);
                node.style.width = size + 'px';
                node.style.height = size + 'px';
            } else if (node.classList.contains('shape-square')) {
                const size = Math.max(newWidth, newHeight);
                node.style.width = size + 'px';
                node.style.height = size + 'px';
            } else if (node.classList.contains('shape-diamond')) {
                const size = Math.max(newWidth, newHeight);
                node.style.width = size + 'px';
                node.style.height = size + 'px';
            }
            
            updateConnections();
        }
    });
    
    document.addEventListener('mouseup', function() {
        if (isDragging) {
            isDragging = false;
            node.style.cursor = 'move';
        } else if (isResizing) {
            isResizing = false;
            node.style.cursor = 'move';
        }
    });
}

function addNodeClickHandlers(node) {
    let clickCount = 0;
    let clickTimer = null;
    
    node.addEventListener('click', function(e) {
        e.stopPropagation();
        
        clickCount++;
        
        if (clickCount === 1) {
            clickTimer = setTimeout(() => {
                selectNode(node);
                clickCount = 0;
            }, 300);
        } else if (clickCount === 2) {
            clearTimeout(clickTimer);
            editNodeText(node);
            clickCount = 0;
        }
    });
}

function selectNode(node) {
    if (connectionMode) {
        handleConnectionClick(node);
        return;
    }
    
    document.querySelectorAll('.mind-node').forEach(n => n.classList.remove('selected'));
    node.classList.add('selected');
    selectedNode = node;
    
    updatePropertiesPanel(node);
    console.log('Selected node:', node.id);
}

function editNodeText(node) {
    const textDiv = node.querySelector('.node-text');
    textDiv.contentEditable = true;
    textDiv.focus();
    
    const range = document.createRange();
    range.selectNodeContents(textDiv);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    
    textDiv.addEventListener('blur', function() {
        textDiv.contentEditable = false;
        updatePropertiesPanel(node);
    }, { once: true });
    
    textDiv.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            textDiv.blur();
        }
    });
}

function updatePropertiesPanel(node) {
    const textArea = document.getElementById('nodeText');
    const shapeSelect = document.getElementById('nodeShape');
    const fontSelect = document.getElementById('nodeFontSize');
    
    if (textArea) textArea.value = node.querySelector('.node-text').textContent;
    if (shapeSelect) {
        const shape = node.classList.contains('shape-circle') ? 'circle' :
                     node.classList.contains('shape-square') ? 'square' :
                     node.classList.contains('shape-diamond') ? 'diamond' : 'rectangle';
        shapeSelect.value = shape;
    }
    if (fontSelect) {
        const fontSize = node.querySelector('.node-text').style.fontSize || '14px';
        fontSelect.value = fontSize;
    }
}

// Firebase functions
async function loadFromFirebase() {
    try {
        const response = await fetch('/api/mind-map/load');
        const result = await response.json();
        
        if (result.success && result.data) {
            maps = result.data.maps || maps;
            currentMapId = result.data.currentMapId || 'map1';
            
            rebuildTabs();
            clearCanvas();
            loadMapState(currentMapId);
            
            console.log('Loaded from Firebase successfully');
        }
    } catch (error) {
        console.error('Load error:', error);
    }
}

async function saveToFirebase() {
    try {
        saveCurrentMapState();
        
        const response = await fetch('/api/mind-map/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                maps: maps,
                currentMapId: currentMapId
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('Saved to Firebase successfully');
        } else {
            console.error('Save failed:', result.error);
            alert('Failed to save: ' + result.error);
        }
    } catch (error) {
        console.error('Save error:', error);
        alert('Failed to save mind map');
    }
}

// Connection functions
function createConnection(node1, node2) {
    const svg = document.getElementById('connectionsSvg');
    
    const connection = {
        id: 'conn_' + Date.now(),
        from: node1.id,
        to: node2.id,
        element: null
    };
    
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('class', 'connection-line');
    line.setAttribute('stroke', '#3B82F6');
    line.setAttribute('stroke-width', '2');
    line.setAttribute('marker-end', 'url(#arrowhead)');
    line.setAttribute('data-connection-id', connection.id);
    
    connection.element = line;
    connections.push(connection);
    
    svg.appendChild(line);
    updateConnections();
    
    console.log('Created connection between', node1.id, 'and', node2.id);
}

function handleConnectionClick(node) {
    if (!firstConnectionNode) {
        firstConnectionNode = node;
        node.style.border = '3px solid #EF4444';
        console.log('First node selected for connection');
    } else if (firstConnectionNode !== node) {
        createConnection(firstConnectionNode, node);
        firstConnectionNode.style.border = '';
        firstConnectionNode = null;
        connectionMode = false;
    }
}

// Map management functions
function createNewMap() {
    const mapCount = Object.keys(maps).length + 1;
    const newMapId = 'map' + mapCount;
    
    maps[newMapId] = {
        id: newMapId,
        name: 'Map ' + mapCount,
        nodes: [],
        connections: [],
        created: new Date().toISOString(),
        updated: new Date().toISOString()
    };
    
    const tabList = document.querySelector('.tab-list');
    const addButton = document.querySelector('.tab-add');
    
    const newTab = document.createElement('div');
    newTab.className = 'tab';
    newTab.setAttribute('data-map-id', newMapId);
    newTab.innerHTML = `
        <span>Map ${mapCount}</span>
        <button class="tab-close" onclick="closeMap('${newMapId}')" title="Close Map">×</button>
    `;
    
    newTab.addEventListener('click', (e) => {
        if (!e.target.classList.contains('tab-close')) {
            switchToMap(newMapId);
        }
    });
    
    tabList.insertBefore(newTab, addButton);
    switchToMap(newMapId);
    
    console.log('Created new map:', newMapId);
}

function switchToMap(mapId) {
    if (!maps[mapId]) return;
    
    saveCurrentMapState();
    
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelector(`[data-map-id="${mapId}"]`).classList.add('active');
    
    clearCanvas();
    currentMapId = mapId;
    loadMapState(mapId);
    
    console.log('Switched to map:', mapId);
}

function clearCanvas() {
    const container = document.getElementById('canvasContainer');
    if (container) {
        container.innerHTML = '';
    }
    
    const svg = document.getElementById('connectionsSvg');
    if (svg) {
        const lines = svg.querySelectorAll('.connection-line');
        lines.forEach(line => line.remove());
    }
    
    connections = [];
    selectedNode = null;
    nodeCounter = 0;
}

function saveCurrentMapState() {
    if (!maps[currentMapId]) return;
    
    const nodes = [];
    document.querySelectorAll('.mind-node').forEach(node => {
        nodes.push({
            id: node.id,
            text: node.querySelector('.node-text').textContent,
            x: parseInt(node.style.left) || 0,
            y: parseInt(node.style.top) || 0,
            width: node.style.width,
            height: node.style.height,
            backgroundColor: node.style.backgroundColor || '',
            shape: getNodeShape(node),
            fontSize: node.querySelector('.node-text').style.fontSize || '14px'
        });
    });
    
    maps[currentMapId].nodes = nodes;
    maps[currentMapId].connections = [...connections];
    maps[currentMapId].updated = new Date().toISOString();
}

function loadMapState(mapId) {
    const mapData = maps[mapId];
    if (!mapData) return;
    
    mapData.nodes.forEach(nodeData => {
        const node = document.createElement('div');
        node.className = 'mind-node';
        node.id = nodeData.id;
        node.style.left = nodeData.x + 'px';
        node.style.top = nodeData.y + 'px';
        node.style.width = nodeData.width || '180px';
        node.style.height = nodeData.height || 'auto';
        
        if (nodeData.backgroundColor) {
            node.style.backgroundColor = nodeData.backgroundColor;
        }
        
        if (nodeData.shape && nodeData.shape !== 'rectangle') {
            node.classList.add('shape-' + nodeData.shape);
        }
        
        const nodeText = document.createElement('div');
        nodeText.className = 'node-text';
        nodeText.textContent = nodeData.text;
        nodeText.style.fontSize = nodeData.fontSize;
        
        node.appendChild(nodeText);
        document.getElementById('canvasContainer').appendChild(node);
        
        makeDraggable(node);
        addNodeClickHandlers(node);
        
        const nodeIdNum = parseInt(nodeData.id.replace('node_', ''));
        if (nodeIdNum > nodeCounter) {
            nodeCounter = nodeIdNum;
        }
    });
    
    connections = [...mapData.connections];
    connections.forEach(conn => {
        const svg = document.getElementById('connectionsSvg');
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('class', 'connection-line');
        line.setAttribute('stroke', '#3B82F6');
        line.setAttribute('stroke-width', '2');
        line.setAttribute('marker-end', 'url(#arrowhead)');
        line.setAttribute('data-connection-id', conn.id);
        
        conn.element = line;
        svg.appendChild(line);
    });
    
    updateConnections();
}

function rebuildTabs() {
    const tabList = document.querySelector('.tab-list');
    const addButton = document.querySelector('.tab-add');
    
    document.querySelectorAll('.tab').forEach(tab => tab.remove());
    
    Object.values(maps).forEach(map => {
        const tab = document.createElement('div');
        tab.className = 'tab';
        if (map.id === currentMapId) tab.classList.add('active');
        tab.setAttribute('data-map-id', map.id);
        tab.innerHTML = `
            <span>${map.name}</span>
            <button class="tab-close" onclick="closeMap('${map.id}')" title="Close Map">×</button>
        `;
        
        tab.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab-close')) {
                switchToMap(map.id);
            }
        });
        
        tabList.insertBefore(tab, addButton);
    });
}

function getNodeShape(node) {
    if (node.classList.contains('shape-circle')) return 'circle';
    if (node.classList.contains('shape-square')) return 'square';
    if (node.classList.contains('shape-diamond')) return 'diamond';
    return 'rectangle';
}

// Utility functions
function copySelectedNode() {
    if (!selectedNode) return;
    
    const originalNode = selectedNode;
    const container = document.getElementById('canvasContainer');
    if (!container) return;
    
    nodeCounter++;
    
    const originalRect = originalNode.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    
    const x = (originalRect.left - containerRect.left) + 50;
    const y = (originalRect.top - containerRect.top) + 50;
    
    const node = document.createElement('div');
    node.className = originalNode.className;
    node.id = 'node_' + nodeCounter;
    node.style.left = x + 'px';
    node.style.top = y + 'px';
    node.style.width = originalNode.style.width || '180px';
    node.style.height = originalNode.style.height || 'auto';
    
    if (originalNode.style.backgroundColor) {
        node.style.backgroundColor = originalNode.style.backgroundColor;
    }
    
    const nodeText = document.createElement('div');
    nodeText.className = 'node-text';
    nodeText.textContent = originalNode.querySelector('.node-text').textContent + ' (Copy)';
    
    const originalTextStyle = originalNode.querySelector('.node-text').style;
    if (originalTextStyle.fontSize) {
        nodeText.style.fontSize = originalTextStyle.fontSize;
    }
    
    node.appendChild(nodeText);
    container.appendChild(node);
    
    makeDraggable(node);
    addNodeClickHandlers(node);
    
    selectNode(node);
    
    console.log('Copied node:', originalNode.id, 'to', node.id);
    return node;
}

function deleteSelectedNode() {
    if (!selectedNode) return;
    
    const nodeId = selectedNode.id;
    
    selectedNode.remove();
    
    connections = connections.filter(conn => {
        if (conn.from === nodeId || conn.to === nodeId) {
            if (conn.element) {
                conn.element.remove();
            }
            return false;
        }
        return true;
    });
    
    selectedNode = null;
    
    const textArea = document.getElementById('nodeText');
    if (textArea) textArea.value = '';
    
    console.log('Deleted node:', nodeId);
}

// Make functions globally available
window.addNewNode = addNewNode;
window.updateConnections = updateConnections;
window.saveToFirebase = saveToFirebase;
window.createNewMap = createNewMap;
window.switchToMap = switchToMap;
window.copySelectedNode = copySelectedNode;
window.deleteSelectedNode = deleteSelectedNode;

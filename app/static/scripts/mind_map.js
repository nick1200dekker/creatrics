// Test if script is loading
console.log('mind_map.js loaded!');

class MindMap {
    constructor() {
        console.log('MindMap: Initializing...');

        // Get DOM elements
        this.canvas = document.getElementById('mindMapCanvas');
        this.container = document.getElementById('canvasContainer');
        this.svg = document.getElementById('connectionsSvg');

        if (!this.canvas || !this.container || !this.svg) {
            console.error('MindMap: Required elements not found');
            return;
        }

        // State
        this.nodes = new Map();
        this.connections = [];
        this.selectedNode = null;
        this.currentTool = 'node';
        this.nodeIdCounter = 0;
        this.connectionIdCounter = 0;

        // Dragging state
        this.isDragging = false;
        this.dragNode = null;
        this.dragOffset = { x: 0, y: 0 };

        // Pan and zoom
        this.isPanning = false;
        this.panStart = { x: 0, y: 0 };
        this.scale = 1;
        this.translateX = 0;
        this.translateY = 0;

        // Initialize
        this.init();
    }

    init() {
        console.log('MindMap: Setting up...');
        this.setupEventListeners();
        this.createInitialNode();
        this.loadFromLocalStorage();
    }

    setupEventListeners() {
        // Tool buttons
        document.querySelectorAll('[data-tool]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.setTool(btn.dataset.tool);
            });
        });

        // Canvas click for adding nodes
        this.canvas.addEventListener('click', (e) => {
            if (this.currentTool === 'node' && e.target === this.canvas) {
                const rect = this.canvas.getBoundingClientRect();
                const x = (e.clientX - rect.left - this.translateX) / this.scale;
                const y = (e.clientY - rect.top - this.translateY) / this.scale;
                this.addNode(x - 90, y - 30);
            }
        });

        // Mouse events for dragging
        this.canvas.addEventListener('mousedown', this.handleMouseDown.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));

        // Zoom controls
        const zoomIn = document.getElementById('zoomInBtn');
        const zoomOut = document.getElementById('zoomOutBtn');
        const zoomReset = document.getElementById('zoomResetBtn');

        if (zoomIn) zoomIn.addEventListener('click', () => this.zoom(1.1));
        if (zoomOut) zoomOut.addEventListener('click', () => this.zoom(0.9));
        if (zoomReset) zoomReset.addEventListener('click', () => this.resetZoom());

        // Save button
        const saveBtn = document.getElementById('saveBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.save());
        }

        // Export button
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.toggleExportMenu());
        }

        // Export options
        document.querySelectorAll('.export-option').forEach(option => {
            option.addEventListener('click', () => {
                this.export(option.dataset.format);
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Delete' && this.selectedNode) {
                this.deleteNode(this.selectedNode);
            }
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.save();
            }
        });

        // Auto-save every 30 seconds
        setInterval(() => this.saveToLocalStorage(), 30000);
    }

    setTool(tool) {
        this.currentTool = tool;
        document.querySelectorAll('[data-tool]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === tool);
        });
        console.log('Tool changed to:', tool);
    }

    createInitialNode() {
        if (this.nodes.size === 0) {
            const centerX = this.canvas.offsetWidth / 2 - 100;
            const centerY = this.canvas.offsetHeight / 2 - 30;
            this.addNode(centerX, centerY, 'Central Idea', true);
        }
    }

    addNode(x, y, text = 'New Node', isRoot = false) {
        const nodeId = `node_${++this.nodeIdCounter}`;

        const node = document.createElement('div');
        node.className = 'mind-node' + (isRoot ? ' root' : '');
        node.id = nodeId;
        node.style.left = x + 'px';
        node.style.top = y + 'px';
        node.dataset.nodeId = nodeId;

        // Create node content
        const nodeText = document.createElement('div');
        nodeText.className = 'node-text';
        nodeText.contentEditable = true;
        nodeText.textContent = text;
        nodeText.addEventListener('blur', () => this.saveToLocalStorage());
        nodeText.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                nodeText.blur();
            }
            e.stopPropagation();
        });

        // Create action buttons
        const actions = document.createElement('div');
        actions.className = 'node-actions';

        const addChildBtn = document.createElement('button');
        addChildBtn.innerHTML = '<i class="ph ph-plus"></i>';
        addChildBtn.title = 'Add Child Node';
        addChildBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.addChildNode(node);
        });

        const connectBtn = document.createElement('button');
        connectBtn.innerHTML = '<i class="ph ph-flow-arrow"></i>';
        connectBtn.title = 'Connect to Another Node';
        connectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.startConnection(node);
        });

        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = '<i class="ph ph-trash"></i>';
        deleteBtn.title = 'Delete Node';
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.deleteNode(node);
        });

        if (!isRoot) {
            actions.appendChild(addChildBtn);
            actions.appendChild(connectBtn);
            actions.appendChild(deleteBtn);
        } else {
            actions.appendChild(addChildBtn);
        }

        node.appendChild(nodeText);
        node.appendChild(actions);

        // Add mouse events for dragging
        node.addEventListener('mousedown', (e) => {
            if (e.target === nodeText || e.target.closest('.node-actions')) {
                return;
            }
            this.startDragging(node, e);
        });

        node.addEventListener('click', (e) => {
            if (e.target.closest('.node-actions')) return;
            this.selectNode(node);
        });

        this.container.appendChild(node);
        this.nodes.set(nodeId, {
            element: node,
            x: x,
            y: y,
            text: text,
            connections: []
        });

        console.log('Node added:', nodeId);
        this.saveToLocalStorage();
        return node;
    }

    addChildNode(parentNode) {
        const parentRect = parentNode.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();

        const parentX = (parentRect.left - canvasRect.left - this.translateX) / this.scale;
        const parentY = (parentRect.top - canvasRect.top - this.translateY) / this.scale;

        const childX = parentX + 200;
        const childY = parentY + Math.random() * 100 - 50;

        const childNode = this.addNode(childX, childY, 'New Idea');
        this.connectNodes(parentNode, childNode);
    }

    startConnection(fromNode) {
        this.connectingFrom = fromNode;
        this.currentTool = 'connect';
        this.setTool('connect');
        fromNode.classList.add('connecting');

        // Add temporary event listener to all nodes
        this.nodes.forEach((nodeData, nodeId) => {
            if (nodeData.element !== fromNode) {
                nodeData.element.style.cursor = 'crosshair';
                nodeData.element.addEventListener('click', this.completeConnection);
            }
        });
    }

    completeConnection = (e) => {
        e.stopPropagation();
        const toNode = e.currentTarget;

        if (this.connectingFrom && toNode !== this.connectingFrom) {
            this.connectNodes(this.connectingFrom, toNode);
        }

        this.endConnection();
    }

    endConnection() {
        if (this.connectingFrom) {
            this.connectingFrom.classList.remove('connecting');
        }

        // Remove temporary event listeners
        this.nodes.forEach((nodeData) => {
            nodeData.element.style.cursor = '';
            nodeData.element.removeEventListener('click', this.completeConnection);
        });

        this.connectingFrom = null;
        this.setTool('select');
    }

    connectNodes(fromNode, toNode) {
        const connectionId = `conn_${++this.connectionIdCounter}`;

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.id = connectionId;
        path.className = 'connection-line';
        path.style.stroke = '#3B82F6';
        path.style.strokeWidth = '2';
        path.style.fill = 'none';

        this.svg.appendChild(path);

        const connection = {
            id: connectionId,
            from: fromNode.id,
            to: toNode.id,
            element: path
        };

        this.connections.push(connection);
        this.updateConnection(connection);

        console.log('Connected:', fromNode.id, 'to', toNode.id);
        this.saveToLocalStorage();
    }

    updateConnection(connection) {
        const fromNode = document.getElementById(connection.from);
        const toNode = document.getElementById(connection.to);

        if (!fromNode || !toNode) return;

        const fromRect = fromNode.getBoundingClientRect();
        const toRect = toNode.getBoundingClientRect();
        const svgRect = this.svg.getBoundingClientRect();

        const fromX = (fromRect.left + fromRect.width / 2 - svgRect.left) / this.scale;
        const fromY = (fromRect.top + fromRect.height / 2 - svgRect.top) / this.scale;
        const toX = (toRect.left + toRect.width / 2 - svgRect.left) / this.scale;
        const toY = (toRect.top + toRect.height / 2 - svgRect.top) / this.scale;

        // Create curved path
        const dx = toX - fromX;
        const dy = toY - fromY;
        const dr = Math.sqrt(dx * dx + dy * dy) / 2;

        const path = `M ${fromX},${fromY} Q ${fromX + dx/2},${fromY + dy/2} ${toX},${toY}`;
        connection.element.setAttribute('d', path);
    }

    updateAllConnections() {
        this.connections.forEach(conn => this.updateConnection(conn));
    }

    selectNode(node) {
        // Remove previous selection
        document.querySelectorAll('.mind-node').forEach(n => n.classList.remove('selected'));

        node.classList.add('selected');
        this.selectedNode = node;

        // Update properties panel if needed
        const controlsPanel = document.getElementById('controlsPanel');
        const nodeText = document.getElementById('nodeText');

        if (controlsPanel && nodeText) {
            controlsPanel.style.display = 'block';
            nodeText.value = node.querySelector('.node-text').textContent;
        }
    }

    deleteNode(node) {
        if (node.classList.contains('root')) {
            alert('Cannot delete the root node');
            return;
        }

        const nodeId = node.id;

        // Remove connections
        this.connections = this.connections.filter(conn => {
            if (conn.from === nodeId || conn.to === nodeId) {
                conn.element.remove();
                return false;
            }
            return true;
        });

        // Remove node
        node.remove();
        this.nodes.delete(nodeId);

        if (this.selectedNode === node) {
            this.selectedNode = null;
        }

        console.log('Node deleted:', nodeId);
        this.saveToLocalStorage();
    }

    startDragging(node, e) {
        this.isDragging = true;
        this.dragNode = node;

        const rect = node.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();

        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };

        this.selectNode(node);
        e.preventDefault();
    }

    handleMouseDown(e) {
        // Pan with middle mouse or alt+left click
        if (e.button === 1 || (e.button === 0 && e.altKey)) {
            this.isPanning = true;
            this.panStart = {
                x: e.clientX - this.translateX,
                y: e.clientY - this.translateY
            };
            this.canvas.style.cursor = 'grabbing';
            e.preventDefault();
        }
    }

    handleMouseMove(e) {
        if (this.isDragging && this.dragNode) {
            const canvasRect = this.canvas.getBoundingClientRect();
            const x = (e.clientX - canvasRect.left - this.dragOffset.x - this.translateX) / this.scale;
            const y = (e.clientY - canvasRect.top - this.dragOffset.y - this.translateY) / this.scale;

            this.dragNode.style.left = x + 'px';
            this.dragNode.style.top = y + 'px';

            this.updateAllConnections();
        } else if (this.isPanning) {
            this.translateX = e.clientX - this.panStart.x;
            this.translateY = e.clientY - this.panStart.y;
            this.updateTransform();
        }
    }

    handleMouseUp(e) {
        if (this.isDragging) {
            this.isDragging = false;
            this.dragNode = null;
            this.saveToLocalStorage();
        }

        if (this.isPanning) {
            this.isPanning = false;
            this.canvas.style.cursor = '';
        }
    }

    zoom(factor) {
        this.scale *= factor;
        this.scale = Math.max(0.25, Math.min(3, this.scale));
        this.updateTransform();

        const zoomLevel = document.getElementById('zoomLevel');
        if (zoomLevel) {
            zoomLevel.textContent = Math.round(this.scale * 100) + '%';
        }
    }

    resetZoom() {
        this.scale = 1;
        this.translateX = 0;
        this.translateY = 0;
        this.updateTransform();

        const zoomLevel = document.getElementById('zoomLevel');
        if (zoomLevel) {
            zoomLevel.textContent = '100%';
        }
    }

    updateTransform() {
        const transform = `translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale})`;
        this.container.style.transform = transform;
        this.svg.style.transform = transform;
        this.updateAllConnections();
    }

    save() {
        this.saveToLocalStorage();
        this.saveToServer();

        // Show save indicator
        const indicator = document.getElementById('saveIndicator');
        if (indicator) {
            indicator.classList.add('show');
            setTimeout(() => indicator.classList.remove('show'), 2000);
        }
    }

    saveToLocalStorage() {
        const data = {
            nodes: [],
            connections: [],
            scale: this.scale,
            translateX: this.translateX,
            translateY: this.translateY
        };

        this.nodes.forEach((nodeData, nodeId) => {
            const element = nodeData.element;
            data.nodes.push({
                id: nodeId,
                x: parseInt(element.style.left),
                y: parseInt(element.style.top),
                text: element.querySelector('.node-text').textContent,
                isRoot: element.classList.contains('root')
            });
        });

        this.connections.forEach(conn => {
            data.connections.push({
                from: conn.from,
                to: conn.to
            });
        });

        localStorage.setItem('mindMapData', JSON.stringify(data));
        console.log('Saved to localStorage');
    }

    loadFromLocalStorage() {
        const saved = localStorage.getItem('mindMapData');
        if (!saved) return;

        try {
            const data = JSON.parse(saved);

            // Clear existing
            this.container.innerHTML = '';
            this.svg.innerHTML = '';
            this.nodes.clear();
            this.connections = [];

            // Restore view
            this.scale = data.scale || 1;
            this.translateX = data.translateX || 0;
            this.translateY = data.translateY || 0;
            this.updateTransform();

            // Restore nodes
            data.nodes.forEach(nodeData => {
                this.addNode(nodeData.x, nodeData.y, nodeData.text, nodeData.isRoot);
            });

            // Restore connections
            data.connections.forEach(connData => {
                const fromNode = document.getElementById(connData.from);
                const toNode = document.getElementById(connData.to);
                if (fromNode && toNode) {
                    this.connectNodes(fromNode, toNode);
                }
            });

            console.log('Loaded from localStorage');
        } catch (e) {
            console.error('Error loading saved data:', e);
        }
    }

    saveToServer() {
        const data = {
            nodes: [],
            connections: []
        };

        this.nodes.forEach((nodeData, nodeId) => {
            const element = nodeData.element;
            data.nodes.push({
                id: nodeId,
                x: parseInt(element.style.left),
                y: parseInt(element.style.top),
                text: element.querySelector('.node-text').textContent,
                isRoot: element.classList.contains('root')
            });
        });

        this.connections.forEach(conn => {
            data.connections.push({
                from: conn.from,
                to: conn.to
            });
        });

        // Send to server
        fetch('/api/mind-map/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(result => {
            if (result.success) {
                console.log('Saved to server');
            }
        })
        .catch(err => {
            console.error('Save error:', err);
        });
    }

    toggleExportMenu() {
        const menu = document.getElementById('exportMenu');
        if (menu) {
            menu.classList.toggle('show');
        }
    }

    export(format) {
        const menu = document.getElementById('exportMenu');
        if (menu) menu.classList.remove('show');

        switch(format) {
            case 'json':
                this.exportJSON();
                break;
            case 'png':
                alert('PNG export: Would require html2canvas library');
                break;
            case 'svg':
                this.exportSVG();
                break;
            case 'pdf':
                alert('PDF export: Would require jsPDF library');
                break;
        }
    }

    exportJSON() {
        const data = {
            nodes: [],
            connections: []
        };

        this.nodes.forEach((nodeData, nodeId) => {
            const element = nodeData.element;
            data.nodes.push({
                id: nodeId,
                x: parseInt(element.style.left),
                y: parseInt(element.style.top),
                text: element.querySelector('.node-text').textContent,
                isRoot: element.classList.contains('root')
            });
        });

        this.connections.forEach(conn => {
            data.connections.push({
                from: conn.from,
                to: conn.to
            });
        });

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'mindmap.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    exportSVG() {
        const svgContent = this.svg.outerHTML;
        const blob = new Blob([svgContent], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'mindmap.svg';
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Initialize when page loads
console.log('Document ready state:', document.readyState);

// Manual initialization function for testing
window.initMindMap = function() {
    console.log('Manual initialization called...');
    try {
        if (window.mindMap) {
            console.log('MindMap already exists, recreating...');
        }
        window.mindMap = new MindMap();
        console.log('MindMap initialized successfully!');
        return window.mindMap;
    } catch (error) {
        console.error('Error initializing MindMap:', error);
        return null;
    }
};

// Auto-initialize
if (document.readyState === 'loading') {
    console.log('Waiting for DOMContentLoaded...');
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOMContentLoaded fired, initializing MindMap...');
        window.initMindMap();
    });
} else {
    console.log('DOM already loaded, initializing MindMap immediately...');
    // Small delay to ensure all elements are ready
    setTimeout(() => {
        window.initMindMap();
    }, 100);
}
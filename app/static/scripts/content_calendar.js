// Content Calendar JavaScript - Part 1
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Content Calendar...');
    
    // Global variables
    let calendar = null;
    let events = [];
    let currentView = 'calendar';
    let editingEventId = null;
    let currentMonth = new Date();
    let draggedEventEl = null;
    let dragGhost = null;
    let weekStart = 1; // 1 = Monday (default), 0 = Sunday
    
    // Check if FullCalendar loaded
    if (typeof FullCalendar === 'undefined') {
        console.error('FullCalendar not loaded!');
        document.getElementById('calendar').innerHTML = `
            <div class="loading">
                <div>
                    <p style="margin-bottom: 1rem;">FullCalendar library failed to load.</p>
                    <button class="btn btn-primary" onclick="location.reload()">Reload Page</button>
                </div>
            </div>
        `;
        return;
    }
    
    // Create custom drag ghost element
    function createDragGhost(eventEl, event) {
        // Remove any existing ghost
        removeDragGhost();

        // Get the original element's dimensions
        const rect = eventEl.getBoundingClientRect();

        // Create new ghost element
        dragGhost = document.createElement('div');
        dragGhost.className = 'drag-ghost';
        dragGhost.textContent = event.title;

        // Apply the exact width of the original element
        dragGhost.style.width = rect.width + 'px';
        dragGhost.style.minWidth = rect.width + 'px';
        dragGhost.style.maxWidth = rect.width + 'px';

        // Add platform class for coloring
        const eventData = events.find(e => e.id == event.id);
        if (eventData) {
            if (eventData.platform) {
                dragGhost.classList.add('platform-' + eventData.platform.toLowerCase().replace(/[^a-z0-9]/g, ''));
            } else {
                dragGhost.classList.add('platform-other');
            }

            // Add money emoji for sponsored content
            if (eventData.content_type === 'sponsored') {
                dragGhost.textContent = event.title + ' 💰';
            }
        }

        document.body.appendChild(dragGhost);

        return dragGhost;
    }
    
    function removeDragGhost() {
        if (dragGhost && dragGhost.parentNode) {
            dragGhost.parentNode.removeChild(dragGhost);
            dragGhost = null;
        }
    }
    
    function updateDragGhostPosition(e) {
        if (dragGhost) {
            dragGhost.style.left = e.clientX + 'px';
            dragGhost.style.top = e.clientY + 'px';
        }
    }
    
    // Initialize calendar
    try {
        const calendarEl = document.getElementById('calendar');
        
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: false,
            height: 'auto',
            contentHeight: 'auto',
            aspectRatio: 1.8,
            expandRows: false,
            editable: true,
            selectable: true,
            dayMaxEvents: false,
            eventDisplay: 'block',
            displayEventTime: false,
            events: [],
            fixedWeekCount: false,
            droppable: true,
            eventStartEditable: true,
            eventDurationEditable: false,
            dragRevertDuration: 500,
            dragScroll: true,
            firstDay: weekStart,

            eventDragStart: function(info) {
                // Create and show custom drag ghost
                const ghost = createDragGhost(info.el, info.event);
                
                // Add mouse move listener
                document.addEventListener('mousemove', updateDragGhostPosition);
                
                // Initial position
                updateDragGhostPosition(info.jsEvent);
                
                // Make original event semi-transparent
                info.el.style.opacity = '0.5';
            },

            eventDragStop: function(info) {
                // Remove ghost and listeners
                removeDragGhost();
                document.removeEventListener('mousemove', updateDragGhostPosition);
                
                // Reset opacity
                info.el.style.opacity = '';
            },
            
            eventDrop: function(info) {
                // Clean up any remaining ghost
                removeDragGhost();
                document.removeEventListener('mousemove', updateDragGhostPosition);
                
                // Update event date on backend
                const eventData = {
                    publish_date: info.event.start.toISOString()
                };
                
                fetch(`/content-calendar/api/event/${info.event.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(eventData)
                })
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        info.revert();
                    }
                    // Update local events array without full reload
                    const eventIndex = events.findIndex(e => e.id == info.event.id);
                    if (eventIndex !== -1) {
                        events[eventIndex].publish_date = info.event.start.toISOString();
                    }
                })
                .catch(error => {
                    console.error('Error updating event:', error);
                    info.revert();
                });
            },

            dateClick: function(info) {
                // Format the date properly for datetime-local input
                const clickedDate = new Date(info.date);
                const year = clickedDate.getFullYear();
                const month = String(clickedDate.getMonth() + 1).padStart(2, '0');
                const day = String(clickedDate.getDate()).padStart(2, '0');
                const dateString = `${year}-${month}-${day}T12:00`;
                
                // Open modal with the date pre-filled
                openNewEventModal();
                document.getElementById('event-date').value = dateString;
            },
            
            eventClick: function(info) {
                // Open edit modal instead of delete
                openEditEventModal(info.event.id);
            },
            
            eventDidMount: function(info) {
                // Add custom classes based on event properties
                const event = events.find(e => e.id == info.event.id);
                if (event) {
                    // Add sponsored class for money icon
                    if (event.content_type === 'sponsored') {
                        info.el.classList.add('sponsored');
                    }

                    // Add platform class for coloring
                    if (event.platform) {
                        const platformClass = 'platform-' + event.platform.toLowerCase().replace(/[^a-z0-9]/g, '');
                        info.el.classList.add(platformClass);
                    } else {
                        info.el.classList.add('platform-other');
                    }
                }
            }
        });
        
        calendar.render();
        updateMonthDisplay();
        loadEvents();
        
        console.log('Calendar initialized successfully');
        
    } catch (error) {
        console.error('Error initializing calendar:', error);
        document.getElementById('calendar').innerHTML = `
            <div class="loading">
                <div>
                    <p style="margin-bottom: 1rem;">Error initializing calendar: ${error.message}</p>
                    <button class="btn btn-primary" onclick="location.reload()">Reload Page</button>
                </div>
            </div>
        `;
    }
    
    // Clean up on page unload
    window.addEventListener('beforeunload', function() {
        removeDragGhost();
    });
    
    // Content type selector
    window.selectContentType = function(type) {
        document.querySelectorAll('.content-type-option').forEach(option => {
            option.classList.remove('selected');
        });
        document.querySelector(`.content-type-option[data-type="${type}"]`).classList.add('selected');
    };
    
    // Toggle analytics - now works like a view switch
    window.toggleAnalytics = function() {
        const isAnalyticsActive = document.getElementById('analytics-toggle-btn').classList.contains('active');

        if (!isAnalyticsActive) {
            // Switch to analytics view
            currentView = 'analytics';

            // Update buttons
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.getElementById('analytics-toggle-btn').classList.add('active');

            // Hide all other views
            document.getElementById('calendar').style.display = 'none';
            document.getElementById('table-view').style.display = 'none';
            document.getElementById('kanban-view').style.display = 'none';

            // Show analytics panel
            const panel = document.getElementById('analytics-panel');
            panel.classList.add('show');
            updateAnalytics();
        } else {
            // Switch back to calendar view
            switchView('calendar');
        }
    };
    
    // Update analytics
    function updateAnalytics() {
        const monthStart = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
        const monthEnd = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);
        
        // Filter events for current month
        const monthEvents = events.filter(event => {
            if (!event.publish_date) return false;
            const eventDate = new Date(event.publish_date);
            return eventDate >= monthStart && eventDate <= monthEnd;
        });
        
        const totalPosts = monthEvents.length;
        const organicPosts = monthEvents.filter(e => e.content_type !== 'sponsored').length;
        const sponsoredPosts = monthEvents.filter(e => e.content_type === 'sponsored').length;
        const draftPosts = monthEvents.filter(e => e.status === 'draft').length;
        const scheduledPosts = monthEvents.filter(e => e.publish_date).length;
        const progressPosts = monthEvents.filter(e => e.status === 'in-progress').length;
        const reviewPosts = monthEvents.filter(e => e.status === 'review').length;
        const readyPosts = monthEvents.filter(e => e.status === 'ready').length;

        document.getElementById('total-posts').textContent = totalPosts;
        document.getElementById('organic-posts').textContent = organicPosts;
        document.getElementById('sponsored-posts').textContent = sponsoredPosts;
        document.getElementById('draft-posts').textContent = draftPosts;
        document.getElementById('scheduled-posts').textContent = scheduledPosts;
        document.getElementById('progress-posts').textContent = progressPosts;
        document.getElementById('review-posts').textContent = reviewPosts;
        document.getElementById('ready-posts').textContent = readyPosts;
        
        // Calculate percentages
        if (totalPosts > 0) {
            document.getElementById('organic-percentage').textContent = `${Math.round((organicPosts / totalPosts) * 100)}%`;
            document.getElementById('sponsored-percentage').textContent = `${Math.round((sponsoredPosts / totalPosts) * 100)}%`;
        } else {
            document.getElementById('organic-percentage').textContent = '0%';
            document.getElementById('sponsored-percentage').textContent = '0%';
        }

        // Generate daily posts chart
        generateDailyChart(monthEvents, monthStart, monthEnd);
    }

    // Generate daily posts chart
    function generateDailyChart(monthEvents, monthStart, monthEnd) {
        const daysInMonth = monthEnd.getDate();
        const dailyCounts = new Array(daysInMonth).fill(0);

        // Count posts per day
        monthEvents.forEach(event => {
            if (event.publish_date) {
                const day = new Date(event.publish_date).getDate() - 1; // 0-indexed
                if (day >= 0 && day < daysInMonth) {
                    dailyCounts[day]++;
                }
            }
        });

        const maxCount = Math.max(...dailyCounts, 1); // At least 1 for scale
        const yAxisSteps = 5;
        const yAxisMax = Math.ceil(maxCount / yAxisSteps) * yAxisSteps || 5;

        // Generate Y-axis labels
        const yAxisContainer = document.getElementById('chart-y-axis');
        yAxisContainer.innerHTML = '';
        for (let i = yAxisSteps; i >= 0; i--) {
            const label = document.createElement('div');
            label.textContent = Math.round((yAxisMax / yAxisSteps) * i);
            yAxisContainer.appendChild(label);
        }

        // Generate bars
        const barsContainer = document.getElementById('chart-bars');
        barsContainer.innerHTML = '';

        dailyCounts.forEach((count, index) => {
            const barWrapper = document.createElement('div');
            barWrapper.className = 'chart-bar';
            barWrapper.style.height = `${(count / yAxisMax) * 100}%`;

            // Add tooltip
            const tooltip = document.createElement('div');
            tooltip.className = 'chart-bar-tooltip';
            const date = new Date(monthStart);
            date.setDate(index + 1);
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            tooltip.textContent = `${dateStr}: ${count} ${count === 1 ? 'post' : 'posts'}`;
            barWrapper.appendChild(tooltip);

            barsContainer.appendChild(barWrapper);
        });

        // Generate X-axis labels (show every few days to avoid crowding)
        const xAxisContainer = document.getElementById('chart-x-axis');
        xAxisContainer.innerHTML = '';

        const labelInterval = daysInMonth > 15 ? 5 : 3; // Show every 5 days if month > 15 days, else every 3

        for (let i = 0; i < daysInMonth; i++) {
            const label = document.createElement('div');
            label.className = 'chart-x-label';

            // Only show some labels to avoid crowding
            if (i === 0 || (i + 1) % labelInterval === 0 || i === daysInMonth - 1) {
                label.textContent = i + 1;
            } else {
                label.textContent = '';
            }

            xAxisContainer.appendChild(label);
        }
    }
    
    // Week start toggle
    window.setWeekStart = function(startDay) {
        weekStart = startDay;

        // Update button states
        document.querySelectorAll('.week-toggle-btn').forEach(btn => {
            btn.classList.remove('active');
            if ((startDay === 1 && btn.textContent.includes('Mon')) ||
                (startDay === 0 && btn.textContent.includes('Sun'))) {
                btn.classList.add('active');
            }
        });

        // Update calendar
        if (calendar) {
            calendar.setOption('firstDay', weekStart);
        }

        // Save preference
        localStorage.setItem('calendarWeekStart', weekStart);
    };

    // Load saved week start preference
    const savedWeekStart = localStorage.getItem('calendarWeekStart');
    if (savedWeekStart !== null) {
        weekStart = parseInt(savedWeekStart);
        // Update button states after DOM loads
        setTimeout(() => {
            document.querySelectorAll('.week-toggle-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`.week-toggle-btn:${weekStart === 0 ? 'last-child' : 'first-child'}`).classList.add('active');
        }, 0);
    }

    // Make functions globally available
    window.switchView = function(view) {
        currentView = view;

        // Update buttons
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.textContent.toLowerCase().includes(view)) {
                btn.classList.add('active');
            }
        });

        // Show/hide views
        document.getElementById('calendar').style.display = view === 'calendar' ? 'block' : 'none';
        document.getElementById('table-view').style.display = view === 'table' ? 'block' : 'none';
        document.getElementById('kanban-view').style.display = view === 'kanban' ? 'block' : 'none';

        // Hide analytics panel if switching to non-analytics view
        const analyticsPanel = document.getElementById('analytics-panel');
        if (view !== 'analytics' && analyticsPanel) {
            analyticsPanel.classList.remove('show');
        }

        if (view === 'calendar') {
            // Re-render calendar when switching back to it
            if (calendar) {
                calendar.render();
                calendar.updateSize();
                loadEvents(); // Reload events to ensure calendar is populated
            }
        } else if (view === 'table') {
            renderTable();
        } else if (view === 'kanban') {
            renderKanban();
        }
    };
    
    window.previousMonth = function() {
        if (calendar) {
            calendar.prev();
            currentMonth = calendar.getDate();
            updateMonthDisplay();
            if (document.getElementById('analytics-panel').classList.contains('show')) {
                updateAnalytics();
            }
        }
    };
    
    window.nextMonth = function() {
        if (calendar) {
            calendar.next();
            currentMonth = calendar.getDate();
            updateMonthDisplay();
            if (document.getElementById('analytics-panel').classList.contains('show')) {
                updateAnalytics();
            }
        }
    };
    
    window.openNewEventModal = function() {
        editingEventId = null;
        document.getElementById('modal-title').textContent = 'Add New Event';
        document.getElementById('delete-btn').style.display = 'none';
        document.getElementById('event-id').value = '';
        document.getElementById('event-title').value = '';
        document.getElementById('event-date').value = '';
        document.getElementById('event-platform').value = 'YouTube';
        document.getElementById('event-status').value = 'draft';
        document.getElementById('event-notes').value = '';
        
        // Reset content type selector
        selectContentType('organic');
        
        document.getElementById('event-modal').classList.add('show');
    };
    
    window.openEditEventModal = function(eventId) {
        editingEventId = eventId;
        const event = events.find(e => e.id == eventId);
        
        if (!event) return;
        
        document.getElementById('modal-title').textContent = 'Edit Event';
        document.getElementById('delete-btn').style.display = 'inline-flex';
        document.getElementById('event-id').value = eventId;
        document.getElementById('event-title').value = event.title || '';
        document.getElementById('event-date').value = event.publish_date ? 
            new Date(event.publish_date).toISOString().slice(0, 16) : '';
        document.getElementById('event-platform').value = event.platform || 'YouTube';
        document.getElementById('event-status').value = event.status || 'draft';
        document.getElementById('event-notes').value = event.notes || '';
        
        // Set content type
        selectContentType(event.content_type === 'sponsored' ? 'sponsored' : 'organic');
        
        document.getElementById('event-modal').classList.add('show');
    };
    
    window.closeEventModal = function() {
        document.getElementById('event-modal').classList.remove('show');
        editingEventId = null;
    };
    
    window.saveEvent = function() {
        const eventId = document.getElementById('event-id').value;
        const title = document.getElementById('event-title').value;
        const date = document.getElementById('event-date').value;
        const platform = document.getElementById('event-platform').value;
        const status = document.getElementById('event-status').value;
        const notes = document.getElementById('event-notes').value;
        const contentType = document.querySelector('.content-type-option.selected').dataset.type;
        
        if (!title) {
            return;
        }
        
        const eventData = {
            title: title,
            publish_date: date || null,
            platform: platform,
            status: status,
            notes: notes,
            content_type: contentType
        };
        
        const url = eventId ? 
            `/content-calendar/api/event/${eventId}` : 
            '/content-calendar/api/event';
        const method = eventId ? 'PUT' : 'POST';
        
        // Save to backend
        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(eventData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success || data.event_id) {
                closeEventModal();
                loadEvents();
            }
        })
        .catch(error => {
            console.error('Error saving event:', error);
        });
    };
    
    window.deleteEvent = function() {
        const eventId = document.getElementById('event-id').value;
        
        if (!eventId) return;
        
        if (confirm('Are you sure you want to delete this event?')) {
            fetch(`/content-calendar/api/event/${eventId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    closeEventModal();
                    loadEvents();
                }
            })
            .catch(error => {
                console.error('Error deleting event:', error);
            });
        }
    };
    
    window.editEvent = function(eventId) {
        openEditEventModal(eventId);
    };
    
    // Kanban drag and drop
    let dragTimeout = null;
    
    window.allowDrop = function(ev) {
        ev.preventDefault();
        
        // Clear any existing timeout
        if (dragTimeout) {
            clearTimeout(dragTimeout);
        }
        
        // Add drag-over class with a small delay to prevent flashing
        dragTimeout = setTimeout(() => {
            ev.currentTarget.parentElement.classList.add('drag-over');
        }, 50);
    };
    
    window.dropCard = function(ev) {
        ev.preventDefault();
        
        // Clear timeout
        if (dragTimeout) {
            clearTimeout(dragTimeout);
            dragTimeout = null;
        }
        
        // Remove drag-over class
        ev.currentTarget.parentElement.classList.remove('drag-over');
        
        const eventId = ev.dataTransfer.getData('eventId');
        const newStatus = ev.currentTarget.parentElement.dataset.status;
        
        // Find the dragged card and immediately move it visually
        const card = document.querySelector(`.kanban-card[data-event-id="${eventId}"]`);
        if (card) {
            ev.currentTarget.appendChild(card);
        }
        
        // Update status on backend
        fetch(`/content-calendar/api/event/${eventId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update the events array
                const eventIndex = events.findIndex(e => e.id == eventId);
                if (eventIndex !== -1) {
                    events[eventIndex].status = newStatus;
                }
                // Re-render to update counts
                renderKanban();
            } else {
                // Revert if failed
                loadEvents();
            }
        })
        .catch(error => {
            console.error('Error updating event status:', error);
            loadEvents();
        });
    };
    
    function updateMonthDisplay() {
        if (!calendar) return;
        const date = calendar.getDate();
        currentMonth = date;
        const monthYear = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        document.getElementById('current-month').textContent = monthYear;
    }
    
    function loadEvents() {
        fetch('/content-calendar/api/events')
            .then(response => response.json())
            .then(data => {
                events = data;
                
                // Add events to calendar (only those with dates)
                if (calendar) {
                    calendar.removeAllEvents();
                    data.filter(event => event.publish_date).forEach(event => {
                        const eventDate = new Date(event.publish_date);
                        const today = new Date();
                        const daysUntil = Math.floor((eventDate - today) / (1000 * 60 * 60 * 24));
                        
                        // Determine background color
                        let backgroundColor = getEventColor(event);
                        
                        const classNames = [];
                        if (event.content_type === 'sponsored') {
                            classNames.push('sponsored');
                        }
                        if (event.platform) {
                            classNames.push('platform-' + event.platform.toLowerCase().replace(/[^a-z0-9]/g, ''));
                        } else {
                            classNames.push('platform-other');
                        }

                        calendar.addEvent({
                            id: event.id,
                            title: event.title,
                            start: event.publish_date,
                            backgroundColor: backgroundColor,
                            classNames: classNames,
                            editable: true,  // Ensure each event is draggable
                            startEditable: true
                        });
                    });
                }
                
                // Update analytics if visible
                if (document.getElementById('analytics-panel').classList.contains('show')) {
                    updateAnalytics();
                }
                
                // Update other views if visible
                if (currentView === 'table') {
                    renderTable();
                } else if (currentView === 'kanban') {
                    renderKanban();
                }
            })
            .catch(error => {
                console.error('Error loading events:', error);
            });
    }
    
    function getEventColor(event) {
        // Platform-based coloring only
        const platform = (event.platform || 'Other').toLowerCase();
        switch(platform) {
            case 'youtube': return '#FF0000';
            case 'x':
            case 'twitter': return '#000000';
            case 'instagram': return '#E4405F';
            case 'tiktok': return '#010101';
            case 'blog': return '#6B7280';
            default: return '#9CA3AF';
        }
    }
    
    function shouldHideOldContent(event) {
        if (!event.publish_date) return false;
        
        const eventDate = new Date(event.publish_date);
        const today = new Date();
        const daysSince = Math.floor((today - eventDate) / (1000 * 60 * 60 * 24));
        
        return daysSince > 1;
    }
    
    function renderTable() {
        const tbody = document.getElementById('table-body');
        tbody.innerHTML = '';
        
        // Filter out old content
        const visibleEvents = events.filter(event => !shouldHideOldContent(event));
        
        visibleEvents.forEach(event => {
            const row = document.createElement('tr');
            
            // Add platform color as accent
            const platformColor = getEventColor(event);
            row.style.borderLeft = `3px solid ${platformColor}`;
            
            row.innerHTML = `
                <td>${event.title}${event.content_type === 'sponsored' ? ' 💰' : ''}</td>
                <td>${event.publish_date ? new Date(event.publish_date).toLocaleDateString() : '-'}</td>
                <td>${event.platform || '-'}</td>
                <td><span class="kanban-tag ${event.content_type === 'sponsored' ? 'sponsored' : 'organic'}">${event.content_type === 'sponsored' ? 'Sponsored' : 'Organic'}</span></td>
                <td><span class="status-badge status-${event.status || 'draft'}">${event.status || 'draft'}</span></td>
                <td>
                    <button class="btn btn-icon" onclick="editEvent('${event.id}')">
                        <i class="ph ph-pencil"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }
    
    function renderKanban() {
        // Clear all columns
        const columns = ['draft', 'in-progress', 'review', 'ready'];
        columns.forEach(status => {
            const column = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-column-body`);
            column.innerHTML = '';
        });
        
        // Filter out old content
        const visibleEvents = events.filter(event => !shouldHideOldContent(event));
        
        // Group events by status
        const eventsByStatus = {
            'draft': [],
            'in-progress': [],
            'review': [],
            'ready': []
        };
        
        visibleEvents.forEach(event => {
            const status = event.status || 'draft';
            if (eventsByStatus[status]) {
                eventsByStatus[status].push(event);
            }
        });
        
        // Render cards in each column
        Object.entries(eventsByStatus).forEach(([status, statusEvents]) => {
            const column = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-column-body`);
            const countEl = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-column-count`);
            
            countEl.textContent = statusEvents.length;
            
            statusEvents.forEach(event => {
                const card = document.createElement('div');
                card.className = 'kanban-card';
                card.draggable = true;
                card.dataset.eventId = event.id;
                
                // Add platform-based styling
                const platform = (event.platform || 'Other').toLowerCase();
                card.style.borderLeft = `3px solid ${getEventColor(event)}`;
                
                card.innerHTML = `
                    <div class="kanban-card-title">${event.title}${event.content_type === 'sponsored' ? ' 💰' : ''}</div>
                    <div class="kanban-card-meta">
                        ${event.platform ? `<span class="kanban-tag">${event.platform}</span>` : ''}
                        <span class="kanban-tag ${event.content_type === 'sponsored' ? 'sponsored' : 'organic'}">${event.content_type === 'sponsored' ? 'Sponsored' : 'Organic'}</span>
                    </div>
                    ${event.publish_date ? `
                        <div class="kanban-card-date">
                            <i class="ph ph-calendar"></i>
                            ${new Date(event.publish_date).toLocaleDateString()}
                        </div>
                    ` : ''}
                `;
                
                // Add drag event listeners
                card.addEventListener('dragstart', function(e) {
                    e.dataTransfer.effectAllowed = 'move';
                    e.dataTransfer.setData('eventId', event.id);
                    card.classList.add('dragging');
                });
                
                card.addEventListener('dragend', function(e) {
                    card.classList.remove('dragging');
                    document.querySelectorAll('.kanban-column').forEach(col => {
                        col.classList.remove('drag-over');
                    });
                    
                    // Clear any pending timeout
                    if (dragTimeout) {
                        clearTimeout(dragTimeout);
                        dragTimeout = null;
                    }
                });
                
                card.addEventListener('click', function(e) {
                    if (!e.target.classList.contains('dragging')) {
                        openEditEventModal(event.id);
                    }
                });
                
                column.appendChild(card);
            });
        });
    }
    
    // Add event listeners for kanban columns to handle drag leave
    document.querySelectorAll('.kanban-column-body').forEach(column => {
        column.addEventListener('dragleave', function(e) {
            if (e.target === column) {
                column.parentElement.classList.remove('drag-over');
            }
        });
    });
});

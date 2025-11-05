// Content Calendar JavaScript - Updated Version
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
        removeDragGhost();
        const rect = eventEl.getBoundingClientRect();
        dragGhost = document.createElement('div');
        dragGhost.className = 'drag-ghost';
        dragGhost.textContent = event.title;
        dragGhost.style.width = rect.width + 'px';
        dragGhost.style.minWidth = rect.width + 'px';
        dragGhost.style.maxWidth = rect.width + 'px';

        const eventData = events.find(e => e.id == event.id);
        if (eventData) {
            if (eventData.platform) {
                dragGhost.classList.add('platform-' + eventData.platform.toLowerCase().replace(/[^a-z0-9]/g, ''));
            } else {
                dragGhost.classList.add('platform-other');
            }
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
                const ghost = createDragGhost(info.el, info.event);
                document.addEventListener('mousemove', updateDragGhostPosition);
                updateDragGhostPosition(info.jsEvent);
                info.el.style.opacity = '0.5';
            },

            eventDragStop: function(info) {
                removeDragGhost();
                document.removeEventListener('mousemove', updateDragGhostPosition);
                info.el.style.opacity = '';
            },
            
            eventDrop: function(info) {
                removeDragGhost();
                document.removeEventListener('mousemove', updateDragGhostPosition);

                const newDateTime = info.event.start.toISOString();
                const eventData = {
                    publish_date: newDateTime
                };

                // Update calendar event
                fetch(`/content-calendar/api/event/${info.event.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(eventData)
                })
                .then(response => response.json())
                .then(data => {
                    if (!data.success) {
                        info.revert();
                        return;
                    }

                    const eventIndex = events.findIndex(e => e.id == info.event.id);
                    if (eventIndex !== -1) {
                        events[eventIndex].publish_date = newDateTime;

                        // If this is a YouTube scheduled video, update YouTube as well
                        if (events[eventIndex].youtube_video_id) {
                            return fetch('/api/update-youtube-schedule', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    video_id: events[eventIndex].youtube_video_id,
                                    publish_time: newDateTime
                                })
                            });
                        }
                    }
                })
                .then(response => {
                    if (response) {
                        return response.json();
                    }
                })
                .then(data => {
                    if (data && !data.success) {
                        console.error('Failed to update YouTube schedule:', data.error);
                        alert('Calendar updated but YouTube schedule update failed: ' + data.error);
                    } else if (data && data.success) {
                        console.log('YouTube schedule updated successfully');
                    }
                })
                .catch(error => {
                    console.error('Error updating event:', error);
                    info.revert();
                });
            },

            dateClick: function(info) {
                const clickedDate = new Date(info.date);
                const year = clickedDate.getFullYear();
                const month = String(clickedDate.getMonth() + 1).padStart(2, '0');
                const day = String(clickedDate.getDate()).padStart(2, '0');
                const dateString = `${year}-${month}-${day}`;
                
                openNewEventModal();
                document.getElementById('event-date').value = dateString;
                document.getElementById('event-time').value = '12:00';
            },
            
            eventClick: function(info) {
                openEditEventModal(info.event.id);
            },
            
            eventDidMount: function(info) {
                const event = events.find(e => e.id == info.event.id);
                if (event) {
                    if (event.content_type === 'sponsored') {
                        info.el.classList.add('sponsored');
                    }
                    if (event.platform) {
                        const platformClass = 'platform-' + event.platform.toLowerCase().replace(/[^a-z0-9]/g, '');
                        info.el.classList.add(platformClass);
                    } else {
                        info.el.classList.add('platform-other');
                    }

                    // Add clock icon for YouTube scheduled videos
                    if (event.youtube_video_id) {
                        const titleEl = info.el.querySelector('.fc-event-title');
                        if (titleEl) {
                            const clockIcon = document.createElement('i');
                            clockIcon.className = 'ph-fill ph-clock clock-icon';
                            titleEl.insertBefore(clockIcon, titleEl.firstChild);
                        }
                    }

                    // Add clock icon for Instagram scheduled posts
                    if (event.instagram_post_id) {
                        const titleEl = info.el.querySelector('.fc-event-title');
                        if (titleEl) {
                            const clockIcon = document.createElement('i');
                            clockIcon.className = 'ph-fill ph-clock clock-icon';
                            titleEl.insertBefore(clockIcon, titleEl.firstChild);
                        }
                    }

                    // Add clock icon for TikTok scheduled posts
                    if (event.tiktok_post_id) {
                        const titleEl = info.el.querySelector('.fc-event-title');
                        if (titleEl) {
                            const clockIcon = document.createElement('i');
                            clockIcon.className = 'ph-fill ph-clock clock-icon';
                            titleEl.insertBefore(clockIcon, titleEl.firstChild);
                        }
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
    
    // Platform selector - NEW
    window.selectPlatform = function(platform) {
        // Update the platform dropdown
        const platformOption = document.querySelector(`[data-platform="${platform}"]`);
        if (platformOption) {
            const selectedPlatformText = document.getElementById('selected-platform-text');
            const selectedPlatformInput = document.getElementById('selected-platform');
            const platformDropdownMenu = document.getElementById('platform-dropdown-menu');

            // Remove 'selected' class from all options
            if (platformDropdownMenu) {
                platformDropdownMenu.querySelectorAll('.dropdown-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                // Add 'selected' class to current platform
                platformOption.classList.add('selected');
            }

            if (selectedPlatformText) {
                selectedPlatformText.textContent = platform;
            }

            if (selectedPlatformInput) {
                selectedPlatformInput.value = platform;
            }
        }
    };
    
    // Toggle analytics
    window.toggleAnalytics = function() {
        const isAnalyticsActive = document.getElementById('analytics-toggle-btn').classList.contains('active');

        if (!isAnalyticsActive) {
            currentView = 'analytics';
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.getElementById('analytics-toggle-btn').classList.add('active');

            // Hide all main panels
            document.getElementById('calendar').style.display = 'none';
            document.getElementById('table-view').style.display = 'none';
            document.getElementById('kanban-view').style.display = 'none';

            // Show analytics panel
            const panel = document.getElementById('analytics-panel');
            panel.style.display = 'block';
            panel.classList.add('show');
            updateAnalytics();
        } else {
            switchView('calendar');
        }
    };
    
    // Update analytics
    function updateAnalytics() {
        const monthStart = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);
        const monthEnd = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0);
        
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
        
        if (totalPosts > 0) {
            document.getElementById('organic-percentage').textContent = `${Math.round((organicPosts / totalPosts) * 100)}%`;
            document.getElementById('sponsored-percentage').textContent = `${Math.round((sponsoredPosts / totalPosts) * 100)}%`;
        } else {
            document.getElementById('organic-percentage').textContent = '0%';
            document.getElementById('sponsored-percentage').textContent = '0%';
        }

        generateDailyChart(monthEvents, monthStart, monthEnd);
    }

    // Generate daily posts chart
    function generateDailyChart(monthEvents, monthStart, monthEnd) {
        const daysInMonth = monthEnd.getDate();
        const dailyCounts = new Array(daysInMonth).fill(0);

        monthEvents.forEach(event => {
            if (event.publish_date) {
                const day = new Date(event.publish_date).getDate() - 1;
                if (day >= 0 && day < daysInMonth) {
                    dailyCounts[day]++;
                }
            }
        });

        const maxCount = Math.max(...dailyCounts, 1);
        const yAxisSteps = 5;
        const yAxisMax = Math.ceil(maxCount / yAxisSteps) * yAxisSteps || 5;

        const yAxisContainer = document.getElementById('chart-y-axis');
        yAxisContainer.innerHTML = '';
        for (let i = yAxisSteps; i >= 0; i--) {
            const label = document.createElement('div');
            label.textContent = Math.round((yAxisMax / yAxisSteps) * i);
            yAxisContainer.appendChild(label);
        }

        const barsContainer = document.getElementById('chart-bars');
        barsContainer.innerHTML = '';

        dailyCounts.forEach((count, index) => {
            const barWrapper = document.createElement('div');
            barWrapper.className = 'chart-bar';
            barWrapper.style.height = `${(count / yAxisMax) * 100}%`;

            const tooltip = document.createElement('div');
            tooltip.className = 'chart-bar-tooltip';
            const date = new Date(monthStart);
            date.setDate(index + 1);
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            tooltip.textContent = `${dateStr}: ${count} ${count === 1 ? 'post' : 'posts'}`;
            barWrapper.appendChild(tooltip);

            barsContainer.appendChild(barWrapper);
        });

        const xAxisContainer = document.getElementById('chart-x-axis');
        xAxisContainer.innerHTML = '';

        const labelInterval = daysInMonth > 15 ? 5 : 3;

        for (let i = 0; i < daysInMonth; i++) {
            const label = document.createElement('div');
            label.className = 'chart-x-label';

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

        document.querySelectorAll('.week-toggle-btn').forEach(btn => {
            btn.classList.remove('active');
            if ((startDay === 1 && btn.textContent.includes('Mon')) ||
                (startDay === 0 && btn.textContent.includes('Sun'))) {
                btn.classList.add('active');
            }
        });

        if (calendar) {
            calendar.setOption('firstDay', weekStart);
        }

        localStorage.setItem('calendarWeekStart', weekStart);
    };

    const savedWeekStart = localStorage.getItem('calendarWeekStart');
    if (savedWeekStart !== null) {
        weekStart = parseInt(savedWeekStart);
        setTimeout(() => {
            document.querySelectorAll('.week-toggle-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`.week-toggle-btn:${weekStart === 0 ? 'last-child' : 'first-child'}`).classList.add('active');
        }, 0);
    }

    window.switchView = function(view) {
        currentView = view;

        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.textContent.toLowerCase().includes(view)) {
                btn.classList.add('active');
            }
        });

        // Hide all main panels first
        const calendarEl = document.getElementById('calendar');
        const tableView = document.getElementById('table-view');
        const kanbanView = document.getElementById('kanban-view');
        const analyticsPanel = document.getElementById('analytics-panel');

        if (calendarEl) calendarEl.style.display = 'none';
        if (tableView) tableView.style.display = 'none';
        if (kanbanView) kanbanView.style.display = 'none';
        if (analyticsPanel) {
            analyticsPanel.style.display = 'none';
            analyticsPanel.classList.remove('show');
        }

        // Show selected panel
        if (view === 'calendar' && calendarEl) {
            calendarEl.style.display = 'block';
            // Force calendar to re-render and resize
            setTimeout(() => {
                if (calendar) {
                    calendar.render();
                    calendar.updateSize();
                }
            }, 50);
        } else if (view === 'table' && tableView) {
            tableView.style.display = 'block';
            renderTable();
        } else if (view === 'kanban' && kanbanView) {
            kanbanView.style.display = 'block';
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
    
    window.openNewEventModal = function(contentType = 'organic') {
        editingEventId = null;
        document.getElementById('modal-title').textContent = 'Add New Event';
        document.getElementById('delete-btn').style.display = 'none';
        document.getElementById('event-id').value = '';
        document.getElementById('event-title').value = '';
        document.getElementById('event-date').value = '';
        document.getElementById('event-time').value = '';
        selectPlatform('YouTube');
        document.getElementById('event-status').value = 'draft';
        document.getElementById('event-notes').value = '';
        selectContentType(contentType);
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
        
        // Split datetime into date and time
        if (event.publish_date) {
            const eventDate = new Date(event.publish_date);
            const year = eventDate.getFullYear();
            const month = String(eventDate.getMonth() + 1).padStart(2, '0');
            const day = String(eventDate.getDate()).padStart(2, '0');
            const hours = String(eventDate.getHours()).padStart(2, '0');
            const minutes = String(eventDate.getMinutes()).padStart(2, '0');
            
            document.getElementById('event-date').value = `${year}-${month}-${day}`;
            document.getElementById('event-time').value = `${hours}:${minutes}`;
        } else {
            document.getElementById('event-date').value = '';
            document.getElementById('event-time').value = '';
        }
        
        selectPlatform(event.platform || 'YouTube');
        document.getElementById('event-status').value = event.status || 'draft';
        document.getElementById('event-notes').value = event.notes || '';
        selectContentType(event.content_type === 'sponsored' ? 'sponsored' : 'organic');
        
        document.getElementById('event-modal').classList.add('show');
    };
    
    window.closeEventModal = function() {
        document.getElementById('event-modal').classList.remove('show');
        editingEventId = null;
    };
    
    let isSaving = false;

    window.saveEvent = function() {
        // Prevent duplicate submissions
        if (isSaving) {
            return;
        }

        const eventId = document.getElementById('event-id').value;
        const title = document.getElementById('event-title').value;
        const dateValue = document.getElementById('event-date').value;
        const timeValue = document.getElementById('event-time').value;
        const platform = document.getElementById('selected-platform').value;
        const status = document.getElementById('event-status').value;
        const notes = document.getElementById('event-notes').value;
        const contentType = document.querySelector('.content-type-option.selected').dataset.type;

        if (!title) {
            return;
        }

        // Set saving flag
        isSaving = true;

        // Combine date and time if both provided, convert to ISO string
        let publishDate = null;
        if (dateValue && timeValue) {
            const localDateTime = new Date(`${dateValue}T${timeValue}:00`);
            publishDate = localDateTime.toISOString();
        } else if (dateValue) {
            const localDateTime = new Date(`${dateValue}T12:00:00`);
            publishDate = localDateTime.toISOString();
        }

        const eventData = {
            title: title,
            publish_date: publishDate,
            platform: platform,
            status: status,
            notes: notes,
            content_type: contentType
        };

        const url = eventId ?
            `/content-calendar/api/event/${eventId}` :
            '/content-calendar/api/event';
        const method = eventId ? 'PUT' : 'POST';

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
                // Backend automatically handles YouTube/Instagram/TikTok schedule updates
                closeEventModal();
                loadEvents();
            }
        })
        .catch(error => {
            console.error('Error saving event:', error);
        })
        .finally(() => {
            // Reset saving flag after request completes
            isSaving = false;
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
        
        if (dragTimeout) {
            clearTimeout(dragTimeout);
        }
        
        dragTimeout = setTimeout(() => {
            ev.currentTarget.parentElement.classList.add('drag-over');
        }, 50);
    };
    
    window.dropCard = function(ev) {
        ev.preventDefault();
        
        if (dragTimeout) {
            clearTimeout(dragTimeout);
            dragTimeout = null;
        }
        
        ev.currentTarget.parentElement.classList.remove('drag-over');
        
        const eventId = ev.dataTransfer.getData('eventId');
        const newStatus = ev.currentTarget.parentElement.dataset.status;
        
        const card = document.querySelector(`.kanban-card[data-event-id="${eventId}"]`);
        if (card) {
            ev.currentTarget.appendChild(card);
        }
        
        fetch(`/content-calendar/api/event/${eventId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const eventIndex = events.findIndex(e => e.id == eventId);
                if (eventIndex !== -1) {
                    events[eventIndex].status = newStatus;
                }
                renderKanban();
            } else {
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
                
                if (calendar) {
                    calendar.removeAllEvents();
                    data.filter(event => event.publish_date).forEach(event => {
                        const eventDate = new Date(event.publish_date);
                        const today = new Date();
                        const daysUntil = Math.floor((eventDate - today) / (1000 * 60 * 60 * 24));
                        
                        let backgroundColor = getEventColor(event);
                        
                        const classNames = [];
                        if (event.content_type === 'sponsored') {
                            classNames.push('sponsored');
                        }
                        if (event.youtube_video_id) {
                            classNames.push('youtube-scheduled');
                        }
                        if (event.instagram_post_id) {
                            classNames.push('instagram-scheduled');
                        }
                        if (event.tiktok_post_id) {
                            classNames.push('tiktok-scheduled');
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
                            editable: true,
                            startEditable: true
                        });
                    });
                }
                
                if (document.getElementById('analytics-panel').classList.contains('show')) {
                    updateAnalytics();
                }
                
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
        const platform = (event.platform || 'Other').toLowerCase();
        switch(platform) {
            case 'youtube': return '#CC0029';
            case 'x':
            case 'twitter': return '#4A5568';
            case 'instagram': return '#C13584';
            case 'tiktok': return '#4A5568';
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
        
        const visibleEvents = events.filter(event => !shouldHideOldContent(event));
        
        visibleEvents.forEach(event => {
            const row = document.createElement('tr');
            
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
        const columns = ['draft', 'in-progress', 'review', 'ready'];
        columns.forEach(status => {
            const column = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-column-body`);
            column.innerHTML = '';
        });
        
        const visibleEvents = events.filter(event => !shouldHideOldContent(event));
        
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
        
        Object.entries(eventsByStatus).forEach(([status, statusEvents]) => {
            const column = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-column-body`);
            const countEl = document.querySelector(`.kanban-column[data-status="${status}"] .kanban-column-count`);
            
            countEl.textContent = statusEvents.length;
            
            statusEvents.forEach(event => {
                const card = document.createElement('div');
                card.className = 'kanban-card';
                card.draggable = true;
                card.dataset.eventId = event.id;
                
                const platform = (event.platform || 'Other').toLowerCase();
                card.style.borderLeft = `3px solid ${getEventColor(event)}`;
                
                card.innerHTML = `
                    <div class="kanban-card-title">${event.title}${event.content_type === 'sponsored' ? ' 💰' : ''}</div>
                    <div class="kanban-card-meta">
                        <span class="kanban-tag ${event.content_type === 'sponsored' ? 'sponsored' : 'organic'}">${event.content_type === 'sponsored' ? 'Sponsored' : 'Organic'}</span>
                    </div>
                    ${event.publish_date ? `
                        <div class="kanban-card-date">
                            <i class="ph ph-calendar"></i>
                            ${new Date(event.publish_date).toLocaleDateString()}
                        </div>
                    ` : ''}
                `;
                
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
    
    document.querySelectorAll('.kanban-column-body').forEach(column => {
        column.addEventListener('dragleave', function(e) {
            if (e.target === column) {
                column.parentElement.classList.remove('drag-over');
            }
        });
    });

    // Dropdown functionality for "Add New Event"
    const addEventDropdownTrigger = document.getElementById('add-event-dropdown-trigger');
    const addEventDropdownMenu = document.getElementById('add-event-dropdown-menu');

    if (addEventDropdownTrigger && addEventDropdownMenu) {
        addEventDropdownTrigger.addEventListener('click', function(e) {
            e.stopPropagation();
            addEventDropdownTrigger.classList.toggle('active');
            addEventDropdownMenu.classList.toggle('active');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!addEventDropdownTrigger.contains(e.target) && !addEventDropdownMenu.contains(e.target)) {
                addEventDropdownTrigger.classList.remove('active');
                addEventDropdownMenu.classList.remove('active');
            }
        });

        // Close dropdown when an option is clicked
        addEventDropdownMenu.querySelectorAll('.dropdown-option').forEach(option => {
            option.addEventListener('click', function() {
                addEventDropdownTrigger.classList.remove('active');
                addEventDropdownMenu.classList.remove('active');
            });
        });
    }

    // Platform Dropdown functionality
    const platformDropdownTrigger = document.getElementById('platform-dropdown-trigger');
    const platformDropdownMenu = document.getElementById('platform-dropdown-menu');
    const selectedPlatformText = document.getElementById('selected-platform-text');
    const selectedPlatformInput = document.getElementById('selected-platform');

    if (platformDropdownTrigger && platformDropdownMenu) {
        platformDropdownTrigger.addEventListener('click', function(e) {
            e.stopPropagation();
            platformDropdownTrigger.classList.toggle('active');
            platformDropdownMenu.classList.toggle('active');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!platformDropdownTrigger.contains(e.target) && !platformDropdownMenu.contains(e.target)) {
                platformDropdownTrigger.classList.remove('active');
                platformDropdownMenu.classList.remove('active');
            }
        });

        // Handle platform selection
        platformDropdownMenu.querySelectorAll('.dropdown-option').forEach(option => {
            option.addEventListener('click', function() {
                const platform = this.getAttribute('data-platform');

                // Remove 'selected' class from all options
                platformDropdownMenu.querySelectorAll('.dropdown-option').forEach(opt => {
                    opt.classList.remove('selected');
                });

                // Add 'selected' class to clicked option
                this.classList.add('selected');

                // Update selected text
                selectedPlatformText.textContent = platform;

                // Update hidden input
                selectedPlatformInput.value = platform;

                // Close dropdown
                platformDropdownTrigger.classList.remove('active');
                platformDropdownMenu.classList.remove('active');
            });
        });
    }

    // Populate date dropdown with next 365 days
    const dateSelect = document.getElementById('event-date');
    if (dateSelect) {
        const today = new Date();
        for (let i = 0; i < 365; i++) {
            const date = new Date(today);
            date.setDate(today.getDate() + i);

            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');

            const value = `${year}-${month}-${day}`;
            const display = `${day}/${month}/${year}`;

            const option = document.createElement('option');
            option.value = value;
            option.textContent = display;
            dateSelect.appendChild(option);
        }
    }
});
document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const eventsList = document.getElementById('events-list');
    const recentChatsList = document.getElementById('recent-chats-list');
    const newChatBtn = document.getElementById('new-chat-btn');

    // Tasks View Elements
    const navChat = document.getElementById('nav-chat');
    const navTasks = document.getElementById('nav-tasks');
    const navDashboard = document.getElementById('nav-dashboard');
    const navQuizzes = document.getElementById('nav-quizzes');
    const chatArea = document.querySelector('.chat-area');
    const tasksArea = document.getElementById('tasks-view');
    const dashboardArea = document.getElementById('dashboard-view');
    const quizzesArea = document.getElementById('quizzes-view');
    const scheduledTasksList = document.getElementById('scheduled-tasks-list');
    const manualTasksList = document.getElementById('manual-tasks-list');
    const newTaskInput = document.getElementById('new-task-input');
    const addTaskBtn = document.getElementById('add-task-btn');

    // Quiz View Elements
    const quizSelection = document.getElementById('quiz-selection');
    const quizContent = document.getElementById('quiz-content');
    const backToQuizSelection = document.getElementById('back-to-quiz-selection');

    let currentSessionId = null;

    // Initial load
    fetchEvents();
    loadSessions();
    loadManualTasks();
    loadDashboard();

    // Real-time Dashboard Updates (Poll every 30 seconds)
    setInterval(loadDashboard, 30000);

    // Event Listeners
    if (newChatBtn) {
        newChatBtn.addEventListener('click', createNewChat);
    }

    function createNewChat() {
        currentSessionId = null;
        if (chatMessages) {
            chatMessages.innerHTML = '';
        }
        if (userInput) {
            userInput.value = '';
        }
        // Use window.switchView to ensure it works from anywhere
        if (typeof switchView === 'function') {
            switchView('chat');
        } else if (window.switchView) {
            window.switchView('chat');
        }
    }

    // Expose to window for inline onclick handlers
    window.startNewChat = createNewChat;


    if (navChat) {
        navChat.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('chat');
        });
    }

    if (navTasks) {
        navTasks.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('tasks');
        });
    }

    if (navDashboard) {
        navDashboard.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('dashboard');
        });
    }

    if (navQuizzes) {
        navQuizzes.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('quizzes');
        });
    }

    if (backToQuizSelection) {
        backToQuizSelection.addEventListener('click', () => {
            quizContent.classList.add('hidden');
            quizSelection.classList.remove('hidden');
        });
    }

    // Quiz mode selection
    document.querySelectorAll('.quiz-mode-card').forEach(card => {
        const startBtn = card.querySelector('.quiz-start-btn');
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                const mode = card.getAttribute('data-mode');
                selectQuizMode(mode);
            });
        }
    });

    if (addTaskBtn) {
        addTaskBtn.addEventListener('click', addManualTask);
    }

    if (newTaskInput) {
        newTaskInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                addManualTask();
            }
        });
    }

    const refreshBtn = document.getElementById('refresh-calendar');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', fetchEvents);
    }

    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = userInput.value.trim();
            if (!message) return;

            addMessage(message, 'user');
            userInput.value = '';

            // Show thinking indicator
            const thinkingMsg = showThinking();

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message,
                        session_id: currentSessionId
                    })
                });

                // Remove thinking indicator
                if (thinkingMsg) thinkingMsg.remove();

                const data = await response.json();

                if (data.session_id) {
                    currentSessionId = data.session_id;
                }

                if (data.response) {
                    addMessage(data.response, 'agent');
                }

                if (data.events_updated) {
                    fetchEvents();
                    loadDashboard();
                }

                loadSessions();
            } catch (error) {
                // Remove thinking indicator
                if (thinkingMsg) thinkingMsg.remove();
                console.error('Error:', error);
                addMessage('Sorry, something went wrong.', 'agent');
            }
        });
    }

    function showThinking() {
        if (!chatMessages) return null;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent thinking';

        messageDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="content">
                Thinking<div class="thinking-dots"><span></span><span></span><span></span></div>
            </div>
        `;

        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return messageDiv;
    }

    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');

    if (uploadBtn && fileInput) {
        uploadBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', uploadFile);
    }

    async function uploadFile() {
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                addMessage(`✓ File "${file.name}" uploaded successfully!`, 'agent');
            } else {
                addMessage(`✗ Upload failed: ${data.error}`, 'agent');
            }
        } catch (error) {
            console.error('Upload error:', error);
            addMessage('✗ Upload failed.', 'agent');
        }

        fileInput.value = '';
    }

    function addMessage(content, sender) {
        if (!chatMessages) return;

        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);

        const avatar = document.createElement('div');
        avatar.classList.add('avatar');
        avatar.innerHTML = sender === 'user' ?
            '<i class="fa-solid fa-user"></i>' :
            '<i class="fa-solid fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('content');

        const lines = content.split('\n');
        lines.forEach(line => {
            const p = document.createElement('p');
            p.textContent = line;
            contentDiv.appendChild(p);
        });

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function fetchEvents() {
        if (!eventsList) return;

        try {
            const response = await fetch('/events');
            const data = await response.json();

            if (!data.ok) {
                console.error("Events API Error:", data.error);
                eventsList.innerHTML = `<div class="empty-state error">Error: ${data.error}</div>`;
                if (scheduledTasksList) {
                    scheduledTasksList.innerHTML = `<div class="empty-state error">Error: ${data.error}</div>`;
                }
                return;
            }

            eventsList.innerHTML = '';

            // Also clear the scheduled tasks list if it exists
            if (scheduledTasksList) {
                scheduledTasksList.innerHTML = '';
            }

            let hasEventsToday = false;

            if (data.events && data.events.length > 0) {
                const today = new Date();

                data.events.forEach(event => {
                    // 1. Populate Sidebar List (All upcoming events)
                    const eventItem = document.createElement('div');
                    eventItem.classList.add('event-item');

                    const startDate = new Date(event.start.dateTime || event.start.date);
                    const timeStr = startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                    // Check if event is today
                    const isToday = startDate.getDate() === today.getDate() &&
                        startDate.getMonth() === today.getMonth() &&
                        startDate.getFullYear() === today.getFullYear();

                    eventItem.innerHTML = `
                        <div class="event-time">${timeStr}</div>
                        <div class="event-title">${event.summary}</div>
                    `;
                    eventsList.appendChild(eventItem);

                    // 2. Populate Scheduled Tasks List (All upcoming events)
                    if (scheduledTasksList) {
                        hasEventsToday = true; // Renaming variable conceptually to hasEvents
                        const taskItem = document.createElement('div');
                        taskItem.classList.add('task-item');

                        const isCompleted = event.summary.startsWith("✅ ");
                        if (isCompleted) {
                            taskItem.classList.add('completed');
                        }

                        const checkbox = document.createElement('input');
                        checkbox.type = 'checkbox';
                        checkbox.classList.add('task-checkbox');
                        checkbox.checked = isCompleted;
                        checkbox.onclick = () => window.toggleEventCompletion(event.id, event.summary);

                        const taskContent = document.createElement('div');
                        taskContent.classList.add('task-content');

                        const taskText = document.createElement('div');
                        taskText.classList.add('task-text');
                        taskText.textContent = event.summary;
                        if (isCompleted) {
                            taskText.style.textDecoration = 'line-through';
                            taskText.style.color = 'var(--text-secondary)';
                        }

                        const taskMeta = document.createElement('div');
                        taskMeta.classList.add('task-meta');
                        const dateStr = startDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                        taskMeta.textContent = `${dateStr}, ${timeStr} • ${event.description || 'Google Calendar Event'}`;

                        taskContent.appendChild(taskText);
                        taskContent.appendChild(taskMeta);

                        taskItem.appendChild(checkbox);
                        taskItem.appendChild(taskContent);

                        // Add delete button for completed tasks
                        if (isCompleted) {
                            const deleteBtn = document.createElement('button');
                            deleteBtn.classList.add('delete-task-btn');
                            deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                            deleteBtn.title = 'Delete event';
                            deleteBtn.onclick = () => window.deleteCalendarEvent(event.id, event.summary);
                            taskItem.appendChild(deleteBtn);
                        }

                        scheduledTasksList.appendChild(taskItem);
                    }
                });
            }

            // Handle empty states
            if (eventsList.children.length === 0) {
                eventsList.innerHTML = '<div class="empty-state">No upcoming events</div>';
            }

            if (scheduledTasksList && !hasEventsToday) {
                scheduledTasksList.innerHTML = '<div class="empty-state">No upcoming events scheduled.</div>';
            }

        } catch (error) {
            console.error('Error fetching events:', error);
            eventsList.innerHTML = '<div class="empty-state">Failed to load events</div>';
            if (scheduledTasksList) {
                scheduledTasksList.innerHTML = '<div class="empty-state">Failed to load events</div>';
            }
        }
    }

    // Expose globally
    window.toggleEventCompletion = async function (eventId, currentSummary) {
        try {
            const response = await fetch('/mark_event_complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ event_id: eventId, summary: currentSummary })
            });

            const data = await response.json();
            if (data.ok) {
                fetchEvents(); // Refresh list
            } else {
                alert('Failed to update task');
            }
        } catch (error) {
            console.error('Error updating task:', error);
        }
    };

    // Delete calendar event
    window.deleteCalendarEvent = async function (eventId, eventSummary) {
        if (!confirm(`Are you sure you want to delete "${eventSummary}"?`)) {
            return;
        }

        try {
            const response = await fetch('/delete_calendar_event', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ event_id: eventId })
            });

            const data = await response.json();
            if (data.ok) {
                fetchEvents(); // Refresh list
            } else {
                alert('Failed to delete event');
            }
        } catch (error) {
            console.error('Error deleting event:', error);
            alert('Failed to delete event');
        }
    };

    async function loadSessions() {
        if (!recentChatsList) return;

        try {
            const response = await fetch('/sessions');
            const sessions = await response.json();

            recentChatsList.innerHTML = '';

            sessions.forEach(session => {
                const chatItem = document.createElement('div');
                chatItem.classList.add('chat-item');
                if (session.id === currentSessionId) {
                    chatItem.classList.add('active');
                }

                const title = document.createElement('div');
                title.classList.add('chat-title');
                title.textContent = session.title || 'New Chat';
                title.onclick = () => loadSession(session.id);

                const deleteBtn = document.createElement('button');
                deleteBtn.classList.add('delete-chat-btn');
                deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();
                    deleteSession(session.id);
                };

                chatItem.appendChild(title);
                chatItem.appendChild(deleteBtn);
                recentChatsList.appendChild(chatItem);
            });
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    }

    async function deleteSession(sessionId) {
        try {
            await fetch(`/delete_session/${sessionId}`, { method: 'DELETE' });
            if (sessionId === currentSessionId) {
                createNewChat();
            }
            loadSessions();
        } catch (error) {
            console.error('Error deleting session:', error);
        }
    }

    async function loadSession(sessionId) {
        if (sessionId === currentSessionId) return;

        try {
            const response = await fetch(`/history/${sessionId}`);
            const history = await response.json();

            currentSessionId = sessionId;
            if (chatMessages) {
                chatMessages.innerHTML = '';

                history.forEach(msg => {
                    const sender = msg.role === 'model' ? 'agent' : 'user';
                    addMessage(msg.content, sender);
                });
            }

            loadSessions();
        } catch (error) {
            console.error('Error loading session:', error);
        }
    }

    function switchView(view) {
        if (view === 'chat') {
            chatArea.classList.remove('hidden');
            tasksArea.classList.add('hidden');
            dashboardArea.classList.add('hidden');
            quizzesArea.classList.add('hidden');
            navChat.classList.add('active');
            navTasks.classList.remove('active');
            navDashboard.classList.remove('active');
            navQuizzes.classList.remove('active');
        } else if (view === 'tasks') {
            chatArea.classList.add('hidden');
            tasksArea.classList.remove('hidden');
            dashboardArea.classList.add('hidden');
            quizzesArea.classList.add('hidden');
            navChat.classList.remove('active');
            navTasks.classList.add('active');
            navDashboard.classList.remove('active');
            navQuizzes.classList.remove('active');
            fetchEvents();
            loadManualTasks();
        } else if (view === 'dashboard') {
            chatArea.classList.add('hidden');
            tasksArea.classList.add('hidden');
            dashboardArea.classList.remove('hidden');
            quizzesArea.classList.add('hidden');
            navChat.classList.remove('active');
            navTasks.classList.remove('active');
            navDashboard.classList.add('active');
            navQuizzes.classList.remove('active');
            loadDashboard();
        } else if (view === 'quizzes') {
            chatArea.classList.add('hidden');
            tasksArea.classList.add('hidden');
            dashboardArea.classList.add('hidden');
            quizzesArea.classList.remove('hidden');
            navChat.classList.remove('active');
            navTasks.classList.remove('active');
            navDashboard.classList.remove('active');
            navQuizzes.classList.add('active');
            quizSelection.classList.remove('hidden');
            quizContent.classList.add('hidden');
        }
    }

    // Expose switchView globally for debugging and external access
    window.switchView = switchView;

    async function loadDashboard() {
        try {
            const response = await fetch('/dashboard_stats');
            const data = await response.json();

            // Update Greeting
            const greetingEl = document.getElementById('dashboard-greeting');
            const dateEl = document.getElementById('dashboard-date');
            if (greetingEl) {
                const hour = new Date().getHours();
                let greeting = 'Good morning';
                if (hour >= 12 && hour < 17) greeting = 'Good afternoon';
                else if (hour >= 17) greeting = 'Good evening';
                greetingEl.textContent = `${greeting}, ${data.user_name || 'User'}!`;
            }
            if (dateEl) {
                const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
                dateEl.textContent = new Date().toLocaleDateString(undefined, options);
            }

            // Update Stats
            if (document.getElementById('stat-chats')) document.getElementById('stat-chats').textContent = data.total_chats;
            if (document.getElementById('stat-files')) document.getElementById('stat-files').textContent = data.total_files;
            if (document.getElementById('stat-events')) document.getElementById('stat-events').textContent = data.upcoming_events_count;

            // Update Knowledge Profile
            const knowledgeProfile = document.getElementById('knowledge-profile');
            if (knowledgeProfile) {
                knowledgeProfile.innerHTML = '';
                if (data.knowledge_profile && data.knowledge_profile.length > 0) {
                    data.knowledge_profile.forEach(item => {
                        const topic = item.topic;
                        const score = item.level;
                        const itemDiv = document.createElement('div');
                        itemDiv.classList.add('knowledge-item');
                        itemDiv.innerHTML = `
                            <div class="knowledge-header">
                                <span>${topic}</span>
                                <span>${Math.round(score)}%</span>
                            </div>
                            <div class="progress-bar-bg">
                                <div class="progress-bar-fill" style="width: ${score}%"></div>
                            </div>
                        `;
                        knowledgeProfile.appendChild(itemDiv);
                    });
                } else {
                    knowledgeProfile.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No quiz data yet. Take a quiz to see your stats!</p>';
                }
            }

            // Update Upcoming Events
            const dashboardEvents = document.getElementById('dashboard-events');
            if (dashboardEvents) {
                dashboardEvents.innerHTML = '';
                if (data.upcoming_events && data.upcoming_events.length > 0) {
                    data.upcoming_events.forEach(event => {
                        if (!event || !event.start) return;

                        const dateStr = event.start.dateTime || event.start.date;
                        if (!dateStr) return;

                        const startDate = new Date(dateStr);
                        const month = startDate.toLocaleDateString(undefined, { month: 'short' });
                        const day = startDate.getDate();
                        const time = startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                        const item = document.createElement('div');
                        item.classList.add('dashboard-list-item');
                        item.innerHTML = `
                            <div class="item-date-box">
                                <div class="date-month">${month}</div>
                                <div class="date-day">${day}</div>
                            </div>
                            <div class="item-content">
                                <h4>${event.summary || 'No Title'}</h4>
                                <p>${time}</p>
                            </div>
                        `;
                        dashboardEvents.appendChild(item);
                    });
                } else {
                    dashboardEvents.innerHTML = '<p style="color: var(--text-secondary); padding: 1rem;">No upcoming events.</p>';
                }
            }

        } catch (error) {
            console.error('Error loading dashboard:', error);
        }
    }

    async function deleteSession(sessionId) {
        try {
            await fetch(`/delete_session/${sessionId}`, { method: 'DELETE' });
            if (sessionId === currentSessionId) {
                createNewChat();
            }
            loadSessions();
        } catch (error) {
            console.error('Error deleting session:', error);
        }
    }

    async function loadSession(sessionId) {
        if (sessionId === currentSessionId) return;

        try {
            const response = await fetch(`/history/${sessionId}`);
            const history = await response.json();

            currentSessionId = sessionId;
            if (chatMessages) {
                chatMessages.innerHTML = '';

                history.forEach(msg => {
                    const sender = msg.role === 'model' ? 'agent' : 'user';
                    addMessage(msg.content, sender);
                });
            }

            loadSessions();
        } catch (error) {
            console.error('Error loading session:', error);
        }
    }

    function switchView(view) {
        if (view === 'chat') {
            chatArea.classList.remove('hidden');
            tasksArea.classList.add('hidden');
            dashboardArea.classList.add('hidden');
            quizzesArea.classList.add('hidden');
            navChat.classList.add('active');
            navTasks.classList.remove('active');
            navDashboard.classList.remove('active');
            navQuizzes.classList.remove('active');
        } else if (view === 'tasks') {
            chatArea.classList.add('hidden');
            tasksArea.classList.remove('hidden');
            dashboardArea.classList.add('hidden');
            quizzesArea.classList.add('hidden');
            navChat.classList.remove('active');
            navTasks.classList.add('active');
            navDashboard.classList.remove('active');
            navQuizzes.classList.remove('active');
            fetchEvents();
        } else if (view === 'dashboard') {
            chatArea.classList.add('hidden');
            tasksArea.classList.add('hidden');
            dashboardArea.classList.remove('hidden');
            quizzesArea.classList.add('hidden');
            navChat.classList.remove('active');
            navTasks.classList.remove('active');
            navDashboard.classList.add('active');
            navQuizzes.classList.remove('active');
            loadDashboard();
        } else if (view === 'quizzes') {
            chatArea.classList.add('hidden');
            tasksArea.classList.add('hidden');
            dashboardArea.classList.add('hidden');
            quizzesArea.classList.remove('hidden');
            navChat.classList.remove('active');
            navTasks.classList.remove('active');
            navDashboard.classList.remove('active');
            navQuizzes.classList.add('active');
            quizSelection.classList.remove('hidden');
            quizContent.classList.add('hidden');
        }
    }

    // Expose switchView globally for debugging and external access
    window.switchView = switchView;

    async function loadDashboard() {
        try {
            const response = await fetch('/dashboard_stats');
            const data = await response.json();

            // Update Greeting
            const greetingEl = document.getElementById('dashboard-greeting');
            const dateEl = document.getElementById('dashboard-date');
            if (greetingEl) {
                const hour = new Date().getHours();
                let greeting = 'Good morning';
                if (hour >= 12 && hour < 17) greeting = 'Good afternoon';
                else if (hour >= 17) greeting = 'Good evening';
                greetingEl.textContent = `${greeting}, User!`;
            }
            if (dateEl) {
                const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
                dateEl.textContent = new Date().toLocaleDateString(undefined, options);
            }

            // Update Stats
            if (document.getElementById('stat-chats')) document.getElementById('stat-chats').textContent = data.total_chats;
            if (document.getElementById('stat-files')) document.getElementById('stat-files').textContent = data.total_files;
            if (document.getElementById('stat-events')) document.getElementById('stat-events').textContent = data.upcoming_events_count;

            // Update Knowledge Profile
            const knowledgeProfile = document.getElementById('knowledge-profile');
            if (knowledgeProfile) {
                knowledgeProfile.innerHTML = '';
                if (data.knowledge_profile && data.knowledge_profile.length > 0) {
                    data.knowledge_profile.forEach(item => {
                        const topic = item.topic;
                        const score = item.level;
                        const itemDiv = document.createElement('div');
                        itemDiv.classList.add('knowledge-item');
                        itemDiv.innerHTML = `
                            <div class="knowledge-header">
                                <span>${topic}</span>
                                <span>${Math.round(score)}%</span>
                            </div>
                            <div class="progress-bar-bg">
                                <div class="progress-bar-fill" style="width: ${score}%"></div>
                            </div>
                        `;
                        knowledgeProfile.appendChild(itemDiv);
                    });
                } else {
                    knowledgeProfile.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.9rem;">No quiz data yet. Take a quiz to see your stats!</p>';
                }
            }

            // Update Upcoming Events
            const dashboardEvents = document.getElementById('dashboard-events');
            if (dashboardEvents) {
                dashboardEvents.innerHTML = '';
                if (data.upcoming_events && data.upcoming_events.length > 0) {
                    data.upcoming_events.forEach(event => {
                        if (!event || !event.start) return;

                        const dateStr = event.start.dateTime || event.start.date;
                        if (!dateStr) return;

                        const startDate = new Date(dateStr);
                        const month = startDate.toLocaleDateString(undefined, { month: 'short' });
                        const day = startDate.getDate();
                        const time = startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

                        const item = document.createElement('div');
                        item.classList.add('dashboard-list-item');
                        item.innerHTML = `
                            <div class="item-date-box">
                                <div class="date-month">${month}</div>
                                <div class="date-day">${day}</div>
                            </div>
                            <div class="item-content">
                                <h4>${event.summary || 'No Title'}</h4>
                                <p>${time}</p>
                            </div>
                        `;
                        dashboardEvents.appendChild(item);
                    });
                } else {
                    dashboardEvents.innerHTML = '<p style="color: var(--text-secondary); padding: 1rem;">No upcoming events.</p>';
                }
            }

        } catch (error) {
            console.error('Error loading dashboard:', error);
        }
    }

    function selectQuizMode(mode) {
        quizSelection.classList.add('hidden');
        quizContent.classList.remove('hidden');

        document.querySelectorAll('.quiz-mode-content').forEach(el => el.classList.add('hidden'));

        if (mode === 'upload') {
            document.getElementById('upload-quiz').classList.remove('hidden');
            loadUploadedFiles();
        } else if (mode === 'recall') {
            document.getElementById('recall-quiz').classList.remove('hidden');
            loadDailyRecallQuiz();
        } else if (mode === 'interview') {
            document.getElementById('interview-quiz').classList.remove('hidden');
            setupInterviewMode();
        }
    }

    async function loadUploadedFiles() {
        const filesList = document.getElementById('uploaded-files-list');
        try {
            const response = await fetch('/list_uploads');
            const data = await response.json();

            filesList.innerHTML = '';
            if (data.files && data.files.length > 0) {
                data.files.forEach(file => {
                    const fileItem = document.createElement('div');
                    fileItem.classList.add('file-item');
                    fileItem.style.position = 'relative';
                    fileItem.innerHTML = `
                        <div style="flex: 1; display: flex; align-items: center; gap: 1rem;" onclick="generateUploadQuiz('${file.name}')">
                            <i class="fa-solid fa-file"></i>
                            <div>
                                <div>${file.name}</div>
                                <span style="color: var(--text-secondary); font-size: 0.8rem;">(${(file.size / 1024).toFixed(1)} KB)</span>
                            </div>
                        </div>
                        <button class="delete-file-btn" onclick="event.stopPropagation(); deleteFile('${file.name}')" title="Delete file">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    `;
                    filesList.appendChild(fileItem);
                });
            } else {
                filesList.innerHTML = '<p style="color: var(--text-secondary);">No files uploaded yet. Upload a file from the chat to get started!</p>';
            }
        } catch (error) {
            console.error('Error loading files:', error);
            filesList.innerHTML = '<p style="color: #ef4444;">Failed to load files.</p>';
        }
    }

    // Make deleteFile global so it's accessible from inline onclick
    window.deleteFile = async function (filename) {
        if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
            return;
        }

        try {
            const response = await fetch('/delete_file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename })
            });
            const data = await response.json();

            if (data.success) {
                await loadUploadedFiles();
            } else {
                alert(`Failed to delete file: ${data.error}`);
            }
        } catch (error) {
            console.error('Error deleting file:', error);
            alert('Failed to delete file');
        }
    };

    window.generateUploadQuiz = async function (filename) {
        const questionsContainer = document.getElementById('upload-quiz-questions');
        questionsContainer.innerHTML = '<p>Generating quiz...</p>';
        questionsContainer.classList.remove('hidden');

        try {
            const response = await fetch('/generate_quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'upload', filename })
            });
            const data = await response.json();

            if (data.questions) {
                displayQuestions(data.questions, questionsContainer, filename);
            } else {
                questionsContainer.innerHTML = `<p style="color: #ef4444;">Error: ${data.error || 'Failed to generate quiz'}</p>`;
            }
        } catch (error) {
            console.error('Error generating quiz:', error);
            questionsContainer.innerHTML = '<p style="color: #ef4444;">Failed to generate quiz.</p>';
        }
    };

    async function loadDailyRecallQuiz() {
        const topicsContainer = document.getElementById('recall-topics');
        const questionsContainer = document.getElementById('recall-quiz-questions');

        topicsContainer.innerHTML = '<p>Loading yesterday\'s topics...</p>';

        try {
            const response = await fetch('/generate_quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'recall' })
            });
            const data = await response.json();

            if (data.topics) {
                topicsContainer.innerHTML = `<p><strong>Topics:</strong> ${data.topics.join(', ')}</p>`;
            }

            if (data.questions) {
                questionsContainer.classList.remove('hidden');
                const topicName = data.topics && data.topics.length > 0 ? data.topics[0] : 'Daily Recall';
                displayQuestions(data.questions, questionsContainer, topicName);
            } else {
                topicsContainer.innerHTML = `<p style="color: #ef4444;">${data.error || 'No study sessions found for yesterday'}</p>`;
            }
        } catch (error) {
            console.error('Error loading recall quiz:', error);
            topicsContainer.innerHTML = '<p style="color: #ef4444;">Failed to load quiz.</p>';
        }
    }

    function setupInterviewMode() {
        const startBtn = document.getElementById('start-interview-btn');
        const jobRoleInput = document.getElementById('job-role');
        const interviewChat = document.getElementById('interview-chat');

        if (startBtn) {
            startBtn.onclick = async () => {
                const jobRole = jobRoleInput.value.trim() || 'Software Developer';
                interviewChat.innerHTML = '<p>Generating interview questions...</p>';
                interviewChat.classList.remove('hidden');

                try {
                    const response = await fetch('/generate_quiz', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mode: 'interview', job_role: jobRole })
                    });
                    const data = await response.json();

                    if (data.questions) {
                        interviewChat.innerHTML = '';
                        const qaPairs = [];

                        data.questions.forEach((q, idx) => {
                            const qaCard = document.createElement('div');
                            qaCard.classList.add('interview-qa-pair');

                            // Question Section
                            const questionSection = document.createElement('div');
                            questionSection.classList.add('interview-question');
                            questionSection.innerHTML = `
                                <div class="interviewer-avatar"><i class="fa-solid fa-user-tie"></i></div>
                                <div class="question-content">
                                    <div class="question-label">Interviewer</div>
                                    <div class="question-text">${q.question}</div>
                                </div>
                            `;
                            qaCard.appendChild(questionSection);

                            // Answer Section
                            const answerArea = document.createElement('textarea');
                            answerArea.id = `answer-${idx}`;
                            answerArea.classList.add('interview-answer-area');
                            answerArea.placeholder = 'Type your answer here...';
                            qaCard.appendChild(answerArea);

                            interviewChat.appendChild(qaCard);
                            qaPairs.push({ question: q.question, elementId: `answer-${idx}` });
                        });

                        const submitBtn = document.createElement('button');
                        submitBtn.textContent = 'Submit Interview';
                        submitBtn.classList.add('submit-quiz-btn');
                        submitBtn.style.marginTop = '1rem';

                        submitBtn.onclick = async () => {
                            submitBtn.disabled = true;
                            submitBtn.textContent = 'Evaluating...';

                            const answers = qaPairs.map(item => ({
                                question: item.question,
                                answer: document.getElementById(item.elementId).value
                            }));

                            try {
                                const evalResponse = await fetch('/evaluate_interview', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ qa_pairs: answers, job_role: jobRole })
                                });
                                const evalData = await evalResponse.json();

                                const resultDiv = document.createElement('div');
                                resultDiv.classList.add('quiz-score');
                                resultDiv.style.textAlign = 'left';

                                let feedbackHtml = `<h3>Interview Feedback</h3>
                                    <p style="margin-bottom: 1rem;">${evalData.overall_feedback}</p>
                                    <hr style="border-color: var(--border-color); margin: 1rem 0;">`;

                                if (evalData.evaluations) {
                                    evalData.evaluations.forEach(ev => {
                                        feedbackHtml += `
                                            <div class="interview-feedback-item">
                                                <span class="feedback-rating">Q${ev.question_index + 1} Rating: ${ev.rating}/10</span>
                                                <p style="font-size: 0.95rem; color: var(--text-secondary);">${ev.feedback}</p>
                                            </div>
                                        `;
                                    });
                                }

                                resultDiv.innerHTML = feedbackHtml;
                                interviewChat.appendChild(resultDiv);
                                resultDiv.scrollIntoView({ behavior: 'smooth' });
                                submitBtn.textContent = 'Interview Completed';

                            } catch (err) {
                                console.error('Error evaluating interview:', err);
                                alert('Failed to submit interview.');
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Submit Interview';
                            }
                        };

                        interviewChat.appendChild(submitBtn);

                    } else {
                        interviewChat.innerHTML = `<p style="color: #ef4444;">Error: ${data.error}</p>`;
                    }
                } catch (error) {
                    console.error('Error generating interview:', error);
                    interviewChat.innerHTML = '<p style="color: #ef4444;">Failed to generate questions.</p>';
                }
            };
        }
    }

    function displayQuestions(questions, container, topic = 'General') {
        container.innerHTML = '';
        const userAnswers = {};

        questions.forEach((q, idx) => {
            const qCard = document.createElement('div');
            qCard.classList.add('question-card');

            const qText = document.createElement('div');
            qText.classList.add('question-text');
            qText.textContent = `${idx + 1}. ${q.question}`;
            qCard.appendChild(qText);

            if (q.options) {
                const optionsDiv = document.createElement('div');
                optionsDiv.classList.add('answer-options');

                q.options.forEach((option, optIdx) => {
                    const optDiv = document.createElement('div');
                    optDiv.classList.add('answer-option');

                    const radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.name = `question-${idx}`;
                    radio.value = optIdx;
                    radio.id = `q${idx}-opt${optIdx}`;

                    const label = document.createElement('label');
                    label.htmlFor = `q${idx}-opt${optIdx}`;
                    label.textContent = option;

                    radio.addEventListener('change', () => {
                        userAnswers[idx] = optIdx;
                    });

                    optDiv.appendChild(radio);
                    optDiv.appendChild(label);
                    optionsDiv.appendChild(optDiv);
                });

                qCard.appendChild(optionsDiv);
            }

            container.appendChild(qCard);
        });

        const submitBtn = document.createElement('button');
        submitBtn.textContent = 'Submit Quiz';
        submitBtn.classList.add('submit-quiz-btn');

        submitBtn.onclick = async () => {
            let score = 0;

            // Disable all inputs and show feedback
            questions.forEach((q, idx) => {
                const selectedOptIdx = userAnswers[idx];
                const correctOptIdx = q.correct;

                // Disable inputs
                const radios = document.getElementsByName(`question-${idx}`);
                radios.forEach(radio => radio.disabled = true);

                if (selectedOptIdx === correctOptIdx) {
                    score++;
                    // Highlight correct selection
                    if (selectedOptIdx !== undefined) {
                        const selectedLabel = document.querySelector(`label[for="q${idx}-opt${selectedOptIdx}"]`);
                        if (selectedLabel) selectedLabel.parentElement.classList.add('correct');
                    }
                } else {
                    // Highlight incorrect selection
                    if (selectedOptIdx !== undefined) {
                        const selectedLabel = document.querySelector(`label[for="q${idx}-opt${selectedOptIdx}"]`);
                        if (selectedLabel) selectedLabel.parentElement.classList.add('incorrect');
                    }

                    // Highlight correct answer
                    const correctLabel = document.querySelector(`label[for="q${idx}-opt${correctOptIdx}"]`);
                    if (correctLabel) correctLabel.parentElement.classList.add('correct-answer');
                }
            });

            const percentage = Math.round((score / questions.length) * 100);

            const resultDiv = document.createElement('div');
            resultDiv.classList.add('quiz-score');
            resultDiv.innerHTML = `
                <h3>Quiz Complete!</h3>
                <p>You scored <strong>${score}/${questions.length}</strong> (${percentage}%)</p>
            `;

            // Insert result at top
            container.insertBefore(resultDiv, container.firstChild);
            resultDiv.scrollIntoView({ behavior: 'smooth' });

            // Remove submit button
            submitBtn.remove();

            try {
                await fetch('/submit_quiz_result', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        topic: topic,
                        score: score,
                        total: questions.length
                    })
                });
            } catch (error) {
                console.error('Error saving quiz result:', error);
            }
        };

        container.appendChild(submitBtn);
    }

    async function loadManualTasks() {
        if (!manualTasksList) return;

        try {
            const response = await fetch('/manual_tasks');
            const tasks = await response.json();

            manualTasksList.innerHTML = '';

            tasks.forEach(task => {
                const taskItem = document.createElement('div');
                taskItem.classList.add('task-item');
                if (task.completed) {
                    taskItem.classList.add('completed');
                }

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.checked = task.completed;
                checkbox.onchange = () => toggleTask(task.id);

                const taskText = document.createElement('span');
                taskText.textContent = task.text;

                const deleteBtn = document.createElement('button');
                deleteBtn.classList.add('delete-task-btn');
                deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                deleteBtn.onclick = () => deleteTask(task.id);

                taskItem.appendChild(checkbox);
                taskItem.appendChild(taskText);
                taskItem.appendChild(deleteBtn);
                manualTasksList.appendChild(taskItem);
            });
        } catch (error) {
            console.error('Error loading tasks:', error);
        }
    }

    async function addManualTask() {
        const text = newTaskInput.value.trim();
        if (!text) return;

        try {
            await fetch('/manual_tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });

            newTaskInput.value = '';
            loadManualTasks();
        } catch (error) {
            console.error('Error adding task:', error);
        }
    }

    async function toggleTask(taskId) {
        try {
            await fetch(`/manual_tasks/${taskId}/toggle`, {
                method: 'PUT'
            });
            loadManualTasks();
        } catch (error) {
            console.error('Error toggling task:', error);
        }
    }

    async function deleteTask(taskId) {
        try {
            await fetch(`/manual_tasks/${taskId}`, {
                method: 'DELETE'
            });
            loadManualTasks();
        } catch (error) {
            console.error('Error deleting task:', error);
        }
    }
});

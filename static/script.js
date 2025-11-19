document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const chatMessages = document.getElementById('chat-messages');
    const eventsList = document.getElementById('events-list');
    const recentChatsList = document.getElementById('recent-chats-list');
    const newChatBtn = document.getElementById('new-chat-btn');

    let currentSessionId = null;

    // Initial load
    fetchEvents();
    loadSessions();

    // Event Listeners
    if (newChatBtn) {
        newChatBtn.addEventListener('click', createNewChat);
    }

    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = userInput.value.trim();
            if (!message) return;

            // Add user message
            addMessage(message, 'user');
            userInput.value = '';

            // Show loading
            addMessage('Thinking...', 'agent', true);

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message,
                        session_id: currentSessionId
                    })
                });
                const data = await response.json();

                // Remove loading message
                const loadingMsg = document.querySelector('.loading-msg');
                if (loadingMsg) loadingMsg.remove();

                if (data.error) {
                    addMessage('Error: ' + data.error, 'agent');
                } else {
                    // Update session ID if it was a new chat
                    if (data.session_id && data.session_id !== currentSessionId) {
                        currentSessionId = data.session_id;
                        loadSessions(); // Refresh list to show new title
                    } else if (data.title) {
                        // Refresh list to update title if changed
                        loadSessions();
                    }

                    if (data.response) {
                        addMessage(data.response, 'agent');
                    }

                    if (data.events_updated) {
                        fetchEvents();
                        addMessage("I've updated the schedule.", 'agent');
                    }
                }
            } catch (error) {
                console.error('Error:', error);
                const loadingMsg = document.querySelector('.loading-msg');
                if (loadingMsg) loadingMsg.remove();
                addMessage('Sorry, something went wrong. Please try again.', 'agent');
            }
        });
    }

    async function loadSessions() {
        if (!recentChatsList) return;
        try {
            const response = await fetch('/sessions');
            const sessions = await response.json();

            recentChatsList.innerHTML = '';

            if (sessions.length === 0) {
                recentChatsList.innerHTML = '<div class="no-events">No recent chats</div>';
                return;
            }

            sessions.forEach(session => {
                const item = document.createElement('div');
                item.classList.add('recent-chat-item');
                if (session.id === currentSessionId) {
                    item.classList.add('active');
                }

                // Create content wrapper
                const content = document.createElement('div');
                content.classList.add('recent-chat-item-content');
                content.innerHTML = `<i class="fa-regular fa-comment"></i> ${session.title}`;

                // Create delete button
                const deleteBtn = document.createElement('button');
                deleteBtn.classList.add('delete-chat-btn');
                deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                deleteBtn.title = "Delete Chat";
                deleteBtn.onclick = (e) => {
                    e.stopPropagation(); // Prevent triggering loadSession
                    deleteSession(session.id);
                };

                item.appendChild(content);
                item.appendChild(deleteBtn);

                item.onclick = () => loadSession(session.id);
                recentChatsList.appendChild(item);
            });
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    }

    async function deleteSession(sessionId) {
        if (!confirm('Are you sure you want to delete this chat?')) return;

        try {
            const response = await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
            const data = await response.json();

            if (data.success) {
                // If deleted active session, switch to new chat or another session
                if (sessionId === currentSessionId) {
                    createNewChat();
                } else {
                    loadSessions();
                }
            } else {
                alert('Failed to delete chat');
            }
        } catch (error) {
            console.error('Error deleting session:', error);
            alert('Error deleting chat');
        }
    }

    async function createNewChat() {
        try {
            const response = await fetch('/new_chat', { method: 'POST' });
            const data = await response.json();
            currentSessionId = data.id;

            // Clear chat window
            if (chatMessages) {
                chatMessages.innerHTML = '';
                // Add welcome message
                addMessage("Hello! I'm your StudyCopilot. How can I help you today?", 'agent');
            }

            loadSessions();
        } catch (error) {
            console.error('Error creating new chat:', error);
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
                    // Map 'model' role to 'agent' for display
                    const sender = msg.role === 'model' ? 'agent' : 'user';
                    addMessage(msg.content, sender);
                });
            }

            loadSessions(); // Update active state
        } catch (error) {
            console.error('Error loading session:', error);
        }
    }

    function addMessage(text, sender, isLoading = false) {
        if (!chatMessages) return;

        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender);
        if (isLoading) msgDiv.classList.add('loading-msg');

        const avatarDiv = document.createElement('div');
        avatarDiv.classList.add('avatar');
        avatarDiv.innerHTML = sender === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.classList.add('content');

        // Simple Markdown parsing (bold, lists)
        let formattedText = text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold
            .replace(/\n/g, '<br>'); // Newlines

        contentDiv.innerHTML = formattedText;

        msgDiv.appendChild(avatarDiv);
        msgDiv.appendChild(contentDiv);

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function fetchEvents() {
        if (!eventsList) return;

        try {
            const response = await fetch('/events');
            const data = await response.json();

            eventsList.innerHTML = '';

            if (data.events && data.events.length > 0) {
                data.events.forEach(event => {
                    // Format date
                    const startDate = new Date(event.start.dateTime || event.start.date);
                    const timeStr = startDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    const dateStr = startDate.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });

                    // Create Event Card (Schedule)
                    const eventCard = document.createElement('div');
                    eventCard.classList.add('event-card');
                    eventCard.innerHTML = `
                        <div class="event-title">${event.summary}</div>
                        <div class="event-time"><i class="fa-regular fa-clock"></i> ${dateStr} • ${timeStr}</div>
                    `;
                    eventsList.appendChild(eventCard);
                });
            } else {
                eventsList.innerHTML = '<div class="no-events">No upcoming events.</div>';
            }
        } catch (error) {
            console.error('Error fetching events:', error);
            eventsList.innerHTML = '<div class="error-events">Failed to load.</div>';
        }
    }
});

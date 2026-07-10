// Chatbot JavaScript

let conversationId = null;
let autoPromptTimer = null;

// DOM Elements
const chatBubble = document.getElementById('chatbot-bubble');
const chatWindow = document.getElementById('chatbot-window');
const chatPrompt = document.getElementById('chatbot-prompt');
const closeChat = document.getElementById('close-chat');
const dismissPrompt = document.getElementById('dismiss-prompt');
const chatInput = document.getElementById('chat-input');
const sendButton = document.getElementById('send-message');
const chatMessages = document.getElementById('chat-messages');
const typingIndicator = document.getElementById('typing-indicator');

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Check if user dismissed auto-prompts
    const promptDismissed = localStorage.getItem('chatbot-prompt-dismissed');
    
    if (!promptDismissed) {
        startAutoPromptTimer();
    }
    
    // Load conversation history
    loadConversationHistory();
});

// Event Listeners
chatBubble.addEventListener('click', toggleChatWindow);
closeChat.addEventListener('click', toggleChatWindow);
dismissPrompt.addEventListener('click', dismissAutoPrompt);
sendButton.addEventListener('click', sendMessage);

chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Auto-resize textarea
chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 100) + 'px';
});

// Toggle Chat Window
function toggleChatWindow() {
    const isHidden = chatWindow.classList.contains('hidden');
    
    if (isHidden) {
        chatWindow.classList.remove('hidden');
        chatPrompt.classList.add('hidden');
        chatInput.focus();
        
        // Stop auto-prompt timer when chat is open
        clearTimeout(autoPromptTimer);
    } else {
        chatWindow.classList.add('hidden');
        
        // Restart auto-prompt timer when chat is closed
        const promptDismissed = localStorage.getItem('chatbot-prompt-dismissed');
        if (!promptDismissed) {
            startAutoPromptTimer();
        }
    }
}

// Auto-prompt Timer (every 3 minutes)
function startAutoPromptTimer() {
    autoPromptTimer = setTimeout(function() {
        // Only show if chat window is closed
        if (chatWindow.classList.contains('hidden')) {
            chatPrompt.classList.remove('hidden');
        }
        
        // Set next timer
        startAutoPromptTimer();
    }, 180000); // 3 minutes = 180,000 milliseconds
}

// Dismiss Auto-prompt
function dismissAutoPrompt() {
    chatPrompt.classList.add('hidden');
    localStorage.setItem('chatbot-prompt-dismissed', 'true');
    clearTimeout(autoPromptTimer);
}

// Get JWT token from localStorage
function getAuthToken() {
    return localStorage.getItem('access_token');
}

// Send Message
async function sendMessage() {
    const message = chatInput.value.trim();
    
    if (!message) return;
    
    // Get JWT token
    const token = getAuthToken();
    
    if (!token) {
        appendMessage('assistant', 'Please log in to use the chatbot.');
        return;
    }
    
    // Display user message
    appendMessage('user', message);
    
    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    
    // Disable send button
    sendButton.disabled = true;
    
    // Show typing indicator
    typingIndicator.classList.remove('hidden');
    
    // Scroll to bottom
    scrollToBottom();
    
    try {
        // Send to backend
        const response = await fetch('/api/chatbot/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ 
                message: message,
                conversation_id: conversationId
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Store conversation ID
            conversationId = data.conversation_id;
            
            // Hide typing indicator
            typingIndicator.classList.add('hidden');
            
            // Display assistant response
            appendMessage('assistant', data.reply);
        } else {
            throw new Error(data.error || 'Failed to send message');
        }
        
    } catch (error) {
        console.error('Error:', error);
        
        // Hide typing indicator
        typingIndicator.classList.add('hidden');
        
        // Show error message
        appendMessage('assistant', 'Sorry, I encountered an error. Please try again.');
    }
    
    // Re-enable send button
    sendButton.disabled = false;
    chatInput.focus();
}

// Append Message to Chat
function appendMessage(role, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Convert markdown-style formatting if needed
    contentDiv.innerHTML = formatMessage(text);
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    scrollToBottom();
}

// Format Message (basic markdown support)
function formatMessage(text) {
    // Replace line breaks
    text = text.replace(/\n/g, '<br>');
    
    // Bold text
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Bullet points
    text = text.replace(/^- (.+)$/gm, '<li>$1</li>');
    if (text.includes('<li>')) {
        text = text.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    }
    
    return text;
}

// Scroll to Bottom
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Load Conversation History
async function loadConversationHistory() {
    try {
        const token = getAuthToken();
        
        if (!token) {
            console.log('No token found, skipping history load');
            return;
        }
        
        const response = await fetch('/api/chatbot/history', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            
            if (data.conversation_id) {
                conversationId = data.conversation_id;
            }
            
            // Clear default welcome message if history exists
            if (data.messages && data.messages.length > 0) {
                chatMessages.innerHTML = '';
                
                // Display all messages
                data.messages.forEach(msg => {
                    appendMessage(msg.role, msg.message);
                });
            }
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}
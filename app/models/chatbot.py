from app.extensions import db
from datetime import datetime

class ChatbotConversation(db.Model):
    __tablename__ = 'chatbot_conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    messages = db.relationship('ChatbotMessage', backref='conversation', lazy=True, cascade='all, delete-orphan')
    user = db.relationship('User', backref='chatbot_conversations')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat()
        }


class ChatbotMessage(db.Model):
    __tablename__ = 'chatbot_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('chatbot_conversations.id', ondelete='CASCADE'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }
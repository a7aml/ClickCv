from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.chatbot import ChatbotConversation, ChatbotMessage
from app.services.chatbot_service import ChatbotService
from app.extensions import db

chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/api/chatbot')

@chatbot_bp.route('/message', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message to the chatbot and get AI response"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get or create conversation
        if conversation_id:
            conversation = ChatbotConversation.query.filter_by(
                id=conversation_id, 
                user_id=user_id
            ).first()
            
            if not conversation:
                return jsonify({'error': 'Conversation not found'}), 404
        else:
            # Create new conversation
            conversation = ChatbotConversation(user_id=user_id)
            db.session.add(conversation)
            db.session.commit()
        
        # Save user message
        user_msg = ChatbotMessage(
            conversation_id=conversation.id,
            role='user',
            message=user_message
        )
        db.session.add(user_msg)
        db.session.commit()
        
        # Get AI response
        chatbot_service = ChatbotService()
        ai_response = chatbot_service.get_ai_response(
            user_id=user_id,
            conversation_id=conversation.id,
            user_message=user_message
        )
        
        # Save assistant message
        assistant_msg = ChatbotMessage(
            conversation_id=conversation.id,
            role='assistant',
            message=ai_response
        )
        db.session.add(assistant_msg)
        db.session.commit()
        
        return jsonify({
            'conversation_id': conversation.id,
            'reply': ai_response
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in send_message: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@chatbot_bp.route('/history', methods=['GET'])
@jwt_required()
def get_history():
    """Get conversation history for current user"""
    try:
        user_id = get_jwt_identity()
        
        # Get latest conversation
        conversation = ChatbotConversation.query.filter_by(
            user_id=user_id
        ).order_by(ChatbotConversation.created_at.desc()).first()
        
        if not conversation:
            return jsonify({
                'conversation_id': None,
                'messages': []
            }), 200
        
        # Get all messages
        messages = ChatbotMessage.query.filter_by(
            conversation_id=conversation.id
        ).order_by(ChatbotMessage.timestamp.asc()).all()
        
        return jsonify({
            'conversation_id': conversation.id,
            'messages': [msg.to_dict() for msg in messages]
        }), 200
        
    except Exception as e:
        print(f"Error in get_history: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
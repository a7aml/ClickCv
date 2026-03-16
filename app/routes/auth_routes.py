from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from app.services.auth_service import register_user, login_user

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# -------------------------
# REGISTER
# -------------------------
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    # Basic validation
    if not name or not email or not password:
        return jsonify({'error': 'Name, email and password are required.'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400

    user, error = register_user(name, email, password)

    if error:
        return jsonify({'error': error}), 409

    # Generate JWT token immediately after register
    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'message': 'Account created successfully.',
        'access_token': access_token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email
        }
    }), 201


# -------------------------
# LOGIN
# -------------------------
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    user, error = login_user(email, password)

    if error:
        return jsonify({'error': error}), 401

    # Generate JWT token
    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'message': 'Login successful.',
        'access_token': access_token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email
        }
    }), 200


# -------------------------
# LOGOUT
# -------------------------
@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # JWT is stateless — logout is handled on the frontend by deleting the token
    return jsonify({'message': 'Logged out successfully.'}), 200


# -------------------------
# GET CURRENT USER (useful for frontend to verify token)
# -------------------------
@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    return jsonify({'user_id': user_id}), 200
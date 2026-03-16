from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('LandingPage.html')


@main_bp.route('/signin')
def signin():
    return render_template('SignIn.html')


@main_bp.route('/signup')
def signup():
    return render_template('SignUp.html')


@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@main_bp.route('/profile')
def profile():
    return render_template('profile.html')
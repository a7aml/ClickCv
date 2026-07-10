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

@main_bp.route('/history')
def history():
    return render_template('history.html')

@main_bp.route('/rebuild')
def rebuild():
    return render_template('rebuild.html')

@main_bp.route('/compare-cv')
def compare():
    return render_template('compare.html')



@main_bp.route('/build-cv')
def build():
    return render_template('build.html')

@main_bp.route('/find-job')
def find_job():
    return render_template('find_job.html')

@main_bp.route('/cover-letter')
def cover_letter():
    return render_template('cover_letter.html')

@main_bp.route('/auth/google/exchange')
def google_exchange():
    return render_template('google_exchange.html')

@main_bp.route('/admin')
def admin_panel():
    return render_template('AdminPanel.html')

@main_bp.route('/cv-builder/generate')
def cv_generate_page():
    return render_template('cv_generate.html')

@main_bp.route('/cv-builder/draft/<int:draft_id>/preview')
def cv_preview_page(draft_id):
    return render_template('cv_preview.html', draft_id=draft_id)
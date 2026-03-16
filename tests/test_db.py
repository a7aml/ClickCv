import sys
import os

# Add the root CLICKCV folder to path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db


def test_db_connection():
    app = create_app()

    with app.app_context():
        try:
            db.engine.connect()
            print("✅ Database connected successfully!")
            print(f"📦 Connected to: {db.engine.url}")
        except Exception as e:
            print("❌ Database connection failed!")
            print(f"🔴 Error: {e}")


if __name__ == '__main__':
    test_db_connection()
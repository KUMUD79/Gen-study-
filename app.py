# app.py
from flask import Flask
from flask_login import LoginManager
import os
from services.models import init_db, get_user_by_id, User
from services.routes import routes_bp
from dotenv import load_dotenv, find_dotenv

# --- Load .env so all keys become available ---
load_dotenv(find_dotenv())

def create_app():
    app = Flask(__name__)

    # --- Flask configuration ---
    app.config.from_pyfile('config.py')
    app.secret_key = os.getenv("SECRET_KEY", "fallback-key")

    # --- Initialize SQLite database ---
    init_db()

    # --- Flask-Login setup ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'routes.login'
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        user_data = get_user_by_id(user_id)
        if user_data:
            return User(user_data)
        return None

    # --- Register Blueprints ---
    app.register_blueprint(routes_bp)

    # --- Debug check ---
    print("✅ GEMINI_API_KEY loaded:", bool(os.getenv("GEMINI_API_KEY")))
    print("✅ INTERVIEW_KEY loaded:", bool(os.getenv("INTERVIEW_KEY")))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

# services/routes.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
import json, traceback
from io import BytesIO
# CRITICAL FIX: PyMuPDF imports MUST be inside the function or globally isolated.
# We import them here, and the ATS function will use them.
try:
    import fitz
except ImportError:
    fitz = None
    print("WARNING: PyMuPDF (fitz) not installed. ATS functionality is disabled.")

from services.models import get_db, get_user_by_username, create_user, User
from services.llm_service import (
    generate_notes,
    generate_quiz,
    analyze_resume_ats,
    critique_interview_answer,
    generate_interview_questions, 
    STT_API_URL
)

routes_bp = Blueprint("routes", __name__)


# --- AUTH & CORE NAVIGATION (Retained) ---
@routes_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("routes.home"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_data = get_user_by_username(username)
        if not user_data:
            flash("Invalid credentials", "danger")
            return redirect(url_for("routes.login"))
        user = User(user_data)
        if not user.check_password(password):
            flash("Invalid credentials", "danger")
            return redirect(url_for("routes.login"))
        login_user(user)
        flash(f"Welcome, {user.username}!", "success")
        return redirect(url_for("routes.home"))
    return render_template("auth/login.html")


@routes_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("routes.home"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")
        if get_user_by_username(username):
            flash("Username already exists", "warning")
            return redirect(url_for("routes.register"))
        if create_user(username, password, role):
            flash("Registration successful!", "success")
            return redirect(url_for("routes.login"))
        flash("Registration failed.", "danger")
    return render_template("auth/register.html")


@routes_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("routes.login"))


@routes_bp.route("/")
@login_required
def home():
    if current_user.role == "student":
        return redirect(url_for("routes.student_dashboard"))
    elif current_user.role == "teacher":
        return redirect(url_for("routes.teacher_dashboard"))
    flash("Invalid role.", "danger")
    return redirect(url_for("routes.logout"))


@routes_bp.route("/student/dashboard")
@login_required
def student_dashboard():
    return render_template("student/student_dashboard.html")


@routes_bp.route("/teacher/dashboard")
@login_required
def teacher_dashboard():
    conn = get_db()
    data = conn.execute("""
        SELECT u.username, u.xp, MAX(s.score_percentage) as last_score,
               COUNT(s.id) as quiz_count, MAX(s.timestamp) as last_active
        FROM users u
        LEFT JOIN scores s ON u.id = s.user_id
        WHERE u.role = 'student'
        GROUP BY u.id
        ORDER BY u.xp DESC
    """).fetchall()
    conn.close()
    return render_template("teacher/teacher_dashboard.html", students=data)


@routes_bp.route('/student/quiz/practice')
@login_required
def quiz_practice():
    """Renders the dedicated Quiz Practice page."""
    return render_template('student/quiz_practice.html')


@routes_bp.route('/student/interview')
@login_required
def interview_prep():
    """Renders the Placement Prep page."""
    return render_template('student/interview.html')


# ---------------------- LLM API ENDPOINTS ----------------------

@routes_bp.route("/api/notes", methods=["POST"])
@login_required
def api_generate_notes():
    try:
        data = request.get_json()
        topic = data.get("topic", "")
        result = generate_notes(topic)
        if result.get("error"):
            return jsonify({"error": result["notes"]}), 500
        return jsonify({"notes": result["notes"]})
    except Exception as e:
        print("❌ Notes Error:", e)
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/api/generate-quiz", methods=["POST"])
@login_required
def api_generate_quiz():
    try:
        data = request.get_json()
        content_text = data.get("content_text", "")
        topic = data.get("topic", "General")

        result = generate_quiz(content_text, topic) 
        quiz_json_str = result.get("quiz_json", "{}")

        try:
            quiz_data = json.loads(quiz_json_str)
        except Exception:
            quiz_data = {"questions": []}

        return jsonify({"quiz": quiz_data, "topic": topic})
    except Exception as e:
        print("❌ Quiz Error:", e, traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ---------------------- SCORE SAVE ----------------------
@routes_bp.route("/api/submit-score", methods=["POST"])
@login_required
def api_submit_score():
    try:
        data = request.get_json()
        topic = data.get("topic", "Unknown")
        score_percentage = float(data.get("score_percentage", 0))
        xp_earned = int(data.get("xp_earned", 0))

        conn = get_db()
        conn.execute(
            "INSERT INTO scores (user_id, topic, score_percentage) VALUES (?, ?, ?)",
            (current_user.id, topic, score_percentage),
        )
        conn.execute("UPDATE users SET xp = xp + ? WHERE id = ?", (xp_earned, current_user.id))
        conn.commit()

        new_xp = conn.execute("SELECT xp FROM users WHERE id = ?", (current_user.id,)).fetchone()["xp"]
        conn.close()

        return jsonify({"message": "Saved", "new_xp": new_xp})
    except Exception as e:
        print("⚠️ Score Save Error:", e)
        return jsonify({"error": "Failed to save score"}), 500


# ---------------------- PLACEMENT PREP ENDPOINTS ----------------------

@routes_bp.route("/api/placement/ats/score", methods=["POST"])
@login_required
def api_placement_ats_score():
    try:
        if "resume_file" not in request.files:
            return jsonify({"error": "No resume file uploaded"}), 400

        resume_file = request.files["resume_file"]
        
        # Check if PyMuPDF is available
        if fitz is None:
            return jsonify({"error": "PDF dependency (PyMuPDF/fitz) not installed on server."}), 500

        # PDF to Text Conversion
        file_bytes = resume_file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        resume_text = "".join(page.get_text() + "\n" for page in doc)
        doc.close()

        if not resume_text.strip():
            return jsonify({"error": "Could not extract text from PDF."}), 400

        result = analyze_resume_ats(resume_text)
        if result.get("error"):
            return jsonify({"error": result["suggestions"][0]}), 500

        return jsonify({"score": result["score"], "suggestions": result["suggestions"]})
    except Exception as e:
        print("❌ ATS Error:", e)
        return jsonify({"error": str(e)}), 500


@routes_bp.route('/api/placement/mock/start', methods=['POST'])
@login_required
def api_placement_mock_start():
    try:
        data = request.get_json()
        jd_text = data.get('jd_text')
        
        if not jd_text or len(jd_text) < 50:
            return jsonify({"error": "Job Description missing or too short."}), 400
            
        result = generate_interview_questions(jd_text)
        
        if result.get('error'):
            return jsonify({"error": result['error']}), 500
            
        return jsonify({"questions": result['questions']}), 200
    except Exception as e:
        print(f"❌ Mock Start Error: {e}")
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/api/placement/mock/assess", methods=["POST"])
@login_required
def api_placement_mock_assess():
    try:
        # Note: Frontend sends FormData for this route
        if "audio_file" not in request.files or not request.form.get("question_text"):
            return jsonify({"error": "Missing audio or question."}), 400

        question_text = request.form.get("question_text")
        criteria = request.form.get("criteria", "Relevance, clarity, confidence")
        
        # MOCK TRANSCRIPT (REPLACE WITH STT API CALL FOR PRODUCTION)
        transcript = "This is a mock transcription (STT placeholder). The user answered about technical skills."

        result = critique_interview_answer(question_text, transcript, criteria)
        if result.get("error"):
            return jsonify({"error": result["critique"]}), 500

        return jsonify({"transcript": transcript, "feedback": result["critique"]})
    except Exception as e:
        print("❌ Mock Interview Error:", e)
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
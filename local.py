# offline_model.py
# -------------------------------------------------------------
# Simulated Offline LLM Module - EduAssist-Lite
# -------------------------------------------------------------
# Purpose: Acts as a fallback AI model when Gemini API is not reachable.
# Based on small open-source transformers (GPT-Neo, LLaMA-3-lite)
# -------------------------------------------------------------

from transformers import pipeline
import random

# Load a small open-source model (for demo, use GPT-Neo 125M)
# This runs locally and doesn’t need an API key.
try:
    generator = pipeline("text-generation", model="EleutherAI/gpt-neo-125M")
except Exception as e:
    print(f"[Offline Model] ⚠️ Warning: Model not loaded. ({e})")
    generator = None


def offline_generate_notes(topic: str):
    """
    Generates structured notes for a topic when offline.
    """
    if not generator:
        return f"[Offline Fallback] Notes for {topic}: Study the key concepts manually."

    prompt = f"Write well-structured study notes about {topic} in 5 bullet points."
    response = generator(prompt, max_length=200, do_sample=True)
    return response[0]["generated_text"]


def offline_generate_quiz(topic: str):
    """
    Creates 5 simple MCQs for a topic when offline.
    """
    questions = []
    sample_options = ["A", "B", "C", "D"]

    for i in range(1, 6):
        questions.append({
            "id": i,
            "question": f"What is a key concept of {topic} related to part {i}?",
            "options": [f"Option {opt}" for opt in sample_options],
            "answer": random.choice(sample_options)
        })

    return {"questions": questions}


def offline_analyze_resume(resume_text: str):
    """
    Simulates ATS scoring offline.
    """
    score = random.randint(60, 95)
    suggestions = [
        "Add measurable achievements.",
        "Include more relevant keywords.",
        "Improve formatting for ATS readability."
    ]
    return {"score": score, "suggestions": suggestions}


def offline_interview_feedback(answer_text: str):
    """
    Provides mock interview feedback offline.
    """
    feedback = {
        "ScoreSummary": f"Answer clarity: {random.randint(70, 95)}%",
        "ActionableSuggestion": "Try giving more structured answers using the STAR method."
    }
    return feedback


# Example (for testing)
if __name__ == "__main__":
    print("📘 Notes Example:\n", offline_generate_notes("Machine Learning"))
    print("🧩 Quiz Example:\n", offline_generate_quiz("Python Basics"))
    print("📄 Resume ATS Example:\n", offline_analyze_resume("Experienced data analyst with SQL skills."))
    print("🎤 Interview Feedback Example:\n", offline_interview_feedback("I worked on data visualization using Power BI."))

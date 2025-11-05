# services/llm_service.py

import json
import os
import re
from google import genai
from google.genai.errors import APIError
import requests 
# NOTE: Removed fitz import here, as it's now in routes.py

# --- Global Client Initialization (Dual Key Strategy) ---
QUIZ_KEY = os.getenv("GEMINI_API_KEY") 
PLACEMENT_KEY = os.getenv("INTERVIEW_KEY") 
STT_API_URL = os.getenv("EXTERNAL_STT_URL", "http://mock-stt-api.com/transcribe")

quiz_client = None
placement_client = None

def initialize_clients():
    """Initializes the two required Gemini clients."""
    global quiz_client, placement_client
    
    if QUIZ_KEY and quiz_client is None:
        try:
            quiz_client = genai.Client(api_key=QUIZ_KEY)
            print("✅ Quiz/Notes client (GEMINI_API_KEY) initialized.")
        except Exception as e:
            print(f"Error initializing Quiz client: {e}")
            
    if PLACEMENT_KEY and placement_client is None:
        try:
            placement_client = genai.Client(api_key=PLACEMENT_KEY)
            print("✅ Placement/Interview client (INTERVIEW_KEY) initialized.")
        except Exception as e:
            print(f"Error initializing Placement client: {e}")

initialize_clients()

def get_client(feature_type):
    """Returns the correct client instance based on feature type."""
    if feature_type == 'placement':
        return placement_client
    return quiz_client

# --- CORE LOGIC IMPLEMENTATIONS ---

def _try_parse_quiz_text(text):
    """Robustly searches for and parses the quiz JSON array structure."""
    text = (text or "").strip()
    if not text: return None
    
    match_array = re.search(r"\[.*\]", text, re.DOTALL)
    match_dict = re.search(r"\{.*\}", text, re.DOTALL)

    if match_array:
        try:
            parsed = json.loads(match_array.group(0).strip())
            if isinstance(parsed, list): return {"questions": parsed}
        except Exception:
            pass

    if match_dict:
        try:
            parsed = json.loads(match_dict.group(0).strip())
            if "questions" in parsed and isinstance(parsed["questions"], list): return parsed
        except Exception:
            pass
    
    return None

def _robust_json_load(text, expected_keys):
    """Helper to clean common LLM output noise before parsing JSON (Used for Placement Prep)."""
    text = text.strip()
    cleaned_text = text.replace("```json", "").replace("```", "").strip()
    if cleaned_text.startswith('json '): cleaned_text = cleaned_text[5:].strip()

    try:
        result_json = json.loads(cleaned_text)
        if all(key in result_json for key in expected_keys):
            return result_json
        raise ValueError("JSON structure missing expected keys.")
    except Exception as e:
        return {"error": f"JSONDecodeError or Structure Failure. Raw: {text[:150]}", "raw": text}


# 1. GENERATE NOTES
def generate_notes(topic_text):
    """Generates structured study notes using the Quiz/Notes client."""
    client = get_client('quiz') 
    if not client: return {"notes": "Backend Error: Quiz/Notes client not initialized.", "error": True}
    
    prompt = (
        f"You are an expert technical instructor. Generate detailed, structured study notes "
        f"in Markdown format (with headings, bolding, and bullet points) for the following topic. "
        f"Focus on clarity, concise explanations, and key concepts. **Begin your response with the phrase '---NOTES-START---'.**"
        f"\n\nTopic: {topic_text}"
    )
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return {"notes": response.text, "error": False}
    except APIError as e: return {"notes": "Gemini Service Failed: API connection error.", "error": True}
    except Exception as e: return {"notes": "General Server Error: Could not process request.", "error": True}

# 2. GENERATE QUIZ
def generate_quiz(content_text, topic_text):
    """Generates a structured quiz (MCQs) for a topic based on content."""
    client = get_client('quiz') 
    if not client: return {"quiz_json": json.dumps({"questions": []}), "error": True}
    
    prompt = (
        "Analyze the content provided below. Create 5 multiple-choice questions (MCQs) based ONLY on this content. "
        "The quiz topic is: "
        f"{topic_text}\n"
        "Return ONLY valid JSON (an array of question objects). DO NOT include any text, headers, or markdown outside the array.\n\n"
        f"--- START OF CONTENT ---\n{content_text}\n--- END OF CONTENT ---"
    )
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        normalized = _try_parse_quiz_text(response.text)
        if normalized: return {"quiz_json": json.dumps(normalized), "error": False}
        mock_quiz = {"questions": [{"id": 1, "question": "Fallback Q1: Could not parse AI output", "options": ["A", "B", "C", "D"], "answer": "A"}]}
        return {"quiz_json": json.dumps(mock_quiz), "error": True}
    except APIError as e: return {"quiz_json": json.dumps({"questions": [{"id": 1, "question": "Mock Q1: API Error occurred", "options": ["Yes","No","Maybe","Retry"], "answer": "Yes"}]}), "error": True}
    except Exception as e: return {"quiz_json": json.dumps({"questions": [{"id": 1, "question": "Mock Q1: General Error", "options": ["Yes","No","Maybe","Retry"], "answer": "Yes"}]}), "error": True}


# 3. Used by /api/placement/ats/score
def analyze_resume_ats(resume_text):
    """ATS scoring and suggestion generation using the Placement Client (INTERVIEW_KEY)."""
    client = get_client('placement')
    if not client:
        return {"score": 0, "suggestions": ["Backend Error: Placement client not initialized."], "error": True}
        
    prompt = ("You are an expert Applicant Tracking System (ATS) analyst. Analyze the resume provided "
        "for an Entry-Level Data Analyst role. Evaluate it against 3 criteria: Technical Keyword Match, "
        "Action Verb Usage, and Quantifiable Results. "
        "Return ONLY a JSON object with two keys: 'score' (an integer 0-100) and 'suggestions' (an array of 3 actionable strings). "
        "DO NOT include any surrounding text, markdown, or other characters outside of the JSON object.\n"
        f"\nResume Text:\n---\n{resume_text}")

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        result = _robust_json_load(response.text, ['score', 'suggestions'])
        
        if 'error' in result: return {"score": 0, "suggestions": [result['error']], "error": True}
        return {"score": result['score'], "suggestions": result['suggestions'], "error": False}

    except APIError as e:
        return {"score": 0, "suggestions": [f"Gemini API Error during ATS analysis: {e}"], "error": True}
    except Exception as e:
        return {"score": 0, "suggestions": [f"General Server Error during ATS analysis: {e}"], "error": True}

# 4. Used by /api/placement/mock/start
def generate_interview_questions(jd_text):
    """Generates custom questions based on JD using the Placement Client (INTERVIEW_KEY)."""
    client = get_client('placement')
    if not client:
        return {"questions": [], "error": "Placement client not initialized."}
        
    prompt = ("You are an expert interviewer. Analyze the Job Description (JD) below. Generate 5 interview questions highly relevant to this JD. Structure them as: 2 Technical Questions, 2 Behavioral/STAR Questions, and 1 Situational Question. Return ONLY a JSON array of 5 question strings. DO NOT include any markdown or text outside the array.\n"
        f"\nJob Description:\n---\n{jd_text}")
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        questions_text = response.text.strip()
        questions_text_cleaned = questions_text.replace("```json", "").replace("```", "").strip()
        questions_list = json.loads(questions_text_cleaned)
        
        if isinstance(questions_list, list) and len(questions_list) == 5:
            return {"questions": questions_list, "error": None}
        
        return {"questions": [], "error": "AI failed to return a list of 5 questions. Raw output: " + questions_text[:150]}
    
    except Exception as e:
        return {"questions": [], "error": f"Failed to generate questions: {e}"}

# 5. Used by /api/placement/mock/assess
def critique_interview_answer(question, answer, criteria):
    """Critiques a user's interview answer using the dedicated Placement client (INTERVIEW_KEY)."""
    client = get_client('placement')
    if not client:
        return {"critique": "Backend Error: Placement client not initialized.", "error": True}
        
    prompt = ("You are an expert Data Analyst interviewer and a professional coach. Assess the answer based on the question, the answer, and mandatory criteria. Return ONLY a JSON object with two keys: 'ScoreSummary' (single concise sentence, max 20 words) and 'ActionableSuggestion' (2-3 sentences, focused advice). DO NOT include any surrounding text, markdown, or other characters outside of the JSON object.\n"
        f"\nQuestion: {question}\n\nUser Answer: {answer}\n\nMandatory Criteria: {criteria}")

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        result = _robust_json_load(response.text, ['ScoreSummary', 'ActionableSuggestion'])
        
        if 'error' in result: return {"critique": result['error'], "error": True}
        return {"critique": result, "error": False}

    except APIError as e:
        return {"critique": "Gemini Critique Service Offline: API connection error.", "error": True}
    except Exception as e:
        return {"critique": f"General Server Error: Could not process request. Detail: {e}", "error": True}
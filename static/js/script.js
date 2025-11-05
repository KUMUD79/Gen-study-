document.addEventListener('DOMContentLoaded', () => {
console.log("GenStudy AI Frontend Loaded.");

// --- DOM Elements ---
const notesGeneratorContainer = document.getElementById('notes-generator-container');
const quizPanel = document.getElementById('quiz-panel');
const noteForm = document.getElementById('note-generator-form');
const topicInput = document.getElementById('topic-input');
const notesOutputDiv = document.getElementById('notes-output');
const notesContentPre = document.getElementById('notes-content');
const startQuizBtn = document.getElementById('notes-to-quiz-btn');
const quizQuestionsArea = document.getElementById('quiz-questions-area');
const quizForm = document.getElementById('quiz-form');
const quizResultsArea = document.getElementById('quiz-results-area');
const quizTopicDisplay = document.getElementById('quiz-topic-display');
const xpElement = document.getElementById('user-xp'); 

// Dedicated Quiz Elements
const practiceQuizFormFull = document.getElementById('practice-quiz-form-full');
const practiceTopicInputFull = document.getElementById('practice-topic-input-full');
const practiceQuizOutputFull = document.getElementById('practice-quiz-output-full');
const practiceQuizQuestionsAreaFull = document.getElementById('practice-quiz-questions-area-full');
const quizPracticeSubmitFormFull = document.getElementById('quiz-practice-submit-form-full');
const practiceQuizResultsAreaFull = document.getElementById('practice-quiz-results-area-full');

// --- Global State ---
let currentQuizAnswers = {}; 
let currentQuizTopic = ""; 

// --- Mock Data ---
const MOCK_QUIZ_DATA = {
    topic: "Mock Safety Topic: Python Fundamentals",
    questions: [
        { id: 1, question: "Which module is used for secure hashing in Python?", options: ["requests", "os", "hashlib", "json"], answer: "hashlib" },
        { id: 2, question: "What HTTP status code signifies success?", options: ["404", "500", "200", "302"], answer: "200" },
        { id: 3, question: "What is the purpose of venv?", options: ["Isolation", "Deployment", "Version Control", "Formatting"], answer: "Isolation" },
        { id: 4, question: "Which is a Python micro-framework?", options: ["Django", "Flask", "Pyramid", "Tornado"], answer: "Flask" },
        { id: 5, question: "The 200 status code means?", options: ["Success", "Error", "Redirect", "Forbidden"], answer: "Success" },
    ]
};

// ----------------------------------------------------------------------
// --- QUIZ RENDERER ---
// ----------------------------------------------------------------------
function renderQuiz(questions, targetQuestionsArea, targetResultsArea, namePrefix) {
    targetResultsArea.style.display = 'none';
    currentQuizAnswers = questions.reduce((acc, q, i) => ({ ...acc, [i + 1]: q.answer }), {});
    targetQuestionsArea.innerHTML = questions.map((q, i) => `
        <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <p class="font-semibold text-gray-800 mb-3">${i + 1}. ${q.question}</p>
            <div class="space-y-2">
                ${q.options.map(option => `
                    <label class="flex items-center space-x-2 text-gray-600 hover:bg-gray-200 p-2 rounded-md transition cursor-pointer">
                        <input type="radio" name="${namePrefix}_${i + 1}" value="${option.trim()}" class="text-primary-light focus:ring-primary-light">
                        <span>${option}</span>
                    </label>
                `).join('')}
            </div>
        </div>
    `).join('');
}

// ----------------------------------------------------------------------
// --- NOTES GENERATION (With Markdown Rendering) ---
// ----------------------------------------------------------------------
if (noteForm) {
    noteForm.addEventListener('submit', async (e) => {
        e.preventDefault(); 
        const topic = topicInput.value.trim();
        if (topic.length < 5) {
            notesContentPre.textContent = "Please enter a topic greater than 5 characters.";
            notesOutputDiv.style.display = 'block';
            return;
        }

        notesContentPre.innerHTML = `<div class="text-center py-6"><i class="fas fa-spinner fa-spin mr-2 text-primary-light"></i> Generating detailed notes on: ${topic}...</div>`;
        notesOutputDiv.style.display = 'block';
        if (quizPanel) quizPanel.style.display = 'none';

        try {
            const response = await fetch('/api/notes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic })
            });
            const data = await response.json();

            if (response.ok) {
                let notes = data.notes?.replace('---NOTES-START---', '').trim() || '';
                // Markdown rendering
                if (window.marked) {
                    notesContentPre.innerHTML = marked.parse(notes);
                } else {
                    notesContentPre.textContent = notes;
                }
                currentQuizTopic = topic;
                startQuizBtn.disabled = false;
                startQuizBtn.classList.remove('opacity-50');
            } else {
                notesContentPre.textContent = `Error: ${data.error || "Failed to generate notes."}`;
                startQuizBtn.disabled = true;
            }
        } catch (error) {
            console.error('Notes fetch error:', error);
            notesContentPre.textContent = "Network Error: Could not reach the notes service.";
            startQuizBtn.disabled = true;
        }
    });
}

// ----------------------------------------------------------------------
// --- QUIZ FROM NOTES ---
// ----------------------------------------------------------------------
if (startQuizBtn) {
    startQuizBtn.addEventListener('click', async () => {
        const plainText = notesContentPre.innerText.replace(/\s+/g, ' ').trim();
        if (!plainText || plainText.length < 50) {
            alert("Notes content too short or missing. Please generate notes first.");
            return;
        }

        if (quizPanel) quizPanel.style.display = 'block';
        startQuizBtn.disabled = true;
        quizQuestionsArea.innerHTML = `<div class="text-center py-8"><i class="fas fa-sync fa-spin text-primary-light text-2xl"></i><p class="mt-3 text-gray-600">Generating quiz...</p></div>`;
        quizResultsArea.style.display = 'none';
        quizTopicDisplay.textContent = `Quiz based on: ${currentQuizTopic}`;

        try {
            const response = await fetch('/api/generate-quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content_text: plainText, topic: currentQuizTopic })
            });

            const text = await response.text();
            let data;
            try { data = JSON.parse(text); }
            catch { 
                console.error("Invalid JSON:", text);
                quizQuestionsArea.innerHTML = `<p class="text-red-500 text-center">Quiz generation failed. Please re-login or retry.</p>`;
                return;
            }

            const questions = data.quiz?.questions || [];
            if (questions.length > 0) {
                renderQuiz(questions, quizQuestionsArea, quizResultsArea, 'question');
            } else {
                quizQuestionsArea.innerHTML = `<p class="text-red-500 text-center">No quiz generated. Showing mock quiz.</p>`;
                renderQuiz(MOCK_QUIZ_DATA.questions, quizQuestionsArea, quizResultsArea, 'question');
            }
        } catch (err) {
            console.error("Quiz fetch error:", err);
            quizQuestionsArea.innerHTML = `<p class="text-red-500 text-center">Network error while generating quiz.</p>`;
        } finally {
            startQuizBtn.disabled = false;
        }
    });
}

// ----------------------------------------------------------------------
// --- DEDICATED QUIZ PAGE (Improved Prompt) ---
// ----------------------------------------------------------------------
if (practiceQuizFormFull) {
    practiceQuizFormFull.addEventListener('submit', async (e) => {
        e.preventDefault();
        const topic = practiceTopicInputFull.value.trim();
        if (topic.length < 5) {
            alert("Please enter a valid topic.");
            return;
        }

        const enrichedPrompt = `Generate 5 multiple choice questions with 4 options and 1 correct answer about the topic "${topic}". Focus on conceptual understanding.`;

        practiceQuizOutputFull.style.display = 'block';
        practiceQuizQuestionsAreaFull.innerHTML = `<div class="text-center py-8"><i class="fas fa-sync fa-spin text-accent-green text-2xl"></i><p class="mt-3 text-gray-600">Generating 5 MCQs on: ${topic}...</p></div>`;
        practiceQuizResultsAreaFull.style.display = 'none';

        try {
            const response = await fetch('/api/generate-quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content_text: enrichedPrompt, topic })
            });
            const data = await response.json();
            const questions = data.quiz?.questions || [];
            if (questions.length > 0) {
                renderQuiz(questions, practiceQuizQuestionsAreaFull, practiceQuizResultsAreaFull, 'practice_q');
                currentQuizTopic = topic;
                quizPracticeSubmitFormFull.style.display = 'block';
            } else {
                practiceQuizQuestionsAreaFull.innerHTML = `<p class="text-red-500 text-center">Quiz generation failed. Showing mock quiz.</p>`;
                renderQuiz(MOCK_QUIZ_DATA.questions, practiceQuizQuestionsAreaFull, practiceQuizResultsAreaFull, 'practice_q');
            }
        } catch (err) {
            console.error("Practice quiz error:", err);
            practiceQuizQuestionsAreaFull.innerHTML = `<p class="text-red-500 text-center">Error generating quiz. Try again later.</p>`;
        }
    });
}

// ----------------------------------------------------------------------
// --- QUIZ SUBMISSION (Shared) ---
// ----------------------------------------------------------------------
const submitQuizHandler = async (form, resultsArea, prefix) => {
    const total = Object.keys(currentQuizAnswers).length;
    if (!total) {
        resultsArea.innerHTML = `<p class="text-red-500 text-center">Error: No quiz data loaded.</p>`;
        return;
    }

    let score = 0;
    for (let i = 1; i <= total; i++) {
        const chosen = form.querySelector(`input[name="${prefix}_${i}"]:checked`);
        if (chosen && chosen.value.trim() === currentQuizAnswers[i]?.trim()) score++;
    }

    const percentage = ((score / total) * 100).toFixed(2);
    const xpEarned = score * 10;
    resultsArea.style.display = 'block';
    resultsArea.innerHTML = `
        <div class="text-center">
            <h4 class="text-2xl font-bold text-primary-dark">Quiz Completed!</h4>
            <p class="text-3xl font-extrabold ${percentage >= 70 ? 'text-accent-green' : 'text-red-500'} my-2">${score} / ${total}</p>
            <p class="text-lg font-semibold text-gray-700">Score: ${percentage}%</p>
            <p class="text-yellow-600 font-medium">+${xpEarned} XP Earned!</p>
        </div>
    `;

    try {
        const res = await fetch('/api/submit-score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic: currentQuizTopic || "Practice Quiz",
                score_percentage: parseFloat(percentage),
                xp_earned: xpEarned
            })
        });
        if (res.ok) {
            const data = await res.json();
            if (xpElement) xpElement.textContent = data.new_xp;
        }
    } catch (err) {
        console.error("Score submission error:", err);
    }
};

if (quizForm)
    quizForm.addEventListener('submit', e => { e.preventDefault(); submitQuizHandler(quizForm, quizResultsArea, 'question'); });

if (quizPracticeSubmitFormFull)
    quizPracticeSubmitFormFull.addEventListener('submit', e => { e.preventDefault(); submitQuizHandler(quizPracticeSubmitFormFull, practiceQuizResultsAreaFull, 'practice_q'); });

if (notesGeneratorContainer && quizPanel) quizPanel.style.display = 'none';

});

import streamlit as st
from login_page import login
from firebase_helper import init_firestore
from profile_pannel import create_user_account
import google.generativeai as genai
import json
import os
import random
import time

st.set_page_config(page_title="Exit Ticket Generator", layout="wide")

from config import DEFAULT_QUESTIONS_COUNT
from ui import app_ui

db = init_firestore()

# Subject list for dropdown
subjects = ["Cloud Computing", "Machine Learning", "Cybersecurity", "Data Structures", "Networking"]

# def create_question_page():
#     st.markdown(
#         app_ui,
#         unsafe_allow_html=True
#     )
    
#     st.title("Create Your Own Question")
    
#     with st.form("user_question_form"):
#         subject = st.selectbox("Select Subject", subjects)
#         topic = st.text_input("Enter Topic")
#         subtopic = st.text_input("Enter Sub Topic")
#         question = st.text_area("Enter Question")
#         option_A = st.text_input("Option A")
#         option_B = st.text_input("Option B")
#         option_C = st.text_input("Option C")
#         option_D = st.text_input("Option D")
#         correct_answer = st.selectbox("Correct Answer", ["A", "B", "C", "D"])
#         explanation = st.text_area("Explanation for the Correct Answer")
#         submit = st.form_submit_button("Submit Question")
        
#         if submit:
#             generated_question = {
#                 "question": question,
#                 "options": {
#                     "A": option_A,
#                     "B": option_B,
#                     "C": option_C,
#                     "D": option_D
#                 },
#                 "correct_answer": correct_answer,
#                 "explanation": explanation,
#                 "topic": topic,
#                 "subtopic": subtopic,
#                 "subject": subject
#             }
            
#             st.success("✅ Your question has been created!")
            
#             from firebase_helper import save_question
#             save_question(db, generated_question, source="user")
            
#             # Store in session state for later pinning
#             st.session_state.generated_question = generated_question
    
#     # Show generated question and allow pinning
#     if "generated_question" in st.session_state:
#         st.write("### Generated Question")
#         st.json(st.session_state.generated_question)
        

GOOGLE_API_KEY = st.secrets["api_keys"]["google_api_key"]

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Enhanced system prompt for better API integration
SYSTEM_PROMPT = """You are a highly qualified MCQ generator for an engineering college lecture. Your task is to create exactly {num_questions} multiple-choice questions (MCQs) based strictly on the list of topics provided from a lecture. These MCQs serve as exit ticket questions to assess students' understanding of core concepts.

Instructions:
- Only use concepts that were explicitly covered in the given topic list
- Do not include or infer content beyond the provided topics
- Focus on the most essential technical points, definitions, principles, or equations
- Each question must have one correct answer and three plausible distractors
- The correct answer must be factually accurate
- Write short, clear, and professional questions and answer choices
- Use standard engineering terminology and units
- Keep all technical details precise and concise

Output Format (JSON):
{
  "questions": [
    {
      "question": "Question text here?",
      "options": {
        "A": "Option A text",
        "B": "Option B text", 
        "C": "Option C text",
        "D": "Option D text"
      },
      "correct_answer": "C",
      "explanation": "Brief explanation of why this answer is correct",
      "topic": "Main topic of the question",
      "subtopic": "Subtopic or Specific concept of focus area"
    }
  ]
}

Requirements:
- Return ONLY valid JSON format
- Ensure all questions are relevant to the provided topics and the subject
- Do not deviate and hallucinate from the subject
- Make explanations educational and clear
- Each question MUST include both a "topic" and "subtopic" field. These are mandatory.
- Use engineering-appropriate language and precision"""

def generate_mcqs(lecture_topics, ai_instructions, num_questions, subject):
    """Generate MCQs using Google AI Studio"""
    try:
        if not GOOGLE_API_KEY:
            st.error("Google API key not found. Please set GOOGLE_API_KEY in your environment variables.")
            return None
        
        # Create the prompt with system prompt
        prompt = f"""{SYSTEM_PROMPT}

Subject:
{subject}

Lecture Topics:
{lecture_topics}

Additional Instructions:
{ai_instructions if ai_instructions.strip() else "No additional instructions provided."}

Please generate exactly {num_questions} MCQs based on the above topics and instructions. Do not generate fewer or more.

Return ONLY the JSON format as specified above."""

        # Generate response using Gemini
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        
        # Parse JSON response
        try:
            # Extract JSON from response
            response_text = response.text
            # Find JSON content (handle cases where response might have extra text)
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            json_str = response_text[start_idx:end_idx]
            
            mcqs = json.loads(json_str)
            
            from firebase_helper import save_question
            for q in mcqs.get("questions", []):
                q["subject"] = subject
                save_question(db, q, source="ai")
            
            return mcqs
            
        except json.JSONDecodeError as e:
            st.error(f"Error parsing AI response: {e}")
            st.text("Raw response:")
            st.text(response.text)
            return None
            
    except Exception as e:
        st.error(f"Error generating MCQs: {e}")
        return None

def regenerate_teacher_question(question_index, subject, topics, instructions):
    """Regenerate a single question for teachers"""
    with st.spinner("🔄 Regenerating question..."):
        # Generate a single question
        mcqs = generate_mcqs(topics, instructions, 1, subject)
        
        if mcqs and 'questions' in mcqs and len(mcqs['questions']) > 0:
            # Replace the question at the given index
            st.session_state.teacher_all_mcqs[question_index] = mcqs['questions'][0]
            st.success("✅ Question regenerated successfully!")
            st.rerun()
        else:
            st.error("Failed to regenerate question. Please try again.")


def main():
    from login_page import login
    
    st.markdown(
        app_ui,
        unsafe_allow_html=True
    )
    
    st.set_page_config(
        page_title="MCQ Generator",
        page_icon="🎓",
        layout="wide"
    )
    
    # If not logged in, show login
    if not st.session_state.get("logged_in", False):
        login()
        return
    
    # Show sidebar info and logout button
    st.sidebar.success(f"Logged in as {st.session_state.get('role')} ({st.session_state.get('username')})")
    
    if st.sidebar.button("🚪 Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    # Role-based routing
    role = st.session_state.get("role", "Student")  # default fallback
    
    if role == "Teacher":
        teacher_dashboard()
    elif role == "Student":
        student_dashboard()
    else:
        st.error("🚫 Unknown role. Please contact admin.")

def teacher_dashboard():
    st.sidebar.title("👩‍🏫 Teacher Dashboard")
    page = st.sidebar.radio("Navigate", ["📘 Create Exit Ticket", "🎫 My Published Tickets"])
    
    if page == "📘 Create Exit Ticket":
        st.title("🎓 Create Exit Ticket")
        st.markdown("""
        Exit tickets are quick assessments at the end of a lesson to check students' understanding.
        Teachers can use AI to generate MCQs based on the lecture content to include in exit tickets.
        """)
        
        # Initialize teacher-specific session state
        for key, default in {
            "teacher_mcqs": None,
            "teacher_all_mcqs": None,
            "teacher_ready_for_review": False
        }.items():
            if key not in st.session_state:
                st.session_state[key] = default
        
        # Flow control for teachers
        if st.session_state.teacher_mcqs is None:
            show_teacher_input_page()
        elif not st.session_state.teacher_ready_for_review:
            show_teacher_questions_page()
        else:
            show_teacher_input_page()  # Reset to input page after review
    
    # elif page == "📝 Create Question":
    #     create_question_page()
    
    elif page == "🎫 My Published Tickets":
        view_published_tickets_page()

def student_dashboard():
    st.sidebar.title("🎓 Student Dashboard")
    page = st.sidebar.radio("Navigate", ["🎫 Take Exit Ticket"])

    if page == "🎫 Take Exit Ticket":
        st.title("🎫 Exit Ticket")
        st.markdown("Enter the ticket ID provided by your teacher to start the exit ticket.")

        # Initialize session state for exit tickets
        for key, default in {
            "ticket_data": None,
            "ticket_current_question": 0,
            "ticket_user_answers": {},
            "ticket_quiz_completed": False,
            "ticket_show_feedback": False,
            "ticket_last_user_answer": None
        }.items():
            if key not in st.session_state:
                st.session_state[key] = default

        # Flow control for exit tickets
        if st.session_state.ticket_data is None:
            show_ticket_input_page()

        elif not st.session_state.ticket_quiz_completed:
            # 🔁 Randomly select only 3 questions once
            if 'ticket_initialized' not in st.session_state:
                all_questions = st.session_state.ticket_data['questions']
                st.session_state.ticket_data['questions'] = random.sample(all_questions, min(3, len(all_questions)))
                st.session_state.ticket_current_question = 0
                st.session_state.ticket_user_answers = {}
                st.session_state.ticket_quiz_completed = False
                st.session_state.ticket_initialized = True

            show_ticket_quiz_page()

        else:
            show_ticket_results_page()
    

def show_teacher_input_page():
    """Input page specifically for teachers"""
    from config import DEFAULT_QUESTIONS_COUNT
    
    st.markdown(
        app_ui,
        unsafe_allow_html=True
    )
    
    st.markdown("Enter all details marked with `*` to generate MCQs")
    st.header("📝 Enter Lecture Information")
    
    with st.form("teacher_mcq_form"):
        st.markdown("### 📚 Lecture Subject *")
        subject = st.text_area(
            "Enter the subject of your lecture",
            placeholder="e.g., Cloud Computing, Machine Learning, etc.",
            help="Specify the subject for which you want to generate MCQs",
            height=69)
        
        st.markdown("---")
        
        st.markdown("### 📖 Lecture Topics & Summary *")
        lecture_topics = st.text_area(
            "Add a detailed summary of the lecture topics",
            placeholder="Enter the main topics, concepts, and key points covered in your lecture...",
            height=100,
            help="Include all important topics, definitions, formulas, and concepts that were covered"
        )
        
        ai_instruction_options = {
            "None": "",
            "🧠 Focus on conceptual clarity": "Emphasize conceptual understanding of the topics.",
            "🧪 Include numerical or formula-based questions": "Include numerical problems or questions requiring application of formulas.",
            "🛠️ Emphasize real-world applications": "Generate questions that relate the concepts to real-world engineering applications.",
            "🔍 Include commonly misunderstood concepts": "Focus on common misconceptions or tricky areas in the lecture topics.",
            "🎯 Prioritize definition-based questions": "Ask for precise definitions and terminology-based MCQs.",
            "🔄 Convert Above Text Questions into MCQs": "Take the provided descriptive or paragraph-style questions and convert them into multiple-choice format."
        }
        
        st.markdown("---")
        st.subheader("🤖 AI Instructions (Optional)")
        selected_instruction_key = st.selectbox(
            "Additional instructions for AI",
            options=list(ai_instruction_options.keys()),
            help="Choose how the AI should generate your questions"
        )
        ai_instructions = ai_instruction_options[selected_instruction_key]
        
        st.markdown("---")
        st.subheader("🧮 Number of Questions to Generate")
        num_questions = st.slider(
            "Number of questions",
            min_value=3,
            max_value=10,
            value=5,
            help="Generate questions for your exit ticket"
        )
        
        submitted = st.form_submit_button("🚀 Generate MCQs", type="primary")
        
        if submitted:
            if not lecture_topics.strip():
                st.error("Please enter lecture topics to generate MCQs.")
                return
            
            with st.spinner("🤖 Generating MCQs with AI..."):
                mcqs = generate_mcqs(lecture_topics, ai_instructions, num_questions, subject)
                
                if mcqs and 'questions' in mcqs:
                    if len(mcqs['questions']) < num_questions:
                        st.error(f"Only {len(mcqs['questions'])} questions were generated. Please try again or reduce the count.")
                        return
                    
                    # Store in teacher-specific session state
                    st.session_state.teacher_subject = subject
                    st.session_state.teacher_lecture_topics = lecture_topics
                    st.session_state.teacher_ai_instructions = ai_instructions
                    st.session_state.teacher_all_mcqs = mcqs['questions']
                    st.session_state.teacher_mcqs = mcqs['questions']
                    st.session_state.teacher_ready_for_review = False
                    
                    st.rerun()
                else:
                    st.error("Failed to generate MCQs. Please try again.")

def show_teacher_questions_page():
    """Display all generated questions for teachers to review and edit"""
    st.header("📚 Generated Questions - Review & Edit")
    
    if 'teacher_all_mcqs' not in st.session_state or not st.session_state.teacher_all_mcqs:
        st.warning("⚠️ No questions found. Please generate questions first.")
        return

    all_mcqs = st.session_state.teacher_all_mcqs
    subject = st.session_state.get("teacher_subject", "")
    topics = st.session_state.get("teacher_lecture_topics", "")
    instructions = st.session_state.get("teacher_ai_instructions", "")

    st.markdown(f"**Subject:** {subject}")
    st.markdown(f"**Total Questions Generated:** {len(all_mcqs)}")
    st.markdown("---")

    for i, question_data in enumerate(all_mcqs):
        edit_key = f"teacher_edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        with st.expander(f"Question {i + 1}: {question_data['question'][:50]}..."):
            if not st.session_state[edit_key]:
                st.markdown(f"**Question:** {question_data['question']}")

                for option, text in question_data['options'].items():
                    if option == question_data['correct_answer']:
                        st.markdown(f"✅ **{option}) {text}** (Correct Answer)")
                    else:
                        st.markdown(f"{option}) {text}")

                st.markdown(f"**Explanation:** {question_data.get('explanation', 'No explanation provided.')}")
                st.markdown(f"**Topic:** {question_data.get('topic', 'Unknown')}")
                st.markdown(f"**Subtopic:** {question_data.get('subtopic', 'Unknown')}")

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✏️ Edit", key=f"teacher_edit_btn_{i}"):
                        st.session_state[edit_key] = True
                with col2:
                    if st.button("🔁 Regenerate", key=f"teacher_regen_{i}"):
                        regenerate_teacher_question(i, subject, topics, instructions)

            else:
                # EDIT MODE
                st.markdown("### ✏️ Editing Mode")
                edited_question = st.text_area("Edit Question", question_data['question'], key=f"teacher_q_text_{i}")

                edited_options = {}
                correct_option = st.selectbox(
                    "Correct Answer",
                    list(question_data['options'].keys()),
                    index=list(question_data['options'].keys()).index(question_data['correct_answer']),
                    key=f"teacher_correct_{i}"
                )

                for option in sorted(question_data['options'].keys()):
                    edited_options[option] = st.text_input(
                        f"Option {option}",
                        value=question_data['options'][option],
                        key=f"teacher_opt_{i}_{option}"
                    )

                edited_explanation = st.text_area("Explanation", question_data.get('explanation', ''), key=f"teacher_exp_{i}")
                edited_topic = st.text_input("Topic", question_data.get('topic', ''), key=f"teacher_topic_{i}")
                edited_subtopic = st.text_input("Subtopic", question_data.get('subtopic', ''), key=f"teacher_subtopic_{i}")

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("💾 Save", key=f"teacher_save_{i}"):
                        st.session_state.teacher_all_mcqs[i] = {
                            "question": edited_question,
                            "options": edited_options,
                            "correct_answer": correct_option,
                            "explanation": edited_explanation,
                            "topic": edited_topic,
                            "subtopic": edited_subtopic,
                        }
                        st.session_state[edit_key] = False
                        st.success("✅ Question updated.")
                        st.rerun()
                with col2:
                    if st.button("❌ Cancel", key=f"teacher_cancel_{i}"):
                        st.session_state[edit_key] = False
                        st.rerun()

    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔄 Generate New Set", key="teacher_generate_new_btn"):
            subject = st.session_state.get("teacher_subject", "")
            topics = st.session_state.get("teacher_lecture_topics", "")
            instructions = st.session_state.get("teacher_ai_instructions", "")
            num_questions = st.session_state.get("teacher_num_questions", 5)  # fallback to 5 if missing

            new_mcqs = generate_mcqs(topics, instructions, num_questions, subject)
            if new_mcqs and 'questions' in new_mcqs:
                st.session_state.teacher_mcqs = new_mcqs['questions']
                st.session_state.teacher_all_mcqs = new_mcqs['questions']
                st.session_state.teacher_ready_for_review = True
                st.success("✅ New questions generated.")
            else:
                st.error("❌ Failed to generate a new set. Please try again.")
            # st.rerun()

    with col2:
        if st.button("📤 PUBLISH Exit Ticket", key="teacher_publish_btn"):
            publish_exit_ticket()

def publish_exit_ticket():
    """Publish the current questions as an exit ticket"""
    try:
        if 'teacher_all_mcqs' not in st.session_state or not st.session_state.teacher_all_mcqs:
            st.error("No questions to publish!")
            return
    
        # Get teacher information
        teacher_name = st.session_state.get('username', 'Unknown Teacher')
        subject = st.session_state.get('teacher_subject', 'Unknown Subject')
        lecture_topics = st.session_state.get('teacher_lecture_topics', 'No topics specified')
        questions = st.session_state.teacher_all_mcqs
        
        # Create exit ticket
        from firebase_helper import create_exit_ticket
        ticket = create_exit_ticket(db, questions, teacher_name, subject, lecture_topics)
        
        if ticket:
            st.success(f"🎉 Exit Ticket Published Successfully!")
            st.info(f"**Ticket ID: {ticket['ticket_id']}**")
            st.markdown(f"**Title:** {ticket['title']}")
            st.markdown(f"**Subject:** {ticket['subject']}")
            st.markdown(f"**Total Questions:** {ticket['total_questions']}")
            st.markdown("---")
            st.markdown("📋 **Share this Ticket ID with your students:**")
            st.code(ticket['ticket_id'], language=None)
            st.markdown("Students can use this ID to access and answer the exit ticket.")
            
            # Store published ticket info in session state
            st.session_state.published_ticket = ticket
            
            # Reset teacher session state for new generation
            st.session_state.teacher_mcqs = None
            st.session_state.teacher_all_mcqs = None
            st.session_state.teacher_ready_for_review = False
            
        else:
            st.error("Failed to publish exit ticket. Please try again.")
            
    except Exception as e:
        st.error(f"Error publishing exit ticket: {e}")

def view_published_tickets_page():
    """Display all tickets published by the current teacher"""
    st.header("🎫 My Published Exit Tickets")
    st.markdown(app_ui, unsafe_allow_html=True)
    
    teacher_name = st.session_state.get('username', 'Unknown Teacher')
    
    from firebase_helper import get_all_tickets_by_teacher
    tickets = get_all_tickets_by_teacher(db, teacher_name)
    
    if not tickets:
        st.info("📭 No exit tickets published yet.")
        st.markdown("Create your first exit ticket using the '📘 Create Exit Ticket' tab!")
        return
    
    st.markdown(f"**Total Published Tickets:** {len(tickets)}")
    st.markdown("---")
    
    # ADD: Check if we should show analytics for a specific ticket
    if 'show_analytics_for' in st.session_state:
        view_ticket_analytics(st.session_state.show_analytics_for)
        if st.button("🔙 Back to All Tickets"):
            del st.session_state.show_analytics_for
            st.rerun()
        return
    
    for idx, ticket in enumerate(tickets):
        with st.expander(f"🎫 {ticket.get('title', 'Untitled')} - ID: {ticket['ticket_id']}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Ticket ID:** `{ticket['ticket_id']}`")
                st.markdown(f"**Subject:** {ticket.get('subject', 'N/A')}")
                st.markdown(f"**Total Questions:** {ticket.get('total_questions', 0)}")
                st.markdown(f"**Status:** {ticket.get('status', 'unknown').title()}")
                
                # Fixed timestamp handling
                created_at = ticket.get('created_at', 'Unknown')
                try:
                    if hasattr(created_at, 'strftime'):
                        formatted_date = created_at.strftime('%Y-%m-%d %H:%M')
                    elif hasattr(created_at, 'to_pydatetime'):
                        formatted_date = created_at.to_pydatetime().strftime('%Y-%m-%d %H:%M')
                    else:
                        formatted_date = str(created_at)
                except:
                    formatted_date = "Unknown"
                
                st.markdown(f"**Created:** {formatted_date}")
                
                # Show lecture topics
                topics = ticket.get('lecture_topics', '')
                if topics:
                    st.markdown(f"**Topics:** {topics}")
                
                # ADD: Show response count
                from firebase_helper import get_ticket_analytics
                analytics = get_ticket_analytics(db, ticket['ticket_id'])
                st.markdown(f"**📊 Responses:** {analytics['total_responses']} | **📈 Avg Score:** {analytics['average_score']}%")
            
            with col2:
                # Action buttons
                if st.button("📋 Copy ID", key=f"copy_id_{idx}"):
                    st.code(ticket['ticket_id'], language=None)
                    st.success("ID ready to copy!")
                
                # ADD: View Analytics button
                if st.button("📊 View Analytics", key=f"analytics_{idx}"):
                    st.session_state.show_analytics_for = ticket['ticket_id']
                    st.rerun()
                
                if ticket.get('status') == 'active':
                    if st.button("🔒 Deactivate", key=f"deactivate_{idx}"):
                        from firebase_helper import update_ticket_status
                        if update_ticket_status(db, ticket['ticket_id'], 'inactive'):
                            st.success("Ticket deactivated!")
                            st.rerun()
                        else:
                            st.error("Failed to deactivate ticket.")
                else:
                    if st.button("✅ Activate", key=f"activate_{idx}"):
                        from firebase_helper import update_ticket_status
                        if update_ticket_status(db, ticket['ticket_id'], 'active'):
                            st.success("Ticket activated!")
                            st.rerun()
                        else:
                            st.error("Failed to activate ticket.")
            
            # Questions preview
            questions = ticket.get('questions', [])
            if questions:
                st.markdown("**Questions Preview:**")
                for i, q in enumerate(questions[:2]):
                    question_text = q.get('question', 'No question text')
                    if len(question_text) > 60:
                        question_text = question_text[:60] + "..."
                    st.markdown(f"{i+1}. {question_text}")
                if len(questions) > 2:
                    st.markdown(f"... and {len(questions) - 2} more questions")

def show_ticket_input_page():
    """Page for students to enter ticket ID"""
    
    with st.form("ticket_id_form"):
        st.markdown("### Enter the Ticket ID provided by your teacher")
        ticket_id = st.text_input(
            "Ticket ID",
            placeholder="e.g., A3X9K2",
            help="Enter the 6-character ticket ID (case insensitive)"
        ).upper().strip()
        
        submitted = st.form_submit_button("🚀 Access Exit Ticket", type="primary")
        
        if submitted:
            if not ticket_id:
                st.error("Please enter a ticket ID.")
                return
            
            if len(ticket_id) != 6:
                st.error("Ticket ID should be 6 characters long.")
                return
            
            # Retrieve ticket from database
            from firebase_helper import get_exit_ticket
            with st.spinner("Loading exit ticket..."):
                ticket_data = get_exit_ticket(db, ticket_id)
                
                if ticket_data:
                    if ticket_data.get('status') != 'active':
                        st.error("This exit ticket is no longer active. Please contact your teacher.")
                        return
                    
                    # Store ticket data in session state
                    st.session_state.ticket_data = ticket_data
                    st.session_state.ticket_current_question = 0
                    st.session_state.ticket_user_answers = {}
                    st.session_state.ticket_quiz_completed = False
                    st.session_state.ticket_show_feedback = False
                    st.session_state.ticket_last_user_answer = None
                    st.session_state.student_name = None  # Initialize student name
                    st.session_state.response_saved = False  # Initialize save status
                    st.session_state.student_already_attempted = False  # Track attempt status
                    
                    st.rerun()
                else:
                    st.error("Invalid ticket ID. Please check and try again.")


def show_ticket_quiz_page():
    """Display the exit ticket quiz interface"""
    ticket_data = st.session_state.ticket_data
    questions = ticket_data['questions']
    current_q = st.session_state.ticket_current_question

    # Display ticket info
    st.header(f"🎫 {ticket_data.get('title', 'Exit Ticket')}")
    st.markdown(f"**Subject:** {ticket_data.get('subject', 'N/A')}")
    st.markdown(f"**Teacher:** {ticket_data.get('teacher_name', 'N/A')}")
    
    # Student name input and duplicate check
    if 'student_name' not in st.session_state or not st.session_state.student_name:
        st.markdown("---")
        student_name = st.text_input(
            "👤 Enter your name:",
            placeholder="Your full name",
            help="This will be used to track your responses"
        )
        
        if student_name:
            student_name = student_name.strip()
            
            # Check if student has already attempted this ticket
            from firebase_helper import check_student_already_attempted
            if check_student_already_attempted(db, ticket_data['ticket_id'], student_name):
                st.error(f"❌ You have already completed this exit ticket!")
                st.info("Each student can attempt an exit ticket only once.")
                st.session_state.student_already_attempted = True
                return
            else:
                st.session_state.student_name = student_name
                st.session_state.student_already_attempted = False
                st.rerun()
        else:
            st.warning("Please enter your name to continue.")
            return
    else:
        # Double-check if student has already attempted (in case they reload the page)
        if not st.session_state.get('student_already_attempted', False):
            from firebase_helper import check_student_already_attempted
            if check_student_already_attempted(db, ticket_data['ticket_id'], st.session_state.student_name):
                st.error(f"❌ You have already completed this exit ticket!")
                st.info("Each student can attempt an exit ticket only once.")
                st.session_state.student_already_attempted = True
                return
        
        st.markdown(f"**Student:** {st.session_state.student_name}")
    
    st.markdown("---")

    if current_q >= len(questions):
        st.session_state.ticket_quiz_completed = True
        st.rerun()
        return

    # Progress bar
    progress = (current_q + 1) / len(questions)
    st.progress(progress)
    st.caption(f"Question {current_q + 1} of {len(questions)}")

    question_data = questions[current_q]
    st.subheader(f"Question {current_q + 1}")
    st.markdown(f"**{question_data['question']}**")

    # Show answer options in a form
    with st.form(f"ticket_question_{current_q}"):
        answer_given = current_q in st.session_state.ticket_user_answers

        user_answer = st.radio(
            "Select your answer:",
            options=list(question_data['options'].keys()),
            format_func=lambda x: f"{x}) {question_data['options'][x]}",
            key=f"ticket_radio_{current_q}",
            disabled=answer_given
        )

        submitted = st.form_submit_button("Submit Answer", type="primary", disabled=answer_given)

    # Process after form is submitted (outside form block)
    if submitted:
        st.session_state.ticket_user_answers[current_q] = user_answer
        st.session_state.ticket_last_user_answer = user_answer

        correct_answer = question_data['correct_answer']
        if user_answer == correct_answer:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Incorrect. The correct answer is {correct_answer})")

        st.info(f"**Explanation:** {question_data.get('explanation', 'No explanation provided.')}")

    # Navigation buttons (outside the form)
    col1, col2 = st.columns([1, 1])

    with col1:
        if current_q > 0:
            if st.button("⬅️ Previous Question", key=f"ticket_prev_{current_q}"):
                st.session_state.ticket_current_question = current_q - 1
                st.rerun()

    with col2:
        if current_q < len(questions) - 1:
            if st.button("➡️ Next Question", key=f"ticket_next_{current_q}"):
                st.session_state.ticket_current_question = current_q + 1
                st.rerun()
        else:
            if st.button("🏁 Finish Exit Ticket", key=f"ticket_finish_{current_q}"):
                st.session_state.ticket_quiz_completed = True
                st.rerun()

def show_ticket_results_page():
    """Display results after completing the exit ticket"""
    ticket_data = st.session_state.ticket_data
    questions = ticket_data['questions']
    user_answers = st.session_state.ticket_user_answers
    
    st.header("🎉 Exit Ticket Completed!")
    st.markdown(f"**Subject:** {ticket_data.get('subject', 'N/A')}")
    st.markdown(f"**Teacher:** {ticket_data.get('teacher_name', 'N/A')}")
    st.markdown(f"**Student:** {st.session_state.get('student_name', 'Unknown')}")
    st.markdown("---")
    
    # Calculate score
    correct_count = 0
    total_questions = len(questions)
    
    for i, question_data in enumerate(questions):
        if i in user_answers and user_answers[i] == question_data['correct_answer']:
            correct_count += 1
    
    score_percentage = (correct_count / total_questions) * 100
    
    # Display score with styling
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.metric(
            label="📊 Your Score",
            value=f"{correct_count}/{total_questions}",
            delta=f"{score_percentage:.1f}%"
        )
    
    # Save student response to Firebase (only once and with better error handling)
    if 'response_saved' not in st.session_state or not st.session_state.response_saved:
        score_data = {
            "correct_count": correct_count,
            "total_questions": total_questions,
            "percentage": score_percentage
        }
        
        try:
            from firebase_helper import save_student_response
            with st.spinner("💾 Saving your response..."):
                success = save_student_response(
                    db, 
                    ticket_data['ticket_id'], 
                    st.session_state.get('student_name', 'Unknown'),
                    user_answers,
                    score_data
                )
                
                if success:
                    st.session_state.response_saved = True
                    st.success("✅ Your response has been recorded!")
                else:
                    st.error("❌ You have already completed this exit ticket!")
                    st.info("Each student can attempt an exit ticket only once.")
                    
        except Exception as e:
            st.error(f"❌ Failed to save your response: {str(e)}")
            st.info("Please contact your teacher if this problem persists.")
            print(f"Error saving response: {e}")
    else:
        st.info("✅ Response already saved!")
    
    # Performance message
    if score_percentage >= 80:
        st.success("🌟 Excellent work! You have a strong understanding of the concepts.")
    elif score_percentage >= 60:
        st.info("👍 Good job! You understand most concepts well.")
    else:
        st.warning("📚 Keep studying! Review the concepts and try again.")
    
    st.markdown("---")
    
    # Detailed review
    st.subheader("📝 Detailed Review")
    
    for i, question_data in enumerate(questions):
        with st.expander(f"Question {i + 1}: {question_data['question'][:50]}..."):
            st.markdown(f"**Question:** {question_data['question']}")
            
            user_answer = user_answers.get(i, "NA")
            correct_answer = question_data['correct_answer']
            
            # Show user's answer
            if user_answer == correct_answer:
                st.success(f"✅ Your answer: {user_answer}) {question_data['options'][user_answer]}")
            else:
                st.error(f"❌ Your answer: {user_answer}) {question_data['options'].get(user_answer, 'Not answered')}")
                st.success(f"✅ Correct answer: {correct_answer}) {question_data['options'][correct_answer]}")
            
            st.info(f"**Explanation:** {question_data.get('explanation', 'No explanation provided.')}")
            st.markdown(f"**Topic:** {question_data.get('topic', 'Unknown')}")
            st.markdown(f"**Subtopic:** {question_data.get('subtopic', 'Unknown')}")
    
    # Action buttons
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🔄 Take Another Exit Ticket"):
            # Reset ticket session state
            st.session_state.ticket_data = None
            st.session_state.ticket_current_question = 0
            st.session_state.ticket_user_answers = {}
            st.session_state.ticket_quiz_completed = False
            st.session_state.ticket_show_feedback = False
            st.session_state.ticket_last_user_answer = None
            st.session_state.student_name = None
            st.session_state.response_saved = False
            st.session_state.student_already_attempted = False
            if 'ticket_initialized' in st.session_state:
                del st.session_state.ticket_initialized
            st.rerun()

def show_input_page():
    """Original input page for student quiz generation"""
    from config import DEFAULT_QUESTIONS_COUNT
    
    st.markdown("Enter all details marked with `*` to generate MCQs")
    st.header("📝 Enter Your Requirements")
    
    with st.form("mcq_form"):
        st.markdown("### 📚 Select Subject *")
        subject = st.text_area(
            "Enter the subject of your lecture",
            placeholder="e.g., Cloud Computing, Machine Learning, etc.",
            help="Specify the subject for which you want to generate MCQs",
            height=50)
        
        st.markdown("---")
        
        st.markdown("### 📖 Enter Topics *")
        lecture_topics = st.text_area(
            "Enter the topics you want to be tested on",
            placeholder="Enter topics, concepts, and areas you want to practice...",
            height=100,
            help="List all topics you want questions about"
        )
        
        ai_instruction_options = {
            "None": "",
            "🧠 Focus on conceptual clarity": "Emphasize conceptual understanding of the topics.",
            "🧪 Include numerical or formula-based questions": "Include numerical problems or questions requiring application of formulas.",
            "🛠️ Emphasize real-world applications": "Generate questions that relate the concepts to real-world engineering applications.",
            "🔍 Include commonly misunderstood concepts": "Focus on common misconceptions or tricky areas in the lecture topics.",
            "🎯 Prioritize definition-based questions": "Ask for precise definitions and terminology-based MCQs."
        }
        
        st.markdown("---")
        st.subheader("🤖 AI Instructions (Optional)")
        selected_instruction_key = st.selectbox(
            "Additional instructions for AI",
            options=list(ai_instruction_options.keys()),
            help="Choose how the AI should generate your questions"
        )
        ai_instructions = ai_instruction_options[selected_instruction_key]
        
        st.markdown("---")
        st.subheader("🧮 Number of Questions to Generate")
        num_questions = st.slider(
            "Number of questions",
            min_value=3,
            max_value=10,
            value=DEFAULT_QUESTIONS_COUNT,
            help="Choose how many questions you want to practice"
        )
        
        submitted = st.form_submit_button("🚀 Generate MCQs", type="primary")
        
        if submitted:
            if not lecture_topics.strip():
                st.error("Please enter topics to generate MCQs.")
                return
            
            with st.spinner("🤖 Generating MCQs with AI..."):
                mcqs = generate_mcqs(lecture_topics, ai_instructions, num_questions, subject)
                
                if mcqs and 'questions' in mcqs:
                    if len(mcqs['questions']) < num_questions:
                        st.error(f"Only {len(mcqs['questions'])} questions were generated. Please try again or reduce the count.")
                        return
                    
                    # Store in session state
                    st.session_state.subject = subject
                    st.session_state.lecture_topics = lecture_topics
                    st.session_state.ai_instructions = ai_instructions
                    st.session_state.all_mcqs = mcqs['questions']
                    st.session_state.mcqs = mcqs['questions']
                    st.session_state.ready_for_quiz = False
                    st.rerun()
                else:
                    st.error("Failed to generate MCQs. Please try again.")

def regenerate_question(question_index, subject, topics, instructions):
    """Regenerate a single question"""
    with st.spinner("🔄 Regenerating question..."):
        # Generate a single question
        mcqs = generate_mcqs(topics, instructions, 1, subject)
        
        if mcqs and 'questions' in mcqs and len(mcqs['questions']) > 0:
            # Replace the question at the given index
            st.session_state.all_mcqs[question_index] = mcqs['questions'][0]
            st.success("✅ Question regenerated successfully!")
            st.rerun()
        else:
            st.error("Failed to regenerate question. Please try again.")

def show_quiz_page():
    """Display the quiz interface"""
    questions = st.session_state.mcqs
    current_q = st.session_state.current_question
    
    if current_q >= len(questions):
        st.session_state.quiz_completed = True
        st.rerun()
        return
    
    # Progress bar
    progress = (current_q + 1) / len(questions)
    st.progress(progress)
    st.caption(f"Question {current_q + 1} of {len(questions)}")
    
    question_data = questions[current_q]
    
    st.subheader(f"Question {current_q + 1}")
    st.markdown(f"**{question_data['question']}**")
    
    # Show answer options
    with st.form(f"question_{current_q}"):
        # Determine if question is already answered
        answer_given = current_q in st.session_state.user_answers
        
        user_answer = st.radio(
            "Select your answer:",
            options=list(question_data['options'].keys()),
            format_func=lambda x: f"{x}) {question_data['options'][x]}",
            key=f"radio_{current_q}",
            disabled=answer_given
        )
        
        submitted = st.form_submit_button("Submit Answer", type="primary", disabled=answer_given)
        
        if submitted:
            # Store user's answer
            st.session_state.user_answers[current_q] = user_answer
            st.session_state.last_user_answer = user_answer
            
            # Show immediate feedback
            correct_answer = question_data['correct_answer']
            if user_answer == correct_answer:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Incorrect. The correct answer is {correct_answer})")
            
            st.info(f"**Explanation:** {question_data.get('explanation', 'No explanation provided.')}")
            
            # Navigation buttons
            col1, col2 = st.columns([1, 1])
            
            with col1:
                if current_q > 0:
                    if st.button("⬅️ Previous Question", key=f"prev_{current_q}"):
                        st.session_state.current_question = current_q - 1
                        st.rerun()
            
            with col2:
                if current_q < len(questions) - 1:
                    if st.button("➡️ Next Question", key=f"next_{current_q}"):
                        st.session_state.current_question = current_q + 1
                        st.rerun()
                else:
                    if st.button("🏁 Finish Quiz", key=f"finish_{current_q}"):
                        st.session_state.quiz_completed = True
                        st.rerun()

def show_results_page():
    """Display results after completing the quiz"""
    questions = st.session_state.mcqs
    user_answers = st.session_state.user_answers
    
    st.header("🎉 Quiz Completed!")
    st.markdown("---")
    
    # Calculate score
    correct_count = 0
    total_questions = len(questions)
    
    for i, question_data in enumerate(questions):
        if i in user_answers and user_answers[i] == question_data['correct_answer']:
            correct_count += 1
    
    score_percentage = (correct_count / total_questions) * 100
    
    # Display score with styling
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.metric(
            label="📊 Your Score",
            value=f"{correct_count}/{total_questions}",
            delta=f"{score_percentage:.1f}%"
        )
    
    # Performance message
    if score_percentage >= 80:
        st.success("🌟 Excellent work! You have a strong understanding of the concepts.")
    elif score_percentage >= 60:
        st.info("👍 Good job! You understand most concepts well.")
    else:
        st.warning("📚 Keep studying! Review the concepts and try again.")
    
    st.markdown("---")
    
    # Detailed review
    st.subheader("📝 Detailed Review")
    
    for i, question_data in enumerate(questions):
        with st.expander(f"Question {i + 1}: {question_data['question'][:50]}..."):
            st.markdown(f"**Question:** {question_data['question']}")
            
            user_answer = user_answers.get(i, "NA")
            correct_answer = question_data['correct_answer']
            
            # Show user's answer
            if user_answer == correct_answer:
                st.success(f"✅ Your answer: {user_answer}) {question_data['options'][user_answer]}")
            else:
                st.error(f"❌ Your answer: {user_answer}) {question_data['options'].get(user_answer, 'Not answered')}")
                st.success(f"✅ Correct answer: {correct_answer}) {question_data['options'][correct_answer]}")
            
            st.info(f"**Explanation:** {question_data.get('explanation', 'No explanation provided.')}")
            st.markdown(f"**Topic:** {question_data.get('topic', 'Unknown')}")
            st.markdown(f"**Subtopic:** {question_data.get('subtopic', 'Unknown')}")
    
    # Action buttons
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🔄 Retake Quiz"):
            # Reset quiz but keep questions
            st.session_state.current_question = 0
            st.session_state.user_answers = {}
            st.session_state.quiz_completed = False
            st.session_state.show_feedback = False
            st.session_state.last_user_answer = None
            st.rerun()
    
    with col2:
        if st.button("📝 Generate New Quiz"):
            # Reset all session state
            st.session_state.mcqs = None
            st.session_state.all_mcqs = None
            st.session_state.current_question = 0
            st.session_state.user_answers = {}
            st.session_state.quiz_completed = False
            st.session_state.show_feedback = False
            st.session_state.last_user_answer = None
            st.session_state.ready_for_quiz = False
            st.rerun()

def view_ticket_analytics(ticket_id):
    """
    Display analytics and student responses for a specific ticket
    """
    st.header(f"📊 Analytics for Ticket: {ticket_id}")
    
    from firebase_helper import get_ticket_analytics, get_exit_ticket
    
    # Get ticket info
    ticket_data = get_exit_ticket(db, ticket_id)
    if not ticket_data:
        st.error("Ticket not found!")
        return
    
    # Get analytics
    analytics = get_ticket_analytics(db, ticket_id)
    
    # Display ticket info
    st.markdown(f"**Title:** {ticket_data.get('title', 'N/A')}")
    st.markdown(f"**Subject:** {ticket_data.get('subject', 'N/A')}")
    st.markdown(f"**Total Questions:** {ticket_data.get('total_questions', 0)}")
    st.markdown("---")
    
    # Display analytics metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📝 Total Responses", analytics['total_responses'])
    
    with col2:
        st.metric("👥 Unique Students", analytics.get('unique_students', 0))
    
    with col3:
        st.metric("📊 Average Score", f"{analytics['average_score']}%")
    
    st.markdown("---")
    
    # Display individual responses
    if analytics['total_responses'] > 0:
        st.subheader("📋 Student Responses")
        
        responses = analytics.get('responses', [])
        for i, response in enumerate(responses):
            with st.expander(f"👤 {response.get('student_name', 'Unknown')} - {response.get('score', {}).get('percentage', 0):.1f}%"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown(f"**Score:** {response.get('score', {}).get('correct_count', 0)}/{response.get('score', {}).get('total_questions', 0)}")
                    st.markdown(f"**Percentage:** {response.get('score', {}).get('percentage', 0):.1f}%")
                
                with col2:
                    completed_at = response.get('completed_at', 'Unknown')
                    try:
                        if hasattr(completed_at, 'strftime'):
                            formatted_time = completed_at.strftime('%Y-%m-%d %H:%M')
                        elif hasattr(completed_at, 'to_pydatetime'):
                            formatted_time = completed_at.to_pydatetime().strftime('%Y-%m-%d %H:%M')
                        else:
                            formatted_time = str(completed_at)
                    except:
                        formatted_time = "Unknown"
                    
                    st.markdown(f"**Completed:** {formatted_time}")
                
                # Show detailed responses - FIXED LOGIC
                st.markdown("**Answers:**")
                responses_dict = response.get('responses', {})
                questions = ticket_data.get('questions', [])
                
                for q_idx_str, student_answer in responses_dict.items():
                    q_idx = int(q_idx_str)  # Convert string back to int for indexing
                    if q_idx < len(questions):
                        question = questions[q_idx]
                        correct_answer = question['correct_answer']
                        
                        # FIXED: Compare student_answer with correct_answer properly
                        is_correct = student_answer == correct_answer
                        
                        # FIXED: Show correct status symbol
                        status = "✅" if is_correct else "❌"
                        
                        # Get the text for the student's answer
                        answer_text = question['options'].get(student_answer, 'N/A')
                        
                        st.markdown(f"{status} Q{q_idx+1}: {student_answer}) {answer_text}")
                        
                        # Optionally show what the correct answer was if student was wrong
                        if not is_correct:
                            correct_text = question['options'].get(correct_answer, 'N/A')
                            st.markdown(f"    🎯 Correct: {correct_answer}) {correct_text}")
    else:
        st.info("No student responses yet.")
        
if __name__ == "__main__":
    main()
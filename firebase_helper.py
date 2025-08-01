import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter  # Add this import
import uuid
from datetime import datetime

def init_firestore():
    cred = credentials.Certificate("serviceAccountKey.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

def save_question(db, question_obj, source="user"):
    question_obj["source"] = source  # mark whether it's from AI or user
    db.collection("all_questions").add(question_obj)

def generate_ticket_id():
    """Generate a unique 6-character ticket ID"""
    import random
    import string
    
    # Generate a 6-character alphanumeric ID (uppercase for readability)
    ticket_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return ticket_id

def create_exit_ticket(db, questions, teacher_name, subject, lecture_topics, ticket_title=None):
    """
    Create an exit ticket with unique ID and store in Firestore
    
    Args:
        db: Firestore client
        questions: List of question objects
        teacher_name: Name of the teacher creating the ticket
        subject: Subject of the lecture
        lecture_topics: Topics covered in lecture
        ticket_title: Optional custom title for the ticket
    
    Returns:
        dict: Created ticket object with ticket_id
    """
    try:
        # Generate unique ticket ID
        ticket_id = generate_ticket_id()
        
        # Check if ticket ID already exists (very unlikely but good practice)
        while ticket_exists(db, ticket_id):
            ticket_id = generate_ticket_id()
        
        # Create ticket object
        ticket = {
            "ticket_id": ticket_id,
            "title": ticket_title or f"{subject} Exit Ticket",
            "subject": subject,
            "lecture_topics": lecture_topics,
            "teacher_name": teacher_name,
            "questions": questions,
            "created_at": datetime.now(),
            "total_questions": len(questions),
            "status": "active"  # Can be used later for deactivating tickets
        }
        
        # Store in Firestore with ticket_id as document ID
        db.collection("tickets").document(ticket_id).set(ticket)
        
        return ticket
        
    except Exception as e:
        print(f"Error creating exit ticket: {e}")
        return None

def ticket_exists(db, ticket_id):
    """Check if a ticket with given ID already exists"""
    try:
        doc = db.collection("tickets").document(ticket_id).get()
        return doc.exists
    except Exception as e:
        print(f"Error checking ticket existence: {e}")
        return False

def get_exit_ticket(db, ticket_id):
    """
    Retrieve an exit ticket by its ID
    
    Args:
        db: Firestore client
        ticket_id: Unique ticket identifier
    
    Returns:
        dict: Ticket object if found, None otherwise
    """
    try:
        # Convert ticket_id to uppercase for consistency
        ticket_id = ticket_id.upper().strip()
        
        doc = db.collection("tickets").document(ticket_id).get()
        
        if doc.exists:
            ticket_data = doc.to_dict()
            return ticket_data
        else:
            return None
            
    except Exception as e:
        print(f"Error retrieving exit ticket: {e}")
        return None

def get_all_tickets_by_teacher(db, teacher_name):
    """
    Get all tickets created by a specific teacher
    """
    try:
        # Updated syntax
        tickets_ref = db.collection("tickets") \
                       .where(filter=FieldFilter("teacher_name", "==", teacher_name)) \
                       .stream()
        
        tickets = []
        for doc in tickets_ref:
            ticket_data = doc.to_dict()
            tickets.append(ticket_data)
        
        tickets.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        return tickets
        
    except Exception as e:
        print(f"Error retrieving teacher's tickets: {e}")
        return []

# Alternative version if you want to try Firestore ordering (requires index)
def get_all_tickets_by_teacher_with_ordering(db, teacher_name):
    """
    Alternative version with Firestore ordering - requires composite index
    """
    try:
        tickets_ref = db.collection("tickets") \
                       .where("teacher_name", "==", teacher_name) \
                       .order_by("created_at", direction=firestore.Query.DESCENDING) \
                       .stream()
        
        tickets = []
        for doc in tickets_ref:
            ticket_data = doc.to_dict()
            tickets.append(ticket_data)
        
        return tickets
        
    except Exception as e:
        print(f"Error with ordered query: {e}")
        print("You may need to create a composite index in Firestore")
        print("Index needed: Collection: 'tickets', Fields: 'teacher_name' (Ascending), 'created_at' (Descending)")
        
        # Fallback to simple query
        return get_all_tickets_by_teacher(db, teacher_name)

def update_ticket_status(db, ticket_id, status):
    """
    Update the status of a ticket (e.g., 'active', 'inactive', 'expired')
    
    Args:
        db: Firestore client
        ticket_id: Unique ticket identifier
        status: New status for the ticket
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ticket_id = ticket_id.upper().strip()
        
        db.collection("tickets").document(ticket_id).update({
            "status": status,
            "updated_at": datetime.now()
        })
        
        return True
        
    except Exception as e:
        print(f"Error updating ticket status: {e}")
        return False

def delete_ticket(db, ticket_id):
    """
    Delete a ticket from the database
    
    Args:
        db: Firestore client
        ticket_id: Unique ticket identifier
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ticket_id = ticket_id.upper().strip()
        
        db.collection("tickets").document(ticket_id).delete()
        return True
        
    except Exception as e:
        print(f"Error deleting ticket: {e}")
        return False

def save_student_response(db, ticket_id, student_name, responses, score_data):
    """
    Save student's exit ticket responses to Firestore (with duplicate prevention)
    """
    try:
        ticket_id = ticket_id.upper().strip()
        student_name = student_name.strip()
        
        # Check if student has already attempted this ticket
        if check_student_already_attempted(db, ticket_id, student_name):
            print(f"DEBUG: Student {student_name} has already attempted ticket {ticket_id}")
            return False  # Don't allow duplicate attempts
        
        # Convert integer keys to strings for Firestore compatibility
        string_responses = {str(k): v for k, v in responses.items()}
        
        # Create response document
        response_doc = {
            "ticket_id": ticket_id,
            "student_name": student_name,
            "responses": string_responses,
            "score": score_data,
            "completed_at": datetime.now(),
            "submission_id": str(uuid.uuid4())
        }
        
        # Store in student_responses collection
        doc_ref = db.collection("student_responses").add(response_doc)
        
        return True
        
    except Exception as e:
        print(f"ERROR in save_student_response: {e}")
        import traceback
        print(f"ERROR traceback: {traceback.format_exc()}")
        return False
    
def get_ticket_responses(db, ticket_id):
    """
    Get all student responses for a specific ticket
    """
    try:
        ticket_id = ticket_id.upper().strip()
        
        # Updated syntax
        responses_ref = db.collection("student_responses") \
                         .where(filter=FieldFilter("ticket_id", "==", ticket_id)) \
                         .stream()
        
        responses = []
        for doc in responses_ref:
            response_data = doc.to_dict()
            responses.append(response_data)
        
        responses.sort(key=lambda x: x.get('completed_at', datetime.min), reverse=True)
        return responses
        
    except Exception as e:
        print(f"Error retrieving ticket responses: {e}")
        return []

def get_student_response_history(db, student_name):
    """
    Get all exit ticket responses by a specific student
    """
    try:
        student_name = student_name.strip()
        
        # Updated syntax
        responses_ref = db.collection("student_responses") \
                         .where(filter=FieldFilter("student_name", "==", student_name)) \
                         .stream()
        
        responses = []
        for doc in responses_ref:
            response_data = doc.to_dict()
            responses.append(response_data)
        
        responses.sort(key=lambda x: x.get('completed_at', datetime.min), reverse=True)
        return responses
        
    except Exception as e:
        print(f"Error retrieving student response history: {e}")
        return []

def get_ticket_analytics(db, ticket_id):
    """
    Get analytics summary for a ticket (with duplicate prevention)
    
    Args:
        db: Firestore client
        ticket_id: The ticket ID
    
    Returns:
        dict: Analytics data
    """
    try:
        responses = get_ticket_responses(db, ticket_id)
        
        if not responses:
            return {
                "total_responses": 0,
                "average_score": 0,
                "completion_rate": 0,
                "unique_students": 0,
                "responses": []
            }
        
        # Remove duplicates by keeping only the latest response per student
        unique_responses = {}
        for resp in responses:
            student_name = resp.get('student_name', '').strip()
            completed_at = resp.get('completed_at', datetime.min)
            
            # Keep only the latest response for each student
            if student_name not in unique_responses:
                unique_responses[student_name] = resp
            else:
                # Compare timestamps and keep the latest
                existing_time = unique_responses[student_name].get('completed_at', datetime.min)
                if completed_at > existing_time:
                    unique_responses[student_name] = resp
        
        # Convert back to list
        filtered_responses = list(unique_responses.values())
        
        # Calculate analytics on unique responses
        total_responses = len(filtered_responses)
        total_score = sum(resp.get('score', {}).get('percentage', 0) for resp in filtered_responses)
        average_score = total_score / total_responses if total_responses > 0 else 0
        
        # Count unique students
        unique_students = len(unique_responses)
        
        return {
            "total_responses": total_responses,
            "unique_students": unique_students,
            "average_score": round(average_score, 1),
            "responses": filtered_responses
        }
        
    except Exception as e:
        print(f"Error calculating ticket analytics: {e}")
        return {
            "total_responses": 0, 
            "average_score": 0, 
            "completion_rate": 0,
            "unique_students": 0,
            "responses": []
        }

def check_student_already_attempted(db, ticket_id, student_name):
    """
    Check if a student has already attempted a specific exit ticket
    
    Args:
        db: Firestore client
        ticket_id: Unique ticket identifier
        student_name: Name of the student
    
    Returns:
        bool: True if student has already attempted, False otherwise
    """
    try:
        ticket_id = ticket_id.upper().strip()
        student_name = student_name.strip()
        
        # Query for existing responses from this student for this ticket
        responses_ref = db.collection("student_responses") \
                         .where(filter=FieldFilter("ticket_id", "==", ticket_id)) \
                         .where(filter=FieldFilter("student_name", "==", student_name)) \
                         .limit(1) \
                         .stream()
        
        # Check if any document exists
        for doc in responses_ref:
            return True  # Student has already attempted
        
        return False  # Student hasn't attempted yet
        
    except Exception as e:
        print(f"Error checking student attempt: {e}")
        return False  # On error, allow attempt (fail-safe)

def get_ticket_stats(db, ticket_id):
    """
    Get basic statistics for a ticket (for future use)
    
    Args:
        db: Firestore client
        ticket_id: Unique ticket identifier
    
    Returns:
        dict: Ticket statistics
    """
    try:
        ticket = get_exit_ticket(db, ticket_id)
        
        if ticket:
            return {
                "ticket_id": ticket_id,
                "title": ticket.get("title", ""),
                "subject": ticket.get("subject", ""),
                "total_questions": ticket.get("total_questions", 0),
                "created_at": ticket.get("created_at", ""),
                "status": ticket.get("status", "unknown")
            }
        else:
            return None
            
    except Exception as e:
        print(f"Error getting ticket stats: {e}")
        return None 
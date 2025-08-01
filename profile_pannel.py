import streamlit as st
from firebase_admin import auth
from firebase_config import init_firebase

db = init_firebase()

# --- Admin Auth (simple, hardcoded) ---
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "supersecret"

def admin_login():
    st.title("🔐 Admin Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state.admin_logged_in = True
            st.rerun()  # <-- use experimental_rerun()
        else:
            st.error("Invalid admin credentials.")

def create_user_account():
    st.title("👤 Create New User")

    email = st.text_input("User Email")
    password = st.text_input("User Password", type="password")
    role = st.selectbox("Select Role", ["Student", "Teacher"])

    if st.button("Create Account"):
        try:
            user = auth.create_user(email=email, password=password)  # Correct usage
            # Add user role to Firestore
            db.collection("users").document(user.uid).set({
                "email": email,
                "role": role
            })
            st.success(f"✅ User created with role: {role}")
        except Exception as e:
            st.error(f"❌ Error: {e}")

def main():
    if not st.session_state.get("admin_logged_in", False):
        admin_login()
    else:
        create_user_account()

if __name__ == "__main__":
    main()

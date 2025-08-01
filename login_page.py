import streamlit as st
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin once
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

API_KEY = st.secrets["firebase"]["apiKey"]

def firebase_sign_in(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    res = requests.post(url, json=payload)
    if res.status_code == 200:
        return res.json()
    return None

def get_role(uid):
    doc = db.collection("users").document(uid).get()
    if doc.exists:
        data = doc.to_dict()
        return data.get("role", "Student")
    return "Student"

def login():
    st.title("🔐 Login Portal")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = firebase_sign_in(email, password)
        if user:
            uid = user["localId"]
            role = get_role(uid)

            st.session_state.logged_in = True
            st.session_state.username = email
            st.session_state.role = role
            st.session_state.user = {
                "email": email,
                "uid": uid,
                "role": role
            }

            st.success(f"✅ Logged in as {role}: {email}")
            st.rerun()
        else:
            st.error("❌ Invalid email or password.")

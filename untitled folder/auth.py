import streamlit as st
import database
import time

def render_auth_widget():
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            submit = st.form_submit_button("Login", use_container_width=True)
            if submit:
                user = database.authenticate_user(email, password)
                if user:
                    st.session_state.user = user
                    st.success("Success!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    with tab2:
        with st.form("signup_form"):
            new_email = st.text_input("New Email", key="signup_email")
            new_password = st.text_input("New Password", type="password", key="signup_pass")
            submit_signup = st.form_submit_button("Create Account", use_container_width=True)
            if submit_signup:
                if not new_email or not new_password:
                    st.error("Fill in all fields.")
                else:
                    if database.create_user(new_email, new_password):
                        st.success("Created! Please log in.")
                    else:
                        st.error("Email exists.")
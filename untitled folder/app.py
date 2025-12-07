import streamlit as st
from google import genai
import config
import database
import state
import ui
import logic

# 1. Setup
st.set_page_config(layout="wide", page_title="Gemini Tree Chat")
database.init_db()
state.init_session_state()

# 2. Check API
if not config.API_KEY:
    st.error("⚠️ GEMINI_API_KEY not found in .env file.")
    st.stop()

try:
    client = genai.Client(api_key=config.API_KEY)
except Exception as e:
    st.error(f"Error initializing Client: {e}")
    st.stop()

# 3. Render UI
ui.inject_custom_js()
ui.render_top_bar()
ui.render_sidebar(client)
ui.render_chat_history()

# 4. Logic Loops
logic.process_branching(client)

if prompt := st.chat_input("Type a message..."):
    with st.chat_message("user"): st.write(prompt)
    if logic.handle_response(client, prompt):
        st.rerun()
import streamlit as st
import config
import database
from classes import ChatNode

def init_session_state():
    if "user" not in st.session_state:
        st.session_state.user = None
        
    if "total_input_tokens" not in st.session_state:
        st.session_state.total_input_tokens = 0
    if "total_output_tokens" not in st.session_state:
        st.session_state.total_output_tokens = 0
        
    if "total_cost" not in st.session_state:
        if st.session_state.user:
            st.session_state.total_cost = st.session_state.user["total_cost"]
        else:
            st.session_state.total_cost = 0.0

    if "root" not in st.session_state:
        st.session_state.root = ChatNode("system", "Start of Conversation")
        st.session_state.current_node = st.session_state.root
        
    if "selected_model_key" not in st.session_state:
        st.session_state.selected_model_key = config.DEFAULT_MODEL_KEY

    if "generation_seed" not in st.session_state:
        st.session_state.generation_seed = 42 # Default seed
    
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.7
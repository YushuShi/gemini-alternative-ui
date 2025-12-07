import streamlit as st
import config
from classes import ChatNode
from utils import track_usage

def handle_response(client, prompt_text=None):
    """
    Generates response from Gemini.
    If prompt_text is provided, it creates a USER node first.
    If not (re-running logic), it assumes node exists.
    """
    if prompt_text:
        u_node = ChatNode("user", prompt_text, parent=st.session_state.current_node)
        st.session_state.current_node.add_child(u_node)
        st.session_state.current_node = u_node

    model_key = st.session_state.selected_model_key
    model_id = config.MODELS[model_key]["id"]
    model_pricing = config.MODELS[model_key]["pricing"]
    
    with st.spinner(f"{model_key} is thinking..."):
        try:
            full_context, _ = st.session_state.current_node.get_history()
            api_msgs = [m for m in full_context if m.role != "system"]
            
            resp = client.models.generate_content(model=model_id, contents=api_msgs)
            track_usage(resp, model_pricing) 
            
            a_node = ChatNode("model", resp.text, parent=st.session_state.current_node)
            st.session_state.current_node.add_child(a_node)
            st.session_state.current_node = a_node
            return True
        except Exception as e:
            st.error(f"Error: {e}")
            return False

def process_branching(client):
    """Checks URL query params for branch triggers."""
    if "branch_text" in st.query_params:
        if "processed_branch" not in st.session_state:
            branch_text = st.query_params["branch_text"]
            st.session_state.processed_branch = branch_text
            
            # Clean params
            p = dict(st.query_params)
            p.pop("branch_text", None)
            st.query_params.clear()
            for k, v in p.items(): st.query_params[k] = v

            prompt = f"Please explain {branch_text}"
            with st.chat_message("user"): st.write(prompt)
            
            if handle_response(client, prompt):
                del st.session_state.processed_branch
                st.rerun()
            else:
                if "processed_branch" in st.session_state: del st.session_state.processed_branch
        else:
            # Clean up if stuck
            p = dict(st.query_params)
            p.pop("branch_text", None)
            st.query_params.clear()
            for k, v in p.items(): st.query_params[k] = v
            if "processed_branch" in st.session_state: del st.session_state.processed_branch
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
            
            # Use seed and temperature
            from google.genai import types
            gen_config = types.GenerateContentConfig(
                temperature=st.session_state.get("temperature", 0.7),
                seed=int(st.session_state.get("generation_seed", 42))
            )

            resp = client.models.generate_content(
                model=model_id, 
                contents=api_msgs, 
                config=gen_config
            )
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
            for k, v in p.items(): st.query_params[k] = v
            if "processed_branch" in st.session_state: del st.session_state.processed_branch

def process_url_actions():
    """Handles deletion and navigation events from custom JS."""
    rerun_needed = False
    
    # 1. Deletion
    if "delete_node_id" in st.query_params:
        target_id = st.query_params["delete_node_id"]
        # Find node
        target_node = st.session_state.root.find_node(target_id)
        if target_node and target_node.parent:
            # Remove from parent
            target_node.parent.remove_child(target_node)
            
            # If deleted node was in current path, reset to parent
            # Check if current_node is descendant
            curr = st.session_state.current_node
            is_descendant = False
            while curr:
                if curr.id == target_id:
                    is_descendant = True
                    break
                curr = curr.parent
            
            if is_descendant:
                st.session_state.current_node = target_node.parent
            
            st.success("Analysis branch deleted.")
            rerun_needed = True
        
        # Clean param
        p = dict(st.query_params)
        p.pop("delete_node_id", None)
        st.query_params.clear()
        for k, v in p.items(): st.query_params[k] = v

    # 2. Navigation
    if "navigate_node_id" in st.query_params:
        target_id = st.query_params["navigate_node_id"]
        target_node = st.session_state.root.find_node(target_id)
        if target_node:
            st.session_state.current_node = target_node
            st.session_state.show_full_history = False
            rerun_needed = True

        # Clean param
        p = dict(st.query_params)
        p.pop("navigate_node_id", None)
        st.query_params.clear()
        for k, v in p.items(): st.query_params[k] = v

    if rerun_needed:
        st.rerun()
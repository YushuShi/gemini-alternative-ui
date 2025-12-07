import streamlit as st
from google.genai import types
import config
import database
import auth
from utils import track_usage, is_main_branch

# --- JAVASCRIPT INJECTION ---
def inject_custom_js():
    st.markdown("""
    <script>
    (function() {
        'use strict';
        function init() {
            let selectedText = '';
            let lastSelectionTime = 0;
            document.addEventListener('mouseup', () => {
                 const txt = window.getSelection().toString().trim();
                 if(txt) { selectedText = txt; lastSelectionTime = Date.now(); window.lastSelectedText = txt; window.lastSelectionTime = lastSelectionTime; }
            }, true);
            document.addEventListener('keydown', function(e) {
                const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
                const modifier = isMac ? e.metaKey : e.ctrlKey;
                if (modifier && (e.key === 'Enter' || e.keyCode === 13)) {
                    let text = window.getSelection().toString().trim();
                    if (!text && window.lastSelectedText && (Date.now() - window.lastSelectionTime < 10000)) {
                        text = window.lastSelectedText;
                    }
                    if (text) {
                        e.preventDefault(); e.stopPropagation();
                        const url = window.location.href.split('?')[0] + '?branch_text=' + encodeURIComponent(text);
                        window.location.href = url;
                    }
                }
            }, true);
        }
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
        else init();
    })();
    </script>
    """, unsafe_allow_html=True)

# --- RECURSIVE TREE RENDERER ---
def render_tree_sidebar(node, depth=0, is_last=True, prefix="", parent=None, sibling_index=0, root=None, skip_render=False):
    if node.role == "system":
        root_node = node
        for i, child in enumerate(node.children):
            render_tree_sidebar(child, depth, i==len(node.children)-1, "", node, i, root_node)
        return
    
    if skip_render:
        for i, child in enumerate(node.children):
            render_tree_sidebar(child, depth+1, i==len(node.children)-1, "", node, i, root, False)
        return
    
    if root is None: root = st.session_state.root
    
    model_child = None
    if node.role == "user" and node.children:
        for child in node.children:
            if child.role == "model":
                model_child = child
                break
    
    is_main = is_main_branch(node, depth, parent, sibling_index, root)
    branch_badge = "📌 main" if is_main else "🌿 branch"
    
    # Label formatting
    max_length = 25
    if model_child:
        q = node.content.replace('\n', ' ').strip()
        combined_label = f"Q: {q[:max_length]}..."
        target_node = model_child
    else:
        l = node.content.replace('\n', ' ').strip()
        combined_label = f"{l[:max_length]}..."
        target_node = node
    
    # Question Number
    q_num = node.get_question_label()
    if q_num:
        combined_label = f"**{q_num}** {combined_label}"

    is_active = (st.session_state.current_node.id == node.id or 
                 (model_child and st.session_state.current_node.id == model_child.id))
    
    role_color = "#9C27B0" if model_child else ("#4285F4" if node.role == "model" else "#34A853")
    
    if is_active:
        st.markdown(f"""
        <div style="background-color: rgba(66, 133, 244, 0.1); padding: 4px 8px; border-radius: 6px; 
                    border-left: 3px solid {role_color}; margin: 2px 0; color: var(--text-color);">
            <div style="font-size: 0.7em; opacity: 0.6;">{branch_badge}</div>
            <div style="font-size: 0.85em;">{combined_label}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        if st.button(f"{combined_label}", key=f"tree_{target_node.id}", use_container_width=True, type="secondary"):
            st.session_state.current_node = target_node
            st.rerun()
    
    if model_child:
        for i, child in enumerate(model_child.children):
            render_tree_sidebar(child, depth+1, i==len(model_child.children)-1, "", model_child, i, root, False)
    else:
        for i, child in enumerate(node.children):
            skip = (node.role == "user" and child.role == "model")
            render_tree_sidebar(child, depth+1, i==len(node.children)-1, "", node, i, root, skip)

# --- LAYOUT COMPONENTS ---
def render_top_bar():
    col_header, col_auth = st.columns([10, 1.5])
    with col_header:
        st.title(f"Chat: {st.session_state.selected_model_key}")
    with col_auth:
        if st.session_state.user:
            with st.popover(f"👤 {st.session_state.user['email'].split('@')[0]}"):
                st.caption(f"Logged in as: {st.session_state.user['email']}")
                if st.button("Log out", use_container_width=True):
                    st.session_state.user = None
                    st.session_state.total_cost = 0.0
                    st.rerun()
        else:
            with st.popover("Sign In"):
                st.markdown("#### Welcome!")
                st.caption("Sign in to save history.")
                auth.render_auth_widget()

def render_sidebar(client):
    with st.sidebar:
        st.header("Gemini Tree Chat")
        st.divider()
        
        tab_tree, tab_settings = st.tabs(["🌳 Tree", "⚙️ Settings"])
        
        with tab_tree:
            with st.container():
                render_tree_sidebar(st.session_state.root)
            st.divider()
            with st.expander("💰 Cost Estimator", expanded=True):
                current_cost = st.session_state.total_cost
                label = "Lifetime (User)" if st.session_state.user else "Session (Guest)"
                if st.session_state.user:
                    current_cost = database.get_user_cost(st.session_state.user["email"])
                
                st.metric("Input Tokens", f"{st.session_state.total_input_tokens:,}")
                st.metric("Output Tokens", f"{st.session_state.total_output_tokens:,}")
                st.metric(label, f"${current_cost:.6f}")

        with tab_settings:
            st.subheader("Model Configuration")
            selected_key = st.radio("Select Model", options=list(config.MODELS.keys()),
                                    index=list(config.MODELS.keys()).index(st.session_state.selected_model_key))
            st.session_state.selected_model_key = selected_key
            
            info = config.MODELS[selected_key]
            st.info(f"ID: `{info['id']}`")
            st.write(f"Input: **${info['pricing']['INPUT_PER_1M']}**")
            st.write(f"Output: **${info['pricing']['OUTPUT_PER_1M']}**")

        st.divider()
        st.subheader("🔍 Manual Search")
        search_query = st.text_input("Google Query")
        if st.button("Search Google"):
            try:
                model_key = st.session_state.selected_model_key
                info = config.MODELS[model_key]
                response = client.models.generate_content(
                    model=info["id"], contents=search_query,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        response_mime_type="text/plain"
                    )
                )
                track_usage(response, info["pricing"])
                st.info(response.text)
                if response.candidates[0].grounding_metadata.grounding_chunks:
                    for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                        st.write(f"- [{chunk.web.title}]({chunk.web.uri})")
            except Exception as e:
                st.error(f"Search failed: {e}")

def render_chat_history():
    history, history_nodes = st.session_state.current_node.get_history()
    
    for i, msg in enumerate(history):
        if msg.role != "system":
            node = history_nodes[i] if i < len(history_nodes) else None
            
            # Formatting
            header_elements = []
            if node:
                q_num = node.get_question_label()
                if q_num: header_elements.append(f"**{q_num}.**")
                
                is_main = is_main_branch(node, 0, None, 0, st.session_state.root)
                badge = "📌 main" if is_main else "🌿 branch"
                header_elements.append(f"<span style='font-size:0.8em;opacity:0.6'>{badge}</span>")

            with st.chat_message(msg.role):
                txt = "".join([p.text for p in msg.parts if p.text])
                if header_elements:
                    st.markdown(f"{' '.join(header_elements)} {txt}", unsafe_allow_html=True)
                else:
                    st.write(txt)
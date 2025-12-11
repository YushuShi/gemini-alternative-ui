import streamlit as st
from google.genai import types
import config
import database
import auth
from utils import track_usage, is_main_branch
from classes import ChatNode

# --- JAVASCRIPT INJECTION ---
def inject_custom_js():
    st.markdown("""
<style>
.tree-node {
    padding: 4px 8px;
    margin: 2px 0;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-size: 14px;
    transition: background-color 0.2s;
}
.tree-node:hover {
    background-color: var(--background-color-secondary, #f0f2f6);
}
.tree-node.active {
    background-color: rgba(66, 133, 244, 0.1);
    color: var(--text-color);
}
/* Context Menu */
#custom-context-menu {
    display: none;
    position: fixed;
    z-index: 999999;
    background: white;
    border: 1px solid #ccc;
    border-radius: 5px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
    padding: 5px 0;
    min-width: 150px;
    font-family: sans-serif;
    font-size: 14px;
}
#custom-context-menu div {
    padding: 8px 15px;
    cursor: pointer;
    color: #333;
}
#custom-context-menu div:hover {
    background-color: #eee;
}
</style>
<div id="custom-context-menu">
    <div onclick="window.handleDeleteNode()">🗑️ Delete Branch</div>
</div>
<script>
(function() {
    'use strict';
    let contextNodeId = null; 

    window.showContextMenu = function(e, nodeId) {
        e.preventDefault();
        contextNodeId = nodeId;
        const menu = document.getElementById('custom-context-menu');
        if (menu) {
            menu.style.display = 'block';
            menu.style.left = e.pageX + 'px';
            menu.style.top = e.pageY + 'px';
        }
    };

    window.handleDeleteNode = function() {
        if (contextNodeId) {
            // Confirm?
            if(confirm("Delete this branch and all its children?")) {
                const url = window.location.href.split('?')[0] + '?delete_node_id=' + contextNodeId;
                window.location.href = url;
            }
            const menu = document.getElementById('custom-context-menu');
            if(menu) menu.style.display = 'none';
        }
    };

    window.navigateTo = function(nodeId) {
            const url = window.location.href.split('?')[0] + '?navigate_node_id=' + nodeId;
            window.location.href = url;
    }

    // Close menu on click anywhere
    document.addEventListener('click', function(e) {
        const menu = document.getElementById('custom-context-menu');
        if (menu && menu.style.display === 'block') {
            menu.style.display = 'none';
        }
    });

    function init() {
        // Text selection listener for branching
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
                    if (!text.startsWith('?')) {
                            const url = window.location.href.split('?')[0] + '?branch_text=' + encodeURIComponent(text);
                            window.location.href = url;
                    }
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
def render_tree_sidebar(node, depth=0, is_last=True, prefix="", parent=None, sibling_index=0, root=None, skip_render=False, active_path_ids=None):
    if active_path_ids is None:
        active_path_ids = set()
        if "current_node" in st.session_state and st.session_state.current_node:
            curr = st.session_state.current_node
            while curr:
                active_path_ids.add(curr.id)
                curr = curr.parent
    if node.role == "system":
        root_node = node
        for i, child in enumerate(node.children):
            render_tree_sidebar(child, depth, i==len(node.children)-1, "", node, i, root_node, False, active_path_ids)
        return
    
    if skip_render:
        for i, child in enumerate(node.children):
            render_tree_sidebar(child, depth+1, i==len(node.children)-1, "", node, i, root, False, active_path_ids)
        return
    
    if root is None: root = st.session_state.root
    
    model_child = None
    if node.role == "user" and node.children:
        for child in node.children:
            if child.role == "model":
                model_child = child
                break
    
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
        combined_label = f"{q_num} {combined_label}"

    is_active = (st.session_state.current_node.id == node.id or 
                 (model_child and st.session_state.current_node.id == model_child.id))
    
    role_color = "#9C27B0" if model_child else ("#4285F4" if node.role == "model" else "#34A853")
    
    
    # Pin Logic: Show pin if this node (or the paired model node) is in the active path BUT is not the active node itself
    # This implies it is a "question for the next question" (an ancestor).
    should_pin = False
    if not is_active:
        if node.id in active_path_ids:
            should_pin = True
        elif model_child and model_child.id in active_path_ids:
            should_pin = True
            
    if should_pin:
        combined_label = f"📌 {combined_label}"

    # HTML Rendering for Context Menu support
    text_color = "var(--text-color)"
    bg_style = ""
    border_style = ""
    
    if is_active:
        bg_style = "background-color: rgba(66, 133, 244, 0.1);"
        border_style = f"border-left: 3px solid {role_color};"
    else:
        # Use a subtle border for non-active to keep alignment
        pass

    html_block = f"""
    <div class="tree-node {'active' if is_active else ''}" 
         style="{bg_style} {border_style} color: {text_color};"
         oncontextmenu="window.showContextMenu(event, '{target_node.id}')"
         onclick="window.navigateTo('{target_node.id}')">
        {combined_label}
    </div>
    """
    st.markdown(html_block, unsafe_allow_html=True)
    
    if model_child:
        for i, child in enumerate(model_child.children):
            render_tree_sidebar(child, depth+1, i==len(model_child.children)-1, "", model_child, i, root, False, active_path_ids)
    else:
        for i, child in enumerate(node.children):
            skip = (node.role == "user" and child.role == "model")
            render_tree_sidebar(child, depth+1, i==len(node.children)-1, "", node, i, root, skip, active_path_ids)

# --- RECURSIVE TREE RENDERER ---
def render_tree_sidebar(node, depth=0, is_last=True, prefix="", parent=None, sibling_index=0, root=None, skip_render=False, active_path_ids=None):
    if active_path_ids is None:
        active_path_ids = set()
        if "current_node" in st.session_state and st.session_state.current_node:
            curr = st.session_state.current_node
            while curr:
                active_path_ids.add(curr.id)
                curr = curr.parent
    if node.role == "system":
        root_node = node
        for i, child in enumerate(node.children):
            render_tree_sidebar(child, depth, i==len(node.children)-1, "", node, i, root_node, False, active_path_ids)
        return
    
    if skip_render:
        for i, child in enumerate(node.children):
            render_tree_sidebar(child, depth+1, i==len(node.children)-1, "", node, i, root, False, active_path_ids)
        return
    
    if root is None: root = st.session_state.root
    
    model_child = None
    if node.role == "user" and node.children:
        for child in node.children:
            if child.role == "model":
                model_child = child
                break
    
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
        combined_label = f"{q_num} {combined_label}"

    is_active = (st.session_state.current_node.id == node.id or 
                 (model_child and st.session_state.current_node.id == model_child.id))
    
    role_color = "#9C27B0" if model_child else ("#4285F4" if node.role == "model" else "#34A853")
    
    
    # Pin Logic: Show pin if this node (or the paired model node) is in the active path BUT is not the active node itself
    # This implies it is a "question for the next question" (an ancestor).
    should_pin = False
    if not is_active:
        if node.id in active_path_ids:
            should_pin = True
        elif model_child and model_child.id in active_path_ids:
            should_pin = True
            
    if should_pin:
        combined_label = f"📌 {combined_label}"

    # Layout: [Navigation Button] [Delete Button]
    # Use columns to position them side-by-side
    col1, col2 = st.columns([0.85, 0.15])
    
    with col1:
        # Use type="primary" if active to highlight, otherwise secondary
        btn_type = "primary" if is_active else "secondary"
        # We can't easily style the button background to exactly match the design, 
        # but type="primary" gives a visual cue.
        if st.button(combined_label, key=f"nav_{target_node.id}", use_container_width=True, type=btn_type):
            st.session_state.current_node = target_node
            st.session_state.show_full_history = False
            st.rerun()
            
    with col2:
        # Only show delete for non-root (system) nodes
        if target_node.role != "system" and target_node.parent:
            if st.button("🗑️", key=f"del_{target_node.id}", help="Delete this branch"):
                # Perform deletion
                parent = target_node.parent
                if parent.remove_child(target_node):
                    # Reset current_node if we deleted the active branch
                    curr = st.session_state.current_node
                    # Check if deleted node is an ancestor of current
                    temp = curr
                    is_descendant = False
                    while temp:
                        if temp.id == target_node.id:
                            is_descendant = True
                            break
                        temp = temp.parent
                    
                    if is_descendant:
                        st.session_state.current_node = parent
                    
                    st.success("Deleted!")
                    st.rerun()

    if model_child:
        for i, child in enumerate(model_child.children):
            render_tree_sidebar(child, depth+1, i==len(model_child.children)-1, "", model_child, i, root, False, active_path_ids)
    else:
        for i, child in enumerate(node.children):
            skip = (node.role == "user" and child.role == "model")
            render_tree_sidebar(child, depth+1, i==len(node.children)-1, "", node, i, root, skip, active_path_ids)

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
        st.header("Conversation Tree")
        
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            # Instead of wiping the tree (st.session_state.root = new node),
            # we simply go back to the root node. This allows a new conversation branch to start
            # while keeping the existing branches visible in the sidebar.
            st.session_state.current_node = st.session_state.root
            st.session_state.show_full_history = False
            st.rerun()

        st.divider()
        
        tab_tree, tab_settings = st.tabs(["🌳 Tree", "⚙️ Settings"])
        
        with tab_tree:
            with st.container():
                render_tree_sidebar(st.session_state.root)
            st.divider()

            with st.expander("�️ Previous Conversations"):
                if not st.session_state.user:
                    st.info("Log in to save/view history.")
                else:
                    if st.button("💾 Save Current", use_container_width=True):
                         database.save_conversation(st.session_state.user["email"], st.session_state.root)
                         st.success("Saved!")
                    
                    st.divider()
                    conversations = database.get_user_conversations(st.session_state.user["email"])
                    if not conversations:
                        st.caption("No saved conversations.")
                    
                    for cid, title, updated_at in conversations:
                        col1, col2 = st.columns([0.85, 0.15])
                        with col1:
                            if st.button(f"{title}\n{updated_at[:16]}", key=cid, use_container_width=True):
                                 if st.session_state.root.children:
                                     database.save_conversation(st.session_state.user["email"], st.session_state.root)
                                 
                                 loaded_node = database.load_conversation(cid)
                                 if loaded_node:
                                     st.session_state.root = loaded_node
                                     st.session_state.current_node = loaded_node
                                     st.session_state.show_full_history = False
                                     st.rerun()
                        with col2:
                            pass # Delete placeholder

            with st.expander("💰 Cost Estimator", expanded=False):
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
            st.subheader("Generation Parameters")
            st.session_state.temperature = st.slider("Temperature", min_value=0.0, max_value=2.0, value=st.session_state.temperature, step=0.1)
            
            # Seed input - use text_input for potentially large integers or number_input
            # number_input with step=1 enforces integer
            st.session_state.generation_seed = int(st.number_input("Random Seed", value=st.session_state.generation_seed, step=1, min_value=0))

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

    # --- FOLDING LOGIC ---
    if "show_full_history" not in st.session_state:
        st.session_state.show_full_history = False

    start_index = 0
    non_system_msgs = [m for m in history if m.role != "system"]
    
    # If we have interactions and folding is enabled
    if len(non_system_msgs) > 0 and not st.session_state.show_full_history:
        # Determine how many messages to show at the end
        # If last is model, we want to show (User, Model) -> 2 messages
        # If last is user, we want to show (User) -> 1 message
        last_role = non_system_msgs[-1].role
        target_show_count = 2 if last_role == "model" else 1
        
        # Find the start_index that leaves 'target_show_count' messages
        count = 0
        for i in range(len(history) - 1, -1, -1):
            if history[i].role != "system":
                count += 1
            if count == target_show_count:
                start_index = i
                break
        
        # Determine how many are hidden
        hidden_count = sum(1 for m in history[:start_index] if m.role != "system")
        
        if hidden_count > 0:
            if st.button(f"Show previous {hidden_count} messages (Unfold)", key="unfold_btn"):
                st.session_state.show_full_history = True
                st.rerun()
    
    for i in range(start_index, len(history)):
        msg = history[i]
        if msg.role != "system":
            node = history_nodes[i] if i < len(history_nodes) else None
            
            # Formatting
            header_elements = []
            if node:
                q_num = node.get_question_label()
                if q_num: header_elements.append(f"**{q_num}.**")
                
                # Badge removed as requested by user
                # is_main = is_main_branch(node, 0, None, 0, st.session_state.root)
                # badge = "📌 main" if is_main else "🌿 branch"
                # header_elements.append(f"<span style='font-size:0.8em;opacity:0.6'>{badge}</span>")

            with st.chat_message(msg.role):
                txt = "".join([p.text for p in msg.parts if p.text])
                if header_elements:
                    st.markdown(f"{' '.join(header_elements)} {txt}", unsafe_allow_html=True)
                else:
                    st.write(txt)
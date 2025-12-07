import os
import streamlit as st
from google import genai
from google.genai import types
import uuid
from dotenv import load_dotenv

# --- CONFIGURATION & PRICING ---
load_dotenv()

# Pricing (USD per 1 million tokens) - Based on generic Flash tier pricing
PRICING = {
    "INPUT_PER_1M": 0.075,  # $0.075 per 1M input tokens
    "OUTPUT_PER_1M": 0.30,  # $0.30 per 1M output tokens
}

API_KEY = os.getenv("GEMINI_API_KEY")

# --- SESSION STATE INITIALIZATION ---
if "total_input_tokens" not in st.session_state:
    st.session_state.total_input_tokens = 0
if "total_output_tokens" not in st.session_state:
    st.session_state.total_output_tokens = 0
if "total_cost" not in st.session_state:
    st.session_state.total_cost = 0.0

if not API_KEY:
    st.set_page_config(page_title="Gemini Tree Chat")
    st.error("⚠️ GEMINI_API_KEY not found. Please set it in your .env file.")
    st.stop()

MODEL_ID = "gemini-2.0-flash"

try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    st.error(f"Error initializing Client: {e}")
    st.stop()

# --- HELPER: COST CALCULATOR ---
def track_usage(response):
    """Extracts token counts and updates session cost."""
    try:
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count or 0
            output_tokens = usage.candidates_token_count or 0
            
            st.session_state.total_input_tokens += input_tokens
            st.session_state.total_output_tokens += output_tokens
            
            input_cost = (input_tokens / 1_000_000) * PRICING["INPUT_PER_1M"]
            output_cost = (output_tokens / 1_000_000) * PRICING["OUTPUT_PER_1M"]
            st.session_state.total_cost += (input_cost + output_cost)
    except Exception as e:
        print(f"Error tracking usage: {e}")

# --- DATA STRUCTURES ---
class ChatNode:
    def __init__(self, role, content, parent=None):
        self.id = str(uuid.uuid4())[:8]
        self.role = role
        self.content = content
        self.parent = parent
        self.children = []
        self.timestamp = str(uuid.uuid1())

    def add_child(self, node):
        self.children.append(node)
        return node

    def get_history(self):
        history = []
        nodes = []
        current = self
        while current:
            history.insert(0, types.Content(
                role=current.role,
                parts=[types.Part(text=current.content)]
            ))
            nodes.insert(0, current)
            current = current.parent
        return history, nodes

# --- TREE LOGIC HELPERS ---
def get_node_by_id(root, target_id):
    if root.id == target_id: return root
    for child in root.children:
        found = get_node_by_id(child, target_id)
        if found: return found
    return None

def is_main_branch(node, depth, parent=None, sibling_index=0, root=None):
    if parent is None or parent.role == "system":
        if root:
            root_children = [n for n in root.children if n.role != "system"]
            if root_children:
                most_recent = max(root_children, key=lambda n: n.timestamp)
                return node == most_recent
        return True
    
    if len(parent.children) > 1:
        most_recent_sibling = max(parent.children, key=lambda n: n.timestamp)
        if node == most_recent_sibling:
            if parent.parent:
                parent_sibling_idx = parent.parent.children.index(parent) if parent in parent.parent.children else 0
                return is_main_branch(parent, depth - 1, parent.parent, parent_sibling_idx, root)
            else:
                if root:
                    root_children = [n for n in root.children if n.role != "system"]
                    if root_children:
                        most_recent_root = max(root_children, key=lambda n: n.timestamp)
                        return parent == most_recent_root
                return True
        else:
            return False
    
    if parent.parent:
        parent_sibling_idx = parent.parent.children.index(parent) if parent in parent.parent.children else 0
        return is_main_branch(parent, depth - 1, parent.parent, parent_sibling_idx, root)
    else:
        if root:
            root_children = [n for n in root.children if n.role != "system"]
            if root_children:
                most_recent_root = max(root_children, key=lambda n: n.timestamp)
                return parent == most_recent_root
        return True

def render_tree_sidebar(node, depth=0, is_last=True, prefix="", parent=None, sibling_index=0, root=None, skip_render=False):
    if node.role == "system":
        root_node = node
        for i, child in enumerate(node.children):
            is_last_child = (i == len(node.children) - 1)
            render_tree_sidebar(child, depth, is_last_child, "", node, i, root_node)
        return
    
    if skip_render:
        for i, child in enumerate(node.children):
            is_last_child = (i == len(node.children) - 1)
            render_tree_sidebar(child, depth + 1, is_last_child, "", node, i, root, skip_render=False)
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
    
    max_length = 30
    if model_child:
        q = node.content.replace('\n', ' ').strip()
        a = model_child.content.replace('\n', ' ').strip()
        combined_label = f"Q: {q[:max_length]}... | A: {a[:max_length]}..."
        is_active = (st.session_state.current_node.id == node.id or 
                     st.session_state.current_node.id == model_child.id)
        target_node = model_child
    else:
        l = node.content.replace('\n', ' ').strip()
        combined_label = f"{l[:max_length]}..."
        is_active = st.session_state.current_node.id == node.id
        target_node = node
    
    role_color = "#9C27B0" if model_child else ("#4285F4" if node.role == "model" else "#34A853")
    
    if is_active:
        # DARK MODE FIX:
        # 1. Use var(--text-color) so text turns white in dark mode.
        # 2. Use rgba(..., 0.1) for background. This creates a faint tint that looks good on both White and Black backgrounds.
        st.markdown(f"""
        <div style="
            background-color: rgba(66, 133, 244, 0.1); 
            padding: 6px 8px; 
            border-radius: 6px; 
            border-left: 3px solid {role_color}; 
            margin: 2px 0;
            color: var(--text-color);
        ">
            <span style="font-size: 0.75em; opacity: 0.7;">{branch_badge}</span>
            <div style="font-size: 0.9em;">{combined_label}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Buttons automatically handle dark mode in Streamlit
        if st.button(f"{branch_badge} {combined_label}", key=f"tree_btn_{target_node.id}", use_container_width=True, type="secondary"):
            st.session_state.current_node = target_node
            st.rerun()
    
    if model_child:
        for i, child in enumerate(model_child.children):
            render_tree_sidebar(child, depth + 1, i==len(model_child.children)-1, "", model_child, i, root, False)
    else:
        for i, child in enumerate(node.children):
            skip = (node.role == "user" and child.role == "model")
            render_tree_sidebar(child, depth + 1, i==len(node.children)-1, "", node, i, root, skip)

# --- MAIN APP ---
st.set_page_config(layout="wide", page_title="Gemini Tree Chat")

if "root" not in st.session_state:
    st.session_state.root = ChatNode("system", "Start of Conversation")
    st.session_state.current_node = st.session_state.root

with st.sidebar:
    st.header("🌳 Conversation Tree")
    
    # --- COST CALCULATOR ---
    with st.expander("💰 Cost Estimator", expanded=True):
        col1, col2 = st.columns(2)
        col1.metric("Input Tokens", f"{st.session_state.total_input_tokens:,}")
        col2.metric("Output Tokens", f"{st.session_state.total_output_tokens:,}")
        st.metric("Estimated Cost", f"${st.session_state.total_cost:.6f}")
        if st.button("Reset Cost"):
            st.session_state.total_input_tokens = 0
            st.session_state.total_output_tokens = 0
            st.session_state.total_cost = 0.0
            st.rerun()

    st.divider()
    with st.container():
        render_tree_sidebar(st.session_state.root)
    
    st.divider()
    st.header("🔍 Manual Search")
    search_query = st.text_input("Google Query")
    if st.button("Search Google"):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=search_query,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    response_mime_type="text/plain"
                )
            )
            track_usage(response) 
            st.info(response.text)
            if response.candidates[0].grounding_metadata.grounding_chunks:
                for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                      st.write(f"- [{chunk.web.title}]({chunk.web.uri})")
        except Exception as e:
            st.error(f"Search failed: {e}")

st.title("Gemini Tree Chat")

# Javascript for Ctrl+Enter Branching
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

# Helper to get current display history
history, history_nodes = st.session_state.current_node.get_history()

def get_node_branch_label(node, root):
    if node.role == "system": return None
    depth = 0; p = node.parent; ap = p
    while p and p.role != "system": depth+=1; p=p.parent
    if ap and ap.role != "system": idx = ap.children.index(node) if node in ap.children else 0; pfc = ap
    else: rc = [n for n in root.children if n.role!="system"]; idx = rc.index(node) if node in rc else 0; pfc = None
    is_main = is_main_branch(node, depth, pfc, idx, root)
    return "📌 main" if is_main else "🌿 branch"

# Display Messages
for i, msg in enumerate(history):
    if msg.role != "system":
        node = history_nodes[i] if i < len(history_nodes) else None
        branch_label = get_node_branch_label(node, st.session_state.root) if node else None
        with st.chat_message(msg.role):
            txt = "".join([p.text for p in msg.parts if p.text])
            if branch_label: 
                # DARK MODE FIX: Use opacity instead of hardcoded color
                st.markdown(f"{txt} <span style='font-size: 0.8em; opacity: 0.6;'>{branch_label}</span>", unsafe_allow_html=True)
            else: 
                st.write(txt)

# Branch Logic
if "branch_text" in st.query_params:
    if "processed_branch" not in st.session_state:
        branch_text = st.query_params["branch_text"]
        st.session_state.processed_branch = branch_text
        
        p = dict(st.query_params); p.pop("branch_text", None); st.query_params.clear();
        for k, v in p.items(): st.query_params[k] = v

        prompt = f"Please explain {branch_text}"
        with st.chat_message("user"): st.write(prompt)
        
        u_node = ChatNode("user", prompt, parent=st.session_state.current_node)
        st.session_state.current_node.add_child(u_node)
        st.session_state.current_node = u_node

        with st.spinner("Gemini is thinking..."):
            try:
                full_context, _ = u_node.get_history()
                api_msgs = [m for m in full_context if m.role != "system"]
                resp = client.models.generate_content(model=MODEL_ID, contents=api_msgs)
                track_usage(resp) 
                
                with st.chat_message("model"): st.write(resp.text)
                
                a_node = ChatNode("model", resp.text, parent=st.session_state.current_node)
                st.session_state.current_node.add_child(a_node)
                st.session_state.current_node = a_node
                del st.session_state.processed_branch
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
                if "processed_branch" in st.session_state: del st.session_state.processed_branch
    else:
        p = dict(st.query_params); p.pop("branch_text", None); st.query_params.clear();
        for k, v in p.items(): st.query_params[k] = v
        if "processed_branch" in st.session_state: del st.session_state.processed_branch

# Main Input
if prompt := st.chat_input("Type a message..."):
    with st.chat_message("user"): st.write(prompt)
    u_node = ChatNode("user", prompt, parent=st.session_state.current_node)
    st.session_state.current_node.add_child(u_node)
    st.session_state.current_node = u_node

    with st.spinner("Thinking..."):
        try:
            full_context, _ = u_node.get_history()
            api_msgs = [m for m in full_context if m.role != "system"]
            resp = client.models.generate_content(model=MODEL_ID, contents=api_msgs)
            track_usage(resp)
            
            with st.chat_message("model"): st.write(resp.text)
            
            a_node = ChatNode("model", resp.text, parent=st.session_state.current_node)
            st.session_state.current_node.add_child(a_node)
            st.session_state.current_node = a_node
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
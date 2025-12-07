from nicegui import ui, app
import asyncio
from functools import partial
import os

# --- IMPORT MODULES ---
import config
import database
from classes import ChatNode
from state_manager import SessionState
import gemini_utils
import auth_ui

# --- INIT ---
database.init_db()
os.environ["NICEGUI_STORAGE_SECRET"] = "super_secret_key_123"

@ui.page('/')
def main_page():
    # 1. Setup State
    state = SessionState()
    state.initialize_from_storage()

    # --- UI RENDER FUNCTIONS ---
    
    @ui.refreshable
    def render_chat_area():
        current = state.current_node
        nodes_to_display = []

        # --- SELECTION LOGIC ---
        if current.role == "system":
            # If Root, show empty (System label handled below)
            pass
        elif current.role == "model":
            # If Answer selected: Show [Parent Question] + [This Answer]
            if current.parent and current.parent.role == "user":
                nodes_to_display.append(current.parent)
            nodes_to_display.append(current)
        elif current.role == "user":
            # If Question selected: Show [This Question] + [Child Answer (if exists)]
            nodes_to_display.append(current)
            model_children = [c for c in current.children if c.role == "model"]
            if model_children:
                nodes_to_display.append(model_children[-1])

        # --- RENDER CONTAINER ---
        # FIX: Changed 'h-full' to 'flex-grow' so it fills space without collapsing
        with ui.scroll_area().classes('w-full flex-grow bg-gray-100 p-6'):
            with ui.column().classes('w-full max-w-4xl mx-auto gap-6'):
                
                # Empty State
                if not nodes_to_display and current.role == "system":
                    with ui.column().classes('w-full h-full items-center justify-center opacity-50'):
                        ui.icon('chat_bubble_outline', size='4rem').classes('text-gray-400')
                        ui.label("Start a conversation by typing below!").classes('text-xl text-gray-400 font-bold')

                # Render Nodes
                for node in nodes_to_display:
                    q_label = node.get_question_label()
                    is_user = (node.role == "user")
                    
                    if is_user:
                        container_cls = 'w-full bg-blue-50 border border-blue-200 rounded-lg p-4 shadow-sm'
                        header_text = "👤 You"
                        header_cls = "text-blue-900 font-bold text-sm"
                    else:
                        container_cls = 'w-full bg-white border border-gray-300 rounded-lg p-6 shadow-md'
                        header_text = f"🤖 Gemini ({state.selected_model_key})"
                        header_cls = "text-green-800 font-bold text-sm"

                    with ui.column().classes(container_cls):
                        # Header
                        with ui.row().classes('items-center gap-2 mb-3 border-b border-gray-200 pb-2 w-full'):
                            ui.label(header_text).classes(header_cls)
                            if q_label:
                                ui.label(f"#{q_label}").classes('text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded')
                        
                        # Content
                        content_text = node.content if node.content else "..."
                        ui.markdown(content_text).classes('w-full text-lg leading-relaxed prose max-w-none text-gray-800')
            
            # Scroll Anchor
            ui.label('').classes('h-1').run_method('scrollIntoView')

    @ui.refreshable
    def render_sidebar_content():
        # A. Profile
        if state.user:
            with ui.row().classes('items-center justify-between w-full'):
                ui.label(f"👤 {state.user['email'].split('@')[0]}").classes('text-base font-bold')
                ui.button(on_click=logout, icon='logout').props('flat round dense')
        else:
            ui.button('Login / Sign Up', on_click=lambda: login_dialog.open()).props('width=100% color=primary')
        
        ui.separator().classes('q-my-md')

        # B. Cost
        with ui.expansion('💰 Cost Estimator', value=True).classes('w-full'):
            with ui.column().classes('gap-1'):
                ui.label(f"In: {state.total_input:,}").classes('text-sm text-gray-600')
                ui.label(f"Out: {state.total_output:,}").classes('text-sm text-gray-600')
                ui.label(f"Total: ${state.total_cost:.6f}").classes('font-bold text-base text-green-700')

        ui.separator().classes('q-my-md')
        
        # C. Drag & Drop
        active = state.current_node
        target_parent = None
        if active.role == "model" and active.parent and active.parent.role == "user":
            if active.parent.parent: target_parent = active.parent.parent
        elif active.role == "user" and active.parent:
             target_parent = active.parent
             
        if target_parent and len(target_parent.children) > 1:
            with ui.expansion('🔄 Reorder Questions', value=True).classes('w-full bg-orange-50 rounded'):
                ui.label('Drag to reorder:').classes('text-xs text-gray-500 q-mb-sm')
                
                def on_sort(e):
                    new_order = [int(x['id']) for x in e.args]
                    target_parent.reorder_children(new_order)
                    render_tree.refresh()
                    render_chat_area.refresh()
                    
                with ui.sortable(on_change=on_sort).classes('w-full gap-2'):
                    for idx, child in enumerate(target_parent.children):
                        if child.role == "user":
                            with ui.card().classes('cursor-move q-pa-sm w-full bg-white').props(f'key={idx} id={idx}'):
                                l = child.get_question_label() or "?"
                                ui.label(f"{l}: {child.content[:15]}...").classes('text-xs font-bold')

        ui.separator().classes('q-my-md')
        ui.label('History Tree').classes('text-h6 font-bold')
        render_tree()

    @ui.refreshable
    def render_tree():
        def draw_node(node, depth=0):
            if node.role == "system":
                for child in node.children: draw_node(child, depth)
                return

            is_active = (node == state.current_node) or (node.role == "user" and state.current_node in node.children)
            
            model_children = [child for child in node.children if child.role == "model"]
            model_child = model_children[-1] if model_children else None
            
            if node.role == "model": return 

            q_num = node.get_question_label()
            txt = node.content[:20].replace('\n','')
            label = f"**{q_num}** {txt}" if q_num else txt
            
            def on_click():
                target = node
                curr_children = [c for c in node.children if c.role == "model"]
                if curr_children: target = curr_children[-1]
                
                state.current_node = target
                render_chat_area.refresh()
                render_sidebar_content.refresh()

            margin = depth * 12
            color = 'blue-800' if is_active else 'gray-600'
            bg = 'bg-blue-100' if is_active else ''
            weight = 'font-bold' if is_active else 'font-normal'

            with ui.row().style(f'margin-left: {margin}px').classes(f'items-center q-my-xs rounded {bg} q-px-xs'):
                ui.icon('subdirectory_arrow_right').classes('text-gray-400 text-xs')
                ui.link(label).classes(f'text-sm {weight} text-{color} cursor-pointer hover:underline').on('click', on_click)
            
            target_children = model_child.children if model_child else node.children
            for child in target_children:
                draw_node(child, depth + 1)

        draw_node(state.root)

    # --- ACTIONS ---
    def start_new_topic():
        state.current_node = state.root
        render_chat_area.refresh()
        render_sidebar_content.refresh()
        ui.notify("Started new topic (Root)")

    async def send_message():
        text = input_box.value
        if not text: return
        input_box.value = ''
        
        u_node = ChatNode("user", text, parent=state.current_node)
        state.current_node.add_child(u_node)
        state.current_node = u_node
        
        render_chat_area.refresh()
        render_sidebar_content.refresh()
        
        client = gemini_utils.get_client()
        if not client: return
        
        model_info = config.MODELS[state.selected_model_key]
        spinner.set_visibility(True)
        
        try:
            full_context, _ = state.current_node.get_history()
            api_msgs = [m for m in full_context if m.role != "system"]
            
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None, 
                partial(client.models.generate_content, model=model_info['id'], contents=api_msgs)
            )
            
            gemini_utils.track_cost(state, resp, model_info['pricing'])
            
            response_text = resp.text if resp.text else "⚠️ [No text response]"
            a_node = ChatNode("model", response_text, parent=state.current_node)
            state.current_node.add_child(a_node)
            state.current_node = a_node
            
        except Exception as e:
            ui.notify(f"Error: {e}", type='negative')
            err_node = ChatNode("model", f"⚠️ Error: {str(e)}", parent=state.current_node)
            state.current_node.add_child(err_node)
            state.current_node = err_node

        finally:
            spinner.set_visibility(False)
            render_chat_area.refresh()
            render_sidebar_content.refresh()

    def logout():
        state.user = None
        state.total_cost = 0.0
        app.storage.user.clear()
        render_sidebar_content.refresh()
        ui.notify("Logged out")

    # --- LAYOUT ---
    login_dialog = auth_ui.render_login_dialog(state, render_sidebar_content.refresh)
    
    with ui.header().classes('bg-white text-black border-b h-16'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center'):
                ui.button(icon='menu', on_click=lambda: left_drawer.toggle()).props('flat color=black size=lg')
                ui.label('Conversation Tree').classes('text-h5 font-bold')
            ui.select(list(config.MODELS.keys())).bind_value(state, 'selected_model_key').props('dense options-dense filled rounded')

    with ui.left_drawer(value=True).classes('bg-gray-50 w-80 border-r') as left_drawer: 
        render_sidebar_content()

    # FIX: Main column structure
    # Use 'gap-0' to avoid accidental spacing issues, 'no-wrap' to ensure structure holds
    with ui.column().classes('w-full h-full gap-0 no-wrap'):
        render_chat_area() # This now has flex-grow
        
        spinner = ui.spinner(size='3em').classes('self-center text-primary q-my-md')
        spinner.set_visibility(False)
        
        with ui.row().classes('w-full q-pa-md gap-4 items-center bg-white border-t'):
            ui.button(icon='add', on_click=start_new_topic).props('round color=green size=md').tooltip('New Topic')
            input_box = ui.input(placeholder='Type...').classes('flex-grow text-lg').on('keydown.enter', send_message)
            ui.button(icon='send', on_click=send_message).props('round color=primary size=lg')

ui.run(title='Conversation Tree', storage_secret="gemini_secret_key", viewport='width=device-width, initial-scale=1')
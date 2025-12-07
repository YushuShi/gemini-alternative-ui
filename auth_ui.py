from nicegui import ui, app
import database

def render_login_dialog(state, on_success_callback):
    """
    Renders the login/signup dialog.
    state: The current SessionState object.
    on_success_callback: A function to call (usually a refresh) when login succeeds.
    """
    with ui.dialog() as login_dialog, ui.card():
        with ui.tabs() as tabs:
            ui.tab('Login')
            ui.tab('Sign Up')
        
        with ui.tab_panels(tabs, value='Login'):
            # --- LOGIN PANEL ---
            with ui.tab_panel('Login'):
                email_in = ui.input('Email')
                pass_in = ui.input('Password', password=True)
                
                def try_login():
                    u = database.authenticate_user(email_in.value, pass_in.value)
                    if u:
                        state.user = u
                        state.total_cost = u['total_cost']
                        app.storage.user['email'] = u['email']
                        login_dialog.close()
                        on_success_callback() # Refresh the sidebar
                        ui.notify('Success!')
                    else:
                        ui.notify('Invalid login', type='negative')
                
                ui.button('Login', on_click=try_login)
            
            # --- SIGNUP PANEL ---
            with ui.tab_panel('Sign Up'):
                new_email = ui.input('New Email')
                new_pass = ui.input('New Password', password=True)
                
                def try_signup():
                    if database.create_user(new_email.value, new_pass.value):
                        ui.notify('Created! Please Login.')
                    else:
                        ui.notify('Email exists', type='negative')
                
                ui.button('Create Account', on_click=try_signup)
                
    return login_dialog
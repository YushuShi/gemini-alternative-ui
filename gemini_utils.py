from google import genai
from nicegui import ui
import config
import database

def get_client():
    if not config.API_KEY:
        ui.notify("API Key missing!", type='negative')
        return None
    return genai.Client(api_key=config.API_KEY)

def track_cost(session, response, pricing):
    try:
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            i_tok = usage.prompt_token_count or 0
            o_tok = usage.candidates_token_count or 0
            session.total_input += i_tok
            session.total_output += o_tok
            cost = (i_tok/1e6)*pricing["INPUT_PER_1M"] + (o_tok/1e6)*pricing["OUTPUT_PER_1M"]
            session.total_cost += cost
            if session.user:
                database.update_user_cost(session.user['email'], cost)
                session.user['total_cost'] = database.get_user_cost(session.user['email'])
    except Exception as e:
        print(f"Cost Error: {e}")
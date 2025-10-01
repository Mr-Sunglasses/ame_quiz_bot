from aiogram.fsm.state import State, StatesGroup


class NewQuizStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_mode = State()
    waiting_single_question = State()
    waiting_bulk_content = State()
    waiting_bulk_confirm = State()
    waiting_duration = State()
    waiting_visibility = State()
    waiting_confirm = State()


class AttemptStates(StatesGroup):
    idle = State()
    in_progress = State()
    finished = State()

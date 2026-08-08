from aiogram.fsm.state import State, StatesGroup

class OrderState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_address = State()
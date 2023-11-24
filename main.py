from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import aiohttp
import sqlite3
from datetime import datetime, timedelta
import random

from datetime import timedelta

from config import TOKEN, START_IMAGE_URL, GITHUB_PASSWORDS_URL

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

conn = sqlite3.connect('data.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    registration_date TEXT NOT NULL,
    last_password_request TEXT
)
''')
conn.commit()

class YourStateEnum(StatesGroup):
    waiting_for_nickname = State()

async def get_passwords_from_github():
    async with aiohttp.ClientSession() as session:
        async with session.get(GITHUB_PASSWORDS_URL) as response:
            if response.status == 200:
                passwords_text = await response.text()
                return passwords_text.split('\n')
            else:
                return []

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    async with aiohttp.ClientSession() as session:
        async with session.get(START_IMAGE_URL) as response:
            if response.status == 200:
                await bot.send_photo(message.chat.id, types.InputFile.from_url(START_IMAGE_URL),
                                     caption="Привет! Выберите одну из опций в меню.",
                                     reply_markup=types.InlineKeyboardMarkup(
                                         inline_keyboard=[
                                             [types.InlineKeyboardButton(text="Профиль", callback_data="profile")],
                                             [types.InlineKeyboardButton(text="Поиск пароля", callback_data="search_password")],
                                             [types.InlineKeyboardButton(text="Оплатить подписку", callback_data="subscribe_payment")],
                                             [types.InlineKeyboardButton(text="О проекте", callback_data="about_project")],
                                         ]
                                     ))
            else:
                await message.answer("Не удалось загрузить изображение. Пожалуйста, попробуйте позже.")

@dp.callback_query_handler(lambda callback_query: True)
async def handle_inline_buttons(callback_query: types.CallbackQuery, state: FSMContext):
    button_text = callback_query.data

    if button_text == "profile":
        user_id = callback_query.from_user.id
        registration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('INSERT INTO users (user_id, registration_date) VALUES (?, ?)', (user_id, registration_date))
        conn.commit()

        profile_info = f"ID: {user_id}\nДата регистрации: {registration_date}"
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id, profile_info)

    elif button_text == "about_project":
        project_info = "Здравствуйте. Наш проект помогает пользователям находить их пароль. " \
                       "Для использования вы должны просто ввести ник пользователя и получить уже готовый пароль."
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(callback_query.from_user.id, project_info)

    elif button_text == "search_password":
        user_id = callback_query.from_user.id

        cursor.execute('SELECT last_password_request FROM users WHERE user_id = ?', (user_id,))
        last_request_time = cursor.fetchone()
        if last_request_time and last_request_time[0]:
            last_request_time = datetime.strptime(last_request_time[0], "%Y-%m-%d %H:%M:%S")
            time_difference = datetime.now() - last_request_time
            if time_difference < timedelta(minutes=15):
                await bot.answer_callback_query(callback_query.id, "Вы уже получали пароль от аккаунта. Подождите 15 минут или купите подписку.")
                return

        await YourStateEnum.waiting_for_nickname.set()
        await bot.answer_callback_query(callback_query.id, "Введите ник, который будете искать в нашей базе данных.")

@dp.message_handler(state=YourStateEnum.waiting_for_nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    nickname = message.text
    passwords = await get_passwords_from_github()
    random_passwords = random.sample(passwords, min(10, len(passwords)))
    await bot.send_message(message.chat.id, "\n".join(random_passwords))
    cursor.execute('UPDATE users SET last_password_request = ? WHERE user_id = ?', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message.from_user.id))
    conn.commit()
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

conn.close()
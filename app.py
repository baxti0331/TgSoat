import logging
import sqlite3
import time
import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# Получаем токен и админ айди из переменных окружения
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Не указан API_TOKEN в переменных окружения")

try:
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
except (TypeError, ValueError):
    raise ValueError("Не указан или неверно указан ADMIN_ID в переменных окружения")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- Состояния FSM ---
class BroadcastStates(StatesGroup):
    waiting_for_type = State()
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_buttons = State()
    waiting_for_confirm = State()

# --- Работа с базой ---
def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        registered_at INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,
        file_id TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_user(user_id: int):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, registered_at) VALUES (?, ?)", (user_id, int(time.time())))
        conn.commit()
    conn.close()

def count_users():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def count_users_since(seconds_ago: int):
    since_ts = int(time.time()) - seconds_ago
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE registered_at >= ?", (since_ts,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def get_all_user_ids():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

# --- Клавиатуры ---
def admin_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📢 Сделать рассылку", callback_data="send_broadcast")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("🔍 Поиск книги", callback_data="admin_search")]
    ])
    return kb

def broadcast_type_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📝 Текст", callback_data="type_text")],
        [InlineKeyboardButton("📄 Файл", callback_data="type_file")],
        [InlineKeyboardButton("🖼 Фото", callback_data="type_photo")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])
    return kb

def confirm_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ Подтвердить рассылку", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])
    return kb

def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ])

# --- Хендлеры ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    add_user(message.from_user.id)
    name = message.from_user.full_name
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"Привет, {name}! Ты — админ.", reply_markup=admin_keyboard())
    else:
        await message.answer(f"Привет, {name}! Введите название книги для поиска.")

@dp.message()
async def save_user_and_search(message: types.Message):
    add_user(message.from_user.id)
    # Пока заглушка для поиска книг — можно реализовать по желанию
    await message.answer("Функция поиска книг пока в разработке.")

# --- Админская панель ---
@dp.callback_query(Text("send_broadcast"))
async def cb_send_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    await callback.message.answer("Выберите тип рассылки:", reply_markup=broadcast_type_keyboard())
    await state.set_state(BroadcastStates.waiting_for_type)
    await callback.answer()

@dp.callback_query(Text(startswith="type_"), BroadcastStates.waiting_for_type)
async def cb_choose_broadcast_type(callback: types.CallbackQuery, state: FSMContext):
    broadcast_type = callback.data.split("_")[1]
    await state.update_data(broadcast_type=broadcast_type)
    if broadcast_type == "text":
        await callback.message.answer("Отправьте текст сообщения для рассылки:", reply_markup=cancel_keyboard())
        await state.set_state(BroadcastStates.waiting_for_text)
    elif broadcast_type == "file":
        await callback.message.answer("Пришлите файл (PDF, документ) для рассылки:", reply_markup=cancel_keyboard())
        await state.set_state(BroadcastStates.waiting_for_media)
    elif broadcast_type == "photo":
        await callback.message.answer("Пришлите фото для рассылки:", reply_markup=cancel_keyboard())
        await state.set_state(BroadcastStates.waiting_for_media)
    await callback.answer()

@dp.message(BroadcastStates.waiting_for_text)
async def handle_broadcast_text(message: types.Message, state: FSMContext):
    text = message.text or ""
    await state.update_data(broadcast_text=text)
    await message.answer(
        "Если хотите добавить инлайн-кнопки, отправьте их в формате:\n"
        "`Текст кнопки1|URL1\nТекст кнопки2|URL2`\n"
        "Иначе отправьте `нет` или `/skip`", parse_mode="Markdown"
    )
    await state.set_state(BroadcastStates.waiting_for_buttons)

@dp.message(BroadcastStates.waiting_for_media)
async def handle_broadcast_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    broadcast_type = data.get("broadcast_type")
    if broadcast_type == "file" and message.document:
        await state.update_data(broadcast_file_id=message.document.file_id, broadcast_file_name=message.document.file_name)
    elif broadcast_type == "photo" and message.photo:
        photo = message.photo[-1]  # Максимальное качество
        await state.update_data(broadcast_photo_id=photo.file_id)
    else:
        await message.answer("Неверный тип сообщения, пришлите корректный файл или фото.")
        return
    await message.answer(
        "Отправьте текст для сообщения рассылки (можно оставить пустым), либо /skip",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(BroadcastStates.waiting_for_text)

@dp.message(BroadcastStates.waiting_for_buttons)
async def handle_broadcast_buttons(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() in ["нет", "/skip"]:
        await state.update_data(broadcast_buttons=None)
    else:
        buttons = []
        lines = text.split("\n")
        for line in lines:
            if "|" in line:
                btn_text, btn_url = line.split("|", 1)
                buttons.append(InlineKeyboardButton(text=btn_text.strip(), url=btn_url.strip()))
        if not buttons:
            await message.answer("Не удалось распарсить кнопки. Отправьте 'нет' или /skip, если не хотите кнопок.")
            return
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(*buttons)
        await state.update_data(broadcast_buttons=kb)
    await message.answer("Проверьте и подтвердите рассылку:", reply_markup=confirm_keyboard())
    await state.set_state(BroadcastStates.waiting_for_confirm)

@dp.message(Text(startswith="/skip"), BroadcastStates.waiting_for_text)
async def skip_text(message: types.Message, state: FSMContext):
    await state.update_data(broadcast_text="")
    await message.answer("Проверьте и подтвердите рассылку:", reply_markup=confirm_keyboard())
    await state.set_state(BroadcastStates.waiting_for_confirm)

@dp.callback_query(Text("confirm_send"), BroadcastStates.waiting_for_confirm)
async def send_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    broadcast_type = data.get("broadcast_type")
    text = data.get("broadcast_text", "")
    buttons = data.get("broadcast_buttons")
    user_ids = get_all_user_ids()
    sent = 0
    failed = 0

    await callback.message.answer(f"Начинаю рассылку {len(user_ids)} пользователям...")
    for user_id in user_ids:
        try:
            if broadcast_type == "text":
                await bot.send_message(user_id, text or " ", reply_markup=buttons)
            elif broadcast_type == "file":
                file_id = data.get("broadcast_file_id")
                if file_id:
                    await bot.send_document(user_id, file_id, caption=text, reply_markup=buttons)
                else:
                    await bot.send_message(user_id, text or " ", reply_markup=buttons)
            elif broadcast_type == "photo":
                photo_id = data.get("broadcast_photo_id")
                if photo_id:
                    await bot.send_photo(user_id, photo_id, caption=text, reply_markup=buttons)
                else:
                    await bot.send_message(user_id, text or " ", reply_markup=buttons)
            sent += 1
            await asyncio.sleep(0.05)  # небольшой delay, чтобы не перегружать Telegram
        except Exception as e:
            logging.warning(f"Не удалось отправить пользователю {user_id}: {e}")
            failed += 1

    await callback.message.answer(f"Рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}")
    await state.clear()
    await callback.answer()

@dp.callback_query(Text("cancel"))
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Действие отменено.")
    await callback.answer()

# --- Статистика для админа ---
@dp.callback_query(Text("stats"))
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    total = count_users()
    day = count_users_since(24 * 3600)
    week = count_users_since(7 * 24 * 3600)
    month = count_users_since(30 * 24 * 3600)
    text = (
        f"📊 Статистика пользователей бота:\n\n"
        f"👥 Всего: {total}\n"
        f"📅 За последние 24 часа: {day}\n"
        f"📆 За последнюю неделю: {week}\n"
        f"🗓 За последний месяц: {month}"
    )
    await callback.message.answer(text)
    await callback.answer()

# --- Обработчик поиска книг (пока заглушка) ---
@dp.callback_query(Text("admin_search"))
async def admin_search(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return
    await callback.message.answer("Функция поиска книг в разработке.")
    await callback.answer()

# --- Запуск бота ---
if __name__ == "__main__":
    init_db()
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)

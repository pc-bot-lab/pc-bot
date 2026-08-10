import asyncio
import sqlite3
import os
import sys
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# ========== КОНФИГ ==========
BOT_TOKEN = "8805962190:AAE55596sWWha0bejMHySYuDgnRYSC9j_1s"
ADMIN_ID = 938815106

# 👇 ВАШ ТЕЛЕГРАМ ЮЗЕРНЕЙМ ДЛЯ УВЕДОМЛЕНИЙ ОБ ОШИБКАХ
DEVELOPER_USERNAME = "@lexiconKrut"

PAYMENT_PHONE = "+7 776 404 2121"
PAYMENT_OPERATOR = "Билайн"
PAYMENT_COUNTRY = "Казахстан"
PAYMENT_AMOUNT = 500

PRODUCTS = {
    "1": {
        "name": "🖥️ Сборка ПК",
        "price": 500,
        "desc": "Профессиональная сборка компьютера любой сложности.",
        "file": "files/pc_build_guide.cfg"
    },
    "2": {
        "name": "🔧 Сборка КАПТ",
        "price": 500,
        "desc": "Сборка каптовальщика для криптовалют.",
        "file": "files/capt_build_guide.cfg"
    }
}

DB_NAME = "shop.db"

# ========== БАЗА ДАННЫХ ==========
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                product_id TEXT,
                product_name TEXT,
                price INTEGER,
                status TEXT DEFAULT '⏳ Ожидает оплаты',
                payment_receipt TEXT,
                file_sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")

def save_order(user_id, username, product_id, product_name, price):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (user_id, username, product_id, product_name, price) VALUES (?,?,?,?,?)",
            (user_id, username, product_id, product_name, price)
        )
        order_id = cur.lastrowid
        conn.commit()
        conn.close()
        return order_id
    except Exception as e:
        print(f"❌ Ошибка сохранения заказа: {e}")
        return None

def update_order_receipt(order_id, file_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("UPDATE orders SET payment_receipt=?, status='📎 Чек отправлен' WHERE id=?", (file_id, order_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка обновления чека: {e}")

def update_order_status(order_id, status):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка обновления статуса: {e}")

def update_order_file_sent(order_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("UPDATE orders SET file_sent=1 WHERE id=?", (order_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка обновления file_sent: {e}")

def get_order(order_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute(
            "SELECT id, user_id, username, product_id, product_name, price, status, payment_receipt, file_sent, created_at FROM orders WHERE id=?",
            (order_id,)
        )
        data = cur.fetchone()
        conn.close()
        return data
    except Exception as e:
        print(f"❌ Ошибка получения заказа: {e}")
        return None

def get_orders(status=None, limit=50):
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT id, user_id, username, product_id, product_name, price, status, payment_receipt, file_sent, created_at FROM orders WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit)
            )
        else:
            cur.execute(
                "SELECT id, user_id, username, product_id, product_name, price, status, payment_receipt, file_sent, created_at FROM orders ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        data = cur.fetchall()
        conn.close()
        return data
    except Exception as e:
        print(f"❌ Ошибка получения заказов: {e}")
        return []

def get_stats():
    try:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM orders")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status='✅ Завершен'")
        completed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status='⏳ Ожидает оплаты'")
        waiting = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status='📎 Чек отправлен'")
        receipt_sent = cur.fetchone()[0]
        conn.close()
        return {"total": total, "completed": completed, "waiting": waiting, "receipt_sent": receipt_sent}
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
        return {"total": 0, "completed": 0, "waiting": 0, "receipt_sent": 0}

# ========== КЛАВИАТУРЫ ==========
def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥️ Каталог услуг", callback_data="catalog")],
        [InlineKeyboardButton(text="📊 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="📞 Контакты", callback_data="contacts")]
    ])
    return kb

def catalog_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, p in PRODUCTS.items():
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{p['name']} - {p['price']}₽", callback_data=f"product_{pid}")
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return kb

def product_actions(pid):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Заказать за 500₽", callback_data=f"order_{pid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="catalog")]
    ])
    return kb

def admin_panel():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📋 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton(text="📎 Чеки на проверку", callback_data="admin_receipts")],
        [InlineKeyboardButton(text="🔙 Выход", callback_data="main_menu")]
    ])
    return kb

def admin_order_actions(order_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"admin_confirm_{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить оплату", callback_data=f"admin_reject_{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_orders")]
    ])
    return kb

# ========== СОСТОЯНИЯ ==========
class OrderState(StatesGroup):
    waiting_for_receipt = State()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def safe_edit_message(call: CallbackQuery, text: str, reply_markup=None, parse_mode="Markdown"):
    try:
        if call.message.text is not None:
            await call.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await call.message.delete()
            await call.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e) or "there is no text" in str(e):
            await call.message.delete()
            await call.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            raise e

def get_file_for_product(product_id):
    product = PRODUCTS.get(product_id)
    if product and product.get('file'):
        return product['file']
    return None

async def send_error_to_developer(bot: Bot, error_text: str):
    """Отправляет ошибку разработчику в Telegram"""
    try:
        message = f"🚨 *ОШИБКА БОТА!*\n\n{error_text}\n\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await bot.send_message(ADMIN_ID, message, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ Не удалось отправить ошибку разработчику: {e}")

# ========== ХЕНДЛЕРЫ ==========
router = Router()

@router.message(Command("start"))
async def start(msg: Message):
    try:
        await msg.answer(
            "🖥️ *Добро пожаловать в сервис сборки ПК и КАПТ!*\n\n"
            "💰 Стоимость услуги: *500₽*\n\n"
            "Выберите услугу в каталоге.",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await send_error_to_developer(msg.bot, f"Ошибка в /start:\n{traceback.format_exc()}")

@router.message(Command("admin"))
async def admin_cmd(msg: Message):
    try:
        if msg.from_user.id != ADMIN_ID:
            await msg.answer("⛔ У вас нет доступа.")
            return
        await msg.answer(
            "👑 *Админ-панель*\n\nВыберите действие:",
            reply_markup=admin_panel(),
            parse_mode="Markdown"
        )
    except Exception as e:
        await send_error_to_developer(msg.bot, f"Ошибка в /admin:\n{traceback.format_exc()}")

@router.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery):
    try:
        await safe_edit_message(call, "🖥️ *Главное меню*\n💰 500₽", reply_markup=main_menu())
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в back_to_main:\n{traceback.format_exc()}")

@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    try:
        await safe_edit_message(call, "📦 *Каталог*\n\nВыберите услугу:", reply_markup=catalog_menu())
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в show_catalog:\n{traceback.format_exc()}")

@router.callback_query(F.data == "contacts")
async def show_contacts(call: CallbackQuery):
    try:
        await safe_edit_message(
            call, 
            "📞 *Менеджер*\n\nСвяжитесь с нами в Telegram:\n@lexiconKrut", 
            reply_markup=main_menu()
        )
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в show_contacts:\n{traceback.format_exc()}")

@router.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    try:
        orders = get_orders(limit=50)
        user_orders = [o for o in orders if o[1] == call.from_user.id]
        if not user_orders:
            await safe_edit_message(call, "📊 *Нет заказов*", reply_markup=main_menu())
            await call.answer()
            return
        
        text = "📊 *Ваши заказы*\n\n"
        for order in user_orders[:5]:
            oid, uid, username, pid, pname, price, status, receipt, file_sent, created = order
            text += f"#{oid} | {status}\n{pname}\n💰 {price}₽\n---\n"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_orders")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
        await safe_edit_message(call, text, reply_markup=kb)
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в my_orders:\n{traceback.format_exc()}")

@router.callback_query(F.data.startswith("product_"))
async def show_product(call: CallbackQuery):
    try:
        pid = call.data.split("_")[1]
        p = PRODUCTS.get(pid)
        if not p:
            await call.answer("Услуга не найдена!")
            return
        text = f"📦 *{p['name']}*\n\n{p['desc']}\n\n💰 *{p['price']}₽*"
        await safe_edit_message(call, text, reply_markup=product_actions(pid))
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в show_product:\n{traceback.format_exc()}")

@router.callback_query(F.data.startswith("order_"))
async def create_order(call: CallbackQuery, state: FSMContext):
    try:
        pid = call.data.split("_")[1]
        p = PRODUCTS.get(pid)
        if not p:
            await call.answer("Услуга не найдена!")
            return
        
        username = call.from_user.username or call.from_user.first_name
        order_id = save_order(call.from_user.id, username, pid, p['name'], p['price'])
        if not order_id:
            await call.answer("❌ Ошибка создания заказа!", show_alert=True)
            return
        
        await state.update_data(order_id=order_id)
        
        payment_text = (
            f"✅ *Заказ #{order_id} создан!*\n\n"
            f"📦 {p['name']}\n"
            f"💰 Сумма: *{PAYMENT_AMOUNT}₽*\n\n"
            f"💳 *Реквизиты для оплаты:*\n"
            f"📱 Номер: `{PAYMENT_PHONE}`\n"
            f"📶 Оператор: {PAYMENT_OPERATOR}\n"
            f"🌍 Страна: {PAYMENT_COUNTRY}\n\n"
            f"📎 *Отправьте ФОТО или ДОКУМЕНТ чека в этот чат*"
        )
        
        await safe_edit_message(call, payment_text, reply_markup=None)
        await state.set_state(OrderState.waiting_for_receipt)
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в create_order:\n{traceback.format_exc()}")

# ======== УЛУЧШЕННАЯ ОБРАБОТКА ЧЕКОВ (ПРИНИМАЕТ ФОТО И ДОКУМЕНТЫ) ========
@router.message(OrderState.waiting_for_receipt, F.photo | F.document)
async def process_receipt_photo(msg: Message, state: FSMContext, bot: Bot):
    try:
        data = await state.get_data()
        order_id = data.get('order_id')
        
        if not order_id:
            # Если order_id не найден в состоянии, ищем последний активный заказ пользователя
            orders = get_orders(limit=10)
            user_orders = [o for o in orders if o[1] == msg.from_user.id and o[6] == "⏳ Ожидает оплаты"]
            if user_orders:
                order_id = user_orders[0][0]
                await state.update_data(order_id=order_id)
            else:
                await msg.answer("❌ Заказ не найден. Пожалуйста, создайте новый заказ через каталог.")
                await state.clear()
                return
        
        # Определяем тип вложения (фото или документ)
        if msg.photo:
            file_id = msg.photo[-1].file_id
            file_type = "фото"
        elif msg.document:
            file_id = msg.document.file_id
            file_type = "документ"
        else:
            await msg.answer("❌ Пожалуйста, отправьте фото или файл чека.")
            return
        
        # Сохраняем чек в базе
        update_order_receipt(order_id, file_id)
        await state.clear()
        
        order = get_order(order_id)
        if not order:
            await msg.answer("❌ Заказ не найден.")
            return
        
        # === ГАРАНТИРОВАННАЯ ОТПРАВКА АДМИНУ ===
        try:
            if msg.photo:
                await bot.send_photo(
                    ADMIN_ID,
                    photo=file_id,
                    caption=(
                        f"📎 *Новый чек!*\n\n"
                        f"Заказ #{order_id}\n"
                        f"👤 {order[2]}\n"
                        f"📦 {order[4]}\n"
                        f"💰 {order[5]}₽\n"
                        f"📎 Тип: {file_type}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_order_actions(order_id)
                )
            else:
                await bot.send_document(
                    ADMIN_ID,
                    document=file_id,
                    caption=(
                        f"📎 *Новый чек!*\n\n"
                        f"Заказ #{order_id}\n"
                        f"👤 {order[2]}\n"
                        f"📦 {order[4]}\n"
                        f"💰 {order[5]}₽\n"
                        f"📎 Тип: {file_type}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_order_actions(order_id)
                )
            # Если админ получил, подтверждаем пользователю
            await msg.answer(
                f"✅ *Чек отправлен!*\nЗаказ #{order_id} ожидает подтверждения.",
                reply_markup=main_menu(),
                parse_mode="Markdown"
            )
        except Exception as e:
            # Если не удалось отправить админу, логируем и уведомляем пользователя
            error_text = f"❌ Ошибка отправки чека админу: {e}\nЗаказ #{order_id}\nПользователь: {order[2]}"
            await send_error_to_developer(bot, error_text)
            await msg.answer(
                "⚠️ Произошла ошибка при отправке чека администратору. Мы уже работаем над этим.\n"
                "Пожалуйста, попробуйте еще раз через 1 минуту.",
                reply_markup=main_menu()
            )
    except Exception as e:
        # Глобальная обработка ошибок
        error_text = f"❌ Критическая ошибка в process_receipt_photo:\n{traceback.format_exc()}"
        await send_error_to_developer(bot, error_text)
        await msg.answer(
            "❌ Произошла ошибка. Пожалуйста, попробуйте еще раз или свяжитесь с поддержкой.",
            reply_markup=main_menu()
        )

@router.message(OrderState.waiting_for_receipt)
async def process_receipt_invalid(msg: Message):
    try:
        await msg.answer(
            f"❌ Отправьте ФОТО или ДОКУМЕНТ с чеком.\n\n"
            f"💳 Номер для оплаты: `{PAYMENT_PHONE}`\n"
            f"💰 Сумма: 500₽",
            parse_mode="Markdown"
        )
    except Exception as e:
        await send_error_to_developer(msg.bot, f"Ошибка в process_receipt_invalid:\n{traceback.format_exc()}")

# ========== АДМИН-ПАНЕЛЬ ==========
@router.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm_payment(call: CallbackQuery, bot: Bot):
    try:
        order_id = int(call.data.split("_")[2])
        order = get_order(order_id)
        if not order:
            await call.answer("Заказ не найден!")
            return
        
        update_order_status(order_id, "✅ Завершен")
        file_path = get_file_for_product(order[3])
        
        if file_path and os.path.exists(file_path):
            document = FSInputFile(file_path)
            await bot.send_document(order[1], document=document, caption=f"📄 *Заказ #{order_id} готов!*", parse_mode="Markdown")
            update_order_file_sent(order_id)
            await call.message.delete()
            await call.message.answer(f"✅ *Оплата подтверждена!* Файл отправлен.", reply_markup=admin_panel(), parse_mode="Markdown")
        else:
            await bot.send_message(order[1], f"✅ *Заказ #{order_id} завершен!*", parse_mode="Markdown")
            await call.message.delete()
            await call.message.answer(f"✅ *Оплата подтверждена!*", reply_markup=admin_panel(), parse_mode="Markdown")
        
        await call.answer()
    except Exception as e:
        await send_error_to_developer(bot, f"Ошибка в admin_confirm_payment:\n{traceback.format_exc()}")

@router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_payment(call: CallbackQuery, bot: Bot):
    try:
        order_id = int(call.data.split("_")[2])
        order = get_order(order_id)
        if not order:
            await call.answer("Заказ не найден!")
            return
        
        update_order_status(order_id, "❌ Отклонен")
        await bot.send_message(order[1], f"❌ *Заказ #{order_id} отклонен!*", parse_mode="Markdown")
        await call.message.delete()
        await call.message.answer(f"❌ *Оплата отклонена!*", reply_markup=admin_panel(), parse_mode="Markdown")
        await call.answer()
    except Exception as e:
        await send_error_to_developer(bot, f"Ошибка в admin_reject_payment:\n{traceback.format_exc()}")

@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    try:
        stats = get_stats()
        text = (
            "📊 *Статистика*\n\n"
            f"📦 Всего заказов: *{stats['total']}*\n"
            f"✅ Завершено: *{stats['completed']}*\n"
            f"⏳ Ожидают оплаты: *{stats['waiting']}*\n"
            f"📎 Чек отправлен: *{stats['receipt_sent']}*"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        await safe_edit_message(call, text, reply_markup=kb)
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в admin_stats:\n{traceback.format_exc()}")

@router.callback_query(F.data == "admin_orders")
async def admin_orders(call: CallbackQuery):
    try:
        orders = get_orders(limit=20)
        if not orders:
            await safe_edit_message(call, "📋 *Нет заказов*", reply_markup=admin_panel())
            await call.answer()
            return
        
        text = "📋 *Список заказов*\n\n"
        for order in orders[:10]:
            oid, uid, username, pid, pname, price, status, receipt, file_sent, created = order
            text += f"#{oid} | {status}\n👤 {username}\n📦 {pname}\n💰 {price}₽\n---\n"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_orders")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        await safe_edit_message(call, text, reply_markup=kb)
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в admin_orders:\n{traceback.format_exc()}")

@router.callback_query(F.data == "admin_receipts")
async def admin_receipts(call: CallbackQuery):
    try:
        orders = get_orders(status="📎 Чек отправлен", limit=20)
        if not orders:
            await safe_edit_message(call, "📎 *Нет чеков на проверку*", reply_markup=admin_panel())
            await call.answer()
            return
        
        text = "📎 *Чеки на проверку*\n\n"
        for order in orders[:10]:
            oid, uid, username, pid, pname, price, status, receipt, file_sent, created = order
            text += f"#{oid} | {status}\n👤 {username}\n📦 {pname}\n💰 {price}₽\n---\n"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for order in orders[:5]:
            oid = order[0]
            kb.inline_keyboard.append([
                InlineKeyboardButton(text=f"📎 Чек #{oid}", callback_data=f"admin_view_receipt_{oid}")
            ])
        kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
        await safe_edit_message(call, text, reply_markup=kb)
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в admin_receipts:\n{traceback.format_exc()}")

@router.callback_query(F.data.startswith("admin_view_receipt_"))
async def admin_view_receipt(call: CallbackQuery, bot: Bot):
    try:
        order_id = int(call.data.split("_")[3])
        order = get_order(order_id)
        if not order or not order[7]:
            await call.answer("Чек не найден!")
            return
        
        # Пытаемся отправить как фото, если не получится — как документ
        try:
            await bot.send_photo(
                call.from_user.id,
                photo=order[7],
                caption=f"📎 *Чек для заказа #{order_id}*\n\n"
                        f"👤 {order[2]}\n📦 {order[4]}\n💰 {order[5]}₽",
                parse_mode="Markdown",
                reply_markup=admin_order_actions(order_id)
            )
        except:
            await bot.send_document(
                call.from_user.id,
                document=order[7],
                caption=f"📎 *Чек для заказа #{order_id}*\n\n"
                        f"👤 {order[2]}\n📦 {order[4]}\n💰 {order[5]}₽",
                parse_mode="Markdown",
                reply_markup=admin_order_actions(order_id)
            )
        await call.answer()
    except Exception as e:
        await send_error_to_developer(bot, f"Ошибка в admin_view_receipt:\n{traceback.format_exc()}")

@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery):
    try:
        await safe_edit_message(call, "👑 *Админ-панель*", reply_markup=admin_panel())
        await call.answer()
    except Exception as e:
        await send_error_to_developer(call.bot, f"Ошибка в admin_back:\n{traceback.format_exc()}")

# ========== ЗАПУСК ==========
async def main():
    try:
        init_db()
        if not os.path.exists("files"):
            os.makedirs("files")
        
        storage = MemoryStorage()
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=storage)
        dp.include_router(router)
        
        # Отправляем уведомление о запуске
        try:
            await bot.send_message(
                ADMIN_ID, 
                f"✅ *Бот успешно запущен!*\n\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"👤 Разработчик: {DEVELOPER_USERNAME}",
                parse_mode="Markdown"
            )
            print("✅ Уведомление о запуске отправлено разработчику")
        except Exception as e:
            print(f"❌ Не удалось отправить уведомление о запуске: {e}")
        
        print("=" * 50)
        print("🤖 БОТ ДЛЯ СБОРКИ ПК/КАПТ ЗАПУЩЕН!")
        print("=" * 50)
        print(f"💳 Реквизиты для оплаты:")
        print(f"   📱 Номер: {PAYMENT_PHONE}")
        print(f"   📶 Оператор: {PAYMENT_OPERATOR}")
        print(f"   🌍 Страна: {PAYMENT_COUNTRY}")
        print(f"   💰 Сумма: {PAYMENT_AMOUNT}₽")
        print("=" * 50)
        print(f"👑 Админ-панель: /admin")
        print(f"👤 ID админа: {ADMIN_ID}")
        print(f"👨‍💻 Разработчик: {DEVELOPER_USERNAME}")
        print("=" * 50)
        print("🚨 Все ошибки будут отправлены в ЛС разработчику!")
        print("=" * 50)
        print("💡 ВАЖНО: Администратор должен написать боту /start, чтобы бот мог отправлять чеки!")
        print("=" * 50)
        
        await dp.start_polling(bot)
    except Exception as e:
        error_text = f"❌ КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ:\n{traceback.format_exc()}"
        print(error_text)
        # Пытаемся отправить ошибку разработчику
        try:
            bot = Bot(token=BOT_TOKEN)
            await send_error_to_developer(bot, error_text)
            await bot.send_message(ADMIN_ID, f"🚨 Бот упал! Ошибка выше.")
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
import os

# ========== КОНФИГ ==========
BOT_TOKEN = "8805962190:AAE55596sWWha0bejMHySYuDgnRYSC9j_1s"
ADMIN_ID = 938815106

# Реквизиты для оплаты
PAYMENT_PHONE = "+7 776 404 2121"
PAYMENT_OPERATOR = "Билайн"
PAYMENT_COUNTRY = "Казахстан"
PAYMENT_AMOUNT = 500

# Каталог товаров/услуг
PRODUCTS = {
    "1": {
        "name": "🖥️ Сборка ПК",
        "price": PAYMENT_AMOUNT,
        "desc": "Профессиональная сборка компьютера любой сложности.\nВходит: подбор комплектующих, сборка, установка ПО, тестирование.",
        "file": "files/pc_build_guide.cfg"
    },
    "2": {
        "name": "🔧 Сборка КАПТ",
        "price": PAYMENT_AMOUNT,
        "desc": "Сборка каптовальщика (КАПТ) для криптовалют.\nВходит: подбор оборудования, настройка, оптимизация.",
        "file": "files/capt_build_guide.cfg"
    }
}

DB_NAME = "shop.db"

# ========== БАЗА ДАННЫХ ==========
def init_db():
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

def save_order(user_id, username, product_id, product_name, price):
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

def update_order_receipt(order_id, file_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET payment_receipt=?, status='📎 Чек отправлен' WHERE id=?", (file_id, order_id))
    conn.commit()
    conn.close()

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()

def update_order_file_sent(order_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET file_sent=1 WHERE id=?", (order_id,))
    conn.commit()
    conn.close()

def get_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, user_id, username, product_id, product_name, price, status, payment_receipt, file_sent, created_at FROM orders WHERE id=?",
        (order_id,)
    )
    data = cur.fetchone()
    conn.close()
    return data

def get_orders(status=None, limit=50):
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

def get_stats():
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
        if "message is not modified" in str(e):
            await call.answer()
        elif "there is no text in the message" in str(e):
            await call.message.delete()
            await call.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            raise e

def get_file_for_product(product_id):
    product = PRODUCTS.get(product_id)
    if product and product.get('file'):
        return product['file']
    return None

# ========== ХЕНДЛЕРЫ ==========
router = Router()

# ---------- ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ ----------
@router.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "🖥️ *Добро пожаловать в сервис сборки ПК и КАПТ!*\n\n"
        "Мы предлагаем профессиональную сборку компьютеров и каптовальщиков.\n"
        "💰 Стоимость услуги: *500₽*\n\n"
        "Выберите услугу в каталоге.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@router.message(Command("admin"))
async def admin_cmd(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("⛔ У вас нет доступа.")
        return
    await msg.answer(
        "👑 *Админ-панель*\n\nВыберите действие:",
        reply_markup=admin_panel(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery):
    await safe_edit_message(
        call,
        "🖥️ *Главное меню*\n\n"
        "💰 Стоимость услуги: *500₽*",
        reply_markup=main_menu()
    )
    await call.answer()

@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    await safe_edit_message(
        call,
        "📦 *Наш каталог*\n\nВыберите услугу:",
        reply_markup=catalog_menu()
    )
    await call.answer()

@router.callback_query(F.data == "contacts")
async def show_contacts(call: CallbackQuery):
    await safe_edit_message(
        call,
        "📞 *Контакты*\n\n"
        "Телефон: +7 (999) 123-45-67\n"
        "Email: support@pc-build.ru\n"
        "Время работы: 9:00 - 21:00",
        reply_markup=main_menu()
    )
    await call.answer()

@router.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    orders = get_orders(limit=50)
    user_orders = [o for o in orders if o[1] == call.from_user.id]
    
    if not user_orders:
        await safe_edit_message(
            call,
            "📊 *У вас нет заказов*\n\nСделайте заказ в каталоге.",
            reply_markup=main_menu()
        )
        await call.answer()
        return
    
    text = "📊 *Ваши заказы*\n\n"
    for order in user_orders[:5]:
        oid, uid, username, pid, pname, price, status, receipt, file_sent, created = order
        text += f"#{oid} | {status}\n{pname}\n💰 {price}₽\n---\n"
    
    pending_order = None
    for o in user_orders:
        if o[6] in ["⏳ Ожидает оплаты", "📎 Чек отправлен"]:
            pending_order = o
            break
    
    if pending_order:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📎 Отправить чек", callback_data=f"send_receipt_{pending_order[0]}")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_orders")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_orders")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
        ])
    
    await safe_edit_message(call, text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("product_"))
async def show_product(call: CallbackQuery):
    pid = call.data.split("_")[1]
    p = PRODUCTS.get(pid)
    if not p:
        await call.answer("Услуга не найдена!")
        return
    
    text = (
        f"📦 *{p['name']}*\n\n"
        f"📝 {p['desc']}\n\n"
        f"💰 Цена: *{p['price']}₽*\n"
    )
    await safe_edit_message(call, text, reply_markup=product_actions(pid))
    await call.answer()

@router.callback_query(F.data.startswith("order_"))
async def create_order(call: CallbackQuery, state: FSMContext):
    pid = call.data.split("_")[1]
    p = PRODUCTS.get(pid)
    if not p:
        await call.answer("Услуга не найдена!")
        return
    
    # Проверяем активные заказы
    orders = get_orders(limit=50)
    user_orders = [o for o in orders if o[1] == call.from_user.id and o[6] in ["⏳ Ожидает оплаты", "📎 Чек отправлен"]]
    
    if user_orders:
        await call.answer("⚠️ У вас уже есть активный заказ! Завершите его.", show_alert=True)
        return
    
    # Создаем заказ
    username = call.from_user.username or call.from_user.first_name
    order_id = save_order(call.from_user.id, username, pid, p['name'], p['price'])
    
    # Сохраняем order_id в состояние
    await state.update_data(order_id=order_id)
    
    # Показываем реквизиты для оплаты
    payment_text = (
        f"✅ *Заказ #{order_id} создан!*\n\n"
        f"📦 {p['name']}\n"
        f"💰 Сумма: *{PAYMENT_AMOUNT}₽*\n\n"
        f"💳 *Реквизиты для оплаты:*\n\n"
        f"📱 На сим карту баланс пополнишь\n"
        f"📞 Номер: `{PAYMENT_PHONE}`\n"
        f"📶 Оператор: {PAYMENT_OPERATOR}\n"
        f"🌍 Страна: {PAYMENT_COUNTRY}\n"
        f"💰 Сумма: *{PAYMENT_AMOUNT}₽*\n\n"
        f"📎 *Отправьте СКРИНШОТ или ФОТО чека об оплате*\n"
        f"(Прямо в этот чат)\n\n"
        f"После отправки чека, он будет отправлен на проверку."
    )
    
    await safe_edit_message(
        call,
        payment_text,
        reply_markup=None
    )
    
    # Переходим в состояние ожидания чека
    await state.set_state(OrderState.waiting_for_receipt)
    await call.answer()

@router.message(OrderState.waiting_for_receipt, F.photo)
async def process_receipt_photo(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        # Если order_id нет в состоянии, ищем последний заказ пользователя
        orders = get_orders(limit=10)
        user_orders = [o for o in orders if o[1] == msg.from_user.id and o[6] in ["⏳ Ожидает оплаты"]]
        if user_orders:
            order_id = user_orders[0][0]
            await state.update_data(order_id=order_id)
        else:
            await msg.answer("❌ Ошибка. Заказ не найден.\nПожалуйста, создайте новый заказ в каталоге.")
            await state.clear()
            return
    
    # Получаем file_id фото
    file_id = msg.photo[-1].file_id
    
    # Обновляем заказ
    update_order_receipt(order_id, file_id)
    await state.clear()
    
    # Получаем данные заказа
    order = get_order(order_id)
    if not order:
        await msg.answer("❌ Заказ не найден.")
        return
    
    # Отправляем чек админу
    await bot.send_photo(
        ADMIN_ID,
        photo=file_id,
        caption=f"📎 *Новый чек!*\n\n"
                f"Заказ #{order_id}\n"
                f"👤 {order[2]}\n"
                f"📦 {order[4]}\n"
                f"💰 {order[5]}₽\n\n"
                f"Подтвердите или отклоните оплату.",
        parse_mode="Markdown",
        reply_markup=admin_order_actions(order_id)
    )
    
    await msg.answer(
        f"✅ *Чек отправлен!*\n\n"
        f"Заказ #{order_id}\n"
        f"Ожидайте подтверждения от менеджера.",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@router.message(OrderState.waiting_for_receipt)
async def process_receipt_invalid(msg: Message):
    await msg.answer(
        f"❌ Пожалуйста, отправьте *ФОТО* чека.\n\n"
        f"💳 *Реквизиты для оплаты:*\n"
        f"📱 На сим карту баланс пополнишь\n"
        f"📞 Номер: `{PAYMENT_PHONE}`\n"
        f"📶 Оператор: {PAYMENT_OPERATOR}\n"
        f"🌍 Страна: {PAYMENT_COUNTRY}\n"
        f"💰 Сумма: *{PAYMENT_AMOUNT}₽*",
        parse_mode="Markdown"
    )

# ========== АДМИН-ПАНЕЛЬ ==========
@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery):
    await safe_edit_message(
        call,
        "👑 *Админ-панель*",
        reply_markup=admin_panel()
    )
    await call.answer()

@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
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

@router.callback_query(F.data == "admin_orders")
async def admin_orders(call: CallbackQuery):
    orders = get_orders(limit=20)
    
    if not orders:
        await safe_edit_message(
            call,
            "📋 *Нет заказов*",
            reply_markup=admin_panel()
        )
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

@router.callback_query(F.data == "admin_receipts")
async def admin_receipts(call: CallbackQuery):
    orders = get_orders(status="📎 Чек отправлен", limit=20)
    
    if not orders:
        await safe_edit_message(
            call,
            "📎 *Нет чеков на проверку*",
            reply_markup=admin_panel()
        )
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

@router.callback_query(F.data.startswith("admin_view_receipt_"))
async def admin_view_receipt(call: CallbackQuery, bot: Bot):
    order_id = int(call.data.split("_")[3])
    order = get_order(order_id)
    
    if not order or not order[7]:
        await call.answer("Чек не найден!")
        return
    
    await bot.send_photo(
        call.from_user.id,
        photo=order[7],
        caption=f"📎 *Чек для заказа #{order_id}*\n\n"
                f"👤 {order[2]}\n"
                f"📦 {order[4]}\n"
                f"💰 {order[5]}₽\n\n"
                f"Подтвердите или отклоните оплату:",
        parse_mode="Markdown",
        reply_markup=admin_order_actions(order_id)
    )
    
    await call.answer()

@router.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm_payment(call: CallbackQuery, bot: Bot):
    order_id = int(call.data.split("_")[2])
    order = get_order(order_id)
    
    if not order:
        await call.answer("Заказ не найден!")
        return
    
    # Обновляем статус
    update_order_status(order_id, "✅ Завершен")
    
    # Получаем путь к файлу
    file_path = get_file_for_product(order[3])
    
    # Отправляем файл пользователю
    if file_path:
        try:
            if os.path.exists(file_path):
                document = FSInputFile(file_path)
                await bot.send_document(
                    order[1],
                    document=document,
                    caption=f"📄 *Ваш заказ #{order_id} готов!*\n\n"
                            f"Благодарим за оплату!\n"
                            f"Вот ваш файл с инструкцией/сборкой.",
                    parse_mode="Markdown"
                )
                update_order_file_sent(order_id)
                
                await call.message.delete()
                await call.message.answer(
                    f"✅ *Оплата подтверждена!*\n\n"
                    f"Заказ #{order_id}\n"
                    f"📄 Файл отправлен пользователю.",
                    reply_markup=admin_panel(),
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(
                    order[1],
                    f"✅ *Заказ #{order_id} завершен!*\n\n"
                    f"Благодарим за оплату!\n"
                    f"⚠️ Файл не найден. Свяжитесь с поддержкой.",
                    parse_mode="Markdown"
                )
                await call.message.delete()
                await call.message.answer(
                    f"✅ *Оплата подтверждена!*\n\n"
                    f"Заказ #{order_id}\n"
                    f"⚠️ Файл не найден: {file_path}",
                    reply_markup=admin_panel(),
                    parse_mode="Markdown"
                )
        except Exception as e:
            await call.message.delete()
            await call.message.answer(
                f"⚠️ *Ошибка при отправке файла:*\n{e}",
                reply_markup=admin_panel(),
                parse_mode="Markdown"
            )
    else:
        await bot.send_message(
            order[1],
            f"✅ *Заказ #{order_id} завершен!*\n\n"
            f"Благодарим за оплату!",
            parse_mode="Markdown"
        )
        await call.message.delete()
        await call.message.answer(
            f"✅ *Оплата подтверждена!*\n\n"
            f"Заказ #{order_id}",
            reply_markup=admin_panel(),
            parse_mode="Markdown"
        )
    
    await call.answer()

@router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_payment(call: CallbackQuery, bot: Bot):
    order_id = int(call.data.split("_")[2])
    order = get_order(order_id)
    
    if not order:
        await call.answer("Заказ не найден!")
        return
    
    update_order_status(order_id, "❌ Отклонен")
    
    await bot.send_message(
        order[1],
        f"❌ *Ваш заказ #{order_id} отклонен!*\n\n"
        f"Оплата не подтверждена.\n"
        f"Пожалуйста, свяжитесь с поддержкой.",
        parse_mode="Markdown"
    )
    
    await call.message.delete()
    await call.message.answer(
        f"❌ *Оплата отклонена!*\n\n"
        f"Заказ #{order_id}",
        reply_markup=admin_panel(),
        parse_mode="Markdown"
    )
    await call.answer()

# ========== ЗАПУСК ==========
async def main():
    init_db()
    
    # Создаем папку для файлов если её нет
    if not os.path.exists("files"):
        os.makedirs("files")
        print("📁 Создана папка files/")
    
    # Проверяем наличие файлов
    print("\n📄 Проверка файлов:")
    files_to_check = [
        "files/pc_build_guide.cfg",
        "files/capt_build_guide.cfg"
    ]
    
    all_files_exist = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path} - найден")
        else:
            print(f"   ❌ {file_path} - НЕ НАЙДЕН!")
            all_files_exist = False
    
    if not all_files_exist:
        print("\n⚠️ ВНИМАНИЕ! Некоторые файлы отсутствуют!")
        print("   Создайте файлы в папке files/ или измените пути в PRODUCTS")
    
    print("\n" + "=" * 50)
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
    print("=" * 50)
    
    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
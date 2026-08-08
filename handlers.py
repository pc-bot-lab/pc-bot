from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import PRODUCTS, ADMIN_ID
from database import add_to_cart, get_cart, clear_cart, save_order, get_orders
from keyboards import main_menu, catalog_menu, product_actions, cart_actions
from states import OrderState

router = Router()

# --- Команда /start ---
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в наш магазин!\nВыберите действие:",
        reply_markup=main_menu()
    )

# --- Навигация по меню (Callbacks) ---
@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu())
    await callback.answer()

@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    await callback.message.edit_text("📦 Выберите товар:", reply_markup=catalog_menu())
    await callback.answer()

@router.callback_query(F.data == "contacts")
async def show_contacts(callback: CallbackQuery):
    await callback.message.edit_text(
        "📞 Свяжитесь с нами:\nТелефон: +7 (999) 123-45-67\nEmail: shop@example.com",
        reply_markup=main_menu()
    )
    await callback.answer()

# --- Просмотр товара ---
@router.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    product_id = callback.data.split("_")[1]
    product = PRODUCTS.get(product_id)
    if not product:
        await callback.answer("Товар не найден!")
        return
    text = f"🆕 {product['name']}\n\n{product['desc']}\n\n💰 Цена: {product['price']}₽"
    await callback.message.edit_text(text, reply_markup=product_actions(product_id))
    await callback.answer()

# --- Добавление в корзину ---
@router.callback_query(F.data.startswith("add_"))
async def add_to_cart_callback(callback: CallbackQuery):
    product_id = callback.data.split("_")[1]
    user_id = callback.from_user.id
    add_to_cart(user_id, product_id)
    await callback.answer("✅ Товар добавлен в корзину!", show_alert=True)

# --- Просмотр корзины ---
@router.callback_query(F.data == "view_cart")
async def view_cart(callback: CallbackQuery):
    user_id = callback.from_user.id
    cart_data = get_cart(user_id)
    
    if not cart_data:
        await callback.message.edit_text("🛒 Ваша корзина пуста.", reply_markup=main_menu())
        await callback.answer()
        return

    total = 0
    text = "🛒 *Ваша корзина:*\n\n"
    for product_id, qty in cart_data:
        product = PRODUCTS.get(product_id)
        if product:
            price = product['price']
            total += price * qty
            text += f"• {product['name']} x{qty} = {price * qty}₽\n"

    text += f"\n💰 *Итого: {total}₽*"
    await callback.message.edit_text(text, reply_markup=cart_actions(), parse_mode="Markdown")
    await callback.answer()

# --- Очистка корзины ---
@router.callback_query(F.data == "clear_cart")
async def clear_cart_callback(callback: CallbackQuery):
    clear_cart(callback.from_user.id)
    await callback.message.edit_text("🗑 Корзина очищена.", reply_markup=main_menu())
    await callback.answer()

# --- Оформление заказа (начало) ---
@router.callback_query(F.data == "checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📞 Введите ваш номер телефона (например, +7 999 123-45-67):")
    await state.set_state(OrderState.waiting_for_phone)
    await callback.answer()

# --- Прием телефона ---
@router.message(OrderState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("🏠 Введите ваш адрес доставки:")
    await state.set_state(OrderState.waiting_for_address)

# --- Прием адреса и сохранение заказа ---
@router.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext, bot: Bot):
    address = message.text
    user_id = message.from_user.id
    
    data = await state.get_data()
    phone = data.get("phone")
    
    cart_data = get_cart(user_id)
    if not cart_data:
        await message.answer("❌ Ваша корзина пуста. Заказ не оформлен.")
        await state.clear()
        return

    items_list = []
    total = 0
    for product_id, qty in cart_data:
        product = PRODUCTS.get(product_id)
        if product:
            items_list.append(f"{product['name']} x{qty}")
            total += product['price'] * qty

    items_str = ", ".join(items_list)
    order_id = save_order(user_id, items_str, total, phone, address)
    
    # Очищаем корзину и состояние
    clear_cart(user_id)
    await state.clear()
    
    # Подтверждение пользователю
    await message.answer(
        f"✅ Заказ #{order_id} оформлен!\nСумма: {total}₽\nСкоро с вами свяжется менеджер.",
        reply_markup=main_menu()
    )
    
    # Уведомление админу
    admin_text = (
        f"🆕 *Новый заказ!*\n"
        f"ID заказа: {order_id}\n"
        f"Товары: {items_str}\n"
        f"Сумма: {total}₽\n"
        f"Телефон: {phone}\n"
        f"Адрес: {address}"
    )
    await bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown")


# --- Админ-команда: просмотр заказов ---
@router.message(Command("orders"))
async def admin_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет прав.")
        return
    
    orders = get_orders(limit=5)
    if not orders:
        await message.answer("Заказов пока нет.")
        return
    
    text = "📋 *Последние заказы:*\n\n"
    for order in orders:
        order_id, user_id, items, total, phone, address, status = order
        text += f"#{order_id} | {status}\nТовары: {items}\nСумма: {total}₽\nТел: {phone}\nАдрес: {address}\n---\n"
    
    await message.answer(text, parse_mode="Markdown")
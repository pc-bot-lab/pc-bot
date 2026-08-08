from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import PRODUCTS

# Главное меню
def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart")],
        [InlineKeyboardButton(text="📞 Контакты", callback_data="contacts")]
    ])
    return kb

# Каталог (список категорий/товаров)
def catalog_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, product in PRODUCTS.items():
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"{product['name']} - {product['price']}₽", callback_data=f"product_{pid}")
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return kb

# Кнопки для конкретного товара
def product_actions(product_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{product_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="catalog")]
    ])
    return kb

# Корзина + кнопка оформления
def cart_actions():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    return kb
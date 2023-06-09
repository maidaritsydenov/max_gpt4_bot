import csv
import logging
import asyncio
import traceback
import html
import json
import tempfile
import pydub
import platform
from pathlib import Path
from datetime import datetime, timedelta

import telegram
from telegram import (Update, User, InlineKeyboardButton, InlineKeyboardMarkup,
                      BotCommand, LabeledPrice)
from telegram.constants import ParseMode
from telegram.ext import (Application, ApplicationBuilder, CallbackContext,
                          CommandHandler, MessageHandler, CallbackQueryHandler,
                          AIORateLimiter, filters, PreCheckoutQueryHandler, ContextTypes)


import openai

import config
import database
import openai_utils
from get_current_usd import usd_rate_check
from synthesis import main
import messages


# setup
db = database.Database()
logger = logging.getLogger(__name__)
user_semaphores = {}
platname = platform.system()

ZERO = 0
GROUP_ATTR = '-'
CWD = Path.cwd()



def split_text_into_chunks(text, chunk_size):
    """Функция разделяет текст на чанки."""

    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


async def register_user_if_not_exists(update: Update, context: CallbackContext, user: User):
    # if not db.check_if_user_exists(user.id) and not update.message.from_user.is_bot:
    if not db.check_if_user_exists(user.id):
        db.add_new_user(
            user.id,
            update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name= user.last_name
        )
        db.start_new_dialog(user.id)

    if db.get_user_attribute(user.id, "current_dialog_id") is None:
        db.start_new_dialog(user.id)

    if user.id not in user_semaphores:
        user_semaphores[user.id] = asyncio.Semaphore(1)


async def check_token_limit(update: Update, context: CallbackContext):
    """Функция проверяет token_limits перед каждым запросом пользователя,
    Если пользователь превысил лимит - False (бот не реагирует на запросы)."""
    keyboard = [
        [InlineKeyboardButton("💰 Купить", callback_data="buy_package")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    user_id = update.message.from_user.id
    balance = db.get_user_attribute(user_id, 'token_limit')

    if balance <= ZERO and user_id not in config.admin_ids:
        text = "🥲 К сожалению, Вы исчерпали весь лимит токенов на сегодня.\n\nВы можете подождать ежедневного обновления токенов или купить пакет токенов."
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        db.set_user_attribute(user_id, 'token_limit', ZERO)
        return False
    return True


async def reset_token_limit(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    """Функция для админа. Обнуление token_limit у юзера {user_id}."""

    user_id = update.message.from_user.id
    chat_id=update.effective_chat.id
    text="Используйте следующую конструкцию:\n\n/reset {user_id}"
    
    if user_id in config.admin_ids:
        try:
            if not context.args:
                await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
                return
            else:
                int(context.args[0])

        except ValueError:
            text="Используйте следующую конструкцию:\n\n/reset {user_id}\n<code>{user_id}</code> должен быть числом."
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            return
        
        if not db.check_if_user_exists(int(context.args[0])):
            
            text=f"Пользователь с user_id: <code>{int(context.args[0])}</code> не зарегистрирован"
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            return
        else:
            db.set_user_attribute(int(context.args[0]), 'token_limit', ZERO)
            username = db.get_user_attribute(int(context.args[0]), "username")
            text=f"Баланс пользователя с user_id: <code>{int(context.args[0])} username: @{username}</code> обнулен!"
            text_for_user = 'Администратор обнулил Ваш баланс.'
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            await context.bot.send_message(int(context.args[0]), text_for_user, parse_mode=ParseMode.HTML)
    else:            
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return


async def add_token_limit_by_id(update: Update, context: CallbackContext):
    """Функция для админа. Добавление {amount} токенов к token_limit у юзера {user_id}."""
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return

    user_id = update.message.from_user.id
    chat_id=update.effective_chat.id
    text="Используйте следующую конструкцию:\n\n/add {user_id} {amount}"
    
    if user_id in config.admin_ids:
        try:
            if not context.args:
                await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
                return
            else:
                int(context.args[0])
                int(context.args[1])

        except ValueError:
            text="Используйте следующую конструкцию:\n\n/add {user_id} {amount}\n<code>{user_id}</code> и <code>{amount}</code> должны быть числами и идти через пробел."
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            return
        
        if not db.check_if_user_exists(int(context.args[0])):
            text=f"Пользователь с user_id: <code>{int(context.args[0])}</code> не зарегистрирован"
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            return
        else:
            db.set_user_attribute(int(context.args[0]), 'token_limit', db.get_user_attribute(int(context.args[0]), 'token_limit') + int(context.args[1]))
            text=f"Баланс пользователя с user_id: <code>{int(context.args[0])}</code> пополнен на {int(context.args[1])} токенов!"
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            text=f"Ваш баланс пополнен на {int(context.args[1])} токенов!\nПроверить баланс можно в профиле /profile"
            await context.bot.send_message(int(context.args[0]), text, parse_mode=ParseMode.HTML)
    else:            
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return


async def send_users_list_for_admin(update: Update, context: CallbackContext):
    """Функция для админа. Отправляет файл со списком юзеров."""
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    
    user_id = update.message.from_user.id
    chat_id=update.effective_chat.id

    date = (str(datetime.now())[:10:])
    if platname == 'Windows':
        path_to_users_file = f'{CWD}/max_gpt4_bot/users/users.csv'
    else:
        path_to_users_file = f'{CWD}/users/users_{date}.csv'
    
    
    if user_id in config.admin_ids:
        user_list_csv, count = db.get_users_list(user_id)

        header = ['Number', "ID", 'Username', 'First_name', 'Last_name', 'Last_interaction', 'N_used_tokens', 'Balance', 'Is_admin', 'Is_paid_sub']
        with open(path_to_users_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            writer.writerows(user_list_csv)

        await update.message.reply_document(open(path_to_users_file, 'rb'), caption=f'👤 Всего юзеров: <b>{count}</b>', parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return
    

async def send_paid_subs_list_for_admin(update: Update, context: CallbackContext):
    """Функция для админа. Отправляет файл со списком платных подписчиков."""
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    user_id = update.message.from_user.id
    
    date = (str(datetime.now())[:10:])
    
    if platname == 'Windows':
        path_to_users_file = f'{CWD}/max_gpt4_bot/users/paid_subs.csv'
    else:
        path_to_users_file = f'{CWD}/users/paid_subs_{date}.csv'
    
    if user_id in config.admin_ids:
        paid_subs_list_csv, count = db.get_paid_subs_list(user_id)

        header = ['Number', "ID", 'Username', 'First_name', 'Last_name', 'Last_interaction', 'N_used_tokens', 'Balance', 'Is_admin', 'Is_paid_sub']
        with open(path_to_users_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)
            writer.writerows(paid_subs_list_csv)

        await update.message.reply_document(open(path_to_users_file, 'rb'), caption=f'👤 Всего платных подписчиков: <b>{count}</b>', parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return


async def send_prices(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    keyboard = []
    for package, package_dict in config.prices_package.items():
        keyboard.append([InlineKeyboardButton(package_dict["name"], callback_data=f"set_package|{package}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.edit_text("<b>Платежная система:</b> ЮMoney\n\n- Токены не сгорают\n- Купленные пакеты токенов суммируются", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    

async def send_buy_callback_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    price_package = query.data.split('|')[1]
    
    name = config.prices_package[price_package]['name']
    price = config.prices_package[price_package]['price']
        
    await buy_callback(update, context, name, price)


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str, price: int) -> None:
    """Payment system. Отправка инвойса без оплаты доставки."""

    user_id = update.callback_query.from_user.id
    title = "🛒 Корзина"
    description = name
    # select a payload just for you to recognize its the donation from your bot
    payload = "Custom-Payload"
    # In order to get a provider_token see https://core.telegram.org/bots/payments#getting-a-token
    currency = "RUB"
    # price in dollars
    price = price
    # price * 100 so as to include 2 decimal points
    prices = [LabeledPrice(f"{name}", price * 100)]

    # optionally pass need_name=True, need_phone_number=True,
    # need_email=True, need_shipping_address=True, is_flexible=True
    try:
        await context.bot.send_invoice(
            user_id, title, description, payload, config.payment_token, currency, prices
        )
    except Exception as e:
            text=f"Что-то пошло не так: {e}"
            await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
            return


# it's the pre-checkout
async def precheckout_callback(update: Update, context: CallbackContext) -> None:
    """Payment system. Answers the PreQecheckoutQuery"""
    query = update.pre_checkout_query
    # check the payload, is this from your bot?
    if query.invoice_payload == "Custom-Payload":
        # Если все данные для оплаты введены правильно, возвращаем True
        await query.answer(ok=True)
    else:
        # Если данные для оплаты введены неверно, возвращаем False
        await query.answer(ok=False, error_message="Неверный идентификатор платежа")
        

# finally, after contacting the payment provider...
async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Payment system. Confirms the successful payment."""
    prices_dict = {
        69: 10000,
        199: 50000,
        399: 100000
    }
    
    date = (str(datetime.now())[:10:])
    user_id = update.message.from_user.id
    
    total_amount = int(update.message.successful_payment.total_amount)/100
    provider_payment_charge_id = update.message.successful_payment.provider_payment_charge_id  
    
    db.set_user_attribute(user_id, 'token_limit', prices_dict[total_amount] + db.get_user_attribute(user_id, 'token_limit'))
    db.set_user_attribute(user_id, 'is_paid_sub', True)
    
    header = ["Date", "ID", 'Username', 'First_name', 'Last_name', 'Last_interaction', 'N_used_tokens', 'Balance', 'Is_admin', 'Is_paid_sub', "Provider_payment_charge_id"]
    
    if platname == 'Windows':
        path_to_users_file = f'{CWD}/max_gpt4_bot/users/provider_payment_charge_id.csv'
    else:
        path_to_users_file = f'{CWD}/users/provider_payment_charge_id.csv'
    
    user_attr = db.get_one_paid_sub_list(user_id, date, provider_payment_charge_id)
    
    with open(path_to_users_file, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        writer.writerows(user_attr)

    await update.message.reply_text(f"Спасибо за платеж❤️\n\nВаш баланс равен {db.get_user_attribute(user_id, 'token_limit')} токенов!\nПроверить баланс можно в личном кабинете /profile")
    await context.bot.send_document(config.admin_ids[0], open(path_to_users_file, 'rb'), caption=f'💰 Совершен платеж!', parse_mode=ParseMode.HTML)


async def copy_to_all(update: Update, context: CallbackContext):
    """Функция для админа. Пересылает сообщение всем юзерам. (Реклама)"""
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    user_id = update.message.from_user.id
    chat_id=update.effective_chat.id
    message = update.message

    if user_id in config.admin_ids:
        banned_ids = []
        try:
            user_ids_list = db.for_text_to_all()           
            for user in user_ids_list:
                try:
                    await context.bot.copy_message(user, from_chat_id=message.chat_id, message_id=message.message_id, parse_mode=ParseMode.HTML)
                except Exception as e:
                    banned_ids.append(user)
            text = f'blocked_ids: {banned_ids}'
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)

        except ValueError:
            text="Ошибка. copy_to_all()"
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            return
    else:            
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return
    

async def send_text_to_all(update: Update, context: CallbackContext):
    """Функция для админа. Отправляет текст после команды /send_message всем юзерам."""
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    
    user_id = update.message.from_user.id
    chat_id=update.effective_chat.id
    text="Используйте следующую конструкцию:\n\n/send_message {text}"
    banned_ids = []
    if user_id in config.admin_ids:
        try:
            if not context.args:
                await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
                return
            else:
                text = ' '.join(map(str, context.args))
                user_ids_list = db.for_text_to_all()                
                for user in user_ids_list:
                    try:
                        await context.bot.send_message(user, text, parse_mode=ParseMode.HTML)
                    except Exception as e:
                        banned_ids.append(user)
                text = f'blocked_ids: {banned_ids}'
                await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
        except ValueError:
            text="Используйте следующую конструкцию:\n\n/send_message {text}\nДобавить функцию загрузки фото, видео или гиф"
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
            return
    else:            
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return
    

async def start_handle(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    keyboard = [
        [InlineKeyboardButton("🎭 Выбрать роль", callback_data="Выбрать роль")],
        [InlineKeyboardButton("⬅️ Восстановить диалог", callback_data="Восстановить диалог"), InlineKeyboardButton("🆕 Начать новый диалог", callback_data="Начать диалог")],
        [InlineKeyboardButton("💰 Купить пакет токенов", callback_data="buy_package")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    user_id = update.message.from_user.id
    
    if user_id in config.admin_ids:
        db.set_user_attribute(user_id, "is_admin", True)
    
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    db.start_new_dialog(user_id)
    balance = db.get_user_attribute(user_id, "token_limit")
    
    reply_text = "Привет! Я <b>Макс,</b> бот реализованный с помощью GPT-3.5 OpenAI API 🤖\n\n"    
    
    # Проверка на сообщение из группы или из приватных чатов
    chat_id = str(update.effective_chat.id)
    if GROUP_ATTR in chat_id:
        reply_text += "Меня можно применять практически к любой задаче, связанной с пониманием или созданием естественного языка, кода или изображения.\n\n✴️ Спроси меня о чем нибудь <b>текстовым</b> или <b>голосовым</b> сообщением, используя слово <code>Макс, '''ВАШ ЗАПРОС'''</code> \n\n✴️ Я могу нарисовать <b>изображение</b>.Для этого отправь мне сообщение\n<code>Макс, нарисуй '''ВАШ ЗАПРОС'''</code>\n\n✴️ Я могу отправить тебе <b>голосовое</b>. Для этого используй конструкцию\n<code>Расскажи '''ВАШ ЗАПРОС'''</code>\n\n<i>*Используй английский язык для повышения качества ответа*</i>\n"
    
    elif GROUP_ATTR not in chat_id:
        reply_text += "Меня можно применять практически к любой задаче, связанной с пониманием или созданием естественного языка, кода или изображения.\n\n✴️ Спроси меня о чем нибудь <b>текстовым</b> или <b>голосовым</b> сообщением\n\n✴️ Я могу нарисовать <b>изображение</b>. Для этого отправь мне сообщение \n<code>Нарисуй '''ВАШ ЗАПРОС'''</code>\n\n✴️ Я могу отправить тебе <b>голосовое</b>. Для этого используй конструкцию\n<code>Расскажи '''ВАШ ЗАПРОС'''</code>\n\n<i>*Используй английский язык для повышения качества ответа*</i>\n"
    
    else:
        reply_text = 'В <b>приватных чатах</b> используй конструкцию <code>Нарисуй</code> для генерации изображения или любое текстовое или голосовое сообщение\n\nВ <b>группах</b> используй конструкцию <code>Макс, </code> или <code>Макс, нарисуй</code> для генерации изображения'
    
    reply_text += f'\n\n💰 Доступно токенов: <b>{balance}</b>\n<i>🔥 Токены обновляются каждый день в 10:00 по МСК.</i>\n'
    
    # reply_text += f'\n\n{HELP_MESSAGE}'
    
    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def help_handle(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("🤖 Что умеет бот?", callback_data="Что умеет бот")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await context.bot.send_message(chat_id, messages.HELP_MESSAGE, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    

async def profile_handle(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    user_id = update.message.from_user.id
    keyboard = [
        [InlineKeyboardButton("🎭 Выбрать роль", callback_data="Выбрать роль")],
        [InlineKeyboardButton("⬅️ Восстановить диалог", callback_data="Восстановить диалог"), InlineKeyboardButton("🆕 Начать новый диалог", callback_data="Начать диалог")],
        [InlineKeyboardButton("💰 Купить пакет токенов", callback_data="buy_package")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    name = db.get_user_attribute(user_id, "first_name")
    balance = db.get_user_attribute(user_id, "token_limit")
    
    s_date, usd_rate = await get_s_date_user_rate(user_id)
    
    if db.get_user_attribute(user_id, 'is_admin'): is_admin = "✅"
    else: is_admin = "❌"
    
    if db.get_user_attribute(user_id, 'is_paid_sub'): is_paid_sub = "✅"
    else: is_paid_sub = "❌" 
    
    text = f"🗄 <b>Личный кабинет</b>\n\n👤 <b>Имя:</b> {name} (<b>ID:</b> {user_id})\n💰 <b>Баланс:</b> {balance} токенов\n\n🧑‍💻 Админ: {is_admin}\n🤩 Платный подписчик: {is_paid_sub}\n\n<i>🔥 Токены обновляются ежедневно в 10:00 по МСК</i>"
    
    await register_user_if_not_exists(update, context, update.message.from_user)
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def profile_button_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    try:
        if query.data == 'Выбрать роль':
            await show_chat_modes_handle(query, context)
        elif query.data == 'Начать диалог':
            await new_dialog_handle(query, context)
        elif query.data == 'Восстановить диалог':
            await retry_handle(query, context)
        elif query.data == 'buy_package':
            await send_prices(query, context)
        elif query.data == 'Что умеет бот':
            await ability_message(query, context)
        else:
            await update.message.reply_text('Неверный query.data. Зови админа!')
            # await query.edit_message_text('Неверный query.data. Зови админа!', parse_mode=ParseMode.HTML)

    except Exception as e:
        error_text = f"Что-то пошло не так. Ошибка: {e}"
        logger.error(error_text)
        await update.message.reply_text(error_text)
        return
    

# async def delete_user(update: Update, context: CallbackContext):
#     """Функция для админа. Удаляет юзера/бота из БД (Если в юзерлист попал бот)."""
#     user_id = update.message.from_user.id
#     chat_id=update.effective_chat.id
#     text="Используйте следующую конструкцию:\n\n/delete {user_or_bot_id}"
    
#     if user_id in config.admin_ids:
#         try:
#             if not context.args:
#                 await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
#                 return
#             else:
#                 int(context.args[0])
#                 text = db.delete_user(int(context.args[0]))
#                 await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
#         except ValueError:
#             text="Используйте следующую конструкцию:\n\n/delete {user_or_bot_id}. Удалить функцию"
#             await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
#             return
#     else:            
#         await update.message.reply_text("Эта команда доступна только администраторам.")
#         return


async def help_handle_for_admins(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    if user_id in config.admin_ids:
        db.set_user_attribute(user_id, "last_interaction", datetime.now())
        await update.message.reply_text(messages.HELP_MESSAGE_FOR_ADMINS, parse_mode=ParseMode.HTML)
        return
    await update.message.reply_text("Эта команда доступна только администраторам.")
    return


async def retry_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if not await check_token_limit(update, context): return
    if await is_previous_message_not_answered_yet(update, context): return
    
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    dialog_messages = db.get_dialog_messages(user_id, dialog_id=None)
    if len(dialog_messages) == 0:
        await update.message.edit_text("Нет сообщений для восстановления диалога 🤷‍♂️")
        return

    last_dialog_message = dialog_messages.pop()
    db.set_dialog_messages(user_id, dialog_messages, dialog_id=None)  # last message was removed from the context

    await message_handle(update, context, message=last_dialog_message["user"], use_new_dialog_timeout=False)


async def message_handle(update: Update, context: CallbackContext, message=None, use_new_dialog_timeout=True):
    # check if message is edited
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
        
    await register_user_if_not_exists(update, context, update.message.from_user)
    if not await check_token_limit(update, context): return
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")
    
    async with user_semaphores[user_id]:
        # new dialog timeout
        if use_new_dialog_timeout:
            if (datetime.now() - db.get_user_attribute(user_id, "last_interaction")).seconds > config.new_dialog_timeout and len(db.get_dialog_messages(user_id)) > 0:
                db.start_new_dialog(user_id)
                await update.message.edit_text(f"Начат новый диалог (Роль: <b>{openai_utils.CHAT_MODES[chat_mode]['name']}</b>) ✅", parse_mode=ParseMode.HTML)
        db.set_user_attribute(user_id, "last_interaction", datetime.now())

        # send typing action
        await update.message.chat.send_action(action="typing")

        try:
            message = message or update.message.text
            
            chat_id = str(update.effective_chat.id)
            # Если с группы, то убираю первое слово "Макс, " из сообщения пользователя
            if (GROUP_ATTR in chat_id) and (config.CHATGPT_GROUP in message):
                message = message[6::]
            else:
                message = message or update.message.text
            

            dialog_messages = db.get_dialog_messages(user_id, dialog_id=None)
            parse_mode = {
                "html": ParseMode.HTML,
                "markdown": ParseMode.MARKDOWN
            }[openai_utils.CHAT_MODES[chat_mode]["parse_mode"]]

            chatgpt_instance = openai_utils.ChatGPT(use_chatgpt_api=config.use_chatgpt_api)


            if message.startswith(config.SALUTESPEECH_PRIVATE):
                await update.message.chat.send_action(action="typing")

                chat_id = update.effective_chat.id
                username = update.message.chat.username
                unique_id = update.update_id
                
                answer, n_used_tokens, n_first_dialog_messages_removed = await chatgpt_instance.send_message(
                        message,
                        dialog_messages=dialog_messages,
                        chat_mode=chat_mode
                    )
                if "<" in answer or '>' in answer:
                    await update.message.chat.send_action(action="typing")
                    text = 'Невозможно озвучить код. Пожалуйста, измените режим.'
                    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
                else:
                    await update.message.chat.send_action(action="record_voice")
                    audio_file_path = await main(answer, unique_id)
                    # TODO - Учет потраченных секунд
                    
                    file = open(f'{audio_file_path}', 'rb')
                    try:
                        # await update.message.reply_text(answer, parse_mode=ParseMode.HTML)
                        await update.message.reply_voice(voice=file, caption=f'@{username}')
                        file.close()
                    except telegram.error.TelegramError as e:
                            print(f"Error sending voice message: {e}")
                            
                            
                # update user data
                new_dialog_message = {"user": message, "bot": answer, "date": datetime.now()}
                db.set_dialog_messages(
                    user_id,
                    db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
                    dialog_id=None
                )
                
                n_used_tokens_last_message = n_used_tokens
                
                db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + db.get_user_attribute(user_id, "n_used_tokens"))
                db.set_user_attribute(user_id, "token_limit", db.get_user_attribute(user_id, "token_limit") - n_used_tokens_last_message)
                # await debbug(update, context, n_used_tokens_last_message)
            else:
                if config.enable_message_streaming:
                    gen = chatgpt_instance.send_message_stream(message, dialog_messages=dialog_messages, chat_mode=chat_mode)
                else:
                    answer, n_used_tokens, n_first_dialog_messages_removed = await chatgpt_instance.send_message(
                        message,
                        dialog_messages=dialog_messages,
                        chat_mode=chat_mode
                    )
                    async def fake_gen():
                        yield "finished", answer, n_used_tokens, n_first_dialog_messages_removed

                    gen = fake_gen()

                # send message to user
                prev_answer = ""
                i = -1
                async for gen_item in gen:
                    i += 1

                    status = gen_item[0]
                    if status == "not_finished":
                        status, answer = gen_item
                    elif status == "finished":
                        status, answer, n_used_tokens, n_first_dialog_messages_removed = gen_item
                    else:
                        raise ValueError(f"Streaming status {status} is unknown")

                    answer = answer[:4096]  # telegram message limit
                    if i == 0:  # send first message (then it'll be edited if message streaming is enabled)
                        try:                    
                            sent_message = await update.message.reply_text(answer, parse_mode=parse_mode)
                        except telegram.error.BadRequest as e:
                            if str(e).startswith("Message must be non-empty"):  # first answer chunk from openai was empty
                                i = -1  # try again to send first message
                                continue
                            else:
                                sent_message = await update.message.reply_text(answer)
                    else:  # edit sent message
                        # update only when 100 new symbols are ready
                        if abs(len(answer) - len(prev_answer)) < 100 and status != "finished":
                            continue

                        try:                    
                            await context.bot.edit_message_text(answer, chat_id=sent_message.chat_id, message_id=sent_message.message_id, parse_mode=parse_mode)
                        except telegram.error.BadRequest as e:
                            if str(e).startswith("Message is not modified"):
                                continue
                            else:
                                await context.bot.edit_message_text(answer, chat_id=sent_message.chat_id, message_id=sent_message.message_id)

                        await asyncio.sleep(0.01)  # wait a bit to avoid flooding
                        
                    prev_answer = answer

                # update user data
                new_dialog_message = {"user": message, "bot": answer, "date": datetime.now()}
                db.set_dialog_messages(
                    user_id,
                    db.get_dialog_messages(user_id, dialog_id=None) + [new_dialog_message],
                    dialog_id=None
                )
                
                n_used_tokens_last_message = n_used_tokens
                
                db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + db.get_user_attribute(user_id, "n_used_tokens"))
                db.set_user_attribute(user_id, "token_limit", db.get_user_attribute(user_id, "token_limit") - n_used_tokens_last_message)
                
                # await debbug(update, context, n_used_tokens_last_message)
                
        except Exception as e:
            error_text = f"Что-то пошло не так. Ошибка: {e}"
            logger.error(error_text)
            await update.message.reply_text(error_text)
            return

        # send message if some messages were removed from the context
        if n_first_dialog_messages_removed > 0:
            keyboard = [
                [InlineKeyboardButton("🆕 Начать новый диалог", callback_data="Начать диалог")]
                ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            if n_first_dialog_messages_removed == 1:
                text = "✍️ <i>Note:</i> Ваш текущий диалог слишком длинный. Ваше <b>first message</b> было удалено из контекста.\n Начните новый диалог."
            else:
                text = f"✍️ <i>Note:</i> Ваш текущий диалог слишком длинный. Ваше <b>{n_first_dialog_messages_removed} first messages</b> было удалено из контекста..\n Начните новый диалог."
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def is_previous_message_not_answered_yet(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    if user_semaphores[user_id].locked():
        text = "⏳ <b>Пожалуйста подождите</b> обработки предыдущего сообщения"
        await update.message.reply_text(text, reply_to_message_id=update.message.id, parse_mode=ParseMode.HTML)
        return True
    else:
        return False
    
    
async def dalle(update: Update, context):
    """Функция генерации картинок с помощью DALL-E от OpenAI.
    TO DO: добавить другие режимы: редактирование картинок + генерация версий."""
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return

    await register_user_if_not_exists(update, context, update.message.from_user)
    if not await check_token_limit(update, context): return
    
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    
    await update.message.chat.send_action(action="upload_photo")    
    
    prompt = ''.join(update.message.text)
    chat_id = str(update.effective_chat.id)
    
    if (GROUP_ATTR in chat_id) and (config.DALLE_GROUP in prompt):
        # Если сообщение пришло с группы/канала, то убираем первые два слова "Макс, нарисуй" из сообщения пользователя
        prompt = ''.join(update.message.text[14::])
        # Отправляем АПИ запрос в DALL-E с сообщением пользователя и получаем ответ
        response = openai.Image.create(
                prompt=prompt,
                n=1,
                size="1024x1024"
                )
        image_url = response['data'][0]['url']

        # Отправляем сгенерированное изображение пользователю
        await update.message.chat.send_action(action="upload_photo")
        await context.bot.send_photo(update.effective_chat.id, photo=image_url)
        await context.bot.send_message(update.effective_chat.id, prompt, parse_mode=ParseMode.HTML)

    # Если с приватных чатов, то убираем первое слово "Нарисуй"
    elif (GROUP_ATTR not in chat_id) and config.DALLE_PRIVATE in prompt:
        prompt = ''.join(update.message.text[8::])
        try:
            response = openai.Image.create(
                    prompt=prompt,
                    n=1,
                    size="1024x1024"
                    )
            image_url = response['data'][0]['url']
            await update.message.chat.send_action(action="upload_photo")
            await context.bot.send_photo(update.effective_chat.id, photo=image_url)
            await context.bot.send_message(update.effective_chat.id, prompt, parse_mode=ParseMode.HTML)
        except openai.error.OpenAIError as e:
            print(e.http_status)
            print(e.error)
    else:
        text = 'Ошибка. Функция работает только из приватных чатов, группы или канала.\n\nИспользуйте конструкцию <code>Макс, нарисуй</code> в группах, или <code>Нарисуй</code> в приватных чатах.'
        await context.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML)
    
    
    # calculate spent dollars
    # n_spent_dollars = config.dalle_price_per_one_image

    n_used_tokens = int(1000)
    db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + db.get_user_attribute(user_id, "n_used_tokens"))
    db.set_user_attribute(user_id, "token_limit", db.get_user_attribute(user_id, "token_limit") - n_used_tokens)


async def voice_message_handle(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return

    chat_id = str(update.effective_chat.id)
    if (GROUP_ATTR in chat_id):
        text = f'💢 Распознавание голосовых сообщений не работает в группе\n\nПерейдите в бота чтобы воспользоваться данным функционалом.\n\n@{config.bot_username}'
        await context.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML)
    else:
        await register_user_if_not_exists(update, context, update.message.from_user)
        if await is_previous_message_not_answered_yet(update, context): return
        
        if not await check_token_limit(update, context): return


        user_id = update.message.from_user.id
        db.set_user_attribute(user_id, "last_interaction", datetime.now())

        voice = update.message.voice
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            
            voice_ogg_path = Path(tmp_dir, "voice.ogg")

            # download
            voice_file = await context.bot.get_file(voice.file_id)
            await voice_file.download_to_drive(voice_ogg_path)

            # convert to mp3    
            voice_mp3_path = Path(tmp_dir, "voice.mp3")
            
            # voice_mp3_path = tmp_dir / "voice.mp3"
            pydub.AudioSegment.from_file(voice_ogg_path).export(voice_mp3_path, format="mp3")

            # transcribe
            with open(voice_mp3_path, "rb") as f:
                transcribed_text = await openai_utils.transcribe_audio(f)

        text = f"🎤: <i>{transcribed_text}</i>"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

        await message_handle(update, context, message=transcribed_text)

        # calculate spent dollars
        n_spent_dollars = voice.duration * (config.whisper_price_per_1_min / 60)

        # normalize dollars to tokens (it's very convenient to measure everything in a single unit)
        price_per_1000_tokens = config.chatgpt_price_per_1000_tokens if config.use_chatgpt_api else config.gpt_price_per_1000_tokens
        n_used_tokens = int(n_spent_dollars / (price_per_1000_tokens / 1000))
        db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + db.get_user_attribute(user_id, "n_used_tokens"))
        db.set_user_attribute(user_id, "token_limit", db.get_user_attribute(user_id, "token_limit") - n_used_tokens)
        


async def new_dialog_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if not await check_token_limit(update, context): return
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    db.start_new_dialog(user_id)
    # await update.message.reply_text("Начат новый диалог ✅")

    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")
    await update.message.reply_text(f"{openai_utils.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)
    # await update.message.reply_text(f"{openai_utils.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=openai_utils.CHAT_MODES[chat_mode]['parse_mode'])
    


async def show_chat_modes_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    keyboard = []
    for chat_mode, chat_mode_dict in openai_utils.CHAT_MODES.items():
        keyboard.append([InlineKeyboardButton(chat_mode_dict["name"], callback_data=f"set_chat_mode|{chat_mode}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.edit_text("Выберите роль:", reply_markup=reply_markup)


async def ability_message(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    # user_id = update.message.from_user.id

    links_to_photo = [
        telegram.InputMediaPhoto('https://i.postimg.cc/FFS7ZcGf/1.jpg'),
        telegram.InputMediaPhoto('https://i.postimg.cc/760wg1Dw/2.jpg'),
        telegram.InputMediaPhoto('https://i.postimg.cc/hPpgbtFz/3.jpg'),
        ]

    keyboard = [[InlineKeyboardButton("Начать чат", callback_data="Начать диалог")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.edit_text(messages.ABILITY_MESSAGE, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    await update.message.reply_media_group(media=links_to_photo, disable_notification=True)


async def set_chat_mode_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    chat_mode = query.data.split("|")[1]

    db.set_user_attribute(user_id, "current_chat_mode", chat_mode)
    db.start_new_dialog(user_id)

    await query.edit_message_text(f"{openai_utils.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


async def show_balance_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    # Получить текущий курс usd to rub
    s_date, usd_rate = await get_s_date_user_rate(user_id)
    price_per_1000_tokens = config.chatgpt_price_per_1000_tokens if config.use_chatgpt_api else config.gpt_price_per_1000_tokens
    n_used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
    
    rub_rate_per_1000_tokens = (price_per_1000_tokens * usd_rate)
    # n_spent_rub = (n_used_tokens * rub_rate_per_1000_tokens)/1000

    balance = db.get_user_attribute(user_id, 'token_limit')

    text = f'💰 Ваш баланс: <b>{balance}</b> токенов.\n'
    # text += f"Вы потратили <b>{n_spent_rub:.03f} руб.</b>\n"
    # text += f"Вы использовали <b>{n_used_tokens}</b> токенов\n\n"
    
    text += f'💲 Курс доллара к рублю на {s_date}: <b>{usd_rate:.02f} руб.</b>\n\n'

    text += "🏷️ Prices\n"
    text += f"<i>- ChatGPT: {rub_rate_per_1000_tokens:.02f} руб. за 1000 токенов\n"
    text += f"- Whisper (voice recognition): {(config.whisper_price_per_1_min * usd_rate):.02f} руб. за 1 минуту\n"
    text += f"- DALL-E (image generation): {(config.dalle_price_per_one_image * usd_rate):.02f} руб. за 1 изображение</i>"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML) 



async def get_s_date_user_rate(user_id):
    old_answer = []
    s_date_old = db.get_user_attribute(user_id, 's_date')
    usd_rate_old = db.get_user_attribute(user_id, 'usd_rate')

    old_answer.append(s_date_old)
    old_answer.append(usd_rate_old)

    new_answer = usd_rate_check(old_answer, user_id)

    s_date = new_answer[0]
    usd_rate = new_answer[1]
            
    db.set_user_attribute(user_id, 's_date', s_date)
    db.set_user_attribute(user_id, 'usd_rate', usd_rate)
    
    return s_date, usd_rate



async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 К сожалению, <b>измененные сообщения</b> не поддерживаются"
    await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def error_handle(update: Update, context: CallbackContext) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        # collect error message
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # split text into multiple messages due to 4096 character limit
        for message_chunk in split_text_into_chunks(message, 4096):
            try:
                await context.bot.send_message(update.effective_chat.id, message_chunk, parse_mode=ParseMode.HTML)
            except telegram.error.BadRequest:
                # answer has invalid characters, so we send it without parse_mode
                await context.bot.send_message(update.effective_chat.id, message_chunk)
    except:
        await context.bot.send_message(update.effective_chat.id, "Some error in error handler")


async def debbug(update: Update, context: CallbackContext, n_used_tokens_last_message: int):
    price_per_1000_tokens = config.chatgpt_price_per_1000_tokens if config.use_chatgpt_api else config.gpt_price_per_1000_tokens
    user_id = update.message.from_user.id

    # Получить текущий курс usd to rub
    old_answer = []

    n_used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
    s_date = db.get_user_attribute(user_id, 's_date')
    usd_rate = db.get_user_attribute(user_id, 'usd_rate')

    old_answer.append(s_date)
    old_answer.append(usd_rate)

    new_answer = usd_rate_check(old_answer, user_id)

    s_date = new_answer[0]
    usd_rate = new_answer[1]
    
    db.set_user_attribute(user_id, 's_date', s_date)
    db.set_user_attribute(user_id, 'usd_rate', usd_rate)
    
    rub_rate_per_1000_tokens = (price_per_1000_tokens * usd_rate)
    n_spent_rub = (n_used_tokens * rub_rate_per_1000_tokens)/1000
    
    text = f'\nКурс доллара к рублю на {s_date}: <b>{usd_rate} руб.</b>\n\n'
    text += f"Потраченные RUB в целом: <b>{n_spent_rub:.03f} руб.</b>\n"
    text += f"Потраченные TOKENS в целом: <b>{n_used_tokens}</b>\n\n"
    text += f"Потраченные TOKENS за последний запрос: <b>{n_used_tokens_last_message}</b>\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def update_token_limit_every_day_at_ten_am(application: Application):
    """Функция ежедневно обновляет token_limit у каждого пользователя, баланс которых меньше 10000 токенов."""

    # Выбираем всех пользователей из базы данных и пополняем их баланс на 10000 токенов
    user_ids_list = db.update_balance_every_day()

    text=f'Ваш баланс равен {config.token_limit_for_users} токенов!\n\nБаланс пополняется каждый день в 10:00 по МСК.'
    for user_id in user_ids_list:
        await application.bot.send_message(user_id, text)
        

def get_tomorrow_10am():
    tomorrow = datetime.now() + timedelta(days=1)
    tomorrow_10am = datetime(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day, hour=7, minute=0, second=0)
    return tomorrow_10am
    

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("/profile", "Личный кабинет 🗄"),
        BotCommand("/help", "Info ℹ️ | Что умеет бот?🤖"),
        BotCommand("/panel", "Админ-панель 🌝"),
        
    ])


def run_bot() -> None:
    application = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .concurrent_updates(True)
        .rate_limiter(AIORateLimiter(max_retries=5))
        .post_init(post_init)
        .build()
    )
    first = get_tomorrow_10am()
    job_queue = application.job_queue
    job_queue.run_repeating(update_token_limit_every_day_at_ten_am, interval=config.update_token_limit, first=first)

    # add handlers
    user_filter = filters.ALL
    if len(config.allowed_telegram_usernames) > 0:
        usernames = [x for x in config.allowed_telegram_usernames if isinstance(x, str)]
        user_ids = [x for x in config.allowed_telegram_usernames if isinstance(x, int)]
        user_filter = filters.User(username=usernames) | filters.User(user_id=user_ids)

    application.add_handler(CommandHandler("start", start_handle, filters=user_filter))
    application.add_handler(CommandHandler("help", help_handle, filters=user_filter))
    application.add_handler(CommandHandler("profile", profile_handle, filters=user_filter))
    
    
    # Add command handler to start the payment invoice
    # application.add_handler(CommandHandler("buy", buy_callback))

    # Pre-checkout handler to final check
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    # Success! Notify your user!
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # admin system
    application.add_handler(CommandHandler("reset", reset_token_limit, filters=user_filter))
    application.add_handler(CommandHandler("panel", help_handle_for_admins, filters=user_filter))
    application.add_handler(CommandHandler("get_users", send_users_list_for_admin, filters=user_filter))
    application.add_handler(CommandHandler("get_subs", send_paid_subs_list_for_admin, filters=user_filter))
    application.add_handler(CommandHandler("add", add_token_limit_by_id, filters=user_filter))
    application.add_handler(CommandHandler("send_message", send_text_to_all, filters=user_filter))
    # application.add_handler(CommandHandler("delete", delete_user, filters=user_filter))
    

    application.add_handler(MessageHandler((filters.Regex(f'{config.DALLE_GROUP}') ^ filters.Regex(f'{config.DALLE_PRIVATE}')) & ~filters.COMMAND & user_filter, dalle))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.VOICE & ~filters.AUDIO & ~filters.VIDEO & ~filters.VIDEO_NOTE & ~filters.PHOTO  & ~filters.ANIMATION & ~filters.Sticker.ALL & ~filters.Document.ALL & user_filter, message_handle))
    application.add_handler(MessageHandler(filters.Regex(f'{config.CHATGPT_GROUP}') & ~filters.COMMAND & user_filter, message_handle)) # текст
    # application.add_handler(CommandHandler("retry", retry_handle, filters=user_filter))
    # application.add_handler(CommandHandler("new", new_dialog_handle, filters=user_filter))

    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.VOICE & user_filter, voice_message_handle))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO & user_filter, copy_to_all))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.VIDEO & user_filter, copy_to_all))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.VIDEO_NOTE & user_filter, copy_to_all))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.ANIMATION & user_filter, copy_to_all))

        
    # application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))
    application.add_handler(CallbackQueryHandler(send_buy_callback_handle, pattern="^set_package"))
    application.add_handler(CallbackQueryHandler(profile_button_handle))

    # application.add_handler(CommandHandler("balance", show_balance_handle, filters=user_filter))
    
    application.add_error_handler(error_handle)
    
    # start the bot
    application.run_polling()


if __name__ == "__main__":
    run_bot()
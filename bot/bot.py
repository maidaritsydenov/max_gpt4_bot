import os
import logging
import asyncio
import traceback
import html
import json
import tempfile
import pydub
from pathlib import Path
from datetime import datetime

import telegram
from telegram import (
    Update, 
    User, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    BotCommand
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    AIORateLimiter,
    filters
)
from telegram.constants import ParseMode, ChatAction

import openai

import config
import database
import openai_utils
from get_current_usd import usd_rate_check


# setup
db = database.Database()
logger = logging.getLogger(__name__)
user_semaphores = {}

HELP_MESSAGE = """Commands:
⚪ /retry – Восстановить последний диалог
⚪ /new – Начать новый диалог
⚪ /mode – Выбрать роль
⚪ /balance – Показать баланс
⚪ /help – Помощь
"""


def split_text_into_chunks(text, chunk_size):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


async def register_user_if_not_exists(update: Update, context: CallbackContext, user: User):
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


async def start_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    db.start_new_dialog(user_id)
    
    reply_text = "Привет! Я <b>Макс,</b> бот реализованный с помщью GPT-3.5 OpenAI API 🤖\n\n"    
    
    # Проверка на сообщение из группы или из приватных чатов
    chat_id = str(update.effective_chat.id)
    ch = '-'
    if ch in chat_id:
        reply_text += "✴️ Меня можно применять практически к любой задаче, связанной с пониманием или созданием естественного языка, кода или изображения.\n\n✴️ Спроси меня о чем нибудь <b>текстовым</b> или <b>голосовым</b> сообщением, используя слово <code>Макс, '''ВАШ ЗАПРОС'''</code> \n\n✴️ Я могу нарисовать <b>изображение</b>. Для этого отправь мне сообщение\n<code>Макс, нарисуй '''ВАШ ЗАПРОС'''</code>\n*Используй английский язык для повышения качества ответа*\n"
    
    elif ch not in chat_id:
        reply_text += "✴️ Меня можно применять практически к любой задаче, связанной с пониманием или созданием естественного языка, кода или изображения.\n\n✴️ Спроси меня о чем нибудь <b>текстовым</b> или <b>голосовым</b> сообщением\n\n✴️ Я могу нарисовать <b>изображение</b>. Для этого отправь мне сообщение\n<code>Нарисуй '''ВАШ ЗАПРОС'''</code>\n*Используй английский язык для повышения качества ответа*\n"
    
    else:
        reply_text = 'В <b>приватных чатах</b> используй конструкцию <code>Нарисуй</code> для генерации изображения или любое текстовое или голосовое сообщение\n\nВ <b>группах</b> используй конструкцию <code>Макс, </code> или <code>Макс, нарисуй</code> для генерации изображения'
        
    reply_text += f'\n\n{HELP_MESSAGE}'
    
    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)


async def help_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def retry_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return
    
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    dialog_messages = db.get_dialog_messages(user_id, dialog_id=None)
    if len(dialog_messages) == 0:
        await update.message.reply_text("Нет сообщений для восстановления диалога 🤷‍♂️")
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
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")
    
    async with user_semaphores[user_id]:
        # new dialog timeout
        if use_new_dialog_timeout:
            if (datetime.now() - db.get_user_attribute(user_id, "last_interaction")).seconds > config.new_dialog_timeout and len(db.get_dialog_messages(user_id)) > 0:
                db.start_new_dialog(user_id)
                await update.message.reply_text(f"Начат новый диалог (Роль: <b>{openai_utils.CHAT_MODES[chat_mode]['name']}</b>) ✅", parse_mode=ParseMode.HTML)
        db.set_user_attribute(user_id, "last_interaction", datetime.now())

        # send typing action
        await update.message.chat.send_action(action="typing")

        try:
            message = message or update.message.text or update.text
            
            chat_id = str(update.effective_chat.id)
            ch = '-'
            # Если с группы, то убираю первое слово "Макс, " из сообщения пользователя
            if (ch in chat_id) and (config.CHATGPT_GROUP in message):
                message = message[6::]
            else:
                message = message or update.message.text


            dialog_messages = db.get_dialog_messages(user_id, dialog_id=None)
            parse_mode = {
                "html": ParseMode.HTML,
                "markdown": ParseMode.MARKDOWN
            }[openai_utils.CHAT_MODES[chat_mode]["parse_mode"]]

            chatgpt_instance = openai_utils.ChatGPT(use_chatgpt_api=config.use_chatgpt_api)
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
            
            price_per_1000_tokens = config.chatgpt_price_per_1000_tokens if config.use_chatgpt_api else config.gpt_price_per_1000_tokens
            # Получить текущий курс usd to rub
            old_answer = []
            # old_answer = ["Число месяца: str", Курс usd: float]

            n_used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
            
            s_date = db.get_user_attribute(user_id, 's_date')
            usd_rate = db.get_user_attribute(user_id, 'usd_rate')

            old_answer.append(s_date)
            old_answer.append(usd_rate)

            new_answer = usd_rate_check(old_answer)

            s_date = new_answer[0]
            usd_rate = new_answer[1]
            
            db.set_user_attribute(user_id, 's_date', s_date)
            db.set_user_attribute(user_id, 'usd_rate', usd_rate)
            
            rub_rate_per_1000_tokens = (price_per_1000_tokens * usd_rate)
            n_spent_rub = (n_used_tokens * rub_rate_per_1000_tokens)/1000
            
            text = f'Для отладки:\nКурс доллара к рублю на {str(datetime.now())[:7:]}-{s_date}: <b>{usd_rate}руб.</b>\n\n'
            text += f"Потраченные RUB в целом: <b>{n_spent_rub:.03f}руб.</b>\n"
            text += f"Потраченные TOKENS в целом: <b>{n_used_tokens}</b>\n\n"
            text += f"Потраченные TOKENS за последний запрос: <b>{n_used_tokens_last_message}</b>\n"
        
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)

        except Exception as e:
            error_text = f"Что-то пошло не так. Ошибка: {e}"
            logger.error(error_text)
            await update.message.reply_text(error_text)
            return

        # send message if some messages were removed from the context
        if n_first_dialog_messages_removed > 0:
            if n_first_dialog_messages_removed == 1:
                text = "✍️ <i>Note:</i> Ваш текущий диалог слишком длинный. Ваше <b>first message</b> было удалено из контекста.\n Отправьте команду /new чтобы начать новый диалог."
            else:
                text = f"✍️ <i>Note:</i> Ваш текущий диалог слишком длинный. Ваше <b>{n_first_dialog_messages_removed} first messages</b> было удалено из контекста..\n Отправьте команду /new чтобы начать новый диалог."
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def is_previous_message_not_answered_yet(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    if user_semaphores[user_id].locked():
        text = "⏳ Пожалуйста <b>подождите</b> обработки предыдущего сообщения"
        await update.message.reply_text(text, reply_to_message_id=update.message.id, parse_mode=ParseMode.HTML)
        return True
    else:
        return False
    
    
async def dalle(update: Update, context):
    """Функция генерации картинок с помощью DALL-E от OpenAI.
    TO DO: добавить другие режимы: редактирование картинок + генерация версий."""

    # args в context - это слова идущие после команды

    # if not context.args:
    #     await context.bot.send_message(chat_id=update.effective_chat.id, text="Используйте следующую конструкцию: '/image <Описание картинки>'")
    #     return

    await register_user_if_not_exists(update, context, update.message.from_user)
    
    await update.message.chat.send_action(action="upload_photo")

    prompt = ''.join(update.message.text)
    chat_id = str(update.effective_chat.id)
    ch = '-'
    if (ch in chat_id) and (config.DALLE_GROUP in prompt):
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
    elif (ch not in chat_id) and config.DALLE_PRIVATE in prompt:
        prompt = ''.join(update.message.text[8::])
        response = openai.Image.create(
                prompt=prompt,
                n=1,
                size="1024x1024"
                )
        image_url = response['data'][0]['url']
        await update.message.chat.send_action(action="upload_photo")
        await context.bot.send_photo(update.effective_chat.id, photo=image_url)
        await context.bot.send_message(update.effective_chat.id, prompt, parse_mode=ParseMode.HTML)
    else:
        text = 'Ошибка. Функция работает только из приватных чатов, группы или канала.'
        await context.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML)


async def voice_message_handle(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    ch = '-'
    if (ch in chat_id):
        text = 'Распознавание голосовых сообщений не работает в группе\nПерейдите в бота чтобы воспользоваться данным функционалом\n\n@max_gpt4_bot'
        await context.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML)
    else:
        await register_user_if_not_exists(update, context, update.message.from_user)
        if await is_previous_message_not_answered_yet(update, context): return

        user_id = update.message.from_user.id
        db.set_user_attribute(user_id, "last_interaction", datetime.now())

        voice = update.message.voice
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            voice_ogg_path = tmp_dir / "voice.ogg"

            # download
            voice_file = await context.bot.get_file(voice.file_id)
            await voice_file.download_to_drive(voice_ogg_path)

            # convert to mp3
            voice_mp3_path = tmp_dir / "voice.mp3"
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


async def new_dialog_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    db.start_new_dialog(user_id)
    await update.message.reply_text("Начат новый диалог ✅")

    chat_mode = db.get_user_attribute(user_id, "current_chat_mode")
    await update.message.reply_text(f"{openai_utils.CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


async def show_chat_modes_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    if await is_previous_message_not_answered_yet(update, context): return

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    keyboard = []
    for chat_mode, chat_mode_dict in openai_utils.CHAT_MODES.items():
        keyboard.append([InlineKeyboardButton(chat_mode_dict["name"], callback_data=f"set_chat_mode|{chat_mode}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select chat mode:", reply_markup=reply_markup)


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
    price_per_1000_tokens = config.chatgpt_price_per_1000_tokens if config.use_chatgpt_api else config.gpt_price_per_1000_tokens
    old_answer = []
    
    n_used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
    s_date = db.get_user_attribute(user_id, 's_date')
    usd_rate = db.get_user_attribute(user_id, 'usd_rate')

    old_answer.append(s_date)
    old_answer.append(usd_rate)

    new_answer = usd_rate_check(old_answer)

    s_date = new_answer[0]
    usd_rate = new_answer[1]
            
    db.set_user_attribute(user_id, 's_date', s_date)
    db.set_user_attribute(user_id, 'usd_rate', usd_rate)
    
    rub_rate_per_1000_tokens = (price_per_1000_tokens * usd_rate)
    n_spent_rub = (n_used_tokens * rub_rate_per_1000_tokens)/1000
 


    text = f"Вы потратили <b>{n_spent_rub:.03f}руб.</b>\n"
    text += f"Вы использовали <b>{n_used_tokens}</b> токенов\n\n"

    text += "🏷️ Prices\n"
    text += f"<i>- ChatGPT: {rub_rate_per_1000_tokens}руб. за 1000 токенов\n"
    text += f"- Whisper (voice recognition): {config.whisper_price_per_1_min * usd_rate}руб. за 1 минуту</i>"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML) 


async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 К сожалению, <b> измененные </b> сообщения не поддерживаются"
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

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("/new", "Начать новый диалог"),
        BotCommand("/mode", "Выбрать роль"),
        BotCommand("/retry", "Восстановить предыдущий диалог"),
        BotCommand("/balance", "Показать баланс"),
        BotCommand("/help", "Помощь"),
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

    # add handlers
    user_filter = filters.ALL
    if len(config.allowed_telegram_usernames) > 0:
        usernames = [x for x in config.allowed_telegram_usernames if isinstance(x, str)]
        user_ids = [x for x in config.allowed_telegram_usernames if isinstance(x, int)]
        user_filter = filters.User(username=usernames) | filters.User(user_id=user_ids)

    application.add_handler(CommandHandler("start", start_handle, filters=user_filter))
    application.add_handler(CommandHandler("help", help_handle, filters=user_filter))

    application.add_handler(MessageHandler((filters.Regex(f'{config.DALLE_GROUP}') ^ filters.Regex(f'{config.DALLE_PRIVATE}')) & ~filters.COMMAND & user_filter, dalle))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.VOICE & ~filters.AUDIO & ~filters.VIDEO & ~filters.VIDEO_NOTE & user_filter, message_handle))
    application.add_handler(MessageHandler(filters.Regex(f'{config.CHATGPT_GROUP}') & ~filters.COMMAND & user_filter, message_handle)) # текст
    application.add_handler(CommandHandler("retry", retry_handle, filters=user_filter))
    application.add_handler(CommandHandler("new", new_dialog_handle, filters=user_filter))

    application.add_handler(MessageHandler(filters.VOICE & user_filter, voice_message_handle))
    
    application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))

    application.add_handler(CommandHandler("balance", show_balance_handle, filters=user_filter))
    
    application.add_error_handler(error_handle)
    
    # start the bot
    application.run_polling()


if __name__ == "__main__":
    run_bot()
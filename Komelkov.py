import logging
import psycopg2
from psycopg2.extras import DictCursor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from googleapiclient.discovery import build

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Параметри бази даних
DB_CONFIG = {
    "dbname": "Practice",
    "user": "postgres",
    "password": "12345",
    "host": "localhost",
    "port": 5432
}

# Налаштування YouTube API
YOUTUBE_API_KEY = "AIzaSyCN3ZCdLR8Rb3-gXaEj6-pu7oIW2px4CnU"
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# Команда скасування
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    if query:
        await query.answer()

    video_message_id = context.user_data.get("video_message_id")
    if video_message_id:
        try:
            await query.message.bot.delete_message(
                chat_id=query.message.chat_id,
                message_id=video_message_id
            )
        except Exception as e:
            print(f"Не вдалося видалити повідомлення: {e}")

    context.user_data.clear()

    if query:
        await query.message.edit_text("Дію скасовано.")

    collection_button = InlineKeyboardButton("Колекції", callback_data="my_collections")
    reply_markup = InlineKeyboardMarkup([[collection_button]])

    if query:
        await query.message.edit_reply_markup(reply_markup)

# Стан користувача
AWAIT_SEARCH_QUERY = "AWAIT_SEARCH_QUERY"
AWAIT_COLLECTION_NAME = "AWAIT_COLLECTION_NAME"
AWAIT_DELETE_VIDEO = "AWAIT_DELETE_VIDEO"

# Функція для отримання курсора
def get_cursor():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn.cursor(cursor_factory=DictCursor)

# Стартове повідомлення
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id  # Отримуємо ID користувача
    username = update.message.from_user.username  # Отримуємо ім'я користувача

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Перевіряємо, чи є користувач у базі
                cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cur.fetchone():  # Якщо користувача немає, додаємо
                    cur.execute("INSERT INTO users (id, username) VALUES (%s, %s)", (user_id, username))
                    conn.commit()

                # Перевіряємо, чи є колекція "Favorites" у користувача
                cur.execute(
                    "SELECT id FROM collections WHERE user_id = %s AND name = 'Favorites'", (user_id,)
                )
                if not cur.fetchone():  # Якщо колекції немає, додаємо
                    cur.execute(
                        "INSERT INTO collections (user_id, name) VALUES (%s, 'Favorites')", (user_id,)
                    )
                    conn.commit()

    except Exception as e:
        logger.error(f"Помилка під час старту: {e}")  # Логування помилки, якщо сталася

    # Відправляємо користувачу повідомлення з привітанням
    await update.message.reply_text(
        "Вітаю! Оберіть дію з меню."
    )

# Обробка початку пошуку відео
async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = AWAIT_SEARCH_QUERY  # Зберігаємо стан "очікування запиту пошуку"
    await update.message.reply_text("Введіть запит для пошуку відео на YouTube.")

# Пошук відео за запитом користувача
async def search_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Перевіряємо, чи ми в правильному стані для пошуку
    if context.user_data.get("state") != AWAIT_SEARCH_QUERY:
        return

    query = update.message.text  # Отримуємо запит для пошуку
    try:
        # Виконуємо запит до YouTube API для пошуку відео
        search_response = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=5  # Максимум 5 результатів
        ).execute()

        # Якщо відео не знайдено, повідомляємо користувача
        if not search_response['items']:
            await update.message.reply_text("Не вдалося знайти жодного відео. Спробуйте інший запит.")
            context.user_data["state"] = None  # Скидаємо стан
            return

        # Для кожного знайденого відео формуємо повідомлення з кнопками
        for item in search_response['items']:
            video_id = item['id']['videoId']  # Отримуємо ID відео
            title = item['snippet']['title']  # Заголовок відео
            description = item['snippet']['description'][:200]  # Опис відео (перші 200 символів)

            keyboard = [[
                InlineKeyboardButton("Переглянути на YouTube", url=f"https://www.youtube.com/watch?v={video_id}"),
                InlineKeyboardButton("Додати до колекції", callback_data=f"add_{video_id}")
            ]]  # Кнопки для перегляду та додавання до колекції

            reply_markup = InlineKeyboardMarkup(keyboard)  # Формуємо розмітку для кнопок

            # Відправляємо повідомлення з відео та кнопками
            await update.message.reply_text(
                f"🔴 {title}\n\n{description}\nhttps://www.youtube.com/watch?v={video_id}",
                reply_markup=reply_markup
            )

        context.user_data["state"] = None  # Скидаємо стан після пошуку
    except Exception as e:
        # Якщо сталася помилка під час пошуку
        await update.message.reply_text(f"Помилка під час пошуку відео: {str(e)}")

# Команда створення колекції
async def create_collection_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Встановлюємо стан для очікування назви колекції
    context.user_data["state"] = AWAIT_COLLECTION_NAME

    if update.message:
        # Отримуємо текст після команди /create_collection
        command_and_text = update.message.text.split(" ", 1)
        if len(command_and_text) > 1:
            collection_name = command_and_text[1]  # Беремо тільки назву колекції
        else:
            await update.message.reply_text("Будь ласка, введіть назву колекції після команди.")
            return

        user_id = update.message.from_user.id

        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    # Перевіряємо, чи існує колекція з такою назвою для цього користувача
                    cur.execute(
                        "SELECT id FROM collections WHERE user_id = %s AND name = %s",
                        (user_id, collection_name)
                    )
                    if cur.fetchone():
                        await update.message.reply_text(f"Колекція з назвою '{collection_name}' вже існує.")
                        return

                    # Додаємо нову колекцію до бази даних
                    cur.execute(
                        "INSERT INTO collections (user_id, name) VALUES (%s, %s)",
                        (user_id, collection_name)
                    )
                    conn.commit()

            await update.message.reply_text(f"Колекція '{collection_name}' успішно створена!")
            context.user_data["state"] = None  # Скидаємо стан

        except Exception as e:
            await update.message.reply_text(f"Помилка: {str(e)}")
            context.user_data["state"] = None

    else:
        await update.message.reply_text("Будь ласка, введіть назву колекції після команди.")

# Перегляд колекцій користувача
async def my_collections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name FROM collections WHERE user_id = %s",
                    (user_id,)
                )
                collections = cur.fetchall()

        buttons = []
        for collection in collections:
            collection_id = collection[0]
            collection_name = collection[1]

            # Додаємо кнопку для перегляду
            buttons.append([
                InlineKeyboardButton(
                    f"{collection_name}",
                    callback_data=f"view_{collection_id}_1"
                )
            ])

            # Додаємо кнопку для видалення колекції (якщо не "favorites")
            if collection_name.lower() != "favorites":
                buttons[-1].append(
                    InlineKeyboardButton(
                        "Видалити", callback_data=f"delete_collection_{collection_id}"
                    )
                )

        reply_markup = InlineKeyboardMarkup(buttons)

        if update.message:
            await update.message.reply_text("Ваші колекції:", reply_markup=reply_markup)
        elif update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text("Ваші колекції:", reply_markup=reply_markup)

    except Exception as e:
        error_message = f"Помилка: {str(e)}"
        if update.message:
            await update.message.reply_text(error_message)
        elif update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(error_message)

# Перегляд вмісту колекції
async def view_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Отримуємо ID колекції та сторінку з callback_data
    data = query.data.split("_")
    collection_id = int(data[1])
    page = int(data[2]) if len(data) > 2 else 1  # Якщо сторінка не передана, то за замовчуванням 1
    items_per_page = 5  # Кількість відео на сторінці

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Отримуємо відео з колекції для поточної сторінки
                cur.execute(
                    """
                    SELECT v.youtube_id, v.title
                    FROM collection_videos cv
                    JOIN videos v ON cv.video_id = v.id
                    WHERE cv.collection_id = %s
                    ORDER BY cv.added_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (collection_id, items_per_page, (page - 1) * items_per_page)
                )
                videos = cur.fetchall()

                # Отримуємо кількість всіх відео в колекції
                cur.execute(
                    "SELECT COUNT(*) FROM collection_videos WHERE collection_id = %s",
                    (collection_id,)
                )
                total_videos = cur.fetchone()[0]

        # Якщо в колекції немає відео
        if not videos:
            await query.message.reply_text("Колекція порожня.")
            return

        # Формуємо список відео з посиланнями на YouTube
        video_list = "\n".join([f"{i + 1}. [{video[1]}](https://www.youtube.com/watch?v={video[0]})"
                               for i, video in enumerate(videos)])

        # Розраховуємо кількість сторінок
        total_pages = (total_videos + items_per_page - 1) // items_per_page
        navigation_buttons = []

        # Кнопки для навігації між сторінками
        if page > 1:
            navigation_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"view_{collection_id}_{page - 1}"))
        if page < total_pages:
            navigation_buttons.append(InlineKeyboardButton("➡️", callback_data=f"view_{collection_id}_{page + 1}"))

        # Кнопки для дій: видалення відео та повернення
        action_buttons = [
            InlineKeyboardButton("🗑️", callback_data=f"delete_video_start_{collection_id}_{page}"),
            InlineKeyboardButton("Повернутись", callback_data="my_collections")
        ]

        # Формуємо розмітку з кнопками
        reply_markup = InlineKeyboardMarkup([navigation_buttons, action_buttons] if navigation_buttons or action_buttons else None)

        # Оновлюємо повідомлення з вмістом колекції
        message = await query.message.edit_text(
            f"Вміст колекції (сторінка {page}/{total_pages}):\n{video_list}",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        # Зберігаємо ID нового повідомлення
        context.user_data["view_message_id"] = message.message_id

    except Exception as e:
        # Обробка помилок
        await query.message.reply_text(f"Помилка: {str(e)}")

# Додавання відео до колекції
async def add_to_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data.split("_", 1)
    video_id = data[1]  # Отримуємо ID відео з callback_data

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Перевіряємо, чи є відео в базі
                cur.execute("SELECT id FROM videos WHERE youtube_id = %s", (video_id,))
                video = cur.fetchone()

                # Якщо відео не знайдено, додаємо його в базу
                if not video:
                    cur.execute(
                        """
                        INSERT INTO videos (youtube_id, title, added_at)
                        VALUES (%s, %s, NOW())
                        RETURNING id
                        """,
                        (video_id, query.message.text.split("\n")[0])
                    )
                    video = cur.fetchone()

                # Отримуємо всі колекції користувача
                cur.execute(
                    "SELECT id, name FROM collections WHERE user_id = %s",
                    (user_id,)
                )
                collections = cur.fetchall()

                # Формуємо кнопки для вибору колекції
                buttons = [
                    [InlineKeyboardButton(name, callback_data=f"select_collection_{collection_id}")]
                    for collection_id, name in collections
                ]
                buttons.append([InlineKeyboardButton("Скасувати", callback_data="cancel")])

                # Надсилаємо користувачу повідомлення з кнопками для вибору колекції
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.message.reply_text("Оберіть колекцію:", reply_markup=reply_markup)

                # Зберігаємо ID відео для подальших операцій
                context.user_data["add_video_id"] = video[0]
    except Exception as e:
        # Обробка помилок
        await query.message.reply_text(f"Помилка: {str(e)}")

async def select_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data.split("_", 2)
    collection_id = int(data[2])

    video_id = context.user_data.get("add_video_id")

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Перевіряємо, чи є колекція для цього користувача
                cur.execute(
                    "SELECT id FROM collections WHERE id = %s AND user_id = %s",
                    (collection_id, user_id)
                )
                collection = cur.fetchone()

                if not collection:
                    await query.message.reply_text("Колекція не знайдена.")
                    return

                # Перевіряємо, чи є вже це відео в колекції
                cur.execute(
                    """
                    SELECT 1 FROM collection_videos 
                    WHERE collection_id = %s AND video_id = %s
                    """,
                    (collection_id, video_id)
                )
                existing_video = cur.fetchone()

                if existing_video:
                    await query.message.reply_text("Це відео вже присутнє в цій колекції.")
                    return

                # Додаємо відео до колекції, якщо його там немає
                cur.execute(
                    """
                    INSERT INTO collection_videos (collection_id, video_id, added_at)
                    VALUES (%s, %s, NOW())
                    """,
                    (collection_id, video_id)
                )
                conn.commit()

                await query.message.reply_text("Відео додано до колекції!")

    except Exception as e:
        await query.message.reply_text(f"Помилка: {str(e)}")

# Видалення колекції
async def delete_collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Отримуємо ID колекції з callback_data та ID користувача
    collection_id = query.data.split("_", 2)[2]
    user_id = query.from_user.id

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Перевіряємо, чи існує колекція та чи належить вона користувачу
                cur.execute(
                    "SELECT name FROM collections WHERE id = %s AND user_id = %s",
                    (int(collection_id), user_id)
                )
                collection = cur.fetchone()

                # Якщо колекція не знайдена або не належить користувачу
                if not collection:
                    await query.message.reply_text("Колекція не знайдена або не належить вам.")
                    return

                # Якщо це колекція "Favorites", її неможливо видалити
                if collection[0].lower() == "favorites":
                    await query.message.reply_text("Колекцію 'Favorites' неможливо видалити.")
                    return

                # Видаляємо відео з цієї колекції та саму колекцію
                cur.execute("DELETE FROM collection_videos WHERE collection_id = %s", (collection_id,))
                cur.execute("DELETE FROM collections WHERE id = %s", (collection_id,))
                conn.commit()

        # Підтверджуємо видалення колекції
        await query.message.reply_text(f"Колекцію '{collection[0]}' успішно видалено!")
    except Exception as e:
        # Виводимо повідомлення про помилку
        await query.message.reply_text(f"Помилка: {str(e)}")

# Видалення відео з колекції
async def delete_video_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Розбираємо дані callback_data: collection_id та page
    data = query.data.split("_")
    collection_id = int(data[3])
    page = int(data[4])

    # Зберігаємо інформацію про поточний стан
    context.user_data["state"] = AWAIT_DELETE_VIDEO
    context.user_data["collection_id"] = collection_id
    context.user_data["page"] = page
    context.user_data["view_message_id"] = query.message.message_id  # Зберігаємо ID повідомлення меню

    items_per_page = 5

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Отримуємо відео з колекції для поточної сторінки
                cur.execute(
                    """
                    SELECT v.id, v.title
                    FROM collection_videos cv
                    JOIN videos v ON cv.video_id = v.id
                    WHERE cv.collection_id = %s
                    ORDER BY cv.added_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (collection_id, items_per_page, (page - 1) * items_per_page)
                )
                videos = cur.fetchall()

        # Якщо відео немає в колекції
        if not videos:
            await query.message.reply_text("Колекція порожня.")
            return

        # Створюємо кнопки для видалення відео
        delete_buttons = [
            InlineKeyboardButton(f"{i + 1}.", callback_data=f"delete_video_{collection_id}_{video[0]}")
            for i, video in enumerate(videos)
        ]

        # Кнопка для скасування операції
        cancel_button = InlineKeyboardButton("Скасувати", callback_data="cancel")

        # Формуємо розмітку кнопок
        reply_markup = InlineKeyboardMarkup([delete_buttons, [cancel_button]])

        # Виводимо повідомлення з кнопками для вибору відео
        await query.message.reply_text(
            "Оберіть відео для видалення:",
            reply_markup=reply_markup
        )

    except Exception as e:
        # Виводимо повідомлення про помилку
        await query.message.reply_text(f"Помилка: {str(e)}")

async def delete_video_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    collection_id = int(data[2])  # collection_id
    video_id = int(data[3])  # video_id
    page = int(data[4]) if len(data) > 4 else 1  # Сторінка, на якій ми працювали

    try:
        # Видалення відео з колекції
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM collection_videos WHERE collection_id = %s AND video_id = %s",
                    (collection_id, video_id)
                )
                conn.commit()

        # Видаляємо повідомлення з кнопками вибору відео
        await query.message.delete()

        # Видалення старого повідомлення з вмістом колекції
        view_message_id = context.user_data.get("view_message_id")
        if view_message_id:
            try:
                await query.bot.delete_message(
                    chat_id=query.message.chat.id,
                    message_id=view_message_id
                )
            except Exception as e:
                print(f"Помилка при видаленні повідомлення з вмістом колекції: {str(e)}")

        # Очищаємо стан користувача після завершення операції
        context.user_data.clear()

    except Exception as e:
        await query.message.edit_text(f"Помилка: {str(e)}")

# Основна програма
def main():
    application = Application.builder().token("7972749516:AAGL0T_5wsQSya47V3J13liAWlLMgLi36Os").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", start_search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_videos))
    application.add_handler(CommandHandler("create_collection", create_collection_start))
    application.add_handler(CommandHandler("my_collections", my_collections))
    application.add_handler(CallbackQueryHandler(my_collections, pattern=r"my_collections"))
    application.add_handler(CallbackQueryHandler(add_to_collection, pattern=r"^add_.*"))
    application.add_handler(CallbackQueryHandler(select_collection, pattern=r"^select_.*"))
    application.add_handler(CallbackQueryHandler(delete_collection, pattern=r"delete_collection_.*"))
    application.add_handler(CallbackQueryHandler(view_collection, pattern=r"view_\d+(_\d+)?"))
    application.add_handler(CallbackQueryHandler(delete_video_start, pattern="^delete_video_start_"))
    application.add_handler(CallbackQueryHandler(delete_video_confirm, pattern="^delete_video_"))
    application.add_handler(CallbackQueryHandler(cancel, pattern=r"cancel"))

    application.run_polling()

if __name__ == "__main__":
    main()

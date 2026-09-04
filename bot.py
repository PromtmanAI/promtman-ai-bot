import os 
import asyncio
import base64
import urllib.request
import json

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery,BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice,ReplyKeyboardMarkup, KeyboardButton 
from openai import OpenAI
from google import genai
from google.genai import types
import psycopg
import fal_client

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
FAL_KEY = os.getenv("FAL_KEY")
WAVESPEED_API_KEY = os.getenv("WAVESPEED_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_references = {}
media_group_tasks = {}

client = OpenAI(api_key=OPENAI_API_KEY)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🎨 Создать изображение", callback_data="generate"),
            InlineKeyboardButton(text="💎 Купить генерации", callback_data="buy"),
        ],
        [
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        ]
    ]
)

reply_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🎨 Создать изображение"),
            KeyboardButton(text="🎬 Создать видео"),
        ],
        [
            KeyboardButton(text="💎 Купить генерации"),
            KeyboardButton(text="👤 Профиль"),
        ]
    ],
    resize_keyboard=True
)
@dp.message(lambda message: message.text == "🎬 Создать видео")
async def video_start(message: Message):
    video_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ Kling 2.5 Turbo Pro",
                    callback_data="video_kling"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔥 Seedance 2.5",
                    callback_data="video_seedance"
                )
            ]
        ]
    )

    await message.answer(
        "🎬 Выбери модель для видео:",
        reply_markup=video_menu
    )
    @dp.callback_query(lambda c: c.data == "video_kling")
async def select_video_kling(callback: CallbackQuery):
    await callback.answer()

    user_references[callback.from_user.id] = {
        "video_model": "kling",
        "video_image": None
    }

    duration_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5 сек", callback_data="kling_5"),
                InlineKeyboardButton(text="10 сек", callback_data="kling_10"),
            ]
        ]
    )

    await callback.message.answer(
        "⚡ Выбран Kling 2.5 Turbo Pro.\n\n"
        "⏱ Выбери длительность видео:",
        reply_markup=duration_menu
    )
    
    @dp.callback_query(lambda c: c.data in ["kling_5", "kling_10"])
async def select_kling_duration(callback: CallbackQuery):
    await callback.answer()

    duration_map = {
        "kling_5": 5,
        "kling_10": 10,
    }

    user_id = callback.from_user.id

    if user_id not in user_references:
        user_references[user_id] = {}

    user_references[user_id]["video_model"] = "kling"
    user_references[user_id]["video_duration"] = duration_map[callback.data]
    user_references[user_id]["video_image"] = None

    await callback.message.answer(
        "🖼 Теперь отправь одно фото, которое нужно оживить."
    )
    
with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0
            )
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS balance INTEGER NOT NULL DEFAULT 0
        """)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет! Я Promtman AI.\n\n"
        "🎨 Напиши, какую картинку хочешь создать.\n\n"
        "Например:\n"
        "Белый Mercedes ночью в Дубае, cinematic photo",
        reply_markup=reply_menu
    )


@dp.callback_query(lambda c: c.data == "generate")
async def generate_button(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎨 Напиши промт — опиши, какую картинку хочешь создать."
    ) 
@dp.message(lambda message: message.text == "🎨 Создать изображение")
async def generate_reference_start(message: Message):
    model_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎨 GPT Image", callback_data="model_gpt")],
            [InlineKeyboardButton(text="🍌 Nano Banana Pro", callback_data="model_nano_pro")], 
            [InlineKeyboardButton(text="💥 Seedream 5.0 Pro", callback_data="model_seedream")], 
            [InlineKeyboardButton(text="🔥 Seedream 5.0 Pro WaveSpeed", callback_data="model_seedream_ws")]
        ]
    )

    await message.answer(
        "🤖 Выбери модель для генерации:",
        reply_markup=model_menu
    )
@dp.callback_query(lambda c: c.data == "model_gpt")
async def select_gpt(callback: CallbackQuery):
    await callback.answer()
    user_references[callback.from_user.id] = {"model": "gpt", "image": None}

    await callback.message.answer(
        "🖼 Отправь фото-референс для GPT Image."
    )
@dp.callback_query(lambda c: c.data == "model_seedream")
async def select_seedream(callback: CallbackQuery):
    await callback.answer()

    user_references[callback.from_user.id] = {
        "model": "seedream",
        "image": None
    }

    await callback.message.answer(
        "💥 Выбран Seedream 5.0 Pro.\n\n"
        "🖼 Отправь фото-референс."
    )
@dp.callback_query(lambda c: c.data == "model_seedream_ws")
async def select_seedream_ws(callback: CallbackQuery):
    await callback.answer()

    quality_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1K", callback_data="ws_1k"),
                InlineKeyboardButton(text="1.5K", callback_data="ws_1_5k"),
                InlineKeyboardButton(text="2K", callback_data="ws_2k"),
            ]
        ]
    )

    await callback.message.answer(
        "🔥 Выбран Seedream 5.0 Pro WaveSpeed.\n\n"
        "Выбери качество:",
        reply_markup=quality_menu
    )
@dp.callback_query(lambda c: c.data in ["ws_1k", "ws_1_5k", "ws_2k"])
async def select_seedream_ws_quality(callback: CallbackQuery):
    await callback.answer()

    quality_map = {
        "ws_1k": "1k",
        "ws_1_5k": "1.5k",
        "ws_2k": "2k",
    }

    quality = quality_map[callback.data]

    user_references[callback.from_user.id] = {
        "model": "seedream_ws",
        "images": [],
        "quality": quality
    }

    format_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1:1", callback_data="ws_ratio_1_1"),
                InlineKeyboardButton(text="3:4", callback_data="ws_ratio_3_4"),
                InlineKeyboardButton(text="4:3", callback_data="ws_ratio_4_3"),
            ],
            [
                InlineKeyboardButton(text="9:16", callback_data="ws_ratio_9_16"),
                InlineKeyboardButton(text="16:9", callback_data="ws_ratio_16_9"),
            ]
        ]
    )

    await callback.message.answer(
        "📐 Теперь выбери формат изображения:",
        reply_markup=format_menu
    )
@dp.callback_query(
    lambda c: c.data in [
        "ws_ratio_1_1",
        "ws_ratio_3_4",
        "ws_ratio_4_3",
        "ws_ratio_9_16",
        "ws_ratio_16_9",
    ]
)
async def select_seedream_ws_ratio(callback: CallbackQuery):
    await callback.answer()

    ratio_map = {
        "ws_ratio_1_1": "1:1",
        "ws_ratio_3_4": "3:4",
        "ws_ratio_4_3": "4:3",
        "ws_ratio_9_16": "9:16",
        "ws_ratio_16_9": "16:9",
    }

    user_id = callback.from_user.id

    if user_id not in user_references:
        await callback.message.answer("❌ Сначала выбери качество.")
        return

    user_references[user_id]["ratio"] = ratio_map[callback.data]

    await callback.message.answer(
        "🖼 Теперь отправь фото-референс."
    )
@dp.callback_query(lambda c: c.data == "model_nano_pro")
async def select_nano_pro(callback: CallbackQuery):
    await callback.answer()

    quality_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1K", callback_data="nano_1k"),
                InlineKeyboardButton(text="2K", callback_data="nano_2k"),
                InlineKeyboardButton(text="4K", callback_data="nano_4k"),
            ]
        ]
    )

    await callback.message.answer(
        "🍌 Выбран Nano Banana Pro.\n\n"
        "Выбери качество:",
        reply_markup=quality_menu
    )
@dp.callback_query(lambda c: c.data in ["nano_1k", "nano_2k", "nano_4k"])
async def select_nano_quality(callback: CallbackQuery):
    await callback.answer()

    quality_map = {
        "nano_1k": "1K",
        "nano_2k": "2K",
        "nano_4k": "4K",
    }

    quality = quality_map[callback.data]

    user_references[callback.from_user.id] = {
        "model": "nano_pro",
        "image": None,
        "quality": quality
    }

    format_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="1:1", callback_data="ratio_1_1"),
            InlineKeyboardButton(text="3:4", callback_data="ratio_3_4"),
            InlineKeyboardButton(text="4:3", callback_data="ratio_4_3"),
        ],
        [
            InlineKeyboardButton(text="9:16", callback_data="ratio_9_16"),
            InlineKeyboardButton(text="16:9", callback_data="ratio_16_9"),
        ]
    ]
)

    await callback.message.answer(
    f"✅ Качество: {quality}\n\n"
    "📐 Теперь выбери формат изображения:",
    reply_markup=format_menu
)
@dp.callback_query(lambda c: c.data in [
    "ratio_1_1",
    "ratio_3_4",
    "ratio_4_3",
    "ratio_9_16",
    "ratio_16_9"
])
async def select_nano_ratio(callback: CallbackQuery):
    await callback.answer()

    ratio_map = {
        "ratio_1_1": "1:1",
        "ratio_3_4": "3:4",
        "ratio_4_3": "4:3",
        "ratio_9_16": "9:16",
        "ratio_16_9": "16:9",
    }

    ratio = ratio_map[callback.data]

    user_references[callback.from_user.id]["ratio"] = ratio

    await callback.message.answer(
        f"✅ Формат: {ratio}\n\n"
        "🖼 Теперь отправь фото-референс."
    )
async def finish_media_group(message: Message, user_id: int, media_group_id: str):
    try:
        await asyncio.sleep(1.5)

        reference_data = user_references.get(user_id)
        if not reference_data:
            return

        images = reference_data.get("images", [])

        prompt_menu = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Готово, перейти к промту",
                        callback_data="references_done"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✍️ Написать свой промт",
                        callback_data="prompt_myself"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔥 Помоги составить промт",
                        callback_data="prompt_help"
                    )
                ]
            ]
        )

        await message.answer(
            f"✅ Получено фото: {len(images)}\n\n"
            "Что делаем дальше?",
            reply_markup=prompt_menu
        )

    except asyncio.CancelledError:
        pass
    finally:
        media_group_tasks.pop(media_group_id, None)
 @dp.message(
    lambda message:
        message.photo
        and message.from_user.id in user_references
        and user_references[message.from_user.id].get("video_model") == "kling"
        and user_references[message.from_user.id].get("video_image") is None
 )
async def receive_kling_photo(message: Message):
    user_id = message.from_user.id

    photo = await bot.download(message.photo[-1])
    user_references[user_id]["video_image"] = photo.read()

    await message.answer(
        "✅ Фото получено.\n\n"
        "✍️ Теперь напиши, что должно происходить в видео."
    )
@dp.message(lambda message: message.photo is not None)
async def receive_reference(message: Message):
    user_id = message.from_user.id
    media_group_id = message.media_group_id

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)

    if user_id not in user_references:
        user_references[user_id] = {"model": "gpt", "images": []}

    if "images" not in user_references[user_id]:
        user_references[user_id]["images"] = []

    if len(user_references[user_id]["images"]) >= 5:
        await message.answer("⚠️ Можно добавить максимум 5 фото.")
        return

    user_references[user_id]["images"].append(photo_bytes.read())
    if media_group_id:
        if media_group_id in media_group_tasks:
            media_group_tasks[media_group_id].cancel()

        media_group_tasks[media_group_id] = asyncio.create_task(
            finish_media_group(message, user_id, media_group_id)
        )
        return

    prompt_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Готово, перейти к промту",
                    callback_data="references_done"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✍️ Написать свой промт",
                    callback_data="prompt_myself"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔥 Помоги составить промт",
                    callback_data="prompt_help"
                )
            ]
        ]
    )

    await message.answer(
        "✅ Фото получено!\n\n"
        "Что делаем дальше?",
        reply_markup=prompt_menu
    )


@dp.callback_query(lambda c: c.data == "references_done")
async def references_done(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    reference_data = user_references.get(user_id)

    if not reference_data or not reference_data.get("images"):
        await callback.message.answer("❌ Сначала отправь хотя бы одно фото.")
        return

    await callback.message.answer(
        f"✅ Добавлено фото: {len(reference_data['images'])}\n\n"
        "Теперь напиши, что хочешь создать."
    )
@dp.callback_query(lambda c: c.data == "prompt_myself")
async def prompt_myself(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer(
        "✍️ Напиши, что хочешь создать или изменить."
    )


@dp.callback_query(lambda c: c.data == "prompt_help")
async def prompt_help(callback: CallbackQuery):
    await callback.answer()
    user_references[callback.from_user.id]["prompt_help"] = True
    
    await callback.message.answer(
        "🔥 Опиши простыми словами, что хочешь получить.\n\n"
        "Например:\n"
        "«Хочу фото возле Lamborghini ночью в Дубае»\n\n"
        "Я помогу превратить это в хороший промт."
    )
@dp.message(lambda message: message.text == "👤 Профиль")
async def profile_text(message: Message):
    user_id = message.from_user.id

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()

    balance = row[0] if row else 0

    await message.answer(
        f"👤 Профиль\n\n"
        f"💎 Генераций на балансе: {balance}"
    )
@dp.callback_query(lambda c: c.data == "profile")
async def profile_button(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()

    balance = row[0] if row else 0

    await callback.message.answer(
        f"👤 Профиль\n\n"
        f"💎 Генераций на балансе: {balance}"
    )
@dp.message(lambda message: message.text == "💎 Купить генерации")
async def buy_text(message: Message):
    buy_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="5 генераций — 50 ⭐", callback_data="buy_5")],
            [InlineKeyboardButton(text="10 генераций — 90 ⭐", callback_data="buy_10")],
            [InlineKeyboardButton(text="25 генераций — 200 ⭐", callback_data="buy_25")]
        ]
    )

    await message.answer(
        "💎 Выбери пакет генераций:",
        reply_markup=buy_menu
    )
@dp.callback_query(lambda c: c.data == "buy")
async def buy_button(callback: CallbackQuery):
    await callback.answer()

    buy_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="5 генераций — 50 ⭐", callback_data="buy_5")],
            [InlineKeyboardButton(text="10 генераций — 90 ⭐", callback_data="buy_10")],
            [InlineKeyboardButton(text="25 генераций — 200 ⭐", callback_data="buy_25")]
        ]
    )

    await callback.message.answer(
        "💎 Выбери пакет генераций:",
        reply_markup=buy_menu
    )
    @dp.callback_query(lambda c: c.data == "buy_5")
    async def buy_5(callback: CallbackQuery):
        await callback.answer()

    await callback.message.answer_invoice(
        title="5 генераций",
        description="Пакет из 5 генераций изображений",
        payload="buy_5",
        currency="XTR",
        prices=[
            LabeledPrice(label="5 генераций", amount=50)
        ]
    )
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query):
    await pre_checkout_query.answer(ok=True)
@dp.message(lambda message: message.successful_payment is not None)
async def successful_payment(message: Message):
    user_id = message.from_user.id

    if message.successful_payment.invoice_payload == "buy_5":
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, balance)
                    VALUES (%s, 5)
                    ON CONFLICT (user_id)
                    DO UPDATE SET balance = users.balance + 5
                    """,
                    (user_id,)
                )

        await message.answer(
            "✅ Оплата прошла!\n"
            "💎 На баланс начислено 5 генераций."
        )
@dp.message(Command("testcredits"))
async def test_credits(message: Message):
    user_id = message.from_user.id
    allowed_users = [8328359349, 1905941634]

    if user_id not in allowed_users:
        await message.answer("❌ Эта команда недоступна.")
        return

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, balance)
                VALUES (%s, 10)
                ON CONFLICT (user_id)
                DO UPDATE SET balance = users.balance + 10
                """,
                (user_id,)
            )
    await message.answer("🧪 Добавлено 10 тестовых генераций.")
@dp.message(
    lambda message:
        message.text
        and message.from_user.id in user_references
        and user_references[message.from_user.id].get("video_model") == "kling"
        and user_references[message.from_user.id].get("video_image") is not None
)
async def generate_kling_video(message: Message):
    user_id = message.from_user.id
    data = user_references[user_id]

    status = await message.answer("🎬 Создаю видео...")

    try:
        image_data_uri = (
            "data:image/jpeg;base64,"
            + base64.b64encode(data["video_image"]).decode("utf-8")
        )

        headers = {
            "Authorization": f"Bearer {WAVESPEED_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": message.text,
            "image": image_data_uri,
            "duration": data.get("video_duration", 5),
            "guidance_scale": 0.5
        }

        request = urllib.request.Request(
            "https://api.wavespeed.ai/api/v3/kwaivgi/kling-v2.5-turbo-pro/image-to-video",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        response = await asyncio.to_thread(
            lambda: urllib.request.urlopen(request, timeout=60).read()
        )

        task_data = json.loads(response)
        task_id = task_data["data"]["id"]

        while True:
            await asyncio.sleep(3)

            result_request = urllib.request.Request(
                f"https://api.wavespeed.ai/api/v3/predictions/{task_id}/result",
                headers={"Authorization": f"Bearer {WAVESPEED_API_KEY}"}
            )

            result_response = await asyncio.to_thread(
                lambda: urllib.request.urlopen(
                    result_request,
                    timeout=30
                ).read()
            )

            result_data = json.loads(result_response)["data"]
            task_status = result_data["status"]

            if task_status == "completed":
                video_url = result_data["outputs"][0]
                break

            if task_status in {"failed", "cancelled", "timeout", "deleted"}:
                raise RuntimeError(
                    result_data.get("error") or f"WaveSpeed: {task_status}"
                )

        video_bytes = await asyncio.to_thread(
            lambda: urllib.request.urlopen(
                video_url,
                timeout=120
            ).read()
        )

        await status.delete()

        await message.answer_video(
            BufferedInputFile(video_bytes, filename="promtman_video.mp4"),
            caption="🎬 Готово!"
        )

    except Exception as e:
        await status.edit_text(f"❌ Ошибка генерации видео:\n{e}")
@dp.message()
async def generate(message: Message):
    if not message.text:
        return

    user_id = message.from_user.id
    prompt_text = message.text
    reference_data = user_references.get(user_id)

    if reference_data and reference_data.get("prompt_help"):
        await message.answer("🔥 Улучшаю промт...")

        prompt_result = await asyncio.to_thread(
            client.responses.create,
            model="gpt-5-mini",
            input=(
                "Ты профессиональный промт-инженер для генерации изображений. "
                "Улучши запрос пользователя: добавь детали сцены, освещение, композицию, "
                "стиль, реализм и качество, но не меняй смысл запроса. "
                "Если используется фото-референс человека, обязательно сохраняй его узнаваемость. "
                "Верни только готовый улучшенный промт без объяснений.\n\n"
                "Запрос пользователя: " + message.text
            )
        )

        prompt_text = prompt_result.output_text.strip()
        user_references[user_id]["prompt_help"] = False

        await message.answer(
            "✨ Улучшенный промт:\n\n" + prompt_text
        )
        
    use_paid = False

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()

            if row:
                balance = row[0]

                if balance <= 0:
                    await message.answer(
                        "🔒 Бесплатная генерация уже использована.\n"
                        "💎 Купи генерации, чтобы продолжить."
                    )
                    return

                use_paid = True

    status = await message.answer("⏳ Создаю изображение...")

    try:
        reference_data = user_references.get(user_id)
        reference_images = reference_data.get("images", []) if reference_data else []
        selected_model = reference_data.get("model") if reference_data else None
        if reference_data:
            reference_data["last_prompt"] = prompt_text

        if not reference_images:
            await status.edit_text(
                "🖼 Сначала нажми «🎨 Создать изображение» и отправь фото-референс."
            )
            return

        if selected_model == "nano_pro":
            interaction = await asyncio.to_thread(
                gemini_client.interactions.create,
                model="gemini-3-pro-image",
                input=[
                    {
                        "type": "text",
                        "text": (
                            "Используй человека с референсного фото как основу. "
                            "Сохраняй его узнаваемость и основные черты внешности, "
                            "но выполняй изменения, которые пользователь явно попросил. "
                            "Запрос пользователя: " + prompt_text +
                            (
                                " Максимальное качество: ультравысокая детализация, фотореализм, "
                                "естественная текстура кожи, точные мелкие детали, реалистичное освещение, "
                                "чёткий фокус, минимум артефактов, профессиональное качество фотографии."
                                if reference_data.get("quality") == "4K" else ""
                            )
                        )
                                },
            *[
                {
                    "type": "image",
                    "data": base64.b64encode(img).decode("utf-8"),
                    "mime_type": "image/jpeg"
                }
                for img in reference_images
            ]
        ],
                response_format={
                    "type": "image",
                    "image_size": reference_data.get("quality", "1K"),
                    "aspect_ratio": reference_data.get("ratio", "1:1")
                }
            )

            image_bytes = base64.b64decode(interaction.output_image.data)

        elif selected_model == "seedream":
            reference_data_uris = [
    "data:image/jpeg;base64,"
    + base64.b64encode(img).decode("utf-8")
    for img in reference_images
            ]

            result = await asyncio.to_thread(
                fal_client.subscribe,
                "bytedance/seedream/v5/pro/edit",
                arguments={
                    "prompt": (
    "Используй человека с референсного фото как точную основу. "
    "Максимально сохраняй идентичность человека: форму лица, глаза, нос, губы, "
    "линию челюсти, пропорции и другие узнаваемые черты. "
    "Точно выполняй запрос пользователя, включая изменения одежды и образа. "
    "Допускаются запросы взрослых пользователей на купальники, бельё, короткие топы, "
    "платья, glamour, boudoir и sensual fashion-съёмку. "
    "Не добавляй откровенную наготу, если пользователь её не просил. "
    "Запрос пользователя: " + prompt_text
),
                    "image_urls": reference_data_uris,
                    "num_images": 1,
                    "output_format": "jpeg"
                }
            )

            image_url = result["images"][0]["url"]

            image_bytes = await asyncio.to_thread(
                lambda: urllib.request.urlopen(
                    image_url,
                    timeout=60
                ).read()
            )

        elif selected_model == "seedream_ws":
            reference_data_uris = [
                "data:image/jpeg;base64,"
                + base64.b64encode(img).decode("utf-8")
                for img in reference_images
            ]

            headers = {
                "Authorization": f"Bearer {WAVESPEED_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "prompt": prompt_text,
                "images": reference_data_uris,
                "aspect_ratio": reference_data.get("ratio", "1:1"),
"resolution": reference_data.get("quality", "1k"),
                "output_format": "jpeg",
                "prompt_optimization_mode": "standard"
            }

            request = urllib.request.Request(
                "https://api.wavespeed.ai/api/v3/bytedance/seedream-v5.0-pro/edit",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )

            response = await asyncio.to_thread(
                lambda: urllib.request.urlopen(request, timeout=60).read()
            )

            task_data = json.loads(response)
            task_id = task_data["data"]["id"]

            while True:
                await asyncio.sleep(2)

                result_request = urllib.request.Request(
                    f"https://api.wavespeed.ai/api/v3/predictions/{task_id}/result",
                    headers={"Authorization": f"Bearer {WAVESPEED_API_KEY}"}
                )

                result_response = await asyncio.to_thread(
                    lambda: urllib.request.urlopen(
                        result_request,
                        timeout=30
                    ).read()
                )

                result_data = json.loads(result_response)["data"]
                task_status = result_data["status"]

                if task_status == "completed":
                    image_url = result_data["outputs"][0]
                    break

                if task_status in {"failed", "cancelled", "timeout", "deleted"}:
                    raise RuntimeError(
                        result_data.get("error") or f"WaveSpeed: {task_status}"
                    )

            image_bytes = await asyncio.to_thread(
                lambda: urllib.request.urlopen(
                    image_url,
                    timeout=60
                ).read()
            )
        else:
            result = await asyncio.to_thread(
                client.images.edit,
                model="gpt-image-1",
                image=[
    (f"reference_{i}.jpg", img, "image/jpeg")
    for i, img in enumerate(reference_images)
],
                prompt=(
                    "Используй человека с референсного фото как основу. "
                    "Сохраняй его узнаваемость и основные черты внешности, "
                    "но обязательно выполняй изменения внешности, которые пользователь явно попросил. "
                    "Не изменяй другие черты без необходимости. "
                    "Запрос пользователя: " + prompt_text
                ),
                size="1024x1024",
            )

            image_bytes = base64.b64decode(result.data[0].b64_json)
        image = BufferedInputFile(
            image_bytes,
            filename="promtman.png"
        )

        await message.answer_photo(
    BufferedInputFile(image_bytes, filename="promtman_preview.png"),
    caption="✨ Готово!", 
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Повторить", callback_data="repeat_generation")]])
)

        await message.answer_document(
    BufferedInputFile(image_bytes, filename=f"promtman_{reference_data.get('quality', '1K')}.png"),
)

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                if use_paid:
                    cur.execute(
                        "UPDATE users SET balance = balance - 1 WHERE user_id = %s",
                        (user_id,)
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO users (user_id, balance)
                        VALUES (%s, 0)
                        ON CONFLICT DO NOTHING
                        """,
                        (user_id,)
                    )
        
        await status.delete()


    except Exception as e:
        print(e)
        await status.edit_text(
            "❌ Не удалось создать изображение. Попробуй ещё раз."
        )


    
@dp.callback_query(lambda c: c.data == "repeat_generation")
async def repeat_generation(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    reference_data = user_references.get(user_id)

    if not reference_data or not reference_data.get("images") or not reference_data.get("last_prompt"):
        await callback.message.answer("❌ Нет сохранённой генерации для повтора.")
        return

    repeat_message = callback.message.model_copy(
        update={
            "from_user": callback.from_user,
            "text": reference_data["last_prompt"]
        }
    )

    await generate(repeat_message)
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

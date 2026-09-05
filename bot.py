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
@dp.callback_query(lambda c: c.data == "video_seedance")
async def select_video_seedance(callback: CallbackQuery):
    await callback.answer()

    user_references[callback.from_user.id] = {
        "video_model": "seedance",
        "video_images": []
    }

    await callback.message.answer(
        "🔥 Выбран Seedance 2.5.\n\n"
        "🖼 Отправь фото-референсы.\n"
        "Можно добавить до 10 фото."
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

    format_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 9:16", callback_data="kling_ratio_9_16"),
            InlineKeyboardButton(text="🖥 16:9", callback_data="kling_ratio_16_9"),
            InlineKeyboardButton(text="⬜ 1:1", callback_data="kling_ratio_1_1"),
        ]
    ]
)

    await callback.message.answer(
    "📐 Теперь выбери формат видео:",
    reply_markup=format_menu
)
@dp.callback_query(
    lambda c: c.data in [
        "kling_ratio_9_16",
        "kling_ratio_16_9",
        "kling_ratio_1_1",
    ]
)
async def select_kling_ratio(callback: CallbackQuery):
    await callback.answer()

    ratio_map = {
        "kling_ratio_9_16": "9:16",
        "kling_ratio_16_9": "16:9",
        "kling_ratio_1_1": "1:1",
    }

    user_id = callback.from_user.id

    if user_id not in user_references:
        await callback.message.answer("❌ Сначала выбери длительность.")
        return

    user_references[user_id]["video_ratio"] = ratio_map[callback.data]

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
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS images_created INTEGER NOT NULL DEFAULT 0
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS videos_created INTEGER NOT NULL DEFAULT 0
        """)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в Promtman AI!\n\n"
        "✨ Создавай изображения и видео с помощью лучших AI-моделей прямо в Telegram.\n\n"
        "🎨 Изображения — создавай с нуля или используй свои фото\n"
        "🎬 Видео — оживляй фотографии и создавай сцены по описанию\n\n"
        "👇 Выбери, что хочешь создать:",
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
            [InlineKeyboardButton(text="🌱 Seedream 5.0 Pro ⭐ Рекомендуем", callback_data="model_seedream_ws")]
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

    quality_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1K — 1 💠", callback_data="fal_1k"),
                InlineKeyboardButton(text="2K — 2 💠", callback_data="fal_2k"),
            ]
        ]
    )

    await callback.message.answer(
        "🌱 Выбран Seedream 5.0 Pro.\n\n"
        "Выбери качество:",
        reply_markup=quality_menu
    )
@dp.callback_query(lambda c: c.data in ["fal_1k", "fal_2k"])
async def select_seedream_quality(callback: CallbackQuery):
    await callback.answer()

    quality_map = {
        "fal_1k": "1K",
        "fal_2k": "2K",
    }

    quality = quality_map[callback.data]

    user_references[callback.from_user.id] = {
        "model": "seedream",
        "images": [],
        "quality": quality
    }

    format_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1:1", callback_data="fal_ratio_1_1"),
                InlineKeyboardButton(text="3:4", callback_data="fal_ratio_3_4"),
                InlineKeyboardButton(text="4:3", callback_data="fal_ratio_4_3"),
            ],
            [
                InlineKeyboardButton(text="9:16", callback_data="fal_ratio_9_16"),
                InlineKeyboardButton(text="16:9", callback_data="fal_ratio_16_9"),
            ]
        ]
    )

    await callback.message.answer(
        f"✅ Seedream 5.0 Pro — {quality}\n\n"
        "📐 Теперь выбери формат изображения:",
        reply_markup=format_menu
    )
@dp.callback_query(
    lambda c: c.data in [
        "fal_ratio_1_1",
        "fal_ratio_3_4",
        "fal_ratio_4_3",
        "fal_ratio_9_16",
        "fal_ratio_16_9",
    ]
)
async def select_seedream_ratio(callback: CallbackQuery):
    await callback.answer()

    ratio_map = {
        "fal_ratio_1_1": "1:1",
        "fal_ratio_3_4": "3:4",
        "fal_ratio_4_3": "4:3",
        "fal_ratio_9_16": "9:16",
        "fal_ratio_16_9": "16:9",
    }

    user_id = callback.from_user.id

    if user_id not in user_references:
        await callback.message.answer("❌ Сначала выбери качество.")
        return

    user_references[user_id]["ratio"] = ratio_map[callback.data]

    await callback.message.answer(
        f"✅ Формат: {ratio_map[callback.data]}\n\n"
        "📷 Теперь отправь фото-референс."
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
@dp.message(
    lambda message:
        message.photo
        and message.from_user.id in user_references
        and user_references[message.from_user.id].get("video_model") == "seedance"
)
async def receive_seedance_photo(message: Message):
    user_id = message.from_user.id
    data = user_references[user_id]

    if len(data["video_images"]) >= 10:
        await message.answer("⚠️ Можно добавить максимум 10 фото.")

    photo = await bot.download(message.photo[-1])
    data["video_images"].append(photo.read())

    done_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Готово, продолжить",
                    callback_data="seedance_refs_done"
                )
            ]
        ]
    )

    await message.answer(
        f"✅ Добавлено фото: {len(data['video_images'])}/10\n\n"
        "Можешь отправить ещё или нажать «Готово».",
        reply_markup=done_menu
    )
@dp.callback_query(lambda c: c.data == "seedance_refs_done")
async def seedance_refs_done(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id
    data = user_references.get(user_id)

    if not data or not data.get("video_images"):
        await callback.message.answer("❌ Сначала отправь хотя бы одно фото.")
        return

    duration_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5 сек", callback_data="seedance_5"),
                InlineKeyboardButton(text="10 сек", callback_data="seedance_10"),
            ],
            [
                InlineKeyboardButton(text="15 сек", callback_data="seedance_15"),
            ]
        ]
    )

    await callback.message.answer(
        f"✅ Фото загружено: {len(data['video_images'])}\n\n"
        "🎬 Выбери длительность видео:",
        reply_markup=duration_menu
    )
@dp.callback_query(
    lambda c: c.data in [
        "seedance_5",
        "seedance_10",
        "seedance_15",
    ]
)
async def select_seedance_duration(callback: CallbackQuery):
    await callback.answer()

    duration_map = {
        "seedance_5": 5,
        "seedance_10": 10,
        "seedance_15": 15,
    }

    user_id = callback.from_user.id
    user_references[user_id]["video_duration"] = duration_map[callback.data]

    format_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 9:16", callback_data="seedance_ratio_9_16"),
                InlineKeyboardButton(text="🖥 16:9", callback_data="seedance_ratio_16_9"),
            ],
            [
                InlineKeyboardButton(text="⬜ 1:1", callback_data="seedance_ratio_1_1"),
                InlineKeyboardButton(text="📸 4:3", callback_data="seedance_ratio_4_3"),
            ],
            [
                InlineKeyboardButton(text="📱 3:4", callback_data="seedance_ratio_3_4"),
            ]
        ]
    )

    await callback.message.answer(
        "📐 Выбери формат видео:",
        reply_markup=format_menu
    )
@dp.callback_query(
    lambda c: c.data in [
        "seedance_ratio_9_16",
        "seedance_ratio_16_9",
        "seedance_ratio_1_1",
        "seedance_ratio_4_3",
        "seedance_ratio_3_4",
    ]
)
async def select_seedance_ratio(callback: CallbackQuery):
    await callback.answer()

    ratio_map = {
        "seedance_ratio_9_16": "9:16",
        "seedance_ratio_16_9": "16:9",
        "seedance_ratio_1_1": "1:1",
        "seedance_ratio_4_3": "4:3",
        "seedance_ratio_3_4": "3:4",
    }

    user_id = callback.from_user.id

    if user_id not in user_references:
        await callback.message.answer("❌ Сначала выбери Seedance 2.5.")
        return

    user_references[user_id]["video_ratio"] = ratio_map[callback.data]

    quality_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="720p",
                callback_data="seedance_720p"
            ),
            InlineKeyboardButton(
                text="1080p",
                callback_data="seedance_1080p"
            ),
        ]
    ]
)

    await callback.message.answer(
    "🎞 Теперь выбери качество видео:",
    reply_markup=quality_menu
)
@dp.callback_query(
    lambda c: c.data in [
        "seedance_720p",
        "seedance_1080p",
    ]
)
async def select_seedance_quality(callback: CallbackQuery):
    await callback.answer()

    quality_map = {
        "seedance_720p": "720p",
        "seedance_1080p": "1080p",
    }

    user_id = callback.from_user.id

    if user_id not in user_references:
        await callback.message.answer("❌ Сначала выбери Seedance 2.5.")
        return

    user_references[user_id]["video_resolution"] = quality_map[callback.data]

    sound_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔊 Со звуком",
                    callback_data="seedance_sound_on"
                ),
                InlineKeyboardButton(
                    text="🔇 Без звука",
                    callback_data="seedance_sound_off"
                ),
            ]
        ]
    )

    await callback.message.answer(
        "🔊 Добавить звук в видео?",
        reply_markup=sound_menu
    )
@dp.callback_query(
    lambda c: c.data in [
        "seedance_sound_on",
        "seedance_sound_off",
    ]
)
async def select_seedance_sound(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id

    if user_id not in user_references:
        await callback.message.answer("❌ Сначала выбери Seedance 2.5.")
        return

    user_references[user_id]["video_audio"] = (
        callback.data == "seedance_sound_on"
    )

    await callback.message.answer(
    "✍️ Теперь опиши, что должно происходить в видео.\n\n"
    "💡 Если загружено несколько фото, используй @image1, @image2, @image3 и т.д.\n\n"
    "Например:\n"
    "@image1 подходит к @image2, они обнимаются и смотрят друг на друга. "
    "Камера плавно приближается."
)
@dp.callback_query(
    lambda c: c.data in [
        "seedance_sound_on",
        "seedance_sound_off",
    ]
)
async def select_seedance_sound(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id

    if user_id not in user_references:
        await callback.message.answer("❌ Сначала выбери Seedance 2.5.")
        return

    user_references[user_id]["video_audio"] = (
        callback.data == "seedance_sound_on"
    )

    await callback.message.answer(
        "✍️ Теперь напиши, что должно происходить в видео."
    )
    async def upload_image_to_wavespeed(image_bytes):
        headers = {
        "Authorization": f"Bearer {WAVESPEED_API_KEY}",
        "Content-Type": "application/json"
    }

    ticket_payload = {
        "filename": "reference.jpg",
        "size": len(image_bytes)
    }

    ticket_request = urllib.request.Request(
        "https://api.wavespeed.ai/api/v3/media/uploads",
        data=json.dumps(ticket_payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    ticket_response = await asyncio.to_thread(
        lambda: urllib.request.urlopen(
            ticket_request,
            timeout=30
        ).read()
    )

    ticket_data = json.loads(ticket_response)["data"]

    upload_url = ticket_data["upload"]["url"]
    upload_headers = ticket_data["upload"]["headers"]
    download_url = ticket_data["download_url"]

    upload_request = urllib.request.Request(
        upload_url,
        data=image_bytes,
        headers=upload_headers,
        method="PUT"
    )

    await asyncio.to_thread(
        lambda: urllib.request.urlopen(
            upload_request,
            timeout=60
        ).read()
    )

    return download_url
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
    name = message.from_user.first_name or "Пользователь"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()

    balance = row[0] if row else 0

    profile_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Пополнить баланс",
                    callback_data="buy"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="profile_stats"
                ),
                InlineKeyboardButton(
                    text="🎁 Пригласить друга",
                    callback_data="invite_friend"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆘 Поддержка",
                    callback_data="support"
                )
            ]
        ]
    )

    await message.answer(
        f"👤 Профиль Promtman AI\n\n"
        f"👋 {name}\n"
        f"🆔 ID: {user_id}\n"
        f"💠 Баланс: {balance} генераций\n\n"
        f"✨ Создавай больше — впереди новые возможности!",
        reply_markup=profile_menu
    )
@dp.callback_query(lambda c: c.data == "profile_stats")
async def profile_stats(callback: CallbackQuery):
    await callback.answer()

    user_id = callback.from_user.id

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT images_created, videos_created
                FROM users
                WHERE user_id = %s
                """,
                (user_id,)
            )
            row = cur.fetchone()

    images_created = row[0] if row else 0
    videos_created = row[1] if row else 0
    total = images_created + videos_created

    await callback.message.answer(
        f"📊 Статистика Promtman AI\n\n"
        f"🎨 Создано изображений: {images_created}\n"
        f"🎬 Создано видео: {videos_created}\n"
        f"✨ Всего генераций: {total}"
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
            [InlineKeyboardButton(text="💠 50 токенов — 50 ⭐", callback_data="buy_50")],
            [InlineKeyboardButton(text="💠 100 токенов — 100 ⭐", callback_data="buy_100")],
            [InlineKeyboardButton(text="💠 300 токенов — 300 ⭐", callback_data="buy_300")],
            [InlineKeyboardButton(text="💠 600 токенов — 600 ⭐", callback_data="buy_600")],
            [InlineKeyboardButton(text="💠 1000 токенов — 1000 ⭐", callback_data="buy_1000")]
        ]
    )

    await message.answer(
        "💠 Выбери пакет токенов:",
        reply_markup=buy_menu
    )
@dp.callback_query(lambda c: c.data == "buy")
async def buy_button(callback: CallbackQuery):
    await callback.answer()

    buy_menu = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💠 50 токенов — 50 ⭐", callback_data="buy_50")],
            [InlineKeyboardButton(text="💠 100 токенов — 100 ⭐", callback_data="buy_100")],
            [InlineKeyboardButton(text="💠 300 токенов — 300 ⭐", callback_data="buy_300")],
            [InlineKeyboardButton(text="💠 600 токенов — 600 ⭐", callback_data="buy_600")],
            [InlineKeyboardButton(text="💠 1000 токенов — 1000 ⭐", callback_data="buy_1000")]
        ]
    )

    await callback.message.answer(
        "💠 Выбери пакет токенов:",
        reply_markup=buy_menu
    )
@dp.callback_query(lambda c: c.data == "buy_50")
async def buy_50(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer_invoice(
        title="💠 50 токенов",
        description="Пополнение баланса Promtman AI на 50 токенов",
        payload="buy_50",
        currency="XTR",
        prices=[
            LabeledPrice(label="50 токенов", amount=50)
        ]
    )
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query):
    await pre_checkout_query.answer(ok=True)
@dp.message(lambda message: message.successful_payment is not None)
async def successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload

    packages = {
        "buy_50": 50,
        "buy_100": 100,
        "buy_300": 300,
        "buy_600": 600,
        "buy_1000": 1000
    }

    tokens = packages.get(payload)

    if tokens is None:
        return

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, balance)
                VALUES (%s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET balance = users.balance + %s
                """,
                (user_id, tokens, tokens)
            )

    await message.answer(
        f"✅ Оплата прошла!\n"
        f"💠 На баланс начислено {tokens} токенов."
    )
@dp.callback_query(lambda c: c.data == "buy_100")
async def buy_100(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer_invoice(
        title="💠 100 токенов",
        description="Пополнение баланса Promtman AI на 100 токенов",
        payload="buy_100",
        currency="XTR",
        prices=[LabeledPrice(label="100 токенов", amount=100)]
    )


@dp.callback_query(lambda c: c.data == "buy_300")
async def buy_300(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer_invoice(
        title="💠 300 токенов",
        description="Пополнение баланса Promtman AI на 300 токенов",
        payload="buy_300",
        currency="XTR",
        prices=[LabeledPrice(label="300 токенов", amount=300)]
    )


@dp.callback_query(lambda c: c.data == "buy_600")
async def buy_600(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer_invoice(
        title="💠 600 токенов",
        description="Пополнение баланса Promtman AI на 600 токенов",
        payload="buy_600",
        currency="XTR",
        prices=[LabeledPrice(label="600 токенов", amount=600)]
    )


@dp.callback_query(lambda c: c.data == "buy_1000")
async def buy_1000(callback: CallbackQuery):
    await callback.answer()

    await callback.message.answer_invoice(
        title="💠 1000 токенов",
        description="Пополнение баланса Promtman AI на 1000 токенов",
        payload="buy_1000",
        currency="XTR",
        prices=[LabeledPrice(label="1000 токенов", amount=1000)]
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
    "aspect_ratio": data.get("video_ratio", "16:9"),
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
@dp.message(
    lambda message:
        message.text
        and message.from_user.id in user_references
        and user_references[message.from_user.id].get("video_model") == "seedance"
        and user_references[message.from_user.id].get("video_images")
)
async def generate_seedance_video(message: Message):
    user_id = message.from_user.id
    data = user_references[user_id]

    status = await message.answer("🎬 Загружаю референсы и создаю видео...")

    try:
        reference_urls = []

        for image_bytes in data["video_images"]:
            image_url = await upload_image_to_wavespeed(image_bytes)
            reference_urls.append(image_url)

        headers = {
            "Authorization": f"Bearer {WAVESPEED_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": message.text,
            "reference_images": reference_urls,
            "aspect_ratio": data.get("video_ratio", "16:9"),
            "resolution": data.get("video_resolution", "720p"),
            "duration": data.get("video_duration", 5),
            "generate_audio": data.get("video_audio", True)
        }

        request = urllib.request.Request(
            "https://api.wavespeed.ai/api/v3/bytedance/seedance-2.5/text-to-video",
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
            BufferedInputFile(
                video_bytes,
                filename="promtman_seedance.mp4"
            ),
            caption="🎬 Seedance 2.5 — готово!"
        )

    except Exception as e:
        await status.edit_text(
            f"❌ Ошибка Seedance 2.5:\n{e}"
        )
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
    reference_data = user_references.get(user_id)
    selected_model = reference_data.get("model") if reference_data else None
    quality = reference_data.get("quality", "1K") if reference_data else "1K"

    token_cost = 1

    if selected_model == "nano_pro":
        token_cost = 4 if quality == "4K" else 2
    elif selected_model == "seedream":
        token_cost = 2 if quality == "2K" else 1
    elif selected_model == "seedream_ws":
        token_cost = 2 if quality == "2K" else 1

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

                if balance < token_cost:
                    await message.answer(
                        f"❌ Недостаточно токенов.\n\n"
                        f"💠 Нужно: {token_cost}\n"
                        f"💠 На балансе: {balance}\n\n"
                        f"Пополните баланс, чтобы продолжить."
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
                            "но выполняй изменения, которые пользователь явно попросил."
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
                    "image_size": "auto_2K" if reference_data.get("quality") == "2K" else "auto_1K",
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
            token_cost = 1

            if selected_model == "nano_pro":
                token_cost = 4 if reference_data.get("quality") == "4K" else 2
            elif selected_model == "seedream":
                token_cost = 2 if reference_data.get("quality") == "2K" else 1
            elif selected_model == "seedream_ws":
                token_cost = 2 if reference_data.get("quality") == "2K" else 1

            with conn.cursor() as cur:
                if use_paid:
                    cur.execute(
                        "UPDATE users SET balance = balance - %s WHERE user_id = %s",
                        (token_cost, user_id)
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

                cur.execute(
                    """
                    UPDATE users
                    SET images_created = images_created + 1
                    WHERE user_id = %s
                    """,
                    (user_id,)
                )
     
    
        
        await status.delete()
    except Exception as e:
        print("IMAGE ERROR:", repr(e))

        if hasattr(e, "read"):
            try:
                print("API RESPONSE:", e.read().decode("utf-8"))
            except Exception:
                pass

        await status.edit_text(
            f"❌ Ошибка генерации:\n{e}"
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

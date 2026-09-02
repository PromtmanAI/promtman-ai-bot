import os
import asyncio
import base64

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery,BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from openai import OpenAI
import psycopg

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)
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
with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
            )
        """)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет! Я Promtman AI.\n\n"
        "🎨 Напиши, какую картинку хочешь создать.\n\n"
        "Например:\n"
        "Белый Mercedes ночью в Дубае, cinematic photo", 
    reply_markup=menu
     )


@dp.callback_query(lambda c: c.data == "generate")
async def generate_button(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎨 Напиши промт — опиши, какую картинку хочешь создать."
    ) 
@dp.message()
async def generate(message: Message):
    if not message.text:
        return
    user_id = message.from_user.id
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE user_id = %s",
                (user_id,)
            )
            if cur.fetchone():
                await message.answer(
                    "🔒 Бесплатная генерация уже использована."
                )
                return

    

    status = await message.answer("⏳ Создаю изображение...")

    try:
        result = await asyncio.to_thread(
                        client.images.generate,
            model="gpt-image-1",
            prompt=message.text,
            size="1024x1024",
        )
            

        image_bytes = base64.b64decode(result.data[0].b64_json)

        image = BufferedInputFile(
            image_bytes,
            filename="promtman.png"
        )

        await message.answer_photo(
            image,
            caption="✨ Готово!"
        )
        with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                    "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (user_id,)
                )

        await status.delete()

    except Exception as e:
        print(e)
        await status.edit_text(
            "❌ Не удалось создать изображение. Попробуй ещё раз."
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

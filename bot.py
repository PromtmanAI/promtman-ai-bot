import os
import asyncio
import base64

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery,BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice 
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
    reply_markup=menu
     )


@dp.callback_query(lambda c: c.data == "generate")
async def generate_button(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎨 Напиши промт — опиши, какую картинку хочешь создать."
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
@dp.message()
async def generate(message: Message):
    if not message.text:
        return
    user_id = message.from_user.id
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


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

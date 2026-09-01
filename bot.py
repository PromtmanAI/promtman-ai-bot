import os
import asyncio
import base64

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, BufferedInputFile
from openai import OpenAI


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = OpenAI(api_key=OPENAI_API_KEY)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет! Я Promtman AI.\n\n"
        "🎨 Напиши, какую картинку хочешь создать.\n\n"
        "Например:\n"
        "Белый Mercedes ночью в Дубае, cinematic photo"
    )


@dp.message()
async def generate(message: Message):
    if not message.text:
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

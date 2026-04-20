# weather_bot.py
import asyncio
import logging
import os
import random
from datetime import datetime

import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

"""
Telegram бот: щоденна погода по містах України о 9:00.

Потрібні змінні в .env:
  BOT_TOKEN         — токен Telegram бота
  CHAT_ID           — ID чату куди слати погоду
  OPENWEATHER_KEY   — ключ OpenWeatherMap API (безкоштовний)

Запуск:
  pip install aiogram httpx apscheduler python-dotenv
  python weather_bot.py
"""

load_dotenv()

BOT_TOKEN       = os.getenv("BOT_TOKEN")
CHAT_ID_RAW     = os.getenv("CHAT_ID")
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY")

CITIES = [
    "Вінниця",
    "Луцьк",
    "Дніпро",
    "Житомир",
    "Ужгород",
    "Запоріжжя",
    "Івано-Франківськ",
    "Київ",
    "Кропивницький",
    "Львів",
    "Миколаїв",
    "Одеса",
    "Полтава",
    "Рівне",
    "Суми",
    "Тернопіль",
    "Харків",
    "Херсон",
    "Хмельницький",
    "Черкаси",
    "Чернівці",
    "Чернігів",
]

# Жарти по типу погоди
COMMENTS = {
    "sunny": [
        "сонцезахисні окуляри обовʼязкові",
        "нарешті можна вийти з печери",
        "навіть кіт хоче на вулицю",
        "гарний день щоб нічого не робити надворі",
        "сонце вирішило попрацювати",
        "засмага сама себе не зробить",
        "відкрий вікно і насолоджуйся",
        "сьогодні навіть понеділок терпимий",
        "природа нарешті згадала що є весна",
        "ідеальний день для пікніка якого не буде",
    ],
    "clear": [
        "ясно як у душі після відпустки",
        "небо чисте, думки теж",
        "ідеально для прогулянки якої не буде",
        "гарно, але надовго не розраховуй",
        "зірки вночі будуть як на долоні",
        "навіть синоптики не зіпсували",
        "повітря свіже — виходь подихати",
        "небо в повній бойовій готовності",
        "сонце і жодних відмовок не виходити",
    ],
    "cloudy": [
        "сонце взяло вихідний",
        "небо думає чи варто старатись",
        "хмари прийшли без запрошення",
        "сіро але терпимо",
        "куртку вдягни про всяк випадок",
        "не дощ але й не свято",
        "небо в режимі енергозбереження",
        "сонце в відпустці, хмари на чергуванні",
        "парасолька в сумці не завадить",
        "фото сьогодні вийдуть без тіней",
        "типовий день — типовий настрій",
        "хмари не визначились що робити",
        "джинси і светр — правильний вибір",
    ],
    "rain": [
        "парасолька це не опція, це необхідність",
        "качки задоволені, решта — ні",
        "гарний день щоб залишитись вдома",
        "дощ вирішив нагадати про себе",
        "кава в руки і нікуди",
        "вулиці миються безкоштовно",
        "волосся зіпсовано ще до виходу",
        "калюжі — це пастки для взуття",
        "дощ це привід нарешті почитати книгу",
        "промокнеш — але це досвід",
        "зонт або каяття — вибір за тобою",
        "дощ знову переміг",
    ],
    "drizzle": [
        "мряка — не дощ, але й не сухо",
        "волосся все одно намокне",
        "небо плаче тихенько",
        "парасолька є? Можна ризикнути без неї",
        "погода як понеділок — ні так ні сяк",
        "куртка краще ніж парасолька",
        "мокро але не критично",
        "небо розпилює воду замість дощу",
    ],
    "snow": [
        "зима повернулась без попередження",
        "квітень переплутав себе з груднем",
        "сніг в квітні — класика України",
        "лопату ще не прибирай",
        "Дід Мороз загубився в календарі",
        "природа не читала прогноз погоди",
        "теплі шкарпетки знову актуальні",
        "сніговик ще можна зліпити",
        "зима каже: я ще не закінчила",
        "весна відкладається, слідкуйте за оновленнями",
    ],
    "thunderstorm": [
        "залишайся вдома, серйозно",
        "Зевс сьогодні не в гуморі",
        "гроза — природа показує хто тут головний",
        "найкращий день для Netflix",
        "телефон від розетки відʼєднай",
        "під деревами не стояти",
        "природа влаштувала шоу без квитків",
        "блискавка — безкоштовний феєрверк",
    ],
    "fog": [
        "туман такий що сусід невидимий",
        "їдеш — повільно, дуже повільно",
        "містично, наче у фільмі жахів",
        "далекоглядність не потрібна — все одно нічого не видно",
        "фари включи навіть вдень",
        "місто зникло — не хвилюйся, повернеться",
        "туман додає таємничості навіть супермаркету",
        "видимість нульова, обережно",
    ],
    "default": [
        "одягнись по погоді",
        "виглянь у вікно перед виходом",
        "природа сьогодні непередбачувана",
        "головне не забути ключі",
        "погода як завжди має свою думку",
        "краще перебдіти ніж недобдіти",
    ],
}

def get_comment(weather_id: int) -> str:
    if weather_id < 300:
        pool = COMMENTS["thunderstorm"]
    elif weather_id < 400:
        pool = COMMENTS["drizzle"]
    elif weather_id < 600:
        pool = COMMENTS["rain"]
    elif weather_id < 700:
        pool = COMMENTS["snow"]
    elif weather_id < 800:
        pool = COMMENTS["fog"]
    elif weather_id == 800:
        pool = COMMENTS["sunny"]
    elif weather_id == 801:
        pool = COMMENTS["clear"]
    elif weather_id <= 803:
        pool = COMMENTS["cloudy"]
    else:
        pool = COMMENTS["cloudy"]
    return random.choice(pool)

def condition_emoji(weather_id: int) -> str:
    if weather_id < 300:
        return "⛈"
    elif weather_id < 400:
        return "🌦"
    elif weather_id < 600:
        return "🌧"
    elif weather_id < 700:
        return "❄️"
    elif weather_id < 800:
        return "🌫"
    elif weather_id == 800:
        return "☀️"
    elif weather_id == 801:
        return "🌤"
    elif weather_id <= 803:
        return "⛅"
    else:
        return "☁️"


async def fetch_weather(city: str) -> dict | None:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q":     f"{city},UA",
        "appid": OPENWEATHER_KEY,
        "units": "metric",
        "lang":  "ua",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logging.warning(f"OpenWeather {resp.status_code} for {city}")
                return None
            data = resp.json()
            weather_id = data["weather"][0]["id"]
            return {
                "city":      city,
                "temp":      round(data["main"]["temp"]),
                "emoji":     condition_emoji(weather_id),
                "comment":   get_comment(weather_id),
            }
    except Exception as e:
        logging.error(f"fetch_weather error for {city}: {e}")
        return None


async def fetch_all_weather() -> list[dict]:
    tasks   = [fetch_weather(city) for city in CITIES]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def send_weather(bot: Bot) -> None:
    logging.info("Fetching weather...")
    weather_data = await fetch_all_weather()

    if not weather_data:
        logging.error("No weather data received")
        return

    date_str = datetime.now().strftime("%d.%m.%Y")
    lines = [f"🌍 Погода по Україні, {date_str}\n"]

    for w in weather_data:
        lines.append(f"**{w['city']}** {w['temp']}° {w['emoji']} — {w['comment']}")

    text = "\n".join(lines)

    await bot.send_message(int(CHAT_ID_RAW), text, parse_mode="Markdown")
    logging.info(f"Weather sent for {len(weather_data)} cities")


async def main() -> None:
    if not all([BOT_TOKEN, CHAT_ID_RAW, OPENWEATHER_KEY]):
        logging.error("Не всі змінні задані в .env")
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    bot = Bot(BOT_TOKEN)
    dp  = Dispatcher()

    @dp.message(Command("start"))
    async def start_cmd(m: Message):
        await m.answer(
            "☀️ Бот погоди запущено!\n"
            "Щодня о 9:00 надсилаю погоду по Україні.\n"
            "Команда /weather — отримати зараз."
        )

    @dp.message(Command("weather"))
    async def weather_cmd(m: Message):
        await m.answer("🔎 Збираю погоду, зачекай...")
        await send_weather(bot)

    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")
    scheduler.add_job(send_weather, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()

    logging.info("Bot started. Weather will be sent daily at 09:00 Kyiv time.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Stopped by KeyboardInterrupt")

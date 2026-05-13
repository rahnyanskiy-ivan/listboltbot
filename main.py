import asyncio
import re
import os

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_PASSWORD = os.getenv("PASSWORD")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =========================
# DATA
# =========================

tasks = []
TASK_MESSAGE_ID = None
BOT_ID = None
BOT_USERNAME = None


# =========================
# FSM
# =========================

class AdminStates(StatesGroup):
    zone = State()
    task_type = State()
    scooters = State()


# =========================
# KEYBOARDS
# =========================

def admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Створити список")],
            [KeyboardButton(text="🗑 Видалити список")]
        ],
        resize_keyboard=True
    )


def zone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
            [KeyboardButton(text="4"), KeyboardButton(text="5"), KeyboardButton(text="6")],
            [KeyboardButton(text="7"), KeyboardButton(text="8"), KeyboardButton(text="9")],
            [KeyboardButton(text="10")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )


def type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👻Поиск")],
            [KeyboardButton(text="🏠Сбор")],
            [KeyboardButton(text="🪫АКБ")],
            [KeyboardButton(text="🚚Ребалансировка")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )


def final_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Додати ще")],
            [KeyboardButton(text="🚀 Опублікувати")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )


# =========================
# BUILD TEXT
# =========================

def build_text(data):
    if not data:
        return "📭 Порожньо"

    data = sorted(data, key=lambda x: (int(x["zone"]), x["type"], x["scooter"]))

    zones = {}
    for t in data:
        zones.setdefault(t["zone"], {}).setdefault(t["type"], []).append(t)

    text = ""
    for zone in zones:
        text += f"Зона {zone}\n"
        for ttype in zones[zone]:
            text += f" {ttype}\n"
            for t in zones[zone][ttype]:
                line = t["scooter"]
                if t["status"]:
                    line += t["status"]
                if t["link"]:
                    line += f" {t['link']}"
                text += line + "\n"
            text += "\n"

    return text.strip()


# =========================
# AUTO CLOSE (🔥 FIXED)
# =========================

def is_fully_closed():
    return tasks and all(t["status"] in ("✅", "❌") for t in tasks)


async def close_list():
    global TASK_MESSAGE_ID, tasks

    final_text = (
        "@fir01, @F_E_2_1_N, список закритий!\n\n"
        f"{build_text(tasks)}\n\n"
        "Всім дякую!"
    )

    try:
        if TASK_MESSAGE_ID:
            await bot.delete_message(GROUP_ID, TASK_MESSAGE_ID)
    except:
        pass

    msg = await bot.send_message(GROUP_ID, final_text)
    TASK_MESSAGE_ID = msg.message_id

    tasks.clear()


# =========================
# UPDATE GROUP
# =========================

async def update_group(force_new=False):
    global TASK_MESSAGE_ID

    text = build_text(tasks)

    if force_new:
        if TASK_MESSAGE_ID:
            try:
                await bot.delete_message(GROUP_ID, TASK_MESSAGE_ID)
            except:
                pass
        TASK_MESSAGE_ID = None

    if not TASK_MESSAGE_ID:
        msg = await bot.send_message(GROUP_ID, text)
        TASK_MESSAGE_ID = msg.message_id
    else:
        try:
            await bot.edit_message_text(
                chat_id=GROUP_ID,
                message_id=TASK_MESSAGE_ID,
                text=text
            )
        except:
            msg = await bot.send_message(GROUP_ID, text)
            TASK_MESSAGE_ID = msg.message_id

    # 🔥 FIX: AUTO CLOSE CHECK RETURNED
    if is_fully_closed():
        await close_list()


# =========================
# LOGIN
# =========================

@dp.message(F.text == ADMIN_PASSWORD)
async def login(message: Message):
    if message.chat.type != ChatType.PRIVATE:
        return

    await message.answer("Адмін панель:", reply_markup=admin_menu())


# =========================
# CREATE
# =========================

@dp.message(F.text == "📦 Створити список")
async def create(message: Message, state: FSMContext):
    tasks.clear()

    await message.answer("Оберіть район:", reply_markup=zone_keyboard())
    await state.set_state(AdminStates.zone)


# =========================
# ZONE
# =========================

@dp.message(AdminStates.zone)
async def zone(message: Message, state: FSMContext):

    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("Адмін панель:", reply_markup=admin_menu())
        return

    await state.update_data(zone=message.text)
    await message.answer("Оберіть тип задачі:", reply_markup=type_keyboard())
    await state.set_state(AdminStates.task_type)


# =========================
# TYPE
# =========================

@dp.message(AdminStates.task_type)
async def task_type(message: Message, state: FSMContext):

    if message.text == "⬅️ Назад":
        await message.answer("Оберіть район:", reply_markup=zone_keyboard())
        await state.set_state(AdminStates.zone)
        return

    await state.update_data(task_type=message.text)
    await message.answer("Введіть самокати:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.scooters)


# =========================
# SCOOTERS
# =========================

@dp.message(AdminStates.scooters)
async def scooters(message: Message, state: FSMContext):

    if message.text == "⬅️ Назад":
        await message.answer("Оберіть тип:", reply_markup=type_keyboard())
        await state.set_state(AdminStates.task_type)
        return

    data = await state.get_data()
    added = 0

    for line in message.text.split("\n"):
        line = line.strip()

        match = re.search(r"(\d{3}-\d{3})\s*([+\-]|❌|✅|\+\+|--)?", line)
        if not match:
            continue

        scooter = match.group(1)
        symbol = match.group(2) or ""

        if symbol in ("+", "++", "✅"):
            status = "✅"
        elif symbol in ("-", "--", "❌"):
            status = "❌"
        else:
            status = ""

        link = line.replace(match.group(0), "").strip()

        tasks.append({
            "zone": data["zone"],
            "type": data["task_type"],
            "scooter": scooter,
            "link": link,
            "status": status
        })

        added += 1

    await message.answer(f"Додано: {added}", reply_markup=final_keyboard())
    await state.clear()


# =========================
# ADD MORE
# =========================

@dp.message(F.text == "➕ Додати ще")
async def add_more(message: Message, state: FSMContext):
    await message.answer("Оберіть район:", reply_markup=zone_keyboard())
    await state.set_state(AdminStates.zone)


# =========================
# PUBLISH
# =========================

@dp.message(F.text == "🚀 Опублікувати")
async def publish(message: Message):

    await update_group(force_new=True)
    await message.answer("Опубліковано", reply_markup=admin_menu())


# =========================
# DELETE
# =========================

@dp.message(F.text == "🗑 Видалити список")
async def delete(message: Message):

    global TASK_MESSAGE_ID, tasks

    tasks.clear()
    TASK_MESSAGE_ID = None

    await message.answer("Список видалено", reply_markup=admin_menu())


# =========================
# GROUP HANDLER
# =========================

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def group_handler(message: Message):

    global TASK_MESSAGE_ID

    if not message.text:
        return

    text_lower = message.text.lower()
    mentioned = BOT_USERNAME and f"@{BOT_USERNAME.lower()}" in text_lower

    updated = False

    # LIVE STATUS UPDATE
    for line in message.text.split("\n"):
        line = line.strip()

        match = re.search(r"(\d{3}-\d{3})\s*([+\-]|❌|✅|\+\+|--)?", line)
        if not match:
            continue

        scooter = match.group(1)
        symbol = match.group(2) or ""

        if symbol in ("+", "++", "✅"):
            status = "✅"
        elif symbol in ("-", "--", "❌"):
            status = "❌"
        else:
            continue

        for t in tasks:
            if t["scooter"] == scooter:
                t["status"] = status
                updated = True
                break

    if updated:
        await asyncio.sleep(0.2)
        await update_group()

    # @MENTION REFRESH
    if mentioned:
        try:
            if TASK_MESSAGE_ID:
                await bot.delete_message(GROUP_ID, TASK_MESSAGE_ID)
        except:
            pass

        await update_group(force_new=True)
# =========================
# MAIN
# =========================

async def main():
    global BOT_ID

    BOT_ID = (await bot.get_me()).id

    print("Bot started")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

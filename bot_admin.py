import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# ТОКЕН БОТА (Замените на свой токен от @BotFather)
TOKEN = "8839559401:AAGVNCieouyHp7P2haJggIwATo1a4pI4d-w"

# Создаем объекты бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Изначальный список администраторов (по юзернеймам или ID)
ADMINS = {"lytixx"}

# Внутриигровая база данных (в реальном проекте используйте SQLite/PostgreSQL)
db = {
    "admins": ADMINS,
    "rp_commands": {
        "обкашлить": "{user1} обкашлил вопросы с {user2}",
        "трахнуть": "{user1} трахнул {user2}"
    },
    "users": {}  # id: {username, messages, rewards: []}
}

def init_user(user_id: int, username: str):
    """Инициализация профиля пользователя в БД"""
    if user_id not in db["users"]:
        db["users"][user_id] = {
            "username": username or f"id{user_id}",
            "messages": 0,
            "rewards": []
        }
    elif username:
        db["users"][user_id]["username"] = username

# Счётчик сообщений для статистики
@dp.message()
async def message_counter(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        init_user(message.from_user.id, message.from_user.username)
        db["users"][message.from_user.id]["messages"] += 1
    
    # Обработка команд в группах
    text = message.text or ""
    
    # 1. Закрепление сообщений (!Закреп)
    if text.startswith("!Закреп"):
        if not message.reply_to_message:
            await message.reply("Перешлите или ответьте этой командой на сообщение, которое нужно закрепить!")
            return
        try:
            await bot.pin_chat_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
            await message.reply("📌 Сообщение успешно закреплено!")
        except Exception as e:
            await message.reply(f"❌ Ошибка закрепления (возможно, у бота нет прав администратора): {e}")
        return

    # 2. РП команды
    cmd = text.split()[0].lower() if text else ""
    if cmd in db["rp_commands"]:
        if not message.reply_to_message:
            await message.reply("Эту РП команду нужно использовать в ответ на чье-то сообщение!")
            return
        
        user1 = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        target = message.reply_to_message.from_user
        user2 = f"@{target.username}" if target.username else target.first_name
        
        template = db["rp_commands"][cmd]
        response = template.format(user1=user1, user2=user2)
        await message.reply(response)
        return

    # 3. Команды профиля и статистики в чате
    if cmd in ["профиль", "!профиль"]:
        init_user(message.from_user.id, message.from_user.username)
        u_data = db["users"][message.from_user.id]
        rewards_str = ", ".join(u_data["rewards"]) if u_data["rewards"] else "Нет наград"
        await message.reply(
            f"👤 **Профиль пользователя:**\n"
            f"🔹 Имя: {message.from_user.first_name}\n"
            f"📊 Сообщений в активе: {u_data['messages']}\n"
            f"🏆 Награды: {rewards_str}"
        )
        return

    if cmd in ["стата", "топ", "!стата", "!топ"]:
        if not db["users"]:
            await message.reply("Статистика пока пуста!")
            return
        
        # Сортируем топ по сообщениям
        sorted_users = sorted(db["users"].items(), key=lambda x: x[1]["messages"], reverse=True)[:10]
        text_top = "📊 **Топ актива чата:**\n"
        for idx, (uid, data) in enumerate(sorted_users, 1):
            text_top += f"{idx}. @{data['username']} — {data['messages']} собщ.\n"
        await message.reply(text_top)
        return

    # 4. Выдача наград (!наградить [название])
    if text.startswith("!наградить"):
        # Проверяем, админ ли тот, кто выдает награду
        is_admin = message.from_user.username in db["admins"] or message.from_user.id in db["admins"]
        if not is_admin:
            await message.reply("❌ Выдавать награды могут только администраторы бота!")
            return
        
        if not message.reply_to_message:
            await message.reply("Ответьте командой `!наградить [название]` на сообщение того, кого хотите поощрить.")
            return
        
        reward_name = text.replace("!наградить", "").strip()
        if not reward_name:
            await message.reply("Укажите название награды после команды, например: `!наградить Активист`")
            return
            
        target = message.reply_to_message.from_user
        init_user(target.id, target.username)
        db["users"][target.id]["rewards"].append(reward_name)
        await message.reply(f"🏆 @{target.username or target.first_name} получил награду: **{reward_name}**!")
        return

# 5. Админ-панель в ЛС бота
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    if message.chat.type != "private":
        return
        
    username = message.from_user.username
    if username in db["admins"] or message.from_user.id in db["admins"]:
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Назначить админа", callback_data="adm_add")
        builder.button(text="➕ Добавить РП команду", callback_data="rp_add")
        builder.adjust(1)
        await message.reply(
            f"👑 **Добро пожаловать в Админ-панель, @{username}!**\n"
            "Вы можете управлять ботом прямо отсюда.",
            reply_markup=builder.as_markup()
        )
    else:
        await message.reply("Привет! Добавь меня в чат и сделай администратором, чтобы я мог управлять им.")

# Обработка кнопок в ЛС
@dp.callback_query()
async def process_callbacks(callback: types.CallbackQuery):
    username = callback.from_user.username
    if username not in db["admins"] and callback.from_user.id not in db["admins"]:
        await callback.answer("У вас нет доступа!", show_alert=True)
        return

    if callback.data == "adm_add":
        await callback.message.answer(
            "Чтобы назначить нового админа, просто перешлите в этот чат любое сообщение от него "
            "или напишите его точный username (без @). В реальном коде добавьте этот хэндлер."
        )
        await callback.answer()
    elif callback.data == "rp_add":
        await callback.message.answer(
            "Для добавления РП-команд добавьте логику состояний (FSM). По умолчанию "
            "новые команды регистрируются в словаре `db['rp_commands']`."
        )
        await callback.answer()

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

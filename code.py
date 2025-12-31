import asyncio
import re
import os
from flask import Flask
from threading import Thread
from telethon import TelegramClient, events, Button, types
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator

app = Flask('')

@app.route('/')
def home():
    return "HelperBot is running 24/7"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

API_ID = 20045757
API_HASH = '7d3ea0c0d4725498789bd51a9ee02421'
BOT_TOKEN = '7701119851:AAH1cGAqONU25HJiOgOEVie1hHm_Cj7TzhQ'

client = TelegramClient('helper_bot_session', API_ID, API_HASH)

user_state = {}
user_channels = {}

async def check_bot_admin(channel, bot_id):
    try:
        participant = await client(GetParticipantRequest(channel, bot_id))
        return isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator))
    except Exception:
        return False

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    sender_id = event.sender_id
    user_state[sender_id] = {'step': 'idle'}
    
    if sender_id in user_channels and user_channels[sender_id]:
        buttons = []
        for ch_id, ch_data in user_channels[sender_id].items():
            buttons.append([Button.inline(f"📡 {ch_data['title']}", data=f"manage_{ch_id}")])
        
        buttons.append([Button.inline("➕ Привязать новый канал", data="add_channel")])
        
        await event.respond(
            "👋 Приветствую в HelperBot!\n\nВыберите канал для управления или привяжите новый объект.",
            buttons=buttons
        )
    else:
        await event.respond(
            "👋 Приветствую в HelperBot!\n\nЯ помогу вам управлять вашим каналом.\n\n"
            "1. Добавьте бота в канал как администратора.\n"
            "2. Отправьте юзернейм канала или перешлите сообщение из него.",
            buttons=[Button.inline("🔗 Привязать канал", data="add_channel")]
        )

@client.on(events.CallbackQuery(data="add_channel"))
async def add_channel_callback(event):
    sender_id = event.sender_id
    user_state[sender_id] = {'step': 'wait_channel_username'}
    await event.edit("📝 Введите юзернейм канала (через @) или перешлите любое сообщение из него:")

@client.on(events.NewMessage)
async def message_input_handler(event):
    if not event.is_private:
        return

    sender_id = event.sender_id
    if sender_id not in user_state:
        user_state[sender_id] = {'step': 'idle'}
    
    state_data = user_state[sender_id]
    state = state_data.get('step')

    if state == 'wait_channel_username':
        target_entity = None
        
        if event.fwd_from:
            try:
                if event.fwd_from.from_id:
                    target_entity = await client.get_entity(event.fwd_from.from_id)
            except Exception as e:
                await event.respond(f"❌ Ошибка получения данных: {e}")
                return
        else:
            text = event.text.strip()
            if not text.startswith('@') and not text.startswith('https://t.me/'):
                text = f"@{text}"
            try:
                target_entity = await client.get_entity(text)
            except Exception as e:
                await event.respond(f"❌ Канал не найден: {e}")
                return

        if not target_entity or not isinstance(target_entity, (types.Channel, types.Chat)):
            await event.respond("❌ Это не канал. Пожалуйста, укажите верный юзернейм.")
            return

        bot_info = await client.get_me()
        is_admin = await check_bot_admin(target_entity, bot_info.id)
        
        if not is_admin:
            await event.respond("❌ Бот не администратор в этом канале. Выдайте все права.")
            return

        if sender_id not in user_channels:
            user_channels[sender_id] = {}
        
        user_channels[sender_id][target_entity.id] = {
            'title': target_entity.title,
            'entity': target_entity
        }
        
        user_state[sender_id]['step'] = 'idle'
        await event.respond(
            f"✅ Канал **{target_entity.title}** успешно привязан!",
            buttons=[Button.inline("📱 В меню", data="start_back")]
        )

    elif state == 'wait_log_text':
        channel_id = state_data['channel_id']
        emoji = state_data['emoji']
        sender = await event.get_sender()
        username = sender.username or sender.first_name
        
        final_log = (
            f"{emoji} **{event.text}**\n"
            f"👤 ***@{username}***\n\n"
            f"#логи #тест"
        )
        
        target_channel = user_channels[sender_id][channel_id]['entity']
        await client.send_message(target_channel, final_log)
        user_state[sender_id]['step'] = 'idle'
        await event.respond("✅ Лог отправлен!", buttons=[Button.inline("🔙 Назад", data=f"manage_{channel_id}")])

    elif state == 'wait_simple_msg':
        channel_id = state_data['channel_id']
        final_text = f"🎄 {event.text}\n\n#новости"
        
        target_channel = user_channels[sender_id][channel_id]['entity']
        await client.send_message(target_channel, final_text)
        user_state[sender_id]['step'] = 'idle'
        await event.respond("✅ Сообщение опубликовано!", buttons=[Button.inline("🔙 Назад", data=f"manage_{channel_id}")])

    elif state == 'wait_v_target':
        user_state[sender_id]['target_user'] = event.text.strip()
        user_state[sender_id]['step'] = 'wait_v_me'
        await event.respond("📝 Теперь введите ваш юзернейм:")

    elif state == 'wait_v_me':
        channel_id = state_data['channel_id']
        my_nick = event.text.strip()
        target_nick = state_data['target_user']
        
        if not my_nick.startswith('@'): my_nick = '@' + my_nick
        if not target_nick.startswith('@'): target_nick = '@' + target_nick
        
        final_invite = (
            f"<{my_nick}> Приглашает <{target_nick}> в видеочат!\n\n"
            f"#приглашение #логи"
        )
        
        target_channel = user_channels[sender_id][channel_id]['entity']
        await client.send_message(target_channel, final_invite)
        user_state[sender_id]['step'] = 'idle'
        await event.respond("✅ Приглашение отправлено!", buttons=[Button.inline("🔙 Назад", data=f"manage_{channel_id}")])

    elif state == 'wait_rank_user':
        user_state[sender_id]['rank_user'] = event.text.strip()
        user_state[sender_id]['step'] = 'wait_rank_val'
        
        buttons = []
        row = []
        for i in range(1, 13):
            row.append(Button.inline(str(i), data=f"setrank_{i}"))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
            
        await event.respond("🔢 Выберите ранг для повышения (1-12):", buttons=buttons)

@client.on(events.CallbackQuery(data=re.compile(br'manage_(\d+)')))
async def manage_handler(event):
    channel_id = int(event.pattern_match.group(1).decode())
    sender_id = event.sender_id
    
    buttons = [
        [Button.inline("📝 Отправить Лог", data=f"act_log_{channel_id}")],
        [Button.inline("✉️ Отправить сообщение", data=f"act_msg_{channel_id}")],
        [Button.inline("📞 Пригласить в видеочат", data=f"act_video_{channel_id}")],
        [Button.inline("📈 Повысить ранг", data=f"act_rank_{channel_id}")],
        [Button.inline("🔙 К списку каналов", data="start_back")]
    ]
    
    await event.edit(f"🛰 Управление: **{user_channels[sender_id][channel_id]['title']}**", buttons=buttons)

@client.on(events.CallbackQuery)
async def callback_router(event):
    data = event.data.decode()
    sender_id = event.sender_id

    if data == "start_back":
        await start_handler(event)

    elif data.startswith('act_log_'):
        channel_id = int(data.split('_')[2])
        user_state[sender_id] = {'step': 'wait_log_emoji', 'channel_id': channel_id}
        emojis = ["🛠", "🛡", "🔥", "📢", "⚙️", "✅", "⚠️", "ℹ️"]
        buttons = []
        row = []
        for e in emojis:
            row.append(Button.inline(e, data=f"sel_em_{e}_{channel_id}"))
            if len(row) == 4:
                buttons.append(row)
                row = []
        await event.edit("🎬 Выберите эмодзи для заголовка лога:", buttons=buttons)

    elif data.startswith('sel_em_'):
        parts = data.split('_')
        emoji = parts[2]
        channel_id = int(parts[3])
        user_state[sender_id] = {'step': 'wait_log_text', 'channel_id': channel_id, 'emoji': emoji}
        await event.edit(f"Выбран эмодзи: {emoji}\n\nТеперь введите текст лога:")

    elif data.startswith('act_msg_'):
        channel_id = int(data.split('_')[2])
        user_state[sender_id] = {'step': 'wait_simple_msg', 'channel_id': channel_id}
        await event.edit("🎄 Введите текст сообщения:")

    elif data.startswith('act_video_'):
        channel_id = int(data.split('_')[2])
        user_state[sender_id] = {'step': 'wait_v_target', 'channel_id': channel_id}
        await event.edit("👤 Введите юзернейм приглашаемого лица:")

    elif data.startswith('act_rank_'):
        channel_id = int(data.split('_')[2])
        user_state[sender_id] = {'step': 'wait_rank_user', 'channel_id': channel_id}
        await event.edit("👤 Введите юзернейм для повышения:")

    elif data.startswith('setrank_'):
        rank_val = data.split('_')[1]
        state_data = user_state.get(sender_id, {})
        channel_id = state_data.get('channel_id')
        target_user = state_data.get('rank_user')
        
        if not target_user.startswith('@'): target_user = '@' + target_user
        
        msg_rank = (
            f"❄️ <{target_user}> повышен до <{rank_val}> ранга!\n\n"
            f"#логи"
        )
        
        target_channel = user_channels[sender_id][channel_id]['entity']
        await client.send_message(target_channel, msg_rank)
        user_state[sender_id]['step'] = 'idle'
        await event.respond(f"✅ Готово! Ранг {rank_val} выдан.", buttons=[Button.inline("🔙 Назад", data=f"manage_{channel_id}")])

def main():
    Thread(target=run_web).start()
    client.start(bot_token=BOT_TOKEN)
    print("HelperBot запущен в режиме Enterprise...")
    client.run_until_disconnected()

if __name__ == '__main__':
    main()

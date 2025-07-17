import os
import asyncio
import datetime
import pytz
from telethon import TelegramClient, functions, errors

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE')

client = TelegramClient('session_name', api_id, api_hash)

async def main():
    await client.start(phone)
    moscow = pytz.timezone('Europe/Moscow')
    prev_time = None

    while True:
        now = datetime.datetime.now(moscow).strftime('%H:%M')
        if now != prev_time:
            name = f'Бахти | {now}'
            try:
                await client(functions.account.UpdateProfileRequest(
                    first_name=name,
                    last_name=''
                ))
                print(f'Имя обновлено на {name}')
                prev_time = now
            except errors.FloodWaitError as e:
                print(f'Лимит! Ждём {e.seconds} секунд.')
                await asyncio.sleep(e.seconds + 1)
            except Exception as e:
                print(f'Ошибка: {e}')
        await asyncio.sleep(30)

client.loop.run_until_complete(main())
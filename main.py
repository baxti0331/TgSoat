import os
import asyncio
import datetime
import pytz
from telethon import TelegramClient, functions, errors

api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE')
code = os.getenv('TELEGRAM_CODE')  # Одноразовый код для первого входа

client = TelegramClient('session_name', api_id, api_hash)

async def main():
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        await client.sign_in(phone, code)
        print("Вход выполнен успешно!")

    prev_time = None
    moscow = pytz.timezone('Europe/Moscow')

    while True:
        now = datetime.datetime.now(moscow).strftime('%H:%M')

        if now != prev_time:
            name = f'Иван | {now}'
            try:
                await client(functions.account.UpdateProfileRequest(
                    first_name=name,
                    last_name=''
                ))
                print(f'Имя обновлено на {name}')
                prev_time = now

            except errors.FloodWaitError as e:
                print(f'Попали в лимит! Ждем {e.seconds} секунд.')
                await asyncio.sleep(e.seconds + 1)

            except Exception as e:
                print(f'Другая ошибка: {e}')

        await asyncio.sleep(30)

client.loop.run_until_complete(main())
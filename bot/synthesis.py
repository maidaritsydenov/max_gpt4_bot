# sberaluteSpeech.py
# Синтез текста в речь с помощью SBER SaluteSpeech
# https://developers.sber.ru/docs/ru/salutespeech/category-overview
# Для работы требует установки сертификатов от Минцифры

import os
import uuid
import requests
import json
import base64
import time
import asyncio
import aiohttp
import aiofiles
import platform
from pathlib import Path

import config


SLEEP_TIME = 5
CWD = Path.cwd()


class sberSaluteSpeech:
    def __init__(
                self,
                sber_salute_token,
                sber_salute_scope,
                path_to_sertificate,
                unique_id
                ):
        self.sber_salute_token = sber_salute_token
        self.sber_salute_scope = sber_salute_scope
        self.path_to_sertificate = path_to_sertificate
        self.unique_id = unique_id
        self.access_token, self.access_token_expires_at = self.get_access_token()


    # Получаем токен доступа к API
    # https://developers.sber.ru/docs/ru/salutespeech/authentication
    def get_access_token(self):
        end_point = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

        headers = {
            'Authorization': f'Basic {self.sber_salute_token}',
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = {
            "scope": self.sber_salute_scope
        }
        data = json.dumps(body)
        r = requests.post(end_point, verify=f'{self.path_to_sertificate}', headers=headers, data=body)
        data = r.json()
        # pprint(data)
        access_token = data["access_token"]
        access_token_expires_at = data["expires_at"]
        return access_token, access_token_expires_at


    # Если до конца жизни токена осталось меньше 5 минут - обновляем его
    def update_access_token(self) -> str:
        now = int(time.time() * 1000)
        if (self.access_token_expires_at <= now + 300):
            self.access_token, self.access_token_expires_at = self.get_access_token()
        return self.access_token
    
    
    async def upload_file(self, path_to_file):
        print('1. Загрузка файла')
        url = 'https://smartspeech.sber.ru/rest/v1/data:upload'
        headers = {
            'Authorization': f'Bearer {self.update_access_token()}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        text_file = open(f'{path_to_file}', 'rb')
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=text_file, headers=headers, ssl=False) as r:
                if r.status == 200:
                    response = await r.json()
                    request_file_id = response["result"]["request_file_id"]
                else:
                    raise RuntimeError("Ошибка загрузки файла!")
        await self.create_task(request_file_id)

    
    async def create_task(self, request_file_id):
        print('2. Создание задачи')
        url = 'https://smartspeech.sber.ru/rest/v1/text:async_synthesize'
        headers = {
            'Authorization': f'Bearer {self.update_access_token()}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = '{ "audio_encoding": "opus", "voice": "Bys_24000", "request_file_id": '
        data += f'"{request_file_id}"'
        data += "}'"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, ssl=False) as r:
                if r.status == 200:
                    response = await r.json()
                    id = response['result']['id']
                else:
                    raise RuntimeError("Ошибка загрузки файла!")
        await self.get_task_status(id)

            
    async def get_task_status(self, id, try_num=1):
        print('3. Получение статуса задачи')
        url = 'https://smartspeech.sber.ru/rest/v1/task:get'
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        
        while True:
            await asyncio.sleep(SLEEP_TIME)
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}?id={id}", headers=headers, ssl=False) as r:
                    if r.status == 200:
                        response = await r.json()
                
                        status = response['status']
                        status_at = response['result']['status']
                        print(f' Попытка: {try_num + 1}')
                        print(status, status_at)

                        if try_num > 5:
                            await self.cancel_task(id=id)
                        if response["result"]["status"] == "NEW":
                            print('-', end='', flush=True)
                            continue
                        elif response["result"]["status"] == "RUNNING":
                            print('+', end='', flush=True)
                            continue
                        elif response["result"]["status"] == "CANCELED":
                            print('\nTask has been canceled')
                            break
                        elif response["result"]["status"] == "ERROR":
                            print('\nTask has failed:', response["result"]["error"])
                            response_file_id = None
                            break
                        elif response["result"]["status"] == "DONE":
                            print('\nTask has finished successfully:', response)
                            response_file_id = response["result"]["response_file_id"]
                            break

        if response_file_id:
            recognition_result = await self.download(response_file_id)
            with open(f"{CWD}/voice_messages/voice_message_{self.unique_id}.ogg", "wb") as f:
                f.write(recognition_result.content)
        else:
            raise RuntimeError("Ошибка в синтезе речи в SBER SalutSpeech!")
        print("FINISH!")

        return recognition_result


    async def cancel_task(self, id):
        print('Отмена задачи')
        url = 'https://smartspeech.sber.ru/rest/v1/task:cancel'
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}?id={id}", headers=headers, ssl=False) as r:
                if r.status == 200:
                    result = await r.json()
                    status = result['status']
                    if status == 'CANCELED':
                        # id = result['result']['id']
                        status_at = result['result']['status']
                        return status_at
                    else:
                        message = result['message']
                        print(message)


    async def download(self, response_file_id):
        print('4. Скачивание результата')
        url = 'https://smartspeech.sber.ru/rest/v1/data:download'

        headers = {
            'Authorization': f'Bearer {self.update_access_token()}',
        }

        params = {
        'response_file_id': f'{response_file_id}',
        }

        response = requests.get(
            url=url,
            verify=f'{self.path_to_sertificate}',
            params=params,
            headers=headers,
        )
        return response


async def create_file(text, unique_id):
    text_file = f'{CWD}/text_messages/text_message_{unique_id}.txt'

    async with aiofiles.open(text_file, 'w+', encoding='utf-8') as f:
        await f.write(text)

    stats = os.stat(text_file)
    print(f'Размер файла до: {stats.st_size}')

    if stats.st_size < 401:
        async with aiofiles.open(text_file, 'a') as f:
            await f.write('\x00' * (401 - stats.st_size))

    stats = os.stat(text_file)
    print(f'Размер файла после: {stats.st_size}')

    text_file = Path(text_file)
    return text_file


async def main(text, unique_id):
    platname = platform.system()
    if platname == 'Windows':
        path_to_sertificate = Path('D:/NewDev/max_gpt4_bot', config.PATH_TO_SERTIFICATE)
    else:
        path_to_sertificate = Path('/code', config.PATH_TO_SERTIFICATE)
    

    sber_salite_token_64 = config.SBER_SALUTE_TOKEN
    sber_salute_scope = config.SBER_SALUTE_SCOPE
    sber = sberSaluteSpeech(sber_salite_token_64, sber_salute_scope, path_to_sertificate, unique_id)
    text_file = await create_file(text, unique_id)
    text = await sber.upload_file(text_file)
    text_file = f"{CWD}/voice_messages/voice_message_{unique_id}.ogg"
    return text_file


if __name__ == "__main__":
    unique_id = 123
    text = 'Тест синтеза речи. УУУ получилось!'
    asyncio.run(main(text, unique_id), debug=False)
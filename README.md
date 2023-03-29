# Telegram Bot MaxBot (MidJourney, ChatGPT, etc.)

<p align="center">
<a href="https://t.me/max_gpt4_bot" alt="bot_pic"><img src="https://github.com/maidaritsydenov/max_gpt4_bot/blob/main/static/header.jpg" width="1288" height="240" /></a>
</p>

<p align="center">
<a href="https://t.me/max_gpt4_bot" alt="Run Telegram Bot shield"><img src="https://img.shields.io/badge/RUN-Telegram%20Bot-blue" /></a>
</p>

### The project is under development

* Telegram bot [@max_gpt4_bot](https://t.me/max_gpt4_bot)
* Telegram test bot [@maxima_gpt4_bot](https://t.me/maxima_gpt4_bot)


## Features
- Special chat modes: 👩🏼‍🎓 Assistant, 👩🏼‍💻 Code Assistant, 🎬 Wicked. More soon
- Context in groups
- GPT-4 model
- StableDiffusion
- Kaiber AI
- Track balance spent on OpenAI API
- New design (inline buttons, new pics, main menu, wallet)


## Commands:
- /balance – Показать баланс 💰
- /profile - Личный кабинет с инлайн-кнопками 🗄
- /pay – Купить 100 000 токенов 💳


## Commands for admins:
- /reset user_id – Обнулить лимит токенов у юзера
- /add user_id amount – Пополнить лимит токенов у юзера
- /get_users – Получить csv-файл со списком юзеров
- /get_subs – Получить csv-файл со списком платных подписчиков
- /send_message text - Отправить text всем юзерам
- /delete user_id - Удалить юзера из БД (#)

- 📸 Отправьте фото, видео, кружок или гиф с подписью для перессылки всем юзерам


<p align="center">
<a href="https://t.me/max_gpt4_bot" alt="bot_pic"><img src="https://github.com/maidaritsydenov/max_gpt4_bot/blob/main/static/maxima_gpt4_bot.gif" width="239" height="480" /></a>
</p>

## Usage
В приватных чатах:
```
1. Запрос текста - текст | Запрос изображения - "Нарисуй" | Запрос голосового сообщения - "Расскажи"
2. Запрос текста - голосовое сообщение
```

В группах:
```
Макс, | Макс, нарисуй | Макс, расскажи
```


## Deploy to server
#### TODO: Добавить GitHub workflow для автодеплоя на сервер

* Зайти на сервер
```
ssh username@server_address
```

* Обновить установленные пакеты:
```
sudo apt update
sudo apt upgrade -y
```

* Установить pip (Необязательно)
```
sudo apt install python3-pip
```

* Установить Docker и Docker-Compose:
```
sudo apt install docker.io
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

* Создать ssh-key и добавить на GitHub
```
ssh-keygen
```

* Склонировать репозиторий на сервер
```
git clone git@github.com:{username}/max_gpt4_bot.git
```

* Перейти в папку проекта и скопировать файлы конфига
```
cd max_gpt4_bot
cp config/config.env.example config/config.env
cp config/config.yml.example config/config.yml
```

* Заполнить следующие константы в файле config.yml:
- telegram_token: "" # телеграм токен
- openai_api_key: "" # апи ключ с сайта openai.com
- SBER_SALUTE_TOKEN: "" # апи ключ с сайта salutespeech.ru
- payment_token: "" # токен с botfather payments (yoomoney)
- admin_ids: [] # id юзеров - администраторов
- bot_username: "" # никнейм бота (без @)


* Выполнить сборку и запуск контейнеров
```
sudo docker compose up -d --build
```


* Перед повторной сборкой необходимо удалить папку ".mongodb", удалить все images и volumes в докере.


### Documentation:
* [chat.openai.com](https://chat.openai.com)
* [sbercloud.ru/ru/aicloud/salutespeech](https://developers.sber.ru/docs/ru/salutespeech/category-overview)


<h4>Contact me:</h4>

<a href='https://t.me/maidaritsydenov'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/telegram.svg" width="32" 
   height="32" alt="Telegram"></a>
<a href='https://www.linkedin.com/in/maidari-tsydenov-315b89264/'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/linkedin.svg" width="32" 
   height="32" alt="Linkedin"></a>
<a href='https://www.instagram.com/maidaritsydenov/'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/instagram.svg" width="32" 
   height="32" alt="Instagram"></a>
<a href='https://career.habr.com/maidaritsydenov'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/habr.svg" width="32" 
   height="32" alt="Habr"></a>




# The project is under development

# Telegram Bot MaxBot [@max_gpt4_bot](https://t.me/max_gpt4_bot)
## Test Bot MaxBot [@maxima_gpt4_bot](https://t.me/maxima_gpt4_bot)


## Features
- Special chat modes: 👩🏼‍🎓 Assistant, 👩🏼‍💻 Code Assistant, 🎬 Wicked. More soon
- Context in groups
- GPT-4 model
- StableDiffusion
- Kaiber AI
- Track balance spent on OpenAI API
- Payment system
- Admin system
- New design (inline buttons, new pics, main menu, wallet)

<p align="center">
<a href="https://t.me/max_gpt4_bot" alt="bot_pic"><img src="https://github.com/maidaritsydenov/max_gpt4_bot/blob/main/static/varfix-ai-chatbot-gpt-3.png" width="100" height="100" /></a>
</p>

<p align="center">
<a href="https://t.me/max_gpt4_bot" alt="Run Telegram Bot shield"><img src="https://img.shields.io/badge/RUN-Telegram%20Bot-blue" /></a>
</p>


Documentation: [chat.openai.com](https://chat.openai.com)
You can use mine bot: [@max_gpt4_bot](https://t.me/max_gpt4_bot)


# Usage
* В приватных чатах:
1. Текстовое сообщение: Запрос текста - текст, Запрос изображения - "Нарисуй", Запрос голосового сообщения - "Расскажи"
2. Голосовое сообщение: Запрос текста - голосовое сообщение

* В группах:
1. Аналогично, но с добавлением слова "Макс, " (Макс, | Макс, нарисуй | Макс, расскажи)


# Deploy

## Локально
* Перейти в папку проекта и скопировать файлы конфига
```
cd max_gpt4_bot
cp config/config.env.example config/config.env
cp config/config.yml.example config/config.yml
```

* Заполнить следующие константы:
config.yml:
- telegram_token: ""
- openai_api_key: ""
- SBER_SALUTE_TOKEN: ""

* Выполнить сборку и запуск контейнеров
```
sudo docker compose up -d --build
```

## На сервер
### TODO: Добавить GitHub workflow для автодеплоя на сервер

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

* Склонировать репозиторий на сервер

* Перейти в папку проекта и скопировать файлы конфига
```
cd max_gpt4_bot
cp config/config.env.example config/config.env
cp config/config.yml.example config/config.yml
```

* Заполнить следующие константы:
config.yml:
- telegram_token: ""
- openai_api_key: ""
- SBER_SALUTE_TOKEN: ""

* Выполнить сборку и запуск контейнеров
```
sudo docker compose up -d --build
```


### Authors:
<h4> Maidari Tsydenov </h4>

<h4>Contact me:</h4>

<a href='https://t.me/maidaritsydenov'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/telegram.svg" width="32" 
   height="32" alt="Пример"></a>
<a href='https://www.linkedin.com/in/maidari-tsydenov-315b89264/'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/linkedin.svg" width="32" 
   height="32" alt="Пример"></a>
<a href='https://www.instagram.com/maidaritsydenov/'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/instagram.svg" width="32" 
   height="32" alt="Пример"></a>
<a href='https://career.habr.com/maidaritsydenov'><img src="https://github.com/maidaritsydenov/maidaritsydenov/blob/main/logo/habr.svg" width="32" 
   height="32" alt="Пример"></a>




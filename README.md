# The project is under development
# Telegram Bot MaxBot


## Features
- Special chat modes: 👩🏼‍🎓 Assistant, 👩🏼‍💻 Code Assistant, 🎬 Wicked. More soon
- Context in groups
- GPT-4 model
- StableDiffusion, Midjourney
- Kaiber AI
- Track balance spent on OpenAI API


<p align="center">
<a href="https://t.me/ai_open_gpt_chat_bot" alt="Bot pic"><img src="https://github.com/maidaritsydenov/max_gpt4_bot/blob/main/static/varfix-ai-chatbot-gpt-3.png" width="100" height="100" /></a>
</p>

<p align="center">
<a href="https://t.me/max_gpt4_bot" alt="Run Telegram Bot shield"><img src="https://img.shields.io/badge/RUN-Telegram%20Bot-blue" /></a>
</p>

Documentation: [chat.openai.com](https://chat.openai.com)

You can use mine bot: [@max_gpt4_bot](https://t.me/max_gpt4_bot)



# Usage
* В приватных чатах:
1. Текстовое сообщение: Запрос текстом - текст, Запрос изображения - "Нарисуй"
2. Голосовое сообщение: Запрос текстом - голосовое сообщение, Запрос голосовым сообщением - голосовое сообщение с "Расскажи"

* В группах:
1. Аналогично, но с добавлением "Макс"


# Deploy

## Локально

## На сервер

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

* Установить Docker и Docker-compose:
```
sudo apt install docker.io
```
```
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
```
```
sudo chmod +x /usr/local/bin/docker-compose
```




cd max_gpt4_bot
cp config/config.env.example config/config.env
cp config/config.yml.example config/config.yml

config.yml:
telegram_token: ""
openai_api_key: ""
SBER_SALUTE_TOKEN






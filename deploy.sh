# После установки прав на исполнения нужно сбросить
git checkout deploy.sh

# подтягиваем с git
git pull origin main

# пересобираем контейнер
# TODO: если перенастроить докер не понадобится делать постоянный build
sudo docker compose down
sudo docker compose up -d --build


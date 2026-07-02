# smn-telegram-relay

cp env.example .env

docker-compose up -d

15 */6   * * *   root    docker exec smn-telegram-relay python msgdog.py >> /var/log/msgdog.log

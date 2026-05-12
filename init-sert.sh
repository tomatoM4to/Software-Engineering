#!/bin/bash
# Nginx 컨테이너가 80포트를 점유하고 있다면 임시 중지
docker compose stop nginx || true

# Certbot 컨테이너를 일회성(--rm)으로 실행하여 인증서 발급
# 주의: 이 명령어를 실행하기 전에 도메인의 A 레코드가 OCI 서버 IP를 가리키고 있어야 합니다.
docker run -it --rm --name certbot \
  -p 80:80 \
  -v "$(pwd)/.nginx/certbot/conf:/etc/letsencrypt" \
  -v "$(pwd)/.nginx/certbot/www:/var/www/certbot" \
  certbot/certbot certonly --standalone \
  -d ${DOMAIN} \
  --email ${EMAIL} \
  --agree-tos \
  --no-eff-email

echo "인증서 초기 발급 완료! Nginx를 다시 시작합니다."
docker compose up -d nginx
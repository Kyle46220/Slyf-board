#!/bin/bash
# Append to .env
grep -q "AWS_PUBLIC_URL=" /opt/backend/.env || echo "AWS_PUBLIC_URL=https://pub-70423089a47d4920893525bd40c9fd39.r2.dev" >> /opt/backend/.env

# Restart service
systemctl restart board

# Update DB
sudo -u postgres psql board -c "UPDATE posts SET media_path = replace(media_path, 'https://91b2dd352800097303449d2988f1471c.r2.cloudflarestorage.com/slyfe', 'https://pub-70423089a47d4920893525bd40c9fd39.r2.dev');"
sudo -u postgres psql board -c "UPDATE posts SET og_image_path = replace(og_image_path, 'https://91b2dd352800097303449d2988f1471c.r2.cloudflarestorage.com/slyfe', 'https://pub-70423089a47d4920893525bd40c9fd39.r2.dev');"

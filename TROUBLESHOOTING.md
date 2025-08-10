### С какими ошибками я столкнулась и как их решила:

| Ошибка | Причина | Решение |
|--------|--------|--------|
| `Saving key failed` | Нет папки `.ssh` | `mkdir "%USERPROFILE%\.ssh"` |
| `SSH key not found` | Ключ не найден | `ssh-keygen -t ed25519 -C "yc-user"` |
| `Image not found` | Неправильное имя образа | Используйте `ubuntu-2204-lts` |
| `ERROR: unable to read file 'ssh-rsa...'` | Передан ключ как строка | Используйте `#cloud-config` |
| `Connection refused` | ВМ не загружена | Подождите 90 секунд |
| `Zone not available` | Нет ресурсов | Попробуйте `ru-central1-b` |
| `Port 80 closed` | Группа безопасности | `yc vpc sg update default --add-rule port=80` |

> Мой скрипт делает это автоматически.

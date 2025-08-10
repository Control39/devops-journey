
# Полезные команды для управления Yandex Cloud.

## Управление ВМ

```bash
# Список ВМ
yc compute instance list

# Создать ВМ
yc compute instance create \
  --name auto-vm \
  --zone ru-central1-a \
  --public-ip \
  --create-boot-disk image-family=ubuntu-2204-lts,size=20 \
  --memory 2GB \
  --cores 2

# Остановить ВМ
yc compute instance stop auto-vm

# Удалить ВМ
yc compute instance delete auto-vm
```

## Управление SSH

```bash
# Создать ключ
ssh-keygen -t ed25519 -C "yc-user"

# Проверить публичный ключ
cat ~/.ssh/id_ed25519.pub
```

## Группы безопасности

```bash
# Открыть порт 80
yc vpc security-group update default --add-rule port=80
```

---

> Совет: используйте `--format yaml` или `--format json`- для детального вывода.

---
import subprocess
import json
import time
import os
import sys

VERSION = "1.1.7" # Обновляем версию

def print_header():
    print("=" * 60)
    print(f"АВТОМАТИЗИРОВАННОЕ СОЗДАНИЕ ВМ В ЯНДЕКС.ОБЛАКЕ (v{VERSION})".center(60))
    print("=" * 60)
    print("Скрипт создаст виртуальную машину с веб-сервером Nginx")
    print("и откроет доступ к ней через интернет\n")

def check_yc_installed():
    try:
        subprocess.run(["yc", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("[OK] YC CLI обнаружен")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] YC CLI не установлен или не найден в PATH")
        print("Установите его по инструкции: https://cloud.yandex.ru/docs/cli/quickstart")
        return False

def check_billing():
    try:
        result = subprocess.run(["yc", "billing", "info"], capture_output=True, text=True)
        if "No billing" in result.stdout:
            print("[WARNING] У вас нет активного платёжного аккаунта")
            print("Создайте его в консоли: https://console.cloud.yandex.ru/billing")
            return False
        return True
    except:
        print("[INFO] Не удалось проверить платёжный аккаунт, продолжаем работу")
        return True

def get_ubuntu_image_param():
    """Определяет, какой параметр образа использовать (image-name или image-family).
    Для Ubuntu LTS всегда предпочтительнее image-family."""
    
    # Для стандартных Ubuntu LTS образов всегда используем family
    default_family = "ubuntu-2204-lts"
    
    try:
        # Проверяем, что семейство существует в standard-images [2]
        result = subprocess.run([
            "yc", "compute", "image", "get-latest-from-family", 
            default_family,
            "--folder-id", "standard-images", # Явно указываем folder-id
            "--format", "json"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            image_data = json.loads(result.stdout)
            image_name = image_data.get('name', '')
            print(f"[INFO] Найден образ Ubuntu через семейство {default_family}: {image_name}")
            return default_family, "image-family" # Используем семейство [1][12]
        else:
            print(f"[WARNING] Не удалось найти семейство {default_family}, попытка поиска конкретного образа.")
            # Если семейство не найдено, пытаемся найти конкретный образ, хотя это менее надежно
            result_list = subprocess.run([
                "yc", "compute", "image", "list", 
                "--folder-id", "standard-images", # Явно указываем folder-id
                "--format", "json"
            ], capture_output=True, text=True)
            
            if result_list.returncode == 0:
                images = json.loads(result_list.stdout)
                ubuntu_images = []
                for img in images:
                    name = img.get('name', '').lower()
                    if ('ubuntu' in name and 
                        '22-04' in name and 
                        'nat-instance' not in name and
                        'gpu' not in name and
                        'container' not in name):
                        ubuntu_images.append(img)
                
                if ubuntu_images:
                    ubuntu_images.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                    image_name = ubuntu_images[0]['name']
                    print(f"[INFO] Найден конкретный образ Ubuntu: {image_name}")
                    return image_name, "image-name"
            
    except Exception as e:
        print(f"[WARNING] Ошибка при поиске образа: {e}")
    
    print(f"[INFO] Использую семейство образов по умолчанию: {default_family}")
    return default_family, "image-family"

def get_config():
    image_value, image_param = get_ubuntu_image_param()
    
    return {
        "vm_name": os.getenv("YC_VM_NAME", "auto-vm"),
        "zone": os.getenv("YC_ZONE", "ru-central1-a"),
        "memory": os.getenv("YC_MEMORY", "2"),
        "cores": os.getenv("YC_CORES", "2"),
        "image_value": image_value,  # Это может быть имя или семейство
        "image_param": image_param,  # "image-name" или "image-family"
        "disk_size": os.getenv("YC_DISK_SIZE", "20")
    }

def get_ssh_key_path():
    """Ищет SSH-ключ в стандартных местах"""
    home_dir = os.path.expanduser("~")
    
    # Возможные пути к SSH-ключам
    possible_paths = [
        os.path.join(home_dir, ".ssh", "id_ed25519.pub"),
        os.path.join(home_dir, ".ssh", "id_rsa.pub"),
        os.path.join(home_dir, "ssh", "id_ed25519.pub"),
        os.path.join(home_dir, "ssh", "id_rsa.pub")
    ]
    
    # Для Windows добавляем дополнительные пути
    if os.name == 'nt':
        userprofile = os.environ.get('USERPROFILE', '')
        possible_paths.extend([
            os.path.join(userprofile, ".ssh", "id_ed25519.pub"),
            os.path.join(userprofile, ".ssh", "id_rsa.pub"),
            os.path.join(userprofile, "ssh", "id_ed25519.pub"),
            os.path.join(userprofile, "ssh", "id_rsa.pub")
        ])
    
    # Ищем первый существующий ключ
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def format_ssh_key(public_key):
    """Форматирует SSH-ключ для передачи в YC CLI"""
    key_content = public_key.strip()
    
    # Проверяем, что ключ начинается с правильного типа
    if not (key_content.startswith('ssh-ed25519') or 
            key_content.startswith('ssh-rsa') or 
            key_content.startswith('ecdsa-sha2')):
        raise ValueError("Неподдерживаемый тип SSH-ключа")
    
    # Возвращаем ключ как есть
    return key_content

def create_metadata_file(ssh_key):
    """Создает временный файл с метаданными"""
    import tempfile
    
    metadata_content = f"""#cloud-config
users:
  - name: yc-user
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - {ssh_key.strip()}

packages:
  - nginx

runcmd:
  - systemctl enable nginx
  - systemctl start nginx
  - ufw allow 'Nginx Full'
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write(metadata_content)
        return f.name

def main():
    print_header()

    if not check_yc_installed():
        sys.exit(1)

    if not check_billing():
        print("\n[WARNING] Продолжить без платёжного аккаунта? (y/n)")
        if input().lower() != 'y':
            sys.exit(1)

    print("\n[INFO] Ищу SSH-ключ...")
    key_path = get_ssh_key_path()

    if not key_path:
        print("[ERROR] SSH-ключ не найден")
        print("Создайте ключ командой:")
        print("  ssh-keygen -t ed25519 -C 'yc-user' -f ~/.ssh/id_ed25519")
        print("или")
        print("  ssh-keygen -t rsa -b 4096 -C 'yc-user' -f ~/.ssh/id_rsa")
        sys.exit(1)

    print(f"[OK] Использую SSH-ключ: {key_path}")

    try:
        with open(key_path, 'r', encoding='utf-8') as f:
            public_key = f.read()
    except Exception as e:
        print(f"[ERROR] Не удалось прочитать SSH-ключ: {e}")
        sys.exit(1)

    # Форматируем ключ
    try:
        clean_key = format_ssh_key(public_key)
        print(f"[INFO] SSH-ключ успешно загружен")
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    config = get_config()
    print(f"[INFO] Использую параметры:")
    print(f"  Имя ВМ: {config['vm_name']}")
    print(f"  Зона: {config['zone']}")
    print(f"  Память: {config['memory']} ГБ")
    print(f"  Ядра: {config['cores']}")
    print(f"  Образ: {config['image_value']} ({config['image_param']})")
    print(f"  Размер диска: {config['disk_size']} ГБ")

    # Создаем файл с метаданными
    metadata_file = None
    try:
        metadata_file = create_metadata_file(clean_key)
        print(f"[INFO] Создан файл метаданных: {metadata_file}")

        # Создаем команду с аргументами
        disk_params = f"type=network-ssd,size={config['disk_size']}"
        # Для публичных образов всегда указываем image-folder-id=standard-images [24]
        disk_params += f",image-folder-id=standard-images" 

        # Добавляем либо image-family, либо image-name
        if config['image_param'] == "image-family":
            disk_params += f",image-family={config['image_value']}"
        else: # config['image_param'] == "image-name"
            disk_params += f",image-name={config['image_value']}"

        cmd = [
            "yc", "compute", "instance", "create",
            "--name", config["vm_name"],
            "--zone", config["zone"],
            "--platform", "standard-v3",
            "--memory", config["memory"],
            "--cores", config["cores"],
            "--network-interface", "subnet-name=default-ru-central1-a,nat-ip-version=ipv4",
            "--create-boot-disk", disk_params, # Использование обновленных disk_params
            "--metadata-from-file", f"user-data={metadata_file}"
        ]

        use_shell = os.name == 'nt'

        print("\n[ACTION] Запускаю создание ВМ...")
        print("Эта операция может занять 2-5 минут")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            shell=use_shell
        )

        if result.returncode != 0:
            print(f"\n[ERROR] Ошибка при создании ВМ (код {result.returncode}):")
            print(result.stderr or result.stdout)
            
            # Показываем доступные образы Ubuntu, исключая NAT-инстансы
            print("\n[INFO] Доступные образы Ubuntu (без NAT-инстансов):")
            try:
                images_result = subprocess.run([
                    "yc", "compute", "image", "list", 
                    "--folder-id", "standard-images",
                    "--format", "table"
                ], capture_output=True, text=True, shell=use_shell)
                
                if images_result.returncode == 0:
                    lines = images_result.stdout.split('\n')
                    ubuntu_lines = [line for line in lines if 'ubuntu' in line.lower() and 'nat-instance' not in line.lower() and 'gpu' not in line.lower()]
                    for line in ubuntu_lines[:10]:  # Показываем первые 10
                        if line.strip():
                            print(f"  {line}")
            except:
                pass
            
            sys.exit(1)

        # Парсим IP
        try:
            vm_data = json.loads(result.stdout)
            ip = vm_data['network_interfaces'][0]['primary_v4_address']['one_to_one_nat']['address']
            print(f"\n[SUCCESS] ВМ успешно создана! Внешний IP: {ip}")
        except (json.JSONDecodeError, KeyError):
            print("Не удалось получить IP автоматически.")
            print(f"Посмотрите вручную: yc compute instance get {config['vm_name']} --format json")
            ip = "ВАШ_IP_АДРЕС"

        print("\n[INFO] Жду 90 секунд для инициализации ВМ...")
        time.sleep(90)

        print("\n[ACTION] Открываю порт 80...")
        sg_cmd = [
            "yc", "vpc", "security-group", "update", "default",
            "--add-rule", "direction=ingress,port=80,protocol=tcp,v4-cidrs=0.0.0.0/0"
        ]
        sg_result = subprocess.run(sg_cmd, capture_output=True, text=True, shell=use_shell)
        if sg_result.returncode == 0:
            print("[OK] Порт 80 открыт")
        else:
            print(f"[WARNING] Не удалось открыть порт 80: {sg_result.stderr}")

        print("\n" + "=" * 60)
        print("ВМ УСПЕШНО СОЗДАНА".center(60))
        print("=" * 60)
        
        # Определяем путь к приватному ключу
        private_key_path = key_path.replace(".pub", "")
        ssh_users = ["yc-user", "ubuntu"]
        
        print("\nДля SSH подключения:")
        for user in ssh_users:
            if os.name == 'nt':
                print(f"  ssh -i \"{private_key_path}\" {user}@{ip}")
            else:
                print(f"  ssh -i {private_key_path} {user}@{ip}")
        
        print(f"\nПроверьте веб-сайт: http://{ip}")
        print(f"Удалить ВМ: yc compute instance delete {config['vm_name']}")

    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        # Удаляем временный файл метаданных
        if metadata_file and os.path.exists(metadata_file):
            try:
                os.unlink(metadata_file)
                print(f"[INFO] Временный файл удален: {metadata_file}")
            except:
                pass

if __name__ == "__main__":
    main()

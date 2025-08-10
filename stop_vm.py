# stop_vm.py
# Останавливает ВМ в Яндекс.Облаке

import subprocess
from datetime import datetime

print("⏳ Останавливаю ВМ...")

# Параметры
vm_name = "test-final-vm"

# Команда
cmd = [
    "yc", "compute", "instance", "stop",
    vm_name
]

# Запускаем
result = subprocess.run(cmd, capture_output=True, text=True)

# Логируем
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open("stop_vm_log.txt", "w", encoding="utf-8") as f:
    f.write(f"=== {now} ===\n")
    if result.returncode == 0:
        f.write("✅ ВМ остановлена успешно\n")
        f.write(result.stdout)
    else:
        f.write("❌ Ошибка при остановке ВМ\n")
        f.write(result.stderr)

# Выводим результат
if result.returncode == 0:
    print("✅ ВМ остановлена! Проверь статус: yc compute instance list")
else:
    print("❌ Ошибка:")
    print(result.stderr)
import time
from ftplib import FTP
import os
import subprocess
import sys
import logging
import toml
from socket import gaierror

logging.basicConfig(
    filename="update.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def connect_ftp(server, username, password, max_retries=10, retry_interval=30):
    for attempt in range(max_retries):
        try:
            ftp = FTP(server)
            ftp.login(username, password)
            logging.info(f"Успешное подключение к FTP-серверу")
            return ftp
        except (gaierror, OSError) as e:
            logging.warning(f"Попытка {attempt + 1}/{max_retries}: Не удалось подключиться к FTP-серверу. Ошибка: {e}")
            if attempt < max_retries - 1:
                logging.info(f"Повторная попытка через {retry_interval} секунд...")
                time.sleep(retry_interval)
            else:
                logging.error("Достигнуто максимальное количество попыток подключения. Выход из программы.")
                sys.exit(1)


def stop_process(process_name):
    try:
        result = subprocess.run(f"taskkill /f /im {process_name}", check=True, shell=True, text=True,
                                capture_output=True)
        if result.returncode == 0:
            logging.info(f"Процесс {process_name} успешно остановлен.")
        else:
            logging.warning(f"Процесс {process_name} не найден или не удалось остановить. Вывод: {result.stdout}")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при остановке процесса {process_name}: {e}")


def check_process_stopped(process_name):
    try:
        result = subprocess.run(f"tasklist /fi \"IMAGENAME eq {process_name}\"", check=True, shell=True, text=True,
                                capture_output=True)
        if process_name.lower() in result.stdout.lower():
            logging.warning(f"Процесс {process_name} все еще работает.")
            return False
        logging.info(f"Подтверждено: Процесс {process_name} успешно остановлен.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Ошибка при проверке процесса {process_name}: {e}")


def download_files(ftp, remote_dir, local_dir):
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    ftp.cwd(remote_dir)
    files = ftp.nlst()
    for file_name in files:
        local_file_path = os.path.join(local_dir, file_name)
        with open(local_file_path, 'wb') as local_file:
            ftp.retrbinary(f"RETR {file_name}", local_file.write)
        logging.info(f"Файл {file_name} скачан в {local_file_path}")


def start_process(process_path):
    try:
        subprocess.Popen(process_path, shell=True)
        logging.info(f"Процесс {process_path} успешно запущен.")
    except Exception as e:
        logging.error(f"Ошибка при запуске процесса {process_path}: {e}")
        sys.exit(1)


def main():
    secrets = toml.load(".secrets/secrets.toml")
    server = secrets["ftp"]["server"]
    username = secrets["ftp"]["username"]
    password = secrets["ftp"]["password"]
    remote_dir = '/R_C_Updates/'
    local_dir = 'C:/R-C Client/'
    process_name = 'client.exe'
    process_path = 'C:\\R-C Client\\client.exe'

    stop_process(process_name)
    while not check_process_stopped(process_name):
        logging.info("Ожидание завершения процесса...")
        time.sleep(2)

    ftp = connect_ftp(server, username, password)
    download_files(ftp, remote_dir, local_dir)
    ftp.quit()
    start_process(process_path)


if __name__ == "__main__":
    main()

import csv
import socket
import time
import threading
import subprocess
import anydesk
from bdk import get_unique_name, get_host
import custom_logger
import message
import signal

logger = custom_logger.logger("app.log")

HOST, PORT_SERVER, _ = get_host()
WAITING_SECONDS = 30
UNIQUE_NAME = get_unique_name()
HEARTBEAT_INTERVAL = 30  # секунды

# Глобальная переменная для управления работой клиента
client_running = threading.Event()
client_running.set()


def send_message(sock, message):
    if isinstance(message, str):
        message = message.encode("utf-8")
    message_length = len(message)
    sock.sendall(message_length.to_bytes(4, byteorder="big"))
    sock.sendall(message)


def receive_message(sock):
    message_length_bytes = sock.recv(4)
    if not message_length_bytes:
        raise RuntimeError("Соединение прервано при получении длины сообщения")

    message_length = int.from_bytes(message_length_bytes, byteorder="big")

    chunks = []
    bytes_received = 0
    while bytes_received < message_length:
        chunk = sock.recv(min(message_length - bytes_received, 4096))
        if not chunk:
            raise RuntimeError("Соединение прервано при получении сообщения")
        chunks.append(chunk)
        bytes_received += len(chunk)

    response = b"".join(chunks)

    if response.startswith(b"\x89PNG\r\n\x1a\n"):
        return response
    else:
        try:
            return response.decode("utf-8")
        except UnicodeDecodeError:
            return response


def heartbeat(sock):
    while client_running.is_set():
        try:
            send_message(sock, "HEARTBEAT")
            time.sleep(HEARTBEAT_INTERVAL)
        except:
            logger.error("Ошибка отправки heartbeat")
            break


def connect_to_server(unique_name, host, port, waiting_seconds):
    while client_running.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            logger.info("Connected to server")
            send_message(s, f"CONNECT {unique_name}")

            # Запускаем поток для отправки heartbeat
            heartbeat_thread = threading.Thread(target=heartbeat, args=(s,))
            heartbeat_thread.start()

            return s
        except (ConnectionRefusedError, OSError) as e:
            logger.error(f"Connection failed: {e}. Retrying in {waiting_seconds} seconds...")
            time.sleep(waiting_seconds)


def receive_messages(s, unique_name):
    while client_running.is_set():
        try:
            message = receive_message(s)
            logger.info(f"Received from server: {message}")
            if message == "HEARTBEAT_REQUEST":
                send_message(s, "HEARTBEAT_RESPONSE")
            else:
                answer = run_command(message)
                send_message(s, answer)
        except (ConnectionResetError, RuntimeError, OSError) as e:
            logger.error(f"Error occurred: {e}")
            logger.warning("Connection lost unexpectedly. Reconnecting...")
            break

    start_client(UNIQUE_NAME, HOST, PORT_SERVER, WAITING_SECONDS)


def start_client(unique_name=UNIQUE_NAME, host=HOST, port=PORT_SERVER, waiting_seconds=WAITING_SECONDS):
    s = None
    while client_running.is_set():
        try:
            s = connect_to_server(unique_name, host, port, waiting_seconds)
            receive_thread = threading.Thread(
                target=receive_messages, args=(s, unique_name)
            )
            receive_thread.start()
            receive_thread.join()
        except KeyboardInterrupt:
            logger.error("Client shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.warning(f"Retrying in {waiting_seconds} seconds...")
            time.sleep(waiting_seconds)
        finally:
            if s:
                try:
                    s.close()
                except Exception as e:
                    logger.error(f"Unexpected error with s.close(): {e}")


def get_command_list():
    commands = {}
    with open("commands.csv", mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file, delimiter="$")
        for row in reader:
            commands[row["key"]] = row["command"]
    return commands


def get_command_by_key(key):
    commands = get_command_list()
    return commands.get(key)


def run_command(command):
    command_key = command.split(" ")[0]  # only first key
    command_to_execute = get_command_by_key(command_key)
    match command_key:
        case "ad":
            anydesk.anydesk_screenshot()
            byte_screenshot = anydesk.get_screenshot()
            output = byte_screenshot
            return output
        case "ss":
            anydesk.full_screenshot()
            byte_screenshot = anydesk.get_screenshot()
            output = byte_screenshot
            return output
        case "msg":
            message_text = command.split(" ", 1)[1]
            message_text = message_text.strip("()")
            message.show_message_threaded(message_text)
            return "Сообщение было показано"
        case "update":
            update_exe_path = 'C:\\R-C Client\\update.exe'
            try:
                subprocess.Popen(update_exe_path, shell=True)
                logger.info("Запущен процесс обновления: update.exe")
            except Exception as e:
                logger.error(f"Ошибка при запуске обновления: {e}")
        case None:
            logger.info(f"Command running: {command}")
            result = subprocess.run(
                command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            output = result.stdout.decode("cp866")
            if result.stderr:
                output += "\nDecode Error: " + result.stderr.decode("cp866")
            return output
        case _:
            logger.info(f"Command running: {command_to_execute}")
            result = subprocess.run(
                command_to_execute,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output = result.stdout.decode("cp866")
            if result.stderr:
                output += "\nDecode Error: " + result.stderr.decode("cp866")
            return output


def signal_handler(signum, frame):
    logger.info("Received signal to terminate. Shutting down client...")
    client_running.clear()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    start_client(UNIQUE_NAME, HOST, PORT_SERVER, WAITING_SECONDS)

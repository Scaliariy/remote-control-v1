import socket
import threading
import json
import concurrent.futures
import queue
import signal
import sys
import time
import base64
from bdk import get_host
import custom_logger

_, PORT_SERVER, PORT_STREAMLIT = get_host()
clients = {}
clients_lock = threading.Lock()
responses_queue = queue.Queue()
server_running = threading.Event()
HEARTBEAT_TIMEOUT = 90  # секунды
logger = custom_logger.logger("server.log")


def custom_print(text):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}")
    logger.info(text)


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


def handle_client(conn, addr):
    unique_name = None
    last_heartbeat = time.time()
    try:
        while server_running.is_set():
            try:
                message = receive_message(conn)
                if isinstance(message, str):
                    if message.startswith("CONNECT"):
                        unique_name = message.split(" ", 1)[1]
                        unique_name = f"{unique_name}"
                        with clients_lock:
                            if unique_name in clients:
                                # Закрываем старое соединение
                                old_conn = clients[unique_name]
                                try:
                                    old_conn.close()
                                except:
                                    custom_print(f"Ошибка при закрытии старого соединения для {unique_name}")
                            clients[unique_name] = conn
                        custom_print(f"Клиент подключен: {unique_name} ({addr[0]}:{addr[1]})")
                    elif message == "HEARTBEAT":
                        last_heartbeat = time.time()
                    elif message == "HEARTBEAT_RESPONSE":
                        pass
                        # custom_print(f"Получен ответ от клиента: {unique_name}: {message[:30]}")
                    else:
                        custom_print(f"Получен ответ от клиента: {unique_name}: {message[:30]}")
                        responses_queue.put((unique_name, message))
                elif isinstance(message, bytes):
                    if message.startswith(b"\x89PNG\r\n\x1a\n"):
                        custom_print(f"Получено PNG-изображение от клиента: {unique_name}")
                        responses_queue.put((unique_name, message))
                    else:
                        custom_print(f"Получены неизвестные двоичные данные от клиента: {unique_name}")
                        responses_queue.put((unique_name, message))
                else:
                    custom_print(f"Получен неожиданный тип данных от клиента: {unique_name}")

                # Проверяем время последнего heartbeat
                if time.time() - last_heartbeat > HEARTBEAT_TIMEOUT:
                    raise ConnectionResetError("Heartbeat timeout")

            except (ConnectionResetError, ConnectionAbortedError, RuntimeError) as e:
                custom_print(f"Потеряно соединение с клиентом: {unique_name}: {str(e)}")
                break
    except Exception as e:
        custom_print(f"Ошибка обработки клиента: {unique_name}: {str(e)}")
    finally:
        if unique_name:
            with clients_lock:
                if unique_name in clients:
                    del clients[unique_name]
        try:
            conn.close()
        except:
            pass
        custom_print(f"Клиент отключен: {unique_name}")


def accept_connections(server_socket):
    while server_running.is_set():
        try:
            conn, addr = server_socket.accept()
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.start()
        except socket.timeout:
            continue
        except OSError:
            if not server_running.is_set():
                break
            else:
                custom_print("Ошибка в аccept_connections:", sys.exc_info()[0])
                time.sleep(1)


def send_message_to_client(client, message):
    try:
        send_message(client, message)
        return "success"
    except:
        return "failed"


def handle_streamlit_connection(conn, addr):
    while server_running.is_set():
        try:
            data = receive_message(conn)
            if not data:
                custom_print("Пустые данные получены от Streamlit. Закрытие соединения.")
                break
            try:
                command = json.loads(data)
            except json.JSONDecodeError:
                custom_print(f"Получены некорректные данные от Streamlit: {data}")
                continue

            if command["action"] == "get_clients":
                with clients_lock:
                    client_list = list(clients.keys())
                send_message(conn, json.dumps(client_list))
            elif command["action"] == "send_multi_message":
                target_clients = command["clients"]
                message = command["message"]
                results = {}
                if len(target_clients) > 0:
                    with clients_lock:
                        with concurrent.futures.ThreadPoolExecutor(
                                max_workers=len(target_clients)
                        ) as executor:
                            future_to_client = {
                                executor.submit(send_message_to_client, clients.get(client), message): client
                                for client in target_clients
                            }
                            for future in concurrent.futures.as_completed(future_to_client):
                                client = future_to_client[future]
                                try:
                                    results[client] = future.result()
                                except Exception as exc:
                                    results[client] = "failed"
                send_message(conn, json.dumps(results))
            elif command["action"] == "get_responses":
                responses = []
                while not responses_queue.empty():
                    client, response = responses_queue.get()
                    if isinstance(response, bytes):
                        response = {
                            "type": "image",
                            "data": base64.b64encode(response).decode('utf-8')
                        }
                    else:
                        response = {
                            "type": "text",
                            "data": response
                        }
                    responses.append((client, response))
                send_message(conn, json.dumps(responses))
            elif command["action"] == "shutdown_server":
                server_running.clear()
                time.sleep(2)  # Даем время другим потокам завершиться
                send_message(conn, json.dumps({"status": "shutting_down"}))
                break
            else:
                custom_print(f"Получена неизвестная команда: {command['action']}")
            # Закрываем соединение после каждого успешного действия
            break
        except (ConnectionResetError, RuntimeError) as e:
            custom_print(f"Ошибка соединения с Streamlit: {str(e)}")
            break
        except Exception as e:
            custom_print(f"Неожиданная ошибка при обработке соединения Streamlit: {str(e)}")
            continue
    conn.close()


def start_server(client_port=PORT_SERVER, streamlit_port=PORT_STREAMLIT):
    global server_running
    server_running = threading.Event()
    server_running.set()

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_socket.bind(("", client_port))
    client_socket.listen()
    client_socket.settimeout(1)
    custom_print(f"Сервер запущен для клиентов на порту {client_port}")

    streamlit_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    streamlit_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    streamlit_socket.bind(("", streamlit_port))
    streamlit_socket.listen()
    streamlit_socket.settimeout(1)
    custom_print(f"Сервер запущен для Streamlit на порту {streamlit_port}")

    client_thread = threading.Thread(target=accept_connections, args=(client_socket,))
    client_thread.start()

    def signal_handler(sig, frame):
        custom_print("Выключение сервера...")
        server_running.clear()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def check_client_connections():
        while server_running.is_set():
            with clients_lock:
                for unique_name, conn in list(clients.items()):
                    try:
                        # Отправляем запрос heartbeat
                        send_message(conn, "HEARTBEAT_REQUEST")
                    except:
                        custom_print(f"Не удалось отправить heartbeat на {unique_name}. Удаление клиента.")
                        del clients[unique_name]
            time.sleep(HEARTBEAT_TIMEOUT // 2)

    heartbeat_thread = threading.Thread(target=check_client_connections)
    heartbeat_thread.start()

    try:
        while server_running.is_set():
            try:
                conn, addr = streamlit_socket.accept()
                streamlit_thread = threading.Thread(
                    target=handle_streamlit_connection, args=(conn, addr)
                )
                streamlit_thread.start()
            except socket.timeout:
                continue
    finally:
        server_running.clear()
        client_socket.close()
        streamlit_socket.close()

        # Закрываем все соединения с клиентами
        with clients_lock:
            for client_conn in clients.values():
                try:
                    send_message(client_conn, "SERVER_SHUTDOWN")
                    client_conn.close()
                except:
                    pass

        # Ждем завершения всех потоков
        for thread in threading.enumerate():
            if thread != threading.current_thread():
                thread.join(timeout=5)

        custom_print("Сервер успешно выключен")
        sys.exit(0)


if __name__ == "__main__":
    start_server()

import streamlit as st
import socket
import json
import hmac
import base64
import pandas as pd
import subprocess
from server import send_message, receive_message
from bdk import get_host, search_client, get_unique_client_types, get_unique_client_addresses

HOST, _, PORT_STREAMLIT = get_host()


# Password authentication function
def check_password():
    """Validates the user's password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        try:
            if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
                st.session_state["password_correct"] = True
                del st.session_state["password"]  # Remove the password from session state.
            else:
                st.session_state["password_correct"] = False
        except TypeError:
            st.warning("Пароль должен содержать только латинские буквы, символы и цифры")

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Display input for password.
    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Неправильный пароль")
    return False


# Establish connection with the server
def connect_to_server(host=HOST, port=PORT_STREAMLIT):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        return s
    except Exception as e:
        st.error(f"Не удалось подключиться к серверу: {e}")
        return None


# Fetch the list of connected clients from the server
def get_connected_clients():
    with connect_to_server() as server_socket:
        if server_socket:
            send_message(server_socket, json.dumps({"action": "get_clients"}))
            response = receive_message(server_socket)
            return json.loads(response)
    return []


# Send a message to multiple clients
def send_multi_message(clients, message):
    with connect_to_server() as server_socket:
        if server_socket:
            command = {
                "action": "send_multi_message",
                "clients": clients,
                "message": message,
            }
            send_message(server_socket, json.dumps(command))
            response = receive_message(server_socket)
            return json.loads(response)
    return {}


# Get responses from clients
def get_responses():
    with connect_to_server() as server_socket:
        if server_socket:
            send_message(server_socket, json.dumps({"action": "get_responses"}))
            response = receive_message(server_socket)
            return json.loads(response)
    return []


# Shutdown the server
def shutdown_server():
    with connect_to_server() as server_socket:
        if server_socket:
            send_message(server_socket, json.dumps({"action": "shutdown_server"}))
            response = receive_message(server_socket)
            return json.loads(response)
    return {"status": "failed"}


# Main function for Streamlit application
def main():
    st.set_page_config(page_title="R-C Server", page_icon="🛠️")
    st.title("R-C Server")

    # Check password before continuing
    if not check_password():
        st.stop()

    # Initialize session state variables
    initialize_session_state()

    # Form for client filtering
    display_client_filter_form()

    # Display client list and handling message sending and responses
    handle_clients_display()

    # Shutdown server button
    st.divider()
    if st.button("Выключить сервер", type="primary"):
        handle_server_shutdown()

    # Sidebar for displaying commands
    display_sidebar_commands()


# Initialize session state variables
def initialize_session_state():
    session_defaults = {
        "responses": [],
        "bdk_clients": [],
        "clients": [],
        "chosen_clients": {},
        "client_pc_name": "",
        "client_type_option": "",
        "client_address_option": "",
        "visibility": "visible",
        "disabled": False
    }
    for key, value in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# Display client filtering form
def display_client_filter_form():
    with st.form(key="client_filter_form"):
        st.session_state.client_pc_name = st.text_input("Введите имя клиентского ПК:")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.session_state.client_type_option = st.selectbox(
                "Выберите тип клиента",
                [None] + get_unique_client_types(),
                label_visibility=st.session_state.visibility,
                disabled=st.session_state.disabled,
            )
        with col2:
            st.session_state.client_address_option = st.selectbox(
                "Выберите адрес клиента",
                [None] + get_unique_client_addresses(),
                label_visibility=st.session_state.visibility,
                disabled=st.session_state.disabled,
            )
        with col3:
            st.write("")  # Placeholder for button alignment
            submit_button = st.form_submit_button(label="Обновить список клиентов")

    if submit_button:
        update_clients_list()


# Update clients list based on the filter
def update_clients_list():
    st.session_state.clients = get_connected_clients()
    st.session_state.bdk_clients = search_client(
        st.session_state.client_pc_name,
        st.session_state.client_type_option,
        st.session_state.client_address_option
    ) if st.session_state.clients else []

    if not st.session_state.bdk_clients:
        st.warning("Онлайн клиенты не найдены")


# Display connected clients and handle sending messages and receiving responses
def handle_clients_display():
    if st.session_state.clients:
        clients_set = {c.split("(", 1)[0] for c in st.session_state.clients}
        clients_dict = {c.split("(", 1)[0]: c for c in st.session_state.clients}

        data = [
            {
                "status": "🌐" if client["client_pc_name"] in clients_set else "🔴",
                "client_pc_name": client["client_pc_name"],
                "original_name": clients_dict.get(client["client_pc_name"], client["client_pc_name"])
            }
            for client in st.session_state.bdk_clients
        ]

        chosen = {}
        for row in data:
            chosen[row['original_name']] = st.checkbox(
                f"{row['status']}-{row['original_name']}",
                key=row["original_name"],
                disabled=row["status"] == "🔴"
            )

        st.session_state.chosen_clients = chosen

    handle_message_sending()
    handle_client_responses()


# Handle message sending to selected clients
def handle_message_sending():
    if "chosen_clients" in st.session_state and st.session_state.chosen_clients:
        st.subheader("Отправка сообщения клиентам")
        selected_clients = [c for c, selected in st.session_state.chosen_clients.items() if selected]
        message_multi = st.text_input("Введите сообщение для отправки")
        if st.button("Отправить"):
            results = send_multi_message(selected_clients, message_multi)
            with st.expander("Результаты отправки сообщений"):
                for client, status in results.items():
                    if status == "success":
                        st.success(f"Сообщение отправлено клиенту {client}")
                    else:
                        st.error(f"Ошибка при отправке сообщения клиенту {client}")


# Handle receiving responses from clients
def handle_client_responses():
    st.subheader("Ответы от клиентов")
    if st.button("Получить ответы"):
        st.session_state.responses = get_responses()

    for client, response in st.session_state.responses:
        with st.expander(client):
            if response["type"] == "image":
                image_bytes = base64.b64decode(response["data"])
                st.image(image_bytes)
            else:
                st.write(response["data"])


# Handle server shutdown
def handle_server_shutdown():
    result = shutdown_server()
    if result["status"] == "shutting_down":
        st.success("Сервер успешно выключен")
    else:
        st.error("Ошибка при выключении сервера")


# Display commands in the sidebar
def display_sidebar_commands():
    st.sidebar.subheader("Команды")
    file_path = "dist/commands.csv"
    df = pd.read_csv(file_path, sep='$')
    edited_df = st.sidebar.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        height=500,
        column_config={
            "key": "Сокращение",
            "command": "Команда",
            "comment": "Комментарий",
        }
    )
    if st.sidebar.checkbox("Внесение изменений в список команд⚠️"):
        if st.sidebar.button('Сохранить изменения', icon="💾"):
            edited_df.to_csv(file_path, sep='$', index=False)
            st.sidebar.success("Изменения записаны!")

        if st.sidebar.button('Выгрузить на FTP', icon="↗️"):
            try:
                result = subprocess.run(["dist/upload.exe"], check=True, capture_output=True, text=True)
                st.sidebar.success(result.stdout)
            except subprocess.CalledProcessError as e:
                st.sidebar.error(e.stderr)


if __name__ == "__main__":
    main()

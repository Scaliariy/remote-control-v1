import os
import socket
import time
import datetime
import uuid
import requests
from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConfigurationError
import custom_logger
import toml

logger = custom_logger.logger("app.log")

secrets = toml.load(".secrets/secrets.toml")
MONGO_URI = secrets["database"]["uri"]
DB_NAME = 'BDK'
COLLECTION_NAME = 'clients'
UNIQUE_NAME_FILE = "unique_name.txt"


def connect_to_mongodb_collection(db_name, collection_name):
    while True:
        try:
            client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
            client.server_info()
            db = client[db_name]
            collection = db[collection_name]
            return collection
        except (AutoReconnect, ConfigurationError) as e:
            logger.error(f"Failed to connect to the database: {e}")
            logger.error("Retrying to establish a connection...")
            time.sleep(30)


def get_local_client_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except socket.error as e:
        logger.error(f"Error occurred while fetching the local IP address: {e}")
        return None


def get_external_ip():
    try:
        external_ip = requests.get('https://api.ipify.org').text
        return external_ip
    except requests.RequestException as e:
        logger.error(f"Error occurred while fetching the external IP address: {e}")
        return None


def get_mac_address():
    return ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2 * 6, 2)][::-1])


def save_client_data(client_pc_name, client_hostname, client_mac_address, client_external_ip,
                     client_local_ip, client_address, client_type, timestamp):
    clients_collection = connect_to_mongodb_collection(DB_NAME, COLLECTION_NAME)
    query = {"client_pc_name": client_pc_name}
    new_data = {
        "$set": {
            "client_local_ip": client_local_ip,
            "client_external_ip": client_external_ip,
            "client_mac_address": client_mac_address,
            "client_hostname": client_hostname,
            "client_type": client_type,
            "client_address": client_address,
            "timestamp": timestamp
        }
    }
    result = clients_collection.update_one(query, new_data, upsert=True)
    if result.matched_count == 1:
        logger.info(f"Successfully UPDATED the client data in the database with id {result.upserted_id}.")
    elif result.matched_count == 0:
        logger.info(f"Successfully INSERTED new client data in the database with id {result.upserted_id}.")
    else:
        logger.error("Failed to insert/update new client data in the database.")


def choose_value(collection, field, filter_field=None, filter_value=None):
    if filter_field:
        unique_values = collection.distinct(field, {filter_field: filter_value})
    else:
        unique_values = collection.distinct(field)
    unique_values.append("Add new")
    for index, value in enumerate(unique_values, start=1):
        print(f"{index}. {value}")
    index = int(input(f"Choose {field} number: "))
    chosen_value = unique_values[index - 1]
    if chosen_value == "Add new":
        return input(f"Enter a new '{field}': ")
    else:
        return chosen_value


def get_unique_name():
    try:
        if os.path.exists(UNIQUE_NAME_FILE):
            with open(UNIQUE_NAME_FILE, 'r') as file:
                unique_name = file.read().strip()
                unique_name = unique_name.split(',')[0].strip('[]')
            return unique_name
        else:
            raise FileNotFoundError(f"File {UNIQUE_NAME_FILE} not found.")
    except FileNotFoundError as e:
        logger.error(e)
        return None


def update_client_data():
    client_pc_name = get_unique_name()
    if client_pc_name:
        clients_collection = connect_to_mongodb_collection(DB_NAME, COLLECTION_NAME)
        timestamp = datetime.datetime.now()
        client_local_ip = get_local_client_ip()
        client_external_ip = get_external_ip()
        client_mac_address = get_mac_address()
        client_hostname = socket.gethostname()
        client_data = clients_collection.find_one({"client_pc_name": client_pc_name})
        if client_data:
            save_client_data(client_pc_name, client_hostname, client_mac_address, client_external_ip,
                             client_local_ip, client_data.get('client_address'),
                             client_data.get('client_type'),
                             timestamp)
        else:
            logger.error(f"No client found in the database with name {client_pc_name}")
    else:
        logger.error(f"Failed to get unique name from file.")


def create_or_update_client():
    clients_collection = connect_to_mongodb_collection(DB_NAME, COLLECTION_NAME)
    timestamp = datetime.datetime.now()
    client_local_ip = get_local_client_ip()
    client_external_ip = get_external_ip()
    client_mac_address = get_mac_address()
    client_hostname = socket.gethostname()
    if not os.path.exists(UNIQUE_NAME_FILE):
        while True:
            print("\n\t*** CLIENT ADDING FORM ***\n")
            client_type = choose_value(clients_collection, 'client_type')
            print('\n')
            client_address = choose_value(clients_collection, 'client_address', 'client_type', client_type)
            print('\n')
            unique_name = input("Enter short unique name for the computer (e.g.: Kassa 1, PC 1): ")
            unique_name = f"{unique_name.upper()}-{client_address}-{client_type}-{client_mac_address}"
            print(f"\n{unique_name}")
            confirmation = input("Save this name? (Y/N): ")
            print('\n')
            if confirmation.lower() == "y":
                if clients_collection.find_one({"client_pc_name": unique_name}) is None:
                    break
                else:
                    print("The name already exists in the database. Please choose a different name.")
                    answer = input("Create with this name? (Y/N)")
                    if answer.lower() == 'y':
                        break
            else:
                continue
        with open(UNIQUE_NAME_FILE, 'w') as file:
            file.write(f"[{unique_name}],")
        client_pc_name = get_unique_name()
        save_client_data(client_pc_name, client_hostname, client_mac_address, client_external_ip,
                         client_local_ip, client_address, client_type, timestamp)
    else:
        update_client_data()


def search_client(client_pc_name, client_type, client_address):
    """Searches for clients in the MongoDB database by PC name, type, and address."""
    clients_collection = connect_to_mongodb_collection(DB_NAME, COLLECTION_NAME)

    query = {"client_pc_name": {"$regex": client_pc_name, "$options": "i"}}

    if client_type:
        query["client_type"] = client_type

    if client_address:
        query["client_address"] = client_address

    result = clients_collection.find(query)

    clients = [
        {
            "client_pc_name": client["client_pc_name"],
            "client_local_ip": client["client_local_ip"],
        }
        for client in result
    ]
    return clients


def get_host():
    host_collection = connect_to_mongodb_collection(DB_NAME, "host")
    host_doc = host_collection.find_one()
    if host_doc:
        host = host_doc.get('host')
        port_server = int(host_doc.get('port_server'))
        port_streamlit = int(host_doc.get('port_streamlit'))
    else:
        host = None
        port_server = None
        port_streamlit = None

    return host, port_server, port_streamlit


def get_unique_client_types():
    clients_collection = connect_to_mongodb_collection(DB_NAME, COLLECTION_NAME)
    return clients_collection.distinct("client_type")


def get_unique_client_addresses():
    clients_collection = connect_to_mongodb_collection(DB_NAME, COLLECTION_NAME)
    return clients_collection.distinct("client_address")


if __name__ == "__main__":
    create_or_update_client()

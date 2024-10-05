from ftplib import FTP
import os
import sys
import toml


def connect_ftp(server, username, password):
    ftp = FTP(server)
    ftp.login(username, password)
    return ftp


def upload_files(ftp, local_dir, files_to_upload, remote_dir):
    try:
        if remote_dir:
            ftp.cwd(remote_dir)

        for file_name in files_to_upload:
            local_file_path = os.path.join(local_dir, file_name)
            if os.path.isfile(local_file_path):
                with open(local_file_path, 'rb') as local_file:
                    ftp.storbinary(f"STOR {file_name}", local_file)
                print(f"Файл {file_name} загружен на сервер в {remote_dir}")
            else:
                print(f"Файл {file_name} не найден в {local_file_path}")
    except Exception as e:
        print(f"Ошибка при загрузке файлов: {e}")
        sys.exit(1)


def main():
    secrets = toml.load(".secrets/secrets.toml")
    server = secrets["ftp"]["server"]
    username = secrets["ftp"]["username"]
    password = secrets["ftp"]["password"]
    remote_dir = '/R_C_Updates/'
    local_dir = 'dist'
    files_to_upload = ['client.exe', 'commands.csv', 'bdk.exe']

    ftp = connect_ftp(server, username, password)

    upload_files(ftp, local_dir, files_to_upload, remote_dir)

    ftp.quit()


if __name__ == "__main__":
    main()

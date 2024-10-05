from datetime import date, datetime, timedelta

today = date.today()
cleaning_date = today - timedelta(days=7)

try:
    with open("app.log", "r") as fr:
        lines = fr.readlines()

        with open("app.log", "w") as fw:
            for line in lines:
                try:
                    line_date = datetime.strptime(line[:10], '%Y-%m-%d').date()
                    if line_date > cleaning_date:
                        fw.write(line)
                except ValueError:
                    print(f"Warning: Invalid date format in string: {line.strip()}")
except FileNotFoundError:
    print("Error: File 'app.log' not found.")
except PermissionError:
    print("Error: Insufficient rights to access the file 'app.log'.")
except OSError as e:
    print(f"Error: Error while working with file: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")

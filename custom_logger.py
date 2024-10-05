import time


class CustomLogger:
    def __init__(self, filename):
        self.filename = filename
        self.last_message = None

    def log(self, level, message):
        if message != self.last_message:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {level} {message}\n")
            self.last_message = message

    def info(self, message):
        self.log("INFO", message)

    def error(self, message):
        self.log("ERROR", message)

    def warning(self, message):
        self.log("WARNING", message)


def logger(filename):
    return CustomLogger(filename)

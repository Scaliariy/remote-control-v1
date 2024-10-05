import tkinter as tk
import threading


def show_message_threaded(message):
    def run_tk():
        root = tk.Tk()
        root.title("Администратор")

        # Размеры окна
        window_width = 400
        window_height = 200

        # Размеры экрана
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        # Координаты для центрирования окна
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)

        # Установка размера и положения окна
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        root.attributes("-topmost", True)

        message_label = tk.Label(root, text=message, font=("Arial", 16, "bold"), padx=20, pady=20,
                                 wraplength=350)  # wraplength для переноса строки
        message_label.pack(fill='both', expand=True)

        close_button = tk.Button(root, text="Закрыть", command=root.quit, padx=10, pady=5)
        close_button.pack(pady=10)  # добавляем отступ

        root.mainloop()

    thread = threading.Thread(target=run_tk)
    thread.start()


if __name__ == '__main__':
    show_message_threaded("Это ваше сообщение!")

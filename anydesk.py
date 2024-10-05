import subprocess
import pyautogui
import time

SCREENSHOT_PATH = "anydesk_screenshot.png"


def full_screenshot():
    screenshot_path = SCREENSHOT_PATH
    screenshot = pyautogui.screenshot()
    screenshot.save(screenshot_path)


def anydesk_screenshot():
    anydesk_path = "C:\\Program Files (x86)\\AnyDesk\\AnyDesk.exe"
    subprocess.Popen([anydesk_path])
    time.sleep(5)
    full_screenshot()


def get_screenshot():
    screenshot_path = SCREENSHOT_PATH
    with open(screenshot_path, 'rb') as f:
        byte_image = f.read()
    return byte_image


if __name__ == '__main__':
    anydesk_screenshot()
    print(get_screenshot())

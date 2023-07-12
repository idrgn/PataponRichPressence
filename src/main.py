import ctypes
import time

import win32gui
import win32process
from pypresence import Presence

from const import BASE, class_names, game_state_messages, overlay_files
from data import read_str, read_str_short, read_uint


def find_window(partial_title):
    window_handle = None
    window_titles = []

    def enum_windows_callback(handle, _):
        title = win32gui.GetWindowText(handle)
        if partial_title.lower() in title.lower():
            window_titles.append(title)
            nonlocal window_handle
            window_handle = handle

    win32gui.EnumWindows(enum_windows_callback, None)

    return window_handle, window_titles


def get_process_data():
    window_handle, window_titles = find_window("PPSSPP")

    if window_handle is not None:
        lower = win32gui.SendMessage(window_handle, 0xB118, 0, 2)
        upper = win32gui.SendMessage(window_handle, 0xB118, 0, 3)
        return (upper * 0x100000000) + lower, win32process.GetWindowThreadProcessId(
            window_handle
        )[1]


def get_game_data():
    print("# Updating data")
    base_address, window_pid = get_process_data()

    if base_address != 0x0:
        OpenProcess = ctypes.windll.kernel32.OpenProcess
        ReadProcessMemory = ctypes.windll.kernel32.ReadProcessMemory
        processHandle = OpenProcess(0x10, False, window_pid)

        # Get base address of the game
        data = ctypes.c_uint32()
        bytes_read = ctypes.c_uint32()
        result = ReadProcessMemory(
            processHandle,
            base_address,
            ctypes.byref(data),
            ctypes.sizeof(data),
            ctypes.byref(bytes_read),
        )

        if result == 0:
            return

        game_memory_pointer = data.value

        # Get game memory
        buf_len = 0x1800000
        buf = ctypes.create_string_buffer(buf_len)
        read = ctypes.c_size_t()

        result = ReadProcessMemory(
            processHandle,
            game_memory_pointer + 0x8800000,
            buf,
            buf_len,
            ctypes.byref(read),
        )

        if result == 0:
            return

        data = bytearray(buf)

        # Pointer to save pointer location
        base_data_pointer = read_uint(data, 0x2ABD94)
        print(f" - Base data pointer: {hex(base_data_pointer)}")
        if base_data_pointer == 0x0:
            return

        game_data = {}

        # Pointer to savedata start
        save_pointer = read_uint(data, base_data_pointer - BASE + 0x50)
        print(f" - Save pointer: {hex(save_pointer)}")

        # Pointer to multiplayer start
        multi_pointer = read_uint(data, base_data_pointer - BASE + 0x78)
        print(f" - Multi pointer: {hex(multi_pointer)}")

        if save_pointer != 0x00:
            # Get current class
            current_class = read_uint(data, save_pointer - BASE + 0x9520)
            game_data["current_class"] = class_names[current_class]
            print(f" - Current class: {class_names[current_class]}")

        if multi_pointer != 0x0:
            # Get quest name
            quest_name = read_str_short(data, multi_pointer - BASE + 0x9FC + 0x100)
            game_data["current_quest"] = quest_name
            print(f" - Current quest: {quest_name}")

        # Get current overlay file
        overlay_file = read_str(data, 0x08ABB1A0 - BASE)
        print(f" - Overlay_file: {overlay_file}")
        game_data["overlay_file"] = overlay_file

    return game_data


def process_game_data(game_data):
    overlay = game_data["overlay_file"]

    if overlay == overlay_files["none"] or overlay == overlay_files["title"]:
        detail = "In title"
        state = None
    elif overlay == overlay_files["azito"]:
        detail = f"Class: {game_data['current_class']}"
        state = f"{game_state_messages[overlay]}"
    elif overlay == overlay_files["mission"]:
        detail = f"Class: {game_data['current_class']}"
        state = f"{game_state_messages[overlay]}: {game_data['current_quest']}"

    return detail, state


if __name__ == "__main__":
    game_data = get_game_data()
    client_id = "1128592742314938458"
    RPC = Presence(client_id)
    RPC.connect()

    detail, state = process_game_data(game_data)

    while True:
        RPC.update(
            details=detail,
            state=state,
        )

        time.sleep(15)

        game_data = get_game_data()

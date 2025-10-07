from customtkinter import *
from socket import *
import base64
import io
import os
import sys
from PIL import Image, ImageDraw
import threading

# установить рабочую директорию в папку, где лежит client.py
os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))


def make_round_image(path, size=(40, 40), bg_color=None):
    """Возвращает CTkImage с круглой маской."""
    pil = Image.open(path).resize(size, Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    pil.putalpha(mask)

    if bg_color:
        background = Image.new("RGBA", size, bg_color)
        background.paste(pil, (0, 0), mask=mask)
        pil = background

    return CTkImage(light_image=pil, size=size)


def change_avatar(main_window, current_avatar_label):
    window_avatar = CTkToplevel(main_window)
    window_avatar.title("Вибір аватара")
    window_avatar.resizable(False, False)
    window_avatar.geometry(f"300x300")

    avatars_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatars")
    if not os.path.isdir(avatars_dir):
        CTkLabel(window_avatar, text="⚠️ Немає папки 'avatars/'").pack(pady=50)
        return

    avatar_files = [f for f in os.listdir(avatars_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]

    if not avatar_files:
        CTkLabel(window_avatar, text="⚠️ Немає аватарів у папці 'avatars/'").pack(pady=50)
        return

    frame = CTkFrame(window_avatar)
    frame.pack(padx=10, pady=10, fill="both", expand=True)

    def select_avatar(path):
        # сохраняем локально выбранный аватар
        main_window.avatar_path = path
        img = CTkImage(light_image=Image.open(path), size=(50, 50))
        current_avatar_label.configure(image=img)
        current_avatar_label.image = img

        # ⚠️ НЕ отправляем на сервер!
        window_avatar.destroy()

    row, col = 0, 0
    for file in avatar_files:
        path = os.path.join(avatars_dir, file)
        try:
            img = CTkImage(light_image=Image.open(path), size=(70, 70))
        except Exception:
            # если файл битый — пропускаем
            continue
        btn = CTkButton(frame, image=img, text="", width=70, height=70,
                        fg_color="transparent", hover_color="#2b2b2b",
                        command=lambda p=path: select_avatar(p))
        btn.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        if col > 2:   # максимум 3 в ряд
            col = 0
            row += 1


class MainWindow(CTk):
    def __init__(self):
        super().__init__()
        self.geometry('500x400')
        self.label = None
        self.username = ""
        self.avatar_path = "images.jpg"
        self.avatars_by_user = {}

        # menu frame
        self.menu_frame = CTkFrame(self, height=300, width=40)
        self.menu_frame.pack_propagate(False)
        self.menu_frame.place(x=0, y=0)

        self.is_show_menu = False
        self.speed_animate_menu = -5

        self.btn = CTkButton(self, text="⚙️", width=30, command=self.menu)
        self.btn.place(x=0, y=0)

        self.open_img_button = CTkButton(self, text="*", width=50, height=40, command=self.open_file)
        self.open_img_button.place(x=0, y=0)

        self.chat_field = CTkScrollableFrame(self)
        self.chat_field.place(x=0, y=0)
        self.message_frame = self.chat_field

        self.message_entry = CTkEntry(self, placeholder_text="Введіть повідомлення", height=40)
        self.message_entry.place(x=0, y=0)

        self.send_button = CTkButton(self, text=">", width=50, height=40, command=self.send_message)
        self.send_button.place(x=0, y=0)

        # аватарка и кнопка смены аватара
        self.avatar_label = CTkLabel(self, text="")
        self.avatar_label.pack(pady=10)
        self.change_avatar_button = CTkButton(
            self, text="Змінити аватар",
            command=lambda: change_avatar(self, self.avatar_label)
        )
        # пока не отображаем change_avatar_button; пользователь может открыть через меню

        # профильный аватар (используется в update_profile_avatar)
        self.profile_avatar_label = self.avatar_label

        # попытка подключиться к серверу
        try:
            self.sock = socket(AF_INET, SOCK_STREAM)
            self.sock.connect(("localhost", 8080))
            hello = f"TEXT@{self.username}@приєднався до чату\n"
            self.sock.send(hello.encode('utf-8'))
            threading.Thread(target=self.recv_message, daemon=True).start()
        except Exception:
            # если не получилось — ставим sock = None и выводим сообщение
            self.sock = None
            self.add_message("Не вдалося підключитися до сервера")

        # предварительная загрузка иконок сердечек (чтобы не открывать файлы каждый раз)
        self.heart_white_img = None
        self.heart_purple_img = None
        try:
            self.heart_white_img = CTkImage(light_image=Image.open("heart_white.png"), size=(20, 20))
            self.heart_purple_img = CTkImage(light_image=Image.open("heart_purple.png"), size=(20, 20))
        except Exception:
            # если нет файлов — создаём пустые заглушки
            self.heart_white_img = None
            self.heart_purple_img = None

        # запускаем адаптивный layout
        self.adaptive_tiger()

    def menu(self):
        # переключаем состояние меню
        self.is_show_menu = not self.is_show_menu
        self.speed_animate_menu *= -1
        self.btn.configure(text="⚙️")
        # удаляем старые виджеты меню (если есть) перед созданием новых
        for w in self.menu_frame.winfo_children():
            w.destroy()

        if self.is_show_menu:
            # открыть меню: показываем поля редактирования
            self.label = CTkLabel(self.menu_frame, text="Редагувати ім'я")
            self.label.pack(pady=10)

            self.entry = CTkEntry(self.menu_frame)
            self.entry.pack(padx=10)

            self.save_btn = CTkButton(self.menu_frame, text="Зберегти", command=self.save_username)
            self.save_btn.pack(pady=10)

            self.button_avatar = CTkButton(
                self.menu_frame, text="Редагувати аватар",
                command=lambda: change_avatar(self, self.avatar_label)
            )
            self.button_avatar.pack(pady=10)
        else:
            # меню скрываем — ничего дополнительного
            pass

        # запускаем анимацию изменения ширины
        self.show_menu()

    def save_username(self):
        self.new_name = self.entry.get().strip()
        if self.new_name:
            self.username = self.new_name
            self.add_message(f"Ваше ім’я змінено на: {self.username}", author=self.username, is_self=True)

    def show_menu(self):
        # простая анимация изменения ширины меню
        current_w = self.menu_frame.winfo_width()
        target_open = 200
        target_closed = 40

        # двигаем в сторону цели
        if self.is_show_menu and current_w < target_open:
            self.menu_frame.configure(width=min(target_open, current_w + abs(self.speed_animate_menu)))
            self.after(10, self.show_menu)
        elif (not self.is_show_menu) and current_w > target_closed:
            self.menu_frame.configure(width=max(target_closed, current_w - abs(self.speed_animate_menu)))
            self.after(10, self.show_menu)

    def add_message(self, message, author, is_me=False):
        row_frame = CTkFrame(self.message_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)

        if not is_me:  # 👈 только у чужих сообщений аватарка
            avatar_path = self.avatars_by_user.get(author, self.avatar_path)

            if avatar_path and os.path.isfile(avatar_path):
                try:
                    avatar = make_round_image(avatar_path, size=(40, 40))
                except Exception:
                    avatar = None
            else:
                avatar = None

            if avatar:
                avatar_frame = CTkFrame(row_frame, fg_color="transparent")
                avatar_frame.pack(side="left", padx=5)
                avatar_label = CTkLabel(avatar_frame, image=avatar, text="", fg_color="transparent")
                avatar_label.image = avatar
                avatar_label.pack()

        # текст сообщения
        msg_label = CTkLabel(
            row_frame,
            text=message,
            anchor="w" if not is_me else "e",
            fg_color="#2b2b2b" if not is_me else "#1f6aa5",
            text_color="white",
            padx=10,
            pady=5,
            corner_radius=10,
        )
        msg_label.pack(side="left" if not is_me else "right", padx=5)

        # контейнер для текста/изображения сообщения
        message_frame = CTkFrame(row_frame, fg_color="#f0f0f0", corner_radius=8)
        message_frame.pack(side="left" if not is_me else "right", padx=5, pady=2)

        wraplength_size = max(100, self.winfo_width() - 250)

        if author and not is_me:
            CTkLabel(
                message_frame, text=author, text_color="#6a5acd",
                font=("Arial", 12, "bold"), anchor="w", justify="left"
            ).pack(padx=10, pady=(5, 0), anchor="w")

        if img:
            CTkLabel(
                message_frame, text=message, image=img, compound="top",
                text_color="black", justify="left", wraplength=wraplength_size
            ).pack(padx=10, pady=(0, 5), anchor="w")
        else:
            CTkLabel(
                message_frame, text=message, text_color="black",
                justify="left", wraplength=wraplength_size
            ).pack(padx=10, pady=(0, 5), anchor="w")

        # ❤️ лайк
        like_frame = CTkFrame(row_frame, fg_color="transparent")
        like_frame.pack(side="right" if is_me else "left", padx=5)

        # используем заранее загруженные иконки, если есть
        heart_white_img = self.heart_white_img
        heart_purple_img = self.heart_purple_img

        # если иконок нет — создаём простую метку
        if heart_white_img is None:
            heart_label = CTkLabel(like_frame, text="♡", fg_color="transparent", cursor="hand2")
        else:
            heart_label = CTkLabel(like_frame, image=heart_white_img, text="", fg_color="transparent", cursor="hand2")
            heart_label.image = heart_white_img

        heart_label.pack()
        heart_label.liked = False

        def toggle_heart(event=None, from_server=False):
            heart_label.liked = not heart_label.liked
            if heart_white_img and heart_purple_img:
                heart_label.configure(image=(heart_purple_img if heart_label.liked else heart_white_img))
                heart_label.image = (heart_purple_img if heart_label.liked else heart_white_img)
            else:
                heart_label.configure(text="❤" if heart_label.liked else "♡")

            if not from_server and self.sock:
                try:
                    data = f"LIKE@{author}@{message}\n"
                    self.sock.sendall(data.encode())
                except:
                    pass

        # связываем клик
        heart_label.bind("<Button-1>", lambda e: toggle_heart())

        # сохраняем для возможного обновления лайков с сервера
        if not hasattr(self, "messages"):
            self.messages = []
        self.messages.append({"author": author, "message": message, "heart": heart_label, "toggle": toggle_heart})

    def update_profile_avatar(self):
        avatar_path = self.avatars_by_user.get(self.username, self.avatar_path)
        if not os.path.isfile(avatar_path):
            avatar_path = self.avatar_path if os.path.isfile(self.avatar_path) else None
        if avatar_path:
            avatar = make_round_image(avatar_path, size=(60, 60))
            self.profile_avatar_label.configure(image=avatar)
            self.profile_avatar_label.image = avatar

    def send_message(self):
        message = self.message_entry.get().strip()
        if message:
            self.add_message(message, author=self.username)
            data = f"TEXT@{self.username}@{message}\n"
            try:
                if self.sock:
                    self.sock.sendall(data.encode())
            except:
                pass
            self.message_entry.delete(0, len(self.message_entry.get()))

    def recv_message(self):
        buffer = ""
        while True:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode('utf-8', errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self.handle_line(line.strip())
            except:
                break
        if getattr(self, "sock", None):
            try:
                self.sock.close()
            except:
                pass
        self.sock = None

    def open_file(self):
        file_name = filedialog.askopenfilename()
        if not file_name:
            return
        try:
            with open(file_name, "rb") as f:
                raw = f.read()
            b64_data = base64.b64encode(raw).decode()
            short_name = os.path.basename(file_name)
            data = f"IMAGE@{self.username}@{short_name}@{b64_data}\n"
            if self.sock:
                self.sock.sendall(data.encode())
            ctk_img = CTkImage(light_image=Image.open(file_name), size=(150, 150))
            self.add_message("", img=ctk_img, author=self.username)
        except Exception as e:
            self.add_message(f"Не вдалося надіслати зображення: {e}")

    def adaptive_tiger(self):
        # Подгоняем размеры элементов под окно
        try:
            self.menu_frame.configure(height=self.winfo_height())
            self.chat_field.place(x=self.menu_frame.winfo_width())
            self.chat_field.configure(width=max(100, self.winfo_width() - self.menu_frame.winfo_width() - 20),
                                      height=max(100, self.winfo_height() - self.message_entry.winfo_height() - self.btn.winfo_height()))
            self.send_button.place(x=max(0, self.winfo_width() - self.send_button.winfo_width()),
                                   y=max(0, self.winfo_height() - self.send_button.winfo_height()))
            self.message_entry.place(x=self.menu_frame.winfo_width(),
                                     y=max(0, self.winfo_height() - self.message_entry.winfo_height()))
            self.message_entry.configure(width=max(100, self.winfo_width() - self.menu_frame.winfo_width() - 110))
            self.open_img_button.place(x=max(0, self.winfo_width() - 105), y=self.send_button.winfo_y())
        except Exception:
            pass
        self.after(50, self.adaptive_tiger)

    def handle_line(self, line):
        if not line:
            return
        parts = line.split("@", 3)
        msg_type = parts[0]

        if msg_type == "TEXT":
            if len(parts) >= 3:
                author = parts[1]
                message = parts[2]
                self.add_message(message, author=author)

        elif msg_type == "IMAGE":
            if len(parts) >= 4:
                author = parts[1]
                filename = parts[2]
                b64_img = parts[3]
                try:
                    img_data = base64.b64decode(b64_img)
                    pil_img = Image.open(io.BytesIO(img_data))
                    ctk_img = CTkImage(light_image=pil_img, size=(150, 150))
                    self.add_message("", img=ctk_img, author=author)
                except Exception as e:
                    self.add_message(f"Помилка зображення: {e}")

        elif msg_type == "LIKE":
            if len(parts) >= 3:
                author = parts[1]
                message = parts[2]
                for msg in getattr(self, "messages", []):
                    if msg["author"] == author and msg["message"] == message:
                        # отметка лайка от сервера — не шлём обратно
                        msg["toggle"](from_server=True)
                        break
        else:
            self.add_message(line)


if __name__ == "__main__":
    global main_window
    main_window = MainWindow()
    main_window.mainloop()

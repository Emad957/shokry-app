import os
import platform
import shutil
import socket
import threading
import flet as ft
import yt_dlp

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 2080
PROXY_URL = f"http://{PROXY_HOST}:{PROXY_PORT}"
PROXY_URL_ARIA2C = f"http://{PROXY_HOST}:{PROXY_PORT}"

IS_MOBILE = platform.system() == "Linux" and os.path.exists("/data/data")


def is_proxy_running(host=PROXY_HOST, port=PROXY_PORT):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def is_aria2c_installed():
    return shutil.which("aria2c") is not None


def is_ffmpeg_installed():
    return shutil.which("ffmpeg") is not None


def get_default_download_dir():
    if IS_MOBILE:
        for path in ["/storage/emulated/0/Download", "/sdcard/Download"]:
            if os.path.isdir(path):
                return path
    return os.path.join(os.path.expanduser("~"), "Downloads")


def main(page: ft.Page):
    page.title = "البرنامج دة اتعمل علشان اسب لشكري"
    page.theme_mode = ft.ThemeMode.DARK
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.padding = 20

    if not IS_MOBILE:
        page.window.width = 420
        page.window.height = 350
        page.window.resizable = False

    default_download_dir = get_default_download_dir()
    selected_path = {"dir": default_download_dir}

    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    url_input = ft.TextField(
        label="رابط الفيديو",
        hint_text="https://youtu.be/...",
        prefix_icon=ft.Icons.LINK,
        border_radius=10,
        autofocus=not IS_MOBILE,
        expand=True,
        text_size=16,
    )

    path_text = ft.Text(
        selected_path["dir"],
        size=11,
        color=ft.Colors.GREY_400,
        overflow=ft.TextOverflow.ELLIPSIS,
        text_align=ft.TextAlign.CENTER,
    )

    progress_bar = ft.ProgressBar(value=0, visible=False, color=ft.Colors.BLUE_400)
    info_text = ft.Text("", size=13, text_align=ft.TextAlign.CENTER)

    def on_folder_picked(e: ft.FilePickerResultEvent):
        if e.path:
            selected_path["dir"] = e.path
            path_text.value = e.path
            info_text.value = f"تم تحديد: {e.path}"
            info_text.color = ft.Colors.GREEN_400
            page.update()

    file_picker.on_result = on_folder_picked

    def pick_folder_dialog(e):
        file_picker.get_directory_path(
            dialog_title="اختر مجلد الحفظ",
            initial_directory=selected_path["dir"],
        )

    locate_btn = ft.Button(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=18),
                ft.Text("Locate", size=14, weight=ft.FontWeight.BOLD),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=6,
        ),
        on_click=pick_folder_dialog,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_700,
            color=ft.Colors.WHITE,
            padding=12,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        expand=True,
    )

    download_btn = ft.Button(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED),
                ft.Text("تحميل", size=15, weight=ft.FontWeight.BOLD),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE,
            padding=15,
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        expand=True,
    )

    def update_progress(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                percent = downloaded / total
                progress_bar.value = percent
                speed = d.get("_speed_str", "N/A")
                info_text.value = f"السرعة: {speed} | مكتمل: {percent * 100:.1f}%"
            else:
                progress_bar.value = None
                info_text.value = "جاري التحميل..."
            page.update()
        elif d["status"] == "finished":
            progress_bar.value = 1.0
            info_text.value = "تم التحميل بنجاح!"
            info_text.color = ft.Colors.GREEN_400
            download_btn.disabled = False
            page.update()

    def build_ydl_opts(save_template: str) -> dict:
        proxy_on = is_proxy_running()
        ffmpeg = is_ffmpeg_installed()
        aria2c = is_aria2c_installed()

        ydl_opts = {
            "format": (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
                if ffmpeg
                else "best[ext=mp4]/best"
            ),
            "progress_hooks": [update_progress],
            "noplaylist": True,
            "outtmpl": save_template,
            "nocheckcertificate": True,
            "socket_timeout": 30,
            "retries": 15,
            "fragment_retries": 15,
            "extractor_retries": 20,
            "file_access_retries": 5,
            "retry_sleep_functions": {
                "http": lambda n: min(4 * (2**n), 60),
                "fragment": lambda n: min(3 * (2**n), 30),
                "extractor": lambda n: min(3 * (2**n), 45),
            },
            "http_headers": {
                "User-Agent": "com.google.android.youtube/19.29.37 (Linux; U; Android 14) gzip",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "extractor_args": {
                "youtube": {
                    "player_client": ["tv", "web", "android"],
                    "player_skip": ["webpage"],
                }
            },
            "geo_bypass": True,
        }

        if ffmpeg:
            ydl_opts["merge_output_format"] = "mp4"

        if proxy_on:
            ydl_opts["proxy"] = PROXY_URL

        if aria2c:
            aria2_args = [
                "--min-split-size=1M",
                "--max-connection-per-server=16",
                "--split=32",
                "--max-concurrent-downloads=1",
                "--max-tries=10",
                "--retry-wait=2",
                "--file-allocation=none",
                "--summary-interval=1",
                "--console-log-level=warn",
                "--disk-cache=64M",
                "--enable-http-pipelining=true",
            ]
            if proxy_on:
                aria2_args.append(f"--all-proxy={PROXY_URL_ARIA2C}")
            ydl_opts["external_downloader"] = "aria2c"
            ydl_opts["external_downloader_args"] = {"aria2c": aria2_args}
        else:
            ydl_opts["concurrent_fragment_downloads"] = 4

        return ydl_opts

    def run_download(e):
        url = url_input.value.strip()
        if not url:
            info_text.value = "يرجى إدخال الرابط أولاً"
            info_text.color = ft.Colors.RED_400
            page.update()
            return

        if not url.startswith(("http://", "https://")):
            info_text.value = "يرجى إدخال رابط صحيح"
            info_text.color = ft.Colors.RED_400
            page.update()
            return

        download_btn.disabled = True
        progress_bar.visible = True
        progress_bar.value = None
        info_text.value = "جاري التحميل..."
        info_text.color = ft.Colors.WHITE
        page.update()

        def task():
            save_template = os.path.join(selected_path["dir"], "%(title)s.%(ext)s")
            ydl_opts = build_ydl_opts(save_template)
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                progress_bar.visible = False
                download_btn.disabled = False
                page.update()
            except Exception as err:
                progress_bar.visible = False
                info_text.value = f"فشل: {str(err)[:120]}"
                info_text.color = ft.Colors.RED_400
                download_btn.disabled = False
                page.update()

        threading.Thread(target=task, daemon=True).start()

    download_btn.on_click = run_download

    page.add(
        ft.Column(
            [
                url_input,
                ft.Row([locate_btn, download_btn], spacing=10),
                path_text,
                progress_bar,
                info_text,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.run(main)

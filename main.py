import datetime
import math
import os
import pickle
import pprint
import re
import shutil
import threading
import time
import tomllib
import zipfile
from collections import deque
from itertools import count
from logging import DEBUG, FileHandler, Formatter, getLogger

import webp
from discord_webhook import DiscordWebhook
from PIL import Image, UnidentifiedImageError
from pixivpy3 import AppPixivAPI
from pixivpy3.utils import PixivError
from plyer import notification as notice
from pystyle import *
from requests.exceptions import ChunkedEncodingError
from rich.console import Console
from tomli_w import dump
from tqdm import tqdm
from urllib3.exceptions import ProtocolError


class Client:
    def __init__(self, refresh_token):
        self.aapi = AppPixivAPI()
        self.refresh_token = refresh_token
        self.access_token_get, self.expires_in = self.login()
        self.queue = deque()
        self.users = 0
        self.ugoira = None
        self.page = count()

    def login(self):
        try:
            auth_data = self.aapi.auth(refresh_token=self.refresh_token)
        except PixivError as e:
            logger.error(f"{type(e)}: {str(e)}")
            if "RemoteDisconnected" in str(e):
                print_("[!] Authentication error!: RemoteDisconnected.")
            elif "refresh_token is set" in str(e):
                print_("[!] Authentication error!: refresh token is nothing.")
                exit()
            elif "check refresh_token" in str(e):
                print_("[!] Authentication error!: Invalid refresh token.")
                exit()
            else:
                print_("[!] Authentication error!")
        except Exception as e:
            logger.error(f"{type(e)}: {str(e)}")
            exit()
        else:
            print_("[*] Login successfully!")
            logger.debug(auth_data)
            return time.time(), auth_data["expires_in"]

    def expires_check(self):
        elapsed_time = time.time() - self.access_token_get
        if elapsed_time >= self.expires_in:
            print_("[!] Expires in access token!")
            auth_data = self.aapi.auth(refresh_token=self.refresh_token)
            logger.debug(auth_data)
            self.access_token_get, self.expires_in = self.login()

    def download(self):
        def convert_size(size):
            units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB")
            i = math.floor(math.log(size, 1024)) if size > 0 else 0
            size = round(size / 1024 ** i, 2)

            return f"{size} {units[i]}"

        def ugoira2gif(ugoira_zip, path, id, delays):
            output = os.path.join(path, f"{id}_p0 ugoira.{settings['ugoira2gif']['format']}")
            ctime = os.path.getctime(ugoira_zip)
            images = list()
            try:
                with zipfile.ZipFile(ugoira_zip) as zf:
                    files = zf.namelist()
                    ugoira_path = str(os.path.join(settings["directory"], "ugoira", str(id)))
                    zf.extractall(ugoira_path)
                    delays_set = list(set(delays))
                    gcd = math.gcd(*delays_set)
            except zipfile.BadZipFile as e:
                logger.error(f"{type(e)}: {str(e)}")
            else:
                for delay, file in zip(delays, files):
                    image = Image.open(os.path.join(ugoira_path, file))
                    if image.mode != "RGB":
                        image = image.convert("RGB")
                    for _ in range(math.floor(delay / gcd)):
                        images.append(image)
                else:
                    if os.path.splitext(output)[1] == ".gif":
                        try:
                            images[0].save(
                                output,
                                save_all=True,
                                append_images=images[1:],
                                optimize=False,
                                duration=gcd,
                                loop=0,
                            )
                        except AttributeError as e:
                            logger.error(f"{type(e)}: {str(e)}")
                    elif os.path.splitext(output)[1] == ".webp":
                        webp.save_images(images, output, fps=(1000 / gcd))
                    os.utime(output, times=(ctime, ctime))
                    shutil.rmtree(ugoira_path)
                    logger.debug(f"ugoira2gif: {ugoira_zip} -> {output}")
            os.remove(ugoira_zip)
            return output

        if qsize := len(self.queue):
            files_num = 0
            files_size = 0
            print_("[*] Download started.")
            notification("Download stared.")
            start = time.time()
            if qsize != 1:
                qbar = tqdm(total=qsize, desc="Queue", leave=False)
            for i in range(qsize):
                data = self.queue.popleft()
                path = str(os.path.join(settings["directory"], data["folder"]))
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                post_id = data["id"]
                attachments = data["attachments"]
                for attachment in tqdm(attachments, desc="Attachments", leave=False):
                    file = os.path.join(path, os.path.basename(attachment))
                    if os.path.exists(file) or os.path.join(path, f"{id}_p0 ugoira.{settings['ugoira2gif']['format']}"):
                        continue
                    while True:
                        try:
                            self.aapi.download(attachment, path=path)
                            if data["type"] == "ugoira" and settings["ugoira2gif"]["enable"]:
                                # threading.Thread(target=ugoira2gif, args=(file, path, data["id"], data["delays"])).start()
                                output = ugoira2gif(file, path, data["id"], data["delays"])
                                files_size = files_size + os.path.getsize(output)
                            else:
                                Image.open(file)
                                # logger.debug(attachment)
                                files_size = files_size + os.path.getsize(file)
                                time.sleep(1)
                            files_num = files_num + 1
                            break
                        except (ProtocolError, UnidentifiedImageError, ChunkedEncodingError, ConnectionError,
                                PixivError) as e:
                            logger.error(f"{type(e)}: {str(e)}")
                            time.sleep(10)
                        except KeyboardInterrupt:
                            print_("[*] Stopped.")
                            input()
                            self.expires_check()
                        except OSError as e:
                            if str(e) == "[Errno 28] No space left on device":
                                with open("./queue", "wb") as f:
                                    pickle.dump(self.queue, f)
                                print_("[!] No space left on device.")
                            elif type(e) is FileNotFoundError:
                                logger.error(f"{type(e)}: {str(e)}")
                                break
                            else:
                                logger.error(f"{type(e)}: {str(e)}")
                            os.remove(file)
                            input()
                            exit()
                        except Exception as e:
                            logger.error(f"{type(e)}: {str(e)}")
                            os.remove(file)
                            input()
                            exit()
                if "qbar" in locals():
                    qbar.update()
            if "qbar" in locals():
                qbar.close()
            elapsed = time.time() - start
            info = f"TIME: {datetime.timedelta(seconds=elapsed)}\nFILES: {files_num}\nSIZE: {convert_size(files_size)}"
            print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
            print_("[*] Download finished.")
            notification(f"Download finished.\n{info}")
        else:
            print_("[!] There is nothing in the queue.")

    def parse(self, illust: dict):
        id = illust["id"]
        user = {
            "id": illust["user"]["id"],
            "name": illust["user"]["name"],
            "account": illust["user"]["account"],
            "is_followed": illust["user"]["is_followed"]
        }
        tags = [re.sub(r"\d+users", "", tag["name"]) for tag in illust["tags"]]
        total_bookmarks = illust["total_bookmarks"]
        is_bookmarked = illust["is_bookmarked"]
        is_muted = illust["is_muted"]
        illust_type = illust["type"]
        if result := self.check(id, user, tags, total_bookmarks, is_bookmarked, is_muted, illust_type):
            if type(result) is str:
                folder = result
            else:
                folder = ""
            create_date = illust["create_date"]
            data = {
                "id": id,
                "attachments": [],
                "type": illust_type,
                "folder": folder,
                "create_date": create_date
            }
            if illust_type == "ugoira":
                while True:
                    try:
                        ugoira_data = self.aapi.ugoira_metadata(id)
                        data["attachments"].append(ugoira_data["ugoira_metadata"]["zip_urls"]["medium"])
                        data["delays"] = [frame["delay"] for frame in ugoira_data["ugoira_metadata"]["frames"]]
                    except PixivError as e:
                        if "RemoteDisconnected" in str(e):
                            print_("[!] RemoteDisconnected.")
                        else:
                            logger.error(f"{type(e)}: {str(e)}")
                        time.sleep(1)
                    except KeyError as e:
                        try:
                            message = ugoira_data["error"]["message"]
                            if message == "RateLimit" or message == "Rate Limit":
                                print_("[!] RateLimit.")
                                time.sleep(180)
                            else:
                                print(ugoira_data)
                                logger.error(f"{type(e)}: {str(e)}")
                                time.sleep(1)
                                break
                        except KeyError:
                            time.sleep(1)
                    except TypeError:
                        break
                    else:
                        break
            else:
                try:
                    data["attachments"].append(illust["meta_single_page"]["original_image_url"])
                except KeyError:
                    data["attachments"] = [attachment["image_urls"]["original"] for attachment in illust["meta_pages"]]
            self.queue.append(data)

    def check(self, id: int, user: dict, tags: list, total_bookmarks: int, is_bookmarked: bool, is_muted: bool,
              illust_type: bool):
        if settings["ignore"]["enable"]:
            if user["id"] in settings["ignore"]["user"] or not set(tags).isdisjoint(
                    settings["ignore"]["tag"]) or is_muted:
                # logger.debug("ignore")
                return False
        if self.users > total_bookmarks:
            # logger.debug(f"{self.users} > {total_bookmarks}")
            return False
        if self.ugoira and not illust_type == "ugoira":
            return False
        elif self.ugoira is False and illust_type != "ugoira":
            return False
        if not is_bookmarked:
            self.aapi.illust_bookmark_add(id)
        if settings["folder"]["enable"]:
            if not set(tags).isdisjoint(settings["folder"]["tag"]):
                for ftag in settings["folder"]["tag"]:
                    if ftag in tags:
                        # logger.debug(ftag)
                        return ftag
        return True

    def offsetLimitBypass(self, next_qs, start_date=None):
        print_("[*] OffsetLimitBypass.")
        if start_date is None:
            date = datetime.datetime.fromisoformat(self.queue[-1]["create_date"])
        else:
            date = datetime.datetime.fromisoformat(start_date)
        logger.debug(str(date.date()))
        next_qs["start_date"] = str(date.date())
        next_qs["end_date"] = "2007-09-10"
        next_qs["offset"] = 0
        logger.debug(next_qs)
        return next_qs

    def init_option(self):
        self.users = 0
        self.ugoira = None
        self.page = count()

    def option(self):
        option = Write.Input(Center.XCenter("[OPTION] > ", spaces=40), Colors.green_to_black, interval=0,
                               hide_cursor=False)
        if s := re.search(r"(\d+)users", option):
            self.users = int(s.group(1))
        if s := re.search(r"(\d+):(\d+)?page", option):
            if s.group(2) is None:
                self.page = count(int(s.group(1)))
            else:
                print(s.groups())
                if step := int(s.group(1)) // 166:
                    print(step)
                    self.page = [166] * step
                    self.page.extend(range(int(s.group(2)) % 166))
                else:
                    self.page = range(int(s.group(1)), int(s.group(2)))
        elif s := re.search(r"(\d+)page", option):
            self.page = range(int(s.group(1)))
        if "ugoira-not" in option:
            self.ugoira = False
        elif "ugoira" in option:
            self.ugoira = True
        # print_(f"[OPTION] users: users: {self.users}, page: {page}, ugoira: {self.ugoira}")
        logger.debug(f"OPTION: users={self.users}, page={self.page}, ugoira={self.ugoira}")

    def illust(self, id):
        self.expires_check()
        data = self.aapi.illust_detail(id)
        try:
            illust = data["illust"]
            self.parse(illust)
        except PixivError as e:
            if "RemoteDisconnected" in str(e):
                print_("[!] RemoteDisconnected.")
            else:
                logger.error(f"{type(e)}: {str(e)}")
            time.sleep(1)
        except KeyError as e:
            logger.debug(data)
            logger.error(f"{type(e)}: {str(e)}")
        else:
            time.sleep(1)

    def user(self, id):
        self.expires_check()
        user_info = self.aapi.user_detail(id)
        try:
            info = f"ID: {user_info['user']['id']}\nNAME: {user_info['user']['name']}\nILLUSTS: {user_info['profile']['total_illusts'] + user_info['profile']['total_manga']}"
            print("")
            print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
            print("")
            notification(info)
        except KeyError:
            print(user_info)
            return
        for type in ["illust", "manga"]:
            next_qs = {"user_id": id, "type": type}
            for i in self.page:
                data = self.aapi.user_illusts(**next_qs)
                try:
                    illusts = data["illusts"]
                    for illust in illusts:
                        self.parse(illust)
                    next_qs = self.aapi.parse_qs(data["next_url"])
                    if next_qs["offset"] == 5010:
                        next_qs["start_date"] = illusts[-1]["create_date"]
                        next_qs["end_date"] = "2007-09-10"
                        next_qs["offset"] = 0
                except PixivError as e:
                    if "RemoteDisconnected" in str(e):
                        print_("[!] RemoteDisconnected.")
                    else:
                        logger.error(f"{type(e)}: {str(e)}")
                    time.sleep(1)
                except KeyError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    try:
                        message = data["error"]["message"]
                        if message == "RateLimit" or message == "Rate Limit":
                            print_("[!] RateLimit.")
                            time.sleep(180)
                        elif message == '{"offset":["offset must be no more than 5000"]}':
                            # next_qs = self.offsetLimitBypass(next_qs, start_date=create_date)
                            time.sleep(1)
                    except KeyError as e:
                        logger.error(f"{type(e)}: {str(e)}")
                        time.sleep(1)
                except TypeError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    break
                else:
                    if next_qs is None:
                        logger.debug(f"{type(next_qs)}: {str(next_qs)}")
                        break
                    time.sleep(1)

    def bookmarks(self):
        self.expires_check()
        next_qs = {"user_id": self.aapi.user_id}
        for i in self.page:
            data = self.aapi.user_bookmarks_illust(**next_qs)
            try:
                illusts = data["illusts"]
                for illust in illusts:
                    self.parse(illust)
                next_qs = self.aapi.parse_qs(data["next_url"])
                if next_qs["offset"] == 5010:
                    next_qs["start_date"] = illusts[-1]["create_date"]
                    next_qs["end_date"] = "2007-09-10"
                    next_qs["offset"] = 0
            except PixivError as e:
                if "RemoteDisconnected" in str(e):
                    print_("[!] RemoteDisconnected.")
                else:
                    logger.error(f"{type(e)}: {str(e)}")
                time.sleep(1)
            except KeyError as e:
                logger.error(f"{type(e)}: {str(e)}")
                try:
                    message = data["error"]["message"]
                    if message == "RateLimit" or message == "Rate Limit":
                        print_("[!] RateLimit.")
                        time.sleep(180)
                    elif message == '{"offset":["offset must be no more than 5000"]}':
                        # next_qs = self.offsetLimitBypass(next_qs, start_date=create_date)
                        time.sleep(1)
                except KeyError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    time.sleep(1)
            except TypeError as e:
                logger.error(f"{type(e)}: {str(e)}")
                break
            else:
                if next_qs is None:
                    logger.debug(f"{type(next_qs)}: {str(next_qs)}")
                    break
                time.sleep(1)
        info = f"PAGE: {self.page}\nILLUSTS: {len(self.queue)}"
        print("")
        print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
        print("")
        notification(info)

    def search(self, word):
        self.expires_check()
        next_qs = {"word": word}
        for i in self.page:
            data = self.aapi.search_illust(**next_qs)
            try:
                illusts = data["illusts"]
                for illust in illusts:
                    self.parse(illust)
                next_qs = self.aapi.parse_qs(data["next_url"])
                logger.debug(f"page: {i}, offset: {int(next_qs['offset'])}")
                if next_qs["offset"] == 5010:
                    next_qs["start_date"] = illusts[-1]["create_date"]
                    next_qs["end_date"] = "2007-09-10"
                    next_qs["offset"] = 0
            except PixivError as e:
                if "RemoteDisconnected" in str(e):
                    print_("[!] RemoteDisconnected.")
                else:
                    logger.error(f"{type(e)}: {str(e)}")
                time.sleep(1)
            except KeyError as e:
                logger.error(f"{type(e)}: {str(e)}")
                try:
                    message = data["error"]["message"]
                    if message == "RateLimit" or message == "Rate Limit":
                        print_("[!] RateLimit.")
                        time.sleep(180)
                    elif message == '{"offset":["offset must be no more than 5000"]}':
                        # next_qs = self.offsetLimitBypass(next_qs, start_date=create_date)
                        time.sleep(1)
                except KeyError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    time.sleep(1)
            except TypeError as e:
                logger.error(f"{type(e)}: {str(e)}")
                break
            else:
                if next_qs is None:
                    logger.debug(f"{type(next_qs)}: {str(next_qs)}")
                    break
                time.sleep(1)
        info = f"WORD: {word}\nUSERS: {self.users}\nILLUSTS: {len(self.queue)}"
        print("")
        print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
        print("")
        notification(info)

    def recent(self):
        self.expires_check()
        next_qs = {}
        for i in self.page:
            data = self.aapi.illust_new(**next_qs)
            try:
                illusts = data["illusts"]
                for illust in illusts:
                    self.parse(illust)
                next_qs = self.aapi.parse_qs(data["next_url"])
                if next_qs["offset"] == 5010:
                    next_qs["start_date"] = illusts[-1]["create_date"]
                    next_qs["end_date"] = "2007-09-10"
                    next_qs["offset"] = 0
            except PixivError as e:
                if "RemoteDisconnected" in str(e):
                    print_("[!] RemoteDisconnected.")
                else:
                    logger.error(f"{type(e)}: {str(e)}")
                time.sleep(1)
            except KeyError as e:
                logger.error(f"{type(e)}: {str(e)}")
                try:
                    message = data["error"]["message"]
                    if message == "RateLimit" or message == "Rate Limit":
                        print_("[!] RateLimit.")
                        time.sleep(180)
                    elif message == '{"offset":["offset must be no more than 5000"]}':
                        # next_qs = self.offsetLimitBypass(next_qs, start_date=create_date)
                        time.sleep(1)
                except KeyError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    time.sleep(1)
            except TypeError as e:
                logger.error(f"{type(e)}: {str(e)}")
                break
            else:
                if next_qs is None:
                    logger.debug(f"{type(next_qs)}: {str(next_qs)}")
                    break
                time.sleep(1)

        info = f"PAGE: {self.page}\nILLUSTS: {len(self.queue)}"
        print("")
        print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
        print("")
        notification(info)


def notification(message: str):
    def desktop(message: str):
        notice.notify(title="Notification", message=message, app_name="SUBARU", app_icon="./icon.ico")

    def discord(message: str):
        if settings["notification"]["discord"]["webhookUrl"] != "":
            if settings["notification"]["discord"]["mention"]["enable"]:
                if settings["notification"]["discord"]["mention"]["discordId"] != "":
                    message = f"<@{settings['notification']['discord']['mention']['discordId']}>\n{message}"
            DiscordWebhook(url=settings["notification"]["discord"]["webhookUrl"], content=message).execute()

    if settings["notification"]["enable"]:
        if settings["notification"]["desktop"]["enable"]:
            desktop(message)
        if settings["notification"]["discord"]["enable"]:
            discord(message)


def print_(text: str):
    print(Colorate.Vertical(Colors.green_to_black, Center.XCenter(text, spaces=40), 3))


def input_(text: str):
    return Write.Input(Center.XCenter(text, spaces=40), Colors.green_to_black, interval=0)


def load_settings():
    with open("settings.toml", "rb") as f:
        settings = tomllib.load(f)
    print_("[*] Load settings.")
    return settings


def login():
    from pixiv_auth import login
    refresh_token = login()
    if refresh_token not in settings["refresh_token"]:
        settings["refresh_token"].append(refresh_token)
        with open("settings.toml", "wb") as f:
            dump(settings, f)
        return refresh_token


def make_logger(name):
    logger = getLogger(name)
    logger.setLevel(DEBUG)

    fl_handler = FileHandler(filename=".log", encoding="utf-8", mode="w")
    fl_handler.setLevel(DEBUG)
    fl_handler.setFormatter(
        Formatter(
            "[{levelname}] {asctime} [{filename}:{lineno}] {message}", style="{"
        )
    )
    logger.addHandler(fl_handler)

    return logger


banner = r"""
   ______  _____  ___   ___  __  __
  / __/ / / / _ )/ _ | / _ \/ / / /
 _\ \/ /_/ / _  / __ |/ , _/ /_/ / 
/___/\____/____/_/ |_/_/|_|\____/  
"""
menu = """
[d] Download  [b] Bookmarks  [s] Search
[r] Recent    [l] Login      [R] Reload
"""
print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
version = "1.0"
System.Title(f"SUBARU v{version}")

os.chdir(os.path.dirname(os.path.abspath(__file__)))
logger = make_logger(__name__)
settings = load_settings()
try:
    client = Client(settings["refresh_token"][0])
except IndexError as e:
    logger.error(f"{type(e)}: {str(e)}")
    print_("[!] refresh token is nothing.")
    refresh_token = login()
    client = Client(refresh_token)

console = Console()

if __name__ == "__main__":
    while True:
        System.Clear()
        print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
        print_(menu)
        mode = input_("[SUBARU] > ")
        if mode == "d":
            System.Clear()
            print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
            urls = input_("[URL] > ").split()
            for url in urls:
                if m := re.match(r"https://(www\.)?pixiv\.net/(users|artworks)/(\d+)", url):
                    if m.group(2) == "users" and len(urls) == 1:
                        client.option()
                    with console.status("[bold green]Fetching data...") as status:
                        if m.group(2) == "artworks":
                            client.illust(m.group(3))
                        elif m.group(2) == "users":
                            client.user(m.group(3))
                    print_("[*] Fetch done.")
            try:
                client.download()
            except Exception as e:
                logger.error(f"{type(e)}: {str(e)}")
        elif mode == "b" or mode == "r":
            System.Clear()
            print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
            print("")
            client.option()
            with console.status("[bold green]Fetching data...") as status:
                if mode == "b":
                    client.bookmarks()
                else:
                    client.recent()
            print_("[*] Fetch done.")
            try:
                client.download()
            except Exception as e:
                logger.error(f"{type(e)}: {str(e)}")
        elif mode == "s":
            System.Clear()
            print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
            print("")
            word = Write.Input(Center.XCenter("[WORD] > ", spaces=40), Colors.green_to_black, interval=0,
                               hide_cursor=False)
            client.option()
            try:
                with console.status("[bold green]Fetching data...") as status:
                    client.search(word)
                print_("[*] Fetch done.")
                client.download()
            except Exception as e:
                logger.error(f"{type(e)}: {str(e)}")
        elif mode == "R":
            System.Clear()
            print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
            print("")
            settings = load_settings()
        client.init_option()
        input_("[*] Press ENTER to go back.")

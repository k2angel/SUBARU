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
        self.aapi.auth(refresh_token=refresh_token)
        self.queue = deque()
        self.users = 0

    def download(self):
        def convert_size(size):
            units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB")
            i = math.floor(math.log(size, 1024)) if size > 0 else 0
            size = round(size / 1024 ** i, 2)

            return f"{size} {units[i]}"

        def ugoira2gif(ugoira_zip, path, id, delays):
            time = datetime.datetime.now().timestamp()
            images = list()
            with zipfile.ZipFile(ugoira_zip) as zf:
                files = zf.namelist()
                ugoira_path = str(os.path.join(settings["directory"], "ugoira", id))
                zf.extractall(ugoira_path)
                delays_set = list(set(delays))
                gcd = math.gcd(*delays_set)
            for delay, file in zip(delays, files):
                image = Image.open(os.path.join(ugoira_path, file)).quantize()
                if image.mode != "RGB":
                    image = image.convert("RGB")
                for _ in range(math.floor(delay / gcd)):
                    images.append(image)
            else:
                gif_path = os.path.join(path, f"{id}_p0 ugoira.gif")
                try:
                    images[0].save(
                        gif_path,
                        save_all=True,
                        append_images=images[1:],
                        optimize=False,
                        duration=gcd,
                        loop=0,
                    )
                except AttributeError as e:
                    print(str(e))
                os.utime(gif_path, times=(time, time))
                os.remove(ugoira_zip)
                shutil.rmtree(ugoira_path)

        if qsize := len(self.queue):
            files_num = 0
            files_size = 0
            print_("[*] Download started.")
            notification("Download stared.")
            start = time.time()
            if qsize != 1:
                qbar = tqdm(range(qsize), desc="Queue", leave=False)
            for i in range(qsize):
                data = self.queue.popleft()
                path = str(os.path.join(settings["directory"], data["folder"]))
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                post_id = data["id"]
                attachments = data["attachments"]
                for attachment in tqdm(attachments, desc="Attachments", leave=False):
                    file = os.path.join(path, os.path.basename(attachment))
                    if os.path.exists(file):
                        continue
                    while True:
                        try:
                            self.aapi.download(attachment, path=path)
                            if data["type"] == "ugoira" and settings["ugoira2gif"]["enable"]:
                                threading.Thread(target=ugoira2gif, args=(file, path, data["id"], data["delays"]))
                                time.sleep(1)
                            else:
                                Image.open(file)
                            files_num = files_num + 1
                            files_size = files_size + os.path.getsize(file)
                            time.sleep(1)
                            break
                        except (ProtocolError, UnidentifiedImageError, ChunkedEncodingError, ConnectionError, PixivError):
                            time.sleep(10)
                        except KeyboardInterrupt:
                            print_("[*] Stopped.")
                            input()
                        except OSError as e:
                            if str(e) == "[Errno 28] No space left on device":
                                with open("./queue", "wb") as f:
                                    pickle.dump(self.queue, f)
                            else:
                                print(type(e))
                                print(str(e))
                            os.remove(file)
                            input()
                            exit()
                        except Exception as e:
                            print(type(e))
                            print(str(e))
                            os.remove(file)
                            input()
                            exit()
                    if "qbar" in locals():
                        qbar.update(1)
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
        if result := self.check(id, user, tags, total_bookmarks, is_bookmarked, is_muted):
            if type(result) is str:
                folder = result
            else:
                folder = ""
            illust_type = illust["type"]
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
                            print(str(e))
                        time.sleep(1)
                    except KeyError as e:
                        message = data["error"]["message"]
                        if message == "RateLimit" or message == "Rate Limit":
                            print_("[!] RateLimit.")
                            time.sleep(180)
                        else:
                            print(data)
                            print(str(e))
                            time.sleep(1)
                            break
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

    def check(self, id: int, user: dict, tags: list, total_bookmarks: int, is_bookmarked: bool, is_muted: bool):
        if settings["ignore"]["enable"]:
            if user["id"] in settings["ignore"]["user"] or not set(tags).isdisjoint(settings["ignore"]["tag"]) or is_muted:
                #print_("ignore")
                return False
        if self.users > total_bookmarks:
            #print(f"{self.users} < {total_bookmarks}")
            return False
        if not is_bookmarked:
            self.aapi.illust_bookmark_add(id)
        if settings["folder"]["enable"]:
            if not set(tags).isdisjoint(settings["folder"]["tag"]):
                for ftag in settings["folder"]["tag"]:
                    if ftag in tags:
                        #print_(ftag)
                        return ftag
        return True

    def offsetLimitBypass(self, next_qs):
        print_("[*] OffsetLimitBypass.")
        date = datetime.datetime.fromisoformat(self.queue[-1]["create_date"])
        next_qs["start_date"] = str(date.date())
        return next_qs

    def illust(self, id):
        data = self.aapi.illust_detail(id)
        try:
            illust = data["illust"]
            self.parse(illust)
        except PixivError as e:
            if "RemoteDisconnected" in str(e):
                print_("[!] RemoteDisconnected.")
            else:
                print(str(e))
            time.sleep(1)
        except KeyError as e:
            print(data)
            print(str(e))
        else:
            time.sleep(1)

    def user(self, id):
        user_info = self.aapi.user_detail(id)
        try:
            info = f"ID: {user_info['user']['id']}\nNAME: {user_info['user']['name']}\nILLUSTS: {user_info['profile']['total_illusts'] + user_info['profile']['total_manga']}"
            print("")
            print_(info)
            print("")
            notification(info)
        except KeyError:
            print(user_info)
            return
        next_qs = {"user_id": id}
        while True:
            data = self.aapi.user_illusts(**next_qs)
            try:
                illusts = data["illusts"]
                for illust in illusts:
                    self.parse(illust)
                next_qs = self.aapi.parse_qs(data["next_url"])
            except PixivError as e:
                if "RemoteDisconnected" in str(e):
                    print_("[!] RemoteDisconnected.")
                else:
                    print(str(e))
                time.sleep(1)
            except KeyError as e:
                message = data["error"]["message"]
                if message == "RateLimit" or message == "Rate Limit":
                    print_("[!] RateLimit.")
                    time.sleep(180)
                elif message == '{"offset":["offset must be no more than 5000"]}':
                    next_qs = self.offsetLimitBypass(next_qs)
                    time.sleep(1)
                else:
                    print(data)
                    print(str(e))
                    break
            except TypeError:
                break
            else:
                if next_qs is None:
                    break
                time.sleep(1)

    def bookmarks(self, page):
        next_qs = {"user_id": self.aapi.user_id}
        for i in range(page):
            data = self.aapi.user_bookmarks_illust(**next_qs)
            try:
                illusts = data["illusts"]
                for illust in illusts:
                    self.parse(illust)
                next_qs = self.aapi.parse_qs(data["next_url"])
            except PixivError as e:
                if "RemoteDisconnected" in str(e):
                    print_("[!] RemoteDisconnected.")
                else:
                    print(str(e))
                time.sleep(1)
            except KeyError as e:
                message = data["error"]["message"]
                if message == "RateLimit" or message == "Rate Limit":
                    print_("[!] RateLimit.")
                    time.sleep(180)
                elif message == '{"offset":["offset must be no more than 5000"]}':
                    next_qs = self.offsetLimitBypass(next_qs)
                    time.sleep(1)
                else:
                    print(data)
                    print(str(e))
                    break
            except TypeError:
                break
            else:
                if next_qs is None:
                    break
                time.sleep(1)

    def search(self, word):
        if s := re.search(r"--(\d+)users", word):
            self.users = int(s.group(1))
            #word = word.replace(s.group(0), "")
        next_qs = {"word": word}
        while True:
            data = self.aapi.search_illust(**next_qs)
            try:
                illusts = data["illusts"]
                for illust in illusts:
                    self.parse(illust)
                next_qs = self.aapi.parse_qs(data["next_url"])
            except PixivError as e:
                if "RemoteDisconnected" in str(e):
                    print_("[!] RemoteDisconnected.")
                else:
                    print(str(e))
                time.sleep(1)
            except KeyError as e:
                message = data["error"]["message"]
                if message == "RateLimit" or message == "Rate Limit":
                    print_("[!] RateLimit.")
                    time.sleep(180)
                elif message == '{"offset":["offset must be no more than 5000"]}':
                    next_qs = self.offsetLimitBypass(next_qs)
                    time.sleep(1)
                else:
                    print(data)
                    print(str(e))
                    break
            except TypeError:
                break
            else:
                if next_qs is None:
                    break
                time.sleep(1)
        self.users = 0

    def recent(self, page):
        next_qs = {}
        for i in range(page):
            data = self.aapi.illust_new(**next_qs)
            try:
                illusts = data["illusts"]
                for illust in illusts:
                    self.parse(illust)
                next_qs = self.aapi.parse_qs(data["next_url"])
            except PixivError as e:
                if "RemoteDisconnected" in str(e):
                    print_("[!] RemoteDisconnected.")
                else:
                    print(str(e))
                time.sleep(1)
            except KeyError as e:
                message = data["error"]["message"]
                if message == "RateLimit" or message == "Rate Limit":
                    print_("[!] RateLimit.")
                    time.sleep(180)
                elif message == '{"offset":["offset must be no more than 5000"]}':
                    next_qs = self.offsetLimitBypass(next_qs)
                    time.sleep(1)
                else:
                    print(data)
                    print(str(e))
                    break
            except TypeError:
                break
            else:
                time.sleep(1)

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
    return Write.Input(Center.XCenter(text, spaces=40), Colors.green_to_black,
                       interval=0, hide_cursor=True)


def settings():
    with open("settings.toml", "rb") as f:
        settings = tomllib.load(f)
    return settings


def login():
    from pixiv_auth import login
    refresh_token = login()
    if refresh_token not in settings["refresh_token"]:
        settings["refresh_token"].append(refresh_token)
        with open("settings.toml", "wb") as f:
            dump(settings, f)


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
version = "1.0"
System.Title(f"SUBARU v{version}")

os.chdir(os.path.dirname(os.path.abspath(__file__)))
settings = settings()
client = Client(settings["refresh_token"][0])

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
            url = input_("[URL] > ")
            if m := re.match(r"https://(www\.)?pixiv\.net/(users|artworks)/(\d+)", url):
                with console.status("[bold green]Fetching data...") as status:
                    if m.group(2) == "artworks":
                        client.illust(m.group(3))
                    elif m.group(2) == "users":
                        client.user(m.group(3))
                print_("[*] Fetch done.")
                try:
                    client.download()
                except Exception as e:
                    print(type(e))
                    print_(str(e))
        elif mode == "b" or mode == "r":
            System.Clear()
            print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
            print("")
            try:
                page = int(input_("[PAGE] > "))
            except ValueError:
                print_("[!] Error.")
                continue
            with console.status("[bold green]Fetching data...") as status:
                if mode == "b":
                    client.bookmarks(page)
                else:
                    client.recent(page)
            print_("[*] Fetch done.")
            try:
                client.download()
            except Exception as e:
                print(type(e))
                print_(str(e))
        elif mode == "s":
            System.Clear()
            print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))
            print("")
            word = Write.Input(Center.XCenter("[WORD] > ", spaces=40), Colors.green_to_black, interval=0)
            with console.status("[bold green]Fetching data...") as status:
                client.search(word)
            print_("[*] Fetch done.")
            try:
                client.download()
            except Exception as e:
                print(type(e))
                print_(str(e))
        input_("[*] Press ENTER to go back.")

import copy
import datetime
import html
import itertools
import json
import math
import os
import pickle
import re
import shutil
import subprocess
import threading
import time
import tomllib
import zipfile
from collections import deque
from itertools import count
from logging import DEBUG, FileHandler, Formatter, getLogger
from urllib.parse import urlparse

import keyboard
import tomli_w
import webp
from discord_webhook import DiscordWebhook
from PIL import Image, UnidentifiedImageError
from pixivpy3 import AppPixivAPI
from pixivpy3.utils import PixivError
from plyer import notification as notice
from pystyle import *
from requests.exceptions import ChunkedEncodingError
from rich.console import Console
from tqdm import tqdm
from urllib3.exceptions import ProtocolError


class Client:
    def __init__(self, refresh_token):
        self.option_ = None
        self.queue = None
        self.aapi = AppPixivAPI()
        self.refresh_token = refresh_token
        self.access_token_get, self.expires_in = self.login()
        if not os.path.exists("./queue"):
            self.queue_list = dict()
            pickle.dump(self.queue_list, open("./queue", "wb"))
        else:
            self.queue_list = pickle.load(open("./queue", "rb"))
        if not os.path.exists("./stalker.json"):
            self.stalker = dict()
            with open("./stalker.json", "w", encoding="utf-8") as f:
                json.dump(self.stalker, f, indent=4, ensure_ascii=False)
        else:
            with open("./stalker.json", "r", encoding="utf-8") as f:
                self.stalker = json.load(f)
        self.init()
        self.reporter_run = settings["notification"]["report"]["enable"]
        self.error_message = {
            "ratelimit": "Rate Limit",
            "invalid": "Error occurred at the OAuth process. Please check your Access Token to fix this. "
                       "Error Message: invalid_grant"
        }

    def init(self):
        self.queue = {
            "queue": deque(),
            "time": None,
            "name": "",
            "option": "",
            "size": 0
        }
        self.option_ = {
            "users": 0,
            "illust": None,
            "manga": None,
            "ugoira": None,
            "r-18": None,
            "r-18g": None,
            "follow": None,
            "page": [count()],
            "ignore": settings["ignore"]["enable"],
            "delete": False
        }

    def login(self):
        while True:
            try:
                auth_data = self.aapi.auth(refresh_token=self.refresh_token)
            except PixivError as e:
                logger.error(f"{type(e)}: {str(e)}")
                if "RemoteDisconnected" in str(e):
                    print_("[!] Authentication error!: RemoteDisconnected.")
                elif "refresh_token is set" in str(e):
                    print_("[!] Authentication error!: refresh token is nothing.")
                    input()
                    exit()
                elif "check refresh_token" in str(e):
                    print_("[!] Authentication error!: Invalid refresh token.")
                    input()
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
            self.access_token_get, self.expires_in = self.login()

    def reporter(self):
        logger.debug("reporter started...")
        while self.reporter_run:
            for i in range(settings["notification"]["report"]["interval"] * 60):
                if not self.reporter_run:
                    break
                time.sleep(1)
            if not self.reporter_run:
                break
            info = f"LEFTOVER QUEUE: {len(self.queue['queue']) + 1}"
            notification(info)
        logger.debug("reporter stopped...")

    def reporter_join(self, reporter_t: threading.Thread):
        self.reporter_run = False
        reporter_t.join()
        self.reporter_run = True

    def download(self):
        def convert_size(size):
            units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB")
            i = math.floor(math.log(size, 1024)) if size > 0 else 0
            size = round(size / 1024 ** i, 2)

            return f"{size} {units[i]}"

        def ugoira2gif(ugoira_zip, path, id, delays):
            u_format = settings['ugoira2gif']['format']
            if u_format == "gif" or u_format == "webp" or u_format == "apng":
                if u_format == "apng":
                    u_format = "png"
            else:
                return
            output = os.path.join(path, f"{id}_p0 ugoira.{u_format}")
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
                    if u_format == "gif" or u_format == "webp":
                        image = image.quantize()
                        # if image.mode != "RGB":
                        #     image = image.convert("RGB")
                    for _ in range(math.floor(delay / gcd)):
                        images.append(image)
                else:
                    if u_format == "gif" or u_format == "png":
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
                    elif u_format == "webp":
                        webp.save_images(images, output, fps=(1000 / gcd))
                    os.utime(output, times=(ctime, ctime))
                    shutil.rmtree(ugoira_path)
                    logger.debug(f"ugoira2gif: {ugoira_zip} -> {output}")
            try:
                os.remove(ugoira_zip)
            except PermissionError as e:
                logger.error(f"{type(e)}: {str(e)}")

        if qsize := len(self.queue["queue"]):
            exit_ = False
            files_num = 0
            files_size = 0
            print_("[*] Download started.")
            print("")
            notification("Download stared.")
            start = time.time()
            self.queue["time"] = datetime.datetime.now()
            self.queue["size"] = qsize
            self.queue_list[str(start)] = self.queue
            pickle.dump(self.queue_list, open("./queue", "wb"))
            if qsize != 1:
                qbar = tqdm(total=qsize, desc="Queue", leave=False)
                logger.debug(f"qsize: {qsize}")
                if self.reporter_run:
                    reporter_t = threading.Thread(target=self.reporter)
                    reporter_t.start()
            for i in range(qsize):
                data = self.queue["queue"].popleft()
                path = str(os.path.join(settings["directory"], data["folder"]))
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                post_id = data["id"]
                attachments = data["attachments"]
                asize = len(attachments)
                if asize != 1:
                    abar = tqdm(total=asize, desc="Attachments", leave=False)
                for attachment in attachments:
                    file = os.path.join(path, os.path.basename(attachment))
                    if data["type"] == "ugoira":
                        u_format = settings['ugoira2gif']['format']
                        if u_format == "gif" or u_format == "webp" or u_format == "apng":
                            if u_format == "apng":
                                u_format = "png"
                            e_path = os.path.join(path, f"{post_id}_p0 ugoira.{u_format}")
                            if os.path.exists(e_path):
                                logger.debug(f"exists file: {e_path}")
                                continue
                        else:
                            continue
                    elif os.path.exists(file):
                        logger.debug(f"exists file: {file}")
                        continue

                    while True:
                        try:
                            self.aapi.download(attachment, path=path)
                            if data["type"] == "ugoira" and settings["ugoira2gif"]["enable"]:
                                files_size = files_size + os.path.getsize(file)
                                if settings["ugoira2gif"]["thread"]:
                                    threading.Thread(target=ugoira2gif,
                                                     args=(file, path, post_id, data["delays"])).start()
                                else:
                                    ugoira2gif(file, path, data["id"], data["delays"])
                            else:
                                Image.open(file)
                                files_size = files_size + os.path.getsize(file)
                                time.sleep(1)
                            files_num = files_num + 1
                            if asize != 1:
                                abar.update()
                            logger.debug(f"downloaded: {file}")
                            break
                        except (ProtocolError, UnidentifiedImageError, ChunkedEncodingError, ConnectionError,
                                PixivError) as e:
                            logger.error(f"{type(e)}: {str(e)}")
                            time.sleep(10)
                        except KeyboardInterrupt:
                            if self.reporter_run:
                                self.reporter_join(reporter_t)
                            if asize != 1:
                                abar.close()
                            if qsize != 1:
                                qbar.close()
                            print_("[*] Stopped.")
                            print_("[?] Resume the queue? (y/n) > ")
                            if keyboard.is_pressed("y"):
                                print("")
                                if qsize != 1:
                                    qbar = tqdm(total=qsize, desc="Queue", leave=False, initial=i+1)
                                if asize != 1:
                                    abar = tqdm(total=len(attachments), desc="Attachments", leave=False,
                                                initial=attachments.index(attachment))
                                if self.reporter_run:
                                    reporter_t = threading.Thread(target=self.reporter)
                                    reporter_t.start()
                            else:
                                self.queue["queue"].appendleft(data)
                                exit_ = True
                                os.remove(file)
                                break
                        except OSError as e:
                            if str(e) == "[Errno 28] No space left on device":
                                print_("[!] No space left on device.")
                                pickle.dump(self.queue_list, open("./queue", "wb"))
                                if self.reporter_run:
                                    self.reporter_join(reporter_t)
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
                if qsize != 1:
                    qbar.update()
                    self.queue["size"] = len(self.queue["queue"])
                    self.queue_list[str(start)] = self.queue
                    pickle.dump(self.queue_list, open("./queue", "wb"))
                if asize != 1:
                    abar.close()
                if exit_:
                    break
            if not exit_:
                del self.queue_list[str(start)]
                pickle.dump(self.queue_list, open("./queue", "wb"))
            if qsize != 1:
                qbar.close()
            if self.reporter_run and not exit_:
                self.reporter_join(reporter_t)
            elapsed = time.time() - start
            info = f"TIME: {datetime.timedelta(seconds=elapsed)}\nFILES: {files_num}\nSIZE: {convert_size(files_size)}"
            print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
            print("")
            print_("[*] Download finished.")
            notification(f"Download finished.\n{info}")
        else:
            print_("[!] There is nothing in the queue.")
        self.init()

    def parse(self, illust):
        id_ = illust["id"]
        user = {
            "id": illust["user"]["id"],
            "name": illust["user"]["name"],
            "account": illust["user"]["account"],
            "is_followed": illust["user"]["is_followed"]
        }
        tags = [re.sub(r"\d+users", "", tag["name"]) for tag in illust["tags"]]
        for i in range(len(tags)):
            tag = tags[i]
            for vague in settings["folder"]["vague"]:
                if tag in vague["vague"]:
                    # logger.debug(f"{tag} -> {vague['tag']}")
                    tags[i] = tag.replace(tag, vague["tag"])
        total_bookmarks = illust["total_bookmarks"]
        is_bookmarked = illust["is_bookmarked"]
        is_muted = illust["is_muted"]
        illust_type = illust["type"]
        illust_ai_type = illust["illust_ai_type"]
        x_restrict = illust["x_restrict"]
        if result := self.check(id_, user, tags, total_bookmarks, is_bookmarked, is_muted, illust_type, illust_ai_type,
                                x_restrict):
            if type(result) is str:
                folder = result
            else:
                folder = ""
            create_date = illust["create_date"]
            data = {
                "id": id_,
                "attachments": [],
                "type": illust_type,
                "folder": folder,
                "create_date": create_date
            }
            if illust_type == "ugoira":
                while True:
                    try:
                        ugoira_data = self.aapi.ugoira_metadata(id_)
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
                            if message == self.error_message["ratelimit"]:
                                print_("[!] RateLimit.")
                                time.sleep(180)
                            else:
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
            self.queue["queue"].append(data)
            logger.debug(f"queue append: {data['id']}")

    def check(self, id, user, tags, total_bookmarks, is_bookmarked, is_muted, illust_type, illust_ai_type, x_restrict):
        def trans(path):
            return path.translate(str.maketrans(
                {"　": " ", '\\': '＼', '/': '／', ':': '：', '*': '＊', '?': '？', '"': '”',
                 '<': '＜', '>': '＞', '|': '｜'}))

        if self.option_["ignore"]:
            if user["id"] in settings["ignore"]["user"] or is_muted:
                logger.debug(f"ignore user: {user['id']}")
                return False
            elif not set(tags).isdisjoint(settings["ignore"]["tag"]):
                for itag in settings["ignore"]["tag"]:
                    if itag in tags:
                        logger.debug(f"ignore tag: {itag}")
                return False
            if settings["ignore"]["ai_illust"]["enable"] and illust_ai_type == 2:
                if not settings["ignore"]["ai_illust"]["follow_user"]:
                    logger.debug("ignore: AI")
                    return False
                elif not user["is_followed"]:
                    logger.debug("ignore: AI")
                    return False
        if self.option_["users"] > total_bookmarks:
            logger.debug(f"ignore users: {self.option_['users']} > {total_bookmarks}")
            return False
        if self.option_["illust"] and illust_type != "illust":
            logger.debug(f"exclusive illust: {illust_type}")
            return False
        elif self.option_["illust"] is False and illust_type == "illust":
            logger.debug(f"ignore illust: {illust_type}")
            return False
        if self.option_["manga"] and illust_type != "manga":
            logger.debug(f"exclusive manga: {illust_type}")
            return False
        elif self.option_["manga"] is False and illust_type == "manga":
            logger.debug(f"ignore manga: {illust_type}")
            return False
        if self.option_["ugoira"] and illust_type != "ugoira":
            logger.debug(f"exclusive ugoira: {illust_type}")
            return False
        elif self.option_["ugoira"] is False and illust_type == "ugoira":
            logger.debug(f"ignore ugoira: {illust_type}")
            return False
        if self.option_["r-18"] and x_restrict == 0:
            logger.debug(f"exclusive R-18: {x_restrict}")
            return False
        elif self.option_["r-18"] is False and x_restrict != 0:
            logger.debug(f"ignore R-18: {x_restrict}")
            return False
        if self.option_["r-18g"] and x_restrict != 2:
            logger.debug(f"exclusive R-18G: {x_restrict}")
            return False
        elif self.option_["r-18g"] is False and x_restrict == 2:
            logger.debug(f"ignore R-18G: {x_restrict}")
            return False
        if self.option_["follow"] and not user["is_followed"]:
            logger.debug(f"exclusive follow user: {user['is_followed']}")
            return False
        elif self.option_["follow"] is False and user["is_followed"]:
            logger.debug(f"ignore follow user: {user['is_followed']}")
            return False
        if not is_bookmarked and settings["bookmark"]:
            self.aapi.illust_bookmark_add(id)
        if settings["folder"]["enable"]:
            if settings["folder"]["follow_user"] and user["is_followed"]:
                return f"users/{self.stalker_check(str(user['id']), trans(user['name']))}[{user['id']}]"
            if user["id"] in settings["folder"]["user"]:
                for fuser in settings["folder"]["user"]:
                    if fuser == user["id"]:
                        return f"users/{self.stalker_check(str(user['id']), trans(user['name']))}[{user['id']}]"
            if not set(tags).isdisjoint(settings["folder"]["tag"]):
                for ftag in settings["folder"]["tag"]:
                    if ftag in tags:
                        # logger.debug(ftag)
                        return "tags/" + trans(ftag)
        return True

    def stalker_check(self, uuid, path):
        try:
            if self.stalker[uuid] == path:
                return path
            else:
                old_path = self.stalker[uuid]
                try:
                    os.rename(os.path.join(settings["directory"], f"{old_path}[{uuid}]"),
                              os.path.join(settings["directory"], f"{path}[{uuid}]"))
                except (FileNotFoundError, FileExistsError) as e:
                    logger.error(f"{type(e)}: {str(e)}")
                self.stalker[uuid] = path
                with open("./stalker.json", "w", encoding="utf-8") as f:
                    json.dump(self.stalker, f, indent=4, ensure_ascii=False)
                return path
        except KeyError:
            self.stalker[uuid] = path
            with open("./stalker.json", "w", encoding="utf-8") as f:
                json.dump(self.stalker, f, indent=4, ensure_ascii=False)
            return path

    def option(self):
        option = input_("[OPTION] > ", hide_cursor=False)
        if not option.split():
            option = settings["option"]
        self.queue["option"] = option
        logger.debug(option)
        if s := re.search(r"(\d+)users", option):
            self.option_["users"] = int(s.group(1))
        if s := re.search(r"(\d+):(\d+)?page", option):
            start = int(s.group(1))
            if s.group(2) is None:  # 200:page
                if step := int(s.group(1)) // 166:  # 200:page
                    page = [[166] * step, count((start % 166) + 1)]
                else:  # 100:page
                    page = [[start], count(start + 1)]
            else:  # 200:250page
                end = int(s.group(2))
                elapsed = end - start
                if step := start // 166:  # 200:250page -> 50
                    start_ = start - 166 * step
                    if step != end // 166:  # 200:400page -> 200
                        # print(0)
                        page = [[166] * step, range(start_, 166)]
                        elapsed = elapsed - 166 + start_
                        for i in range(elapsed // 166):
                            page.append(range(166))
                        page.append(range(end % 166))
                    else:  # 200:250page -> 50
                        # print(1)
                        page = [[166] * step, range(start_, end % 166)]
                elif elapsed // 166:  # 100:300page -> 200
                    # print(3)
                    page = [range(start, 166)]
                    elapsed = elapsed - (166 - start)
                    for i in range(elapsed // 166):
                        page.append(range(166))
                    page.append(range(elapsed % 166))
                else:  # 100:150page -> 50
                    # print(4)
                    page = [range(start, end)]
            self.option_["page"] = page
        elif s := re.search(r"(\d+)page", option):
            start = int(s.group(1))
            if step := start // 166:  # 200page
                page = [range(166)] * step
                page.append(range(start % 166))
            else:  # 100page
                page = [range(start)]
            self.option_["page"] = page
        if "ignore-disable" in option:
            self.option_["ignore"] = False
        if "illust-not" in option:
            self.option_["illust"] = False
        elif "illust" in option:
            self.option_["illust"] = True
        if "manga-not" in option:
            self.option_["manga"] = False
        elif "manga" in option:
            self.option_["manga"] = True
        if "ugoira-not" in option:
            self.option_["ugoira"] = False
        elif "ugoira" in option:
            self.option_["ugoira"] = True
        if "r-18-not" in option:
            self.option_["r-18"] = False
        elif "r-18" in option:
            self.option_["r-18"] = True
        if "r-18g-not" in option:
            self.option_["r-18g"] = False
        elif "r-18g" in option:
            self.option_["r-18g"] = True
        if "follow" in option:
            self.option_["follow"] = True
        elif "follow-not" in option:
            self.option_["follow"] = False
        info = ", ".join([f"{key}={self.option_[key]}" for key in self.option_.keys()])
        logger.debug(f"OPTION: {info}")

    def illust(self, id_):
        self.expires_check()
        self.queue["name"] = f"illust: {id_}"
        data = self.aapi.illust_detail(id_)
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

    def user(self, id_):
        self.expires_check()
        while True:
            try:
                user_info = self.aapi.user_detail(id_)
                info = (f"ID: {user_info['user']['id']}\nNAME: {user_info['user']['name']}\n"
                        f"ILLUSTS: {user_info['profile']['total_illusts'] + user_info['profile']['total_manga']}")
                self.queue["name"] = f"{user_info['user']['name']}[{user_info['user']['id']}]"
                print("")
                print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
                print("")
                notification(info)
            except PixivError as e:
                logger.error(f"{type(e)}: {str(e)}")
                time.sleep(1)
            except KeyError as e:
                logger.error(f"{type(e)}: {str(e)}")
                logger.error(user_info)
                time.sleep(1)
            else:
                break
        for type_ in ["illust", "manga"]:
            next_qs = {"user_id": id_, "type": type_}
            init_offset = False
            page = copy.deepcopy(self.option_["page"])
            logger.debug(f"{type_}: {page}")
            debug_index = 0
            for i_obj in page:
                logger.debug(i_obj)
                for i in i_obj:
                    debug_index = debug_index + 1
                    if not init_offset:
                        next_qs["offset"] = i * 30
                    try:
                        data = self.aapi.user_illusts(**next_qs)
                        illusts = data["illusts"]
                        for illust in illusts:
                            self.parse(illust)
                        next_qs = self.aapi.parse_qs(data["next_url"])
                        logger.debug(f"page: {debug_index}, offset: {debug_index * 30}")
                        if next_qs["offset"] == "5010":
                            next_qs["start_date"] = str(
                                datetime.datetime.fromisoformat(illusts[-1]["create_date"]).date())
                            next_qs["end_date"] = "2007-09-10"
                            next_qs["offset"] = 0
                            if type(i_obj) is itertools.count and not init_offset:
                                logger.debug(f"init_offset: {type(i_obj)}")
                                init_offset = True
                            logger.debug(next_qs)
                    except PixivError as e:
                        if "RemoteDisconnected" in str(e):
                            print_("[!] RemoteDisconnected.")
                        else:
                            logger.error(f"{type(e)}: {str(e)}")
                        time.sleep(1)
                    except KeyError as e:
                        logger.error(f"{type(e)}: {str(e)}")
                        logger.error(data)
                        try:
                            message = data["error"]["message"]
                            if message == self.error_message["ratelimit"]:
                                print_("[!] RateLimit.")
                                time.sleep(180)
                            elif message == self.error_message["invalid"]:
                                self.access_token_get, self.expires_in = self.login()
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
        self.queue["name"] = f"bookmarks"
        next_qs = {"user_id": self.aapi.user_id}
        init_offset = False
        debug_index = 0
        for i_obj in self.option_["page"]:
            logger.debug(i_obj)
            for i in i_obj:
                debug_index = debug_index + 1
                if not init_offset:
                    next_qs["offset"] = i * 30

                try:
                    data = self.aapi.user_bookmarks_illust(**next_qs)
                    illusts = data["illusts"]
                    for illust in illusts:
                        self.parse(illust)
                    next_qs = self.aapi.parse_qs(data["next_url"])
                    logger.debug(f"page: {debug_index}, offset: {debug_index * 30}")
                    if next_qs["offset"] == "5010":
                        next_qs["start_date"] = str(datetime.datetime.fromisoformat(illusts[-1]["create_date"]).date())
                        next_qs["end_date"] = "2007-09-10"
                        next_qs["offset"] = 0
                        if type(i_obj) is itertools.count and not init_offset:
                            logger.debug(f"init_offset: {type(i_obj)}")
                            init_offset = True
                        logger.debug(next_qs)
                except PixivError as e:
                    if "RemoteDisconnected" in str(e):
                        print_("[!] RemoteDisconnected.")
                    else:
                        logger.error(f"{type(e)}: {str(e)}")
                    time.sleep(1)
                except KeyError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    logger.error(data)
                    try:
                        message = data["error"]["message"]
                        if message == self.error_message["ratelimit"]:
                            print_("[!] RateLimit.")
                            time.sleep(180)
                        elif message == self.error_message["invalid"]:
                            self.access_token_get, self.expires_in = self.login()
                    except KeyError as e:
                        logger.error(f"{type(e)}: {str(e)}")
                        time.sleep(1)
                except TypeError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    info = f"PAGE: {self.option_['page']}\nILLUSTS: {len(self.queue['queue'])}"
                    print("")
                    print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
                    print("")
                    notification(info)
                    break
                else:
                    if next_qs is None:
                        logger.debug(f"{type(next_qs)}: {str(next_qs)}")
                        info = f"PAGE: {self.option_['page']}\nILLUSTS: {len(self.queue['queue'])}"
                        print("")
                        print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
                        print("")
                        notification(info)
                        break
                    time.sleep(1)

    def search(self, word):
        self.expires_check()
        self.queue["name"] = f"{word}"
        next_qs = {"word": word}
        init_offset = False
        debug_index = 0
        for i_obj in self.option_["page"]:
            logger.debug(i_obj)
            logger.debug(next_qs)
            for i in i_obj:
                debug_index = debug_index + 1
                if not init_offset:
                    next_qs["offset"] = i * 30
                try:
                    data = self.aapi.search_illust(**next_qs)
                    illusts = data["illusts"]
                    for illust in illusts:
                        self.parse(illust)
                    next_qs = self.aapi.parse_qs(data["next_url"])
                    logger.debug(f"page: {debug_index}, offset: {debug_index * 30}")
                    if next_qs["offset"] == "5010":
                        next_qs["start_date"] = str(datetime.datetime.fromisoformat(illusts[-1]["create_date"]).date())
                        next_qs["end_date"] = "2007-09-10"
                        next_qs["offset"] = 0
                        if type(i_obj) is itertools.count and not init_offset:
                            logger.debug(f"init_offset: {type(i_obj)}")
                            init_offset = True
                        logger.debug(next_qs)
                except PixivError as e:
                    if "RemoteDisconnected" in str(e):
                        print_("[!] RemoteDisconnected.")
                    else:
                        logger.error(f"{type(e)}: {str(e)}")
                    time.sleep(1)
                except KeyError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    logger.error(data)
                    try:
                        message = data["error"]["message"]
                        if message == self.error_message["ratelimit"]:
                            print_("[!] RateLimit.")
                            time.sleep(180)
                        elif message == self.error_message["invalid"]:
                            self.access_token_get, self.expires_in = self.login()
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
        info = f"WORD: {word}\nUSERS: {self.option_['users']}\nILLUSTS: {len(self.queue['queue'])}"
        # print("")
        # print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
        # print("")
        notification(info)

    def recent(self):
        self.expires_check()
        self.queue["name"] = f"recent"
        next_qs = dict()
        init_offset = False
        debug_index = 0
        for i_obj in self.option_["page"]:
            logger.debug(i_obj)
            for i in i_obj:
                debug_index = debug_index + 1
                if not init_offset:
                    next_qs["offset"] = i * 30

                try:
                    data = self.aapi.illust_new(**next_qs)
                    illusts = data["illusts"]
                    for illust in illusts:
                        self.parse(illust)
                    next_qs = self.aapi.parse_qs(data["next_url"])
                    logger.debug(f"page: {debug_index}, offset: {debug_index * 30}")
                    if next_qs["offset"] == "5010":
                        next_qs["start_date"] = str(datetime.datetime.fromisoformat(illusts[-1]["create_date"]).date())
                        next_qs["end_date"] = "2007-09-10"
                        next_qs["offset"] = 0
                        if type(i_obj) is itertools.count and not init_offset:
                            logger.debug(f"init_offset: {type(i_obj)}")
                            init_offset = True
                        logger.debug(next_qs)
                except PixivError as e:
                    if "RemoteDisconnected" in str(e):
                        print_("[!] RemoteDisconnected.")
                    else:
                        logger.error(f"{type(e)}: {str(e)}")
                    time.sleep(1)
                except KeyError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    logger.error(data)
                    try:
                        message = data["error"]["message"]
                        if message == self.error_message["ratelimit"]:
                            print_("[!] RateLimit.")
                            time.sleep(180)
                        elif message == self.error_message["invalid"]:
                            self.access_token_get, self.expires_in = self.login()
                    except KeyError as e:
                        logger.error(f"{type(e)}: {str(e)}")
                        time.sleep(1)
                except TypeError as e:
                    logger.error(f"{type(e)}: {str(e)}")
                    info = f"PAGE: {self.option_['page']}\nILLUSTS: {len(self.queue['queue'])}"
                    print("")
                    print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
                    print("")
                    notification(info)
                    break
                else:
                    if next_qs is None:
                        logger.debug(f"{type(next_qs)}: {str(next_qs)}")
                        info = f"PAGE: {self.option_['page']}\nILLUSTS: {len(self.queue['queue'])}"
                        print("")
                        print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
                        print("")
                        notification(info)
                        break
                    time.sleep(1)
        info = f"USERS: {self.option_['users']}\nILLUSTS: {len(self.queue['queue'])}"
        print("")
        print(Colorate.Vertical(Colors.green_to_black, Box.Lines(info), 3))
        print("")
        notification(info)

    def novel(self, id):
        # 小説内容
        data = self.aapi.novel_detail(id)
        novel = data["novel"]
        user_name = novel["user"]["name"]
        title = novel["title"]
        caption = html.unescape(novel["caption"])
        # HTML改行タグを変換
        if "<br />" in caption:
            caption = caption.replace("<br />", "\n")
        novel_url = "https://pixiv.net/novel/show.php?id=%s" % novel["id"]
        image_url = novel["image_urls"]["large"]
        # 表紙をダウンロード
        # aapi.download()
        # 小説本文
        json_result = self.aapi.novel_text(id)
        text = json_result["novel_text"]
        data = [title, user_name, caption, novel_url, image_url, text]


def notification(message: str):
    def desktop(message: str):
        try:
            notice.notify(title="Notification", message=message, app_name="SUBARU", app_icon="./icon.ico")
        except Exception as e:
            logger.debug(f"{type(e)}: {str(e)}")

    def discord(message: str):
        if settings["notification"]["discord"]["webhookUrl"] != "":
            if settings["notification"]["discord"]["mention"]["enable"]:
                if settings["notification"]["discord"]["mention"]["discordId"] != "":
                    message = f"<@{settings['notification']['discord']['mention']['discordId']}>\n{message}"
            try:
                DiscordWebhook(url=settings["notification"]["discord"]["webhookUrl"], content=message).execute()
            except Exception as e:
                logger.debug(f"{type(e)}: {str(e)}")

    if settings["notification"]["enable"]:
        if settings["notification"]["desktop"]["enable"]:
            desktop(message)
        if settings["notification"]["discord"]["enable"]:
            discord(message)


def print_(text: str):
    print(Colorate.Vertical(Colors.green_to_black, Center.XCenter(text, spaces=spaces), 3))


def input_(text: str, hide_cursor=True):
    return Write.Input(Center.XCenter(text, spaces=spaces), Colors.green_to_black, interval=0, hide_cursor=hide_cursor)


def print_banner():
    System.Clear()
    print(Colorate.Vertical(Colors.green_to_black, Center.Center(banner, yspaces=2), 3))


def load_settings():
    try:
        with open("settings.toml", "rb") as f:
            settings = tomllib.load(f)
    except FileNotFoundError:
        import requests
        res = requests.get("https://raw.githubusercontent.com/k2angel/SUBARU/main/settings.toml")
        settings = tomllib.loads(res.text)
        with open("settings.toml", "w", encoding="utf-8") as f:
            print(res.text, f)
    except tomllib.TOMLDecodeError as e:
        print_(f"[!] settings.toml loading failed{str(e).replace('Unclosed array', '')}")
        input()
        exit()
    print_("[*] Load settings.")
    return settings


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
[r] Recent    [q] Queue      [R] Reload
"""
print_banner()
print("")
__version__ = "1.7.3"
System.Title(f"SUBARU v{__version__}")
spaces = len(Center.XCenter(menu).split("\n")[0])

os.chdir(os.path.dirname(os.path.abspath(__file__)))
logger = make_logger(__name__)
settings = load_settings()
try:
    client = Client(settings["refresh_token"])
except IndexError as e:
    logger.error(f"{type(e)}: {str(e)}")
    print_("[!] refresh token is nothing.")
    from pixiv_auth import login

    refresh_token = login()
    if refresh_token not in settings["refresh_token"]:
        settings["refresh_token"] = refresh_token
        with open("settings.toml", "wb") as f:
            tomli_w.dump(settings, f)
    client = Client(refresh_token)

console = Console()

if __name__ == "__main__":
    while True:
        print_banner()
        print_(menu)
        mode = input_("[SUBARU] > ")
        if mode == "d":
            print_banner()
            print("")
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
            else:
                try:
                    client.download()
                except Exception as e:
                    logger.error(f"{type(e)}: {str(e)}")
        elif mode == "b" or mode == "r":
            print_banner()
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
            print_banner()
            print("")
            word = input_("[WORD] > ", hide_cursor=False)
            if word.split():
                client.option()
                try:
                    with console.status("[bold green]Fetching data...") as status:
                        client.search(word)
                    print_("[*] Fetch done.")
                    client.download()
                except Exception as e:
                    logger.error(f"{type(e)}: {str(e)}")
        elif mode == "q":
            print_banner()
            print("")
            qd = client.queue_list
            if len(qd) != 0:
                ql = list()
                for i, key in zip(range(len(qd.keys())), qd.keys()):
                    qd_ = qd[key]
                    print_(
                        f"[{i + 1}] {qd_['time'].strftime('%Y-%m-%d %H:%M:%S')} | {qd_['name']} | {qd_['option']} | {qd_['size']}")
                    ql.append(key)
                try:
                    index = input_("[QUEUE] > ")
                    i = int(index)
                    if i == 0:
                        continue
                    client.queue = client.queue_list.pop(ql[i - 1])
                    pickle.dump(client.queue_list, open("./queue", "wb"))
                    try:
                        client.download()
                    except Exception as e:
                        logger.error(f"{type(e)}: {str(e)}")
                except ValueError:
                    pass
            else:
                print_("Not found queue.")
        elif mode == "R":
            print_banner()
            print("")
            settings = load_settings()
        elif mode == "e":
            print_("[*] Exit.")
            exit()
        input_("[*] Press ENTER to go back.")

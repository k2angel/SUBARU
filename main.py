import datetime
import math
import os
import queue
import re
import shutil
import threading
import time
import tomllib
import zipfile
from itertools import count
from logging import (DEBUG, INFO, FileHandler, Formatter, StreamHandler,
                     getLogger)

from PIL import Image, UnidentifiedImageError
from pixivpy3 import AppPixivAPI
from pixivpy3.utils import PixivError
from plyer import notification
from pystyle import *
from tqdm import tqdm


class Client:
    def __init__(self, refresh_token):
        self.aapi = AppPixivAPI()
        self.aapi.auth(refresh_token=refresh_token)
        print(self.aapi.access_token)

banner = """
   ______  _____  ___   ___  __  __
  / __/ / / / _ )/ _ | / _ \/ / / /
 _\ \/ /_/ / _  / __ |/ , _/ /_/ / 
/___/\____/____/_/ |_/_/|_|\____/  
"""

menu = """
[01] Download  [02] Bookmarks  [03] Search
[04] Recent    [05] Login      [06] Reload
"""

if __name__ == "__main__":
    System.Clear()
    print(Colorate.Vertical(Colors.green_to_black, banner, speed=3))
    print(Colorate.Vertical(Colors.green_to_black, menu, speed=3))
    Client("RKvLN4RDl50rdpN3kDLkiUw2riyZYATqENR0XyQxXTM")
    Client("aCBgRlNpLeJDnKzjo0OwvEYS3xgziShcCSsDg9f9PWE")
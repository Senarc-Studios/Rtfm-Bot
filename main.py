from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Pattern, Match, TypedDict

import traceback
import logging

from re import compile as re_compile, escape as re_escape, IGNORECASE
from os import listdir, getenv as os_getenv

from discord import Intents
from discord.ext import commands

from dotenv import load_dotenv
from aiohttp import ClientSession
from doc_search import AsyncScraper
from asqlite import connect as asqlite_connect

if TYPE_CHECKING:
    from typing_extensions import Self

    from discord import Message
    from discord.ext.commands.bot import PrefixType

    from asqlite import Connection, Cursor
    from sqlite3 import Row

    class RTFMLibraryData(TypedDict):
        name: str
        link: str


async def get_prefix(client: RTFMBot, message: Message) -> list[str]:
    extras: list[str] = ["rtfm*", "rm*", "r*"]
    comp: Pattern[str] = re_compile("^(" + "|".join(map(re_escape, extras)) + ").*", flags=IGNORECASE)
    match: Optional[Match[str]] = comp.match(message.content)

    if match is not None:
        extras.append(match.group(1))

    return commands.when_mentioned_or(*extras)(client, message)


class RTFMBot(commands.Bot):
    def __init__(self, *, command_prefix: PrefixType[Self], intents: Intents) -> None:
        super().__init__(command_prefix=command_prefix, intents=intents)

        # filled in by setup_hook
        self.db: Optional[Connection] = None
        self.session: Optional[ClientSession] = None
        self.rtfm_libraries: dict[str, str] = {}
        self.scraper: Optional[AsyncScraper] = None

    async def setup_hook(self) -> None:
        # load extensions
        for filename in listdir("./cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                except commands.errors.ExtensionError:
                    traceback.print_exc()

        # initialize global aiohttp session
        self.session = ClientSession()

        # load rtfm libraries
        self.db = await asqlite_connect("bot.db")
        main_cursor: Cursor = await self.db.cursor()
        result: Cursor = await main_cursor.execute("SELECT * FROM RTFM_DICTIONARY")

        rtfm_libraries: list[Row[str]] = await result.fetchall()
        self.rtfm_libraries = dict(rtfm_libraries)  # type: ignore # this is supported.

        # initialize scraper
        self.scraper = AsyncScraper(session=self.session)

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        if self.db:
            await self.db.close()
        await super().close()


bot = RTFMBot(command_prefix=get_prefix, intents=Intents(messages=True, message_content=True, guilds=True))


@bot.event
async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
    # from sys import exc_info as sys_exc_info
    # more_information = sys_exc_info()
    # error_wanted = traceback.format_exc()
    # default behaviour:
    traceback.print_exc()
    # print(more_information[0])


logging.basicConfig(level=logging.INFO)

load_dotenv()
bot.run(os_getenv("TOKEN"))

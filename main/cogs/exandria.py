#!/usr/bin/env python3
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                         Import
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
from __future__ import annotations

# Standard library imports
import logging
import random
import os

from typing import TYPE_CHECKING, Optional

# Third party imports
import asyncio
import discord
import pandas as pd

from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
from gspread import authorize
from gspread import Client as GSpreadClient

# Local application imports
from main.cogs.utils.config import Config
from main.cogs.utils.context import Context


if TYPE_CHECKING:
    from main.Zen import Zen
    from utils.context import Context

GuildChannel = discord.TextChannel | discord.VoiceChannel | discord.StageChannel | discord.CategoryChannel | discord.Thread

log = logging.getLogger('__name__')


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class SheetHandler:
    def __init__(self) -> None:
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        self._active = False
        self.credentials = None
        self.sheetClient = self._connect()

    def _connect(self) -> Optional[GSpreadClient]:
        if os.path.exists('./main/settings/credentials.json'):
            self.credentials = Credentials.from_service_account_file(
                './main/settings/credentials.json',
                scopes=self.SCOPES
            )
            self._active = True
        else:
            log.error("Unable to find credentials file. Aborting connection.")
            return None

        return authorize(self.credentials)

    def close(self):
        self.sheetClient.session.close()

    def get_data(
        self, sheet_id: str, worksheet_id: str | int = 0
    ) -> pd.DataFrame:
        sheet = self.sheetClient.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(
            worksheet_id
        ) if type(worksheet_id) == int else sheet.worksheet(worksheet_id)

        return pd.DataFrame(worksheet.get_all_records())

    async def get_participants(self, sheet_id: str, ) -> set[str]:
        df = self.get_data(sheet_id)
        participants = set(df.loc[:, "Discord Username"].to_list())
        return participants


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Main
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


class Exandria(commands.Cog):
    def __init__(self, bot: Zen) -> None:
        self.bot: Zen = bot
        self.sheet_config = bot.google_sheet_config
        self.SheetHandler = SheetHandler()
        self.log_sheets: dict[bool] = dict()
        self.get_sheet_updates.start()

        for key in self.sheet_config.all().keys():
            self.log_sheets[key] = True

    def cog_unload(self) -> None:
        self.get_sheet_updates.cancel()
        self.SheetHandler.close()

    async def cog_check(self, ctx: Context) -> bool:
        return ctx.guild.id in [719063399148814418, 739684323141353597]

    # -----------------------------------------------------------------------
    #                               Tasks
    @tasks.loop(minutes=45.0)
    async def get_sheet_updates(self):
        try:
            if self.log_sheets['themedWorldBuilding']:
                await self.handle_themed_event_data()
        except Exception as e:
            log.error(e, exc_info=True)
            pass

    @get_sheet_updates.before_loop
    async def before_sheet_updates(self):
        await self.bot.wait_until_ready()

    async def handle_themed_event_data(self) -> None:
        sheet_data = self.sheet_config.get('themedWorldBuilding')
        last_update_count = sheet_data.get('lastSent')
        df: pd.DataFrame = self.SheetHandler.get_data(sheet_data.get('id'))

        # Validation
        if df.shape[0] == last_update_count:
            return

        data = df.iloc[last_update_count:, 1:]

        # Get channel data
        guild = self.bot.get_guild(719063399148814418)
        channel = guild.get_channel(int(sheet_data.get('channel_id')))

        # Construct Embeds
        for idx, row in data.iterrows():
            msg = f"**Entry #{idx + 1}**  **By**: {row['Discord Username']}\n"
            msg += f"**Tags**: {row['Primary Tag']}, {row['Secondary Tags (Comma Separated)']}\n\n"

            try:
                # await channel.send(embed=e)
                await channel.send(content=msg)
                content = row["Entry"]
                content = [content[i:i+2000]
                           for i in range(0, len(content), 2000)]
                for c in content:
                    await channel.send(content=c)

                await channel.send(content="```\n.\n```")
            except Exception as e:
                log.error(e, exc_info=True)

        # Update last sent
        sheet_data['lastSent'] = df.shape[0]
        await self.sheet_config.put('themedWorldBuilding', sheet_data)

    # -----------------------------------------------------------------------
    #                               Commands
    @commands.command(name='start_theme')
    @commands.has_permissions(administrator=True)
    async def start_theme(self, ctx: Context, region: str) -> None:
        # Create content
        separator = '```\n.' + ('\n' * 50) + '.\n```'
        month = discord.utils.utcnow().strftime('%B %Y')
        content = f"`Month of {month} - Region {region.upper()}`\n"
        content += f"`Map -->` https://media.discordapp.net/attachments/725862865176625254/946156671405809754/exandria_themed_space.png"
        content += '\n`For event information check` --> <#970866227935334450>'

        # Send to channel
        await ctx.send(separator)
        await ctx.send(content)
        await asyncio.sleep(3)
        await ctx.send('```\n \n```')

        # Delete original message
        await ctx.message.delete()

    @commands.command(name='end_theme')
    @commands.has_permissions(administrator=True)
    async def end_theme(self, ctx: Context, region: str) -> None:
        guild = ctx.guild

        # Get data
        participants: list[str] = list(await self.SheetHandler.get_participants(
            self.sheet_config.get('themedWorldBuilding').get('id')
        ))
        num_participants = len(participants)
        winner_str = random.choice(participants)
        # participants = [(await self.bot.get_or_fetch_member(guild, p)).__str__() for p in participants]
        winner_user = (await self.bot.query_member_named(guild, winner_str))
        winner_user = winner_user.mention if winner_user is not None else winner_str

        # Content
        content = f'<@&980602495564939264> \n\n'
        content += f'`DRAW PRIZE GOES TO:` {winner_user}\n'
        content += f'`END OF REGION {region.upper()}. All submitted resources will be compiled into a document shortly and be available for consumption.`'
        content += f'\n\n`Thank you to everyone that participated.\n'
        content += f' Stats: {{participants: {num_participants}}}`\n'
        # content += f'`Participants: {", ".join(participants)}`'

        await ctx.send(content=content)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#                          Setup
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
async def setup(bot: Zen) -> None:
    await bot.add_cog(Exandria(bot))

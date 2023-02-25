"""Saves usernames associated with ID"""
import asyncio

import discord.errors
from discord.ext import commands
from discord.ext import tasks

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "user_names_table"
SETTINGS_COLUMNS = ("user_id", "user_name")


async def fetch_user_name(bot: commands.Bot, user_id: int):
    user_name = await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], user_id=user_id)
    if not user_name:
        print(f"Unable to find user with ID {user_id}. Attempting to fetch username...")
        await asyncio.sleep(5)
        try:
            user = await bot.fetch_user(user_id)
            if user:
                user_name = str(user)
            else:
                user_name = "<unknown-user>"
        except discord.errors.NotFound:
            user_name = "<unknown-user>"
        print(f"Saving user name for {user_id} as {user_name}")
        await save_user_name(user_id, user_name)
    return user_name


async def save_user_name(user_id: int, user_name: str):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], user_name, user_id=user_id)


#########################################

class UserNameData(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        self.save_user_names.start()

    @tasks.loop(hours=24)
    async def save_user_names(self):
        await asyncio.sleep(1800)
        for guild in self.bot.guilds:
            for member in guild.members:
                user_name = str(member).replace("'", "")
                await save_user_name(member.id, user_name)


async def setup(bot):
    await bot.add_cog(UserNameData(bot))

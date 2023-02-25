"""Regularly clear a channel."""
from datetime import datetime
from datetime import timedelta
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "channels_to_clear"
SETTINGS_COLUMNS = ("guild_id", "channel_list")


async def fetch_to_clear_channel_list(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id)


async def write_to_clear_channel_list(guild_id: int, channel_list: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], channel_list, guild_id=guild_id)


#########################################


class ChannelClearer(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        self.channel_clearer.start()

    async def cog_unload(self):
        self.channel_clearer.cancel()

    @discord.app_commands.command(
        name="_setup_clearer",
        description="Sets up a task that deletes a channels content every 24 hours.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_clearer(self, interaction: discord.Interaction, channel: discord.TextChannel):
        channels_to_clear = await fetch_to_clear_channel_list(interaction.guild_id)
        if channel.name in channels_to_clear:
            channels_to_clear.remove(channel.name)
            await interaction.response.send_message(f"Removed channel {channel.mention} from auto-clearer.",
                                                    ephemeral=True)
        else:
            channels_to_clear.append(channel.name)
            await interaction.response.send_message(f"Added channel {channel.mention} to auto-clearer.",
                                                    ephemeral=True)

        await write_to_clear_channel_list(interaction.guild_id, channels_to_clear)

    @tasks.loop(minutes=60)
    async def channel_clearer(self):
        await asyncio.sleep(500)

        def check_if_pin(msg: discord.Message):
            if msg.pinned:
                return False
            else:
                return True

        for guild in self.bot.guilds:
            channels_to_clear = await fetch_to_clear_channel_list(guild.id)
            for channel_name in channels_to_clear:
                channel: discord.TextChannel = discord.utils.get(guild.channels, name=channel_name)
                if not channel:
                    continue
                now = datetime.utcnow()
                two_weeks = timedelta(days=13)
                one_day = timedelta(hours=24)
                print(f"Purging channel {channel.name} in {guild.name}")
                purged_message = await channel.purge(limit=None, check=check_if_pin, oldest_first=True,
                                                     before=now - one_day, after=now - two_weeks)
                print(f"\tPurged {len(purged_message)} messages.")


async def setup(bot):
    await bot.add_cog(ChannelClearer(bot))

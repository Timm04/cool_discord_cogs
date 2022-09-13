"""Cog Description"""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks
from datetime import datetime
from datetime import timedelta


class ChannelClearer(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.channel_clearer.start()

    async def cog_unload(self):
        self.channel_clearer.cancel()

    @discord.app_commands.command(
        name="setup_clearer",
        description="Sets up a task that deletes a channels content every 24 hours.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def setup_clearer(self, interaction: discord.Interaction, channel: discord.TextChannel):
        channels_to_clear = await self.bot.open_json_file(interaction.guild, "channels_to_clear.json", list())
        if channel.name in channels_to_clear:
            channels_to_clear.remove(channel.name)
            await interaction.response.send_message(f"Removed channel {channel.mention} from auto-clearer.")
        else:
            channels_to_clear.append(channel.name)
            await interaction.response.send_message(f"Added channel {channel.mention} to auto-clearer.")

        await self.bot.write_json_file(interaction.guild, "channels_to_clear.json", channels_to_clear)

    @tasks.loop(minutes=60)
    async def channel_clearer(self):
        await asyncio.sleep(300)

        def check_if_pin(msg: discord.Message):
            if msg.pinned:
                return False
            else:
                return True

        for guild in self.bot.guilds:
            channels_to_clear = await self.bot.open_json_file(guild, "channels_to_clear.json", list())
            for channel_name in channels_to_clear:
                channel = discord.utils.get(guild.channels, name=channel_name)
                if not channel:
                    continue
                now = datetime.utcnow()
                two_weeks = timedelta(days=13)
                one_day = timedelta(hours=24)
                await channel.purge(limit=None, check=check_if_pin, oldest_first=True,
                                    before=now - one_day, after=now - two_weeks)


async def setup(bot):
    await bot.add_cog(ChannelClearer(bot))

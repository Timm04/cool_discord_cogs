"""Cog Description"""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks
import pickle
from datetime import timedelta
from datetime import datetime


async def process_dissoku(message: discord.Message):
    await asyncio.sleep(3)
    if not message.embeds:
        return False
    elif not message.embeds[0].fields:
        return False
    elif "をアップしたよ" in message.embeds[0].fields[0].name:
        return True
    else:
        return False


async def process_disboard(message: discord.Message):
    await asyncio.sleep(3)
    if not message.embeds:
        return False
    elif ":thumbsup:" in message.embeds[0].description:
        return True
    else:
        return False


class BumpReminder(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bump_bots = {761562078095867916: ("Dissoku", "`/dissoku up`", 60.0, process_dissoku),
                          302050872383242240: ("Disboard", "`/bump`", 120.0, process_disboard)}

    async def cog_load(self):
        for guild in self.bot.guilds:
            guild: discord.Guild
            bump_channel_name = await self.bot.open_json_file(guild, "bump_channel_name.json", str())
            bump_channel = discord.utils.get(guild.channels, name=bump_channel_name)
            if not bump_channel:
                continue

            for bump_bot_id in self.bump_bots:
                bump_bot = discord.utils.get(guild.members, id=bump_bot_id)
                if not bump_bot:
                    continue

                loop = asyncio.get_running_loop()
                loop.create_task(self.bump_reminder(bump_bot, bump_channel))

    async def save_time(self, bump_bot):
        wait_time = timedelta(minutes=self.bump_bots[bump_bot.id][2])
        next_bump_time = datetime.utcnow() + wait_time

        with open(f"data/{bump_bot.guild.id}/time_until_next_bump_{self.bump_bots[bump_bot.id][0]}", "wb") as date_file:
            pickle.dump(next_bump_time, date_file)

    async def load_time(self, bump_bot):
        try:
            with open(f"data/{bump_bot.guild.id}/time_until_next_bump_{self.bump_bots[bump_bot.id][0]}",
                      "rb") as date_file:
                next_bump_time = pickle.load(date_file)
                time_difference = next_bump_time - datetime.utcnow()
                minutes_left = int(time_difference.total_seconds() / 60)

                if minutes_left > self.bump_bots[bump_bot.id][2] or minutes_left < 1:
                    minutes_left = 1
        except FileNotFoundError:
            minutes_left = 1

        return minutes_left

    async def bump_reminder(self, bump_bot, bump_channel):

        def check_if_bot(message: discord.Message):
            if message.author == bump_bot and message.guild == bump_bot.guild and message.interaction:
                return True

        minutes_until_next_bump = await self.load_time(bump_bot)
        while True:
            try:
                bot_message = await self.bot.wait_for('message', check=check_if_bot,
                                                      timeout=minutes_until_next_bump * 60)
            except asyncio.TimeoutError:
                await bump_channel.send(f"Bump now with {self.bump_bots[bump_bot.id][1]}")
                minutes_until_next_bump = self.bump_bots[bump_bot.id][2]
                continue
            is_bump = await self.bump_bots[bump_bot.id][3](bot_message)
            if is_bump:
                await self.save_time(bump_bot)
                minutes_until_next_bump = await self.load_time(bump_bot)
                success_member = bot_message.interaction.user
                await bump_channel.send(f"{success_member.mention} Thanks for bumping!",
                                        allowed_mentions=discord.AllowedMentions.none())
            else:
                minutes_until_next_bump = await self.load_time(bump_bot)

    @discord.app_commands.command(
        name="set_bump_channel",
        description="Set the channel in which bump reminders should be dispatched.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def set_bump_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.bot.write_json_file(interaction.guild, "bump_channel_name.json", channel.name)
        await interaction.response.send_message(f"Set bump channel to {channel.name}")


async def setup(bot):
    await bot.add_cog(BumpReminder(bot))

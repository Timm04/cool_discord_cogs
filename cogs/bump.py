"""Cog that enables bump reminders for Disboard and Dissoku. Can be expanded to include more bots."""
import asyncio
from datetime import datetime
from datetime import timedelta

import discord
from discord.ext import commands
from discord.ext import tasks

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "bump_settings"
SETTINGS_COLUMNS = ("guild_id", "bump_channel_name", "bump_role_name", "last_disboard_bump", "last_dissoku_bump",
                    "leaderboard_activated", "bump_leaderboard")


async def save_bump_channel_name(guild_id: int, channel: discord.TextChannel):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], channel.name, guild_id=guild_id)


async def load_bump_channel_name(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id)


async def save_last_bump_time(guild_id: int, bot_column_index: int, time_string: str):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[bot_column_index],
                                       time_string, guild_id=guild_id)


async def load_last_bump_time(guild_id: int, bot_column_index: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[bot_column_index], guild_id=guild_id)


async def save_bump_role_name(guild_id: int, role: discord.Role):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], role.name, guild_id=guild_id)


async def load_bump_role_name(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id)


async def toggle_leaderboard(guild_id: int, leaderboard_active: bool):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[5],
                                       leaderboard_active, guild_id=guild_id)


async def load_leaderboard_active(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[5], guild_id=guild_id)


async def save_leaderboard(guild_id: int, leaderboard: dict):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[6], leaderboard, guild_id=guild_id)


async def load_leaderboard(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[6],
                                             guild_id=guild_id, default_type=dict)


#########################################

# Save and load last bump time across bot restarts

async def save_time(bump_bot: discord.Member):
    wait_time = timedelta(minutes=BUMP_BOTS[bump_bot.id][2])
    next_bump_time = datetime.utcnow() + wait_time
    next_bump_time_string = next_bump_time.strftime("%Y-%m-%d %H:%M:%S")
    bot_column_index = BUMP_BOTS[bump_bot.id][4]
    await save_last_bump_time(bump_bot.guild.id, bot_column_index, next_bump_time_string)


async def load_time(bump_bot: discord.Member):
    bot_column_index = BUMP_BOTS[bump_bot.id][4]
    next_bump_time_string = await load_last_bump_time(bump_bot.guild.id, bot_column_index)
    if not next_bump_time_string:
        next_bump_time_string = "2022-01-01 01:01:01"
    next_bump_time = datetime.strptime(next_bump_time_string, "%Y-%m-%d %H:%M:%S")
    if not next_bump_time:
        minutes_left = 1
    else:
        time_difference = next_bump_time - datetime.utcnow()
        minutes_left = int(time_difference.total_seconds() / 60)

    if minutes_left > BUMP_BOTS[bump_bot.id][2] or minutes_left < 1:
        minutes_left = 1

    return minutes_left


#########################################

# Determine if message by bots is a bump or not.

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


#########################################

# Static bump bot information

BUMP_BOTS = {761562078095867916: ("Dissoku", "`/dissoku up`", 61.0, process_dissoku, 4),
             302050872383242240: ("Disboard", "`/bump`", 121.0, process_disboard, 3)}


#########################################

async def load_bump_settings(guild: discord.Guild):
    bump_channel_name = await load_bump_channel_name(guild.id)
    if not bump_channel_name:
        return False

    bump_channel = discord.utils.get(guild.channels, name=bump_channel_name)
    if not bump_channel:
        return False

    bump_role_name = await load_bump_role_name(guild.id)
    bump_role = discord.utils.get(guild.roles, name=bump_role_name)

    leaderboard_active = await load_leaderboard_active(guild.id)
    if not leaderboard_active:
        leaderboard_active = False

    return bump_channel, bump_role, leaderboard_active


async def increment_leaderboard_points(bump_member: discord.Member):
    bump_leaderboard: dict = await load_leaderboard(bump_member.guild.id)
    member_id = str(bump_member.id)
    old_data = bump_leaderboard.get(member_id, (str(bump_member), 0))
    old_points = old_data[1]
    new_points = old_points + 1
    new_data = (str(bump_member), new_points)
    bump_leaderboard[member_id] = new_data
    await save_leaderboard(bump_member.guild.id, bump_leaderboard)
    return old_points, new_points


async def make_leaderboard_post(bump_channel: discord.TextChannel, past_bot_pins: list, embed: discord.Embed,
                                current_index: int):
    try:
        current_pin: discord.Message = past_bot_pins[current_index]
    except IndexError:
        current_pin = await bump_channel.send("Bump Leaderboard")
        await current_pin.pin()

    await current_pin.edit(content="", embed=embed)


#########################################


class BumpReminder(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tasks = []

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        self.update_leaderboards.start()

        for guild in self.bot.guilds:

            bump_settings = await load_bump_settings(guild)
            if not bump_settings:
                continue

            for bump_bot_id in BUMP_BOTS:
                bump_bot = discord.utils.get(guild.members, id=bump_bot_id)
                if not bump_bot:
                    continue

                loop = asyncio.get_running_loop()

                task = loop.create_task(self.bump_reminder(bump_bot))
                self.tasks.append(task)

    async def cog_unload(self):
        for task in self.tasks:
            task.cancel()

        self.update_leaderboards.cancel()

    async def bump_reminder(self, bump_bot):

        def check_if_bot(message: discord.Message):
            if message.author == bump_bot and message.guild == bump_bot.guild and message.interaction:
                return True

        minutes_until_next_bump = await load_time(bump_bot)
        while True:

            bump_settings = await load_bump_settings(bump_bot.guild)
            if not bump_settings:
                return
            else:
                bump_channel, bump_role, leaderboard_active = bump_settings

            try:
                bot_message = await self.bot.wait_for('message', check=check_if_bot,
                                                      timeout=minutes_until_next_bump * 60)
            except asyncio.TimeoutError:
                bump_message = f"Bump now with {BUMP_BOTS[bump_bot.id][1]}"
                if bump_role:
                    bump_message = bump_role.mention + " " + bump_message
                await bump_channel.send(bump_message)
                minutes_until_next_bump = BUMP_BOTS[bump_bot.id][2]
                continue
            is_bump = await BUMP_BOTS[bump_bot.id][3](bot_message)
            if is_bump:
                await save_time(bump_bot)
                minutes_until_next_bump = await load_time(bump_bot)
                bump_member = bot_message.interaction.user
                bump_success_string = f"{bump_member.mention} Thanks for bumping!"

                if leaderboard_active:
                    old_points, new_points = await increment_leaderboard_points(bump_member)
                    bump_success_string = bump_success_string + f"\nIncreased your leaderboard points from " \
                                                                f"**{old_points}** to **{new_points}**"

                await bump_channel.send(bump_success_string,
                                        allowed_mentions=discord.AllowedMentions.none())
            else:
                minutes_until_next_bump = await load_time(bump_bot)

    @discord.app_commands.command(
        name="_setup_bump_reminder",
        description="Set the channel in which bump reminders should be dispatched.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(bump_channel="Channel to which the bump reminder should be dispatched.",
                                   activate_leaderboard="Whether or not a leaderboard should be created, keeping track"
                                                        "of users bump count.",
                                   mention_role="What role should be mentioned on bump reminders, if any")
    async def setup_bump_reminder(self, interaction: discord.Interaction,
                                  bump_channel: discord.TextChannel,
                                  activate_leaderboard: bool,
                                  mention_role: discord.Role = None):
        await save_bump_channel_name(interaction.guild_id, bump_channel)
        await toggle_leaderboard(interaction.guild_id, activate_leaderboard)
        if mention_role:
            await save_bump_role_name(interaction.guild_id, mention_role)

        await interaction.response.send_message(f"Set bump reminders with the following settings:\n"
                                                f"Bump Channel: {bump_channel.mention}\n"
                                                f"Leaderboard activated: {activate_leaderboard}\n"
                                                f"Role mention activated: "
                                                f"{False if not mention_role else mention_role.mention}",
                                                ephemeral=True)

        await self.bot.reload_extension("cogs.bump")

    async def update_leaderboard(self, bump_channel: discord.TextChannel):
        bump_leaderboard: dict = await load_leaderboard(bump_channel.guild.id)
        if not bump_leaderboard:
            return
        sorted_ids = sorted(bump_leaderboard.items(), key=lambda key_value: key_value[1], reverse=True)
        past_bot_pins = [pin for pin in await bump_channel.pins() if pin.author.id == self.bot.user.id]

        leaderboard_embed = discord.Embed(title="Bump Leaderboard")
        embed_description_strings = []
        current_embed_index = 0
        for index, user_info in enumerate(sorted_ids):
            user_id = int(user_info[0])
            member = bump_channel.guild.get_member(user_id)
            points = user_info[1][1]
            if not member:
                user_mention = user_info[1][0]
            else:
                user_mention = member.mention
            leaderboard_line = f"{index + 1}. {user_mention} **{points}点**"
            embed_description_strings.append(leaderboard_line)
            if len('\n'.join(embed_description_strings)) > 4000:
                embed_description_strings.pop()
                embed_description = '\n'.join(embed_description_strings)
                leaderboard_embed.description = embed_description
                await make_leaderboard_post(bump_channel, past_bot_pins, leaderboard_embed, current_embed_index)

                leaderboard_embed = discord.Embed(title="Bump Leaderboard")
                embed_description_strings = [leaderboard_line]
                current_embed_index += 1

        if embed_description_strings:
            embed_description = '\n'.join(embed_description_strings)
            leaderboard_embed.description = embed_description
            await make_leaderboard_post(bump_channel, past_bot_pins, leaderboard_embed, current_embed_index)

    @tasks.loop(minutes=60.0)
    async def update_leaderboards(self):
        await asyncio.sleep(600)
        for guild in self.bot.guilds:
            active = await load_leaderboard_active(guild.id)
            if not active:
                continue
            bump_channel_name = await load_bump_channel_name(guild.id)
            bump_channel = discord.utils.get(guild.channels, name=bump_channel_name)
            if not bump_channel:
                continue
            print(f"Updating bump leaderboard for guild {guild.name}")
            await self.update_leaderboard(bump_channel)


async def setup(bot):
    await bot.add_cog(BumpReminder(bot))

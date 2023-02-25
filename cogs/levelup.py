"""Rank system interfacing with Kotoba bot"""
import asyncio
import os
import re

import aiohttp
import discord
from discord.ext import commands

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "level_up_settings"
SETTINGS_COLUMNS = ("guild_id", "rank_system", "success_announce_channel", "failure_announce_channels")


async def fetch_rank_system(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id,
                                             default_type=list)


async def fetch_announce_channel(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id,
                                             default_type=str)


async def fetch_failure_channels(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3], guild_id=guild_id,
                                             default_type=list)


async def write_rank_system(guild_id: int, rank_system: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], rank_system, guild_id=guild_id)


async def write_announce_channel(guild_id: int, announce_channel_name: str):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], announce_channel_name,
                                       guild_id=guild_id)


async def write_failure_channels(guild_id: int, failure_channels: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3], failure_channels, guild_id=guild_id)


#########################################

KOTOBA_BOT_ID = 251239170058616833


#########################################

# Utility functions

async def give_reward_role(member, role_name_to_give, role_name_to_remove=None):
    """Gives and removes a role from the role name."""
    role_to_give = discord.utils.get(member.guild.roles, name=role_name_to_give)
    role_to_remove = None
    if role_name_to_remove:
        role_to_remove = discord.utils.get(member.guild.roles, name=role_name_to_remove)
    if role_to_give:
        await member.add_roles(role_to_give)
    if role_to_remove:
        await member.remove_roles(role_to_remove)


async def verify_quiz_settings(user_rank_data, quiz_data, member: discord.Member):
    """Ensures a user didn't use cheat settings for the quiz."""
    (quiz_name, answer_count, answer_time_limit, font,
     font_size, role_name_to_get, role_name_to_lose, fail_count, command, file_path) = user_rank_data

    try_again_line = f"\nUse the following command to try again: `{command}`"

    user_count = len(quiz_data["participants"])
    if user_count > 1:
        return False, "Quiz failed due to multiple people participating." + try_again_line

    shuffle = quiz_data["settings"]["shuffle"]
    if not shuffle:
        return False, "Quiz failed due to the shuffle setting being activated." + try_again_line

    is_loaded = quiz_data["isLoaded"]
    if is_loaded:
        return False, "Quiz failed due to being loaded." + try_again_line

    for deck in quiz_data["decks"]:
        if deck["mc"]:
            return False, "Quiz failed due to being set to multiple choice." + try_again_line

    for deck in quiz_data["decks"]:
        try:
            if deck["startIndex"]:
                return False, "Quiz failed due to having a start index." + try_again_line
        except KeyError:
            pass
        try:
            if deck["endIndex"]:
                return False, "Quiz failed due to having an end index." + try_again_line
        except KeyError:
            pass

    if answer_count != quiz_data["settings"]["scoreLimit"]:
        return False, "Set score limit and required score limit don't match." + try_again_line

    if answer_time_limit != quiz_data["settings"]["answerTimeLimitInMs"]:
        return False, "Set answer time does match required answer time." + try_again_line

    if font != "any" and font != quiz_data["settings"]["font"]:
        return False, "Set font does not match required font." + try_again_line

    if font_size != quiz_data["settings"]["fontSize"]:
        return False, "Set font size does not match required font size." + try_again_line

    failed_question_count = len(quiz_data["questions"]) - quiz_data["scores"][0]["score"]
    if failed_question_count > fail_count:
        return False, "Failed too many questions." + try_again_line

    if answer_count != quiz_data["scores"][0]["score"]:
        return False, "Not enough questions answered." + try_again_line

    combined_name = " + ".join([deck["name"] for deck in quiz_data["decks"]])

    return True, f"{member.mention} has passed the {combined_name}!" \
                 f"\nUse `/levelup` to get the next level up command."


async def verify_if_rank_quiz(member: discord.Member, quiz_data):
    """Determines if a quiz is a rank quiz. If so returns the rank data for the reward rank."""
    rank_system = await fetch_rank_system(member.guild.id)
    user_rank_data = False

    # Get corresponding data.
    for rank_data in rank_system:
        (quiz_name, answer_count, answer_time_limit, font,
         font_size, role_name_to_get, role_name_to_lose, fail_count, command, file_path) = rank_data
        for role in member.roles:
            if role.name == role_name_to_lose:
                user_rank_data = rank_data

    if not user_rank_data:
        return False

    # Determine if current quiz is the correct one
    deck_strings = []
    for deck in quiz_data["decks"]:
        try:
            deck_strings.append(deck["shortName"])
        except KeyError:
            return  # Review quiz without deck name
    combined_deck_string = "+".join(deck_strings)

    (quiz_name, answer_count, answer_time_limit, font,
     font_size, role_name_to_get, role_name_to_lose, fail_count, command, file_path) = user_rank_data

    if combined_deck_string == quiz_name:
        return user_rank_data
    else:
        return False


async def get_quiz_id(message: discord.Message):
    """Extract the ID of a quiz to use with the API."""
    try:
        if "Ended" in message.embeds[0].title:
            return re.findall(r"game_reports/([\da-z]*)", message.embeds[0].fields[-1].value)[0]
    except IndexError:
        return False
    except TypeError:
        return False


async def fetch_user_rank_name(member: discord.Member):
    rank_system = await fetch_rank_system(member.guild.id)
    rank_names = set([rank_info[5] for rank_info in rank_system]) | set(rank_info[4] for rank_info in rank_system)
    user_rank_names = [role.name for role in member.roles]
    user_rank_name = list(rank_names & set(user_rank_names))[0]
    return user_rank_name


#########################################


class LevelUp(commands.Cog):

    def __init__(self, bot):
        self.aiosession = None
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        self.aiosession = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.aiosession.close()

    @discord.app_commands.command(
        name="_add_ordered_rank",
        description="Add a role to the list of ordered attainable quiz roles."
                    "\nPreviously added has to be cleared first.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(quiz_name="Quiz short name. + inbetween for multiple quizzes.",
                                   answer_count="Answer count",
                                   answer_time_limit="Seconds to answer within",
                                   font="Font required",
                                   role_to_get="Reward role",
                                   role_to_lose="Role that should be stripped",
                                   fail_count="Tolerated failure count")
    @discord.app_commands.choices(
        font=[discord.app_commands.Choice(name="No font requirement", value="any"),
              discord.app_commands.Choice(name="AC Gyousho (Medium difficult)", value="AC Gyousho"),
              discord.app_commands.Choice(name="Aoyagi Kouzan Gyousho (Hard difficulty)",
                                          value="Aoyagi Kouzan Gyousho")],
        answer_time_limit=[discord.app_commands.Choice(name="5 Seconds", value=5001),
                           discord.app_commands.Choice(name="6 Seconds", value=6001),
                           discord.app_commands.Choice(name="7 Seconds", value=7001),
                           discord.app_commands.Choice(name="8 Seconds", value=8001),
                           discord.app_commands.Choice(name="9 Seconds", value=9001),
                           discord.app_commands.Choice(name="10 Seconds", value=10001),
                           discord.app_commands.Choice(name="11 Seconds", value=11001),
                           discord.app_commands.Choice(name="12 Seconds", value=12001)],
        font_size=[discord.app_commands.Choice(name="30px", value=30),
                   discord.app_commands.Choice(name="35px", value=35),
                   discord.app_commands.Choice(name="40px", value=40),
                   discord.app_commands.Choice(name="60px", value=60),
                   discord.app_commands.Choice(name="80px", value=80)])
    @discord.app_commands.default_permissions(administrator=True)
    async def add_ordered_rank(self, interaction: discord.Interaction, quiz_name: str, answer_count: int,
                               answer_time_limit: int, font: str, font_size: int, role_to_get: discord.Role,
                               role_to_lose: discord.Role, fail_count: int, file_to_send: discord.Attachment = None):

        font_mapping = {
            "any": 1,
            "Aoyagi Kouzan Gyousho": 7,
            "AC Gyousho": 10,
        }

        command = f"k!quiz {quiz_name} nodelay atl={int(answer_time_limit / 1000)} {answer_count} " \
                  f"font={font_mapping[font]} size={font_size} mmq={fail_count + 1}"

        if file_to_send:
            file_path = f"data/server_files/{file_to_send.filename}"
            await file_to_send.save(file_path)
        else:
            file_path = None

        quiz_data = (quiz_name, answer_count, answer_time_limit, font, font_size, role_to_get.name, role_to_lose.name,
                     fail_count, command, file_path)

        old_rank_system = await fetch_rank_system(interaction.guild_id)
        new_rank_system = list()

        # Avoid duplicates
        for rank in old_rank_system:
            if not rank[0] == quiz_name:
                new_rank_system.append(rank)

        new_rank_system.append(quiz_data)
        await write_rank_system(interaction.guild_id, new_rank_system)

        await interaction.response.send_message(f"Added {quiz_name} ordered quiz with the following command:"
                                                f"\n`{command}`"
                                                f"\n The role that should be rewarded is `{role_to_get.name}` and "
                                                f"the role that should be removed is `{role_to_lose.name}`")

    @discord.app_commands.command(
        name="_set_quiz_announce_channel",
        description="Set the channel where passed quizzes should be announced.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="The channel in which people passing the quizzes should be announced.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_quiz_announce_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await write_announce_channel(interaction.guild_id, channel.name)
        await interaction.response.send_message(
            f"Updated the announce channel for passed quizzes to {channel.mention}.")

    @discord.app_commands.command(
        name="_toggle_quiz_failure_message",
        description="Toggle whether the bot should say why a quiz failed in a channel.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="Channel in which the bot should say why a quiz failed.")
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_quiz_failure_message(self, interaction: discord.Interaction, channel: discord.TextChannel):
        channel_names = await fetch_failure_channels(interaction.guild_id)
        if channel.name in channel_names:
            channel_names.remove(channel.name)
            await write_failure_channels(interaction.guild_id, channel_names)
            await interaction.response.send_message(f"Deactivated failure messages for the channel {channel.mention}")
        else:
            channel_names.append(channel.name)
            await write_failure_channels(interaction.guild_id, channel_names)
            await interaction.response.send_message(f"Activated failure messages for the channel {channel.mention}")

    @discord.app_commands.command(
        name="levelup",
        description="Get the next levelup command.")
    @discord.app_commands.guild_only()
    async def levelup(self, interaction: discord.Interaction):
        user_rank_data = None
        rank_system = await fetch_rank_system(interaction.guild_id)
        for rank_data in rank_system:
            (quiz_name, answer_count, answer_time_limit, font,
             font_size, role_name_to_get, role_name_to_lose, fail_count, command, file_path) = rank_data
            for role in interaction.user.roles:
                if role.name == role_name_to_lose:
                    user_rank_data = rank_data

        if user_rank_data:
            (quiz_name, answer_count, answer_time_limit, font,
             font_size, role_name_to_get, role_name_to_lose, fail_count, command, file_path) = user_rank_data
            await interaction.response.send_message(command, ephemeral=True)
        else:
            await interaction.response.send_message("There is no level-up command for your current ranks.",
                                                    ephemeral=True)

    @discord.app_commands.command(
        name="levelup_all",
        description="See all level up commands.")
    @discord.app_commands.guild_only()
    async def levelup_all(self, interaction: discord.Interaction):
        rank_system = await fetch_rank_system(interaction.guild_id)
        command_list = [rank_data[-2] for rank_data in rank_system]
        await interaction.response.send_message("\n".join(command_list), ephemeral=True)

    @discord.app_commands.command(
        name="rankusers",
        description="See all users with a specific role.")
    @discord.app_commands.describe(role="Role for which all members should be displayed.")
    @discord.app_commands.guild_only()
    async def rankusers(self, interaction: discord.Interaction, role: discord.Role):
        member_count = len(role.members)
        mention_string = []
        for member in role.members:
            mention_string.append(member.mention)
        if len(" ".join(mention_string)) < 500:
            mention_string.append(f"\nA total {member_count} members have the role {role.mention}.")
            await interaction.response.send_message(" ".join(mention_string),
                                                    allowed_mentions=discord.AllowedMentions.none())
        else:
            member_string = [str(member) for member in role.members]
            member_string.append(f"\nTotal {member_count} members.")
            with open("data/rank_user_count.txt", "w") as text_file:
                text_file.write("\n".join(member_string))
            await interaction.response.send_message("Here you go:",
                                                    file=discord.File("data/rank_user_count.txt"))
            os.remove("data/rank_user_count.txt")

    @discord.app_commands.command(
        name="ranktable",
        description="Get an overview of the amount of users in each rank.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def ranktable(self, interaction: discord.Interaction):
        rank_system = await fetch_rank_system(interaction.guild_id)
        role_name_list = []
        for rank_data in rank_system:
            (quiz_name, answer_count, answer_time_limit, font,
             font_size, role_name_to_get, role_name_to_lose, fail_count, command, file_path) = rank_data
            if role_name_to_lose not in role_name_list:
                role_name_list.append(role_name_to_lose)
            if role_name_to_get not in role_name_list:
                role_name_list.append(role_name_to_get)

        rank_roles = [discord.utils.get(interaction.guild.roles, name=role_name) for role_name in role_name_list]
        duplicate_role_members = []
        missing_role_members = []
        total_members = 0
        rank_count = dict()
        for member in interaction.guild.members:
            role_count = 0
            if member.bot:
                continue
            total_members += 1
            for role in member.roles:
                if role in rank_roles:
                    role_count += 1
                    rank_count[role.name] = rank_count.get(role.name, 0) + 1
            if role_count == 0:
                missing_role_members.append(member)
            elif role_count > 1:
                duplicate_role_members.append(member)

        ranktable_message = ["**Role Distribution**"]
        for role_name in role_name_list:
            ranktable_message.append(f"{role_name}: {rank_count[role_name]}")

        if duplicate_role_members:
            duplicate_mention_string = " ".join([member.mention for member in duplicate_role_members])
            ranktable_message.append(f"\nMembers with duplicate roles:\n {duplicate_mention_string}")

        if missing_role_members:
            missing_mention_string = " ".join([member.mention for member in missing_role_members])
            ranktable_message.append(f"\nMembers with missing roles:\n {missing_mention_string}")

        ranktable_message.append(f"\nTotal member count: {total_members}")
        ranktable_string = "\n".join(ranktable_message)

        await interaction.response.send_message(ranktable_string,
                                                allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener(name="on_message")
    async def level_up_routine(self, message: discord.Message):
        if not message.author.id == KOTOBA_BOT_ID:
            return

        quiz_id = await get_quiz_id(message)
        if not quiz_id:
            return

        quiz_data = await self.extract_quiz_data_from_id(quiz_id)

        member = message.guild.get_member(int(quiz_data["participants"][0]["discordUser"]["id"]))
        user_rank_data = await verify_if_rank_quiz(member, quiz_data)

        if user_rank_data:
            passed, info = await verify_quiz_settings(user_rank_data, quiz_data, member)
        else:
            passed = False
            info = "Wrong quiz for your current level."

        if passed:
            (quiz_name, answer_count, answer_time_limit, font,
             font_size, role_name_to_get, role_name_to_lose, fail_count, command, file_path) = user_rank_data
            announce_channel_name = await fetch_announce_channel(message.guild.id)
            if announce_channel_name:
                announce_channel = discord.utils.get(message.guild.channels, name=announce_channel_name)
                await announce_channel.send(info, file=discord.File(file_path))
            await give_reward_role(member, role_name_to_get, role_name_to_lose)
        else:
            failure_channel_names = await fetch_failure_channels(message.guild.id)
            if message.channel.name in failure_channel_names:
                await message.channel.send(f"{member.mention} {info}")

    async def extract_quiz_data_from_id(self, quiz_id):
        jsonurl = f"https://kotobaweb.com/api/game_reports/{quiz_id}"
        await asyncio.sleep(1)
        async with self.aiosession.get(jsonurl) as resp:
            return await resp.json()


async def setup(bot):
    await bot.add_cog(LevelUp(bot))

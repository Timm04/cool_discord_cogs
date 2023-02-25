"""Create and backup emoji"""
import asyncio
import os
import re
import shutil

import discord
from discord.ext import commands

from . import data_management

#########################################

increment_lock = asyncio.Lock()

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "emoji_usage"
SETTINGS_COLUMNS = ("guild_id", "emoji_usage_data")


async def fetch_emoji_statistics(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id,
                                             default_type=dict)


async def write_emoji_statistics(guild_id: int, emoji_statistics: dict):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], emoji_statistics,
                                       guild_id=guild_id)


#########################################

class EmojiManager(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)

    @discord.app_commands.command(
        name="add_emoji",
        description="Upload an emoji to the server.")
    @discord.app_commands.describe(emoji_name="The name of the emoji.",
                                   emoji_file="The emoji image.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def add_emoji(self, interaction: discord.Interaction, emoji_name: str, emoji_file: discord.Attachment):
        await interaction.response.defer()

        if emoji_file.size > 33554432:
            await interaction.edit_original_response(content="File size is too large.")
            return

        if emoji_file.width != emoji_file.height:
            await interaction.edit_original_response(content="Emoji size and width have to match.")
            return

        emoji_bytes = await emoji_file.read()
        custom_emoji = await interaction.guild.create_custom_emoji(name=emoji_name, image=emoji_bytes,
                                                                   reason=f"Custom emoji by {str(interaction.user)}")
        await interaction.edit_original_response(content=f"Uploaded your emoji: {str(custom_emoji)}")

    @commands.Cog.listener(name="on_reaction_add")
    async def emoji_usage_counter_reaction(self, reaction: discord.Reaction, member: discord.Member):
        if not reaction.message.guild:
            return
        async with increment_lock:
            if reaction.emoji in reaction.message.guild.emojis:
                emoji_usage_dict = await fetch_emoji_statistics(member.guild.id)
                emoji_usage_dict[reaction.emoji.name] = emoji_usage_dict.get(reaction.emoji.name, 0) + 1
                await write_emoji_statistics(member.guild.id, emoji_usage_dict)

    @commands.Cog.listener(name="on_message")
    async def emoji_usage_counter_message(self, message: discord.Message):
        if not message.guild:
            return
        emoji_strings = re.findall(r"<:(.+?):\d+>", message.content)
        unique_emoji_strings = set(emoji_strings)
        if unique_emoji_strings:
            for emoji_string in unique_emoji_strings:
                emoji: discord.Emoji = discord.utils.get(message.guild.emojis, name=emoji_string)
                if emoji:
                    async with increment_lock:
                        emoji_usage_dict = await fetch_emoji_statistics(message.guild.id)
                        emoji_usage_dict[emoji.name] = emoji_usage_dict.get(emoji.name, 0) + 1
                        await write_emoji_statistics(message.guild.id, emoji_usage_dict)

    @discord.app_commands.command(
        name="emoji_usage",
        description="Send out emoji usage statistics for the server.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(send_messages=True)
    async def emoji_usage(self, interaction: discord.Interaction):
        emoji_usage_dict = await fetch_emoji_statistics(interaction.guild_id)
        emoji_report_lines = []

        for emoji_data in sorted(emoji_usage_dict.items(), key=lambda x: x[1], reverse=True):
            emoji_name, uses = emoji_data
            emoji = discord.utils.get(interaction.guild.emojis, name=emoji_name)
            if emoji:
                emoji_line = f"{str(emoji)} {uses}回"
                emoji_report_lines.append(emoji_line)

        for emoji in interaction.guild.emojis:
            if emoji.name not in emoji_usage_dict:
                emoji_line = f"{str(emoji)} 0回"
                emoji_report_lines.append(emoji_line)

        emoji_embed = discord.Embed(title=f"{interaction.guild.name} Emoji Usage Statistics.")
        current_field = []
        counter = 1
        for emoji_line in emoji_report_lines:
            current_field.append(f"{counter}. {emoji_line}")
            counter += 1
            if len("\n".join(current_field)) > 950:
                emoji_embed.add_field(name="Emoji:", value="\n".join(current_field))
                current_field = []
                if len(emoji_embed) > 5000:
                    break
        if current_field:
            emoji_embed.add_field(name="Emoji:", value="\n".join(current_field))

        await interaction.response.send_message(embed=emoji_embed, ephemeral=True)

    @discord.app_commands.command(
        name="_backup_emoji",
        description="Download all emoji with usage statistics. WARNING: A lot of API calls.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def backup_emoji(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if os.path.isdir(f"data/{interaction.guild.id}_emoji_backup"):
            pass
        else:
            os.mkdir(f"data/{interaction.guild.id}_emoji_backup")

        for emoji in interaction.guild.emojis:
            emoji_save_path = f"data/{interaction.guild.id}_emoji_backup/{emoji.name + emoji.url[-4:]}"
            if os.path.exists(emoji_save_path):
                continue
            else:
                await asyncio.sleep(2)
                await emoji.save(f"data/{interaction.guild.id}_emoji_backup/{emoji.name + emoji.url[-4:]}")
                print(f"Downloaded emoji to: data/{interaction.guild.id}_emoji_backup/{emoji.name + emoji.url[-4:]}")
        await interaction.edit_original_response(content=f"{interaction.user.mention} Finished downloading emoji.")

        def create_emoji_zip():
            path_to_folder = f"data/{interaction.guild.id}_emoji_backup"
            file_to_save = f"data/{interaction.guild.id}_emoji_backup"
            shutil.make_archive(file_to_save, "zip", path_to_folder)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, create_emoji_zip)
        print("Created .zip backup file.")

    @discord.app_commands.command(
        name="download_emoji",
        description="Send the emoji data as a zip file to the chat as well as usage statistics.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(send_messages=True)
    async def download_emoji(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_response(content="Here are your requested emoji backup files:",
                                                 attachments=[
                                                     discord.File(f"data/{interaction.guild.id}_emoji_backup.zip")])


async def setup(bot):
    await bot.add_cog(EmojiManager(bot))

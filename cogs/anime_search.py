"""Cog that lets users search for video examples from an anime database (for language learning)."""
import asyncio
import json
import os
import pkgutil
import random
import re
import shutil
import subprocess
import tempfile

import discord
from discord.ext import commands
import pysubs2

from . import data_management

# Ensure folder existence and load config
DATABASE_BUCKET = pkgutil.get_data(__package__, "config/database_bucket.txt").decode()
LOCAL_DATABASE_PATH = 'data/anime_search_database'
REMOTE_DATABASE_PATH = "database/"
SEARCH_RESULT_PATH = 'data/search_result'

if not os.path.exists(LOCAL_DATABASE_PATH):
    os.mkdir(LOCAL_DATABASE_PATH)
if not os.path.exists(SEARCH_RESULT_PATH):
    os.mkdir(SEARCH_RESULT_PATH)


##############################################

# Buttons
class SelectResultButton(discord.ui.Button):
    """Button that lets users select a search result. If a result is chosen a video will be encoded and sent."""

    def __init__(self, result_index: int, search_results: list, interaction_user: discord.User,
                 current_offset: int):
        super().__init__(label=str(result_index + 1), style=discord.ButtonStyle.primary, row=0)
        self.selected_result = search_results[current_offset + result_index]
        self.check_user_id = interaction_user.id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.check_user_id:
            await interaction.response.send_message("This button is not for you :).", ephemeral=True)
            return

        await interaction.response.send_message("Generating clip...", ephemeral=True)
        cut_file_name, text_summary, random_folder, video_file, subtitle_file = await generate_clip(
            self.selected_result)
        text_embed = discord.Embed(title=f"{interaction.user} requested from {self.selected_result['anime_name']}:",
                                   description=f"`{text_summary}`")

        full_context_view = await create_full_context_view(random_folder, video_file, subtitle_file, interaction)
        await interaction.edit_original_response(content="Finished creating clip.")
        await interaction.message.reply(embed=text_embed,
                                        file=discord.File(f"{random_folder}/{cut_file_name}"),
                                        view=full_context_view)


class ShiftResultsButton(discord.ui.Button):
    """Button that shifts result left or right."""

    def __init__(self, label: str, current_offset: int, interaction_user: discord.User,
                 searched_text: str, search_results: list):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=1)
        self.current_offset = current_offset
        self.check_user_id = interaction_user.id
        self.label = label
        self.searched_text = searched_text
        self.search_results = search_results

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.check_user_id:
            await interaction.response.send_message("This button is not for you :).", ephemeral=True)
            return

        await interaction.response.defer()
        if self.label == "<":
            new_offset = self.current_offset - 5
        else:
            new_offset = self.current_offset + 5
        if new_offset <= 0:
            new_offset = 0

        result_embed = await create_result_embed(self.search_results, self.searched_text, new_offset)
        interaction_message = await interaction.original_response()
        result_view = await create_result_view(self.search_results, interaction.user, new_offset, self.searched_text,
                                               interaction_message)

        await interaction.edit_original_response(embed=result_embed, view=result_view)


class FullContextButton(discord.ui.Button):
    """Button appended to a result that lets users fetch the whole result."""

    def __init__(self, interaction_user, random_folder, video_file, subtitle_file):
        super().__init__(label='Full Context', style=discord.ButtonStyle.primary, row=1)
        self.interaction_user = interaction_user
        self.random_folder = random_folder
        self.video_file = video_file
        self.subtitle_file = subtitle_file

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.interaction_user.id:
            await interaction.response.send_message("This button is not for you :).", ephemeral=True)
            return

        await interaction.response.send_message("Fetching full context...", ephemeral=True)
        subtitle = pysubs2.load(f"{self.random_folder}/{self.subtitle_file}")
        full_text = "\n".join([line.text for line in subtitle])
        full_context_embed = discord.Embed(title=f"Full context requested by {self.interaction_user}",
                                           description=f'```{full_text[0:4000]}```')
        await interaction.message.reply(embed=full_context_embed,
                                        file=discord.File(f"{self.random_folder}/{self.video_file}"))
        await interaction.message.edit(view=None)
        try:
            shutil.rmtree(self.random_folder)
        except FileNotFoundError:
            pass


##############################################

class SelfClearingView(discord.ui.View):
    """View that deletes itself after timeout. Also deletes temporaryr result folder if specified."""

    def __init__(self, interaction_message, folder_to_clear=None):
        super().__init__()
        self.interaction_message = interaction_message
        self.folder_to_clear = folder_to_clear

    async def on_timeout(self):
        self.clear_items()
        await self.interaction_message.edit(content="Selection timed out.", view=self)
        if self.folder_to_clear:
            try:
                shutil.rmtree(self.folder_to_clear)
            except FileNotFoundError:
                pass


##############################################

async def create_result_view(search_results, interaction_user, current_offset, searched_text, interaction_message):
    choice_menu = SelfClearingView(interaction_message)
    for index, result in enumerate(search_results[current_offset:current_offset + 5]):
        select_button = SelectResultButton(index, search_results, interaction_user, current_offset)
        choice_menu.add_item(select_button)
    cycle_left_button = ShiftResultsButton("<", current_offset, interaction_user, searched_text, search_results)
    cycle_right_button = ShiftResultsButton(">", current_offset, interaction_user, searched_text, search_results)
    choice_menu.add_item(cycle_left_button)
    choice_menu.add_item(cycle_right_button)
    return choice_menu


async def create_full_context_view(random_folder, video_file, subtitle_file, interaction: discord.Interaction):
    full_context_menu = SelfClearingView(interaction.message, random_folder)
    full_context_button = FullContextButton(interaction.user, random_folder, video_file, subtitle_file)
    full_context_menu.add_item(full_context_button)
    return full_context_menu


async def create_result_embed(search_results, text_to_search, offset=0):
    if not offset:
        result_embed = discord.Embed(title=f"Search result for '{text_to_search}'", colour=discord.Colour.gold())
    else:
        result_embed = discord.Embed(title=f"Search result for '{text_to_search}' [Offset: {offset}]",
                                     colour=discord.Colour.gold())
    for index, result in enumerate(search_results[offset:offset + 5]):
        result_embed.add_field(name=f"Result from {result['anime_name']}",
                               value=f"**{index + 1}.** `{result['text']}`", inline=False)
    return result_embed


async def cut_clip(start_time, end_time, video_file_name, folder_name):
    start_time = str(start_time / 1000.0)
    end_time = str(end_time / 1000.0)

    def cut_video():
        cut_command = ["python3",
                       "-m",
                       "ffmpeg_smart_trim.trim",
                       f"{folder_name}/{video_file_name}",
                       "--start_time",
                       start_time,
                       "--end_time",
                       end_time,
                       "--output",
                       f"{folder_name}/trimmed_{video_file_name}"]

        encode_job = subprocess.Popen(cut_command)
        encode_job.wait()
        return True

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, cut_video)
    return f"trimmed_{video_file_name}"


async def generate_clip(result):
    video_file = result["video_file"]
    subtitle_file = result["subtitle_file"]
    random_folder = tempfile.mkdtemp(dir=SEARCH_RESULT_PATH)
    await data_management.download_from_s3(f"{random_folder}/{video_file}", f"8_finished_clips/{video_file}",
                                           bucket=DATABASE_BUCKET)
    await data_management.download_from_s3(f"{random_folder}/{subtitle_file}", f"9_finished_subs/{subtitle_file}",
                                           bucket=DATABASE_BUCKET)

    subtitle = pysubs2.load(f"{random_folder}/{subtitle_file}")
    start_time = result["start_time"]
    relevant_sub = next((line for line in subtitle if line.start == start_time), None)
    if not subtitle.index(relevant_sub) == 0:
        previous_sub = subtitle[subtitle.index(relevant_sub) - 1]
    else:
        previous_sub = None
    if not subtitle[-1] == relevant_sub:
        next_sub = subtitle[subtitle.index(relevant_sub) + 1]
    else:
        next_sub = None

    texts = []

    if previous_sub:
        texts.append(previous_sub.text)
        start_time = previous_sub.start - 1000
    else:
        start_time = relevant_sub.start - 1000

    texts.append(relevant_sub.text)

    if next_sub:
        texts.append(next_sub.text)
        end_time = next_sub.end + 500
    else:
        end_time = relevant_sub.end + 500

    if start_time < 0:
        start_time = 0

    cut_file_name = await cut_clip(start_time, end_time, video_file, random_folder)
    text_summary = '\n'.join(texts)
    return cut_file_name, text_summary, random_folder, video_file, subtitle_file


async def perform_search_query(searched_text: str):
    search_command = ["groonga", f"{LOCAL_DATABASE_PATH}/JPSUBS.db",
                      f"select --table MainSubs --limit 100 --query text:@{searched_text}"]

    def run_search():
        search = subprocess.run(search_command, capture_output=True)
        return search

    loop = asyncio.get_running_loop()
    finished_query = await loop.run_in_executor(None, run_search)

    json_results = json.loads(finished_query.stdout.decode("utf-8"))[1][0][2:]
    search_results = []
    for json_result in json_results:
        result = dict()
        result["anime_name"] = json_result[2]
        result["subtitle_file"] = json_result[5]
        result["video_file"] = json_result[7]
        result["text"] = json_result[6]
        result["start_time"] = json_result[4]
        result["end_time"] = json_result[3]
        result["context_name"] = json_result[1]
        search_results.append(result)

    random.shuffle(search_results)
    return search_results


async def download_db():
    file_list = await data_management.list_files_from_s3(folder_path=REMOTE_DATABASE_PATH, bucket=DATABASE_BUCKET)
    for file in file_list:
        await data_management.download_from_s3(f'{LOCAL_DATABASE_PATH}/{file}',
                                               f"{REMOTE_DATABASE_PATH}{file}",
                                               bucket=DATABASE_BUCKET)
    return


##############################################

class AnimeSearch(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="search",
        description="Search in the anime example database.")
    @discord.app_commands.guild_only()
    async def search(self, interaction: discord.Interaction, text_to_search: str):
        text_to_search = re.sub(r"\s", "", text_to_search.lower().strip())
        text_to_search = re.sub(r"[a-zA-Z]", "", text_to_search)
        if not text_to_search:
            await interaction.response.send_message("Invalid search. Please search in Japanese.")
            return

        await interaction.response.defer()
        search_results = await perform_search_query(text_to_search)
        result_embed = await create_result_embed(search_results, text_to_search)
        interaction_message = await interaction.original_response()
        result_view = await create_result_view(search_results, interaction.user, 0, text_to_search, interaction_message)

        await interaction.edit_original_response(content="", embed=result_embed, view=result_view)

    @discord.app_commands.command(
        name="list_anime",
        description="List the anime in the database.")
    @discord.app_commands.guild_only()
    async def list_anime(self, interaction: discord.Interaction):
        with open("data/database/anime_names.json") as json_file:
            anime_data = json.load(json_file)

        anime_in_db = list(anime_data.values())

        anime_list_embed = discord.Embed(title="Anime in database", description="\n".join(anime_in_db))
        await interaction.response.send_message(embed=anime_list_embed)

    @commands.command(name='update_anime_db')
    @commands.has_permissions(administrator=True)
    async def update_anime_db(self, ctx: commands.Context):
        """Download the search database from S3"""
        reply = await ctx.reply("Downloading database...")
        await download_db()
        await reply.edit(content="Finished downloading database.")


async def setup(bot):
    await bot.add_cog(AnimeSearch(bot))

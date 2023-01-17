"""Launch bot and load cogs."""
import discord
import sys
from discord.ext import commands
import json
import asyncio
import logging
import traceback

log = logging.getLogger(__name__)
testing_mode = False
testing_cog = "cogs.join_and_leave"

class CustomCommandTree(discord.app_commands.CommandTree):
    def __init__(self, bot):
        super().__init__(client=bot)
        self.bot = bot

    async def on_error(self, interaction: discord.Interaction, error, /):
        error_type, value, tb = sys.exc_info()
        traceback_string = '\n'.join(traceback.format_list(traceback.extract_tb(tb)))
        error_string = f"```{str(value)}\n\n{traceback_string}```"
        await self.bot.bot_owner_dm_channel.send(error_string)

        command = interaction.command
        if command is not None:
            if command._has_any_error_handlers():
                return

            log.error('Ignoring exception in command %r', command.name, exc_info=error)
        else:
            log.error('Ignoring exception in command tree', exc_info=error)


class DJTBot(commands.Bot):

    def __init__(self):
        super().__init__(command_prefix="$", intents=discord.Intents.all(), help_command=None,
                         tree_cls=CustomCommandTree)
        if not testing_mode:
            with open("data/token.txt") as token_file:
                self.token = token_file.read()
        else:
            with open("data/testing_token.txt") as token_file:
                self.token = token_file.read()

    async def on_error(self, event_method: str, /, *args, **kwargs):
        log.exception('Ignoring exception in %s', event_method)
        error_type, value, tb = sys.exc_info()
        traceback_string = '\n'.join(traceback.format_list(traceback.extract_tb(tb)))
        error_string = f"Error occurred in `{value}`\n```{str(value)}\n\n{traceback_string}```"
        await self.bot_owner_dm_channel.send(error_string)

    async def on_ready(self):
        application_info = await self.application_info()
        bot_owner = application_info.owner
        await bot_owner.create_dm()
        self.bot_owner_dm_channel = bot_owner.dm_channel

        game = discord.Game("with slash commands.")
        await self.change_presence(activity=game)

        print(f"Logged in as {self.user}")
        if not testing_mode:
            await self.load_essential_cogs()
            await self.load_standard_cogs()
            await self.load_experimental_cogs()
        else:
            await self.load_essential_cogs()
            await self.load_extension(testing_cog)
            print(f"Loaded {testing_cog} cog.")

    async def load_essential_cogs(self):
        await self.load_extension("cogs.setup_logging")
        print("Loaded 'logging' cog.")
        await self.load_extension("cogs.config")
        print("Loaded 'config' cog.")

    async def load_standard_cogs(self):
        await self.load_extension("cogs.error_catcher")
        print("Loaded 'error catcher' cog.")
        await self.load_extension("cogs.assignable_roles")
        print("Loaded 'assignable roles' cog.")
        await self.load_extension("cogs.rank_saver")
        print("Loaded 'rank saver' cog.")
        await self.load_extension("cogs.open_ai_interaction")
        print("Loaded 'open ai interaction' cog.")
        await self.load_extension("cogs.deleted_messages_log")
        print("Loaded 'deleted messages log' cog.")
        await self.load_extension("cogs.levelup")
        print("Loaded 'level up' cog.")
        await self.load_extension("cogs.clubs")
        print("Loaded 'clubs' cog.")
        await self.load_extension("cogs.moderation")
        print("Loaded 'moderation' cog.")
        await self.load_extension("cogs.temporary_vc")
        print("Loaded 'temporary voice channel' cog.")
        await self.load_extension("cogs.join_and_leave")
        print("Loaded 'join and leave message' cog.")
        await self.load_extension("cogs.bump")
        print("Loaded 'bump' cog.")
        await self.load_extension("cogs.emoji_manager")
        print("Loaded 'emoji manager' cog.")
        await self.load_extension("cogs.auto_receive")
        print("Loaded 'auto receive' cog.")
        await self.load_extension("cogs.nickname_counter")
        print("Loaded 'nickname counter' cog.")
        await self.load_extension("cogs.custom_role")
        print("Loaded 'custom role' cog.")
        await self.load_extension("cogs.notable_posts")
        print("Loaded 'notable posts' cog.")
        await self.load_extension("cogs.backup")
        print("Loaded 'backup' cog.")
        await self.load_extension("cogs.polling")
        print("Loaded 'polling' cog.")
        await self.load_extension("cogs.channel_clearer")
        print("Loaded 'channel clearer' cog.")
        await self.load_extension("cogs.state_saver")
        print("Loaded 'state saver' cog.")
        await self.load_extension("cogs.misc")
        print("Loaded 'misc' cog.")
        await self.load_extension("cogs.quiz_cage")
        print("Loaded 'quiz cage' cog.")

    async def load_experimental_cogs(self):
        pass


    async def open_json_file(self, guild, filename, empty_data_container, general_data=False):
        def open_json(guild, filename, empty_data_container, general_data):
            try:
                if not general_data:
                    with open(f"data/{guild.id}/{filename}") as json_file:
                        json_data = json.load(json_file)
                else:
                    with open(f"data/{filename}") as json_file:
                        json_data = json.load(json_file)
            except FileNotFoundError:
                json_data = empty_data_container
            except json.JSONDecodeError:
                json_data = empty_data_container

            return json_data

        loop = asyncio.get_running_loop()
        json_data = await loop.run_in_executor(None, open_json, guild, filename, empty_data_container, general_data)
        return json_data

    async def write_json_file(self, guild, filename, data, general_data=False):
        def write_json(guild, filename, data, general_data):
            if not general_data:
                with open(f"data/{guild.id}/{filename}", "w") as json_file:
                    json.dump(data, json_file)
            else:
                with open(f"data/{filename}", "w") as json_file:
                    json.dump(data, json_file)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, write_json, guild, filename, data, general_data)


djtbot = DJTBot()
djtbot.run(djtbot.token, log_handler=None)

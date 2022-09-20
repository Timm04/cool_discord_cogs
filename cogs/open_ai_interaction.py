"""OpenAI chat bot"""
import discord
import re
import asyncio
import openai
from functools import partial
from discord.ext import commands
from discord.ext import tasks


class ChangePromptModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Set the new OpenAI prompt.")
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await self.bot.write_json_file(interaction.guild, "openai_prompt.json", self.children[0].value)
        await interaction.response.send_message("Updated the OpenAI prompt.")


class OpenAIReply(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        pass

    async def delete_current_key(self):
        api_key_list = await self.bot.open_json_file("no_guild", "open_ai_keys.json", list(), general_data=True)
        current_key = api_key_list[0]
        api_key_list.remove(current_key)
        await self.bot.write_json_file("no_guild", "open_ai_keys.json", api_key_list, general_data=True)

    @discord.app_commands.command(
        name="_edit_openai_prompt",
        description="Change the prompt for the OpenAI bot.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def edit_openai_prompt(self, interaction: discord.Interaction):
        current_prompt = await self.bot.open_json_file(interaction.guild, "openai_prompt.json", "")
        change_prompt_modal = ChangePromptModal(self.bot)
        change_prompt_modal.add_item(
            discord.ui.TextInput(label='New Prompt:', style=discord.TextStyle.paragraph, default=current_prompt,
                                 min_length=100, max_length=1000))
        await interaction.response.send_modal(change_prompt_modal)

    @discord.app_commands.command(
        name="add_openai_key",
        description="Add an OpenAI key for the bot to use.")
    @discord.app_commands.describe(openai_key="OpenAI API key.")
    async def add_openai_key(self, interaction: discord.Interaction, openai_key: str):
        openai.api_key = openai_key
        try:
            completion = openai.Completion.create(engine="text-davinci-002",
                                                  prompt="How many human beings exist on planet earth?")
        except openai.error.RateLimitError:
            await interaction.response.send_message("This key has already reached the quota limit.", ephemeral=True)
            await asyncio.sleep(5)
            await interaction.delete_original_response()
            return
        except openai.error.AuthenticationError:
            await interaction.response.send_message("Key seems to be incorrect.", ephemeral=True)
            await asyncio.sleep(5)
            await interaction.delete_original_response()
            return
        if completion:
            api_key_list = await self.bot.open_json_file("no_guild", "open_ai_keys.json", list(), general_data=True)
            api_key_list.append(openai_key)
            await self.bot.write_json_file("no_guild", "open_ai_keys.json", list(set(api_key_list)), general_data=True)
            await interaction.response.send_message(f"{interaction.user.mention} Key has been added!",
                                                    ephemeral=True)
            await interaction.channel.send("New API key has been added.")
            await asyncio.sleep(5)
            await interaction.delete_original_response()

    @discord.app_commands.command(
        name="_toggle_openai",
        description="Enable/Disable the OpenAI bot.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_openai(self, interaction: discord.Interaction):
        current_status = await self.bot.open_json_file(interaction.guild, "open_ai_status.json", False)
        if current_status:
            current_status = False
            await self.bot.write_json_file(interaction.guild, "open_ai_status.json", current_status)
            await interaction.response.send_message("Deactivated the OpenAI bot.")
        else:
            current_status = True
            await self.bot.write_json_file(interaction.guild, "open_ai_status.json", current_status)
            await interaction.response.send_message("Activated the OpenAI bot.")

    async def generate_message(self, prompt, guild):
        current_status = await self.bot.open_json_file(guild, "open_ai_status.json", False)

        api_key_list = await self.bot.open_json_file("no_guild", "open_ai_keys.json", list(), general_data=True)
        try:
            api_key = api_key_list[0]
            openai.api_key = api_key
        except IndexError:
            return f"There seem to be no API keys available." \
                   f"\n- You can add a new API key to the bot using the command `/add_openai_key`" \
                   f"\n- You can get an OpenAI key by signing up for a free trial on https://beta.openai.com/." \
                   f"\nTo sign up you need a phone number, but you can use any free SMS receiver for sign up."

        if not current_status:
            return f"OpenAI bot is currently deactivated in this guild. There are {len(api_key)} API keys available."

        prompt = prompt.replace("@", " ")
        prompt = prompt.replace("古明地さとり", "Satori, ")
        prompt = prompt.replace("A:", "Satori:")
        loop = asyncio.get_running_loop()
        try:
            completion = await loop.run_in_executor(None, partial(openai.Completion.create, engine="text-davinci-002",
                                                                  prompt=prompt,
                                                                  presence_penalty=2.0,
                                                                  frequency_penalty=2.0,
                                                                  max_tokens=350))

        except openai.error.RateLimitError:
            await self.delete_current_key()
            return "Key has reached API limit."
        except openai.error.AuthenticationError:
            await self.delete_current_key()
            return "Key seems to not work anymore."
        except openai.error.APIConnectionError:
            return "What?"

        ai_reply = completion["choices"][0]["text"].replace("\n", "")
        ai_reply = re.sub(r"https?://.*\.\w{2,3}", "<snip>", ai_reply)
        if "Q:" in ai_reply:
            ai_reply = ai_reply.split("Q:")[0]
        return ai_reply

    @discord.app_commands.command(
        name="ask_ai",
        description="Ask the AI something.")
    @discord.app_commands.describe(question="Your question.")
    async def ask_ai(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        pre_prompt = await self.bot.open_json_file(interaction.guild, "openai_prompt.json", "")
        full_prompt = f"{pre_prompt}" \
                      f"\nQ: {question}" \
                      f"\nA: "

        reply = await self.generate_message(full_prompt, interaction.guild)
        await interaction.edit_original_response(content=f"Q: {question} \nA: {reply}",
                                                 allowed_mentions=discord.AllowedMentions.none())

    async def reply_to_message(self, message: discord.Message, history=None):
        cleaned_user_name = "".join([symbol for symbol in message.author.display_name if symbol.isalnum()])
        cleaned_message_content = message.clean_content
        pre_prompt = await self.bot.open_json_file(message.guild, "openai_prompt.json", "")
        full_prompt = f"{pre_prompt}" \
                      f"\n{history}" \
                      f"\n{cleaned_user_name}: {cleaned_message_content}" \
                      f"\nA: "
        reply = await self.generate_message(full_prompt, message.guild)
        if cleaned_user_name + ":" in reply:
            reply = reply.split(cleaned_user_name + ":")[0]
        return reply

    async def fetch_history(self, message_by_self: discord.Message, history_strings=None):
        if not history_strings:
            history_strings = []
        history_strings.append(f"A: {message_by_self.clean_content}")
        try:
            replied_to_message = message_by_self.reference.cached_message
        except AttributeError:
            return history_strings
        if not replied_to_message:
            return history_strings
        replied_to_author_name = "".join(
            [symbol for symbol in replied_to_message.author.display_name if symbol.isalnum()])
        replied_to_content = replied_to_message.clean_content
        history_strings.append(f"{replied_to_author_name}: {replied_to_content}")
        if len(history_strings) > 8:
            return history_strings
        try:
            if replied_to_message.reference.cached_message.author == self.bot.user:
                history_strings = await self.fetch_history(replied_to_message.reference.cached_message,
                                                           history_strings=history_strings)
        except AttributeError:
            pass
        return history_strings

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        mention = f"<@{self.bot.user.id}>"
        if message.author == self.bot.user:
            return
        if message.author.bot:
            return
        if mention in message.content:

            current_status = await self.bot.open_json_file(message.guild, "open_ai_status.json", False)
            if not current_status:
                return

            ai_message = await self.reply_to_message(message)
            try:
                await message.reply(ai_message, allowed_mentions=discord.AllowedMentions.none())
            except discord.errors.HTTPException:
                await message.reply("Come again?", allowed_mentions=discord.AllowedMentions.none())
            return
        replied_to_user_id = None
        try:
            replied_to_user_id = message.reference.cached_message.author.id
        except AttributeError:
            pass
        if replied_to_user_id == self.bot.user.id:

            current_status = await self.bot.open_json_file(message.guild, "open_ai_status.json", False)
            if not current_status:
                return

            history_strings = await self.fetch_history(message.reference.cached_message)
            history_strings.reverse()
            history = '\n'.join(history_strings)
            ai_message = await self.reply_to_message(message, history=history)
            try:
                await message.reply(ai_message, allowed_mentions=discord.AllowedMentions.none())
            except discord.errors.HTTPException:
                await message.reply("Come again?", allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(OpenAIReply(bot))

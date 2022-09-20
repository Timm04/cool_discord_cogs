"""Create a nickname that counts days"""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks
from datetime import datetime
from datetime import timedelta


class NicknameCounter(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.update_nicknames.start()

    async def cog_unload(self):
        self.update_nicknames.cancel()

    @discord.app_commands.command(
        name="nickname_counter",
        description="Create a counter inside a nickname.")
    @discord.app_commands.guild_only()
    @discord.app_commands.choices(count_up_or_down=[
        discord.app_commands.Choice(name="Count up", value="Up"),
        discord.app_commands.Choice(name="Count down", value="Down")])
    @discord.app_commands.describe(count_up_or_down="Whether to count up or count down.",
                                   starting_number="What number the counter should start at.",
                                   nickname="Your new nickname. Include XXXX as placeholder.")
    @discord.app_commands.default_permissions(send_messages=True)
    async def nickname_counter(self, interaction: discord.Interaction, count_up_or_down: str, starting_number: int, nickname: str):
        await interaction.response.defer()
        if "XXXX" not in nickname:
            await interaction.edit_original_response(content="You have to include `XXXX` in your nickname as a placeholder.")
            return

        if len(nickname) > 32:
            await interaction.edit_original_response(content="Nickname has to be shorter than 32 symbols.")
            return

        current_date_string = datetime.utcnow().strftime("%Y-%m-%d")

        nickname_data = (nickname, count_up_or_down, starting_number, current_date_string)
        user_nickname_data = await self.bot.open_json_file(interaction.guild, "counting_nickname_data.json", dict())
        user_nickname_data[str(interaction.user.id)] = nickname_data
        await self.bot.write_json_file(interaction.guild, "counting_nickname_data.json", user_nickname_data)

        await self.update_user_nickname(interaction.user, nickname_data)
        await interaction.edit_original_response(content="Changed your nickname!")

    async def update_user_nickname(self, member: discord.Member, nickname_data):
        await asyncio.sleep(5)
        nickname, count_up_or_down, starting_number, date_string = nickname_data
        if len(nickname) > 32:
            return
        relevant_date = datetime.strptime(date_string, "%Y-%m-%d")
        current_date_string = datetime.utcnow().strftime("%Y-%m-%d")
        current_date = datetime.strptime(current_date_string, "%Y-%m-%d")
        time_difference_in_days = int((current_date - relevant_date).days)
        if count_up_or_down == "Up":
            current_counter = starting_number + time_difference_in_days
        else:
            current_counter = starting_number - time_difference_in_days
            if current_counter <= 0:
                current_counter = 0

        nickname_string = nickname.replace("XXXX", str(current_counter))
        await member.edit(nick=nickname_string)

    @discord.app_commands.command(
        name="delete_nickname_counter",
        description="Delete the nickname counter.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(send_messages=True)
    async def delete_nickname_counter(self, interaction: discord.Interaction):
        user_nickname_data = await self.bot.open_json_file(interaction.guild, "counting_nickname_data.json", dict())
        if str(interaction.user.id) in user_nickname_data:
            del user_nickname_data[str(interaction.user.id)]
            await interaction.user.edit(nick=None)
            await self.bot.write_json_file(interaction.guild, "counting_nickname_data.json", user_nickname_data)
            await interaction.response.send_message("Cleared your nickname data.")
        else:
            await interaction.response.send_message("Couldn't find you in the data.")

    @tasks.loop(minutes=60)
    async def update_nicknames(self):
        await asyncio.sleep(600)
        for guild in self.bot.guilds:
            user_nickname_data = await self.bot.open_json_file(guild, "counting_nickname_data.json", dict())
            for user_id in user_nickname_data:
                member = guild.get_member(int(user_id))
                if not member:
                    continue
                await asyncio.sleep(5)
                await self.update_user_nickname(member, user_nickname_data[user_id])


async def setup(bot):
    await bot.add_cog(NicknameCounter(bot))

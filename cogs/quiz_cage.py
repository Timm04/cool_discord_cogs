"""Cog Description"""
import asyncio

import discord
from discord.ext import commands

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "quiz_cage"
SETTINGS_COLUMNS = ("guild_id", "settings", "user_data")


async def fetch_quiz_cage_settings(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id,
                                             default_type=list)


async def write_quiz_cage_settings(guild_id: int, settings):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], settings, guild_id=guild_id)


async def fetch_quiz_cage_data(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id, default_type=dict)


async def write_quiz_cage_data(guild_id: int, data):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], data, guild_id=guild_id)


#########################################


update_lock = asyncio.Lock()


class QuizCage(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)

    @discord.app_commands.command(
        name="_set_quiz_cage_role",
        description="Set a role to be the punishment role.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(quiz_cage_role="Punishment role.",
                                   update_channel="Channel where updates about the quiz cage should be posted.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_quiz_cage_role(self, interaction: discord.Interaction, quiz_cage_role: discord.Role,
                                 update_channel: discord.TextChannel):
        quiz_cage_settings = (quiz_cage_role.name, update_channel.name)
        await write_quiz_cage_settings(interaction.guild_id, quiz_cage_settings)
        await interaction.response.send_message(
            f"Set quiz cage role to {quiz_cage_role.mention} and update channel to {update_channel.mention}.",
            allowed_mentions=discord.AllowedMentions.none())

    @discord.app_commands.command(
        name="quiz_cage",
        description="Give someone a role that they will only lose by getting another role.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(goal_role="The role users have to get to lose the punishment role.")
    @discord.app_commands.default_permissions(administrator=True)
    async def quiz_cage(self, interaction: discord.Interaction, goal_role: discord.Role, member: discord.Member):
        quiz_cage_role_name, update_channel_name = await fetch_quiz_cage_settings(interaction.guild_id)
        quiz_cage_role = discord.utils.get(interaction.guild.roles, name=quiz_cage_role_name)
        quiz_cage_data = await fetch_quiz_cage_data(interaction.guild_id)
        await member.add_roles(quiz_cage_role)
        quiz_cage_data[str(member.id)] = goal_role.name
        await write_quiz_cage_data(interaction.guild_id, quiz_cage_data)
        await interaction.response.send_message(
            f"Quiz caged the user {member.mention} until they reach {goal_role.name}")

    @discord.app_commands.command(
        name="list_quiz_cage",
        description="List all users currently quiz caged.")
    @discord.app_commands.guild_only()
    async def list_quiz_cage(self, interaction: discord.Interaction):
        quiz_cage_data = await fetch_quiz_cage_data(interaction.guild_id)
        quiz_cage_embed = discord.Embed(title="User Quiz Cage Data")
        for user_id in quiz_cage_data:
            member = interaction.guild.get_member(int(user_id))
            if not member:
                continue
            quiz_cage_embed.add_field(name=f"{str(member)}", value=f"Quiz caged until **{quiz_cage_data[user_id]}**.")

        await interaction.response.send_message(embed=quiz_cage_embed)

    @commands.Cog.listener(name="on_member_update")
    async def remove_quiz_cage(self, member_before: discord.Member, member_after: discord.Member):
        try:
            quiz_cage_role_name, update_channel_name = await fetch_quiz_cage_settings(member_before.guild.id)
        except ValueError:
            return
        quiz_cage_role = discord.utils.get(member_before.guild.roles, name=quiz_cage_role_name)
        async with update_lock:
            if quiz_cage_role in member_before.roles:
                quiz_cage_data = await fetch_quiz_cage_data(member_before.guild.id)
                try:
                    role_to_get_name = quiz_cage_data[str(member_before.id)]
                except KeyError:
                    await member_after.remove_roles(quiz_cage_role)
                    return
                role_to_get = discord.utils.get(member_before.guild.roles, name=role_to_get_name)
                if role_to_get in member_after.roles:
                    await member_after.remove_roles(quiz_cage_role)
                    del quiz_cage_data[str(member_before.id)]
                    await write_quiz_cage_data(member_before.guild.id, quiz_cage_data)
                    update_channel = discord.utils.get(member_before.guild.text_channels, name=update_channel_name)
                    await update_channel.send(
                        f"{member_after.mention} got the **{role_to_get_name}** role and the quiz cage was lifted.")


async def setup(bot):
    await bot.add_cog(QuizCage(bot))

"""Cog that enables certain roles to automatically receive other roles."""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "auto_receive_roles_settings"
SETTINGS_COLUMNS = ("guild_id", "auto_receive_roles", "auto_receive_banned")


async def fetch_auto_receive_role_data(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id)


async def fetch_auto_receive_banned_data(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id)


async def write_auto_receive_role_data(guild_id: int, auto_receive_role_data: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], auto_receive_role_data,
                                       guild_id=guild_id)


async def write_auto_receive_banned_data(guild_id: int, auto_receive_banned_data: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], auto_receive_banned_data,
                                       guild_id=guild_id)


#########################################


async def autocomplete_auto_receive(interaction: discord.Interaction, current_input: str):
    auto_receive_data = await fetch_auto_receive_role_data(interaction.guild_id)
    possible_options = []
    for role_to_have, role_to_get in auto_receive_data:
        if current_input in role_to_have or current_input in role_to_get:
            possible_options.append(discord.app_commands.Choice(name=f"{role_to_have} -> {role_to_get}",
                                                                value=f"{role_to_have}+{role_to_get}"))

    return possible_options[0:25]


#########################################

class AutoReceive(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        self.give_auto_roles.start()

    async def cog_unload(self):
        self.give_auto_roles.cancel()

    @discord.app_commands.command(
        name="_set_role_auto_receive",
        description="Set up a role to be automatically assigned to users of another role.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(role_to_have="The role users should have.",
                                   role_to_get="The role users that have the first role should get.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_role_auto_receive(self, interaction: discord.Interaction, role_to_have: discord.Role,
                                    role_to_get: discord.Role):
        auto_receive_data = await fetch_auto_receive_role_data(interaction.guild_id)
        auto_receive_data.append((role_to_have.name, role_to_get.name))
        await write_auto_receive_role_data(interaction.guild_id, auto_receive_data)
        await interaction.response.send_message(f"Added `{role_to_have.name} -> {role_to_get.name}` auto receive.",
                                                ephemeral=True)

    @discord.app_commands.command(
        name="_remove_auto_receive",
        description="Remove a role auto receive setting.")
    @discord.app_commands.guild_only()
    @discord.app_commands.autocomplete(receive_string=autocomplete_auto_receive)
    @discord.app_commands.describe(receive_string="Which receive data should be removed.")
    @discord.app_commands.default_permissions(administrator=True)
    async def remove_auto_receive(self, interaction: discord.Interaction, receive_string: str):
        auto_receive_data = await fetch_auto_receive_role_data(interaction.guild_id)
        role_to_have_name, role_to_receive_name = receive_string.split("+")
        auto_receive_data.remove([role_to_have_name, role_to_receive_name])
        await write_auto_receive_role_data(interaction.guild_id, auto_receive_data)
        await interaction.response.send_message(f"Removed the `{role_to_have_name} -> {role_to_receive_name}` assign.",
                                                ephemeral=True)

    @discord.app_commands.command(
        name="_toggle_auto_receive_ban",
        description="Ban a member from automatically receiving roles.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(member="The member that should be banned.",
                                   role="The role that should no longer be given.")
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_auto_receive_ban(self, interaction: discord.Interaction, member: discord.Member,
                                      role: discord.Role):
        if role in member.roles:
            await member.remove_roles(role)

        banned_user_data = await fetch_auto_receive_banned_data(interaction.guild_id)
        action = None
        for banned_user in banned_user_data:
            banned_user_id, banned_role_name = banned_user
            if banned_user_id == member.id and banned_role_name == role.name:
                banned_user_data.remove(banned_user)
                action = "Unbanned"
        if not action:
            banned_user_data.append([member.id, role.name])
            action = "Banned"

        await write_auto_receive_banned_data(interaction.guild_id, banned_user_data)
        await interaction.response.send_message(f"{action} {member} from automatically getting the role {role.name}.",
                                                ephemeral=True)

    @tasks.loop(minutes=10)
    async def give_auto_roles(self):
        await asyncio.sleep(600)
        for guild in self.bot.guilds:
            auto_receive_data = await fetch_auto_receive_role_data(guild.id)
            banned_user_data = await fetch_auto_receive_banned_data(guild.id)
            for role_data in auto_receive_data:
                role_to_have_name, role_to_receive_name = role_data
                role_to_have = discord.utils.get(guild.roles, name=role_to_have_name)
                role_to_receive = discord.utils.get(guild.roles, name=role_to_receive_name)
                if not role_to_have or not role_to_receive:
                    auto_receive_data.remove(role_data)
                    await write_auto_receive_role_data(guild.id, auto_receive_data)
                    continue
                for member in role_to_have.members:

                    banned = False
                    for banned_id, role_name in banned_user_data:
                        if member.id == banned_id and role_to_receive.name == role_name:
                            banned = True

                    if role_to_receive not in member.roles and not banned:
                        print(f"AUTO-RECEIVE: Gave {member} the role {role_to_receive} in guild {guild.id}")
                        await member.add_roles(role_to_receive)


async def setup(bot):
    await bot.add_cog(AutoReceive(bot))

"""Allow creation of custom roles.
Set up a role called 'Pos. Reference Role' for the bot to create roles below that role in position."""
import asyncio
import re

import discord
from discord.ext import commands
from discord.ext import tasks

from . import data_management

#########################################

# Database Operations and Values
SETTINGS_TABLE_NAME = "custom_role_settings"
SETTINGS_COLUMNS = ("guild_id", "allowed_roles", "custom_role_data")


async def fetch_custom_role_data(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id,
                                             default_type=dict)


async def fetch_allowed_roles(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id)


async def write_custom_role_data(guild_id: int, custom_role_data: dict):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], custom_role_data,
                                       guild_id=guild_id)


async def write_allowed_roles(guild_id: int, allowed_roles: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], allowed_roles,
                                       guild_id=guild_id)


#########################################

async def clear_custom_role_data(member: discord.Member):
    custom_role_data = await fetch_custom_role_data(member.guild.id)
    if str(member.id) in custom_role_data:
        role_id = custom_role_data.get(str(member.id))
        custom_role = member.guild.get_role(role_id)
        if custom_role:
            await custom_role.delete()
        del custom_role_data[str(member.id)]
        await write_custom_role_data(member.guild.id, custom_role_data)


#########################################

class CustomRole(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        self.strip_roles.start()

    async def cog_unload(self):
        self.strip_roles.cancel()

    @discord.app_commands.command(
        name="make_custom_role",
        description="Create a custom role for yourself.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(role_name="Role name. Maximum of 7 symbols.",
                                   color_code="Hex color code. Example: #A47267",
                                   role_icon="Image that should be used.")
    @discord.app_commands.default_permissions(send_messages=True)
    async def make_custom_role(self, interaction: discord.Interaction, role_name: str, color_code: str,
                               role_icon: discord.Attachment = None):
        await interaction.response.defer()

        allowed = False
        user_role_names = [role.name for role in interaction.user.roles]
        allowed_roles = await fetch_allowed_roles(interaction.guild_id)
        if set(user_role_names) & set(allowed_roles):
            allowed = True

        if not allowed:
            await interaction.edit_original_response(
                content=f"You need one of the following roles for custom role creation: {', '.join(allowed_roles)}")
            return

        custom_role_data = await fetch_custom_role_data(interaction.guild_id)

        if len(role_name) > 7:
            await interaction.edit_original_response(
                content="Please use a shorter role name. Restrict yourself to 7 symbols.")
            return

        if str(interaction.user.id) in custom_role_data:
            await clear_custom_role_data(interaction.user)

        if role_name in [role.name for role in interaction.guild.roles]:
            await interaction.edit_original_response(content="You can't use this role name.")
            return

        color_match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color_code)
        if not color_match:
            await interaction.edit_original_response(content="Please enter a valid hex color code.")
            return

        actual_color_code = int(re.findall(r'^#((?:[0-9a-fA-F]{3}){1,2})$', color_code)[0], base=16)
        discord_colour = discord.Colour(actual_color_code)

        reference_role = discord.utils.get(interaction.guild.roles, name='Pos. Reference Role')
        if not reference_role:
            await interaction.edit_original_response(content="This extension needs a positional reference role called"
                                                             "`Pos. Reference Role`. Please have the admin create it.")
            return

        if role_icon:
            display_icon = await role_icon.read()
            custom_role = await interaction.guild.create_role(name=role_name, colour=discord_colour,
                                                              display_icon=display_icon)
        else:
            custom_role = await interaction.guild.create_role(name=role_name, colour=discord_colour)
        positions = {custom_role: reference_role.position - 1}
        await interaction.guild.edit_role_positions(positions)
        await interaction.user.add_roles(custom_role)

        custom_role_data[str(interaction.user.id)] = custom_role.id
        await write_custom_role_data(interaction.guild_id, custom_role_data)
        await interaction.edit_original_response(content=f"Created your custom role: {custom_role.mention}")

    @discord.app_commands.command(
        name="delete_custom_role",
        description="Remove a custom role from yourself.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(send_messages=True)
    async def delete_custom_role(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await clear_custom_role_data(interaction.user)
        await interaction.edit_original_response(content="Deleted your custom role.")

    @discord.app_commands.command(
        name="_toggle_custom_role_perms",
        description="Allow or disallow a role custom role creation.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(role="The role that should be allowed or disallowed.")
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_custom_role_perms(self, interaction: discord.Interaction, role: discord.Role):
        allowed_roles = await fetch_allowed_roles(interaction.guild_id)
        if role.name in allowed_roles:
            allowed_roles.remove(role.name)
            action = "Forbid"
        else:
            allowed_roles.append(role.name)
            action = "Allowed"

        await write_allowed_roles(interaction.guild_id, allowed_roles)

        await interaction.response.send_message(
            f"{action} `{role.name}` custom role creation! "
            f"Roles allowed custom role creation are now: {', '.join(allowed_roles)}")

    @tasks.loop(minutes=200)
    async def strip_roles(self):
        await asyncio.sleep(180)
        for guild in self.bot.guilds:
            allowed_roles = await fetch_allowed_roles(guild.id)
            custom_role_data = await fetch_custom_role_data(guild.id)
            for member_id in custom_role_data:
                member = guild.get_member(int(member_id))
                if member:
                    if set([role.name for role in member.roles]) & set(allowed_roles):
                        custom_role_allowed = True
                    else:
                        custom_role_allowed = False
                    if not custom_role_allowed:
                        await asyncio.sleep(5)
                        await clear_custom_role_data(member)
                        print(f"CUSTOM ROLE: Removed custom role from {str(member)}.")
                else:
                    new_custom_role_data = await fetch_custom_role_data(guild.id)
                    role_id = custom_role_data[member_id]
                    role = guild.get_role(role_id)
                    if role:
                        await role.delete()
                    del new_custom_role_data[member_id]
                    await write_custom_role_data(guild.id, new_custom_role_data)


async def setup(bot):
    await bot.add_cog(CustomRole(bot))

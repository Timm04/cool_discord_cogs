"""Allow creationg of custom roles"""
import asyncio

import discord
import re
from discord.ext import commands
from discord.ext import tasks


class CustomRole(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.strip_roles.start()

    async def cog_unload(self):
        self.strip_roles.cancel()

    @discord.app_commands.command(
        name="make_custom_role",
        description="Create a custom role for yourself.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(send_messages=True)
    async def make_custom_role(self, interaction: discord.Interaction, role_name: str, color_code: str, role_icon: discord.Attachment = None):
        await interaction.response.defer()
        active, reference_role_name = await self.bot.open_json_file(interaction.guild, "custom_role_status.json", list())
        if not active:
            await interaction.edit_original_response(content="Custom role creation is deactivated.")
            return

        if role_name in [role.name for role in interaction.guild.roles]:
            await interaction.edit_original_response(content="You can't use this role name.")
            return

        allowed = False
        allowed_roles = await self.bot.open_json_file(interaction.guild, "custom_creation_allowed_roles.json", list())
        for role in interaction.user.roles:
            if role.name in allowed_roles:
                allowed = True

        if not allowed:
            await interaction.edit_original_response(content=f"You need one of the following roles for custom role creation: {', '.join(allowed_roles)}")
            return

        custom_role_data = await self.bot.open_json_file(interaction.guild, "custom_role_data.json", dict())

        # Role already exists
        if str(interaction.user.id) in custom_role_data:
            await self.clear_user(interaction.user)

        if len(role_name) > 7:
            await interaction.edit_original_response(content="Please use a shorter role name. Restrict yourself to 7 symbols.")
            return

        color_match = re.search(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color_code)
        if not color_match:
            await interaction.edit_original_response(content="Please enter a valid hex color code.")
            return

        actual_color_code = int(re.findall(r'^#((?:[0-9a-fA-F]{3}){1,2})$', color_code)[0], base=16)
        discord_colour = discord.Colour(actual_color_code)

        reference_role = discord.utils.get(interaction.guild.roles, name=reference_role_name)
        if not reference_role:
            raise ValueError("Could not find custom role reference role.")

        if role_icon:
            display_icon = await role_icon.read()
            custom_role = await interaction.guild.create_role(name=role_name, colour=discord_colour, display_icon=display_icon)
        else:
            custom_role = await interaction.guild.create_role(name=role_name, colour=discord_colour)
        positions = {custom_role: reference_role.position - 1}
        await interaction.guild.edit_role_positions(positions)
        await interaction.user.add_roles(custom_role)

        custom_role_data[str(interaction.user.id)] = custom_role.id
        await self.bot.write_json_file(interaction.guild, "custom_role_data.json", custom_role_data)
        await interaction.edit_original_response(content=f"Created your custom role: {custom_role.mention}")

    @discord.app_commands.command(
        name="delete_custom_role",
        description="Remove a custom role from yourself.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(send_messages=True)
    async def delete_custom_role(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.clear_user(interaction.user)
        await interaction.edit_original_response(content="Done.")

    async def clear_user(self, member: discord.Member):
        await asyncio.sleep(5)
        custom_role_data = await self.bot.open_json_file(member.guild, "custom_role_data.json", dict())
        if str(member.id) in custom_role_data:
            role_id = custom_role_data.get(str(member.id))
            custom_role = member.guild.get_role(role_id)
            if custom_role:
                await custom_role.delete()
            del custom_role_data[str(member.id)]
            await self.bot.write_json_file(member.guild, "custom_role_data.json", custom_role_data)

    @discord.app_commands.command(
        name="_activate_custom_roles",
        description="Activate the creation of custom roles.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(active="Whether custom role creation should be active.",
                                   reference_role="The role UNDER which custom roles should be created.")
    @discord.app_commands.default_permissions(administrator=True)
    async def activate_custom_roles(self, interaction: discord.Interaction, active: bool, reference_role: discord.Role):
        custom_role_status = (active, reference_role.name)
        await self.bot.write_json_file(interaction.guild, "custom_role_status.json", custom_role_status)
        await interaction.response.send_message(f"Set custom role creation to {active}; Roles sorted under `{reference_role.name}`")

    @discord.app_commands.command(
        name="_set_custom_role_perms",
        description="Allow or disallow a role custom role creation.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(role="The role that should be allowed or disallowed.",
                                   allow="Whether to allow or to disallow.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_custom_role_perms(self, interaction: discord.Interaction, role: discord.Role, allow: bool):
        allowed_roles = await self.bot.open_json_file(interaction.guild, "custom_creation_allowed_roles.json", list())
        if allow:
            if role.name not in allowed_roles:
                allowed_roles.append(role.name)
        else:
            if role.name in allowed_roles:
                allowed_roles.remove(role.name)

        await self.bot.write_json_file(interaction.guild, "custom_creation_allowed_roles.json", allowed_roles)

        await interaction.response.send_message(f"Updated settings! Roles allowed custom role creation are now: {', '.join(allowed_roles)}")

    @tasks.loop(minutes=200)
    async def strip_roles(self):
        await asyncio.sleep(180)
        for guild in self.bot.guilds:
            allowed_roles = await self.bot.open_json_file(guild, "custom_creation_allowed_roles.json", list())
            custom_role_data = await self.bot.open_json_file(guild, "custom_role_data.json", dict())
            new_custom_role_data = await self.bot.open_json_file(guild, "custom_role_data.json", dict())
            for member_id in custom_role_data:
                member = guild.get_member(int(member_id))
                if member:
                    custom_role_allowed = False
                    for role in member.roles:
                        if role.name in allowed_roles:
                            custom_role_allowed = True
                    if not custom_role_allowed:
                        await self.clear_user(member)
                        print(f"Removed custom role from {str(member)}.")
                else:
                    role_id = custom_role_data[member_id]
                    role = guild.get_role(role_id)
                    if role:
                        await role.delete()
                    del new_custom_role_data[member_id]
                    await self.bot.write_json_file(guild, "custom_role_data.json", new_custom_role_data)

async def setup(bot):
    await bot.add_cog(CustomRole(bot))

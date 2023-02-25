"""Cog that lets users add roles to themselves using a slash command.
Administrators can add and remove roles using slash commands."""
import discord
from discord.ext import commands

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "assignable_roles_settings"
SETTINGS_COLUMNS = ("guild_id", "assignable_roles", "forbidden_roles")


async def fetch_forbidden_roles(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id)


async def fetch_addable_roles(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id)


async def write_forbidden_roles(guild_id: int, forbidden_roles_data: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], forbidden_roles_data,
                                       guild_id=guild_id)


async def write_addable_roles(guild_id: int, addable_roles_data: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], addable_roles_data, guild_id=guild_id)


#########################################

# Select menus to add and remove roles

class SelectRolesToAdd(discord.ui.Select):

    def __init__(self, my_guild: discord.Guild, choice_count):
        super().__init__(max_values=choice_count)
        self.guild = my_guild

    async def callback(self, interaction: discord.Interaction):
        role_names = self.values
        role_list = [discord.utils.get(self.guild.roles, name=role_name) for role_name in role_names]
        await interaction.user.add_roles(*role_list)
        await interaction.response.send_message(
            f"{interaction.user.mention} Added the following roles to you: "
            f"{', '.join([role.mention for role in role_list])}",
            ephemeral=True)


class SelectRolesToRemove(discord.ui.Select):

    def __init__(self, my_guild: discord.Guild, choice_count):
        super().__init__(max_values=choice_count)
        self.guild = my_guild

    async def callback(self, interaction: discord.Interaction):
        role_names = self.values
        role_list = [discord.utils.get(self.guild.roles, name=role_name) for role_name in role_names]
        await interaction.user.remove_roles(*role_list)
        await interaction.response.send_message(
            f"{interaction.user.mention} Removed the following roles from you: "
            f"{', '.join([role.mention for role in role_list])}",
            ephemeral=True)


#########################################

# Load options for the add_roles and remove_roles views
async def load_options(interaction, remove_roles=False):
    addable_roles_list = await fetch_addable_roles(interaction.guild_id)
    if not addable_roles_list:
        await interaction.response.send_message("There seem to be no self assignable roles.")
        return False

    if remove_roles:
        my_role_selection = SelectRolesToRemove(interaction.guild, len(addable_roles_list))
    else:
        my_role_selection = SelectRolesToAdd(interaction.guild, len(addable_roles_list))
    for role_data in addable_roles_list:
        my_role_selection.add_option(label=role_data[0], description=role_data[2], emoji=role_data[1])
    return my_role_selection


# Check for command execution
async def check_if_allowed_to_add_roles(interaction: discord.Interaction):
    forbidden_roles_list = await fetch_forbidden_roles(interaction.guild_id)
    for role_name in [role.name for role in interaction.user.roles]:
        if role_name in forbidden_roles_list:
            await interaction.response.send_message(f"{interaction.user.mention} You are not allowed to self-assign "
                                                    f"roles.", ephemeral=True)
            return False
    return True


#########################################

class AssignableRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)

    @discord.app_commands.command(
        name="add_roles",
        description="Brings up the role selection menu. Add roles to yourself!")
    @discord.app_commands.guild_only()
    @discord.app_commands.check(check_if_allowed_to_add_roles)
    async def add_roles(self, interaction: discord.Interaction):
        view_object = discord.ui.View()
        my_role_selection = await load_options(interaction)
        if my_role_selection:
            view_object.add_item(my_role_selection)
            await interaction.response.send_message(f"{interaction.user.mention} Select roles to **add** to yourself:",
                                                    view=view_object,
                                                    ephemeral=True)

    @discord.app_commands.command(
        name="remove_roles",
        description="Brings up the role selection menu. Remove roles from yourself.")
    @discord.app_commands.guild_only()
    async def remove_roles(self, interaction: discord.Interaction):
        view_object = discord.ui.View()
        my_role_selection = await load_options(interaction, remove_roles=True)
        if my_role_selection:
            view_object.add_item(my_role_selection)
            await interaction.response.send_message(
                f"{interaction.user.mention} Select roles to **remove** from yourself:",
                view=view_object,
                ephemeral=True)

    @discord.app_commands.command(
        name="_add_role_to_assignable",
        description="Add a role to the list of self assignable roles.")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(role='The role to add to the list of self-assignables.',
                                   emoji='The emoji the role should be represented by.',
                                   description='A description of the role to be added.')
    @discord.app_commands.guild_only()
    async def add_role_to_assignable(self, interaction: discord.Interaction,
                                     role: discord.Role,
                                     emoji: str, description: str):
        addable_roles_list = await fetch_addable_roles(interaction.guild_id)

        role_data = (role.name, emoji, description)
        addable_roles_list.append(role_data)

        await write_addable_roles(interaction.guild_id, addable_roles_list)

        await interaction.response.send_message(
            f"Added the role '{role.mention}' to the list of self-assignable roles.",
            ephemeral=True)

    @discord.app_commands.command(
        name="_remove_role_from_assignable",
        description="Remove a role from the list of self assignable roles.")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(role='The role to remove from the list of self-assignables.')
    @discord.app_commands.guild_only()
    async def remove_role_from_assignable(self, interaction: discord.Interaction, role: discord.Role):
        addable_roles_list = await fetch_addable_roles(interaction.guild_id)

        for role_data in addable_roles_list:
            if role.name == role_data[0]:
                addable_roles_list.remove(role_data)

        await write_addable_roles(interaction.guild_id, addable_roles_list)
        await interaction.response.send_message(
            f"Removed the role '{role.mention}' from the list of self-assignable roles.",
            ephemeral=True)

    @discord.app_commands.command(
        name="_toggle_role_assign_permission",
        description="Forbid a role from assigning themselves roles.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(role="The role to add to the list of roles that can't self assign.")
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_role_assign_permission(self, interaction: discord.Interaction, role: discord.Role):
        forbidden_roles_list = await fetch_forbidden_roles(interaction.guild_id)

        if role.name in forbidden_roles_list:
            operation = "Allowed"
            forbidden_roles_list.remove(role.name)
        else:
            operation = "Forbid"
            forbidden_roles_list.append(role.name)

        await write_forbidden_roles(interaction.guild_id, forbidden_roles_list)
        await interaction.response.send_message(f"{operation} the role {role.mention} to self-assign roles.",
                                                ephemeral=True)

    # TODO: Add a task that regularly checks whether all added roles still exist and if not removes them.


async def setup(bot):
    await bot.add_cog(AssignableRoles(bot))

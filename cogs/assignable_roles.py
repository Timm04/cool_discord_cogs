"""Self assignable roles."""
import discord
from discord.ext import commands
from discord.ext import tasks
from pathlib import Path
import json

class SelectRolesToAdd(discord.ui.Select):

    def __init__(self, my_guild: discord.Guild, choice_count):
        super().__init__(max_values=choice_count)
        self.guild = my_guild

    async def callback(self, interaction: discord.Interaction):
        role_names = self.values
        role_list = [discord.utils.get(self.guild.roles, name=role_name) for role_name in role_names]
        await interaction.user.add_roles(*role_list)
        await interaction.response.send_message(
            f"{interaction.user.mention} Added the following roles to you: {', '.join(role_names)}")

class SelectRolesToRemove(discord.ui.Select):

    def __init__(self, my_guild: discord.Guild, choice_count):
        super().__init__(max_values=choice_count)
        self.guild = my_guild

    async def callback(self, interaction: discord.Interaction):
        role_names = self.values
        role_list = [discord.utils.get(self.guild.roles, name=role_name) for role_name in role_names]
        await interaction.user.remove_roles(*role_list)
        await interaction.response.send_message(
            f"{interaction.user.mention} Removed the following roles from you: {', '.join(role_names)}")

class AssignableRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        pass

    async def load_options(self, interaction, remove_roles=False):
        addable_roles_list = await self.bot.open_json_file(interaction.guild, "addable_roles.json", list())
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

    @discord.app_commands.command(
        name="add_roles",
        description="Brings up the role selection menu. Add roles to yourself!")
    @discord.app_commands.guild_only()
    async def add_roles(self, interaction: discord.Interaction):
        forbidden_roles_list = await self.bot.open_json_file(interaction.guild, "forbidden_roles.json", list())
        for forbidden_role_name in forbidden_roles_list:
            for user_role_name in [role.name for role in interaction.user.roles]:
                if forbidden_role_name == user_role_name:
                    await interaction.response.send_message(
                        f"{interaction.user.mention} You are not allowed to self-assign roles.")
                    return

        view_object = discord.ui.View(timeout=60)
        my_role_selection = await self.load_options(interaction)
        if my_role_selection:
            view_object.add_item(my_role_selection)
            await interaction.response.send_message(
                f"{interaction.user.mention} Select roles to **add** to yourself:", view=view_object)
        await view_object.wait()
        await interaction.delete_original_response()

    @discord.app_commands.command(
        name="remove_roles",
        description="Brings up the role selection menu. Remove roles from yourself.")
    @discord.app_commands.guild_only()
    async def remove_roles(self, interaction: discord.Interaction):
        view_object = discord.ui.View()
        my_role_selection = await self.load_options(interaction, remove_roles=True)
        if my_role_selection:
            view_object.add_item(my_role_selection)
            await interaction.response.send_message(
                f"{interaction.user.mention} Select roles to **remove** from yourself:", view=view_object)
            await view_object.wait()
            await interaction.edit_original_response(content="Command call timed out.", view=None)

    @discord.app_commands.command(
        name="_add_role_to_assignable",
        description="Add a role to the list of self assignable roles.")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(role='The role to add to the list of self-assignables.',
                                   emoji='The emoji the role should be represented by.',
                                   description='A description of the role to be added.')
    @discord.app_commands.guild_only()
    async def add_role_to_assignable(self, interaction: discord.Interaction, role: discord.Role,
                                     emoji: str, description: str):
        addable_roles_list = await self.bot.open_json_file(interaction.guild, "addable_roles.json", list())

        role_data = (role.name, emoji, description)
        addable_roles_list.append(role_data)

        await self.bot.write_json_file(interaction.guild, "addable_roles.json", addable_roles_list)

        await interaction.response.send_message(f"Added the role '{role.name}' to the list of self-assignable roles.")

    @discord.app_commands.command(
        name="_remove_role_from_assignable",
        description="Remove a role from the list of self assignable roles.")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.describe(role='The role to add to the list of self-assignables.')
    @discord.app_commands.guild_only()
    async def remove_role_from_assignable(self, interaction: discord.Interaction, role: discord.Role):
        addable_roles_list = await self.bot.open_json_file(interaction.guild, "addable_roles.json", list())

        for role_data in addable_roles_list:
            if role.name == role_data[0]:
                addable_roles_list.remove(role_data)

        await self.bot.write_json_file(interaction.guild, "addable_roles.json", addable_roles_list)

        await interaction.response.send_message(f"Removed the role '{role.name}' from the list of self-assignable roles.")

    @discord.app_commands.command(
        name="_toggle_role_assign_permission",
        description="Forbid a role from assigning themselves roles.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(role="The role to add to the list of roles that can't self assign.")
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_role_assign_permission(self, interaction: discord.Interaction, role:discord.Role):
        forbidden_roles_list = await self.bot.open_json_file(interaction.guild, "forbidden_roles.json", list())

        if role.name in forbidden_roles_list:
            operation = "Allowed"
            forbidden_roles_list.remove(role.name)
        else:
            operation = "Forbid"
            forbidden_roles_list.append(role.name)

        await self.bot.write_json_file(interaction.guild, "forbidden_roles.json", forbidden_roles_list)

        await interaction.response.send_message(f"{operation} the role `{role.name}` to self-assign roles.")

async def setup(bot):
    await bot.add_cog(AssignableRoles(bot))
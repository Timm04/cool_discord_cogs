"""Automatically receive roles."""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks

async def autocomplete_autoreceive(interaction: discord.Interaction, current_input: str):
    auto_receive_data = await interaction.client.open_json_file(interaction.guild, "auto_receive_roles.json", list())
    possible_options = []
    for role_to_have, role_to_get in auto_receive_data:
        if current_input in role_to_have or current_input in role_to_get:
            possible_options.append(discord.app_commands.Choice(name=f"{role_to_have} -> {role_to_get}",
                                                                value=f"{role_to_have}+{role_to_get}"))

    return possible_options[0:25]

class AutoReceive(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
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
        auto_receive_data = await self.bot.open_json_file(interaction.guild, "auto_receive_roles.json", list())
        auto_receive_data.append((role_to_have.name, role_to_get.name))
        await self.bot.write_json_file(interaction.guild, "auto_receive_roles.json", auto_receive_data)
        await interaction.response.send_message(f"Added `{role_to_have.name} -> {role_to_get.name}` auto receive.")

    @discord.app_commands.command(
        name="_remove_auto_receive",
        description="Remove a role auto receive setting.")
    @discord.app_commands.guild_only()
    @discord.app_commands.autocomplete(receive_string=autocomplete_autoreceive)
    @discord.app_commands.describe(receive_string="Which receive data should be removed.")
    @discord.app_commands.default_permissions(administrator=True)
    async def remove_auto_receive(self, interaction: discord.Interaction, receive_string: str):
        auto_receive_data = await self.bot.open_json_file(interaction.guild, "auto_receive_roles.json", list())
        role_to_have_name, role_to_receive_name = receive_string.split("+")
        auto_receive_data.remove([role_to_have_name, role_to_receive_name])
        await self.bot.write_json_file(interaction.guild, "auto_receive_roles.json", auto_receive_data)
        await interaction.response.send_message(f"Removed the `{role_to_have_name} -> {role_to_receive_name}` assign.")

    @discord.app_commands.command(
        name="_ban_auto_receive",
        description="Ban a member from automatically receiving roles.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(member="The member that should be banned.",
                                   role="The role that should no longer be given.")
    @discord.app_commands.default_permissions(administrator=True)
    async def ban_auto_receive(self, interaction: discord.Interaction, member: discord.Member,
                                  role: discord.Role):
        if role in member.roles:
            await member.remove_roles(role)

        banned_user_data = await self.bot.open_json_file(interaction.guild, "auto_receive_banned_data.json", list())
        banned_user_data.append([member.id, role.name])
        await self.bot.write_json_file(interaction.guild, "auto_receive_banned_data.json", banned_user_data)
        await interaction.response.send_message(f"Banned {member} from automatically getting the role {role.name}.")

    @tasks.loop(minutes=10)
    async def give_auto_roles(self):
        await asyncio.sleep(400)
        for guild in self.bot.guilds:
            auto_receive_data = await self.bot.open_json_file(guild, "auto_receive_roles.json", list())
            banned_user_data = await self.bot.open_json_file(guild, "auto_receive_banned_data.json", list())
            for role_to_have_name, role_to_receive_name in auto_receive_data:
                role_to_have = discord.utils.get(guild.roles, name=role_to_have_name)
                role_to_receive = discord.utils.get(guild.roles, name=role_to_receive_name)
                if not role_to_have or not role_to_receive:
                    raise ValueError("Role to receive or role to have not found.")
                for member in role_to_have.members:

                    banned = False
                    for banned_id, role_name in banned_user_data:
                        if member.id == banned_id and role_to_receive.name == role_name:
                            banned = True

                    if role_to_receive not in member.roles and not banned:
                        print(f"Gave {member} the role {role_to_receive}")
                        await member.add_roles(role_to_receive)

async def setup(bot):
    await bot.add_cog(AutoReceive(bot))

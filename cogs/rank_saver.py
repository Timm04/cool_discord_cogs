"""Backup role data"""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "rank_saver"
SETTINGS_COLUMNS = (
    "guild_id", "rank_saver_status", "rank_restoration_status", "rank_data", "excluded_roles", "announce_channel_name")


async def fetch_rank_saver_status(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id)


async def write_rank_saver_status(guild_id: int, rank_saver_status):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], rank_saver_status, guild_id=guild_id)


async def fetch_restoration_status(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id)


async def write_restoration_status(guild_id: int, restoration_status):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], restoration_status, guild_id=guild_id)


async def fetch_rank_data(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3], guild_id=guild_id,
                                             default_type=dict)


async def write_rank_data(guild_id: int, rank_data):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3], rank_data, guild_id=guild_id)


async def fetch_excluded_roles(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[4], guild_id=guild_id)


async def write_excluded_roles(guild_id: int, excluded_roles):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[4], excluded_roles, guild_id=guild_id)


async def fetch_announce_chanel_name(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[5], guild_id=guild_id)


async def write_announce_channel_name(guild_id: int, channel_name):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[5], channel_name, guild_id=guild_id)


#########################################

ROLES_TO_NOT_SAVE = ("@everyone", "Server Booster")


#########################################

class RankSaver(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        self.rank_saver.start()

    @tasks.loop(minutes=10.0)
    async def rank_saver(self):
        await asyncio.sleep(60)
        for guild in self.bot.guilds:
            to_save = await fetch_rank_saver_status(guild.id)
            if to_save:
                user_roles_dictionary = await fetch_rank_data(guild.id)
                all_members = [member for member in guild.members if member.bot is False]

                for member in all_members:
                    member_roles = [role.name for role in member.roles if role.name not in ROLES_TO_NOT_SAVE]
                    user_roles_dictionary[str(member.id)] = member_roles

                await write_rank_data(guild.id, user_roles_dictionary)

    @discord.app_commands.command(
        name="_toggle_rank_saver",
        description="Enable/Disable rank saving.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_rank_saver(self, interaction: discord.Interaction):
        to_save = await fetch_rank_saver_status(interaction.guild_id)
        if to_save:
            to_save = False
            await write_rank_saver_status(interaction.guild_id, to_save)
            await interaction.response.send_message("Disabled rank saver.")
        else:
            to_save = True
            await write_rank_saver_status(interaction.guild_id, to_save)
            await interaction.response.send_message("Enabled rank saver.")

    @discord.app_commands.command(
        name="_toggle_rank_restorer",
        description="Enable/Disable rank restoration.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_rank_restorer(self, interaction: discord.Interaction):
        to_restore = await fetch_restoration_status(interaction.guild_id)
        if to_restore:
            to_restore = False
            await write_restoration_status(interaction.guild_id, to_restore)
            await interaction.response.send_message("Disabled rank restoration.")
        else:
            to_restore = True
            await write_restoration_status(interaction.guild_id, to_restore)
            await interaction.response.send_message("Enabled rank restoration.")

    @discord.app_commands.command(
        name="_select_restore_announce_channel",
        description="Select the chanel in which the rank restoration message should be sent. Again to deactivated.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="Channel in which the role restoration message should be sent.")
    @discord.app_commands.default_permissions(administrator=True)
    async def select_restore_announce_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        to_restore_channel = await fetch_announce_chanel_name(interaction.guild_id)
        if to_restore_channel == channel.name:
            to_restore_channel = str()
            await write_announce_channel_name(interaction.guild_id, to_restore_channel)
            await interaction.response.send_message("Deactivated the rank restoration announcement.")
        else:
            to_restore_channel = channel.name
            await write_announce_channel_name(interaction.guild_id, to_restore_channel)
            await interaction.response.send_message(
                f"Set the rank restoration announcement channel to {channel.mention}.")

    @discord.app_commands.command(
        name="_exclude_role_from_restore",
        description="Exclude/Include (toggle) a role from being restored by the rank restorer.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(role="Role which should not be restored.")
    @discord.app_commands.default_permissions(administrator=True)
    async def exclude_role_from_restore(self, interaction: discord.Interaction, role: discord.Role):
        roles_to_not_restore = await fetch_excluded_roles(interaction.guild_id)
        if role.name not in roles_to_not_restore:
            roles_to_not_restore.append(role.name)
            await write_excluded_roles(interaction.guild_id, roles_to_not_restore)
            await interaction.response.send_message(f"Deactivated restoration of the role {role.mention}",
                                                    allowed_mentions=discord.AllowedMentions.none())
        else:
            roles_to_not_restore.remove(role.name)
            await write_excluded_roles(interaction.guild_id, roles_to_not_restore)
            await interaction.response.send_message(f"Activated restoration of the role {role.mention}",
                                                    allowed_mentions=discord.AllowedMentions.none())

    @commands.Cog.listener(name="on_member_join")
    async def rank_restorer(self, member: discord.Member):
        to_restore = await fetch_restoration_status(member.guild.id)
        if not to_restore:
            return
        user_roles_dictionary = await fetch_rank_data(member.guild.id)
        role_names = user_roles_dictionary.get(str(member.id))
        roles_to_not_restore = await fetch_excluded_roles(member.guild.id)
        if role_names:
            await asyncio.sleep(8)
            roles_to_restore = [discord.utils.get(member.guild.roles, name=role_name) for role_name in role_names]
            roles_to_restore = [role for role in roles_to_restore if role and role.name not in roles_to_not_restore]
            roles_to_remove = [role for role in member.roles if role.name not in ROLES_TO_NOT_SAVE]
            await member.remove_roles(*roles_to_remove)
            await member.add_roles(*roles_to_restore)
        else:
            return
        to_restore_channel_name = await fetch_announce_chanel_name(member.guild.id)
        if to_restore_channel_name:
            to_restore_channel = discord.utils.get(member.guild.channels, name=to_restore_channel_name)
            await to_restore_channel.send(f"Restored **{', '.join([role.name for role in roles_to_restore])}** for"
                                          f"{member.mention}.")


async def setup(bot):
    await bot.add_cog(RankSaver(bot))

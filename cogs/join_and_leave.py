"""Cog that lets you set up join and leave message."""
import asyncio

import discord
from discord.ext import commands

from . import data_management
from . import levelup

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "join_and_leave_message_settings"
SETTINGS_COLUMNS = ("guild_id", "join_message_settings", "additional_join_message_settings", "leave_message_settings")


async def fetch_join_message_settings(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id,
                                             default_type=list)


async def fetch_add_join_message_settings(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], guild_id=guild_id,
                                             default_type=list)


async def fetch_leave_message_settings(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3], guild_id=guild_id,
                                             default_type=list)


async def write_join_message_settings(guild_id: int, join_message_settings: tuple):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], join_message_settings,
                                       guild_id=guild_id)


async def write_add_join_message_settings(guild_id: int, join_message_settings: tuple):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], join_message_settings,
                                       guild_id=guild_id)


async def write_leave_message_settings(guild_id: int, leave_message_settings: tuple):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3], leave_message_settings,
                                       guild_id=guild_id)


#########################################

class ChangeMessageModal(discord.ui.Modal):
    def __init__(self, bot, channel, upload_file, active, default_role=None, is_join=True):
        super().__init__(title="Set the new join message.")
        self.bot = bot
        self.channel = channel
        self.active = active
        self.upload_file = upload_file
        self.is_join = is_join
        if default_role:
            self.default_role_name = default_role.name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        if self.upload_file:
            file_path = await self.save_file_from_attachment()
        else:
            file_path = False

        if self.is_join:
            join_message_settings = (
                self.children[0].value, self.channel.name, file_path, self.active, self.default_role_name)
            await write_join_message_settings(interaction.guild_id, join_message_settings)
            await interaction.edit_original_response(content="Updated join message settings.")
        else:
            leave_message_settings = (self.children[0].value, self.channel.name, file_path, self.active)
            await write_leave_message_settings(interaction.guild_id, leave_message_settings)
            await interaction.edit_original_response(content="Updated leave message settings.")

    async def save_file_from_attachment(self):
        file_path = f"data/server_files/{self.upload_file.filename}"
        await self.upload_file.save(file_path)
        return file_path


class SecondJoinMessageModal(discord.ui.Modal):
    def __init__(self, bot, channel, active):
        super().__init__(title="Set the second new join message.")
        self.bot = bot
        self.channel = channel
        self.active = active

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        join_message_settings = (self.children[0].value, self.channel.name, self.active)
        await write_add_join_message_settings(interaction.guild_id, join_message_settings)
        await interaction.edit_original_response(content="Updated second join message settings.")


class JoinAndLeave(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)

    @discord.app_commands.command(
        name="_set_join_msg",
        description=r"Set up the join message for new members. Templates: <GUILDNAME> <USERMENTION> <CREATIONDATE>")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="The channel in which join messages should be sent.",
                                   upload_file="The file that should be sent, if any",
                                   default_role="Role that should be given on member join",
                                   active="Whether the join message should be sent at all.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_join_msg(self, interaction: discord.Interaction, channel: discord.TextChannel,
                           default_role: discord.Role, active: bool,
                           upload_file: discord.Attachment= None):

        current_settings = await fetch_join_message_settings(interaction.guild_id)
        if current_settings:
            current_message = current_settings[0]
        else:
            current_message = "Templates: \n<GUILDNAME> for guild name.\n<USERMENTION> for user mention." \
                              "\n<CREATIONDATE> for account creation date."

        input_message_modal = ChangeMessageModal(self.bot, channel, upload_file, active, default_role)
        input_message_modal.add_item(discord.ui.TextInput(label="New join message",
                                                          style=discord.TextStyle.paragraph,
                                                          default=current_message))

        await interaction.response.send_modal(input_message_modal)

    @discord.app_commands.command(
        name="_set_second_join_msg",
        description=r"Set up an additional join message. Templates: <GUILDNAME> <USERMENTION> <CREATIONDATE>")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="The channel in which join messages should be sent.",
                                   active="Whether the join message should be sent at all.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_second_join_msg(self, interaction: discord.Interaction, channel: discord.TextChannel, active: bool):

        current_settings = await fetch_add_join_message_settings(interaction.guild_id)
        if current_settings:
            current_message = current_settings[0]
        else:
            current_message = "Templates: \n<GUILDNAME> for guild name.\n<USERMENTION> for user mention." \
                              "\n<CREATIONDATE> for account creation date. \n<USERNAME> for username."

        input_message_modal = SecondJoinMessageModal(self.bot, channel, active)
        input_message_modal.add_item(discord.ui.TextInput(label="New join message",
                                                          style=discord.TextStyle.paragraph,
                                                          default=current_message))

        await interaction.response.send_modal(input_message_modal)

    @discord.app_commands.command(
        name="_set_leave_msg",
        description=r"Set up the leave message for new members  Templates: <USERNAME> <RANK>")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="The channel to which the leave message should be sent.",
                                   upload_file="The file that should be sent if any.",
                                   active="Whether a leave message should be sent at all.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_leave_msg(self, interaction: discord.Interaction, channel: discord.TextChannel,
                            active: bool, upload_file: discord.Attachment = None):
        current_settings = await fetch_leave_message_settings(interaction.guild_id)
        if current_settings:
            current_message = current_settings[0]
        else:
            current_message = "Templates: \n<GUILDNAME> for guild name.\n<USERMENTION> for user mention.\n" \
                              "<RANK> for ordered rank. \n <USERNAME> for username."

        input_message_modal = ChangeMessageModal(self.bot, channel, upload_file, active, is_join=False)
        input_message_modal.add_item(discord.ui.TextInput(label="New leave message",
                                                          style=discord.TextStyle.paragraph,
                                                          default=current_message))

        await interaction.response.send_modal(input_message_modal)

    @commands.Cog.listener(name="on_member_join")
    async def send_join_message(self, member: discord.Member):
        join_message_settings = await fetch_join_message_settings(member.guild.id)
        try:
            message, channel_name, file_path, active, default_role_name = join_message_settings
        except ValueError:
            return
        if active:
            join_channel = discord.utils.get(member.guild.channels, name=channel_name)
            if not join_channel:
                raise ValueError("Join message channel can't be found.")

            message = message.replace("<GUILDNAME>", member.guild.name)
            message = message.replace("<USERMENTION>", member.mention)
            message = message.replace("<USERNAME>", str(member))
            message = message.replace("<CREATIONDATE>", str(member.created_at)[0:10])
            if file_path:
                await join_channel.send(message, file=discord.File(file_path))
            else:
                await join_channel.send(message)

            if default_role_name:
                default_role = discord.utils.get(member.guild.roles, name=default_role_name)
                if default_role:
                    await member.add_roles(default_role)

        add_join_message_settings = await fetch_add_join_message_settings(member.guild.id)
        try:
            message, channel_name, active = add_join_message_settings
        except ValueError:
            return
        if active:
            join_channel = discord.utils.get(member.guild.channels, name=channel_name)
            if not join_channel:
                raise ValueError("Second join message channel can't be found.")

            message = message.replace("<GUILDNAME>", member.guild.name)
            message = message.replace("<USERMENTION>", member.mention)
            message = message.replace("<USERNAME>", str(member))
            message = message.replace("<CREATIONDATE>", str(member.created_at)[0:10])
            await join_channel.send(message)

    @commands.Cog.listener(name="on_member_remove")
    async def send_leave_message(self, member: discord.Member):
        leave_message_settings = await fetch_leave_message_settings(member.guild.id)
        try:
            message, channel_name, file_path, active = leave_message_settings
        except ValueError:
            return
        if not active:
            return
        leave_channel = discord.utils.get(member.guild.channels, name=channel_name)
        if not leave_channel:
            raise ValueError("Leave message channel can't be found.")

        if "<RANK>" in message:
            # TODO: Put in function to retrieve the rank
            user_rank_string = await levelup.fetch_user_rank_name(member)
            message = message.replace("<RANK>", user_rank_string)

        message = message.replace("<GUILDNAME>", member.guild.name)
        message = message.replace("<USERMENTION>", member.mention)
        if member.nick:
            message = message.replace("<USERNAME>", f"{str(member)} ({member.nick})")
        else:
            message = message.replace("<USERNAME>", str(member))
        if file_path:
            await leave_channel.send(message, file=discord.File(file_path))
        else:
            await leave_channel.send(message)


async def setup(bot):
    await bot.add_cog(JoinAndLeave(bot))

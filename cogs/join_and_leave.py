"""Cog Description"""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks

class ChangeMessageModal(discord.ui.Modal):
    def __init__(self, bot, channel, upload_file, active, default_role=None, is_join=True):
        super().__init__(title="Set the new join message.")
        self.bot = bot
        self.channel = channel
        self.active = active
        self.upload_file = upload_file
        self.is_join = is_join
        self.default_role_name = default_role.name

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        if self.upload_file:
            file_path = await self.save_file_from_attachment(interaction)
        else:
            file_path = False

        if self.is_join:
            join_message_settings = (self.children[0].value, self.channel.name, file_path, self.active, self.default_role_name)
            await self.bot.write_json_file(interaction.guild, "join_message_settings.json", join_message_settings)
            await interaction.edit_original_response(content="Updated join message settings.")
        else:
            leave_message_settings = (self.children[0].value, self.channel.name, file_path, self.active)
            await self.bot.write_json_file(interaction.guild, "leave_message_settings.json", leave_message_settings)
            await interaction.edit_original_response(content="Updated leave message settings.")

    async def save_file_from_attachment(self, interaction: discord.Interaction):
        request_message = await interaction.channel.send(f"{interaction.user.mention} Please upload the file that "
                                                         f"should be uploaded:")

        def response_check(check_message):
            if check_message.author.id == interaction.user.id:
                if check_message.attachments:
                    return True
            return False

        upload_message = await self.bot.wait_for('message', timeout=60.0, check=response_check)
        file_name = upload_message.attachments[0].filename
        path = f"data/{interaction.guild.id}/{file_name}"
        await upload_message.attachments[0].save(path)

        notify_message = await interaction.channel.send(f"{interaction.user.mention} Saved your file!")
        await asyncio.sleep(3)
        to_delete_message = [request_message, upload_message, notify_message]

        def purge_check(check_message):
            if check_message in to_delete_message:
                return True
            else:
                return False

        await interaction.channel.purge(limit=30, check=purge_check)
        return path

class SecondJoinMessageModal(discord.ui.Modal):
    def __init__(self, bot, channel, active):
        super().__init__(title="Set the second new join message.")
        self.bot = bot
        self.channel = channel
        self.active = active

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        join_message_settings = (self.children[0].value, self.channel.name, self.active)
        await self.bot.write_json_file(interaction.guild, "2nd_join_message_settings.json", join_message_settings)
        await interaction.edit_original_response(content="Updated second join message settings.")

class JoinAndLeave(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        pass

    @discord.app_commands.command(
        name="set_join_msg",
        description=r"Set up the join message for new members. Templates: <GUILDNAME> <USERMENTION> <CREATIONDATE>")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="The channel in which join messages should be sent.",
                                   upload_file="Whether or not a file should be sent on join.",
                                   default_role="Role that should be given on member join",
                                   active="Whether the join message should be sent at all.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_join_msg(self, interaction: discord.Interaction, channel: discord.TextChannel,
                           upload_file: bool, default_role: discord.Role, active: bool):

        current_settings = await self.bot.open_json_file(interaction.guild, "join_message_settings.json", list())
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
        name="set_second_join_msg",
        description=r"Set up an additional join message. Templates: <GUILDNAME> <USERMENTION> <CREATIONDATE>")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="The channel in which join messages should be sent.",
                                   active="Whether the join message should be sent at all.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_second_join_msg(self, interaction: discord.Interaction, channel: discord.TextChannel, active: bool):

        current_settings = await self.bot.open_json_file(interaction.guild, "2nd_join_message_settings.json", list())
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
        name="set_leave_msg",
        description=r"Set up the leave message for new members  Templates: <USERNAME> <RANK>")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="The channel to which the leave message should be sent.",
                                   upload_file="Whether or not a file should be uploaded.",
                                   active="Whether a leave message should be sent at all.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_leave_msg(self, interaction: discord.Interaction, channel: discord.TextChannel, upload_file: bool, active: bool):
        current_settings = await self.bot.open_json_file(interaction.guild, "leave_message_settings.json", list())
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
        message, channel_name, file_path, active, default_role_name = await self.bot.open_json_file(member.guild, "join_message_settings.json", list())
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
                default_role = discord.utils.get(member.roles, name=default_role_name)
                if default_role:
                    await member.add_roles(default_role)

        message, channel_name, active = await self.bot.open_json_file(member.guild, "2nd_join_message_settings.json", list())
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
        message, channel_name, file_path, active = await self.bot.open_json_file(member.guild, "leave_message_settings.json", list())
        if not active:
            return
        leave_channel = discord.utils.get(member.guild.channels, name=channel_name)
        if not leave_channel:
            raise ValueError("Leave message channel can't be found.")

        if "<RANK>" in message:
            user_rank_string = await self.get_user_role_string(member)
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

    async def get_user_role_string(self, member: discord.Member):
        rank_system = await self.bot.open_json_file(member.guild, "rank_system.json", list())
        for rank in rank_system:
            role_name_to_check = rank[6]
            second_role_name_to_check = rank[5]
            for role in member.roles:
                if role.name == role_name_to_check:
                    return role_name_to_check
                elif role.name == second_role_name_to_check:
                    return second_role_name_to_check

        return "no rank data"

async def setup(bot):
    await bot.add_cog(JoinAndLeave(bot))

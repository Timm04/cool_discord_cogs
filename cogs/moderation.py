"""Cog providing some basic moderator tools"""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks
from datetime import datetime
from datetime import timedelta

class ModerationModal(discord.ui.Modal):
    def __init__(self, action_function_name, target_object, bot):
        super().__init__(title="Moderator Report")

        self.action_function_name = action_function_name.lower().replace(" ", "_")
        self.target_object = target_object
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        log_channel_name = await self.bot.open_json_file(interaction.guild, "moderator_channel.json", str())
        log_channel = discord.utils.get(interaction.guild.channels, name=log_channel_name)
        if not log_channel:
            raise ValueError("Not able to find moderation log channel.")

        report_embed = discord.Embed(title="Moderator Log",
                                     description=f"{interaction.user.mention} just performed a moderator action.",
                                     colour=discord.Colour.red())

        reason = self.children[0].value

        if self.action_function_name == "delete_message":
            performed_action = await self.delete_message()
            if not performed_action:
                await interaction.edit_original_response(content=
                    f"You cannot perform this action on that user, {interaction.user.display_name}!")
                return
            else:
                report_embed.add_field(name="Message Deletion",
                                       value=f"**Message author**: {self.target_object.author.mention}"
                                             f"\n**Name**: `{str(self.target_object.author)}`"
                                             f"\n**Author ID**: `{self.target_object.author.id}`"
                                             f"\n**Channel**: {self.target_object.channel.mention}"
                                             f"\n**Reason**: `{reason}`")
                await interaction.channel.send(embed=report_embed)
                report_embed.add_field(name="**Message Content**",
                                       value=f"`{self.target_object.content}`",
                                       inline=False)
                report_embed.add_field(name="Attachments",
                                       value=f"Message had `{len(self.target_object.attachments)}` attachments.")

        elif self.action_function_name == "purge_messages":
            performed_action = await self.purge_messages()
            if not performed_action:
                await interaction.edit_original_response(content=
                    f"You cannot perform this action on that user, {interaction.user.display_name}!")
                return
            else:
                messages_content = performed_action[1]
                report_embed.add_field(name=f"Message Purge ({self.children[1].value} Messages)",
                                       value=f"**Messages author**: {self.target_object.author.mention}"
                                             f"\n**Name**: `{str(self.target_object.author)}`"
                                             f"\n**Author ID**: `{self.target_object.author.id}`"
                                             f"\n**Channel**: {self.target_object.channel.mention}"
                                             f"\n**Reason**: `{reason}`")
                await interaction.channel.send(embed=report_embed)
                report_embed.add_field(name="**Messages Content**",
                                       value=f"`{messages_content}`\n[...]",
                                       inline=False)

        elif self.action_function_name == "timeout_user":
            performed_action = await self.timeout_member()
            if not performed_action:
                await interaction.edit_original_response(content=
                    f"You cannot perform this action on that user, {interaction.user.display_name}!")
                return
            hours = performed_action[1]
            report_embed.add_field(name=f"Timeout for {hours} hours",
                                   value=f"**Member**: {self.target_object.mention}"
                                         f"\n**Name**: `{str(self.target_object)}`"
                                         f"\n**Author ID**: `{self.target_object.id}`"
                                         f"\n**Reason**: `{reason}`")
            await interaction.channel.send(embed=report_embed)

        elif self.action_function_name == "kick_user":
            performed_action = await self.kick_user()
            if not performed_action:
                await interaction.edit_original_response(content=
                    f"You cannot perform this action on that user, {interaction.user.display_name}!")
                return
            print(report_embed)
            report_embed.add_field(name=f"Kick",
                                   value=f"**Member**: {self.target_object.mention}"
                                         f"\n**Name**: `{str(self.target_object)}`"
                                         f"\n**Author ID**: `{self.target_object.id}`"
                                         f"\n**Reason**: `{reason}`")
            print(report_embed)
            await interaction.channel.send(embed=report_embed)

        elif self.action_function_name == "toggle_pin":
            try:
                pin_action = await self.toggle_ping()
            except discord.errors.HTTPException:
                await interaction.edit_original_response(content=f"Message seems to have been deleted., {interaction.user.display_name}!")
                return
            if pin_action:
                report_embed.add_field(name=f"Pin",
                                       value=f"**Message**: [Jump To Message]({self.target_object.jump_url})"
                                             f"\n**Reason**: `{reason}`")
            else:
                report_embed.add_field(name=f"Unpin",
                                       value=f"**Message** : [Jump To Message]({self.target_object.jump_url})"
                                             f"\n**Reason**: `{reason}`")

            await interaction.channel.send(embed=report_embed)

        await asyncio.sleep(5)
        await log_channel.send(embed=report_embed)
        await interaction.edit_original_response(content=f"Thank you for your hard work, {interaction.user.display_name}!")

    async def delete_message(self):
        self.target_object: discord.Message
        if self.target_object.author.guild_permissions.administrator:
            return False
        await self.target_object.delete()
        return True

    async def purge_messages(self):
        self.target_object: discord.Message
        try:
            message_count = int(self.children[1].value)
        except ValueError:
            message_count = 1
        member_to_purge = self.target_object.author

        self.target_object: discord.Message
        if member_to_purge.guild_permissions.administrator:
            return False

        count = 1

        def purge_check(message):
            message_date = message.created_at.replace(tzinfo=None)
            time_difference = datetime.utcnow() - message_date
            if time_difference.days >= 14:
                return False
            if message.author == member_to_purge:
                nonlocal count
                count += 1
                return count <= message_count
            else:
                return False

        deleted_messages = await self.target_object.channel.purge(limit=200, check=purge_check,
                                                                  before=self.target_object,
                                                                  reason=self.children[0].value)

        messages_content_list = [message.content for message in deleted_messages]
        messages_content_list.insert(0, self.target_object.content)
        await self.target_object.delete()
        return True, "\n".join(messages_content_list)[0:1000]

    async def timeout_member(self):
        self.target_object: discord.Member
        try:
            hours = int(self.children[1].value)
        except ValueError:
            hours = 0

        if self.target_object.guild_permissions.administrator:
            return False

        hours_to_timeout = timedelta(hours=hours)
        await self.target_object.timeout(hours_to_timeout, reason=self.children[0].value)
        return True, hours

    async def kick_user(self):
        self.target_object: discord.Member
        if self.target_object.guild_permissions.administrator:
            return False

        await self.target_object.create_dm()
        dm_channel = self.target_object.dm_channel
        try:
            await dm_channel.send(f"You got kicked from {self.target_object.guild.name} "
                                  f"for the following reason:\n`{self.children[0].value}`")
        except discord.errors.Forbidden:
            pass
        await self.target_object.kick(reason=self.children[0].value)
        return True

    async def toggle_ping(self):
        self.target_object: discord.Message
        if self.target_object.pinned:
            await self.target_object.unpin(reason=self.children[0].value)
            return False
        else:
            await self.target_object.pin(reason=self.children[0].value)
            return True


class Moderation(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.delete_ctx_menu = discord.app_commands.ContextMenu(name="Delete message",
                                                                callback=self.delete_message)
        self.purge_ctx_menu = discord.app_commands.ContextMenu(name="Purge messages",
                                                               callback=self.purge_messages)
        self.timeout_ctx_menu = discord.app_commands.ContextMenu(name="Timeout user",
                                                                 callback=self.timeout_user)
        self.kick_ctx_menu = discord.app_commands.ContextMenu(name="Kick user",
                                                              callback=self.kick_user)
        self.pin_ctx_menu = discord.app_commands.ContextMenu(name="Toggle pin",
                                                             callback=self.toggle_pin)

    @discord.app_commands.command(
        name="_set_mod_channel",
        description="Set a channel for moderation reports.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(mod_channel="The channel to which moderation reports get sent.")
    @discord.app_commands.default_permissions(administrator=True)
    async def set_mod_channel(self, interaction: discord.Interaction, mod_channel: discord.TextChannel):
        mod_channel_name = mod_channel.name
        await self.bot.write_json_file(interaction.guild, "moderator_channel.json", mod_channel_name)
        await interaction.response.send_message(f"Set moderator channel to {mod_channel.mention}.")

    async def cog_load(self):
        self.bot.tree.add_command(self.delete_ctx_menu)
        self.bot.tree.add_command(self.purge_ctx_menu)
        self.bot.tree.add_command(self.timeout_ctx_menu)
        self.bot.tree.add_command(self.kick_ctx_menu)
        self.bot.tree.add_command(self.pin_ctx_menu)

    @discord.app_commands.default_permissions(administrator=True)
    async def delete_message(self, interaction: discord.Interaction, message: discord.Message):
        moderation_modal = ModerationModal(interaction.command.name, message, self.bot)
        moderation_modal.add_item(discord.ui.TextInput(label='Reason for delete', min_length=4, max_length=400))
        await interaction.response.send_modal(moderation_modal)

    @discord.app_commands.default_permissions(administrator=True)
    async def purge_messages(self, interaction: discord.Interaction, message: discord.Message):
        moderation_modal = ModerationModal(interaction.command.name, message, self.bot)
        moderation_modal.add_item(discord.ui.TextInput(label='Reason for purge', min_length=4, max_length=400,
                                                       style=discord.TextStyle.paragraph,
                                                       placeholder="Beware the bot can only see 200 msgs back from "
                                                                   "the msg you selected and no further than two "
                                                                   "weeks."))
        moderation_modal.add_item(discord.ui.TextInput(label='Message Count', min_length=1, max_length=2,
                                                       default="20"))
        await interaction.response.send_modal(moderation_modal)

    @discord.app_commands.default_permissions(administrator=True)
    async def timeout_user(self, interaction: discord.Interaction, member: discord.Member):
        moderation_modal = ModerationModal(interaction.command.name, member, self.bot)
        moderation_modal.add_item(discord.ui.TextInput(label='Reason for timeout', min_length=4, max_length=400))
        moderation_modal.add_item(discord.ui.TextInput(label='How many hours to timeout', min_length=1, max_length=2,
                                                       default="1"))
        await interaction.response.send_modal(moderation_modal)

    @discord.app_commands.default_permissions(administrator=True)
    async def kick_user(self, interaction: discord.Interaction, member: discord.Member):
        moderation_modal = ModerationModal(interaction.command.name, member, self.bot)
        moderation_modal.add_item(discord.ui.TextInput(label='Reason for kick', min_length=4, max_length=400))
        await interaction.response.send_modal(moderation_modal)

    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_pin(self, interaction: discord.Interaction, message: discord.Message):
        moderation_modal = ModerationModal(interaction.command.name, message, self.bot)
        moderation_modal.add_item(discord.ui.TextInput(label='Reason for toggling pin', min_length=4, max_length=400))
        await interaction.response.send_modal(moderation_modal)


async def setup(bot):
    await bot.add_cog(Moderation(bot))

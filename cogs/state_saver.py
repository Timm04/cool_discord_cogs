"""Save guild roles/channels/permissions and more"""
import asyncio
import io
import os
import pickle
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext import tasks

from . import rank_saver


async def snapshot_autocomplete(interaction: discord.Interaction, current_input: str):
    possible_choices = []
    folder_path = f"snapshots/"
    snapshot_list = os.listdir(folder_path)
    for snapshot in snapshot_list:
        full_path = folder_path + snapshot
        choice = discord.app_commands.Choice(name=snapshot, value=full_path)
        if current_input in snapshot:
            possible_choices.append(choice)

    return possible_choices[0:25]


async def get_missing_bot_list(guild, guild_snapshot):
    missing_bots = []
    for bot_role in guild_snapshot.bot_roles:
        bot_member = guild.get_member(bot_role.bot_id)
        if not bot_member:
            missing_bots.append(f"`{bot_role.name}`")

    return missing_bots


async def save_roles(guild, guild_snapshot):
    for role in guild.roles:
        if role.is_bot_managed():
            guild_snapshot.add_bot_role(role.name, role.hoist, role.position, role.colour, role.permissions,
                                        role.members[0].id)
        elif role.is_premium_subscriber():
            if role.display_icon:
                role_icon = await role.display_icon.read()
                guild_snapshot.add_premium_role(role.name, role.hoist, role.mentionable, role.position, role.colour,
                                                role.permissions, role_icon)
            else:
                guild_snapshot.add_premium_role(role.name, role.hoist, role.mentionable, role.position, role.colour,
                                                role.permissions)
        elif role.is_default():
            guild_snapshot.add_default_role(role.mentionable, role.permissions)

        elif role.display_icon:
            role_icon = await role.display_icon.read()
            guild_snapshot.add_user_role(role.name, role.hoist, role.mentionable, role.position, role.colour,
                                         role.permissions, role_icon)
        else:
            guild_snapshot.add_user_role(role.name, role.hoist, role.mentionable, role.position, role.colour,
                                         role.permissions)

    return guild_snapshot


async def save_channels(guild, guild_snapshot):
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            if not channel.category:
                text_channel_snapshot = SnapshotTextChannel(channel.name, channel.topic, channel.nsfw,
                                                            channel.position,
                                                            channel.permissions_synced,
                                                            channel.default_auto_archive_duration)
            else:
                text_channel_snapshot = SnapshotTextChannel(channel.name, channel.topic, channel.nsfw,
                                                            channel.position,
                                                            channel.permissions_synced,
                                                            channel.default_auto_archive_duration,
                                                            channel.category.name)
            for role in channel.overwrites:
                if not isinstance(role, discord.Role):
                    continue
                overwrite = channel.overwrites[role]
                text_channel_snapshot.add_overwrite(role.name, overwrite)
            guild_snapshot.add_text_channel(text_channel_snapshot)

        elif isinstance(channel, discord.VoiceChannel):
            if not channel.category:
                voice_channel_snapshot = SnapshotVoiceChannel(channel.name, channel.nsfw, channel.position,
                                                              channel.permissions_synced)
            else:
                voice_channel_snapshot = SnapshotVoiceChannel(channel.name, channel.nsfw, channel.position,
                                                              channel.permissions_synced, channel.category.name)
            for role in channel.overwrites:
                if not isinstance(role, discord.Role):
                    continue
                overwrite = channel.overwrites[role]
                voice_channel_snapshot.add_overwrite(role.name, overwrite)
            guild_snapshot.add_voice_channel(voice_channel_snapshot)

        elif isinstance(channel, discord.CategoryChannel):
            category_snapshot = SnapshotCategoryChannel(channel.name, channel.nsfw, channel.position)
            for role in channel.overwrites:
                if not isinstance(role, discord.Role):
                    continue
                overwrite = channel.overwrites[role]
                category_snapshot.add_overwrite(role.name, overwrite)
            guild_snapshot.add_category(category_snapshot)

    return guild_snapshot


async def save_threads(guild, guild_snapshot):
    for thread in guild.threads:
        if isinstance(thread.parent, discord.TextChannel):
            thread_snapshot = SnapshotThread(name=thread.name,
                                             auto_archive_duration=thread.auto_archive_duration,
                                             channel_name=thread.parent.name)
            guild_snapshot.add_thread(thread_snapshot)

    return guild_snapshot


async def save_pins(guild, guild_snapshot):
    for channel in guild.text_channels:
        await asyncio.sleep(1)
        pins = await channel.pins()
        for pin in pins:
            if pin.author.bot:
                continue
            file_list = [(await attachment.read(), attachment.filename) for attachment in pin.attachments if
                         attachment.size < 8000000]
            snapshot_pin = PinnedMessage(author=str(pin.author), date=str(pin.created_at)[:10],
                                         channel_name=pin.channel.name, content=pin.content,
                                         files=file_list)

            guild_snapshot.add_pin(snapshot_pin)

    return guild_snapshot


async def create_snapshot(guild: discord.Guild):
    guild_snapshot = SnapshotGuild()
    guild_snapshot = await save_roles(guild, guild_snapshot)
    guild_snapshot = await save_channels(guild, guild_snapshot)
    guild_snapshot = await save_threads(guild, guild_snapshot)
    guild_snapshot = await save_pins(guild, guild_snapshot)

    date_string = str(datetime.utcnow())[:10]
    guild_name = guild.name.lower().replace(" ", "_")
    with open(f"snapshots/{date_string}_{guild_name}_snapshot", "wb") as file:
        pickle.dump(guild_snapshot, file)

    return guild_snapshot


class StateSaver(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.snapshot_loop.start()

    async def cog_unload(self):
        self.snapshot_loop.cancel()

    @discord.app_commands.command(
        name="_save_snapshot",
        description="Save the current server state to a file which can be restored later.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def save_snapshot(self, interaction: discord.Interaction):
        await interaction.response.defer()

        await create_snapshot(interaction.guild)

        await interaction.edit_original_response(content="Saved snapshot!")

    @discord.app_commands.command(
        name="_load_snapshot",
        description="Load a previously saved snapshot.")
    @discord.app_commands.guild_only()
    @discord.app_commands.autocomplete(file_path=snapshot_autocomplete)
    @discord.app_commands.default_permissions(administrator=True)
    async def load_snapshot(self, interaction: discord.Interaction, file_path: str):
        with open(file_path, "rb") as file:
            guild_snapshot = pickle.load(file)

        button_view = discord.ui.View()
        button_view.add_item(ConfirmDeletionButton(self.bot, guild_snapshot))

        channel_mentions = " | ".join([channel.mention for channel in interaction.guild.channels])
        role_mentions = " | ".join([role.mention for role in interaction.guild.roles if not role.is_bot_managed()])
        to_delete_embed = discord.Embed(title="Roles and Channels to delete:",
                                        description=f"**Channels**: {channel_mentions}\n\n"
                                                    f"**Roles** {role_mentions}")

        missing_bots = await get_missing_bot_list(interaction.guild, guild_snapshot)

        await interaction.response.send_message(f"Are you sure you want to load the snapshot?\n"
                                                f"The following bots seem to be missing and permissions will not be "
                                                f"restored for them:"
                                                f"{', '.join(missing_bots)}\n"
                                                f"**THIS WILL DELETE ALL ROLES AND CHANNELS.**", embed=to_delete_embed,
                                                view=button_view, ephemeral=True)

    @discord.app_commands.command(
        name="_restore_roles",
        description="Manually start the role restorer for the current members.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def restore_roles(self, interaction: discord.Interaction, guild_id: str):
        await interaction.response.send_message("Restoring roles.")
        guild_id = int(guild_id)
        user_roles_dictionary = await rank_saver.fetch_rank_data(guild_id)
        for user_id in user_roles_dictionary:
            member = interaction.guild.get_member(int(user_id))
            if not member:
                continue
            role_names = user_roles_dictionary.get(str(member.id))
            await asyncio.sleep(5)
            roles_to_restore = [discord.utils.get(member.guild.roles, name=role_name) for role_name in role_names]
            roles_to_restore = [role for role in roles_to_restore if role]
            roles_to_remove = [role for role in member.roles if
                               role.name != "@everyone" and role.name != "Server Booster"]
            await member.remove_roles(*roles_to_remove)
            await member.add_roles(*roles_to_restore)
            await interaction.channel.send(
                f"Giving roles {', '.join([role.name for role in roles_to_restore])} to {member}.\n"
                f"\tRemoving roles {', '.join([role.name for role in roles_to_remove])}")

        await interaction.channel.send("Done.")

    @tasks.loop(hours=24)
    async def snapshot_loop(self):
        await asyncio.sleep(6000)
        for guild in self.bot.guilds:
            print(f"Creating snapshot for {guild.name}.")
            await create_snapshot(guild)

        # TODO: Add function to remove old snapshots


async def setup(bot):
    await bot.add_cog(StateSaver(bot))


class SnapshotGuild:
    def __init__(self):
        self.user_roles = []
        self.bot_roles = []
        self.default_role = None
        self.premium_role = None

        self.categories = []
        self.text_channels = []
        self.voice_channels = []
        self.threads = []

        self.pinned_messages = []

    def add_user_role(self, name, hoist, mentionable, role_position, colour, permissions, display_icon=None):
        user_role = SnapshotUserRole(name, hoist, mentionable, role_position, colour, permissions, display_icon)
        self.user_roles.append(user_role)

    def add_default_role(self, mentionable, permissions):
        default_role = SnapshotDefaultRole(mentionable, permissions)
        self.default_role = default_role

    def add_bot_role(self, name, hoist, role_position, colour, permissions, bot_id):
        bot_role = SnapshotBotRole(name, hoist, role_position, colour, permissions, bot_id)
        self.bot_roles.append(bot_role)

    def add_premium_role(self, name, hoist, mentionable, role_position, colour, permissions, display_icon=None):
        premium_role = SnapshotPremiumRole(name, hoist, mentionable, role_position, colour, permissions, display_icon)
        self.premium_role = premium_role

    def add_category(self, category):
        self.categories.append(category)

    def add_text_channel(self, text_channel):
        self.text_channels.append(text_channel)

    def add_voice_channel(self, voice_channel):
        self.voice_channels.append(voice_channel)

    def add_thread(self, thread):
        self.threads.append(thread)

    def add_pin(self, pin):
        self.pinned_messages.append(pin)


class SnapshotDefaultRole:
    def __init__(self, mentionable: bool, permissions: discord.Permissions):
        self.mentionable = mentionable
        self.permissions = permissions


class SnapshotUserRole:
    def __init__(self, name: str, hoist: bool, mentionable: bool, role_position: int, colour: discord.Colour,
                 permissions: discord.Permissions, display_icon=None):
        self.name = name
        self.hoist = hoist
        self.mentionable = mentionable
        self.colour = colour
        self.permissions = permissions
        self.position = role_position
        self.display_icon = None
        if display_icon:
            self.display_icon = display_icon


class SnapshotPremiumRole:
    def __init__(self, name: str, hoist: bool, mentionable: bool, role_position: int, colour: discord.Colour,
                 permissions: discord.Permissions, display_icon=None):
        self.name = name
        self.hoist = hoist
        self.mentionable = mentionable
        self.colour = colour
        self.permissions = permissions
        self.position = role_position
        self.display_icon = None
        if display_icon:
            self.display_icon = display_icon


class SnapshotBotRole:
    def __init__(self, name: str, hoist: bool, role_position: int, colour: discord.Colour,
                 permissions: discord.Permissions, bot_id: int):
        self.name = name
        self.hoist = hoist
        self.role_position = role_position
        self.colour = colour
        self.permissions = permissions
        self.bot_id = bot_id


class SnapshotPermissionOverwrite:
    def __init__(self, role_name, overwrite):
        self.role_name = role_name
        self.overwrite = overwrite


class SnapshotCategoryChannel:
    def __init__(self, name, nsfw, position):
        self.name = name
        self.nsfw = nsfw
        self.position = position
        self.overwrites = []

    def add_overwrite(self, role_name, overwrite):
        role_overwrite = SnapshotPermissionOverwrite(role_name, overwrite)
        self.overwrites.append(role_overwrite)


class SnapshotTextChannel:
    def __init__(self, name, topic, nsfw, position, permissions_synced, default_auto_archive_duration,
                 category_name=None):
        self.name = name
        self.topic = topic
        self.nsfw = nsfw
        self.position = position
        self.category_name = category_name
        self.permissions_synced = permissions_synced
        self.default_auto_archive_duration = default_auto_archive_duration
        self.overwrites = []

    def add_overwrite(self, role_name, overwrite):
        role_overwrite = SnapshotPermissionOverwrite(role_name, overwrite)
        self.overwrites.append(role_overwrite)


class SnapshotThread:
    def __init__(self, name, auto_archive_duration, channel_name):
        self.name = name
        self.auto_archive_duration = auto_archive_duration
        self.channel_name = channel_name


class SnapshotVoiceChannel:
    def __init__(self, name, nsfw, position, permissions_synced, category_name=None):
        self.name = name
        self.nsfw = nsfw
        self.position = position
        self.category_name = category_name
        self.permissions_synced = permissions_synced
        self.overwrites = []

    def add_overwrite(self, role_name, overwrite):
        role_overwrite = SnapshotPermissionOverwrite(role_name, overwrite)
        self.overwrites.append(role_overwrite)


class PinnedMessage:
    def __init__(self, author, date, channel_name, content=None, files=None):
        self.author = author
        self.date = date
        self.channel_name = channel_name
        self.content = content
        self.files = files


async def verify_if_top_role(guild, bot):
    top_role = None
    for role in guild.roles:
        if not top_role:
            top_role = role
        if top_role < role:
            top_role = role

    bot_member = guild.get_member(bot.user.id)
    if top_role not in bot_member.roles:
        return False
    else:
        for role in bot_member.roles:
            if role.is_bot_managed():
                return role


async def delete_all_channels(guild: discord.Guild):
    for channel in guild.channels:
        await asyncio.sleep(1)
        print(f"Deleting channel: {channel.name}")
        await channel.delete()


async def delete_roles(guild: discord.Guild):
    for role in guild.roles:
        try:
            await asyncio.sleep(1)
            print(f"Deleting role: {role.name}")
            await role.delete(reason="Restoration.")
        except discord.errors.HTTPException:
            print(f"Failed to delete role: {role.name}")


class ConfirmDeletionButton(discord.ui.Button):
    def __init__(self, bot, guild_snapshot):
        super().__init__(label="I am sure.", style=discord.ButtonStyle.danger)
        self.bot = bot
        self.guild_snapshot: SnapshotGuild = guild_snapshot
        self.role_positions = dict()

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Deleting guild...")

        bot_role = await self.verify_permissions(interaction)
        if not bot_role:
            return

        await delete_roles(interaction.guild)
        await self.edit_default_role(interaction.guild)
        await self.edit_premium_role(interaction.guild)
        await self.create_roles_and_positions(interaction.guild, bot_role)
        await delete_all_channels(interaction.guild)
        await self.create_categories(interaction.guild)
        await self.create_text_channels(interaction.guild)
        await self.create_voice_channels(interaction.guild)
        await self.create_threads(interaction.guild)
        await self.create_pins(interaction.guild)

        await interaction.guild.text_channels[0].send("Finished creating guild.")

    async def verify_permissions(self, interaction):
        bot_role = await verify_if_top_role(interaction.guild, self.bot)
        if not bot_role:
            await interaction.edit_original_response(content="Bot does not have top role.\n"
                                                             "Please ensure that it does before loading a snapshot.")

            return False

        if not bot_role.permissions.administrator:
            await interaction.edit_original_response(content="Bot does not have administrator privileges.")
            return False

        return bot_role

    async def create_categories(self, guild: discord.Guild):
        for category_data in self.guild_snapshot.categories:
            overwrites = dict()
            for overwrite in category_data.overwrites:
                role = discord.utils.get(guild.roles, name=overwrite.role_name)
                if role:
                    overwrites[role] = overwrite.overwrite
            await asyncio.sleep(1)
            print(f"Creating category: {category_data.name}")
            category_channel = await guild.create_category_channel(name=category_data.name,
                                                                   position=category_data.position,
                                                                   overwrites=overwrites)
            await category_channel.edit(nsfw=category_data.nsfw)

    async def create_text_channels(self, guild: discord.Guild):
        for text_channel_data in self.guild_snapshot.text_channels:
            overwrites = dict()
            for overwrite in text_channel_data.overwrites:
                role = discord.utils.get(guild.roles, name=overwrite.role_name)
                if role:
                    overwrites[role] = overwrite.overwrite
            await asyncio.sleep(1)
            print(f"Creating text-channel: {text_channel_data.name}")
            if text_channel_data.category_name:
                category = discord.utils.get(guild.categories, name=text_channel_data.category_name)
            else:
                category = None

            text_channel = await guild.create_text_channel(name=text_channel_data.name, category=category,
                                                           position=text_channel_data.position,
                                                           topic=text_channel_data.topic,
                                                           nsfw=text_channel_data.nsfw,
                                                           default_auto_archive_duration=text_channel_data.default_auto_archive_duration,
                                                           overwrites=overwrites)
            await text_channel.edit(sync_permissions=text_channel_data.permissions_synced)

    async def create_voice_channels(self, guild: discord.Guild):
        for voice_channel_data in self.guild_snapshot.voice_channels:
            overwrites = dict()
            for overwrite in voice_channel_data.overwrites:
                role = discord.utils.get(guild.roles, name=overwrite.role_name)
                if role:
                    overwrites[role] = overwrite.overwrite
            await asyncio.sleep(1)
            print(f"Creating voice channel: {voice_channel_data.name}")
            if voice_channel_data.category_name:
                category = discord.utils.get(guild.categories, name=voice_channel_data.category_name)
            else:
                category = None
            voice_channel = await guild.create_voice_channel(name=voice_channel_data.name,
                                                             position=voice_channel_data.position,
                                                             category=category, overwrites=overwrites)

            await voice_channel.edit(nsfw=voice_channel_data.nsfw,
                                     sync_permissions=voice_channel_data.permissions_synced)

    async def edit_default_role(self, guild: discord.Guild):
        print("Editing default role...")
        await guild.default_role.edit(permissions=self.guild_snapshot.default_role.permissions,
                                      mentionable=self.guild_snapshot.default_role.mentionable)

    async def edit_premium_role(self, guild: discord.Guild):
        print("Looking for premium role...")
        if guild.premium_subscriber_role:
            print("Found. Editing premium role...")
            role = self.guild_snapshot.premium_role
            await guild.premium_subscriber_role.edit(name=role.name, permissions=role.permissions,
                                                     colour=role.colour, hoist=role.hoist,
                                                     display_icon=role.display_icon,
                                                     mentionable=role.mentionable)

            self.role_positions[guild.premium_subscriber_role] = role.position

    async def edit_bot_roles(self, guild: discord.Guild):
        for bot_role_data in self.guild_snapshot.bot_roles:
            bot_member = guild.get_member(bot_role_data.bot_id)
            if not bot_member:
                continue
            bot_role = discord.utils.get(guild.roles, name=bot_role_data.name)
            await bot_role.edit(name=bot_role_data.name, hoist=bot_role.hoist,
                                colour=bot_role_data.colour, permissions=bot_role_data.permissions)

            self.role_positions[bot_role] = bot_role_data.position

    async def create_roles_and_positions(self, guild, bot_role):
        for role in self.guild_snapshot.user_roles:
            await asyncio.sleep(1)
            print(f"Creating role: {role.name}")
            new_role = await guild.create_role(name=role.name, permissions=role.permissions,
                                               colour=role.colour, hoist=role.hoist,
                                               mentionable=role.mentionable)

            self.role_positions[new_role] = role.position

        top_position = max(list(self.role_positions.values())) + 1
        self.role_positions[bot_role] = top_position
        await guild.edit_role_positions(self.role_positions)

    async def create_threads(self, guild):
        for thread_data in self.guild_snapshot.threads:
            parent_channel = discord.utils.get(guild.channels, name=thread_data.channel_name)
            await asyncio.sleep(1)
            print(f"Creating thread: {thread_data.name}")
            await parent_channel.create_thread(name=thread_data.name, type=discord.ChannelType.public_thread,
                                               auto_archive_duration=thread_data.auto_archive_duration)

    async def create_pins(self, guild):
        for pin_data in self.guild_snapshot.pinned_messages:
            pin_data: PinnedMessage
            channel = discord.utils.get(guild.channels, name=pin_data.channel_name)
            channel: discord.TextChannel
            pin_embed = discord.Embed(title=f"Pinned message by {pin_data.author} on {pin_data.date}",
                                      description=pin_data.content)

            file_list = []
            for file_data, file_name in pin_data.files:
                file = io.BytesIO(file_data)
                file_list.append(discord.File(file, filename=file_name))

            await asyncio.sleep(2)
            pin_message = await channel.send(embed=pin_embed, files=file_list)
            await asyncio.sleep(1)
            await pin_message.pin()

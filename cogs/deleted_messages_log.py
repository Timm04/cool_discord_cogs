"""Save deleted messages."""
import asyncio
from datetime import datetime
from datetime import timedelta
import discord
from discord.ext import commands
from discord.ext import tasks


class DeletedMessagesLog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.deleter.start()

    @discord.app_commands.command(
        name="_setup_logger",
        description="Setup the deleted messages logger.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(active="Whether deleted messages should be logged or not.",
                                   channel="In what channel deleted messages should be logged.",
                                   clear_after_hours="After how many hours the contents of the channel should be "
                                                     "deleted.")
    @discord.app_commands.default_permissions(administrator=True)
    async def setup_logger(self, interaction: discord.Interaction, active: bool, channel: discord.TextChannel,
                           clear_after_hours: int):
        settings = (active, channel.name, clear_after_hours)
        await self.bot.write_json_file(interaction.guild, "deleted_messages_log_settings.json", settings)
        await interaction.response.send_message("Updated settings.")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.id == self.bot.user.id:
            return
        try:
            active, channel_name, clear_after_hours = await self.bot.open_json_file(
                message.guild, "deleted_messages_log_settings.json", list())
        except ValueError:
            return  # Logger is not set up yet
        if not active:
            return
        channel = discord.utils.get(message.guild.channels, name=channel_name)
        if not channel:
            return  # Channel name was changed
        if channel == message.channel:
            return

        current_time = datetime.utcnow()
        current_time_string = current_time.strftime("%b-%d %H:%M")

        content_embed = discord.Embed(title=f"Deleted message by {message.author} in #{message.channel.name} "
                                            f"at {current_time_string} UTC.")
        content_embed.set_thumbnail(url=message.author.display_avatar.url)
        if message.content:
            content_embed.add_field(name="Message content:", value=message.content[0:1000])

        information_string = f"Name: {message.author}" \
                             f"\nMention: {message.author.mention}" \
                             f"\nID: {message.author.id}"

        image_files = await self.retrieve_attachments(message)
        if image_files:
            information_string += f"\nContained **{len(image_files)}** attachments:"

        await channel.send(content=information_string,
                           files=image_files,
                           embed=content_embed,
                           allowed_mentions=discord.AllowedMentions.none())

    async def retrieve_attachments(self, message: discord.Message):
        if message.attachments:
            files = list()
            for attachment in message.attachments:
                try:
                    image_file = await attachment.to_file(use_cached=True)
                    files.append(image_file)
                except discord.errors.HTTPException:
                    return None
            return files
        else:
            return None

    @tasks.loop(minutes=10.0)
    async def deleter(self):
        await asyncio.sleep(120)
        for guild in self.bot.guilds:
            try:
                active, channel_name, clear_after_hours = await self.bot.open_json_file(
                    guild, "deleted_messages_log_settings.json", list())
            except ValueError:
                return  # Logger is not set up yet
            if not active:
                return
            channel = discord.utils.get(guild.channels, name=channel_name)
            if not channel:
                return  # Channel name was changed
            delete_limit = timedelta(hours=24)
            await channel.purge(before=datetime.utcnow() - delete_limit)


async def setup(bot):
    await bot.add_cog(DeletedMessagesLog(bot))

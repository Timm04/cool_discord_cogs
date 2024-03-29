"""Send posts with a lot of reactions to seperate channel"""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks

from . import data_management

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "notable_posts_settings"
SETTINGS_COLUMNS = ("guild_id", "notable_posts_settings")


async def fetch_notable_posts_settings(guild_id: int):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id,
                                             default_type=list)


async def write_notable_posts_settings(guild_id: int, settings: tuple):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], settings,
                                       guild_id=guild_id)


#########################################

embed_post_lock = asyncio.Lock()


async def edit_notable_post(embed_message: discord.Message, reaction_message: discord.Message):
    reaction_embed = embed_message.embeds[0]
    reaction_embed.remove_field(-1)

    reaction_string = [f"{reaction.count} {reaction.emoji}" for reaction in reaction_message.reactions]
    reaction_string = ", ".join(reaction_string)
    reaction_embed.add_field(name="Reactions:", value=reaction_string, inline=False)
    await asyncio.sleep(10)
    await embed_message.edit(embed=reaction_embed)


async def highest_reaction_count(reaction_message: discord.Message):
    highest_reaction_count = max([reaction.count for reaction in reaction_message.reactions])
    return highest_reaction_count


class NotablePosts(commands.Cog):

    def __init__(self, bot):
        self.notable_post_info = None
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)

        self.notable_post_info = dict()
        for guild in self.bot.guilds:
            self.notable_post_info[guild.id] = dict()

        self.update_notable_posts.start()

    async def cog_unload(self):
        self.update_notable_posts.cancel()

    @discord.app_commands.command(
        name="_activate_notable_posts",
        description="Activate reposting of notable posts in an embed.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def activate_notable_posts(self, interaction: discord.Interaction, active: bool, channel: discord.TextChannel,
                                     reaction_count: int):
        notable_posts_settings = active, channel.name, reaction_count
        self.notable_post_info[interaction.guild.id] = dict()
        await write_notable_posts_settings(interaction.guild_id, notable_posts_settings)
        await interaction.response.send_message(f"Updated notable posts settings.\n"
                                                f"Active: `{active}`\n"
                                                f"Channel: `{channel.name}`\n"
                                                f"Reaction count: `{reaction_count}`")

    async def entry_exists(self, reaction_message):
        guild_notable_posts = self.notable_post_info[reaction_message.guild.id]
        if reaction_message.id in guild_notable_posts:
            return True
        else:
            return False

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, member: discord.Member):
        if await self.entry_exists(reaction.message):
            return
        if not member.guild:
            return
        notable_posts_settings = await fetch_notable_posts_settings(member.guild.id)
        if not notable_posts_settings:
            return
        active, channel_name, needed_reaction_count = notable_posts_settings
        if not active:
            return
        notable_posts_channel = discord.utils.get(member.guild.channels, name=channel_name)
        if not notable_posts_channel:
            raise ValueError("Notable posts channel not found.")
        message_reaction_count = await highest_reaction_count(reaction.message)
        if message_reaction_count >= needed_reaction_count:
            await self.create_notable_post(notable_posts_channel, reaction.message, message_reaction_count)

    async def create_notable_post(self, notable_posts_channel: discord.TextChannel, reaction_message: discord.Message,
                                  reaction_count: int):

        async with embed_post_lock:
            if await self.entry_exists(reaction_message):
                return
            description = f"[Jump To Message]({reaction_message.jump_url})"
            if reaction_message.content:
                description += f"\n\n**Content:**\n{reaction_message.content}"

            reaction_embed = discord.Embed(description=description)
            reaction_embed.set_author(name=str(reaction_message.author),
                                      icon_url=str(reaction_message.author.avatar.url))
            if reaction_message.attachments:
                reaction_embed.add_field(name="Media:", value="The post contained the following image:", inline=False)
                reaction_embed.set_image(url=reaction_message.attachments[0].url)
            reaction_string = [f"{reaction.count} {reaction.emoji}" for reaction in reaction_message.reactions]
            reaction_string = ", ".join(reaction_string)
            reaction_embed.add_field(name="Reactions:", value=reaction_string, inline=False)
            embed_message = await notable_posts_channel.send(embed=reaction_embed)
            guild_notable_posts = self.notable_post_info[reaction_message.guild.id]
            guild_notable_posts[reaction_message.id] = (embed_message, reaction_message, reaction_count)
            self.notable_post_info[reaction_message.guild.id] = guild_notable_posts

    @tasks.loop(minutes=5)
    async def update_notable_posts(self):
        await asyncio.sleep(60)
        for guild in self.bot.guilds:
            guild_notable_posts = self.notable_post_info[guild.id]
            for embed_message, reaction_message, old_reaction_count in list(guild_notable_posts.values()):
                await asyncio.sleep(5)
                reaction_message = await reaction_message.channel.fetch_message(reaction_message.id)
                current_reaction_count = await highest_reaction_count(reaction_message)
                if current_reaction_count != old_reaction_count:
                    await edit_notable_post(embed_message, reaction_message)


async def setup(bot):
    await bot.add_cog(NotablePosts(bot))

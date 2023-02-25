"""Cog providing various utility functions such as syncing commands and dynamically reloading cogs."""
import asyncio
import pkgutil

import discord
from discord.ext import commands

OWNER_ID = int(pkgutil.get_data(__package__, "config/owner_id.txt").decode())


def check_if_bot_owner(interaction: discord.Interaction):
    return interaction.user.id == OWNER_ID


class Config(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self.thread_joiner())

    # Join Threads
    async def thread_joiner(self):
        for guild in self.bot.guilds:
            guild: discord.Guild
            for thread in guild.threads:
                if thread.me:
                    continue
                else:
                    await asyncio.sleep(5)
                    print(f"Joining thread {thread.name}")
                    await thread.join()

    @commands.Cog.listener(name="on_thread_create")
    async def join_threads(self, thread: discord.Thread):
        await thread.join()

    ##############################################

    @commands.command()
    @commands.is_owner()
    async def sync_guild(self, ctx: discord.ext.commands.Context):
        """Sync commands to current guild. Good for testing."""
        self.bot.tree.copy_global_to(guild=discord.Object(id=ctx.guild.id))
        await self.bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
        await ctx.send(f"Synced commands to guild with id {ctx.guild.id}.")

    @commands.command()
    @commands.is_owner()
    async def clear_global_commands(self, ctx):
        """Clear all global commands."""
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()
        await ctx.send("Cleared global commands.")

    ##############################################

    # Dynamically reload cogs
    @discord.app_commands.command(
        name="_reload_cog",
        description="Reload a cog without restarting the bot.")
    @discord.app_commands.default_permissions(administrator=True)
    @discord.app_commands.check(check_if_bot_owner)
    async def reload_cog(self, interaction: discord.Interaction):
        my_view = discord.ui.View(timeout=1800)
        for cog_name in [extension for extension in self.bot.extensions]:
            cog_button = ReloadButtons(self.bot, label=cog_name)
            my_view.add_item(cog_button)
        await interaction.response.send_message(f"Please select the cog you would like to reload.",
                                                view=my_view,
                                                ephemeral=True)


class ReloadButtons(discord.ui.Button):

    def __init__(self, bot: commands.Bot, label):
        super().__init__(label=label)
        self.bot = bot

    async def callback(self, interaction):
        cog_to_reload = self.label
        await self.bot.reload_extension(cog_to_reload)
        await interaction.response.send_message(f"Reloaded the following cog: {cog_to_reload}")
        print(f"Reloaded the following cog: {cog_to_reload}")
        await asyncio.sleep(10)
        await interaction.delete_original_response()


async def setup(bot):
    await bot.add_cog(Config(bot))

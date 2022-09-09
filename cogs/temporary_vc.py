"""Cog Description"""
import discord
from discord.ext import commands
from discord.ext import tasks


class TemporaryVC(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.clear_vcs.start()

    async def cog_unload(self):
        self.clear_vcs.cancel()

    @discord.app_commands.command(
        name="create_vc",
        description="Create a temporary voice channel. Need to be inside a VC to use this command!")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel_name="The name of the temporary voice channel.")
    @discord.app_commands.default_permissions(send_messages=True)
    async def create_vc(self, interaction: discord.Interaction, channel_name: str):
        if interaction.user.voice:
            bottom_vc = interaction.guild.voice_channels[-1]
            custom_vc = await interaction.guild.create_voice_channel(name=channel_name,
                                                         reason="User command",
                                                         category=bottom_vc.category,
                                                         position=bottom_vc.position + 1)

            await interaction.user.move_to(custom_vc, reason="Channel creation.")
            custom_vc_list = await self.bot.open_json_file(interaction.guild, "custom_vcs.json", list())
            custom_vc_list.append(custom_vc.id)
            await self.bot.write_json_file(interaction.guild, "custom_vcs.json", custom_vc_list)
            await interaction.response.send_message(f"Created a temporary voice channel called `{channel_name}`.")
        else:
            await interaction.response.send_message("You need to be in a voice channel to use this command.",
                                                    ephemeral=True)
            return

    @tasks.loop(minutes=5)
    async def clear_vcs(self):
        for guild in self.bot.guilds:
            guild: discord.Guild
            custom_vc_list = await self.bot.open_json_file(guild, "custom_vcs.json", list())
            for custom_vc_id in custom_vc_list:
                custom_vc = guild.get_channel(custom_vc_id)
                if not custom_vc:
                    custom_vc_list.remove(custom_vc_id)
                    await self.bot.write_json_file(guild, "custom_vcs.json", custom_vc_list)
                if not custom_vc.members:
                    await custom_vc.delete(reason="Empty custom channel.")
                    custom_vc_list.remove(custom_vc_id)
                    await self.bot.write_json_file(guild, "custom_vcs.json", custom_vc_list)

async def setup(bot):
    await bot.add_cog(TemporaryVC(bot))

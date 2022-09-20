"""Backup role data"""
import asyncio
import discord
from discord.ext import commands
from discord.ext import tasks

class RankSaver(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.rank_saver.start()

    @tasks.loop(minutes=10.0)
    async def rank_saver(self):
        await asyncio.sleep(60)
        for guild in self.bot.guilds:
            to_save = await self.bot.open_json_file(guild, "rank_saver_status.json", False)
            if to_save:
                user_roles_dictionary = await self.bot.open_json_file(guild, "rank_saver.json", dict())
                all_members = [member for member in guild.members if member.bot is False]
                roles_to_not_save = ["@everyone", "Server Booster"]
                for member in all_members:
                    member_roles = [role.name for role in member.roles if role.name not in roles_to_not_save]
                    user_roles_dictionary[str(member.id)] = member_roles

                await self.bot.write_json_file(guild, "rank_saver.json", user_roles_dictionary)

    @discord.app_commands.command(
        name="_toggle_rank_saver",
        description="Enable/Disable rank saving.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_rank_saver(self, interaction: discord.Interaction):
        to_save = await self.bot.open_json_file(interaction.guild, "rank_saver_status.json", False)
        if to_save:
            to_save = False
            await self.bot.write_json_file(interaction.guild, "rank_saver_status.json", to_save)
            await interaction.response.send_message("Disabled rank saver.")
        else:
            to_save = True
            await self.bot.write_json_file(interaction.guild, "rank_saver_status.json", to_save)
            await interaction.response.send_message("Enabled rank saver.")

    @discord.app_commands.command(
        name="_toggle_rank_restorer",
        description="Enable/Disable rank restoration.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def toggle_rank_restorer(self, interaction: discord.Interaction):
        to_restore = await self.bot.open_json_file(interaction.guild, "rank_restoration_status.json", False)
        if to_restore:
            to_restore = False
            await self.bot.write_json_file(interaction.guild, "rank_restoration_status.json", to_restore)
            await interaction.response.send_message("Disabled rank restoration.")
        else:
            to_restore = True
            await self.bot.write_json_file(interaction.guild, "rank_restoration_status.json", to_restore)
            await interaction.response.send_message("Enabled rank restoration.")

    @discord.app_commands.command(
        name="_select_restore_announce_channel",
        description="Select the chanel in which the rank restoration message should be sent. Again to deactivated.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(channel="Channel in which the role restoration message should be sent.")
    @discord.app_commands.default_permissions(administrator=True)
    async def select_restore_announce_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        to_restore_channel = await self.bot.open_json_file(interaction.guild, "rank_restoration_channel.json", str())
        if to_restore_channel == channel.name:
            to_restore_channel = str()
            await self.bot.write_json_file(interaction.guild, "rank_restoration_channel.json", to_restore_channel)
            await interaction.response.send_message("Deactivated the rank restoration announcement.")
        else:
            to_restore_channel = channel.name
            await self.bot.write_json_file(interaction.guild, "rank_restoration_channel.json", to_restore_channel)
            await interaction.response.send_message(f"Set the rank restoration announcement channel to {channel.mention}.")

    @commands.Cog.listener(name="on_member_join")
    async def rank_restorer(self, member: discord.Member):
        to_restore = await self.bot.open_json_file(member.guild, "rank_restoration_status.json", False)
        if not to_restore:
            return
        user_roles_dictionary = await self.bot.open_json_file(member.guild, "rank_saver.json", dict())
        role_names = user_roles_dictionary.get(str(member.id))
        if role_names:
            await asyncio.sleep(8)
            roles_to_restore = [discord.utils.get(member.guild.roles, name=role_name) for role_name in role_names]
            roles_to_restore = [role for role in roles_to_restore if role]
            roles_to_remove = [role for role in member.roles if role.name != "@everyone"]
            await member.remove_roles(*roles_to_remove)
            await member.add_roles(*roles_to_restore)
        else:
            return
        to_restore_channel_name = await self.bot.open_json_file(member.guild, "rank_restoration_channel.json", str())
        if to_restore_channel_name:
            to_restore_channel = discord.utils.get(member.guild.channels, name=to_restore_channel_name)
            await to_restore_channel.send(f"Restored **{', '.join([role.name for role in roles_to_restore])}** for"
                                          f"{member.mention}.")

async def setup(bot):
    await bot.add_cog(RankSaver(bot))

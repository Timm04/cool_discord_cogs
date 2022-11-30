"""Some key functions required for other cogs."""
import asyncio

import discord
from discord.ext import commands
from discord.ext import tasks
import os


class Config(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def create_config_folders(self):
        for guild in self.bot.guilds:
            if os.path.isdir(f"data/{guild.id}"):
                continue
            else:
                os.mkdir(f"data/{guild.id}")

    async def cog_load(self):
        await self.create_config_folders()
        loop = asyncio.get_running_loop()
        loop.create_task(self.thread_joiner())

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

    @discord.app_commands.command(
        name="help",
        description="Get an overview of commands.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def help(self, interaction: discord.Interaction):
        command_string = ""
        admin_commands = []
        for command in self.bot.tree.get_commands():
            if isinstance(command, discord.app_commands.Command):
                if command.name.startswith("_"):
                    admin_commands.append(f"\n**/{command.name}**\n{command.description}\n")
                else:
                    command_string += f"\n**/{command.name}**\n{command.description}\n"

        if interaction.user.guild_permissions.administrator:
            for admin_string in admin_commands:
                command_string += admin_string

        help_embed = discord.Embed(title="Command Overview", description=command_string)

        await interaction.response.send_message(embed=help_embed, ephemeral=True)



    @commands.Cog.listener(name="on_thread_create")
    async def join_threads(self, thread: discord.Thread):
        await thread.join()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def sync(self, ctx: discord.ext.commands.Context):
        if not ctx.guild:
            await ctx.reply("Command can only be used in a guild.")
            return
        self.bot.tree.copy_global_to(guild=discord.Object(id=ctx.guild.id))
        await self.bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
        await ctx.send(f"Synced commands to guild with id {ctx.guild.id}.")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def clear_global_commands(self, ctx):
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()
        await ctx.send("Cleared global commands.")

    @discord.app_commands.command(
        name="_reload_cog",
        description="Reload a cog without restarting the bot.")
    @discord.app_commands.default_permissions(administrator=True)
    async def reload_cog(self, interaction: discord.Interaction):
        my_view = CogSelectView(timeout=1800)
        for cog_name in [extension for extension in self.bot.extensions]:
            cog_button = ReloadButtons(self.bot, label=cog_name)
            my_view.add_item(cog_button)
        await interaction.response.send_message(f"Please select the cog you would like to reload.",
                                                view=my_view,
                                                ephemeral=True)

    @discord.app_commands.command(
        name="_verify_configuration",
        description="Goes through the config files to ensure everything is in order.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def verify_configuration(self, interaction: discord.Interaction):
        settings_embed = discord.Embed(description="Settings:")

        # ---Commands---
        commands_report = []
        global_slash_commands = self.bot.tree.get_commands(type=discord.AppCommandType.chat_input)
        commands_report.append(f"Global slash command count: `{len(global_slash_commands)}` (Max 100)")
        global_context_menus = self.bot.tree.get_commands(type=discord.AppCommandType.message) + \
                               self.bot.tree.get_commands(type=discord.AppCommandType.user)
        commands_report.append(f"Global context menus: `{len(global_context_menus)}` (Max 5)")

        guild_slash_commands = self.bot.tree.get_commands(guild=interaction.guild,
                                                          type=discord.AppCommandType.chat_input)
        commands_report.append(f"Guild slash command count: `{len(guild_slash_commands)}` (Max 100)")
        guild_context_menus = self.bot.tree.get_commands(guild=interaction.guild, type=discord.AppCommandType.message) + \
                              self.bot.tree.get_commands(guild=interaction.guild, type=discord.AppCommandType.user)
        commands_report.append(f"Guild context menus: `{len(guild_context_menus)}` (Max 5)")

        settings_embed.add_field(name="Commmands",
                                 value="\n".join(commands_report),
                                 inline=False)

        # ---Assignable roles---
        addable_roles_data = await self.bot.open_json_file(interaction.guild, "addable_roles.json", list())
        forbidden_roles_list = await self.bot.open_json_file(interaction.guild, "forbidden_roles.json", list())

        assignable_roles_setting_report = []
        for role_name, role_emoji, role_description in addable_roles_data:
            if discord.utils.get(interaction.guild.roles, name=role_name):
                assignable_roles_setting_report.append(f"`{role_name}` Emoji:{role_emoji} Found: ✅")
            else:
                assignable_roles_setting_report.append(f"`{role_name}` Emoji:{role_emoji} Found: ❌")
        settings_embed.add_field(name="Assignable Roles",
                                 value="\n".join(assignable_roles_setting_report))

        assignable_roles_forbidden_report = []
        for role_name in forbidden_roles_list:
            if discord.utils.get(interaction.guild.roles, name=role_name):
                assignable_roles_forbidden_report.append(f"`{role_name}` Found: ✅")
            else:
                assignable_roles_forbidden_report.append(f"`{role_name}` Found: ❌")
        settings_embed.add_field(name="Roles forbidden from self-assign",
                                 value="\n".join(assignable_roles_forbidden_report))

        # ---Rank Saver---
        to_save = await self.bot.open_json_file(interaction.guild, "rank_saver_status.json", False)
        to_restore = await self.bot.open_json_file(interaction.guild, "rank_restoration_status.json", False)
        to_restore_channel = await self.bot.open_json_file(interaction.guild, "rank_restoration_channel.json", str())
        rank_saver_report = []
        if to_save:
            rank_saver_report.append("Rank saver active: ✅")
        else:
            rank_saver_report.append("Rank saver active: ❌")
        if to_restore:
            rank_saver_report.append("Rank restoration active: ✅")
        else:
            rank_saver_report.append("Rank restoration active: ❌")
        if to_restore_channel:
            if discord.utils.get(interaction.guild.channels, name=to_restore_channel):
                rank_saver_report.append(f"Rank restoration message channel: `{to_restore_channel}`; Found: ✅")
            else:
                rank_saver_report.append(f"Rank restoration message channel: `{to_restore_channel}`; Found: ❌")
        else:
            rank_saver_report.append(f"Rank restoration message channel: ❌")

        user_roles_dictionary = await self.bot.open_json_file(interaction.guild, "rank_saver.json", dict())
        rank_saver_report.append(f"Currently saved ranks for {len(user_roles_dictionary)} users.")
        settings_embed.add_field(name="Rank Saver",
                                 value="\n".join(rank_saver_report),
                                 inline=False)

        # ---Open API---
        current_openai_status = await self.bot.open_json_file(interaction.guild, "open_ai_status.json", False)
        openai_report = []
        if current_openai_status:
            openai_report.append("OpenAI active: ✅")
        else:
            openai_report.append("OpenAI active: ❌")

        api_key_list = await self.bot.open_json_file("no_guild", "open_ai_keys.json", list(), general_data=True)
        openai_report.append(f"Saved API keys: {len(api_key_list)}")
        current_prompt = await self.bot.open_json_file(interaction.guild, "openai_prompt.json", "")
        if len(current_prompt) > 1000:
            current_prompt = f"{len(current_prompt)} symbols long."
        openai_report.append(f"Current prompt: {current_prompt}")

        settings_embed.add_field(name="Open API status",
                                 value="\n".join(openai_report),
                                 inline=False)

        # ---Deleted Messages Log---
        logger_active, logger_channel_name, logger_clear_after_hours = await self.bot.open_json_file(
            interaction.guild, "deleted_messages_log_settings.json", list())
        deleted_msg_logger_report = []
        if logger_active:
            deleted_msg_logger_report.append("Saving deleted messages: ✅")
        else:
            deleted_msg_logger_report.append("Saving deleted messages: ❌")
        if discord.utils.get(interaction.guild.channels, name=logger_channel_name):
            deleted_msg_logger_report.append(f"Channel: `{logger_channel_name}`; Found: ✅")
        else:
            deleted_msg_logger_report.append(f"Channel: `{logger_channel_name}`; Found: ❌")

        deleted_msg_logger_report.append(f"Channels clears after `{logger_clear_after_hours}` hours.")

        settings_embed.add_field(name="Deleted messages",
                                 value="\n".join(deleted_msg_logger_report))

        # ---Ordered rank system---
        rank_system = await self.bot.open_json_file(interaction.guild, "rank_system.json", list())
        rank_system_hierarchy_report = []
        rank_system_commands = []
        for rank in rank_system:
            (quiz_name, answer_count, answer_time_limit, font,
             font_size, role_name_to_get, role_name_to_lose, fail_count, command) = rank
            role_to_get = discord.utils.get(interaction.guild.roles, name=role_name_to_get)
            role_to_lose = discord.utils.get(interaction.guild.roles, name=role_name_to_lose)
            report_line = role_name_to_lose
            if role_to_lose:
                report_line += " ✅"
            else:
                report_line += " ❌"
            report_line += " ➜ " + role_name_to_get
            if role_to_get:
                report_line += " ✅"
            else:
                report_line += " ❌"

            rank_system_hierarchy_report.append(report_line)
            rank_system_commands.append(command)

        settings_embed.add_field(name="Ordered rank hierarchy",
                                 value="\n".join(rank_system_hierarchy_report),
                                 inline=False)

        settings_embed.add_field(name="Ordered rank commands",
                                 value="\n\n".join(rank_system_commands),
                                 inline=False)

        channel_reports = []
        announce_channel_name = await self.bot.open_json_file(interaction.guild, "quiz_announce_channel.json", str())
        if discord.utils.get(interaction.guild.channels, name=announce_channel_name):
            announce_channel_report = f"Announce channel: `{announce_channel_name}`; Found: ✅"
        else:
            announce_channel_report = f"Announce channel: `{announce_channel_name}`; Found: ❌"

        channel_reports.append(announce_channel_report)
        failure_channel_names = await self.bot.open_json_file(interaction.guild, "quiz_failure_channels.json", list())
        for channel_name in failure_channel_names:
            if discord.utils.get(interaction.guild.channels, name=channel_name):
                channel_reports.append(f"Failure announce channel: `{channel_name}`; Found: ✅")
            else:
                channel_reports.append(f"Failure announce channel: `{channel_name}`; Found: ❌")

        settings_embed.add_field(name="Quiz channel reports",
                                 value="\n".join(channel_reports))
        # ---Clubs---
        club_report = []
        club_data = await self.bot.open_json_file(interaction.guild, "clubs/club_data.json", dict())
        for club_abbreviation in club_data:
            club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]
            club_manager_role = discord.utils.get(interaction.guild.roles, name=club_manager_role_name)
            if club_manager_role:
                club_report.append(f"`{club_name}` manager role: `{club_manager_role_name}`; Found: ✅")
            else:
                club_report.append(f"`{club_name}` manager role: `{club_manager_role_name}`; Found: ❌")

            club_channel = discord.utils.get(interaction.guild.channels, name=club_channel_name)
            if club_channel:
                club_report.append(f"`{club_name}` channel: `{club_channel_name}`; Found: ✅")
            else:
                club_report.append(f"`{club_name}` channel: `{club_channel_name}`; Found: ❌")
            banned_ids = await self.bot.open_json_file(interaction.guild,
                                                       f"clubs/{club_abbreviation}_banned_users.json", list())
            club_report.append(f"`{len(banned_ids)}` users banned from `{club_name}`.")
            checkpoint_role_data = await self.bot.open_json_file(interaction.guild,
                                                                 f"clubs/{club_abbreviation}_checkpoint_roles.json",
                                                                 list())
            for role_name, points_needed in checkpoint_role_data:
                reward_role = discord.utils.get(interaction.guild.roles, name=role_name)
                if reward_role:
                    club_report.append(f"`{club_name}` reward role: `{role_name}`; Points: `{points_needed}`; Found: ✅")
                else:
                    club_report.append(f"`{club_name}` reward role: `{role_name}`; Points: `{points_needed}`; Found: ❌")
            point_role_data = await self.bot.open_json_file(interaction.guild,
                                                            f"clubs/{club_abbreviation}_role_string.json", list())
            for point_string in point_role_data:
                club_report.append(f"`{club_name}` reward role suffix: `{point_string}`")

        settings_embed.add_field(name="Clubs report",
                                 value="\n".join(club_report),
                                 inline=False)
        # ---Moderation---
        moderator_log_channel_name = await self.bot.open_json_file(interaction.guild, "moderator_channel.json", str())
        moderator_log_channel = discord.utils.get(interaction.guild.channels, name=moderator_log_channel_name)
        if moderator_log_channel:
            moderator_report = f"Mod log channel: `{moderator_log_channel}`; Found: ✅"
        else:
            moderator_report = f"`Mod log channel: `{moderator_log_channel}`; Found: ❌"

        settings_embed.add_field(name="Moderation report",
                                 value=moderator_report,
                                 inline=False)

        # ---Join and leave messages report---
        messages_report = []
        join_message, join_channel_name, join_file_path, join_active, default_role_name = await self.bot.open_json_file(interaction.guild, "join_message_settings.json", list())
        leave_message, leave_channel_name, leave_file_path, leave_active = await self.bot.open_json_file(interaction.guild, "leave_message_settings.json", list())

        if join_message:
            messages_report.append("Join message set: ✅")
        else:
            messages_report.append("Join message set: ❌")
        if join_channel_name:
            if discord.utils.get(interaction.guild.channels, name=join_channel_name):
                messages_report.append(f"Join message channel: `{join_channel_name}`; Found: ✅")
            else:
                messages_report.append(f"Join message channel: `{join_channel_name}`; Found: ❌")
        if join_file_path:
            messages_report.append(f"Send file: `{join_file_path}`")
        if join_active:
            messages_report.append("Join message active: ✅")
        else:
            messages_report.append("Join message active: ❌")

        if default_role_name:
            if discord.utils.get(interaction.guild.roles, name=default_role_name):
                messages_report.append(f"Default role: `{default_role_name}`; Found: ✅")
            else:
                messages_report.append(f"Default role: `{default_role_name}`; Found: ❌")

        if leave_message:
            messages_report.append("Leave message set: ✅")
        else:
            messages_report.append("Leave message set: ❌")
        if leave_channel_name:
            if discord.utils.get(interaction.guild.channels, name=leave_channel_name):
                messages_report.append(f"Leave message channel: `{leave_channel_name}`; Found: ✅")
            else:
                messages_report.append(f"Leave message channel: `{leave_channel_name}`; Found: ❌")
        if leave_file_path:
            messages_report.append(f"Send file: `{leave_file_path}`")
        if leave_active:
            messages_report.append("Leave message active: ✅")
        else:
            messages_report.append("Leave message active: ❌")

        settings_embed.add_field(name="Join and Leave Messages",
                                       value='\n'.join(messages_report))

        # ---Bump report---
        bump_report = []
        bump_channel_name = await self.bot.open_json_file(interaction.guild, "bump_channel_name.json", str())
        if bump_channel_name:
            if discord.utils.get(interaction.guild.channels, name=bump_channel_name):
                bump_report.append(f"Bump channel: `{bump_channel_name}`; Found: ✅")
            else:
                bump_report.append(f"Bump channel: `{bump_channel_name}`; Found: ❌")

        bump_bots = {761562078095867916: "Dissoku",
                     302050872383242240: "Disboard"}

        for bump_bot_id in bump_bots:
            if interaction.guild.get_member(bump_bot_id):
                bump_report.append(f"`{bump_bots[bump_bot_id]}`; Found: ✅")
            else:
                bump_report.append(f"`{bump_bots[bump_bot_id]}`; Found: ❌")

        settings_embed.add_field(name="Bump Reminder",
                                 value='\n'.join(bump_report),
                                 inline=False)

        # ---Auto receive report---
        receive_report = []
        auto_receive_data = await self.bot.open_json_file(interaction.guild, "auto_receive_roles.json", list())
        for role_to_have_name, role_to_get_name in auto_receive_data:
            role_to_have = discord.utils.get(interaction.guild.roles, name=role_to_have_name)
            role_to_get = discord.utils.get(interaction.guild.roles, name=role_to_get_name)
            if role_to_have and role_to_get:
                receive_report.append(f"{role_to_have} -> {role_to_get}; Found: ✅")
            else:
                receive_report.append(f"{role_to_have} -> {role_to_get}; Found: ❌")
        banned_user_data = await self.bot.open_json_file(interaction.guild, "auto_receive_banned_data.json", list())
        receive_report.append(f"Banned {len(banned_user_data)} user from receiving a role.")

        settings_embed.add_field(name="Auto Receive",
                                 value="\n".join(receive_report),
                                 inline=False)

        # --- report---

        # ---Embed report---
        embed_report = []
        embed_report.append(f"Settings embed length: `{len(settings_embed)}` (Max 5800)")
        embed_report.append(f"Settingds embed field count `{len(settings_embed.fields)}` (Max 24)")

        settings_embed.add_field(name="Settings embed",
                                 value="\n".join(embed_report),
                                 inline=False)

        await interaction.response.send_message(embed=settings_embed)
        print(f"Settings embed length :{len(settings_embed)} (Max 6000)\n"
              f"Field count: {len(settings_embed.fields)} (Max 25)")


class CogSelectView(discord.ui.View):

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator


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

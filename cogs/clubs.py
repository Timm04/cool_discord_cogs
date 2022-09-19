"""Cog Description"""
import asyncio
import os
import discord
from typing import Union
from discord.ext import commands
from discord.ext import tasks


class BanUserFromChallengeCommand(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_ban_user",
                         description=f"Ban a user from the {challenge_name}. "
                                     f"This will delete all their progress and clear their points!",
                         callback=self.ban_member,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(member=f"The member to ban.")
    @discord.app_commands.default_permissions(administrator=True)
    async def ban_member(self, interaction: discord.Interaction, member: discord.Member):
        banned_ids = await self.bot.open_json_file(interaction.guild,
                                                   f"clubs/{self.challenge_prefix}_banned_users.json", list())
        if member.id not in banned_ids:
            banned_ids.append(member.id)
            await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_banned_users.json",
                                           banned_ids)
            # Add record deleter
            all_user_data = await self.bot.open_json_file(interaction.guild,
                                                          f"clubs/{self.challenge_prefix}_user_data.json", dict())
            ban_user_data = all_user_data.pop(str(member.id))
            await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_user_data.json",
                                           all_user_data)

            await interaction.response.send_message(f"Banned {member} from the {self.challenge_name} and deleted their "
                                                    f"scores! For reference: {str(ban_user_data)}")
        else:
            await interaction.response.send_message(f"This user is already banned.")


class UnbanUserFromChallengeCommand(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_unban_user",
                         description=f"Unban a user from the {challenge_name}.",
                         callback=self.unban_member,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(member=f"The member to unban.")
    @discord.app_commands.default_permissions(administrator=True)
    async def unban_member(self, interaction: discord.Interaction, member: discord.Member):
        banned_ids = await self.bot.open_json_file(interaction.guild,
                                                   f"clubs/{self.challenge_prefix}_banned_users.json", list())
        if member.id not in banned_ids:
            await interaction.response.send_message(f"User {str(member)} does not seem to be banned.")
            return
        else:
            banned_ids.remove(member.id)
            await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_banned_users.json",
                                           banned_ids)
            await interaction.response.send_message(f"Unbanned {member} from the {self.challenge_name}!")


async def time_period_autocomplete(interaction: discord.Interaction, current_input: str):
    years = ['2019', '2020', '2021', '2022', '2023']
    months = ['01', "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
    possible_periods = []
    for year in years:
        for month in months:
            possible_periods.append(f"{year}-{month}")

    possible_period_choices = [discord.app_commands.Choice(name=possible_period, value=possible_period)
                               for possible_period in possible_periods if current_input in possible_period]

    return possible_period_choices[0:25]


class AddWorkToChallenge(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_add_work",
                         description=f"Add a new work to the {challenge_name}",
                         callback=self.add_work,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(work_name=f"The full name of the work to add.",
                                   short_id=f"ID to uniquely identify the work.",
                                   beginning_period="What month the challenge should start.",
                                   end_period="What month the challenge should end.",
                                   additional_info="Additional info about the work, e.g. URL to VNDB or MAL.")
    @discord.app_commands.autocomplete(beginning_period=time_period_autocomplete,
                                       end_period=time_period_autocomplete)
    @discord.app_commands.default_permissions(administrator=True)
    async def add_work(self, interaction: discord.Interaction, work_name: str, short_id: str, beginning_period: str,
                       end_period: str, additional_info: str):
        work_data = await self.bot.open_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_work_data.json",
                                                  dict())
        if short_id in work_data:
            await interaction.response.send_message("There is a work registered under that ID already. Delete it to add"
                                                    " a new one first.")
            return
        work_data[short_id] = (work_name, beginning_period, end_period, additional_info)
        await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_work_data.json", work_data)
        await interaction.response.send_message(f"Added `{work_name}` for the time period "
                                                f"`{beginning_period}` to `{end_period}` with the unique ID "
                                                f"`{short_id}` to the `{self.challenge_name}`.")


async def works_autocomplete(interaction: discord.Interaction, current_input: str):
    challenge_prefix = interaction.command.name.split("_")[0]
    work_data = await interaction.client.open_json_file(interaction.guild, f"clubs/{challenge_prefix}_work_data.json",
                                                        dict())

    possible_choices = []
    for short_id in work_data:
        full_name = work_data[short_id][0]
        relevant_period = work_data[short_id][1] + "-" + work_data[short_id][2]

        if current_input.lower() in short_id.lower() or current_input.lower() in full_name.lower():
            possible_choices.append(discord.app_commands.Choice(name=f"{short_id} ({relevant_period})", value=short_id))
            possible_choices.append(discord.app_commands.Choice(name=f"{full_name} ({relevant_period})", value=full_name))

    return possible_choices[0:25]

async def works_namespace_autocomplete(interaction: discord.Interaction, current_input: str):
    challenge_prefix = interaction.namespace.club
    work_data = await interaction.client.open_json_file(interaction.guild, f"clubs/{challenge_prefix}_work_data.json",
                                                        dict())
    possible_choices = []
    for short_id in work_data:
        full_name = work_data[short_id][0]
        if current_input.lower() in short_id.lower() or current_input.lower() in full_name.lower():
            possible_choices.append(discord.app_commands.Choice(name=full_name, value=full_name))

    return possible_choices[0:25]

async def clubs_autocomplete(interaction: discord.Interaction, current_input: str):
    club_data = await interaction.client.open_json_file(interaction.guild, "clubs/club_data.json", dict())
    possible_choices = []
    for club_abbreviation in club_data:
        club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]
        if current_input.lower() in club_abbreviation.lower() or current_input.lower() in club_name.lower():
            possible_choices.append(discord.app_commands.Choice(name=club_name, value=club_abbreviation))

    return possible_choices[0:25]

async def get_workid_from_name_or_id(work_data, name_or_id):
    main_id = None
    if name_or_id in work_data:
        main_id = name_or_id
        return main_id
    else:
        for work_id in work_data:
            if name_or_id == work_data[work_id][0]:
                main_id = work_id
                return main_id
    if not main_id:
        return


class RemoveWorkFromChallenge(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_remove_work",
                         description=f"Remove a work from the {challenge_name}",
                         callback=self.remove_work,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(work_name_or_id=f"ID or name of the work")
    @discord.app_commands.autocomplete(work_name_or_id=works_autocomplete)
    @discord.app_commands.default_permissions(administrator=True)
    async def remove_work(self, interaction: discord.Interaction, work_name_or_id: str):
        work_data = await self.bot.open_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_work_data.json",
                                                  dict())
        main_id = await get_workid_from_name_or_id(work_data, work_name_or_id)
        if not main_id:
            await interaction.response.send_message("Unable to find work. Exiting...")
            return

        work_name, beginning_period, end_period, additional_info = work_data.pop(main_id)
        await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_work_data.json",
                                       work_data)

        all_user_data = await self.bot.open_json_file(interaction.guild,
                                                      f"clubs/{self.challenge_prefix}_user_data.json", dict())
        for userid in all_user_data:
            user_work_data = all_user_data[userid]
            all_user_data[userid] = [work for work in user_work_data if work[0] != main_id]

        await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_user_data.json",
                                       all_user_data)

        await interaction.response.send_message(f"{interaction.user.mention} "
                                                f"Removed `{work_name}` for the time period `{beginning_period}` to"
                                                f" `{end_period}` with the unique ID `{main_id}` from the "
                                                f"{self.challenge_name}. Also removed it from all user records.")


class RewardWorkToUser(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_reward_work",
                         description=f"Reward a work to a user in the {challenge_name}.",
                         callback=self.reward_work,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(member="The member that should be rewarded",
                                   work_name_or_id=f"ID or name of the work",
                                   points="How many points should be rewarded.")
    @discord.app_commands.autocomplete(work_name_or_id=works_autocomplete)
    @discord.app_commands.choices(
        points=[discord.app_commands.Choice(name="1 Point", value=1),
                discord.app_commands.Choice(name="2 Points", value=2),
                discord.app_commands.Choice(name="3 Points", value=3)])
    @discord.app_commands.default_permissions(administrator=True)
    async def reward_work(self, interaction: discord.Interaction, member: discord.Member, work_name_or_id: str,
                          points: int):
        banned_ids = await self.bot.open_json_file(interaction.guild,
                                                   f"clubs/{self.challenge_prefix}_banned_users.json", list())
        if member.id in banned_ids:
            await interaction.response.send_message(f"User `{member}` is banned from the {self.challenge_name}!")
            return

        all_user_data = await self.bot.open_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_user_data.json"
                                                      , dict())
        work_data = await self.bot.open_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_work_data.json",
                                                  dict())
        work_id = await get_workid_from_name_or_id(work_data, work_name_or_id)
        work_name, beginning_period, end_period, additional_info = work_data[work_id]

        reward_user_data = all_user_data.get(str(member.id), list())
        for reward_data in reward_user_data:
            if reward_data[0] == work_id:
                await interaction.response.send_message(f"User `{member}` has already been rewarded for `{work_name}`.")
                return

        old_total_points = sum([reward_data[1] for reward_data in reward_user_data])
        reward_tuple = (work_id, points)
        reward_user_data.append(reward_tuple)
        all_user_data[str(member.id)] = reward_user_data
        await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_user_data.json",
                                       all_user_data)
        new_total_points = sum([reward_data[1] for reward_data in reward_user_data])
        await interaction.response.send_message(
            f"Rewarded `{work_name}` to `{str(member)}` bringing their total points "
            f"from **{old_total_points}** to **{new_total_points}**")


async def user_works_autocomplete(interaction: discord.Interaction, current_input: str):
    challenge_prefix = interaction.command.name.split("_")[0]
    member = interaction.namespace.member
    all_user_data = await interaction.client.open_json_file(interaction.guild,
                                                            f"clubs/{challenge_prefix}_user_data.json", dict())
    reward_user_data = all_user_data.get(str(member.id), list())
    possible_choices = []
    for work_id, points in reward_user_data:
        work_data = await interaction.client.open_json_file(interaction.guild,
                                                            f"clubs/{challenge_prefix}_work_data.json", dict())
        work_name, beginning_period, end_period, additional_info = work_data[work_id]
        if current_input.lower() in work_name.lower() or current_input.lower() in work_id.lower():
            possible_choices.append(discord.app_commands.Choice(name=f"{work_name} ({points} Points)", value=work_id))

    return possible_choices[0:25]


class UnrewardWorkFromUser(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_unreward_work",
                         description=f"Remove a work from a user in the {challenge_name}.",
                         callback=self.unreward_work,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(member="The member that should be unrewarded",
                                   work_id="Work name or id.")
    @discord.app_commands.autocomplete(work_id=user_works_autocomplete)
    @discord.app_commands.default_permissions(administrator=True)
    async def unreward_work(self, interaction: discord.Interaction, member: discord.Member, work_id: str):
        all_user_data = await self.bot.open_json_file(interaction.guild,
                                                      f"clubs/{self.challenge_prefix}_user_data.json", dict())
        unreward_user_data = all_user_data.get(str(member.id), list())
        old_total_points = sum([reward_data[1] for reward_data in unreward_user_data])
        for reward_data in unreward_user_data:
            if work_id == reward_data[0]:
                unreward_user_data.remove(reward_data)
                all_user_data[str(member.id)] = unreward_user_data
                new_total_points = sum(reward_data[1] for reward_data in unreward_user_data)
                await self.bot.write_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_user_data.json",
                                               all_user_data)
                await interaction.response.send_message(f"Removed work with the ID `{work_id}` from `{str(member)}`"
                                                        f" bringing their total points from **{old_total_points}** to"
                                                        f" **{new_total_points}**.")


async def generate_leaderboard_embeds(all_user_data, guild, club_name):
    leaderboard_dict = dict()
    for user_id in all_user_data:
        member = guild.get_member(int(user_id))
        if not member:
            continue
        total_points = 0
        for work_entry in all_user_data[user_id]:
            work_id, points = work_entry
            total_points += points

        leaderboard_dict[member.mention] = total_points

    ordered_member_ids = sorted(leaderboard_dict, key=leaderboard_dict.get, reverse=True)
    leaderboard_strings = []
    for index, member_mention in enumerate(ordered_member_ids):
        leaderboard_strings.append(f"{index + 1}. {member_mention} {leaderboard_dict[member_mention]}点")

    embeds_to_send = []
    my_embed = discord.Embed(title=f"{club_name} Leaderboard")
    my_field_strings = []
    for leaderboard_string in leaderboard_strings:
        if len(my_embed) < 5900:
            if len("\n".join(my_field_strings)) < 900:
                my_field_strings.append(leaderboard_string)
            else:
                my_field_strings.append(leaderboard_string)
                my_embed.add_field(name="---", value="\n".join(my_field_strings))
                my_field_strings = []
        else:
            embeds_to_send.append(my_embed)
            my_embed = discord.Embed(title=f"{club_name} Leaderboard")

    if my_field_strings:
        my_embed.add_field(name="---", value="\n".join(my_field_strings))
    embeds_to_send.append(my_embed)

    return embeds_to_send


async def generate_works_embeds(all_work_data, club_name):
    sorted_ids = sorted(all_work_data, key=lambda key: all_work_data[key][1])
    history_strings = []
    for index, work_id in enumerate(sorted_ids):
        work_name, start_date, end_date, extra_info = all_work_data[work_id]
        if start_date == end_date:
            history_strings.append(f"{index + 1}. **{start_date}** `{work_name}` {extra_info} | ID: `{work_id}`")
        else:
            history_strings.append(
                f"{index + 1}. **{start_date}-{end_date}** `{work_name}` {extra_info} | ID: `{work_id}`")

    embeds_to_send = []
    my_embed = discord.Embed(title=f"{club_name} Past Works")
    my_field_strings = []
    for history_string in history_strings:
        if len(my_embed) < 5900:
            if len("\n".join(my_field_strings)) < 700:
                my_field_strings.append(history_string)
            else:
                my_field_strings.append(history_string)
                my_embed.add_field(name="---", value="\n".join(my_field_strings), inline=False)
                my_field_strings = []
        else:
            embeds_to_send.append(my_embed)
            my_embed = discord.Embed(title=f"{club_name} Past Works")

    if my_field_strings:
        my_embed.add_field(name="---", value="\n".join(my_field_strings), inline=False)
    embeds_to_send.append(my_embed)

    return embeds_to_send


class PrintOutLeaderboard(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_leaderboard",
                         description=f"Print out the current leaderboard for the {challenge_name}.",
                         callback=self.leaderboard,
                         guild_ids=[guild_to_register.id])

        self.bot = bot
        self.challenge_prefix = challenge_prefix
        self.challenge_name = challenge_name

    @discord.app_commands.default_permissions(send_messages=True)
    async def leaderboard(self, interaction: discord.Interaction):
        all_user_data = await self.bot.open_json_file(interaction.guild,
                                                      f"clubs/{self.challenge_prefix}_user_data.json", dict())
        embeds_to_send = await generate_leaderboard_embeds(all_user_data, interaction.guild, self.challenge_name)
        await interaction.response.send_message(embeds=embeds_to_send,
                                                allowed_mentions=discord.AllowedMentions.none())


class PrintOutPastWorks(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_past_works",
                         description=f"Print out the past works for the {challenge_name}.",
                         callback=self.past_works,
                         guild_ids=[guild_to_register.id])

        self.bot = bot
        self.challenge_prefix = challenge_prefix
        self.challenge_name = challenge_name

    @discord.app_commands.default_permissions(send_messages=True)
    async def past_works(self, interaction: discord.Interaction):
        work_data = await self.bot.open_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_work_data.json",
                                                  dict())

        embeds_to_send = await generate_works_embeds(work_data, self.challenge_name)
        await interaction.response.send_message(embeds=embeds_to_send,
                                                allowed_mentions=discord.AllowedMentions.none())


class PrintOutListOfUserWithWork(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_get_work_users",
                         description=f"Print out the list of users that read a work for the {challenge_name}.",
                         callback=self.get_work_users,
                         guild_ids=[guild_to_register.id])

        self.bot = bot
        self.challenge_prefix = challenge_prefix
        self.challenge_name = challenge_name

    @discord.app_commands.default_permissions(send_messages=True)
    @discord.app_commands.describe(work_name_or_id="The name or the id of the work.")
    @discord.app_commands.autocomplete(work_name_or_id=works_autocomplete)
    async def get_work_users(self, interaction: discord.Interaction, work_name_or_id: str):
        work_data = await self.bot.open_json_file(interaction.guild, f"clubs/{self.challenge_prefix}_work_data.json",
                                                  dict())
        all_user_data = await self.bot.open_json_file(interaction.guild,
                                                      f"clubs/{self.challenge_prefix}_user_data.json", dict())
        read_user_ids = []
        work_id = await get_workid_from_name_or_id(work_data, work_name_or_id)
        if not work_id:
            await interaction.response.send_message("Unknown work.",
                                                    ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())
            return
        work_name, beginning_period, end_period, additional_info = work_data[work_id]
        for user_id in all_user_data:
            read_works = [read_id_and_points[0] for read_id_and_points in all_user_data[user_id]]
            if work_id in read_works:
                read_user_ids.append(user_id)

        my_embed = discord.Embed(title=f"{len(read_user_ids)} members have read {work_name} for the"
                                       f" {self.challenge_name}. Not listed users have left the server.")
        field_string = []
        for user_id in read_user_ids:
            member = interaction.guild.get_member(int(user_id))
            if member:
                if len("\n".join(field_string)) < 900:
                    field_string.append(member.mention)
                else:
                    field_string.append(member.mention)
                    my_embed.add_field(name="---", value=f"\n".join(field_string))
                    field_string = []

        my_embed.add_field(name="---", value="\n".join(field_string) + "---")
        await interaction.response.send_message(embed=my_embed,
                                                allowed_mentions=discord.AllowedMentions.none())

class ReviewModal(discord.ui.Modal):
    def __init__(self, work_name, channel: discord.TextChannel, manager_role: discord.Role):
        super().__init__(title=f"Review for {work_name}")
        self.work_name = work_name
        self.channel = channel
        self.manager_role = manager_role

    review = discord.ui.TextInput(label='Review:', style=discord.TextStyle.paragraph, min_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        review_embed = discord.Embed(title=f"{self.work_name} review by {str(interaction.user)}",
                                     description=f"|| {self.review} ||")
        await self.channel.send(f"{self.manager_role.mention} | User {interaction.user.mention} has submitted"
                                       f" a review for **{self.work_name}**", embed=review_embed)
        await interaction.response.send_message(f'Your review has been forwarded!', ephemeral=True)

class Clubs(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.create_folders()

    def create_folders(self):
        for guild in self.bot.guilds:
            if os.path.isdir(f"data/{guild.id}/clubs"):
                continue
            else:
                os.mkdir(f"data/{guild.id}/clubs")

    async def cog_load(self):
        for guild in self.bot.guilds:
            await self.add_slash_commands(guild)

        self.point_reward_roles_loop.start()
        self.clear_empty_reward_roles.start()
        self.checkpoint_roles_loop.start()
        self.create_and_update_pins.start()

    async def cog_unload(self):
        self.point_reward_roles_loop.cancel()
        self.clear_empty_reward_roles.cancel()
        self.checkpoint_roles_loop.cancel()
        self.create_and_update_pins.cancel()

    @discord.app_commands.command(
        name="review",
        description="Write a review for a work you read/watched.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(club="Name or shorthand of the club",
                                   work_name="The work you want to review")
    @discord.app_commands.autocomplete(club=clubs_autocomplete,
                                       work_name=works_namespace_autocomplete)
    @discord.app_commands.default_permissions(send_messages=True)
    async def review(self, interaction: discord.Interaction, club: str, work_name: str):
        club_data = await self.bot.open_json_file(interaction.guild, "clubs/club_data.json", dict())
        for club_abbreviation in club_data:
            if club == club_abbreviation:
                club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]
                club_manager_role = discord.utils.get(interaction.guild.roles, name=club_manager_role_name)
                if not club_manager_role:
                    raise ValueError(f'Club manager role not found for {club_name}.')
                club_channel = discord.utils.get(interaction.guild.channels, name=club_channel_name)
                if not club_channel:
                    raise ValueError(f'Club channel not found for {club_name}.')
                review_modal = ReviewModal(work_name, club_channel, club_manager_role)
                await interaction.response.send_modal(review_modal)

    @discord.app_commands.command(
        name="create_new_club",
        description="Creates a challenge/club. WARNING: Creates slash commands that have to be manually allowed.")
    @discord.app_commands.describe(club_name="The full name of the club.",
                                   club_abbreviation="Short name for the club. Best are 3 small letters like 'vnc'.",
                                   club_manager_role="The role that should manage the club.",
                                   club_channel="The channel in which club activity should occur.")
    @discord.app_commands.guild_only()
    @discord.app_commands.default_permissions(administrator=True)
    async def create_new_club(self, interaction: discord.Interaction, club_name: str, club_abbreviation: str,
                              club_manager_role: discord.Role, club_channel: discord.TextChannel):
        club_data = await self.bot.open_json_file(interaction.guild, "clubs/club_data.json", dict())
        if club_name in club_data.values() or club_abbreviation in club_data.keys():
            await interaction.response.send_message("Club already exists. Exiting...")
            return
        club_data[club_abbreviation] = (club_name, club_manager_role.name, club_channel.name)
        await self.bot.write_json_file(interaction.guild, "clubs/club_data.json", club_data)
        await interaction.response.send_message(f"Created new club `{club_name}` with the abbreviation "
                                                f"`{club_abbreviation}`. The club manager role is "
                                                f"{club_manager_role.mention} and the channel is {club_channel.mention}."
                                                , allowed_mentions=discord.AllowedMentions.none())

        await self.bot.reload_extension("cogs.clubs")

    @discord.app_commands.command(
        name="add_point_role_to_challenge",
        description="Add a point role to a challenge that is automatically assigned with points earned.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(club_abbreviation="Short name for the club.",
                                   point_string="The point string that should be appended to the role.",
                                   reference_role="The role UNDER which the reward roles should be created.")
    @discord.app_commands.default_permissions(administrator=True)
    async def add_point_role_to_challenge(self, interaction: discord.Interaction, club_abbreviation: str,
                                          point_string: str, reference_role: discord.Role):

        club_data = await self.bot.open_json_file(interaction.guild, "clubs/club_data.json", dict())
        club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]
        if club_abbreviation not in club_data:
            await interaction.response.send_message(f"Club with the abbreviation {club_abbreviation} not found.")
            return

        new_role_string = (point_string, reference_role.name)
        await self.bot.write_json_file(interaction.guild, f"clubs/{club_abbreviation}_role_string.json",
                                       new_role_string)
        await interaction.response.send_message(f"Assigned the role suffix `{point_string}` as a point reward for the "
                                                f"`{club_name}`. The roles will be created under the role "
                                                f"`{reference_role.name}`.")

    @discord.app_commands.command(
        name="add_checkpoint_role",
        description="Add a checkpoint role to a challenge. For example a checkmark at 10 points.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(club_abbreviation="Short name for the club.",
                                   role_name="The name of the role.",
                                   points="How many points have to be earned for the role to be assigned",
                                   reference_role="The role UNDER which the reward roles should be created.")
    @discord.app_commands.default_permissions(administrator=True)
    async def add_checkpoint_role(self, interaction: discord.Interaction, club_abbreviation: str, points: int,
                                  role_name: str, reference_role: discord.Role):
        club_data = await self.bot.open_json_file(interaction.guild, "clubs/club_data.json", dict())
        club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]
        if club_abbreviation not in club_data:
            await interaction.response.send_message(f"Club with the abbreviation {club_abbreviation} not found.")
            return

        reward_role = discord.utils.get(interaction.guild.roles, name=role_name)

        if not reward_role:
            reward_role = await interaction.guild.create_role(name=role_name)
            positions = {reward_role: reference_role.position - 1}
            await interaction.guild.edit_role_positions(positions)

        new_reward_role_data = (reward_role.name, points)
        all_reward_role_data = await self.bot.open_json_file(interaction.guild,
                                                             f"clubs/{club_abbreviation}_checkpoint_roles.json", list())
        for old_reward_role_data in all_reward_role_data:
            if reward_role.name in old_reward_role_data:
                all_reward_role_data.remove(old_reward_role_data)

        all_reward_role_data.append(new_reward_role_data)
        await self.bot.write_json_file(interaction.guild, f"clubs/{club_abbreviation}_checkpoint_roles.json",
                                       all_reward_role_data)
        await interaction.response.send_message(
            f"Created checkmark role {reward_role.name} for the {club_name} rewarded"
            f" at {points} points.")

    async def add_slash_commands(self, guild):
        club_data = await self.bot.open_json_file(guild, "clubs/club_data.json", dict())
        for club_abbreviation in club_data:
            club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]

            ban_command = BanUserFromChallengeCommand(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(ban_command)

            unban_command = UnbanUserFromChallengeCommand(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(unban_command)

            add_work_command = AddWorkToChallenge(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(add_work_command)

            remove_work_command = RemoveWorkFromChallenge(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(remove_work_command)

            reward_command = RewardWorkToUser(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(reward_command)

            unreward_command = UnrewardWorkFromUser(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(unreward_command)

            print_leaderboard_command = PrintOutLeaderboard(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(print_leaderboard_command)

            work_history_command = PrintOutPastWorks(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(work_history_command)

            get_work_users_command = PrintOutListOfUserWithWork(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(get_work_users_command)

    @tasks.loop(minutes=10)
    async def point_reward_roles_loop(self):
        await asyncio.sleep(60)
        for guild in self.bot.guilds:
            club_data = await self.bot.open_json_file(guild, "clubs/club_data.json", dict())
            for club_abbreviation in club_data:
                reward_role_data = await self.bot.open_json_file(guild, f"clubs/{club_abbreviation}_role_string.json",
                                                                 list())
                if not reward_role_data:
                    continue
                point_suffix, reference_role_name = reward_role_data
                club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]
                reference_role = discord.utils.get(guild.roles, name=reference_role_name)
                if not reference_role:
                    continue

                all_user_data = await self.bot.open_json_file(guild, f"clubs/{club_abbreviation}_user_data.json",
                                                              dict())
                for user_id in all_user_data:
                    works_read = all_user_data[user_id]
                    total_points = sum([id_points[1] for id_points in works_read])
                    member = guild.get_member(int(user_id))
                    if not member:
                        continue
                    roles_to_remove = [role for role in member.roles if role.name.endswith(point_suffix)]
                    role_name_to_assign = f"{total_points}{point_suffix}"
                    role_to_assign = discord.utils.get(guild.roles, name=role_name_to_assign)
                    if not role_to_assign:
                        role_to_assign = await guild.create_role(name=role_name_to_assign)
                        positions = dict()
                        positions[role_to_assign] = reference_role.position - 1
                        await guild.edit_role_positions(positions)

                    if role_to_assign in roles_to_remove:
                        roles_to_remove.remove(role_to_assign)

                    if roles_to_remove:
                        print(f"Removing roles {','.join([role.name for role in roles_to_remove])} from {member} for "
                              f"{club_name}.")
                        await asyncio.sleep(5)
                        await member.remove_roles(*roles_to_remove)

                    if role_to_assign not in member.roles:
                        print(f"Giving {role_to_assign.name} to {member} for {club_name}")
                        await asyncio.sleep(5)
                        await member.add_roles(role_to_assign)

    @tasks.loop(minutes=60)
    async def clear_empty_reward_roles(self):
        await asyncio.sleep(120)
        for guild in self.bot.guilds:
            club_data = await self.bot.open_json_file(guild, "clubs/club_data.json", dict())
            for club_abbreviation in club_data:
                point_reward_role_data = await self.bot.open_json_file(guild,
                                                                       f"clubs/{club_abbreviation}_role_string.json",
                                                                       list())
                if not point_reward_role_data:
                    continue
                point_suffix, reference_role_name = point_reward_role_data
                reward_roles_to_delete = [role for role in guild.roles if role.name.endswith(point_suffix) and
                                          len(role.members) == 0]

                for role in reward_roles_to_delete:
                    await asyncio.sleep(10)
                    print(f"Deleting role: {role.name}")
                    await role.delete(reason="No members.")

    async def get_checkpoint_role(self, total_points, checkpoint_role_data):
        checkpoint_role_data = sorted(checkpoint_role_data, key=lambda sublist: sublist[1])
        unearned_role_names = []
        earned_roles = []
        for role_name, points in checkpoint_role_data:
            if total_points < points:
                unearned_role_names.append(role_name)
            elif total_points >= points:
                earned_roles.append(role_name)
        if earned_roles:
            role_name_to_give = earned_roles.pop()
        else:
            role_name_to_give = None
        unearned_role_names.extend(earned_roles)
        return role_name_to_give, unearned_role_names

    @tasks.loop(minutes=10)
    async def checkpoint_roles_loop(self):
        await asyncio.sleep(120)
        for guild in self.bot.guilds:
            club_data = await self.bot.open_json_file(guild, "clubs/club_data.json", dict())
            for club_abbreviation in club_data:
                club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]
                checkpoint_role_data = await self.bot.open_json_file(guild,
                                                                     f"clubs/{club_abbreviation}_checkpoint_roles.json",
                                                                     list())
                if not checkpoint_role_data:
                    continue
                all_user_data = await self.bot.open_json_file(guild, f"clubs/{club_abbreviation}_user_data.json",
                                                              dict())
                for user_id in all_user_data:
                    works_read = all_user_data[user_id]
                    total_points = sum([id_points[1] for id_points in works_read])
                    member = guild.get_member(int(user_id))
                    if not member:
                        continue
                    role_name_to_give, unearned_role_names = await self.get_checkpoint_role(total_points,
                                                                                            checkpoint_role_data)
                    unearned_roles = [discord.utils.get(guild.roles, name=role_name) for role_name in
                                      unearned_role_names]
                    earned_role = discord.utils.get(guild.roles, name=role_name_to_give)

                    remove_roles = False
                    for role in member.roles:
                        if role in unearned_roles:
                            remove_roles = False

                    if remove_roles:
                        await asyncio.sleep(5)
                        print(
                            f"Removing {', '.join([role.name for role in unearned_roles])} from {member} for {club_name}")
                        await member.remove_roles(*unearned_roles)

                    if earned_role and earned_role not in member.roles:
                        await asyncio.sleep(5)
                        print(f"Giving {earned_role.name} to {member} for {club_name}")
                        await member.add_roles(earned_role)

    @tasks.loop(minutes=10)
    async def create_and_update_pins(self):
        await asyncio.sleep(300)
        for guild in self.bot.guilds:
            club_data = await self.bot.open_json_file(guild, "clubs/club_data.json", dict())
            for club_abbreviation in club_data:
                club_name, club_manager_role_name, club_channel_name = club_data[club_abbreviation]

                all_user_data = await self.bot.open_json_file(guild, f"clubs/{club_abbreviation}_user_data.json", dict())
                embeds_to_send_leaderboard = await generate_leaderboard_embeds(all_user_data, guild, club_name)

                work_data = await self.bot.open_json_file(guild, f"clubs/{club_abbreviation}_work_data.json", dict())
                embeds_to_send_works = await generate_works_embeds(work_data, club_name)

                club_channel = discord.utils.get(guild.channels, name=club_channel_name)
                if not club_channel:
                    raise ValueError(f'Club channel not found for {club_name}.')

                await asyncio.sleep(10)
                channel_pins = await club_channel.pins()
                pins_by_self = [pin for pin in channel_pins if pin.author.id == self.bot.user.id and pin.embeds
                                and pin.content == "" and not pin.components]

                try:
                    await asyncio.sleep(5)
                    await pins_by_self[0].edit(embeds=embeds_to_send_works, allowed_mentions=discord.AllowedMentions.none())
                except IndexError:
                    message_to_pin = await club_channel.send(embeds=embeds_to_send_works)
                    await message_to_pin.pin()
                try:
                    await asyncio.sleep(5)
                    await pins_by_self[1].edit(embeds=embeds_to_send_leaderboard, allowed_mentions=discord.AllowedMentions.none())
                except IndexError:
                    message_to_pin = await club_channel.send(embeds=embeds_to_send_leaderboard)
                    await message_to_pin.pin()





async def setup(bot):
    await bot.add_cog(Clubs(bot))

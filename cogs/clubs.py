"""Framework for clubs with a role point system and scoreboard"""
import asyncio
import json

import discord
from discord.ext import commands
from discord.ext import tasks

from . import data_management
from . import user_name_record

#########################################

# Database Operations and Values

SETTINGS_TABLE_NAME = "clubs_settings"
SETTINGS_COLUMNS = ("guild_id", "club_prefix", "club_name", "club_manager_role_name", "club_channel_name",
                    "added_works_json", "user_data_json", "banned_user_list", "reward_role_suffix", "checkpoints_roles")


async def fetch_club_data(guild_id: int, club_prefix: str):
    club_name = await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2],
                                                  guild_id=guild_id,
                                                  club_prefix=club_prefix)
    club_manager_role_name = await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3],
                                                               guild_id=guild_id,
                                                               club_prefix=club_prefix)
    club_channel_name = await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[4],
                                                          guild_id=guild_id,
                                                          club_prefix=club_prefix)
    reward_role_suffix = await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[8],
                                                           guild_id=guild_id,
                                                           club_prefix=club_prefix)

    return club_name, club_manager_role_name, club_channel_name, reward_role_suffix


async def write_club_data(guild_id: int, club_prefix: str, club_name: str, club_manager_role_name: str,
                          club_channel_name, reward_role_suffix):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[2], club_name,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[3], club_manager_role_name,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[4], club_channel_name,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[8], reward_role_suffix,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)


async def fetch_checkpoint_role_data(guild_id: int, club_prefix: str):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[9],
                                             guild_id=guild_id,
                                             club_prefix=club_prefix)


async def write_checkpoint_role_data(guild_id: int, club_prefix: str, checkpoint_role_data: dict):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[9], checkpoint_role_data,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)


async def fetch_banned_user_list(guild_id: int, club_prefix: str):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[7],
                                             guild_id=guild_id,
                                             club_prefix=club_prefix)


async def write_banned_user_list(guild_id: int, club_prefix: str, banned_users: list):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[7], banned_users,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)


async def fetch_club_works_data(guild_id: int, club_prefix: str):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[5],
                                             guild_id=guild_id,
                                             club_prefix=club_prefix)


async def write_clubs_works_data(guild_id: int, club_prefix: str, work_data: dict):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[5], work_data,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)


async def fetch_club_user_data(guild_id: int, club_prefix: str):
    return await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[6],
                                             guild_id=guild_id,
                                             club_prefix=club_prefix)


async def write_club_user_data(guild_id: int, club_prefix: str, user_data: dict):
    await data_management.update_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[6], user_data,
                                       guild_id=guild_id,
                                       club_prefix=club_prefix)


async def fetch_club_prefix_list(guild_id: int):
    club_prefix_list = await data_management.fetch_entry(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS[1], guild_id=guild_id)
    return club_prefix_list


#########################################

# Autocomplete functions

def generate_possible_time_periods():
    years = ['2019', '2020', '2021', '2022', '2023', '2024']
    months = ['01', "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
    possible_periods = []
    for year in years:
        for month in months:
            possible_periods.append(f"{year}-{month}")
    return possible_periods


POSSIBLE_PERIODS = generate_possible_time_periods()


async def time_period_autocomplete(interaction: discord.Interaction, current_input: str):
    possible_period_choices = [discord.app_commands.Choice(name=possible_period, value=possible_period)
                               for possible_period in POSSIBLE_PERIODS if current_input in possible_period]

    return possible_period_choices[0:25]


async def works_autocomplete(interaction: discord.Interaction, current_input: str):
    challenge_prefix = interaction.command.name.split("_")[0]
    work_data = await fetch_club_works_data(interaction.guild_id, challenge_prefix)

    possible_choices = []
    for short_id in work_data:
        full_name = work_data[short_id][0]
        relevant_period = work_data[short_id][1] + "-" + work_data[short_id][2]

        if current_input.lower() in short_id.lower() or current_input.lower() in full_name.lower():
            possible_choices.append(discord.app_commands.Choice(name=f"{short_id} ({relevant_period})", value=short_id))
            possible_choices.append(
                discord.app_commands.Choice(name=f"{full_name} ({relevant_period})", value=short_id))

    return possible_choices[0:25]


async def user_works_autocomplete(interaction: discord.Interaction, current_input: str):
    challenge_prefix = interaction.command.name.split("_")[0]
    member = interaction.namespace.member
    all_user_data = await fetch_club_user_data(interaction.guild_id, challenge_prefix)
    work_data = await fetch_club_works_data(interaction.guild_id, challenge_prefix)
    reward_user_data = all_user_data.get(str(member.id), list())
    possible_choices = []
    for work_id, points in reward_user_data:
        work_name, beginning_period, end_period, additional_info = work_data[work_id]
        if current_input.lower() in work_name.lower() or current_input.lower() in work_id.lower():
            possible_choices.append(discord.app_commands.Choice(name=f"{work_name} ({points} Points)", value=work_id))

    return possible_choices[0:25]


#########################################

# Other functions

async def generate_leaderboard_embeds(bot, all_user_data, guild, club_name):
    embeds_to_send = []
    sorted_ids = sorted(all_user_data, key=lambda key: sum(entry[1] for entry in all_user_data[key]), reverse=True)

    leaderboard_embed = discord.Embed(title=f"{club_name} Leaderboard")
    leaderboard_description_strings = []
    for index, user_id in enumerate(sorted_ids):
        member = guild.get_member(int(user_id))
        member_points = sum(entry[1] for entry in all_user_data[user_id])
        if not member:
            user_name = await user_name_record.fetch_user_name(bot, int(user_id))
            leaderboard_description_strings.append(f"{index + 1}. <{user_name}> {member_points}点")
        else:
            leaderboard_description_strings.append(f"{index + 1}. {member.mention} {member_points}点")

        if len("\n".join(leaderboard_description_strings)) > 1000:
            current_member_line = leaderboard_description_strings.pop()

            if len(leaderboard_embed) < 5000:
                leaderboard_embed.add_field(name="---", value="\n".join(leaderboard_description_strings), inline=False)
                leaderboard_description_strings = [current_member_line]
            else:
                embeds_to_send.append(leaderboard_embed)
                leaderboard_embed = discord.Embed(title=f"{club_name} Leaderboard")
                leaderboard_embed.add_field(name="---", value="\n".join(leaderboard_description_strings), inline=False)
                leaderboard_description_strings = [current_member_line]

    if leaderboard_description_strings:
        if len(leaderboard_embed) < 5000:
            leaderboard_embed.add_field(name="---", value="\n".join(leaderboard_description_strings), inline=False)
        else:
            embeds_to_send.append(leaderboard_embed)
            leaderboard_embed = discord.Embed(title=f"{club_name} Leaderboard")
            leaderboard_embed.add_field(name="---", value="\n".join(leaderboard_description_strings), inline=False)

    embeds_to_send.append(leaderboard_embed)

    return embeds_to_send


async def generate_works_embeds(all_work_data, club_name):
    embeds_to_send = []
    sorted_ids = sorted(all_work_data, key=lambda key: all_work_data[key][1])

    works_embed = discord.Embed(title=f"{club_name} Past Works")
    history_strings = []
    for index, work_id in enumerate(sorted_ids):
        work_name, start_date, end_date, extra_info = all_work_data[work_id]
        if start_date == end_date:
            history_strings.append(f"{index + 1}. **{start_date}** `{work_name}` {extra_info} | ID: `{work_id}`")
        else:
            history_strings.append(
                f"{index + 1}. **{start_date}-{end_date}** `{work_name}` {extra_info} | ID: `{work_id}`")

        if len("\n".join(history_strings)) > 1000:
            current_work_line = history_strings.pop()

            if len(works_embed) < 5000:
                works_embed.add_field(name="---", value="\n".join(history_strings), inline=False)
                history_strings = [current_work_line]
            else:
                embeds_to_send.append(works_embed)
                works_embed = discord.Embed(title=f"{club_name} Past Works")
                works_embed.add_field(name="---", value="\n".join(history_strings), inline=False)
                history_strings = [current_work_line]

    if history_strings:
        if len(works_embed) < 5000:
            works_embed.add_field(name="---", value="\n".join(history_strings), inline=False)
        else:
            embeds_to_send.append(works_embed)
            works_embed = discord.Embed(title=f"{club_name} Past Works")
            works_embed.add_field(name="---", value="\n".join(history_strings), inline=False)

    embeds_to_send.append(works_embed)

    return embeds_to_send


async def give_out_reward_roles(guild: discord.Guild, club_prefix: str):
    club_name, club_manager_role_name, club_channel_name, reward_role_suffix = await fetch_club_data(guild.id,
                                                                                                     club_prefix)
    all_user_data = await fetch_club_user_data(guild.id, club_prefix)
    for member_id in all_user_data:
        member = guild.get_member(int(member_id))
        if not member:
            continue
        total_points = sum([reward_data[1] for reward_data in all_user_data[member_id]])
        if total_points == 0:
            continue
        role_name = f"{total_points}{reward_role_suffix}"
        reward_role = discord.utils.get(guild.roles, name=role_name)
        if not reward_role:
            print(f"CLUBS: Creating nonexistent role {role_name}")
            await asyncio.sleep(5)
            reward_role = await guild.create_role(name=role_name, colour=discord.Colour.dark_grey())
        other_reward_roles = [role for role in guild.roles if role.name.endswith(reward_role_suffix) and role is
                              not reward_role]
        if reward_role in member.roles:
            continue
        else:
            await asyncio.sleep(5)
            await member.remove_roles(*other_reward_roles)
            print(f"CLUBS: Giving {member} the {reward_role.name} role for the {club_name}")
            await asyncio.sleep(5)
            await member.add_roles(reward_role)

    # Role cleanup
    roles_to_delete = [role for role in guild.roles if
                       role.name.endswith(reward_role_suffix) and len(role.members) == 0]
    for role in roles_to_delete:
        print(f"Deleting role {role.name} as it has no members.")
        await asyncio.sleep(5)
        await role.delete(reason="No members for role.")


async def give_out_checkpoint_roles(guild: discord.Guild, club_prefix):
    all_user_data = await fetch_club_user_data(guild.id, club_prefix)
    checkpoint_role_data = await fetch_checkpoint_role_data(guild.id, club_prefix)
    all_checkpoint_roles = [discord.utils.get(role_data[0]) for role_data in checkpoint_role_data]
    if not checkpoint_role_data:
        return
    sorted_checkpoint_role_data = sorted(checkpoint_role_data, key=lambda item: item[1])
    for user_id in all_user_data:
        member = guild.get_member(int(user_id))
        if not member:
            continue
        total_points = sum([reward_data[1] for reward_data in all_user_data[user_id]])
        role_name_to_give = None
        for role_name, needed_points in sorted_checkpoint_role_data:
            if total_points >= needed_points:
                role_name_to_give = role_name
        if role_name_to_give:
            checkpoint_role = discord.utils.get(guild.roles, name=role_name_to_give)
            if not checkpoint_role:
                continue
            if checkpoint_role in member.roles:
                continue
            print(f"CLUBS: Giving {checkpoint_role.name} to {member}")
            await asyncio.sleep(5)
            await member.remove_roles(*all_checkpoint_roles)
            await asyncio.sleep(5)
            await member.add_roles(checkpoint_role)


#########################################

# Club custom commands

class ToggleBanCommand(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_toggle_ban_user",
                         description=f"Ban/Unban a user from the {challenge_name} and clear record.",
                         callback=self.ban_or_unban_member,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(member=f"The member to ban.")
    @discord.app_commands.default_permissions(administrator=True)
    async def ban_or_unban_member(self, interaction: discord.Interaction, member: discord.Member):
        banned_ids = await fetch_banned_user_list(interaction.guild_id, self.challenge_prefix)
        if member.id not in banned_ids:

            # Ban Member
            banned_ids.append(member.id)
            await write_banned_user_list(interaction.guild_id, self.challenge_prefix, banned_ids)

            # Delete member data
            all_user_data = await fetch_club_user_data(interaction.guild_id, self.challenge_prefix)
            banned_user_data = all_user_data.pop(str(member.id))
            await write_club_user_data(interaction.guild_id, self.challenge_prefix, all_user_data)

            await interaction.response.send_message(f"Banned {member} from the {self.challenge_name} and deleted their "
                                                    f"scores! Cleared user data: `{json.dumps(banned_user_data)}`")
        else:
            banned_ids.remove(member.id)
            await write_banned_user_list(interaction.guild_id, self.challenge_prefix, banned_ids)
            await interaction.response.send_message(f"Unbanned {member}. "
                                                    f"They can now participate in the {self.challenge_name} again.")


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
        work_data = await fetch_club_works_data(interaction.guild_id, self.challenge_prefix)
        if short_id in work_data:
            await interaction.response.send_message("There is a work registered under that ID already. Delete it to add"
                                                    " a new one first.")
            return
        work_data[short_id] = (work_name, beginning_period, end_period, additional_info)
        await write_clubs_works_data(interaction.guild_id, self.challenge_prefix, work_data)
        await interaction.response.send_message(f"Added `{work_name}` for the time period "
                                                f"`{beginning_period}` to `{end_period}` with the unique ID "
                                                f"`{short_id}` to the `{self.challenge_name}`.")


class RemoveWorkFromChallenge(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_remove_work",
                         description=f"Remove a work from the {challenge_name}",
                         callback=self.remove_work,
                         guild_ids=[guild_to_register.id])

        self.challenge_name = challenge_name
        self.challenge_prefix = challenge_prefix
        self.bot = bot

    @discord.app_commands.describe(work_id=f"ID or name of the work")
    @discord.app_commands.autocomplete(work_id=works_autocomplete)
    @discord.app_commands.default_permissions(administrator=True)
    async def remove_work(self, interaction: discord.Interaction, work_id: str):
        work_data = await fetch_club_works_data(interaction.guild_id, self.challenge_prefix)
        if work_id not in work_data:
            await interaction.response.send_message("Unable to find work. Exiting...")
            return

        work_name, beginning_period, end_period, additional_info = work_data.pop(work_id)
        await write_clubs_works_data(interaction.guild_id, self.challenge_prefix, work_data)

        all_user_data = await fetch_club_user_data(interaction.guild_id, self.challenge_prefix)

        for user_id in all_user_data:
            user_work_data = all_user_data[user_id]
            all_user_data[user_id] = [work for work in user_work_data if work[0] != work_id]

        await write_club_user_data(interaction.guild_id, self.challenge_prefix, all_user_data)

        await interaction.response.send_message(f"{interaction.user.mention} "
                                                f"Removed `{work_name}` for the time period `{beginning_period}` to"
                                                f" `{end_period}` with the unique ID `{work_id}` from the "
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
                                   work_id=f"ID of the work",
                                   points="How many points should be rewarded.")
    @discord.app_commands.autocomplete(work_id=works_autocomplete)
    @discord.app_commands.choices(
        points=[discord.app_commands.Choice(name="1 Point", value=1),
                discord.app_commands.Choice(name="2 Points", value=2),
                discord.app_commands.Choice(name="3 Points", value=3),
                discord.app_commands.Choice(name="4 Points", value=4)])
    @discord.app_commands.default_permissions(administrator=True)
    async def reward_work(self, interaction: discord.Interaction, member: discord.Member, work_id: str,
                          points: int):
        banned_ids = await fetch_banned_user_list(interaction.guild_id, self.challenge_prefix)
        if member.id in banned_ids:
            await interaction.response.send_message(f"User `{member}` is banned from the {self.challenge_name}!")
            return

        all_user_data = await fetch_club_user_data(interaction.guild_id, self.challenge_prefix)
        work_data = await fetch_club_works_data(interaction.guild_id, self.challenge_prefix)
        if work_id not in work_data:
            await interaction.response.send_message(f"Unable to find work. Exiting.")
            return
        work_name, beginning_period, end_period, additional_info = work_data[work_id]

        reward_user_data = all_user_data.get(str(member.id), list())
        for reward_data in reward_user_data:
            if reward_data[0] == work_id:
                await interaction.response.send_message(f"User `{member}` has already been rewarded for `{work_name}`. "
                                                        f"Remove it from them first to reward it again.")
                return

        old_total_points = sum([reward_data[1] for reward_data in reward_user_data])
        reward_tuple = (work_id, points)
        reward_user_data.append(reward_tuple)
        all_user_data[str(member.id)] = reward_user_data
        await write_club_user_data(interaction.guild_id, self.challenge_prefix, all_user_data)
        new_total_points = sum([reward_data[1] for reward_data in reward_user_data])
        await interaction.response.send_message(
            f"Rewarded `{work_name}` to `{str(member)}` bringing their total points "
            f"from **{old_total_points}** to **{new_total_points}**")


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
        all_user_data = await fetch_club_user_data(interaction.guild_id, self.challenge_prefix)
        unreward_user_data = all_user_data.get(str(member.id), list())
        old_total_points = sum([reward_data[1] for reward_data in unreward_user_data])
        for reward_data in unreward_user_data[:]:
            if work_id == reward_data[0]:
                unreward_user_data.remove(reward_data)
                all_user_data[str(member.id)] = unreward_user_data
                new_total_points = sum(reward_data[1] for reward_data in unreward_user_data)
                await write_club_user_data(interaction.guild_id, self.challenge_prefix, all_user_data)
                await interaction.response.send_message(f"Removed work with the ID `{work_id}` from `{str(member)}`"
                                                        f" bringing their total points from **{old_total_points}** to"
                                                        f" **{new_total_points}**.")


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
        all_user_data = await fetch_club_user_data(interaction.guild_id, self.challenge_prefix)
        await interaction.response.defer()
        embeds_to_send = await generate_leaderboard_embeds(self.bot, all_user_data, interaction.guild,
                                                           self.challenge_name)
        await interaction.edit_original_response(embed=embeds_to_send[0],
                                                 allowed_mentions=discord.AllowedMentions.none())
        if embeds_to_send[1:]:
            for embed in embeds_to_send[1:]:
                await interaction.message.reply(embed=embed)


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
        work_data = await fetch_club_works_data(interaction.guild_id, self.challenge_prefix)

        embeds_to_send = await generate_works_embeds(work_data, self.challenge_name)
        await interaction.response.send_message(embeds=embeds_to_send,
                                                allowed_mentions=discord.AllowedMentions.none())

        if embeds_to_send[1:]:
            for embed in embeds_to_send[1:]:
                await interaction.message.reply(embed=embed)


class PrintOutListOfUserWithWork(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_get_work_users",
                         description=f"Print out the list of users that read/watched a work for the {challenge_name}.",
                         callback=self.get_work_users,
                         guild_ids=[guild_to_register.id])

        self.bot = bot
        self.challenge_prefix = challenge_prefix
        self.challenge_name = challenge_name

    @discord.app_commands.default_permissions(send_messages=True)
    @discord.app_commands.describe(work_id="The name or the id of the work.")
    @discord.app_commands.autocomplete(work_id=works_autocomplete)
    async def get_work_users(self, interaction: discord.Interaction, work_id: str):
        work_data = await fetch_club_works_data(interaction.guild_id, self.challenge_prefix)
        all_user_data = await fetch_club_user_data(interaction.guild_id, self.challenge_prefix)

        if work_id not in work_data:
            await interaction.response.send_message("Unknown work. Exiting...",
                                                    ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())
            return

        work_name, beginning_period, end_period, additional_info = work_data[work_id]
        read_users_strings = []
        for user_id in all_user_data:
            member = interaction.guild.get_member(int(user_id))
            if not member:
                continue
            if work_id in [read_data[0] for read_data in all_user_data[user_id]]:
                read_users_strings.append(f"{member} {member.mention}")

        read_users_embed = discord.Embed(title=f"{len(read_users_strings)} users for {work_name}. "
                                               f"Unlisted users have left the server.")
        read_users_embed.description = "\n".join(read_users_strings)

        await interaction.response.send_message(embed=read_users_embed,
                                                allowed_mentions=discord.AllowedMentions.none())


class PrintOutListOfWorksForUser(discord.app_commands.Command):
    def __init__(self, challenge_prefix, challenge_name, guild_to_register, bot):
        super().__init__(name=f"{challenge_prefix}_get_user_works",
                         description=f"Print out the list of works that was read/watched "
                                     f"by a user for the {challenge_name}.",
                         callback=self.get_users_work,
                         guild_ids=[guild_to_register.id])

        self.bot = bot
        self.challenge_prefix = challenge_prefix
        self.challenge_name = challenge_name

    @discord.app_commands.default_permissions(send_messages=True)
    @discord.app_commands.describe(member="Member you want to get works for")
    async def get_users_work(self, interaction: discord.Interaction, member: discord.Member):
        work_data = await fetch_club_works_data(interaction.guild_id, self.challenge_prefix)
        all_user_data = await fetch_club_user_data(interaction.guild_id, self.challenge_prefix)

        if str(member.id) not in all_user_data:
            await interaction.response.send_message("User not found in data. Exiting...")
            return

        work_strings = []
        for work_id, points in all_user_data[str(member.id)]:
            work_name, beginning_period, end_period, additional_info = work_data[work_id]
            work_string = f"{work_name} (**{work_id}**) with {points} points."
            work_strings.append(work_string)

        read_works_embed = discord.Embed(title=f"Works read by {member} for the {self.challenge_name}")
        read_works_embed.description = "\n".join(work_strings)
        await interaction.response.send_message(embed=read_works_embed)


#########################################


class Clubs(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await data_management.create_table(SETTINGS_TABLE_NAME, SETTINGS_COLUMNS)
        for guild in self.bot.guilds:
            await self.add_slash_commands(guild)
        self.club_updates.start()

    async def add_slash_commands(self, guild):
        club_abbreviations = await fetch_club_prefix_list(guild.id)
        for club_abbreviation in club_abbreviations:
            club_data = await fetch_club_data(guild.id, club_abbreviation)
            club_name, club_manager_role_name, club_channel_name, reward_role_suffix = club_data

            ban_command = ToggleBanCommand(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(ban_command)

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

            get_users_works_command = PrintOutListOfWorksForUser(club_abbreviation, club_name, guild, self.bot)
            self.bot.tree.add_command(get_users_works_command)

    # TODO: (Low priority; create on demand)  Slash command to add new clubs

    # TODO: (Low priority; create on demand)  Slash command to add checkpoint roles

    # TODO: (Low priority; create on demand) Slash command to set reward role suffix string

    async def update_leaderboard_pins(self, guild: discord.Guild, club_prefix):
        club_name, club_manager_role_name, club_channel_name, reward_role_suffix = await fetch_club_data(guild.id,
                                                                                                         club_prefix)

        club_channel = discord.utils.get(guild.channels, name=club_channel_name)
        if not club_channel:
            return

        past_leaderboard_pins = [pin for pin in await club_channel.pins()
                                 if pin.embeds and pin.embeds[0].title.endswith("Leaderboard")
                                 and pin.author.id == self.bot.user.id]

        all_user_data = await fetch_club_user_data(guild.id, club_prefix)
        leaderboard_embeds = await generate_leaderboard_embeds(self.bot, all_user_data, guild, club_name)
        for index, embed in enumerate(leaderboard_embeds):
            try:
                to_edit_message = past_leaderboard_pins[index]
            except IndexError:
                print(f"CLUBS: Creating new leaderboard message for {club_name}")
                await asyncio.sleep(10)
                to_edit_message = await club_channel.send(embed=discord.Embed(title=f"{club_name} Leaderboard"))
                await to_edit_message.pin()
            print(f"CLUBS: Editing leaderboard message for {club_name}")
            await asyncio.sleep(10)
            await to_edit_message.edit(embed=embed)

    async def update_past_works_pins(self, guild: discord.Guild, club_prefix):
        club_name, club_manager_role_name, club_channel_name, reward_role_suffix = await fetch_club_data(guild.id,
                                                                                                         club_prefix)

        club_channel = discord.utils.get(guild.channels, name=club_channel_name)
        if not club_channel:
            return

        past_leaderboard_pins = [pin for pin in await club_channel.pins()
                                 if pin.embeds and pin.embeds[0].title.endswith("Past Works")
                                 and pin.author.id == self.bot.user.id]

        all_works_data = await fetch_club_works_data(guild.id, club_prefix)
        works_embeds = await generate_works_embeds(all_works_data, club_name)
        for index, embed in enumerate(works_embeds):
            try:
                to_edit_message = past_leaderboard_pins[index]
            except IndexError:
                print(f"CLUBS: Creating new past works message for {club_name}")
                await asyncio.sleep(10)
                to_edit_message = await club_channel.send(embed=discord.Embed(title=f"{club_name} Past Works"))
                await to_edit_message.pin()
            print(f"CLUBS: Editing past works message for {club_name}")
            await asyncio.sleep(10)
            await to_edit_message.edit(embed=embed)

    @tasks.loop(minutes=10)
    async def club_updates(self):
        await asyncio.sleep(90)
        for guild in self.bot.guilds:
            club_prefixes = await fetch_club_prefix_list(guild.id)
            for club_prefix in club_prefixes:
                await self.update_leaderboard_pins(guild, club_prefix)
                await self.update_past_works_pins(guild, club_prefix)
                await give_out_reward_roles(guild, club_prefix)
                await give_out_checkpoint_roles(guild, club_prefix)

    # TODO: Add function that removes checkpoint roles if user loses points


async def setup(bot):
    await bot.add_cog(Clubs(bot))

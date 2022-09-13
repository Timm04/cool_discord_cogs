"""Cog Description"""
import discord
import os
from discord.ext import commands
from discord.ext import tasks


class Polling(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        for guild in self.bot.guilds:
            active_polls = await self.bot.open_json_file(guild, "active_polls.json", dict())
            for poll_id in active_polls:
                poll_settings = active_polls[poll_id]
                poll_view = await create_poll_view(poll_settings)
                print(f"Loaded poll with ID {poll_id}")
                self.bot.add_view(poll_view)

    async def cog_unload(self):
        for guild in self.bot.guilds:
            active_polls = await self.bot.open_json_file(guild, "active_polls.json", dict())
            for poll_id in active_polls:
                poll_settings = active_polls[poll_id]
                poll_view = await create_poll_view(poll_settings)
                poll_view.stop()


    @discord.app_commands.command(
        name="poll",
        description="Create a poll.")
    @discord.app_commands.guild_only()
    @discord.app_commands.describe(poll_name="The full name of the poll i.e. `April Monthly VN Poll`.",
                                   poll_id="Short one-word identifier for the poll i.e. `aprilvn2022`",
                                   vote_count="How many votes should each person have?")
    @discord.app_commands.default_permissions(send_messages=True)
    async def poll(self, interaction: discord.Interaction, poll_name: str, poll_id: str, vote_count: int = 1):
        poll_id = str(interaction.guild.id) + ":" + poll_id

        active_polls = await self.bot.open_json_file(interaction.guild, "active_polls.json", dict())
        if poll_id in active_polls:
            await interaction.response.send_message("Poll ID already in use.", ephemeral=True)
            return

        await send_settings_message(interaction, poll_name, poll_id, vote_count)


async def setup(bot):
    await bot.add_cog(Polling(bot))


async def create_settings_view(poll_settings):
    buttons_view = discord.ui.View(timeout=600)
    buttons_view.add_item(EditOptionsButton(poll_settings))
    buttons_view.add_item(EditAllowedRolesButton(poll_settings))
    buttons_view.add_item(EditRoleWeightsButton(poll_settings))
    buttons_view.add_item(CreatePollButton(poll_settings))
    return buttons_view


async def send_settings_message(interaction: discord.Interaction, poll_name, poll_id, vote_count, options=None,
                                allowed_roles=["@everyone"], role_weights=None):

    settings_embed = discord.Embed(title=poll_name, description=f"Poll with the unique ID: `{poll_id}`")
    if options:
        settings_embed.add_field(name="Vote Options", value="\n".join([f"• {option}" for option in options]),
                                 inline=False)
    else:
        settings_embed.add_field(name="Vote Options", value="No options set up yet.", inline=False)

    settings_embed.add_field(name="Vote Count", value=vote_count)

    role_list = [discord.utils.get(interaction.guild.roles, name=role_name) for role_name in allowed_roles]
    role_list = [role for role in role_list if role]
    if role_list:
        settings_embed.add_field(name="Allowed roles", value="\n".join([f"{role.mention}" for role in role_list]),
                                 inline=False)
    else:
        settings_embed.add_field(name="Allowed roles", value=interaction.guild.default_role.mention, inline=False)

    if role_weights:
        role_weight_strings = []
        for role_name in role_weights:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if not role:
                continue
            role_weight = role_weights[role_name]
            role_weight_strings.append(f"{role.mention} : `{role_weight}`")
        settings_embed.add_field(name="Role weights", value="\n".join(role_weight_strings))

    poll_settings = (poll_name, poll_id, vote_count, options, allowed_roles, role_weights, interaction.user.id)
    buttons_view = await create_settings_view(poll_settings)

    await interaction.response.send_message(embed=settings_embed, view=buttons_view, ephemeral=True,
                                            allowed_mentions=discord.AllowedMentions.none())


# Edit options button
class EditOptionsButton(discord.ui.Button):
    def __init__(self, poll_settings):
        super().__init__(label="Edit Options", style=discord.ButtonStyle.primary)
        self.poll_settings = poll_settings

    async def callback(self, interaction: discord.Interaction):
        poll_name, poll_id, vote_count, options, allowed_roles, role_weights, creator_id = self.poll_settings
        options_modal = EditOptionsModal(self.poll_settings)
        if options:
            options_input = discord.ui.TextInput(label="Enter options separated by new line.",
                                                 default="\n".join(options), style=discord.TextStyle.paragraph)
        else:
            options_input = discord.ui.TextInput(label="Enter options separated by new line",
                                                 style=discord.TextStyle.paragraph)

        options_modal.add_item(options_input)
        await interaction.response.send_modal(options_modal)


# Edit options modal
class EditOptionsModal(discord.ui.Modal):
    def __init__(self, poll_settings):
        super().__init__(title="Options. Max 100 characters/line.")
        self.poll_settings = poll_settings

    async def on_submit(self, interaction: discord.Interaction):
        poll_name, poll_id, vote_count, old_options, allowed_roles, role_weights, creator_id = self.poll_settings
        options_input = self.children[0].value
        new_options = options_input.split("\n")
        new_options = list(set(new_options))
        new_options = [option for option in new_options if option and len(option) <= 100][0:25]
        await send_settings_message(interaction, poll_name, poll_id, vote_count, new_options, allowed_roles,
                                    role_weights)


# Edit allowed roles button
class EditAllowedRolesButton(discord.ui.Button):
    def __init__(self, poll_settings):
        super().__init__(label="Edit Allowed Roles", style=discord.ButtonStyle.primary)
        self.poll_settings = poll_settings

    async def callback(self, interaction: discord.Interaction):
        poll_name, poll_id, vote_count, old_options, allowed_roles, role_weights, creator_id = self.poll_settings
        allowed_roles_modal = EditAllowedRolesModal(self.poll_settings)

        allowed_roles_input = discord.ui.TextInput(label="Enter exact role names separated by new line.",
                                                   default="\n".join(allowed_roles),
                                                   style=discord.TextStyle.paragraph)

        role_name_list = "\n".join([role.name for role in interaction.guild.roles])
        reference__input = discord.ui.TextInput(label="Role reference. Copy from here.",
                                                default=role_name_list,
                                                style=discord.TextStyle.paragraph)

        allowed_roles_modal.add_item(allowed_roles_input)
        allowed_roles_modal.add_item(reference__input)

        await interaction.response.send_modal(allowed_roles_modal)


class EditAllowedRolesModal(discord.ui.Modal):
    def __init__(self, poll_settings):
        super().__init__(title="Allowed roles.")
        self.poll_settings = poll_settings

    async def on_submit(self, interaction: discord.Interaction):
        poll_name, poll_id, vote_count, options, allowed_roles, role_weights, creator_id = self.poll_settings
        allowed_roles_input = self.children[0].value
        new_allowed_roles = allowed_roles_input.split("\n")
        await send_settings_message(interaction, poll_name, poll_id, vote_count, options, new_allowed_roles,
                                    role_weights)


# Edit role weights button
class EditRoleWeightsButton(discord.ui.Button):
    def __init__(self, poll_settings):
        super().__init__(label="Edit Role Weights", style=discord.ButtonStyle.primary)
        self.poll_settings = poll_settings

    async def callback(self, interaction: discord.Interaction):
        poll_name, poll_id, vote_count, old_options, allowed_roles, role_weights, creator_id = self.poll_settings
        role_weights_modal = EditRoleWeightsModal(self.poll_settings)

        if role_weights:
            role_weight_strings = []
            for role_name in role_weights:
                role_weight = role_weights[role_name]
                role_weight_strings.append(f"{role_name}:{role_weight}")

            role_weights_input = discord.ui.TextInput(label="Enter role names & weights with colon.",
                                                      default="\n".join(role_weight_strings),
                                                      style=discord.TextStyle.paragraph)

        else:
            role_weights_input = discord.ui.TextInput(label="Enter role names & weights with colon.",
                                                      style=discord.TextStyle.paragraph)

        reference_role_weight_strings = []
        for role in interaction.guild.roles:
            reference_role_weight_strings.append(f"{role.name}:1.0")

        role_weights_reference_input = discord.ui.TextInput(
            label="Role weight reference. Copy from here.",
            default="\n".join(reference_role_weight_strings),
            style=discord.TextStyle.paragraph)

        role_weights_modal.add_item(role_weights_input)
        role_weights_modal.add_item(role_weights_reference_input)
        await interaction.response.send_modal(role_weights_modal)


class EditRoleWeightsModal(discord.ui.Modal):
    def __init__(self, poll_settings):
        super().__init__(title="Role Weights")
        self.poll_settings = poll_settings

    async def on_submit(self, interaction: discord.Interaction):
        poll_name, poll_id, vote_count, options, allowed_roles, role_weights, creator_id = self.poll_settings
        roles_weight_input = self.children[0].value
        role_weights = dict()
        for input_line in roles_weight_input.splitlines():
            try:
                role_name, weight = input_line.split(":")
                weight = float(weight)
                role_weights[role_name] = weight
            except ValueError:
                continue

        await send_settings_message(interaction, poll_name, poll_id, vote_count, options, allowed_roles, role_weights)


# Create poll button
class CreatePollButton(discord.ui.Button):
    def __init__(self, poll_settings):
        super().__init__(label="Create Poll", style=discord.ButtonStyle.success)
        self.poll_settings = poll_settings

    async def callback(self, interaction: discord.Interaction):
        await send_poll_message(interaction, self.poll_settings)


async def send_poll_message(interaction, poll_settings):
    poll_name, poll_id, vote_count, options, allowed_roles, role_weights, creator_id = poll_settings
    if not options:
        await interaction.response.send_message("You forgot to set up voting options!", ephemeral=True)
        return

    settings_embed = discord.Embed(title=poll_name, description=f"Poll by {interaction.user.mention} with the unique ID: `{poll_id}`")
    settings_embed.add_field(name="Vote Options", value="\n".join([f"• {option}" for option in options]), inline=False)
    settings_embed.add_field(name="Vote Count", value=vote_count)

    role_list = [discord.utils.get(interaction.guild.roles, name=role_name) for role_name in allowed_roles]
    role_list = [role for role in role_list if role]
    if role_list:
        settings_embed.add_field(name="Allowed roles", value="\n".join([f"{role.mention}" for role in role_list]),
                                 inline=False)
    else:
        settings_embed.add_field(name="Allowed roles", value=interaction.guild.default_role.mention, inline=False)

    if role_weights:
        role_weight_strings = []
        for role_name in role_weights:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if not role:
                continue
            role_weight = role_weights[role_name]
            role_weight_strings.append(f"{role.mention} : `{role_weight}`")
        settings_embed.add_field(name="Role weights", value="\n".join(role_weight_strings))

    poll_view = await create_poll_view(poll_settings)

    await interaction.response.send_message(embed=settings_embed,
                                            view=poll_view,
                                            allowed_mentions=discord.AllowedMentions.none())

    active_polls = await interaction.client.open_json_file(interaction.guild, "active_polls.json", dict())
    active_polls[poll_id] = poll_settings
    await interaction.client.write_json_file(interaction.guild, "active_polls.json", active_polls)


# Create poll view
async def create_poll_view(poll_settings):
    poll_name, poll_id, vote_count, options, allowed_roles, role_weights, creator_id = poll_settings
    poll_view = discord.ui.View(timeout=None)
    poll_select = PollSelect(poll_settings)
    for option in options:
        poll_select.add_option(label=option)

    info_button = PollVoteInfoButton(poll_settings)
    end_button = PollEndButton(poll_settings)

    poll_view.add_item(poll_select)
    poll_view.add_item(info_button)
    poll_view.add_item(end_button)
    return poll_view


# Vote Select
class PollSelect(discord.ui.Select):
    def __init__(self, poll_settings):
        poll_name, self.poll_id, vote_count, options, self.allowed_roles, self.role_weights, creator_id = poll_settings
        if vote_count > len(options):
            vote_count = len(options)
        super().__init__(custom_id=self.poll_id + ":select", max_values=vote_count)

    async def callback(self, interaction: discord.Interaction):

        if not await self.vote_allowed(interaction):
            return

        vote_weight = await self.get_vote_weight(interaction)
        await self.register_votes(interaction, vote_weight)

        await interaction.response.send_message(f"Registered your votes! Your vote weight is `{vote_weight}`.",
                                                ephemeral=True)

    async def register_votes(self, interaction: discord.Interaction, vote_weight):
        vote_data = await interaction.client.open_json_file(interaction.guild, f"{self.poll_id}:votes.json", dict())
        votes = list(self.values)
        votes.append(vote_weight)
        vote_data[str(interaction.user.id)] = votes
        await self.edit_message(interaction, vote_data)
        await interaction.client.write_json_file(interaction.guild, f"{self.poll_id}:votes.json", vote_data)

    async def edit_message(self, interaction: discord.Interaction, vote_data):
        poll_message = interaction.message
        poll_embed = poll_message.embeds[0]
        users_voted_field = discord.utils.get(poll_embed.fields, name="Vote Progress")
        if users_voted_field:
            poll_embed.remove_field(-1)
        poll_embed.add_field(name="Vote Progress", value=f"`{len(vote_data)}` users have voted so far.")
        await poll_message.edit(embed=poll_embed, view=self.view)

    async def vote_allowed(self, interaction: discord.Interaction):
        vote_allowed = False
        for role in interaction.user.roles:
            if role.name in self.allowed_roles:
                vote_allowed = True
        if not vote_allowed:
            await interaction.response.send_message("You are not allowed to vote on this poll.", ephemeral=True)
        return vote_allowed

    async def get_vote_weight(self, interaction: discord.Interaction):
        if not self.role_weights:
            return 1.0
        user_role_weights = []
        for role in interaction.user.roles:
            for weight_role_name in self.role_weights:
                if role.name == weight_role_name:
                    weight = self.role_weights[weight_role_name]
                    user_role_weights.append(weight)

        if user_role_weights:
            user_vote_weight = max(user_role_weights)
            return user_vote_weight
        else:
            return 1.0


# Vote Info
class PollVoteInfoButton(discord.ui.Button):
    def __init__(self, poll_settings):
        poll_name, self.poll_id, vote_count, options, allowed_roles, role_weights, self.creator_id = poll_settings
        super().__init__(custom_id=self.poll_id + ":voteinfo", label="Vote Info",
                         style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator_id:
            vote_data = await self.get_user_vote_info(interaction)
            if not vote_data:
                return

            vote_string, vote_weight = vote_data
            await interaction.response.send_message(f"You have voted for: {vote_string}\n"
                                                    f"Your vote weight is `{vote_weight}`",
                                                    ephemeral=True)
        else:
            vote_data_string = await self.get_all_vote_info(interaction)
            await interaction.response.send_message(vote_data_string, ephemeral=True)

    async def get_user_vote_info(self, interaction: discord.Interaction):
        vote_data = await interaction.client.open_json_file(interaction.guild, f"{self.poll_id}:votes.json", dict())
        user_vote_data = vote_data.get(str(interaction.user.id), None)
        if not user_vote_data:
            await interaction.response.send_message("You haven't voted yet.", ephemeral=True)
            return False
        vote_weight = user_vote_data.pop()
        vote_string = ", ".join(user_vote_data)
        return vote_string, vote_weight

    async def get_all_vote_info(self, interaction: discord.Interaction):
        vote_data = await interaction.client.open_json_file(interaction.guild, f"{self.poll_id}:votes.json", dict())
        vote_summary = [f"A total of {len(vote_data)} members voted:\n"]
        for user_id in vote_data:
            member = interaction.guild.get_member(int(user_id))
            if not member:
                member_name = "<UserLeftServer>"
            else:
                member_name = str(member)

            member_vote_data = vote_data[user_id]
            member_vote_weight = member_vote_data.pop()
            member_vote_string = ", ".join(member_vote_data)
            vote_summary.append(
                f"`{member_name}` voted for {member_vote_string} with vote power `{member_vote_weight}`.")

        return "\n".join(vote_summary)


class PollEndButton(discord.ui.Button):
    def __init__(self, poll_settings):
        self.poll_name, self.poll_id, vote_count, options, allowed_roles, role_weights, self.creator_id = poll_settings
        super().__init__(custom_id=self.poll_id + ":end", label="End Poll",
                         style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        delete_permissions = False
        if interaction.user.id == self.creator_id:
            delete_permissions = True
        if interaction.user.guild_permissions.administrator:
            delete_permissions = True
        if not delete_permissions:
            await interaction.response.send_message("You are not allowed to end this poll.",
                                                    ephemeral=True)
            return

        vote_data = await interaction.client.open_json_file(interaction.guild, f"{self.poll_id}:votes.json", dict())
        vote_result = dict()
        vote_summary = [f"A total of {len(vote_data)} members voted:\n"]
        for user_id in vote_data:
            member_vote_data = vote_data[user_id]
            vote_weight = member_vote_data.pop()
            for vote_option in member_vote_data:
                vote_result[vote_option] = vote_result.get(vote_option, 0) + vote_weight

            member = interaction.guild.get_member(int(user_id))
            if not member:
                member_name = "`<UserLeftServer>`"
            else:
                member_name = member.mention

            member_vote_string = ", ".join(member_vote_data)
            vote_summary.append(f"{member_name} voted for {member_vote_string} with vote power `{vote_weight}`.")

        result_embed = discord.Embed(title=f"The poll {self.poll_name} has concluded.",
                                     description="\n".join(vote_summary))
        sorted_options = sorted(vote_result, key=vote_result.get)
        for index, option in enumerate(sorted_options):
            result_embed.add_field(name=f"{index + 1}.", value=f"`{option}` with `{vote_result[option]}` votes.",
                                   inline=False)

        # Stop listening to View.
        self.view.stop()

        # Remove votes data
        os.remove(f"data/{interaction.guild.id}/{self.poll_id}:votes.json")

        # Remove poll from active polls
        active_polls = await interaction.client.open_json_file(interaction.guild, "active_polls.json", dict())
        del active_polls[self.poll_id]
        await interaction.client.write_json_file(interaction.guild, "active_polls.json", active_polls)

        # Edit post
        poll_message = interaction.message
        poll_embed = poll_message.embeds[0]
        poll_embed.add_field(name="Finished", value="The poll has ended.")
        await poll_message.edit(embed=poll_embed, view=None)

        await interaction.response.send_message(embed=result_embed)
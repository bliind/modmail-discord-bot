import discord
import json
import os
import io
import datetime
import db
import re
import jinja2
import math
from discord import app_commands
from ConfirmView import ConfirmView
from ReportView import ReportView
from ReportModal import ReportModal

class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

def load_config():
    global config
    config_file = 'config.json' if env == 'prod' else 'config.test.json'
    with open(config_file, encoding='utf8') as stream:
        config = json.load(stream)
    config = dotdict(config)

env = os.getenv('MODMAIL_ENV')
load_config()

class HTMLTemplate:
    def __init__(self):
        loader = jinja2.FileSystemLoader(searchpath="./")
        self.env = jinja2.Environment(loader=loader, autoescape=False)
        self.template = self.env.get_template('template2.html.j2')
htmlTemplate = HTMLTemplate()

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.synced = False

    async def on_ready(self):
        if not self.synced:
            await tree.sync(guild=discord.Object(id=config.server))
            self.synced = True
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="your complaints!"))

        print(f"{config.env.upper()} Modmail is ready for duty")

        self.server = [g for g in self.guilds if g.id == config.server][0]
        for role in self.server.roles:
            if role.name == config.mod_role:
                self.mod_role = role
                break

class ModmailCommands:
    async def cmd_reply(self, message):
        ticket = db.get_ticket_by_channel(message.channel.id)
        if not ticket or ticket['active'] != 1:
            return

        firstword = message.content.split(' ')[0]
        content = message.content.replace(firstword, '')
        embed = make_outgoing_embed(message.author, content)
        embed.color = discord.Color.green()
        user = bot.get_user(ticket['user_id'])
        files = await get_attachments(message)
        try:
            sent = await user.send(embed=embed, files=files)
        except:
            await message.reply('Could not DM User')
            return
        newfiles = await get_attachments(sent)
        await message.channel.send(embed=embed, files=newfiles)
        await message.delete()

    async def cmd_areply(self, message):
        ticket = db.get_ticket_by_channel(message.channel.id)
        if not ticket or ticket['active'] != 1:
            return

        firstword = message.content.split(' ')[0]
        content = message.content.replace(firstword, '')
        outgoing = make_outgoing_embed(bot.user, content, anonymous=True)
        internal = make_internal_embed(message.author, content, anonymous=True)
        user = bot.get_user(ticket['user_id'])
        files = await get_attachments(message)
        try:
            sent = await user.send(embed=outgoing, files=files)
        except:
            await message.reply('Could not DM User')
            return
        newfiles = await get_attachments(sent)
        await message.channel.send(embed=internal, files=newfiles)
        await message.delete()

    async def cmd_close(self, message):
        ticket = db.get_ticket_by_channel(message.channel.id)
        if not ticket or ticket['active'] != 1:
            return

        split = message.content.split(' ')
        content = message.content.replace(split[0], '')
        user = bot.get_user(ticket['user_id'])
        try: keyword = split[1]
        except:
            await message.reply("Can't do! _(need a close message)_")
            return

        if keyword != 'silently':
            ticket_chan = bot.get_channel(ticket['channel_id'])
            embed = make_info_embed('Thread closed', content)
            files = await get_attachments(message)
            sent = False
            try:
                sent = await user.send(embed=embed, files=files)
            except:
                embed.description += '\n\n_Could not DM user_'
            if sent: files = await get_attachments(sent)
            await ticket_chan.send(embed=embed, files=files)

        # pull all messages, log to html
        await save_channel_log(user, message.channel)

        # delete ticket channel
        await message.channel.delete()

        # delete ticket row in db
        db.close_ticket(ticket['id'])

    async def cmd_closes(self, message):
        ticket = db.get_ticket_by_channel(message.channel.id)
        if not ticket or ticket['active'] != 1:
            return

        # pull all messages, log to html
        user = bot.get_user(ticket['user_id'])
        await save_channel_log(user, message.channel)

        # delete ticket channel
        await message.channel.delete()

        # delete ticket row in db
        db.close_ticket(ticket['id'])

    async def cmd_contact(self, message):
        try: user_id = int(message.content.split(' ')[1])
        except:
            await message.reply('=contact UserID')

        ticket = db.get_ticket(user_id)
        if ticket:
            await message.reply(f'User has open ticket already: <#{ticket["channel_id"]}>')
            return

        user = bot.get_user(user_id)
        new_message = dotdict({
            "author": user,
            "content": "",
            "id": 0,
            "attachments": []
        })
        channel_id = await create_ticket(new_message)
        await message.reply(f'Ticket opened: <#{channel_id}>')
        remainder = ' '.join(message.content.split(' ')[2:])
        if remainder:
            chan = bot.get_channel(channel_id)
            intemb = make_internal_embed(message.author, remainder, anonymous=True)
            await chan.send(embed=intemb)
            outemb = make_outgoing_embed(bot.user, remainder, anonymous=True)
            try:
                await user.send(embed=outemb)
            except:
                failemb = make_embed('red')
                failemb.description = 'Failed to DM user'
                await chan.send(embed=failemb)

    async def cmd_block(self, message):
        try:
            user_id = message.content.split(' ')[1]
            reason = ' '.join(message.content.split(' ')[2:])
        except:
            await message.reply('=block UserID Reason')
            return

        user = bot.get_user(int(user_id))
        if db.add_block(user.id, user.name, message.author.id, reason):
            await message.reply(f'{user.name} ({user.id}) added to block list')

    async def cmd_unblock(self, message):
        try:
            user_id = message.content.split(' ')[1]
        except:
            await message.reply('=unblock UserID')

        if db.delete_block(user_id):
            await message.reply(f'{user_id} unblocked')

    async def cmd_blocks(self, message):
        blocks = db.list_blocks()
        embed = make_info_embed('Blocked Users', '')

        for block in blocks:
            embed.description += f'<@{block["user_id"]}> ({block["user_name"]})\n'
            embed.description += f'_blocked by <@{block["moderator_id"]}> for {block["reason"]}_\n\n'

        await message.reply(embed=embed)

    async def cmd_sub(self, message):
        ticket = db.get_ticket_by_channel(message.channel.id)
        if not ticket or ticket['active'] != 1:
            return

        if db.add_sub(ticket['id'], message.author.id):
            await message.reply('You will now be pinged for replies to this thread.')
        else:
            await message.reply('Failed')

bot = MyClient()
tree = app_commands.CommandTree(bot)
commands = ModmailCommands()

def check_is_allowed(member):
    try:
        role_names = [y.name for y in member.roles]
        for role in role_names:
            if role in config.allowed_roles:
                return True
    except:
        pass

    return False

def get_member_image(member):
    try:
        if member.guild_avatar:
            return member.guild_avatar.url
    except: pass
    try:
        if member.display_avatar:
            return member.display_avatar.url
    except: pass
    try:
        return member.avatar.url
    except:
        return None

def clean_name(name):
    return name.replace('`', '\\`').replace('_', '\\_').replace('*', '\\*')

def get_member_name(member):
    try: 
        if member.nick: return member.nick
    except: pass
    try:
        if member.display_name: return member.display_name
    except: pass
    try:
        if member.global_name: return member.global_name
    except: pass

    return member.name

def make_embed(color, **kwargs):
    return discord.Embed(
        color=getattr(discord.Color, color)(),
        timestamp=datetime.datetime.now(),
        **kwargs
    )

# internal embeds, for use in the ticket channel
def make_internal_embed(member, description, anonymous=False):
    embed = make_embed('blue', description=description)
    embed.set_author(name=get_member_name(member), icon_url=get_member_image(member))
    embed.set_footer(text='Anonymous Reply')
    if not anonymous:
        mod = bot.server.get_member(member.id)
        embed.set_footer(text=f'{mod.roles[-1].name}')

    return embed

# embeds from mods to user DM
def make_outgoing_embed(member, description, anonymous=False):
    embed = make_embed('yellow', description=description)
    embed.set_author(name='SNAP Modmail', icon_url=bot.server.icon.url)
    embed.set_footer(text='Response')
    if not anonymous:
        embed.set_author(name=get_member_name(member), icon_url=get_member_image(member))
        mod = bot.server.get_member(member.id)
        embed.set_footer(text=f'{mod.roles[-1].name}')

    return embed

# info embeds to user DM
def make_info_embed(title, description):
    embed = make_embed('blurple', title=title, description=description)
    embed.set_author(name='SNAP Modmail', icon_url=bot.server.icon.url)
    embed.set_footer(text='Info')

    return embed

# incoming embeds from user
def make_incoming_embed(member, description, message_id):
    embed = make_embed('yellow', description=description)
    embed.set_author(name=get_member_name(member), icon_url=get_member_image(member))
    embed.set_footer(text=f'Message ID: {message_id}')

    return embed

# embed for the opening of the ticket
def make_opener_embed(member, description):
    embed = make_embed('teal', description=description)
    embed.set_author(name=get_member_name(member), icon_url=get_member_image(member))
    embed.set_footer(text=f'User ID: {member.id}')

    return embed

def timestamp():
    now = datetime.datetime.now()
    return int(round(now.timestamp()))

async def create_ticket_channel(user_name):
    server = [g for g in bot.guilds if g.id == config.server][0]
    overwrites = {
        server.default_role: discord.PermissionOverwrite(read_messages=False),
        server.get_role(bot.mod_role.id): discord.PermissionOverwrite(read_messages=True)
    }

    category = [c for c in server.categories if c.id == config.category_id][0]
    channel = await category.create_text_channel(user_name, overwrites=overwrites)

    return channel.id

async def confirm_modmail_creation(message):
    confirm_embed = make_info_embed('', '''
        ### Hello and thanks for contacting the SNAP Modmail!

        This Modmail system is for contacting the Discord Moderators for Discord-based issues. We cannot help with game support issues.
        Please confirm you would still like to contact the moderation team
    '''.replace(' '*8, '').strip())
    confirm_view = ConfirmView(timeout=30)
    confirm_msg = await message.channel.send(embed=confirm_embed, view=confirm_view)
    await confirm_view.wait()
    await confirm_msg.edit(embed=confirm_embed, view=confirm_view)
    if confirm_view.value:
        # yes was picked, create ticket
        await create_ticket(message)
        # reply to user
        reply = make_info_embed(
            'Confirmed!',
            'Your message has been sent to the Moderators! We will be with you momentarily.\n\nAt any time you can react with 🚪 to close the Modmail.'
        )
        sent = await message.channel.send(embed=reply)
        await sent.add_reaction('🚪')

async def create_ticket(message):
    # create the channel
    channel_id = await create_ticket_channel(message.author.name)
    # initial message to channel
    modmail_open = await make_initial_user_embed(message.author)
    channel = bot.get_channel(channel_id)
    await channel.send('@here', embed=modmail_open)
    if message.id != 0:
        initial_message = make_incoming_embed(message.author, message.content, message.id)
        files = await get_attachments(message)
        await channel.send(embed=initial_message, files=files)
    # create db entry
    db.create_ticket(message.author.id, message.author.name, channel_id, timestamp())

    return channel_id

async def make_initial_user_embed(user):
    created = int(round(user.created_at.timestamp()))
    count = db.get_ticket_count(user.id)

    member = bot.server.get_member(user.id)
    if member:
        joined = int(round(member.joined_at.timestamp()))
        description = f'{member.mention} was created <t:{created}:R>, joined <t:{joined}:R>, with {count} past threads.\n\n'
        description += '**Roles**\n'
        for role in member.roles:
            description += f'{role.mention} '
    else:
        description = f'{member.mention} was created <t:{created}:R>, is not on the server, with {count} past threads.\n\n'

    embed = make_opener_embed(user, description)
    embed.set_footer(text=f'User ID: {user.id}')

    return embed

async def save_channel_log(user, channel):
    messages = [m async for m in channel.history(oldest_first=True)]
    output = htmlTemplate.template.render(user=user, messages=messages, bot_id=bot.user.id)
    cleaned_output = re.sub(r'^\s+$\n', '', output, flags=re.MULTILINE)
    filename = f'{user.name}-{timestamp()}.html'
    with open(f'./logs/{filename}', 'w+', encoding="utf-8") as f:
        f.write(cleaned_output)

    # log it
    link = f'https://sween.me/modmail/{filename}'
    if config.env == 'test':
        link = f'http://localhost:8080/{filename}'
    try:
        first_msg = messages[1].embeds[0].description[:59]
    except:
        first_msg = 'Modmail log'
    closer = messages[-1].author
    if closer.id == bot.user.id:
        closer = dotdict({"name": "Recipient", "id": user.id})

    log = make_info_embed(
        f'{user.name} (`{user.id}`)',
        f'[Web Log]({link}): {first_msg}'
    )
    log.set_footer(text=f'Closed by {closer.name} ({closer.id})')
    log_chan = bot.get_channel(config.ticket_log_id)
    await log_chan.send(embed=log)

async def get_attachments(message):
    files = []
    for file in message.attachments:
        with io.BytesIO() as image_binary:
            await file.save(image_binary)
            image_binary.seek(0)
            files.append(discord.File(
                image_binary,
                filename=file.filename,
                spoiler=file.is_spoiler()
            ))

    return files

@bot.event
async def on_message(message):
    if message.author != bot.user:
        if isinstance(message.channel, discord.DMChannel):
            # check if blocked
            if db.is_blocked(message.author.id):
                return
            # check for existing modmail ticket
            tickets = db.get_tickets(message.author.id)
            ticket = [t for t in tickets if t['active'] == 1]
            if ticket:
                channel_id = ticket[0]['channel_id']
            else:
                try:
                    last_ticket_time = datetime.datetime.fromtimestamp(tickets[-1]['datestamp'])
                    diff = datetime.datetime.now() - last_ticket_time
                    # check cooldown
                    if diff.total_seconds() < config.cooldown:
                        remain = config.cooldown - diff.total_seconds()
                        minutes = math.floor(remain / 60)
                        seconds = math.ceil(remain - (minutes*60))
                        timestring = ''
                        if minutes:
                            timestring += f'{minutes} minute{"s" if minutes > 1 else ""}'
                        if minutes and seconds: timestring += ', '
                        if seconds:
                            timestring += f'{seconds} second{"s" if seconds > 1 else ""}'
                        cd_embed = make_info_embed(
                            'Modmail Cooldown',
                            f'You\'ve recently had a modmail. You can open a new one in {timestring}'
                        )
                        await message.channel.send(embed=cd_embed)
                        return
                    else:
                        channel_id = await confirm_modmail_creation(message)
                except:
                    channel_id = await confirm_modmail_creation(message)

            if not channel_id: return

            # post message to ticket
            channel = bot.get_channel(channel_id)
            embed = make_incoming_embed(message.author, message.content, message.id)
            files = await get_attachments(message)
            subs = db.get_subs(ticket[0]['id'])
            pings = [f'<@{s["sub_id"]}>' for s in subs]
            if pings:
                await channel.send(' '.join(pings))
            await channel.send(embed=embed, files=files)

        # if isinstance(message.channel, discord.TextChannel):
        else:
            if not check_is_allowed(message.author):
                return
            firstword = message.content.split(' ')[0]
            if firstword.startswith('='):
                command = f'cmd_{firstword.replace("=", "")}'
                try:
                    await getattr(commands, command)(message)
                except AttributeError:
                    await message.reply(f'Unknown command: {firstword}')
                    return
                except Exception as e:
                    print(e)
                    return

@bot.event
async def on_raw_member_remove(event):
    ticket = db.get_ticket(event.user.id)
    if ticket:
        embed = make_info_embed('User left', f'{event.user.mention} has left the server')
        embed.remove_author()
        channel = bot.get_channel(ticket['channel_id'])
        await channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    ticket = db.get_ticket(member.id)
    if ticket:
        embed = make_info_embed('User joined', f'{member.mention} has joined the server')
        embed.remove_author()
        channel = bot.get_channel(ticket['channel_id'])
        await channel.send(embed=embed)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    if payload.guild_id:
        return

    ticket = db.get_ticket(payload.user_id)
    if not ticket:
        print(f'No ticket for f<@{payload.user_id}>')
        return

    user = bot.get_user(ticket['user_id'])
    chan = bot.get_channel(ticket['channel_id'])
    if payload.emoji.name == '🚪':
        # close ticket
        last_msg = make_info_embed('Thread closed', 'Closed by recipient')
        await chan.send(embed=last_msg)
        user_msg = make_info_embed('Thread closed', 'Thanks for reaching out the Modmail!')
        await user.send(embed=user_msg)
        # pull all messages, log to html
        await save_channel_log(user, chan)

        # delete ticket channel
        await chan.delete()

        # delete ticket row in db
        db.close_ticket(ticket['id'])

@bot.event
async def on_message_edit(before, after):
    if not isinstance(after.channel, discord.DMChannel):
        return
    if after.author.bot:
        return
    if before.content.strip() == after.content.strip():
        return
    ticket = db.get_ticket(after.author.id)
    if not ticket:
        return

    chan = bot.get_channel(ticket['channel_id'])
    async for msg in chan.history():
        try:
            if msg.embeds[0].description.strip() == before.content.strip():
                edited = msg.embeds[0].copy()
                edited.description += f'\n\n--------\n_Edited, new message_:\n\n{after.content}'
                await msg.edit(embed=edited)
                break
        except:
            continue

@tree.context_menu(name='Report Message', guild=discord.Object(id=config.server))
async def report_message_command(interaction, message: discord.Message):
    modal = ReportModal()
    await interaction.response.send_modal(modal)
    await modal.wait()
    description = f'{interaction.user.mention} ({interaction.user.name}) '
    description += f'has reported [this message]({message.jump_url}) from '
    description += f'{message.author.mention} ({message.author.name})!'

    try:
        joined_at = f'<t:{int(round(message.author.joined_at.timestamp()))}>'
    except:
        joined_at = 'No Longer On Server'

    description += f'''\n
        **Reported User's Info:**
        Discord Tag: `{clean_name(message.author.name)}`
        Discord ID: `{message.author.id}`
        Account Created: <t:{int(round(message.author.created_at.timestamp()))}>
        Joined Server: {joined_at}
    '''.replace(' '*8, '')

    description += f'''
        **Reported Message's Info:**
        Message ID: `{message.id}`
        Channel: <#{message.channel.id}>
        Created: <t:{int(round(message.created_at.timestamp()))}>
        Attachments: `{len(message.attachments)}`
        Reactions: `{len(message.reactions)}`
        Content: `{message.content}`
    '''.replace(' '*8, '')

    description += f'''
        **Report Reason:**
        `{modal.reason.value}`
    '''.replace(' '*8, '')

    embed = discord.Embed(
        color=discord.Color.light_gray(),
        description=description,
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name='Message Report Received', icon_url=get_member_image(interaction.user))
    embed.set_thumbnail(url=get_member_image(message.author))

    report_chan = bot.get_channel(config.report_channel_id)
    report_view = ReportView(url=message.jump_url, timeout=None)
    report_message = await report_chan.send(bot.mod_role.mention, embed=embed, view=report_view)
    await report_view.wait()
    if report_view.value:
        u = report_view.buttonpusher
        embed.description += f'\n\n✅ {u.mention} ({u.name}) is handling this'
        embed.color = discord.Color.green()
    elif report_view.value == False:
        u = report_view.buttonpusher
        embed.description += f'\n\n❌ {u.mention} ({u.name}) marked this a false report'
        embed.color = discord.Color.red()
    await report_message.edit(embed=embed, view=report_view)

bot.run(config.token)

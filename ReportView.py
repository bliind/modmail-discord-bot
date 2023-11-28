import discord

class ReportView(discord.ui.View):
    def __init__(self, url, timeout):
        super().__init__(timeout=timeout)
        self.value = None
        self.buttonpusher = None
        jump_button = discord.ui.Button(label='Jump to Message', style=discord.ButtonStyle.gray, url=url)
        self.add_item(jump_button)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label='Handle', style=discord.ButtonStyle.green)
    async def handle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = True
        self.buttonpusher = interaction.user
        await self.on_timeout()
        self.stop()

    @discord.ui.button(label='False Report', style=discord.ButtonStyle.red)
    async def falsereport(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.value = False
        self.buttonpusher = interaction.user
        await self.on_timeout()
        self.stop()

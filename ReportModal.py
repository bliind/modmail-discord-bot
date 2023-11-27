import discord
from discord import ui

class ReportModal(ui.Modal, title="Report Message"):
    reason = ui.TextInput(label='Reason for Report')

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message('Your report has been sent to the moderators, thank you!', ephemeral=True)

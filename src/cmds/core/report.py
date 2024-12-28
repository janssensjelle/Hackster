import asyncio
import logging
import re
from datetime import datetime

import discord
from discord import ApplicationContext, Option, slash_command
from discord.ext import commands
from discord.ext.commands import cooldown

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)


def sanitize_message(message: str) -> str:
    """Sanitize message content to prevent @everyone and similar mentions."""
    # Replace @everyone with [at everyone]
    message = re.sub(r'@everyone', '[at everyone]', message, flags=re.IGNORECASE)
    # Also handle @here as it has similar functionality
    message = re.sub(r'@here', '[at here]', message, flags=re.IGNORECASE)
    return message


class ReportCog(commands.Cog):
    """Cog for handling reports with the possibility to have a user upload multiple images."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(
        guild_ids=settings.guild_ids,
        description="Report an issue to the moderators. You will be prompted to provide images in a DM."
    )
    @cooldown(1, 10, commands.BucketType.user)
    async def report(
        self,
        ctx: ApplicationContext,
        message: Option(str, "What do you want to report?", required=True),
        user: Option(discord.Member, "Who do you want to report?", required=False),
    ) -> None:
        """Allows users to report an issue with a description and prompts them to provide multiple images via DM."""
        # Sanitize the message to prevent mentions of @everyone and @here
        sanitized_message = sanitize_message(message)

        # Defer the response to allow time for processing
        await ctx.defer(ephemeral=True)

        # Get the moderator channel from settings
        mod_channel = discord.utils.get(ctx.guild.channels, id=settings.channels.REPORTS)

        if not mod_channel:
            await ctx.respond(
                "❌ Unable to process report: Moderator channel not found. Please notify an admin.",
                ephemeral=True
            )
            return

        # Notify the user that the bot will DM them
        await ctx.respond(
            "📨 I'll send you a DM to collect any images for your report.",
            ephemeral=True
        )

        # Send a DM to the user
        try:
            dm_channel = await ctx.author.create_dm()
            await dm_channel.send(
                "📎 **Please send the images for your report**\n\n"
                "• Send your images as attachments\n"
                "• Supported formats: PNG, JPG, JPEG, GIF\n"
                "• Type `done` when you've finished\n"
                "• Or wait 60 seconds to submit without more images"
            )

            images = []

            def check(msg: discord.Message) -> bool:
                """Check if the message is from the user and contains attachments or 'done'."""
                return (
                    msg.author == ctx.author
                    and msg.channel == dm_channel
                    and (
                        len(msg.attachments) > 0 or msg.content.lower() == "done"
                    )
                )

            while True:
                try:
                    # Wait for the user's response in DM
                    msg = await self.bot.wait_for("message", timeout=60.0, check=check)

                    if msg.content.lower() == "done":
                        break

                    # Validate and collect the attachments
                    valid_images = [
                        attachment
                        for attachment in msg.attachments
                        if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'gif'])
                    ]

                    if not valid_images and msg.attachments:
                        await dm_channel.send(
                            "⚠️ Invalid file format! Please only send PNG, JPG, JPEG, or GIF images."
                        )
                        continue

                    images.extend(valid_images)
                    await dm_channel.send(
                        f"✅ Received {len(valid_images)} image{'s' if len(valid_images) != 1 else ''}. "
                        "Send more or type `done` to finish."
                    )

                except asyncio.TimeoutError:
                    if images:
                        await dm_channel.send(
                            "⏰ Time's up! I'll proceed with the images you've already sent."
                        )
                    break

            # Prepare the embed
            embed = discord.Embed(
                title="📢 New Report",
                description=f"From {ctx.author.mention}",
                color=discord.Color.yellow(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="📝 Content", value=sanitized_message, inline=False)
            if user:
                embed.add_field(
                    name="User reported",
                    value=f"{user.mention} ({user.id})",
                    inline=False
                )
            if images:
                embed.add_field(
                    name="📎 Attachments",
                    value=f"{len(images)} image{'s' if len(images) != 1 else ''} attached",
                    inline=False
                )
            embed.set_footer(text=f"Reporter ID: {ctx.author.id}")

            # Send the embed first
            await mod_channel.send(embed=embed)

            # If images are provided, send them in a second message
            if images:
                files = [await img.to_file() for img in images]
                await mod_channel.send(files=files)

            await dm_channel.send(
                "✅ Your report has been sent to the moderators!\n"
                + (f"📎 Included {len(images)} image{'s' if len(images) != 1 else ''}" if images else "")
            )

        except discord.Forbidden:
            await ctx.respond(
                "❌ I couldn't send you a DM. Please check your privacy settings and try again.",
                ephemeral=True
            )
            return
        except Exception as e:
            logger.error(f"Error processing report from {ctx.author.id}: {str(e)}", exc_info=True)
            await ctx.respond(
                "❌ An error occurred while processing your report. Please try again later.",
                ephemeral=True
            )


def setup(bot: Bot) -> None:
    """Load the cogs."""
    bot.add_cog(ReportCog(bot))

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import ApplicationContext, Attachment, DMChannel, Member, Message

from src.bot import Bot
from src.core import settings


class TestReportCog:
    """Test cases for the ReportCog class."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        mock_bot = MagicMock(spec=Bot)
        mock_bot.wait_for = AsyncMock()
        mock_bot.add_cog = MagicMock()
        return mock_bot

    @pytest.fixture
    def dm_channel(self):
        """Create a mock DM channel."""
        channel = MagicMock(spec=DMChannel)
        channel.send = AsyncMock()
        return channel

    @pytest.fixture
    def mod_channel(self):
        """Create a mock reporting channel."""
        channel = MagicMock()
        channel.id = settings.channels.REPORTS
        channel.send = AsyncMock()
        return channel

    @pytest.fixture
    def ctx(self, dm_channel, mod_channel):
        """Create a mock ApplicationContext with all necessary attributes."""
        ctx = MagicMock(spec=ApplicationContext)
        ctx.defer = AsyncMock()
        ctx.respond = AsyncMock()

        # Mock author
        ctx.author = MagicMock(spec=Member)
        ctx.author.create_dm = AsyncMock(return_value=dm_channel)
        ctx.author.mention = "@TestUser"
        ctx.author.id = 12345

        # Mock guild and channel
        ctx.guild = MagicMock()
        ctx.channel = MagicMock()
        ctx.channel.mention = "#test-channel"
        ctx.channel.id = 67890

        def mock_get(channels, id):
            if id == settings.channels.REPORTS:
                return mod_channel
            return None

        with patch('discord.utils.get', side_effect=mock_get):
            yield ctx

    @pytest.fixture
    def cog(self, mock_bot):
        """Create ReportCog instance."""
        from src.cmds.core.report import ReportCog
        return ReportCog(mock_bot)

    @staticmethod
    def create_mock_message(author, channel, content="", attachments=None):
        msg = MagicMock(spec=Message)
        msg.author = author
        msg.channel = channel
        msg.content = content.lower() if content else ""
        msg.attachments = attachments or []
        return msg

    @staticmethod
    def create_mock_attachment(filename: str, size: int = 1024 * 1024) -> MagicMock:
        attachment = MagicMock(spec=Attachment)
        attachment.filename = filename
        attachment.size = size
        attachment.to_file = AsyncMock(return_value=MagicMock(filename=filename))
        return attachment

    @pytest.mark.asyncio
    async def test_report_basic_no_images(self, cog, ctx, dm_channel, mod_channel):
        """Test basic report functionality without any images."""
        # Setup message sequence
        done_message = self.create_mock_message(ctx.author, dm_channel, content="done")
        cog.bot.wait_for.side_effect = [done_message]

        # Execute
        await cog.report.callback(cog, ctx, message="Test report")

        # Verify initial responses
        ctx.defer.assert_called_once_with(ephemeral=True)

        # Verify DM notification
        ctx.respond.assert_any_call(
            "📨 I'll send you a DM to collect any images for your report.",
            ephemeral=True
        )

        # Verify embed was sent
        mod_channel.send.assert_called_once()
        _, kwargs = mod_channel.send.call_args
        embed = kwargs['embed']
        assert embed.title == "📢 New Report"
        assert ctx.author.mention in embed.description
        assert embed.fields[0].name == "📝 Content"
        assert embed.fields[0].value == "Test report"

    @pytest.mark.asyncio
    async def test_report_with_valid_images(self, cog, ctx, dm_channel, mod_channel):
        """Test report submission with valid images."""
        # Create mock attachments
        valid_attachments = [
            self.create_mock_attachment("test1.png"),
            self.create_mock_attachment("test2.jpg")
        ]

        # Setup message sequence
        image_message = self.create_mock_message(ctx.author, dm_channel, attachments=valid_attachments)
        done_message = self.create_mock_message(ctx.author, dm_channel, content="done")
        cog.bot.wait_for.side_effect = [image_message, done_message]

        # Execute
        await cog.report.callback(cog, ctx, message="Test report with images")

        # Verify
        assert mod_channel.send.call_count == 2  # One for embed, one for images

        # Check embed
        embed_call = mod_channel.send.call_args_list[0]
        _, embed_kwargs = embed_call
        embed = embed_kwargs['embed']
        assert embed.fields[1].name == "📎 Attachments"
        assert embed.fields[1].value == "2 images attached"

        # Check images
        image_call = mod_channel.send.call_args_list[1]
        _, image_kwargs = image_call
        assert len(image_kwargs['files']) == 2

    @pytest.mark.asyncio
    async def test_report_invalid_file_types(self, cog, ctx, dm_channel, mod_channel):
        """Test report with invalid file types."""
        invalid_attachments = [
            self.create_mock_attachment("test.txt"),
            self.create_mock_attachment("test.pdf"),
            self.create_mock_attachment("test.doc")
        ]

        invalid_message = self.create_mock_message(ctx.author, dm_channel, attachments=invalid_attachments)
        done_message = self.create_mock_message(ctx.author, dm_channel, content="done")
        cog.bot.wait_for.side_effect = [invalid_message, done_message]

        await cog.report.callback(cog, ctx, message="Test report with invalid files")

        # Verify warning message sent via DM
        dm_channel.send.assert_any_call(
            "⚠️ Invalid file format! Please only send PNG, JPG, JPEG, or GIF images."
        )

        # Verify success message sent via DM
        dm_channel.send.assert_called_with(
            "✅ Your report has been sent to the moderators!\n"
        )

        # Verify only embed was sent, no files
        mod_channel.send.assert_called_once()
        _, kwargs = mod_channel.send.call_args
        embed = kwargs['embed']
        assert "Test report with invalid files" in embed.fields[0].value
        assert 'files' not in kwargs

    @pytest.mark.asyncio
    async def test_report_mixed_file_types(self, cog, ctx, dm_channel, mod_channel):
        """Test report with mix of valid and invalid file types."""
        mixed_attachments = [
            self.create_mock_attachment("valid.png"),
            self.create_mock_attachment("invalid.txt"),
            self.create_mock_attachment("valid.jpg")
        ]

        mixed_message = self.create_mock_message(ctx.author, dm_channel, attachments=mixed_attachments)
        done_message = self.create_mock_message(ctx.author, dm_channel, content="done")
        cog.bot.wait_for.side_effect = [mixed_message, done_message]

        await cog.report.callback(cog, ctx, message="Test report with mixed files")

        # Verify only valid images were sent
        assert mod_channel.send.call_count == 2

        embed_call, image_call = mod_channel.send.call_args_list
        _, embed_kwargs = embed_call
        _, image_kwargs = image_call

        embed = embed_kwargs['embed']
        assert embed.fields[1].value == "2 images attached"

        assert len(image_kwargs['files']) == 2

    def test_setup(self, mock_bot):
        """Test the setup function."""
        from src.cmds.core.report import ReportCog, setup

        setup(mock_bot)

        mock_bot.add_cog.assert_called_once()
        cog = mock_bot.add_cog.call_args[0][0]
        assert isinstance(cog, ReportCog)


    @pytest.mark.asyncio
    async def test_report_no_mod_channel(self, cog, ctx):
        """Test report when moderator channel is not found."""
        with patch('discord.utils.get', return_value=None):
            await cog.report.callback(cog, ctx, message="Test report")

        ctx.respond.assert_called_with(
            "❌ Unable to process report: Moderator channel not found. Please notify an admin.",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_report_dm_forbidden(self, cog, ctx):
        """Test report when bot is unable to send DM to the user."""
        ctx.author.create_dm.side_effect = discord.Forbidden(MagicMock(), "Cannot send messages to this user")

        await cog.report.callback(cog, ctx, message="Test report")

        ctx.respond.assert_called_with(
            "❌ I couldn't send you a DM. Please check your privacy settings and try again.",
            ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_report_unexpected_error(self, cog, ctx):
        """Test report when an unexpected error occurs."""
        ctx.author.create_dm.side_effect = Exception("Unexpected error")

        await cog.report.callback(cog, ctx, message="Test report")

        ctx.respond.assert_called_with(
            "❌ An error occurred while processing your report. Please try again later.",
            ephemeral=True
        )

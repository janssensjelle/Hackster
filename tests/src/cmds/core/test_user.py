from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.cmds.core import user
from tests import helpers


class TestUserCog:
    """Test the `User` cog."""

    @pytest.mark.asyncio
    async def test_kick_success(self, ctx, guild, bot, session):
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user_to_kick = helpers.MockMember(id=2, name="User to Kick", bot=False)
        ctx.guild = guild
        ctx.guild.kick = AsyncMock()
        bot.get_member_or_user = AsyncMock(return_value=user_to_kick)

        # Mock the DM channel
        user_to_kick.send = AsyncMock()
        user_to_kick.name = "User to Kick"

        with (
            patch('src.cmds.core.user.add_infraction', new_callable=AsyncMock) as add_infraction_mock,
            patch('src.cmds.core.user.member_is_staff', return_value=False)
        ):
            cog = user.UserCog(bot)
            await cog.kick.callback(cog, ctx, user_to_kick, "Violation of rules")

            reason = "Violation of rules"
            add_infraction_mock.assert_called_once_with(
                ctx.guild, user_to_kick, 0, f"{ctx.user.name} was kicked on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} for {reason} - Evidence: None", ctx.user
            )

            # Assertions
            ctx.guild.kick.assert_called_once_with(user=user_to_kick, reason="Violation of rules")
            ctx.respond.assert_called_once_with("User to Kick got the boot!")

    @pytest.mark.asyncio
    async def test_kick_fail_user_left(self, ctx, guild, bot, session):
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user_to_kick = helpers.MockMember(id=2, name="User to Kick", bot=False)
        ctx.guild = guild
        ctx.guild.kick = AsyncMock()
        bot.get_member_or_user = AsyncMock(return_value=None)

        # Ensure the member_is_staff mock doesn't block execution
        with patch('src.cmds.core.user.member_is_staff', return_value=False):
            cog = user.UserCog(bot)
            await cog.kick.callback(cog, ctx, user_to_kick, "Violation of rules")

            # Assertions
            bot.get_member_or_user.assert_called_once_with(ctx.guild, user_to_kick.id)
            ctx.guild.kick.assert_not_called()  # No kick should occur
            ctx.respond.assert_called_once_with("User seems to have already left the server.")


    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        user.setup(bot)

        bot.add_cog.assert_called_once()

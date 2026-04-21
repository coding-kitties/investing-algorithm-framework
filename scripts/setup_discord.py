"""
Discord channel layout setup script for the
investing-algorithm-framework community server.

Usage:
    export DISCORD_BOT_TOKEN="your-bot-token"
    export DISCORD_GUILD_ID="your-guild-id"
    python scripts/setup_discord.py

Requires: pip install discord.py

Bot invite URL (replace CLIENT_ID with your Application ID):
    https://discord.com/oauth2/authorize?client_id=CLIENT_ID&permissions=268435536&scope=bot
"""

import os
import asyncio
from dotenv import load_dotenv
import discord
load_dotenv()
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])

# Channel layout: list of (category_name, channels)
# Each channel is (name, type, topic)
CHANNEL_LAYOUT = [
    (
        "━━ INFO ━━",
        [
            (
                "👋・welcome",
                discord.ChannelType.text,
                "Start here! Learn about the community and how to get involved.",
            ),
            (
                "📜・rules",
                discord.ChannelType.text,
                "Community guidelines — please read before posting.",
            ),
            (
                "📢・announcements",
                discord.ChannelType.text,
                "Official releases, updates, and important news.",
            ),
            (
                "🗺️・roadmap",
                discord.ChannelType.text,
                "Framework roadmap and upcoming features.",
            ),
        ],
    ),
    (
        "━━ COMMUNITY ━━",
        [
            (
                "💬・general",
                discord.ChannelType.text,
                "Hang out and chat about anything algo trading related.",
            ),
            (
                "🙋・introductions",
                discord.ChannelType.text,
                "New here? Introduce yourself and tell us what you're building.",
            ),
            (
                "🏆・showcase",
                discord.ChannelType.text,
                "Show off your strategies, bots, dashboards, and results.",
            ),
            (
                "💡・ideas",
                discord.ChannelType.text,
                "Brainstorm ideas for strategies, tools, and integrations.",
            ),
        ],
    ),
    (
        "━━ HELP & SUPPORT ━━",
        [
            (
                "❓・help",
                discord.ChannelType.text,
                "Ask questions about using the framework. No question is too basic!",
            ),
            (
                "🐛・bug-reports",
                discord.ChannelType.text,
                "Found a bug? Report it here with steps to reproduce.",
            ),
            (
                "✨・feature-requests",
                discord.ChannelType.text,
                "Suggest new features and improvements for the framework.",
            ),
        ],
    ),
    (
        "━━ DEVELOPMENT ━━",
        [
            (
                "🔨・contributing",
                discord.ChannelType.text,
                "Want to contribute? Discuss PRs, issues, and development workflow.",
            ),
            (
                "📋・pull-requests",
                discord.ChannelType.text,
                "Discuss open PRs and code reviews.",
            ),
            (
                "🚀・releases",
                discord.ChannelType.text,
                "Release notes, changelogs, and migration guides.",
            ),
            (
                "🤖・github-feed",
                discord.ChannelType.text,
                "Automated feed of GitHub activity (issues, PRs, releases).",
            ),
        ],
    ),
    (
        "━━ STRATEGIES ━━",
        [
            (
                "📊・strategy-discussion",
                discord.ChannelType.text,
                "Discuss trading strategies, signals, indicators, and alpha.",
            ),
            (
                "🔬・backtesting",
                discord.ChannelType.text,
                "Share backtesting results, methodology, and pitfalls.",
            ),
            (
                "⚡・live-trading",
                discord.ChannelType.text,
                "Running strategies live? Discuss deployment, monitoring, and ops.",
            ),
            (
                "🪙・crypto",
                discord.ChannelType.text,
                "Crypto-specific strategies, exchanges (Bitvavo, Coinbase, etc.).",
            ),
        ],
    ),
    (
        "━━ RESOURCES ━━",
        [
            (
                "📚・tutorials",
                discord.ChannelType.text,
                "Step-by-step guides and learning resources.",
            ),
            (
                "📖・documentation",
                discord.ChannelType.text,
                "Docs feedback, corrections, and improvement suggestions.",
            ),
            (
                "🔗・external-resources",
                discord.ChannelType.text,
                "Useful links — papers, books, tools, datasets, and APIs.",
            ),
        ],
    ),
    (
        "━━ MARKETPLACES ━━",
        [
            (
                "🏪・general-marketplace",
                discord.ChannelType.text,
                "General discussion about algo trading marketplaces and platforms.",
            ),
            (
                "🐱・finterion",
                discord.ChannelType.text,
                "Discussion about Finterion — deploying and monetizing your strategies.",
            ),
        ],
    ),
    (
        "━━ VOICE ━━",
        [
            ("🎙️・general-voice", discord.ChannelType.voice, None),
            ("👥・pair-programming", discord.ChannelType.voice, None),
            ("📺・screen-share", discord.ChannelType.voice, None),
        ],
    ),
]

# Read-only channels — only admins/mods can post
READ_ONLY_CHANNELS = {
    "👋・welcome",
    "📜・rules",
    "📢・announcements",
    "🗺️・roadmap",
    "🚀・releases",
    "🤖・github-feed",
}

# Pinned messages per channel (sent and pinned on first setup)
PINNED_MESSAGES = {
    "👋・welcome": (
        "# Welcome to the Investing Algorithm Framework community! 🎉\n\n"
        "We're a community of algo traders, quants, and developers building "
        "trading strategies with the **Investing Algorithm Framework**.\n\n"
        "**Quick links:**\n"
        "📖 [Documentation](https://investing-algorithm-framework.com)\n"
        "💻 [GitHub](https://github.com/coding-kitties/investing-algorithm-framework)\n"
        "📦 [PyPI](https://pypi.org/project/investing-algorithm-framework/)\n"
        "🐱 [Finterion](https://finterion.com)\n\n"
        "**Getting started:**\n"
        "1. Read the 📜・rules\n"
        "2. Introduce yourself in 🙋・introductions\n"
        "3. Ask questions in ❓・help\n"
        "4. Share your work in 🏆・showcase\n\n"
        "Happy trading! 🚀"
    ),
    "📜・rules": (
        "# Community Rules 📜\n\n"
        "**1. Be respectful** — Treat everyone with kindness. No harassment, "
        "hate speech, or personal attacks.\n\n"
        "**2. No financial advice** — This is an engineering community. "
        "Don't give or ask for specific investment advice.\n\n"
        "**3. No spam or self-promotion** — Keep promotional content to "
        "🏆・showcase. No unsolicited DMs.\n\n"
        "**4. Stay on topic** — Use the right channels. Off-topic chat "
        "goes in 💬・general.\n\n"
        "**5. No sharing of API keys or credentials** — Never post "
        "secrets, tokens, or passwords.\n\n"
        "**6. Help others learn** — Share knowledge, explain your "
        "reasoning, and be patient with beginners.\n\n"
        "**7. Report issues properly** — Use 🐛・bug-reports with "
        "reproduction steps, or open a GitHub issue.\n\n"
        "Breaking these rules may result in a warning or ban. "
        "Moderators have final say."
    ),
    "🔨・contributing": (
        "# Contributing to the Framework 🔨\n\n"
        "Want to contribute? Here's how to get started:\n\n"
        "1. **Fork** the repo: "
        "[github.com/coding-kitties/investing-algorithm-framework]"
        "(https://github.com/coding-kitties/investing-algorithm-framework)\n"
        "2. **Check open issues** — Look for `good first issue` or "
        "`help wanted` labels\n"
        "3. **Create a branch** — `feature/your-feature` or "
        "`fix/your-fix`\n"
        "4. **Submit a PR** — Reference the issue number\n\n"
        "Discuss your ideas here before starting large changes!"
    ),
    "🐱・finterion": (
        "# Finterion 🐱\n\n"
        "**Finterion** is the marketplace for algorithmic trading strategies.\n"
        "🔗 [finterion.com](https://finterion.com)\n\n"
        "Use this channel to discuss deploying strategies, "
        "monetization, and the Finterion platform."
    ),
}


class SetupBot(discord.Client):
    async def on_ready(self):
        guild = self.get_guild(GUILD_ID)

        if guild is None:
            print(f"Guild {GUILD_ID} not found. Check DISCORD_GUILD_ID.")
            await self.close()
            return

        print(f"Connected to guild: {guild.name}")

        # Get or create mod role for read-only channel overrides
        mod_role = discord.utils.get(guild.roles, name="Moderator")

        if mod_role is None:
            try:
                mod_role = await guild.create_role(
                    name="Moderator",
                    permissions=discord.Permissions(
                        manage_messages=True,
                        kick_members=True,
                        ban_members=True,
                    ),
                    color=discord.Color.blue(),
                    reason="Setup script: moderator role",
                )
                print(f"  Created role: Moderator")
            except discord.Forbidden:
                print(
                    "  Warning: Missing 'Manage Roles' permission. "
                    "Skipping Moderator role creation. "
                    "Read-only channels will not have permission overrides."
                )
                mod_role = None

        position = 0

        for category_name, channels in CHANNEL_LAYOUT:
            # Check if category already exists
            category = discord.utils.get(
                guild.categories, name=category_name
            )

            if category is None:
                category = await guild.create_category(
                    category_name,
                    position=position,
                    reason="Setup script: channel layout",
                )
                print(f"Created category: {category_name}")
            else:
                print(f"Category already exists: {category_name}")

            position += 1

            for channel_name, channel_type, topic in channels:
                # Check if channel already exists in category
                existing = discord.utils.get(
                    category.channels, name=channel_name
                )

                if existing is not None:
                    # Check if pinned message is missing
                    if (
                        channel_name in PINNED_MESSAGES
                        and isinstance(existing, discord.TextChannel)
                    ):
                        has_pins = False
                        async for _ in existing.pins():
                            has_pins = True
                            break

                        if not has_pins:
                            try:
                                msg = await existing.send(
                                    PINNED_MESSAGES[channel_name]
                                )
                                await msg.pin()
                                print(
                                    f"  Channel already exists: "
                                    f"#{channel_name} (added pinned message)"
                                )
                            except discord.Forbidden:
                                print(
                                    f"  Channel already exists: "
                                    f"#{channel_name} (could not pin — "
                                    f"missing Manage Messages permission)"
                                )
                        else:
                            print(
                                f"  Channel already exists: #{channel_name}"
                            )
                    else:
                        print(
                            f"  Channel already exists: #{channel_name}"
                        )
                    continue

                overwrites = None

                if channel_name in READ_ONLY_CHANNELS and mod_role is not None:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(
                            send_messages=False
                        ),
                        mod_role: discord.PermissionOverwrite(
                            send_messages=True
                        ),
                    }

                if channel_type == discord.ChannelType.voice:
                    await category.create_voice_channel(
                        channel_name,
                        reason="Setup script: channel layout",
                    )
                else:
                    kwargs = {
                        "topic": topic,
                        "reason": "Setup script: channel layout",
                    }
                    if overwrites:
                        kwargs["overwrites"] = overwrites

                    channel = await category.create_text_channel(
                        channel_name,
                        **kwargs,
                    )

                    # Send and pin message if configured
                    if channel_name in PINNED_MESSAGES:
                        try:
                            msg = await channel.send(PINNED_MESSAGES[channel_name])
                            await msg.pin()
                            print(f"  Created channel: #{channel_name} (+ pinned message)")
                        except discord.Forbidden:
                            print(f"  Created channel: #{channel_name} (could not pin — missing Manage Messages permission)")
                    else:
                        print(f"  Created channel: #{channel_name}")
                    continue

                print(f"  Created channel: #{channel_name}")

        print("\nDone! Channel layout created.")
        await self.close()


intents = discord.Intents.default()
intents.guilds = True
bot = SetupBot(intents=intents)
bot.run(BOT_TOKEN)

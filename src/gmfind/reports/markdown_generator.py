"""Generate markdown reports for Steam deals."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from gmfind.deals.deals_aggregator import AggregatedDeal

logger = logging.getLogger(__name__)


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    game_count: int = 10
    include_steam_reviews: bool = True
    include_metacritic: bool = True
    include_quotes: bool = True
    include_compatibility: bool = True
    min_quotes: int = 3


class MarkdownReportGenerator:
    """Generates markdown reports for Steam deals."""

    def __init__(self, preferences: dict | None = None):
        """Initialize the generator.

        Args:
            preferences: User preferences dict from config.yaml.
        """
        self.preferences = preferences or {}

    def generate_report(
        self,
        deals: list[AggregatedDeal],
        config: ReportConfig | None = None,
        output_path: str | None = None,
    ) -> str:
        """Generate a complete markdown report.

        Args:
            deals: List of deals to include in the report.
            config: Report configuration options.
            output_path: Optional path to save the report.

        Returns:
            The generated markdown string.
        """
        if config is None:
            config = ReportConfig()

        sections = []

        for rank, deal in enumerate(deals[: config.game_count], 1):
            sections.append(self._generate_game_section(deal, rank, config))

        markdown = "\n".join(sections).strip()

        if output_path:
            self._save_report(markdown, output_path)

        return markdown

    def _generate_header(self, config: ReportConfig) -> str:
        """Generate report header."""
        return ""

    def _generate_game_section(
        self,
        deal: AggregatedDeal,
        rank: int,
        config: ReportConfig,
    ) -> str:
        """Generate markdown section for a single game."""
        sections = []

        steam_url = f"https://store.steampowered.com/app/{deal.app_id}"
        sections.append(f"\n## {rank}. {deal.name}")
        sections.append(f"**Steam:** [{steam_url}]({steam_url})\n")

        # Include about content directly under title
        sections.append(self._generate_about_content(deal))

        # Combined pricing and recommendation section
        sections.append(self._generate_pricing_section(deal))

        if config.include_compatibility:
            sections.append(self._generate_compatibility_section(deal))

        if deal.requires_3rd_party_account:
            warning = "**Warning:** This game requires a 3rd party account"
            if deal.account_details:
                warning += f": {deal.account_details}"
            sections.append(warning + "\n")

        if config.include_metacritic or config.include_steam_reviews:
            sections.append(self._generate_scores_section(deal, config))

        if config.include_quotes:
            sections.append(self._generate_quotes_section(deal, config.min_quotes))

        sections.append("\n---")
        return "\n".join(sections)

    def _generate_about_content(self, deal: AggregatedDeal) -> str:
        """Generate the about content (without section header)."""
        parts = []

        if deal.genres:
            genre_str = ", ".join(deal.genres[:3])
            parts.append(f"A {genre_str.lower()} game")

        if deal.release_year:
            prefix = "released" if parts else "Released"
            parts.append(f"{prefix} in {deal.release_year}")

        if parts:
            about = " ".join(parts) + "."
        else:
            about = f"{deal.name} is available on Steam."

        if deal.steam_reviews:
            summary = deal.steam_reviews.get("summary", "")
            total = deal.steam_reviews.get("total", 0)
            if summary and total > 0:
                about += f" The game has received {summary} reviews from {total:,} players."

        if deal.short_description:
            about += f"\n\n{deal.short_description}"

        return about + "\n"

    def _generate_pricing_section(self, deal: AggregatedDeal) -> str:
        """Generate the combined pricing and recommendation section."""
        section = "\n### Discount and Recommendation\n"
        section += "| Original | Sale | Discount |\n"
        section += "|----------|------|----------|\n"
        orig = f"${deal.original_price:.2f}"
        sale = f"${deal.sale_price:.2f}"
        section += f"| {orig} | {sale} | **-{deal.discount_percent}%** |\n"

        # Add recommendation content
        reasons = []

        if deal.discount_percent >= 75:
            reasons.append(f"At {deal.discount_percent}% off, this is an exceptional deal")
        elif deal.discount_percent >= 50:
            reasons.append(f"With {deal.discount_percent}% off, this represents great value")
        else:
            reasons.append(f"Currently {deal.discount_percent}% off")

        if deal.sale_price <= 10:
            reasons.append(f"priced at just ${deal.sale_price:.2f}")
        elif deal.sale_price <= 20:
            reasons.append(f"available for ${deal.sale_price:.2f}")

        scores = []
        if deal.metacritic_score and deal.metacritic_score >= 85:
            scores.append(f"Metacritic {deal.metacritic_score}")
        if deal.steam_reviews:
            percent = deal.steam_reviews.get("percent_positive", 0)
            if percent >= 90:
                scores.append(f"{percent}% positive on Steam")

        if scores:
            reasons.append(f"with critical acclaim ({', '.join(scores)})")

        compat = []
        if deal.steam_deck_status == "verified":
            compat.append("Steam Deck Verified")
        if deal.protondb_tier in ("platinum", "gold"):
            compat.append(f"ProtonDB {deal.protondb_tier.title()}")
        if compat:
            reasons.append(f"excellent compatibility ({', '.join(compat)})")

        if len(reasons) >= 2:
            section += f"\n{reasons[0]}, {', '.join(reasons[1:])}.\n"
        else:
            section += f"\n{reasons[0]}.\n"

        return section

    def _generate_scores_section(self, deal: AggregatedDeal, config: ReportConfig) -> str:
        """Generate the scores table."""
        scores = "\n### Scores\n"
        scores += "| Source | Score | Details |\n"
        scores += "|--------|-------|--------|\n"

        if config.include_metacritic and deal.metacritic_score:
            link = f"[View]({deal.metacritic_url})" if deal.metacritic_url else "-"
            scores += f"| Metacritic | {deal.metacritic_score}/100 | {link} |\n"

        if config.include_steam_reviews and deal.steam_reviews:
            summary = deal.steam_reviews.get("summary", "")
            total = deal.steam_reviews.get("total", 0)
            percent = deal.steam_reviews.get("percent_positive", 0)
            scores += f"| Steam | {percent}% Positive | {total:,} reviews ({summary}) |\n"

        return scores

    def _generate_quotes_section(self, deal: AggregatedDeal, min_quotes: int) -> str:
        """Generate the critic reviews quotes section."""
        quotes = "\n### Critic Reviews\n"

        all_quotes = []
        seen_outlets = set()

        for quote in deal.metacritic_quotes:
            outlet = quote.get("outlet", "")
            text = quote.get("quote", "")
            score = quote.get("score")

            if not text or outlet in seen_outlets:
                continue

            seen_outlets.add(outlet)
            all_quotes.append((outlet, text, score))

        all_quotes.sort(key=lambda x: (x[2] or 0, len(x[1])), reverse=True)

        if not all_quotes:
            quotes += "*No critic reviews available.*\n"
        else:
            for outlet, text, score in all_quotes[:min_quotes]:
                if len(text) > 200:
                    text = text[:197] + "..."

                score_str = f" **Score: {score}**" if score else ""
                quotes += f'- "{text}" - *{outlet}*{score_str}\n'

        return quotes

    def _generate_compatibility_section(self, deal: AggregatedDeal) -> str:
        """Generate the compatibility section."""
        compat = "\n### Compatibility\n"

        items = []

        if deal.steam_deck_status:
            display = deal.steam_deck_display or deal.steam_deck_status.title()
            items.append(f"**Steam Deck:** {display}")

        if deal.protondb_tier:
            items.append(f"**ProtonDB:** {deal.protondb_tier.title()}")

        if items:
            compat += "- " + "\n- ".join(items) + "\n"
        else:
            compat += "*Compatibility information not available.*\n"

        return compat

    def _generate_footer(self) -> str:
        """Generate report footer."""
        return ""

    def _save_report(self, markdown: str, output_path: str):
        """Save the report to a file.

        Args:
            markdown: The markdown content to save.
            output_path: Path to save the report.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown)

        logger.info(f"Report saved to {path}")


def generate_timestamped_filename(base_dir: str = "docs") -> str:
    """Generate a unique filename with timestamp.

    Args:
        base_dir: Base directory for the report.

    Returns:
        Path string like 'docs/deals_20260111_143052.md'.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_dir}/deals_{timestamp}.md"

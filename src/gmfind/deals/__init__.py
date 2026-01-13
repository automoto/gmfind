"""Deals package for fetching discounted games."""

from .deals_aggregator import AggregatedDeal, DealsAggregator
from .steam_specials import SteamDeal, SteamSpecialsFetcher

__all__ = [
    "SteamDeal",
    "SteamSpecialsFetcher",
    "AggregatedDeal",
    "DealsAggregator",
]

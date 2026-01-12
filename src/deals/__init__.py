"""Deals package for fetching discounted games."""

from .steam_specials import SteamDeal, SteamSpecialsFetcher
from .deals_aggregator import AggregatedDeal, DealsAggregator

__all__ = [
    "SteamDeal",
    "SteamSpecialsFetcher",
    "AggregatedDeal",
    "DealsAggregator",
]

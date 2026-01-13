"""Game recommendation modules for gmfind."""

from gmfind.recommendations.metacritic import MetacriticScraper
from gmfind.recommendations.protondb import ProtonDBClient
from gmfind.recommendations.steam_deck import SteamDeckClient

__all__ = ["MetacriticScraper", "ProtonDBClient", "SteamDeckClient"]

"""Sample data fixtures for testing parsing functions."""

# Sample Steam games XML response (public profile)
STEAM_GAMES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gamesList>
    <steamID64>76561198012345678</steamID64>
    <steamID><![CDATA[TestUser]]></steamID>
    <games>
        <game>
            <appID>1245620</appID>
            <name><![CDATA[Elden Ring]]></name>
            <logo><![CDATA[https://cdn.akamai.steamstatic.com/steam/apps/1245620/capsule_184x69.jpg]]></logo>
            <storeLink><![CDATA[https://store.steampowered.com/app/1245620]]></storeLink>
            <hoursOnRecord>125.5</hoursOnRecord>
            <statsLink><![CDATA[https://steamcommunity.com/profiles/76561198012345678/stats/1245620]]></statsLink>
            <globalStatsLink><![CDATA[https://steamcommunity.com/stats/1245620/achievements/]]></globalStatsLink>
        </game>
        <game>
            <appID>292030</appID>
            <name><![CDATA[The Witcher 3: Wild Hunt]]></name>
            <logo><![CDATA[https://cdn.akamai.steamstatic.com/steam/apps/292030/capsule_184x69.jpg]]></logo>
            <storeLink><![CDATA[https://store.steampowered.com/app/292030]]></storeLink>
            <hoursOnRecord>85.2</hoursOnRecord>
            <statsLink><![CDATA[https://steamcommunity.com/profiles/76561198012345678/stats/292030]]></statsLink>
        </game>
        <game>
            <appID>730</appID>
            <name><![CDATA[Counter-Strike 2]]></name>
            <logo><![CDATA[https://cdn.akamai.steamstatic.com/steam/apps/730/capsule_184x69.jpg]]></logo>
            <storeLink><![CDATA[https://store.steampowered.com/app/730]]></storeLink>
        </game>
    </games>
</gamesList>
"""

# XML with no games
STEAM_GAMES_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<gamesList>
    <steamID64>76561198012345678</steamID64>
    <steamID><![CDATA[TestUser]]></steamID>
    <games>
    </games>
</gamesList>
"""

# Malformed XML
STEAM_GAMES_XML_MALFORMED = """<?xml version="1.0" encoding="UTF-8"?>
<gamesList>
    <games>
        <game>
            <appID>12345</appID>
            <name><![CDATA[Broken Game
"""

# Sample HTML with SSR.renderContext for private inventory
STEAM_LIBRARY_HTML = """<!DOCTYPE html>
<html>
<head><title>Steam Games</title></head>
<body>
<script>
window.SSR.renderContext=JSON.parse("{\\"queryData\\":\\"{\\\\\\"queries\\\\\\":[{\\\\\\"queryKey\\\\\\":[\\\\\\"OwnedGames\\\\\\"],\\\\\\"state\\\\\\":{\\\\\\"data\\\\\\":[{\\\\\\"appid\\\\\\":1245620,\\\\\\"name\\\\\\":\\\\\\"Elden Ring\\\\\\"},{\\\\\\"appid\\\\\\":292030,\\\\\\"name\\\\\\":\\\\\\"The Witcher 3\\\\\\"}]}}]}\\"}");
</script>
</body>
</html>
"""

# Sample HTML with legacy loaderData format
STEAM_LIBRARY_HTML_LEGACY = """<!DOCTYPE html>
<html>
<head><title>Steam Games</title></head>
<body>
<script>
window.SSR.loaderData = ["{\\"listData\\":{\\"rgRecentlyPlayedGames\\":[{\\"appid\\":730,\\"name\\":\\"Counter-Strike 2\\"}]},\\"OwnedGames\\":true}"];
</script>
</body>
</html>
"""

# Sample HTML with no JSON data (for fallback DOM testing)
STEAM_LIBRARY_HTML_NO_JSON = """<!DOCTYPE html>
<html>
<head><title>Steam Games</title></head>
<body>
<div class="GamesListItemContainer">
    <a href="/app/1245620/Elden_Ring/">
        <span class="GameName">Elden Ring</span>
    </a>
</div>
</body>
</html>
"""

# Sample Metacritic page with Nuxt.js embedded data
METACRITIC_REVIEWS_HTML = """<!DOCTYPE html>
<html>
<head><title>Elden Ring Reviews</title></head>
<body>
<script>
window.__NUXT__={config:{},data:[{reviews:[{publicationName:"IGN",score:100,quote:"A masterpiece of open-world design",url:"https://ign.com/reviews/elden-ring"},{publicationName:"GameSpot",score:95,quote:"FromSoftware's best work yet",url:"https://gamespot.com/reviews/elden-ring"}]}]};
</script>
</body>
</html>
"""

# Sample Steam search results HTML
STEAM_SEARCH_HTML = """<!DOCTYPE html>
<html>
<body>
<div id="search_resultsRows">
    <a class="search_result_row" href="https://store.steampowered.com/app/1245620/Elden_Ring/?snr=1_7_7_151_150_1">
        <span class="title">Elden Ring</span>
        <div class="search_price">$59.99</div>
    </a>
    <a class="search_result_row" href="https://store.steampowered.com/app/1888930/Elden_Ring_Shadow_of_the_Erdtree/?snr=1_7_7_151_150_1">
        <span class="title">ELDEN RING Shadow of the Erdtree</span>
        <div class="search_price">$39.99</div>
    </a>
</div>
</body>
</html>
"""

# URL test cases
URL_TEST_CASES = [
    ("https://store.steampowered.com/app/1245620/Elden_Ring/", 1245620),
    ("https://store.steampowered.com/app/730/", 730),
    ("/app/292030/The_Witcher_3/", 292030),
    ("https://store.steampowered.com/bundle/12345/", None),  # Bundle, not app
    ("invalid-url", None),
]

# Metacritic URL slug test cases
METACRITIC_SLUG_TEST_CASES = [
    ("https://www.metacritic.com/game/pc/elden-ring/", "elden-ring"),
    ("https://www.metacritic.com/game/elden-ring/", "elden-ring"),
    ("/game/pc/the-witcher-3-wild-hunt/", "the-witcher-3-wild-hunt"),
    ("/game/baldurs-gate-3/", "baldurs-gate-3"),
    ("https://www.metacritic.com/browse/game/", ""),  # No slug
]

# Normalization test cases
NORMALIZATION_TEST_CASES = [
    ("Elden Ring", "eldenring"),
    ("The Witcher 3: Wild Hunt", "thewitcher3wildhunt"),
    ("DOOM (2016)", "doom2016"),
    ("Baldur's Gate 3", "baldursgate3"),
    ("  Spaces  Everywhere  ", "spaceseverywhere"),
    ("", ""),
]

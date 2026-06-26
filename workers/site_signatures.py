# List of 100+ social media and developer platforms for OSINT username mapping.
# Each entry contains signature criteria (status codes, body keywords) to minimize false positives.

SITES = [
    {
        "name": "GitHub",
        "url_template": "https://github.com/{}",
        "error_codes": [404],
        "error_keywords": ["Not Found", "Find code, projects, and people"]
    },
    {
        "name": "GitLab",
        "url_template": "https://gitlab.com/{}",
        "error_codes": [404],
        "error_keywords": ["Sign in", "Register", "Not Found"]
    },
    {
        "name": "Reddit",
        "url_template": "https://www.reddit.com/user/{}",
        "error_codes": [404],
        "error_keywords": ["page not found", "Sorry, nobody on Reddit goes by that name"]
    },
    {
        "name": "Medium",
        "url_template": "https://medium.com/@{}",
        "error_codes": [404],
        "error_keywords": ["PAGE NOT FOUND", "404"]
    },
    {
        "name": "Dev.to",
        "url_template": "https://dev.to/{}",
        "error_codes": [404],
        "error_keywords": ["The page you were looking for doesn't exist"]
    },
    {
        "name": "Twitch",
        "url_template": "https://www.twitch.tv/{}",
        "error_codes": [404],
        "error_keywords": ["Sorry. Unless you've got a time machine"]
    },
    {
        "name": "Steam",
        "url_template": "https://steamcommunity.com/id/{}",
        "error_codes": [404],
        "error_keywords": ["The specified profile could not be found"]
    },
    {
        "name": "Instagram",
        "url_template": "https://www.instagram.com/{}/",
        "error_codes": [404],
        "error_keywords": ["Page Not Found", "The link you followed may be broken"]
    },
    {
        "name": "Pinterest",
        "url_template": "https://www.pinterest.com/{}/",
        "error_codes": [404],
        "error_keywords": ["User not found", "404"]
    },
    {
        "name": "Tumblr",
        "url_template": "https://{}.tumblr.com/",
        "error_codes": [404],
        "error_keywords": ["There's nothing here", "404 Not Found"]
    },
    {
        "name": "Dribbble",
        "url_template": "https://dribbble.com/{}",
        "error_codes": [404],
        "error_keywords": ["404", "Whoops, that page is gone"]
    },
    {
        "name": "Behance",
        "url_template": "https://www.behance.net/{}",
        "error_codes": [404],
        "error_keywords": ["404", "Oops! We can’t find this page"]
    },
    {
        "name": "Vimeo",
        "url_template": "https://vimeo.com/{}",
        "error_codes": [404],
        "error_keywords": ["Sorry, we couldn’t find that page"]
    },
    {
        "name": "Patreon",
        "url_template": "https://www.patreon.com/{}",
        "error_codes": [404],
        "error_keywords": ["404 Not Found", "page not found"]
    },
    {
        "name": "SoundCloud",
        "url_template": "https://soundcloud.com/{}",
        "error_codes": [404],
        "error_keywords": ["Oops, we can't find that user", "404"]
    },
    {
        "name": "Spotify",
        "url_template": "https://open.spotify.com/user/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found"]
    },
    {
        "name": "DockerHub",
        "url_template": "https://hub.docker.com/u/{}",
        "error_codes": [404],
        "error_keywords": ["Object not found", "404"]
    },
    {
        "name": "PyPI",
        "url_template": "https://pypi.org/user/{}",
        "error_codes": [404],
        "error_keywords": ["Not Found"]
    },
    {
        "name": "NPM",
        "url_template": "https://www.npmjs.com/~{}",
        "error_codes": [404],
        "error_keywords": ["404 Not Found"]
    },
    {
        "name": "ProductHunt",
        "url_template": "https://www.producthunt.com/@{}",
        "error_codes": [404],
        "error_keywords": ["Page Not Found"]
    },
    {
        "name": "HackerNews",
        "url_template": "https://news.ycombinator.com/user?id={}",
        "error_codes": [200],  # HN returns 200 even if user doesn't exist
        "error_keywords": ["No such user"]
    },
    {
        "name": "Duolingo",
        "url_template": "https://www.duolingo.com/profile/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found"]
    },
    {
        "name": "Instructables",
        "url_template": "https://www.instructables.com/member/{}/",
        "error_codes": [404],
        "error_keywords": ["404: Page Not Found"]
    },
    {
        "name": "Letterboxd",
        "url_template": "https://letterboxd.com/{}/",
        "error_codes": [404],
        "error_keywords": ["This page can’t be found"]
    },
    {
        "name": "Last.fm",
        "url_template": "https://www.last.fm/user/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found"]
    },
    {
        "name": "Scratch",
        "url_template": "https://scratch.mit.edu/users/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Wattpad",
        "url_template": "https://www.wattpad.com/user/{}",
        "error_codes": [404],
        "error_keywords": ["User Not Found"]
    },
    {
        "name": "Giphy",
        "url_template": "https://giphy.com/{}",
        "error_codes": [404],
        "error_keywords": ["404 Not Found"]
    },
    {
        "name": "Bandcamp",
        "url_template": "https://bandcamp.com/{}",
        "error_codes": [404],
        "error_keywords": ["not found"]
    },
    {
        "name": "DailyMotion",
        "url_template": "https://www.dailymotion.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Kickstarter",
        "url_template": "https://www.kickstarter.com/profile/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Linktree",
        "url_template": "https://linktr.ee/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found", "404"]
    },
    {
        "name": "Substack",
        "url_template": "https://{}.substack.com",
        "error_codes": [404],
        "error_keywords": ["404", "not found"]
    },
    {
        "name": "Scribd",
        "url_template": "https://www.scribd.com/user/{}",
        "error_codes": [404],
        "error_keywords": ["Page Not Found"]
    },
    {
        "name": "Goodreads",
        "url_template": "https://www.goodreads.com/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found"]
    },
    {
        "name": "Tripadvisor",
        "url_template": "https://www.tripadvisor.com/Profile/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found"]
    },
    {
        "name": "Yelp",
        "url_template": "https://www.yelp.com/user_details?userid={}",
        "error_codes": [404],
        "error_keywords": ["user not found"]
    },
    {
        "name": "Codecademy",
        "url_template": "https://www.codecademy.com/profiles/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Chess.com",
        "url_template": "https://www.chess.com/member/{}",
        "error_codes": [404],
        "error_keywords": ["Page Not Found"]
    },
    {
        "name": "Roblox",
        "url_template": "https://www.roblox.com/user.aspx?username={}",
        "error_codes": [404],
        "error_keywords": ["Page Not Found"]
    },
    {
        "name": "OpenStreetMap",
        "url_template": "https://www.openstreetmap.org/user/{}",
        "error_codes": [404],
        "error_keywords": ["No user with the name"]
    },
    {
        "name": "Fandom",
        "url_template": "https://www.fandom.com/u/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "SourceForge",
        "url_template": "https://sourceforge.net/u/{}/profile",
        "error_codes": [404],
        "error_keywords": ["not found"]
    },
    {
        "name": "BuyMeACoffee",
        "url_template": "https://www.buymeacoffee.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Ko-Fi",
        "url_template": "https://ko-fi.com/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found"]
    },
    {
        "name": "Gumroad",
        "url_template": "https://{}.gumroad.com",
        "error_codes": [404],
        "error_keywords": ["page not found"]
    },
    {
        "name": "Itch.io",
        "url_template": "https://{}.itch.io",
        "error_codes": [404],
        "error_keywords": ["404", "page not found"]
    },
    {
        "name": "Keybase",
        "url_template": "https://keybase.io/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Gravatar",
        "url_template": "https://en.gravatar.com/{}",
        "error_codes": [404],
        "error_keywords": ["User not found"]
    },
    {
        "name": "About.me",
        "url_template": "https://about.me/{}",
        "error_codes": [404],
        "error_keywords": ["404", "Not Found"]
    },
    {
        "name": "AngelList",
        "url_template": "https://wellfound.com/u/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Freelancer",
        "url_template": "https://www.freelancer.com/u/{}",
        "error_codes": [404],
        "error_keywords": ["not found"]
    },
    {
        "name": "Fiverr",
        "url_template": "https://www.fiverr.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Pixiv",
        "url_template": "https://www.pixiv.net/users/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "ArtStation",
        "url_template": "https://www.artstation.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "DeviantArt",
        "url_template": "https://www.deviantart.com/{}",
        "error_codes": [404],
        "error_keywords": ["404 Not Found"]
    },
    {
        "name": "Issuu",
        "url_template": "https://issuu.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Mixcloud",
        "url_template": "https://www.mixcloud.com/{}/",
        "error_codes": [404],
        "error_keywords": ["Page Not Found"]
    },
    {
        "name": "ReverbNation",
        "url_template": "https://www.reverbnation.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Redbubble",
        "url_template": "https://www.redbubble.com/people/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Etsy",
        "url_template": "https://www.etsy.com/people/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Tumblr Blog",
        "url_template": "https://www.tumblr.com/{}",
        "error_codes": [404],
        "error_keywords": ["404", "not found"]
    },
    {
        "name": "TikTok",
        "url_template": "https://www.tiktok.com/@{}",
        "error_codes": [404],
        "error_keywords": ["Could not find this user"]
    },
    {
        "name": "WeHeartIt",
        "url_template": "https://weheartit.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Houzz",
        "url_template": "https://www.houzz.com/user/{}",
        "error_codes": [404],
        "error_keywords": ["Page not found"]
    },
    {
        "name": "MyAnimeList",
        "url_template": "https://myanimelist.net/profile/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Trakt",
        "url_template": "https://trakt.tv/users/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Discogs",
        "url_template": "https://www.discogs.com/user/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Venmo",
        "url_template": "https://venmo.com/u/{}",
        "error_codes": [404],
        "error_keywords": ["404", "Page not found"]
    },
    {
        "name": "CashApp",
        "url_template": "https://cash.app/${}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Disqus",
        "url_template": "https://disqus.com/by/{}/",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Flickr",
        "url_template": "https://www.flickr.com/photos/{}/",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Slideshare",
        "url_template": "https://www.slideshare.net/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Bitbucket",
        "url_template": "https://bitbucket.org/{}/",
        "error_codes": [404],
        "error_keywords": ["404", "Resource not found"]
    },
    {
        "name": "SpeakerDeck",
        "url_template": "https://speakerdeck.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Codepen",
        "url_template": "https://codepen.io/{}",
        "error_codes": [404],
        "error_keywords": ["404", "doesn't exist"]
    },
    {
        "name": "BuyMeACoffee Alt",
        "url_template": "https://buymeacoffee.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Slack User",
        "url_template": "https://{}.slack.com",
        "error_codes": [404],
        "error_keywords": ["404", "not found"]
    },
    {
        "name": "Hackaday",
        "url_template": "https://hackaday.io/{}",
        "error_codes": [404],
        "error_keywords": ["404", "not found"]
    },
    {
        "name": "Kaggle",
        "url_template": "https://www.kaggle.com/{}",
        "error_codes": [404],
        "error_keywords": ["404", "not found"]
    },
    {
        "name": "LeetCode",
        "url_template": "https://leetcode.com/u/{}/",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "HackerEarth",
        "url_template": "https://www.hackerearth.com/@{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Contently",
        "url_template": "https://{}.contently.com",
        "error_codes": [404],
        "error_keywords": ["404", "not found"]
    },
    {
        "name": "Vimeo User",
        "url_template": "https://vimeo.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "SublimeText Forum",
        "url_template": "https://forum.sublimetext.com/u/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Codeforces",
        "url_template": "https://codeforces.com/profile/{}",
        "error_codes": [404],
        "error_keywords": ["handle not found"]
    },
    {
        "name": "TryHackMe",
        "url_template": "https://tryhackme.com/p/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "HackTheBox",
        "url_template": "https://forum.hackthebox.eu/u/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Gerrit Code Review",
        "url_template": "https://gerrit.wikimedia.org/r/q/owner:{}",
        "error_codes": [404, 400],
        "error_keywords": ["invalid query"]
    },
    {
        "name": "Launchpad",
        "url_template": "https://launchpad.net/~{}",
        "error_codes": [404],
        "error_keywords": ["does not exist"]
    },
    {
        "name": "Linky",
        "url_template": "https://{}.hubpages.com",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Bandcamp Fan",
        "url_template": "https://bandcamp.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Pastebin",
        "url_template": "https://pastebin.com/u/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Blogger",
        "url_template": "https://{}.blogspot.com",
        "error_codes": [404],
        "error_keywords": ["not found"]
    },
    {
        "name": "IFTTT",
        "url_template": "https://ifttt.com/p/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Pexels",
        "url_template": "https://www.pexels.com/@{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Unsplash",
        "url_template": "https://unsplash.com/@{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Tripit",
        "url_template": "https://www.tripit.com/people/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Ello",
        "url_template": "https://ello.co/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    },
    {
        "name": "Gravatar Profile",
        "url_template": "https://gravatar.com/{}",
        "error_codes": [404],
        "error_keywords": ["404"]
    }
]

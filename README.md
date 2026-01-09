# Jellyfin Auto Playlists

A tool to automatically make and update [jellyfin](https://jellyfin.org) playlists based on internet lists such as IMDb and letterboxd. Preserves list ordering and syncs with [Overseerr](https://overseerr.dev/)/[Jellyseerr](https://github.com/Fallenbagel/jellyseerr).

```
Getting playlists list...

found /r/TrueFilm Canon (1000 films) 015dee24c79dacfa80300afb7577fc37
************************************************

Processing list with 1000 items
Item A Trip to the Moon (1902) not found in jellyfin
Item The Birth of a Nation (1915) not found in jellyfin
Item Intolerance: Love's Struggle Throughout the Ages (1916) not found in jellyfin
Item A Man There Was (1917) not found in jellyfin
Item The Cabinet of Dr. Caligari (1920) not found in jellyfin
Matched Big Buck Bunny to Jellyfin item cc561c8b1d5da3a080cdb61ebe44d1a7
Matched Big Buck Bunny 2 to Jellyfin item 0515533b716e8fe76d3b630f9b9b6d51
Item Nosferatu (1922) not found in jellyfin
Item Dr. Mabuse, the Gambler (1922) not found in jellyfin
Item Häxan (1922) not found in jellyfin
Matched Big Buck Bunny 3 to Jellyfin item 9a6b8002ef8f12a0611e92f5104d8b8e
...
Matched 15/1000 items
Added 15 items to playlist in order
```

![pic-selected-220609-1405-13](https://user-images.githubusercontent.com/13795113/172853971-8b5ab33b-58a9-4073-8a28-c471e9710cdc.png)

## Supported List Sources

- IMDB Charts - e.g. [Top 250 Movies](https://imdb.com/chart/top), [Top Box Office](https://imdb.com/chart/boxoffice)
- IMDB Lists - e.g. [Top 100 Greatest Movie of All time](https://imdb.com/list/ls055592025)
- Letterboxd - e.g. [Movies everyone should watch at least once...](https://letterboxd.com/fcbarcelona/list/movies-everyone-should-watch-at-least-once)
- mdblist - e.g. [Top Movies of the week](https://mdblist.com/lists/garycrawfordgc/top-movies-of-the-week)
- They Shoot Pictures, Don't They - [The 1,000 Greatest Films](https://www.theyshootpictures.com/gf1000_all1000films_table.php)
- Trakt - e.g. [Popular Movies](https://trakt.tv/movies/popular). See the [Wiki](https://github.com/ghomasHudson/Jellyfin-Auto-Collections/wiki/Plugin-%E2%80%90-Trakt) for instructions.
- [Steven Lu Popular movies](https://github.com/sjlu/popular-movies)
- [The Criterion Channel](https://www.criterionchannel.com/new-collections)
- [Listmania](https://www.listmania.org)
- [BFI](https://www.bfi.org.uk/articles/type/lists)
- Jellyfin API Queries - Make playlists which match a particular filter from the [Jellyfin API](https://api.jellyfin.org/). See the [Wiki](https://github.com/ghomasHudson/Jellyfin-Auto-Collections/wiki/Plugin-%E2%80%90-Jellyfin-API) for some usage examples.
- Radarr/Sonarr - Make playlists from your *arr tags.

Please feel free to send pull requests with more!

## Usage

First, copy `config.yaml.example` to `config.yaml` and change the values for your specific jellyfin instance.

### Bare Metal

Make sure you have Python 3 and pip installed.

Install the requirements with `pip install -r requirements.txt`.

Then run `python main.py`.

### Docker

The easiest way to get going is to use the provided `docker-compose.yml` configuration. Whatever directory you end up mapping to the `/app/config` directory needs to contain your updated `config.yaml` file:

```yaml
services:
  jellyfin-auto-playlists:
    image: ghcr.io/sjorswijsman/jellyfin-auto-playlists:latest
    container_name: jellyfin-auto-playlists
    environment:
      - CRONTAB=0 0 * * *
      - TZ=America/New_York
      - JELLYFIN_SERVER_URL=https://www.jellyfin.example.com
      - JELLYFIN_API_KEY=1a1111aa1a1a1aaaa11a11aa111aaa11
      - JELLYFIN_USER_ID=2b2222bb2b2b2bbbb22b22bb222bbb22
    volumes:
      - ${CONFIG_DIR}/jellyfin-auto-playlists/config:/app/config
```


#### Configuration Options

| Environment Variable           | Description                                                                                                  |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| JELLYFIN_SERVER_URL            | The URL of your Jellyfin instance                                                                            |
| JELLYFIN_API_KEY               | Generated API Key                                                                                            |
| JELLYFIN_USER_ID               | UserID from the URL of your Profile in Jellyfin                                                              |
| CRONTAB                        | The interval the scripts will be run on in crontab syntax. Blank to disable scheduling (make sure you're not using the docker [restart policy](https://docs.docker.com/engine/containers/start-containers-automatically/)).                      |
| TZ                             | Timezone the interval will be run in. No effect if scheduling is disabled.                                   |

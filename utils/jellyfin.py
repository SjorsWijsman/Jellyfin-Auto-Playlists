import requests
from loguru import logger
from base64 import b64encode
import json
import concurrent.futures
from .poster_generation import fetch_collection_posters, safe_download, create_mosaic, get_font


class JellyfinClient:

    imdb_to_jellyfin_type_map = {
        "movie": ["Movie"],
        "short": ["Movie"],
        "tvEpisode": ["TvProgram", "Episode"],
        "tvSeries": ["Program", "Series"],
        "tvShort": ["TvProgram", "Episode", "Program"],
        "tvMiniSeries": ["Program", "Series"],
        "tvMovie": ["Movie", "TvProgram", "Episode"],
        "video": ["Movie", "TvProgram", "Episode", "Series"],
        "show": ["Program", "Series"],
    }

    def __init__(self, server_url: str, api_key: str, user_id: str):
        self.server_url = server_url
        self.api_key = api_key
        self.user_id = user_id

        # Check if server is reachable
        try:
            requests.get(self.server_url)
        except requests.exceptions.ConnectionError:
            raise Exception("Server is not reachable")

        # Check if api key is valid
        res = requests.get(f"{self.server_url}/System/Info", headers={"X-Emby-Token": self.api_key})
        if res.status_code != 200:
            raise Exception("Invalid API key")

        jf_info = res.json()
        logger.debug(f"Jellyfin Version: {jf_info['Version']}")

        # Check if user id is valid
        res = requests.get(f"{self.server_url}/Users/{self.user_id}", headers={"X-Emby-Token": self.api_key})
        if res.status_code != 200:
            raise Exception("Invalid user id")


    def get_all_playlists(self):
        params = {
            "enableTotalRecordCount": "false",
            "enableImages": "false",
            "Recursive": "true",
            "includeItemTypes": "Playlist",
            "fields": ["Name", "Id", "Tags"]
        }
        logger.info("Getting playlists list...")
        res = requests.get(f'{self.server_url}/Users/{self.user_id}/Items',headers={"X-Emby-Token": self.api_key}, params=params)
        return res.json()["Items"]


    def find_playlist_with_name_or_create(self, list_name: str, list_id: str, description: str, plugin_name: str, media_type: str = "Video", is_public: bool = True) -> str:
        '''Returns the playlist id of the playlist with the given name. If it doesn't exist, it creates a new playlist and returns the id of the new playlist.'''
        playlist_id = None
        playlists = self.get_all_playlists()

        # Check if list name in tags
        for playlist in playlists:
            if json.dumps(list_id) in playlist["Tags"]:
                playlist_id = playlist["Id"]
                break

        # if no match - Check if list name == playlist name
        if playlist_id is None:
            for playlist in playlists:
                if list_name == playlist["Name"]:
                    playlist_id = playlist["Id"]
                    break

        if playlist_id is not None:
            logger.info("found existing playlist: " + list_name + " (" + playlist_id + ")")

        if playlist_id is None:
            # Playlist doesn't exist -> Make a new one
            logger.info("No matching playlist found for: " + list_name + ". Creating new playlist...")
            # Use JSON body for better compatibility with is_public parameter
            res2 = requests.post(
                f'{self.server_url}/Playlists',
                headers={"X-Emby-Token": self.api_key},
                json={
                    "Name": list_name,
                    "UserId": self.user_id,
                    "MediaType": media_type,
                    "IsPublic": is_public
                }
            )
            playlist_id = res2.json()["Id"]
            logger.info(f"Created new playlist: {list_name} (IsPublic: {is_public})")

        # Update playlist description and add tags so we can find it later
        if playlist_id is not None:
            playlist = requests.get(f'{self.server_url}/Users/{self.user_id}/Items/{playlist_id}', headers={"X-Emby-Token": self.api_key}).json()
            if playlist.get("Overview", "") == "" and description is not None:
                playlist["Overview"] = description
            playlist["Tags"] = list(set(playlist.get("Tags", []) + ["Jellyfin-Auto-Playlists", plugin_name, json.dumps(list_id)]))
            r = requests.post(f'{self.server_url}/Items/{playlist_id}',headers={"X-Emby-Token": self.api_key}, json=playlist)

        return playlist_id

    def has_poster(self, playlist_id):
        '''Check if a playlist already has a poster'''
        poster_url = f"{self.server_url}/Items/{playlist_id}/Images/Primary"
        r = requests.get(poster_url, headers={"X-Emby-Token": self.api_key})
        if r.status_code == 404:
            return False
        return True


    def make_poster(self, playlist_id, playlist_name, mosaic_limit=20, google_font_url="https://fonts.googleapis.com/css2?family=Dosis:wght@800&display=swap"):

        # Check if playlist poster exists
        poster_urls = fetch_collection_posters(self.server_url, self.api_key, self.user_id, playlist_id)[:mosaic_limit]
        headers={"X-Emby-Token": self.api_key}

        # Use a ThreadPoolExecutor to download images in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(safe_download, url, headers) for url in poster_urls]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Filter out any failed downloads (None values)
        poster_images = [img for img in results if img is not None]

        font_path = get_font(google_font_url)

        if poster_images:
            safe_name = playlist_name.replace(" ", "_").replace("/", "_")
            output_path = f"/tmp/{safe_name}_cover.jpg"
            create_mosaic(poster_images, playlist_name, output_path, font_path)
        else:
            logger.warning(f"No posters available for playlist '{playlist_name}'. Skipping mosaic generation.")
            return

        # Upload

        from PIL import Image
        img = Image.open(output_path)  # or whatever format
        img = img.convert("RGB")  # Ensures it's safe for JPEG
        img.save(output_path, format="JPEG")

        with open(output_path, 'rb') as f:
            img_data = f.read()
        encoded_data = b64encode(img_data)

        headers["Content-Type"] = "image/jpeg"
        r = requests.post(f"{self.server_url}/Items/{playlist_id}/Images/Primary", headers=headers, data=encoded_data)


    def match_item_to_jellyfin(self, item, year_filter: bool = True, jellyfin_query_parameters={}):
        '''Matches an item to a Jellyfin item based on title, release year, and IMDB ID. Returns the Jellyfin item ID or None if not found.'''

        item["media_type"] = self.imdb_to_jellyfin_type_map.get(item["media_type"], item["media_type"])

        params = {
            "enableTotalRecordCount": "false",
            "enableImages": "false",
            "Recursive": "true",
            "IncludeItemTypes": item["media_type"],
            "searchTerm": item["title"],
            "fields": ["ProviderIds", "ProductionYear"]
        }

        params = {**params, **jellyfin_query_parameters}

        res = requests.get(f'{self.server_url}/Users/{self.user_id}/Items',headers={"X-Emby-Token": self.api_key}, params=params)

        # Check if there's an exact imdb_id match first
        match = None
        if "imdb_id" in item:
            for result in res.json()["Items"]:
                if result["ProviderIds"].get("Imdb", None) == item["imdb_id"]:
                    match = result
                    break
        else:
            # Check if there's a year match
            if match is None and year_filter:
                for result in res.json()["Items"]:
                    if str(result.get("ProductionYear", None)) == str(item["release_year"]):
                        match = result
                        break

            # Otherwise, just take the first result
            if match is None and len(res.json()["Items"]) == 1:
                match = res.json()["Items"][0]

        if match is None:
            logger.warning(f"Item {item['title']} ({item.get('release_year','N/A')}) {item.get('imdb_id','')} not found in jellyfin")
            logger.debug(f"List Candidate: {item}")

            # Show what Jellyfin found (if anything) to help debug
            search_results = res.json()['Items']
            if search_results:
                logger.debug(f"Jellyfin found {len(search_results)} results but none matched:")
                for result in search_results[:3]:  # Show first 3 results
                    result_imdb = result.get("ProviderIds", {}).get("Imdb", "no-imdb")
                    result_year = result.get("ProductionYear", "no-year")
                    logger.debug(f"  - '{result.get('Name')}' ({result_year}) IMDB:{result_imdb}")
            else:
                logger.debug(f"Jellyfin search returned no results for '{item['title']}'")

            return None
        else:
            item_id = match["Id"]
            logger.info(f"Matched {item['title']} to Jellyfin item {item_id}")
            logger.debug(f"\tList item: {item}")
            logger.debug(f"\tMatched JF item: {match}")
            return item_id


    def sync_playlist(self, playlist_id: str, item_ids_in_order: list):
        '''Syncs a playlist with the given items in order. Clears the playlist first, then adds all items in the correct order.'''
        if not item_ids_in_order:
            logger.warning(f"No items to add to playlist {playlist_id}")
            return

        # Clear existing items first
        self.clear_playlist(playlist_id)

        # Add items in batches to avoid URL length limits (chunk size of 50)
        # This preserves order by adding batches sequentially
        chunk_size = 50
        total_added = 0

        for i in range(0, len(item_ids_in_order), chunk_size):
            chunk = item_ids_in_order[i:i + chunk_size]
            ids_param = ",".join(chunk)

            logger.debug(f"Adding batch {i//chunk_size + 1}/{(len(item_ids_in_order) + chunk_size - 1)//chunk_size}: {len(chunk)} items")

            try:
                response = requests.post(
                    f'{self.server_url}/Playlists/{playlist_id}/Items',
                    headers={"X-Emby-Token": self.api_key},
                    params={"ids": ids_param, "userId": self.user_id}
                )

                # Check if the request was successful
                if response.status_code in [200, 204]:
                    total_added += len(chunk)
                    logger.debug(f"Successfully added batch of {len(chunk)} items ({total_added}/{len(item_ids_in_order)})")
                else:
                    logger.error(f"Failed to add batch to playlist. Status: {response.status_code}, Response: {response.text}")
                    logger.error(f"Failed batch IDs: {ids_param[:200]}...")

            except Exception as e:
                logger.error(f"Exception while adding batch to playlist: {e}")

        if total_added == len(item_ids_in_order):
            logger.info(f"Successfully added {total_added} items to playlist in order")
        else:
            logger.warning(f"Only added {total_added}/{len(item_ids_in_order)} items to playlist")


    def clear_playlist(self, playlist_id: str):
        '''Clears a playlist by removing all items from it'''
        res = requests.get(f'{self.server_url}/Users/{self.user_id}/Items',headers={"X-Emby-Token": self.api_key}, params={"Recursive": "true", "parentId": playlist_id})
        all_ids = [item["Id"] for item in res.json()["Items"]]

        if not all_ids:
            logger.info(f"Playlist {playlist_id} is already empty")
            return

        logger.info(f"Clearing {len(all_ids)} items from playlist {playlist_id}")

        # Delete all items at once using entryIds parameter
        response = requests.delete(
            f'{self.server_url}/Playlists/{playlist_id}/Items',
            headers={"X-Emby-Token": self.api_key},
            params={"entryIds": ",".join(all_ids)}
        )

        if response.status_code not in [200, 204]:
            logger.error(f"Error clearing playlist items: {response.status_code} - {response.text}")
        else:
            logger.info(f"Successfully cleared playlist {playlist_id}")

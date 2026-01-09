from typing import cast
from utils.jellyfin import JellyfinClient
from utils.jellyseerr import JellyseerrClient
import pluginlib
from loguru import logger
from pyaml_env import parse_config
import os
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import argparse
parser = argparse.ArgumentParser(description='Jellyfin List Scraper')
parser.add_argument('--config', type=str, help='Path to config file', default='config.yaml')
args = parser.parse_args()

# Set logging level
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
# Configure Loguru logger
logger.remove()  # Remove default configuration
logger.add(sys.stderr, level=log_level)

# Load config
if not os.path.exists(args.config):
    logger.error(f"{args.config} does not exist.")
    logger.error(f"Copy config.yaml.example to {args.config} and add your jellyfin config.")
    raise Exception("No config file found.")
config = parse_config(args.config, default_value=None)

def main(config):
    # Setup jellyfin connection
    jf_client = JellyfinClient(
        server_url=config['jellyfin']['server_url'],
        api_key=config['jellyfin']['api_key'],
        user_id=config['jellyfin']['user_id']
    )

    if "jellyseerr" in config:
        js_client = JellyseerrClient(
            server_url=config['jellyseerr']['server_url'],
            api_key=config['jellyseerr'].get('api_key', None),
            email=config['jellyseerr'].get('email', None),
            password=str(config['jellyseerr'].get('password', None)),
            user_type=str(config['jellyseerr'].get('user_type', "local"))
        )
    else:
        js_client = None

    # Load plugins
    loader = pluginlib.PluginLoader(modules=['plugins'])
    plugins = loader.plugins['list_scraper']

    # If Jellyfin_api plugin is enabled - pass the jellyfin creds to it
    if "jellyfin_api" in config["plugins"] and config["plugins"]["jellyfin_api"].get("enabled", False):
        config["plugins"]["jellyfin_api"]["server_url"] = config["jellyfin"]["server_url"]
        config["plugins"]["jellyfin_api"]["user_id"] = config["jellyfin"]["user_id"]
        config["plugins"]["jellyfin_api"]["api_key"] = config["jellyfin"]["api_key"]

    # Update jellyfin with lists
    for plugin_name in config['plugins']:
        if config['plugins'][plugin_name]["enabled"] and plugin_name in plugins:
            for list_entry in config['plugins'][plugin_name]["list_ids"]:
                if isinstance(list_entry, dict):
                    if "list_id" in list_entry:
                        list_id = list_entry["list_id"]
                    else:
                        list_id = list_entry
                    list_name = list_entry.get("list_name", None)
                else:
                    list_id = list_entry
                    list_name = None

                logger.info(f"")
                logger.info(f"")
                logger.info(f"Getting list info for plugin: {plugin_name}, list id: {list_id}")

                # Match list items to jellyfin items
                list_info = plugins[plugin_name].get_list(list_id, config['plugins'][plugin_name])

                # Find jellyfin playlist or create it
                playlist_id = jf_client.find_playlist_with_name_or_create(
                    list_name or list_info['name'],
                    list_id,
                    list_info.get("description", None),
                    plugin_name,
                    media_type=config["jellyfin"].get("playlist_defaults", {}).get("media_type", "Video"),
                    is_public=config["jellyfin"].get("playlist_defaults", {}).get("is_public", True)
                )

                # Match all items to Jellyfin IDs, preserving order
                logger.info(f"Processing list with {len(list_info['items'])} items")
                matched_items = []
                unmatched_items = []

                for item in list_info['items']:  # ORDER PRESERVED!
                    jellyfin_id = jf_client.match_item_to_jellyfin(
                        item,
                        year_filter=config["plugins"][plugin_name].get("year_filter", True),
                        jellyfin_query_parameters=config["jellyfin"].get("query_parameters", {})
                    )

                    if jellyfin_id:
                        matched_items.append(jellyfin_id)
                    else:
                        unmatched_items.append(item)

                # Sync playlist with matched items in order
                logger.info(f"Matched {len(matched_items)}/{len(list_info['items'])} items")
                if matched_items:
                    jf_client.sync_playlist(playlist_id, matched_items)
                else:
                    logger.warning(f"No items matched for playlist: {list_info['name']}")

                # Request missing items via Jellyseerr
                if js_client is not None and unmatched_items:
                    logger.info(f"Requesting {len(unmatched_items)} missing items via Jellyseerr")
                    for item in unmatched_items:
                        js_client.make_request(item)

                # Add a poster image if playlist doesn't have one
                if not jf_client.has_poster(playlist_id):
                    logger.info("Playlist has no poster - generating one")
                    jf_client.make_poster(playlist_id, list_info["name"])



if __name__ == "__main__":
    logger.info("Starting up")
    logger.info("Starting initial run")
    main(config)

    # Setup scheduler
    if "crontab" in config and config["crontab"] != "":
        scheduler = BlockingScheduler()
        scheduler.add_job(main, CronTrigger.from_crontab(config['crontab']), args=[config], timezone=config.get("timezone", "UTC"))
        logger.info("Starting scheduler using crontab: " + config["crontab"])
        scheduler.start()

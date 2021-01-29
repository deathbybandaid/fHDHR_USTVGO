import datetime
from json.decoder import JSONDecodeError
from simplejson import errors as simplejsonerrors


class Plugin_OBJ():

    def __init__(self, channels, plugin_utils):
        self.plugin_utils = plugin_utils

        self.channels = channels

        self.origin = plugin_utils.origin

    def update_epg(self):
        programguide = {}

        todaydate = datetime.date.today()

        self.remove_stale_cache(todaydate)

        pulltime = datetime.datetime.combine(todaydate, datetime.time(0, 0)).timestamp()

        for fhdhr_id in list(self.channels.list[self.plugin_utils.namespace].keys()):
            chan_obj = self.channels.list[self.plugin_utils.namespace][fhdhr_id]

            if str(chan_obj.number) not in list(programguide.keys()):
                programguide[str(chan_obj.number)] = chan_obj.epgdict

            epg_url = "https://ustvgo.tv/tvguide/JSON2/%s.json?%s" % (chan_obj.dict["callsign"].lower().replace("&", ""), pulltime)
            progtimes = self.get_cached(chan_obj.dict["callsign"], todaydate, epg_url)
            events = []
            if progtimes:
                for progtime in list(progtimes["items"].keys()):
                    events.extend(progtimes["items"][progtime])

                for event in events:

                    clean_prog_dict = {
                                        "time_start": int(event["start_timestamp"]),
                                        "time_end": int(event["end_timestamp"]),
                                        "duration_minutes": (int(event["end_timestamp"]) - int(event["start_timestamp"])),
                                        "thumbnail": None,
                                        "title": event["name"],
                                        "sub-title": "Unavailable",
                                        "description": event["description"],
                                        "rating": "N/A",
                                        "episodetitle": None,
                                        "releaseyear": None,
                                        "genres": [],
                                        "seasonnumber": None,
                                        "episodenumber": None,
                                        "isnew": False,
                                        "id": event["id"],
                                        }

                    if event["image"] and event["image"] != "":
                        clean_prog_dict["thumbnail"] = event["image"]

                    if not any((d['time_start'] == clean_prog_dict['time_start'] and d['id'] == clean_prog_dict['id']) for d in programguide[chan_obj.number]["listing"]):
                        programguide[str(chan_obj.number)]["listing"].append(clean_prog_dict)

        return programguide

    def get_cached(self, jsonid, cache_key, url):
        cacheitem = self.plugin_utils.db.get_plugin_value("%s_%s" % (jsonid, cache_key), "offline_cache", "ustvgo")
        if cacheitem:
            self.plugin_utils.logger.info("FROM CACHE:  %s" % cache_key)
            return cacheitem
        else:
            self.plugin_utils.logger.info("Fetching:  %s" % url)
            try:
                resp = self.plugin_utils.web.session.get(url)
            except self.plugin_utils.web.exceptions.HTTPError:
                self.plugin_utils.logger.info('Got an error!  Ignoring it.')
                return

            try:
                result = resp.json()
            except JSONDecodeError:
                self.plugin_utils.logger.info('Got an error!  Ignoring it.')
                return
            except simplejsonerrors.JSONDecodeError:
                self.plugin_utils.logger.info('Got an error!  Ignoring it.')
                return

            self.plugin_utils.db.set_plugin_value("%s_%s" % (jsonid, cache_key), "offline_cache", result, "ustvgo")
            cache_list = self.plugin_utils.db.get_plugin_value("cache_list", "offline_cache", "ustvgo") or []
            cache_list.append("%s_%s" % (jsonid, cache_key))
            self.plugin_utils.db.set_plugin_value("cache_list", "offline_cache", cache_list, "ustvgo")

    def remove_stale_cache(self, todaydate):
        cache_list = self.plugin_utils.db.get_plugin_value("cache_list", "offline_cache", "ustvgo") or []
        cache_to_kill = []
        for cacheitem in cache_list:
            cachedate = datetime.datetime.strptime(str(cacheitem).split("_")[-1], "%Y-%m-%d")
            todaysdate = datetime.datetime.strptime(str(todaydate), "%Y-%m-%d")
            if cachedate < todaysdate:
                cache_to_kill.append(cacheitem)
                self.plugin_utils.db.delete_plugin_value(cacheitem, "offline_cache", "ustvgo")
                self.plugin_utils.logger.info("Removing stale cache:  %s" % cacheitem)
        self.plugin_utils.db.set_plugin_value("cache_list", "offline_cache", [x for x in cache_list if x not in cache_to_kill], "ustvgo")

    def clear_cache(self):
        cache_list = self.plugin_utils.db.get_plugin_value("cache_list", "offline_cache", "ustvgo") or []
        for cacheitem in cache_list:
            self.plugin_utils.db.delete_plugin_value(cacheitem, "offline_cache", "ustvgo")
            self.plugin_utils.logger.info("Removing cache:  %s" % cacheitem)
        self.plugin_utils.db.delete_plugin_value("cache_list", "offline_cache", "ustvgo")

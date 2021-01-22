import datetime
from json.decoder import JSONDecodeError


class OriginEPG():

    def __init__(self, fhdhr):
        self.fhdhr = fhdhr

    def update_epg(self, fhdhr_channels):
        programguide = {}

        todaydate = datetime.date.today()

        self.remove_stale_cache(todaydate)

        pulltime = datetime.datetime.combine(todaydate, datetime.time(0, 0)).timestamp()

        for fhdhr_id in list(fhdhr_channels.list.keys()):
            chan_obj = fhdhr_channels.list[fhdhr_id]

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
        cacheitem = self.fhdhr.db.get_cacheitem_value("%s_%s" % (jsonid, cache_key), "offline_cache", "origin")
        if cacheitem:
            self.fhdhr.logger.info("FROM CACHE:  %s" % cache_key)
            return cacheitem
        else:
            self.fhdhr.logger.info("Fetching:  %s" % url)
            try:
                resp = self.fhdhr.web.session.get(url)
            except self.fhdhr.web.exceptions.HTTPError:
                self.fhdhr.logger.info('Got an error!  Ignoring it.')
                return

            try:
                result = resp.json()
            except JSONDecodeError:
                self.fhdhr.logger.info('Got an error!  Ignoring it.')
                return

            self.fhdhr.db.set_cacheitem_value("%s_%s" % (jsonid, cache_key), "offline_cache", result, "origin")
            cache_list = self.fhdhr.db.get_cacheitem_value("cache_list", "offline_cache", "origin") or []
            cache_list.append("%s_%s" % (jsonid, cache_key))
            self.fhdhr.db.set_cacheitem_value("cache_list", "offline_cache", cache_list, "origin")

    def remove_stale_cache(self, todaydate):
        cache_list = self.fhdhr.db.get_cacheitem_value("cache_list", "offline_cache", "origin") or []
        cache_to_kill = []
        for cacheitem in cache_list:
            cachedate = datetime.datetime.strptime(str(cacheitem).split("_")[-1], "%Y-%m-%d")
            todaysdate = datetime.datetime.strptime(str(todaydate), "%Y-%m-%d")
            if cachedate < todaysdate:
                cache_to_kill.append(cacheitem)
                self.fhdhr.db.delete_cacheitem_value(cacheitem, "offline_cache", "origin")
                self.fhdhr.logger.info("Removing stale cache:  %s" % cacheitem)
        self.fhdhr.db.set_cacheitem_value("cache_list", "offline_cache", [x for x in cache_list if x not in cache_to_kill], "origin")

    def clear_cache(self):
        cache_list = self.fhdhr.db.get_cacheitem_value("cache_list", "offline_cache", "origin") or []
        for cacheitem in cache_list:
            self.fhdhr.db.delete_cacheitem_value(cacheitem, "offline_cache", "origin")
            self.fhdhr.logger.info("Removing cache:  %s" % cacheitem)
        self.fhdhr.db.delete_cacheitem_value("cache_list", "offline_cache", "origin")

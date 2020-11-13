from lxml import html
import datetime


class OriginEPG():

    def __init__(self, fhdhr):
        self.fhdhr = fhdhr

        self.fhdhr.web_cache_dir = self.fhdhr.config.dict["filedir"]["epg_cache"]["origin"]["web_cache"]

    def scrape_json_id(self, callsign):
        chanpage = self.fhdhr.web.session.get("https://ustvgo.tv/" + callsign)
        tree = html.fromstring(chanpage.content)
        jsonid_xpath = "/html/body/div[1]/div[1]/div/div[1]/div/article/div/div[3]/iframe/@src"
        try:
            jsonid = tree.xpath(jsonid_xpath)[0].split("#")[1]
        except IndexError:
            jsonid = None
        return jsonid

    def ustogo_xmltime(self, tm):
        tm = datetime.datetime.fromtimestamp(tm)
        tm = str(tm.strftime('%Y%m%d%H%M%S')) + " +0000"
        return tm

    def update_epg(self, fhdhr_channels):
        programguide = {}

        timestamps = []
        todaydate = datetime.date.today()
        for x in range(0, 6):
            xdate = todaydate + datetime.timedelta(days=x)
            xtdate = xdate + datetime.timedelta(days=1)

            for hour in range(0, 24):
                time_start = datetime.datetime.combine(xdate, datetime.time(hour, 0))
                if hour + 1 < 24:
                    time_end = datetime.datetime.combine(xdate, datetime.time(hour + 1, 0))
                else:
                    time_end = datetime.datetime.combine(xtdate, datetime.time(0, 0))
                timestampdict = {
                                "time_start": str(time_start.strftime('%Y%m%d%H%M%S')) + " +0000",
                                "time_end": str(time_end.strftime('%Y%m%d%H%M%S')) + " +0000",
                                }
                timestamps.append(timestampdict)

        todaydate = datetime.date.today()

        self.remove_stale_cache(todaydate)

        for c in fhdhr_channels.get_channels():
            jsonid = self.scrape_json_id(c["callsign"])
            if not jsonid:
                if str(c["number"]) not in list(programguide.keys()):
                    programguide[str(c["number"])] = {
                                                        "callsign": c["callsign"],
                                                        "name": c["name"],
                                                        "number": c["number"],
                                                        "id": str(c["id"]),
                                                        "thumbnail": None,
                                                        "listing": [],
                                                        }

                for timestamp in timestamps:
                    clean_prog_dict = {
                                        "time_start": timestamp['time_start'],
                                        "time_end": timestamp['time_end'],
                                        "duration_minutes": 60,
                                        "thumbnail": None,
                                        "title": "Unavailable",
                                        "sub-title": "Unavailable",
                                        "description": "Unavailable",
                                        "rating": "N/A",
                                        "episodetitle": None,
                                        "releaseyear": None,
                                        "genres": [],
                                        "seasonnumber": None,
                                        "episodenumber": None,
                                        "isnew": False,
                                        "id": str(c["id"]) + "_" + str(timestamp['time_start']).split(" ")[0],
                                        }

                    programguide[str(c["number"])]["listing"].append(clean_prog_dict)

            else:
                if str(c["number"]) not in list(programguide.keys()):
                    programguide[str(c["number"])] = {
                                                        "callsign": c["callsign"],
                                                        "name": c["name"],
                                                        "number": c["number"],
                                                        "id": str(c["id"]),
                                                        "thumbnail": "https://static.streamlive.to/images/tv/" + jsonid + ".JPG",
                                                        "listing": [],
                                                        }

                epg_url = "https://ustvgo.tv/tvguide/json/" + jsonid + ".json"
                progtimes = self.get_cached(jsonid, todaydate, epg_url)
                events = []
                if progtimes:
                    for progtime in list(progtimes["items"].keys()):
                        events.extend(progtimes["items"][progtime])

                    for event in events:

                        clean_prog_dict = {
                                            "time_start": self.ustogo_xmltime(event["start_timestamp"]),
                                            "time_end": self.ustogo_xmltime(event["end_timestamp"]),
                                            "duration_minutes": 60,
                                            "thumbnail": event["image"],
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

                        programguide[str(c["number"])]["listing"].append(clean_prog_dict)
                else:

                    for timestamp in timestamps:
                        clean_prog_dict = {
                                            "time_start": timestamp['time_start'],
                                            "time_end": timestamp['time_end'],
                                            "duration_minutes": 60,
                                            "thumbnail": None,
                                            "title": "Unavailable",
                                            "sub-title": "Unavailable",
                                            "description": "Unavailable",
                                            "rating": "N/A",
                                            "episodetitle": None,
                                            "releaseyear": None,
                                            "genres": [],
                                            "seasonnumber": None,
                                            "episodenumber": None,
                                            "isnew": False,
                                            "id": str(c["id"]) + "_" + str(timestamp['time_start']).split(" ")[0],
                                            }

                        programguide[str(c["number"])]["listing"].append(clean_prog_dict)

        return programguide

    def get_cached(self, jsonid, cache_key, url):
        cacheitem = self.fhdhr.db.get_cacheitem_value(jsonid + "_" + str(cache_key), "offline_cache", "origin")
        if cacheitem:
            self.fhdhr.logger.info('FROM CACHE:  ' + jsonid + "_" + str(cache_key))
            return cacheitem
        else:
            self.fhdhr.logger.info('Fetching:  ' + url)
            try:
                resp = self.fhdhr.web.session.get(url)
            except self.fhdhr.web.exceptions.HTTPError:
                self.fhdhr.logger.info('Got an error!  Ignoring it.')
                return
            result = resp.json()

            self.fhdhr.db.set_cacheitem_value(jsonid + "_" + str(cache_key), "offline_cache", result, "origin")
            cache_list = self.fhdhr.db.get_cacheitem_value("cache_list", "offline_cache", "origin") or []
            cache_list.append(jsonid + "_" + str(cache_key))
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
                self.fhdhr.logger.info('Removing stale cache:  ' + str(cacheitem))
        self.fhdhr.db.set_cacheitem_value("cache_list", "offline_cache", [x for x in cache_list if x not in cache_to_kill], "origin")

    def clear_cache(self):
        cache_list = self.fhdhr.db.get_cacheitem_value("cache_list", "offline_cache", "origin") or []
        for cacheitem in cache_list:
            self.fhdhr.db.delete_cacheitem_value(cacheitem, "offline_cache", "origin")
            self.fhdhr.logger.info('Removing cache:  ' + str(cacheitem))
        self.fhdhr.db.delete_cacheitem_value("cache_list", "offline_cache", "origin")

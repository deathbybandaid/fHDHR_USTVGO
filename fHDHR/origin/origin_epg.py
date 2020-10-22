from lxml import html
import datetime
import json
import urllib.request


import fHDHR.tools


class originEPG():

    def __init__(self, settings, channels):
        self.config = settings
        self.channels = channels

        self.web = fHDHR.tools.WebReq()

        self.web_cache_dir = self.config.dict["filedir"]["epg_cache"]["origin"]["web_cache"]

    def scrape_json_id(self, callsign):
        chanpage = self.web.session.get("https://ustvgo.tv/" + callsign)
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

    def update_epg(self):
        programguide = {}

        todaydate = datetime.date.today()

        self.remove_stale_cache(todaydate)

        for c in self.channels.get_channels():
            jsonid = self.scrape_json_id(c["callsign"])
            if jsonid:
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
                result = self.get_cached(jsonid, todaydate, epg_url)

                events = []

                progtimes = json.loads(result)
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

        return programguide

    def get_cached(self, jsonid, cache_key, url):
        cache_path = self.web_cache_dir.joinpath(jsonid + "_" + str(cache_key))
        if cache_path.is_file():
            print('FROM CACHE:', str(cache_path))
            with open(cache_path, 'rb') as f:
                return f.read()
        else:
            print('Fetching:  ', url)
            try:
                resp = urllib.request.urlopen(url)
                result = resp.read()
            except urllib.error.HTTPError as e:
                if e.code == 400:
                    print('Got a 400 error!  Ignoring it.')
                    result = (
                        b'{'
                        b'"note": "Got a 400 error at this time, skipping.",'
                        b'"channels": []'
                        b'}')
                else:
                    raise
            with open(cache_path, 'wb') as f:
                f.write(result)
            return result

    def remove_stale_cache(self, todaydate):
        for p in self.web_cache_dir.glob('*'):
            try:
                cachedate = datetime.datetime.strptime(str(p.name).split("_")[-1], "%Y-%m-%d")
                todaysdate = datetime.datetime.strptime(str(todaydate), "%Y-%m-%d")
                if cachedate >= todaysdate:
                    continue
            except Exception as e:
                print(e)
                pass
            print('Removing stale cache file:', p.name)
            p.unlink()

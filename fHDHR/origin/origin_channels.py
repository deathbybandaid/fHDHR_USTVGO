import os
import sys
from lxml import html
import pathlib
import json
import m3u8

from seleniumwire import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.firefox.options import Options as FirefoxOptions

IFRAME_CSS_SELECTOR = '.iframe-container>iframe'


# Disable
def blockPrint():
    sys.stdout = open(os.devnull, 'w')


# Restore
def enablePrint():
    sys.stdout = sys.__stdout__


class OriginChannels():

    def __init__(self, fhdhr, origin):
        self.fhdhr = fhdhr
        self.origin = origin

        self.cache_dir = self.fhdhr.config.dict["filedir"]["epg_cache"]["origin"]["top"]
        self.m3ucache = pathlib.Path(self.cache_dir).joinpath('m3ucache.json')

        self.cached_m3u = {}
        self.load_m3u_cache()

    def load_m3u_cache(self):
        if os.path.isfile(self.m3ucache):
            self.fhdhr.logger.info("Loading Previously Saved Channel m3u.")
            with open(self.m3ucache, 'r') as m3ufile:
                self.cached_m3u = json.load(m3ufile)

    def save_m3u_cache(self):
        self.fhdhr.logger.info("Saving Channel m3u cache.")
        with open(self.m3ucache, 'w') as m3ufile:
            m3ufile.write(json.dumps(self.cached_m3u, indent=4))

    def get_channels(self):
        channel_list = []

        chan_names, chan_urls = self.scrape_channels()

        chan_number_index = 1
        for name, url in zip(chan_names, chan_urls):
            chan_dict = {
                        "name": name.rstrip(),
                        "number": chan_number_index,
                        "callsign": self.format_callsign(url),
                        }
            channel_list.append(chan_dict)
            chan_number_index += 1
        return channel_list

    def get_channel_stream(self, chandict, allchandict):
        caching = True
        streamlist = []
        streamdict = {}

        if chandict["callsign"] in list(self.cached_m3u):
            streamurl = self.cached_m3u[chandict["callsign"]]
        else:
            streamurl = self.get_ustvgo_stream(chandict)
            # if self.fhdhr.config.dict["origin"]["force_best"]:
            streamurl = self.m3u8_beststream(streamurl)

        streamdict = {"number": chandict["number"], "stream_url": streamurl}

        streamlist.append(streamdict)
        return streamlist, caching

    def m3u8_beststream(self, m3u8_url):
        bestStream = None
        videoUrlM3u = m3u8.load(m3u8_url)
        if not videoUrlM3u.is_variant:
            return m3u8_url

        for videoStream in videoUrlM3u.playlists:
            if not bestStream:
                bestStream = videoStream
            elif videoStream.stream_info.bandwidth > bestStream.stream_info.bandwidth:
                bestStream = videoStream

        if not bestStream:
            return bestStream.absolute_uri
        else:
            return m3u8_url

    def scrape_channels(self):
        channels_url = "https://ustvgo.tv/"
        chanpage = self.fhdhr.web.session.get(channels_url)
        tree = html.fromstring(chanpage.content)

        channel_names_xpath = "/html/body/div[1]/div[1]/div/div[2]/div/div/div/article/div[1]/ol/li[*]/strong/a/text()"
        channel_urls_xpath = "/html/body/div[1]/div[1]/div/div[2]/div/div/div/article/div[1]/ol/li[*]/strong/a/@href"

        chan_names = tree.xpath(channel_names_xpath)
        chan_urls = tree.xpath(channel_urls_xpath)
        return chan_names, chan_urls

    def format_callsign(self, url):
        callsign = (url
                    .split('/')[-2]
                    .replace('-live', '')
                    .replace('-channel', '')
                    .replace('-free', '')
                    .replace('-streaming', ''))
        return callsign

    def get_ustvgo_stream(self, chandict):
        driver = self.get_firefox_driver()
        blockPrint()
        driver.get("https://ustvgo.tv/" + chandict["callsign"])
        enablePrint()

        # Get iframe
        iframe = None
        try:
            iframe = driver.find_element_by_css_selector(IFRAME_CSS_SELECTOR)
        except NoSuchElementException:
            self.fhdhr.logger.error('Video frame is not found for channel')
            return None

        # Detect VPN-required channels
        try:
            driver.switch_to.frame(iframe)
            driver.find_element_by_xpath("//*[text()='This channel requires our VPN to watch!']")
            need_vpn = True
        except NoSuchElementException:
            need_vpn = False
        finally:
            driver.switch_to.default_content()

        if need_vpn:
            self.fhdhr.logger.warning('Channel needs VPN to be grabbed.')
            return None

        # Autoplay
        iframe.click()

        try:
            playlist = driver.wait_for_request('/playlist.m3u8', timeout=10)
        except TimeoutException:
            self.fhdhr.logger.error('Channel m3u8 not found.')
            return None

        streamurl = str(playlist)

        driver.close()
        driver.quit()
        self.cached_m3u[chandict["callsign"]] = streamurl
        self.save_m3u_cache()
        return streamurl

    def get_firefox_driver(self):
        ff_options = FirefoxOptions()
        ff_options.add_argument('--headless')

        firefox_profile = webdriver.FirefoxProfile()
        firefox_profile.set_preference('permissions.default.image', 2)
        firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')
        firefox_profile.set_preference('dom.disable_beforeunload', True)
        firefox_profile.set_preference('browser.tabs.warnOnClose', False)
        firefox_profile.set_preference('media.volume_scale', '0.0')

        set_seleniumwire_options = {
                                    'connection_timeout': None,
                                    'verify_ssl': False,
                                    'suppress_connection_errors': True
                                    }
        driver = webdriver.Firefox(seleniumwire_options=set_seleniumwire_options, options=ff_options, firefox_profile=firefox_profile)
        return driver

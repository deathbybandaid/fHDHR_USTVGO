import os
import sys

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
        self.wmsAuthSign = "c2VydmVyX3RpbWU9MS8xMS8yMDIxIDI6NTc6MjcgUE0maGFzaF92YWx1ZT0ySDQyUEQveTdkZUlzUnZnVnI2cFlnPT0mdmFsaWRtaW51dGVzPTI0MA=="

    def get_channels(self):

        channels_url = "https://ustvgo.tv/tvguide/national.json"

        chan_req = self.fhdhr.web.session.get(channels_url)
        entries = chan_req.json()

        channel_list = []
        chan_number_index = 0
        for channel_dict in entries:
            chan_number_index += 1

            clean_station_item = {
                                 "name": channel_dict["Channel"]["FullName"],
                                 "callsign": channel_dict["Channel"]["Name"],
                                 "number": chan_number_index,
                                 "id": channel_dict["Channel"]["SourceId"],
                                 "thumbnail": "https://static.streamlive.to/images/tv/%s.png" % channel_dict["Channel"]["Name"].lower().replace("&", "")
                                 }
            channel_list.append(clean_station_item)
        return channel_list

    def get_channel_stream(self, chandict, stream_args):
        # peer_list = ["peer%s.ustv24h.live" % x for x in range(1, 9)]
        # for peer_url_base in peer_list:
        #    m3u8_url = "https://%s/%s/myStream/playlist.m3u8?wmsAuthSign=%s" % (peer_url_base, chandict["callsign"], self.wmsAuthSign)
        #    videoUrlM3u = m3u8.load(m3u8_url)
        # return None
        streamurl = self.get_ustvgo_stream(chandict)

        stream_info = {"url": streamurl}

        return stream_info

    def get_ustvgo_stream(self, chandict):
        driver = self.get_firefox_driver()
        blockPrint()
        driver.get("https://ustvgo.tv/%s" % chandict["callsign"])
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

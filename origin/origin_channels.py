import m3u8


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
        peer_list = ["peer%s.ustv24h.live" % x for x in range(1, 9)]
        videoUrl_headers = {'User-Agent': "Mozilla/5.0"}
        streamurl = None
        for peer_url_base in peer_list:
            m3u8_url = "https://%s/%s/myStream/playlist.m3u8?wmsAuthSign=%s" % (peer_url_base, chandict["callsign"], self.wmsAuthSign)
            try:
                videoUrlM3u = m3u8.load(m3u8_url, headers=videoUrl_headers)
            except Exception as e:
                self.fhdhr.logger.warning(e)
                videoUrlM3u = None
            if videoUrlM3u:
                streamurl = videoUrlM3u
                stream_info = {"url": streamurl, "headers": videoUrl_headers}

        stream_info = {"url": streamurl, "headers": videoUrl_headers}

        return stream_info

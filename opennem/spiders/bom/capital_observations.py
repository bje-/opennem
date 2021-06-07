from typing import Generator

import scrapy

from opennem.spiders.bom.bom_base import BomJSONObservationSpider

from .utils import get_stations, get_stations_priority

REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}


class BomCapitalsSpider(BomJSONObservationSpider):
    name = "bom.capitals"

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        priority_stations = get_stations_priority()

        _headers = REQUEST_HEADERS.copy()

        for station in priority_stations:
            yield scrapy.Request(station.feed_url, meta={"code": station.code}, headers=_headers)


class BomAllSpider(BomJSONObservationSpider):
    # name = "bom.all"

    def start_requests(self) -> Generator[scrapy.Request, None, None]:
        stations = get_stations()

        _headers = REQUEST_HEADERS.copy()

        for station in stations:
            yield scrapy.Request(station.feed_url, meta={"code": station.code}, headers=_headers)

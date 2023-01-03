def get_station_id(station_code, config):

    base_url = config.url + config.locations_uri

    search_url = base_url

    config.logger.debug(
        f"Querying endpoint: {search_url}")

    location_response = config.session.get(search_url, expire_after=-1)

    if location_response.ok:
        location_dict = location_response.json()
        config.logger.debug(f'Response cached: {location_response.from_cache}')

        locations = location_dict['data']

        if locations:
            return [
                location['nlc'] for location in locations
                if location['code'] == station_code.upper()][0]
        else:
            config.logger.error(f'Invalid station code: {station_code}')
    else:
        config.logger.error(f'Unable to get location: {station_code}')

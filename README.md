# gwr-feed
A simple Python script to generate a [JSON Feed](https://github.com/manton/JSONFeed) for search for train tickets on [Great Western Railway](https://www.gwr.com). Only supports one-way Standard class journeys.

Served over [Flask!](https://github.com/pallets/flask/)

Use the [Docker build](https://github.com/users/leonghui/packages/container/package/gwr-feed) to host your own instance.

1. Set your timezone as an environment variable (see [docker docs]): `TZ=Europe/London`

2. Access the feed using the URL with origin and destination station codes: `http://<host>/?from=BHM&to=EUS`

3. Optionally, specify a:
    - date (YYYY-MM-DD): `http://<host>/?from=BHM&to=EUS&on=2022-12-25`
    - time (HH:MM): `http://<host>/?from=BHM&to=EUS&at=12:00`
    - number of weeks to look ahead: `http://<host>/?from=BHM&to=EUS&weeks_ahead=2`
    - or any combination of the above

4. (Advanced) Use a cron expression to specify a custom commuting schedule:
    - weekdays 8.30am: `http://<host>/cron?from=BHM&to=EUS&job=30 8 * * 1-5`
    - weekends 2pm, 2 weeks from now: `http://<host>/cron?from=BHM&to=EUS&job=00 14 * * 6,7&skip_weeks=2`

Note: set a longer timeout on your feed reader if you use the 'weeks_ahead' option


Tested with:
- [Nextcloud News App](https://github.com/nextcloud/news)

[docker docs]:(https://docs.docker.com/compose/environment-variables/#set-environment-variables-in-containers)

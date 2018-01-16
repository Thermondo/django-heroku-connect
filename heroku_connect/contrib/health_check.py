import json
import logging
import urllib.request
from urllib.error import URLError

from ..conf import settings
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import (
    ServiceReturnedUnexpectedResult, ServiceUnavailable
)

logger = logging.getLogger('heroku-health-check')


class HerokuConnectHealthCheck(BaseHealthCheckBackend):
    """
    Health Check for Heroku Connect.

    Note:

        This features requires `django-health-check`_ to be installed.

    .. _`django-health-check`: https://github.com/KristianOellegaard/django-health-check
    """

    def check_status(self):
        if not (settings.HEROKU_AUTH_TOKEN and settings.HEROKU_CONNECT_APP_NAME):
            raise ServiceUnavailable('Both App Name and Auth Token are required')

        connection_id = self.get_connection_id()
        return self.get_connection_status(connection_id)

    def get_connection_id(self):
        """
        Return ConnectionId from the JSON response of the connections api call.

        For more details check https://devcenter.heroku.com/articles/heroku-connect-api#step-4-retrieve-the-new-connection-s-id

        Sample response from the api call is below::

            {
                "count": 1,
                "results":[{
                    "id": "<connection_id>",
                    "name": "<app_name>",
                    "resource_name": "<resource_name>",
                    …
                }],
                …
            }

        """
        req = urllib.request.Request('%s/v3/connections?app=%s' % (
            settings.HEROKU_CONNECT_API_ENDPOINT, settings.HEROKU_CONNECT_APP_NAME))
        req.add_header('-H', '"Authorization: Bearer %s"' % settings.HEROKU_AUTH_TOKEN)
        try:
            output = urllib.request.urlopen(req)
        except URLError as e:
            raise ServiceReturnedUnexpectedResult(
                'Unable to fetch connectons') from e

        json_output = json.loads(output.read().decode())
        return json_output['results'][0]['id']

    def get_connection_status(self, connection_id):
        """
        Get Connection Status from the JSON response of the connection detail api call.

        For more details https://devcenter.heroku.com/articles/heroku-connect-api#step-8-monitor-the-connection-and-mapping-status

        Sample response from api call is below::

            {
                "id": "<connection_id>",
                "name": "<app_name>",
                "resource_name": "<resource_name>",
                "schema_name": "salesforce",
                "db_key": "DATABASE_URL",
                "state": "IDLE",
                "mappings":[
                    {
                        "id": "<mapping_id>",
                        "object_name": "Account",
                        "state": "SCHEMA_CHANGED",
                        …
                    },
                    {
                        "id": "<mapping_id>",
                        "object_name": "Contact",
                        "state": "SCHEMA_CHANGED",
                        …
                    },
                    …
                ]
                …
            }
        """
        req = urllib.request.Request('%s/connections/%s?deep=true' % (
            settings.HEROKU_CONNECT_API_ENDPOINT, connection_id))
        req.add_header('-H', '"Authorization: Bearer %s"' % settings.HEROKU_AUTH_TOKEN)

        try:
            output = urllib.request.urlopen(req)
        except URLError as e:
            raise ServiceReturnedUnexpectedResult(
                'Unable to fetch connection details') from e

        json_output = json.loads(output.read().decode())
        connection_state = json_output['state']
        if connection_state == 'IDLE':
            return True

# Copyright 2018 Catalyst IT Ltd.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
from urllib.parse import urljoin

import requests

from rt_client.v2.record_manager import LimitedRecordManager, RecordManager
from rt_client.v2.attachments import AttachmentManager
from rt_client.v2.customfields import CustomFieldManager
from rt_client.v2.tickets import TicketManager
from rt_client.v2.transactions import TransactionManager


logger = logging.getLogger(__name__)


class Client(object):
    def __init__(
        self,
        username,
        password,
        endpoint,
        auth_endpoint="NoAuth/Login.html",
        api_endpoint="REST/2.0/",
        auth_token=None,
        verify=True,
    ):
        """
        Args:
            username (str): The user's login username.
            password (str): The user's login password.
            endpoint (str): The base URL of the host RT system. e.g 'rt.host.com/'
            auth_endpoint (str): The endpoint to POST Authorization. e.g 'login/'
            api_endpoint (str, optional): The endpoint for the REST API.
                Defaults to 'REST/2.0/'
            auth_token (str, optional): Authentication token from
                the RT::Authen::Token extension. Defaults to None.
            verify (boolean, optional): whether to verify certs or not
        """
        # Authentication
        self.verify = verify
        self.username = username
        self.password = password
        self.auth_token = auth_token
        self.auth_endpoint = auth_endpoint
        self.api_endpoint = api_endpoint
        self.sess = requests.Session()
        # Set important endpoints
        self.base_host = endpoint
        self.host = urljoin(endpoint, api_endpoint)
        # Create record manager links
        self.authenticate()
        self._create_record_managers()

    def authenticate(self):
        """ Session authentication function """
        auth_url = urljoin(self.base_host, self.auth_endpoint)
        try:
            # Use token authentication, if able
            if self.auth_token:
                token = f"token {self.auth_token}"
                self.sess.post(
                    auth_url, data={"Authentication": token}, verify=self.verify
                )
            # Otherwise, revert to username/password authentication
            else:
                self.sess.post(
                    auth_url,
                    data={"user": self.username, "pass": self.password},
                    verify=self.verify,
                )
            return self.sess
        except Exception:
            logger.debug("RT Client Authentication Failure")
            raise

    def _create_record_managers(self):
        """ Creates managers for each required record type """
        try:
            # Special Records
            self.ticket = TicketManager(self)
            self.transaction = TransactionManager(self)
            self.attachment = AttachmentManager(self)
            self.customfield = CustomFieldManager(self)

            # Fully supported records
            for full_record in ["queue", "catalog", "asset", "user"]:
                setattr(self, full_record, RecordManager(self, full_record))

            # Partially supported records
            for limited_record in ["group", "customrole"]:
                setattr(
                    self, limited_record, LimitedRecordManager(self, limited_record)
                )
        except Exception:
            logger.debug("Failed to create RT Client Record Managers")
            raise

    def _redirected_to_login_page(self, response):
        """Determine if a the response was the result of a redirect from
        the desired endpoint to the login page ("/").
        """
        if len(response.history) > 0:
            for r in response.history:
                if r.status_code == 302 and r.headers.get("Location") == "/":
                    logger.info("Request was redirected")
                    return True
        return False

    def _missing_or_stale_session_cookie(self, response):
        """Determine if a response is likely the result of a stale
        session cookie.
        """

        if response.status_code == 401:
            # Handles case where no cookie exists and future proofs client
            # in case RT is fixed in the future and starts sending sane
            # responses.
            logger.info("Session cookie could be missing or stale")
            return True
        elif self._redirected_to_login_page(response):
            # Request was redirected to the login page which probably
            # means the cookie exists but has an invalid/stale session id.
            logger.info("Session cookie could be stale")
            return True

        return False

    # REST V2

    def request(self, method, url, retries=1, *args, **kwargs):
        """Wrap requests to RT with logic for retrying requests which fail
        due to stale session cookies.
        """

        _url = urljoin(self.host, url)

        response = self.sess.request(method, _url, verify=self.verify, *args, **kwargs)

        if retries > 0 and self._missing_or_stale_session_cookie(response):
            # The request failed for some reason. Incase the issue was a
            # missing or stale session cookie, refresh the cookie and try
            # the request again.
            retries -= 1
            logger.info("Refreshing session")
            self.authenticate()
            logger.info("Attempting request again: (retries remaining=%s)" % retries)
            return self.request(method, url, retries=retries, *args, **kwargs)

        response.raise_for_status()
        return response.json()

    def get(self, url, *args, **kwargs):
        """ Generic GET request to specified URL """

        return self.request("GET", url, *args, **kwargs)

    def post(self, url, content, *args, **kwargs):
        """ Generic POST request to specified URL """

        headers = kwargs.get("headers", {"Content-Type": "application/json"})

        return self.request("POST", url, json=content, headers=headers, *args, **kwargs)

    def post_files(self, url, files, *args, **kwargs):
        """ Generic POST request with files to specified URL """

        return self.request("POST", url, files=files, *args, **kwargs)

    def put(self, url, content, *args, **kwargs):
        """ Generic PUT request to specified URL """

        headers = kwargs.get("headers", {"Content-Type": "application/json"})

        return self.request(
            "PUT",
            url,
            json=content,
            headers=headers,
            *args,
            **kwargs,
        )

    def delete(self, url, *args, **kwargs):
        """ Generic DELETE request to specified URL """

        return self.request("DELETE", url, *args, **kwargs)

    # System Information functionality

    def rt_info(self):
        """
        General Information about the RT system, including RT version and
        plugins
        """
        return self.get("rt")

    def rt_version(self):
        """
        Get RT version.
        """
        response_data = self.rt_info()
        return response_data["Version"]

    def rt_plugins(self):
        """
        Retrieve array of RT plugins.
        """
        response_data = self.rt_info()
        return response_data["Plugins"]

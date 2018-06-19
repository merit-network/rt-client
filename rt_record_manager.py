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

# Constants -----------------------

# Valid record types
RECORD_TYPES = ('ticket', 'queue', 'asset', 'user', 'group',
                'attachment', 'customfield', 'customrole')
# Ticket Statuses
STATUS_TYPES = ('new', 'open', 'stalled', 'resolved', 'rejected', 'deleted')
CLOSED_STATUS = ('resolved', 'rejected', 'deleted')


# Exceptions -----------------------

class UnsupportedError(Exception):
    """Raised by :class:`Record` when any operation not
    currently supported by the RT REST API is requested."""
    pass


# Abstract Record Managers -----------------------

class RecordManager(object):
    def __init__(self, client, record_type):
        """
        Generic Record Manager.

        InvalidRecordException: If the record type is not in RECORD_TYPES.
        """
        if record_type not in RECORD_TYPES:
            raise ValueError("Invalid record type: {}".format(record_type))
        self.record_type = record_type
        self.client = client

    def create(self, attrs, attachments=None):
        """
        Generic record creation.

        Args:
            self.record_type (str): Record type from RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group'.
            attrs (dict): A dictionary of attributes for the record.
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if attachments:
            return self.client.get_v1(
                "{}/new".format(self.record_type),
                content=attrs,
                attachments=attachments
            )
        else:
            return self.client.get(
                self.record_type,
                content=attrs,
            )

    def get(self, record_id):
        """
        Generic record retrieval.

        Args:
            self.record_type (str): Record type from RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group'.
            record_id (str): The id code of the specific record to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.client.get("{}/{}".format(self.record_type, record_id))

    def get_all(self, page=1, per_page=20):
        """
        Generic record archive retrieval.

        Args:
            self.record_type (str): Record type from RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group', 'attachment'
            page (int, optional): The page number, for paginated results.
                Defaults to the first (1) page.
            per_page (int, optional): Number of results per page. Defaults
                to 20 records per page, maximum value of 100.

        Returns:
            JSON dict in the form of the example below:

            {
                "count": 20,
                "page": 1,
                "per_page": 20,
                "total": 3810,
                "items": [
                    {…},
                    {…},
                    …
                ]
            }

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.client.get(
            '{}s/all?page={};per_page={}'.format(self.record_type, page, per_page)
        )

    def update(self, record_id, attrs, attachments=None):
        """"
        Generic record update.

        Args:
            record_id (str): The id code of the specific record to update.
            attrs (dict): A dictionary of attributes with updated values.
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            Array containing a string with confirmation of update.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        # Attatchments are only supported in REST V1
        if attachments:
            return self.client.get_v1(
                "{}/{}/edit".format(self.record_type, record_id),
                content=attrs,
                files=attachments
            )
        else:
            return self.client.put(
                "{}/{}".format(self.record_type, record_id),
                content=attrs
            )

    def delete(self, record_id):
        """
        Generic record deletion.

        Args:
            record_id (str): The id code of the specific record to delete.

        Returns:
            Array containing a string with confirmation of deletion.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.client.delete("{}/{}".format(self.record_type, record_id))

    def search(self, search_terms, page=1, per_page=20):
        """
        Generic record search.

        Args:
            search_terms (array of dict): An array of dicts containing
                the keys "field", "operator" (optional), and "value."
                Example:
                [
                    { "field":    "Name",
                      "operator": "LIKE",
                      "value":    "Engineering" },

                    { "field":    "Lifecycle",
                      "value":    "helpdesk" }
                ]
            page (int, optional): The page number, for paginated results.
                Defaults to the first (1) page.
            per_page (int, optional): Number of results per page. Defaults
                to 20 records per page, maximum value of 100.

        Returns:
            JSON dict in the form of the example below:

            {
                "count": 20,
                "page": 1,
                "per_page": 20,
                "total": 3810,
                "items": [
                    {…},
                    {…},
                    …
                ]
            }

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        search_terms.extend([
            {'field': 'page', 'value': page},
            {'field': 'per_page', 'value': per_page}
        ])
        return self.client.get(
            "{}s".format(self.record_type), content=search_terms
        )

    def history(self, record_id, page=1, per_page=20):
        """
        Generic history retrieval.

        Args:
            record_id (str): The id code of the specific record.
            page (int, optional): The page number, for paginated results.
                Defaults to the first (1) page.
            per_page (int, optional): Number of results per page. Defaults
                to 20 records per page, maximum value of 100.

        Returns:
            JSON dict in the form of the example below:

            {
               "count" : 20,
               "page" : 1,
               "per_page" : 20,
               "total" : 3810,
               "items" : [
                  { … },
                  { … },
                    …
               ]
            }

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.client.get("{}/{}/history?page={};per_page={}".format(
                        self.record_type, the_id, page, per_page))

    def _not_supported_msg(self, operation):
        err_message = "{} is not supported ".format(operation.title())
        err_message += "for record type {} due to RT API limitations.".format(
            self.record_type
        )
        return err_message


class LimitedRecordManager(RecordManager):

    def get_all(self, *args, **kwargs):
        raise UnsupportedError(self._not_supported_msg('get all'))

    def create(self, *args, **kwargs):
        raise UnsupportedError(self._not_supported_msg('create'))

    def update(self, *args, **kwargs):
        raise UnsupportedError(self._not_supported_msg('update'))

    def delete(self, *args, **kwargs):
        raise UnsupportedError(self._not_supported_msg('delete'))

    def history(self, *args, **kwargs):
        raise UnsupportedError(self._not_supported_msg('history'))


# Concrete Record Managers -----------------------

class TicketManager(RecordManager):
    record_type = 'ticket'

    def __init__(self, client):
        self.client = client

    def get_all(self, *args, **kwargs):
        raise UnsupportedError(self._not_supported_msg('get all'))

    def bulk_create(self, data):
        return self.client.post('/tickets/bulk', data)

    def bulk_update(self, data):
        return self.client.put('/tickets/bulk', data)

    def reply(self, ticket_id, attrs, attachments=None):
        """
        Reply to a ticket, include email update to correspondents.

        Args:
            ticket_id (str): The id code of the specific ticket to reply.
            attrs (dict): A dictionary containing keys "Subject", "Content",
                and optionally "Cc" and "Bcc" fields.
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            Array containing a string with confirmation of update.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        # Attatchments are only supported in REST V1
        if attachments:
            content = {
                'id': ticket_id,
                'Action': "correspond",
                'Subject': attrs.get("Subject", None),
                'Text': attrs.get("Content", None),
                'Cc': attrs.get("Cc", None),
                'Bcc': attrs.get("Bcc", None)
            }
            response = self.client.post_v1(
                'ticket/{}/comment'.format(ticket_id),
                content,
                attachments
            )
            return response.text
        else:
            content = {"Action": "Correspond", "ContentType": "text/plain"}
            content.update(attrs)
            return self.client.post(
                'ticket/{}/correspond'.format(ticket_id),
                content
            )

    def comment(self, ticket_id, comment, attachments=None):
        """
        Add a comment to an existing ticket.

        Args:
            ticket_id (str): The id code of the specific ticket to reply.
            comment (str): The string content of the comment to be added.
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            Array containing a string with confirmation of update.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/

        """
        # Attatchments are only supported in REST V1
        if attachments:
            content = {
                'id': ticket_id,
                'Action': "comment",
                'Text': attrs.get("Content", None),
            }
            response = self.client.post_v1(
                'ticket/{}/comment'.format(ticket_id),
                content,
                attachments
            )
            return response.text
        else:
            # Because this endpoint needs a text/plain content type,
            # it calls client.sess.post directly, rather than going through
            # client.post like most other methods.
            response = self.client.sess.post(
                self.client.host + 'ticket/{}/comment'.format(ticket_id),
                data=comment,
                files={'file': attachments},
                headers={"Content-Type": "text/plain"}
            )
            response.raise_for_status()
            return response.json()

    def close(self, ticket_id):
        """
        'Close' a ticket. Note there are only "Resolved" and "Rejected" states.

        Args:
            ticket_id (str): The id code of the specific ticket to close.

        Returns:
            Array containing a string with confirmation of status update.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        # TODO: Ask about how this will be handled ideally.
        return self.update(ticket_id, {"Status": "resolved"})

    def reopen(self, ticket_id):
        """
        Change a ticket's status to open.

        Args:
            ticket_id (str): The id code of the specific ticket to reopen.

        Returns:
            Array containing a string with confirmation of status update.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        # TODO does this need to verify a 'closed' state before changing to open?
        return self.update(ticket_id, {"Status": "open"})

    def change_status(self, ticket_id, new_status):
        """
        Change the a given ticket's status to specified value.

        Args:
            ticket_id (str): The id code of the specific ticket to reopen.
            status (str): A valid ticket state as a string. Valid states
                include: "new", "open", "blocked", "stalled", "resolved", and
                "rejected".

        Returns:
            Array containing a string with confirmation of status update.

        Raises:
            ValueError: If the status does not match a valid existing status.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if new_status in self.STATUS_TYPES:
            return self.update(ticket_id, {"Status": new_status})
        else:
            raise ValueError('Invalid ticket status type {}.'.format(new_status))

    def search(self, search_query, simple_search=False, page=1, per_page=20):
        """
        Search for tickets using TicketSQL.

        Args:
            search_query (str): The query string in TicketSQL.
                Example: '(Status = "new" OR Status = "open") AND Queue = "General"'
                See https://rt-wiki.bestpractical.com/wiki/TicketSQL for more
                detailed information.
            simple_search (bool, optional): When True use simple search syntax,
                when False use TicketSQL.
            page (int, optional): The page number, for paginated results.
                Defaults to the first (1) page.
            per_page (int, optional): Number of results per page. Defaults
                to 20 records per page, maximum value of 100.

        Returns:
            JSON dict in the form of the example below:

            {
               "count" : 20,
               "page" : 1,
               "per_page" : 20,
               "total" : 3810,
               "items" : [
                  { … },
                  { … },
                    …
               ]
            }

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/

        """
        response = self.client.post(
            self.host + 'tickets',
            {
                "query": search_query,
                "simple": 1 if simple_search else 0,
                "page": page,
                "per_page": per_page
            }
        )
        return response.json()


class TransactionManager(LimitedRecordManager):
    record_type = 'transaction'

    def __init__(self, client):
        self.client = client

    def get_attachments(self, transaction_id, page=1, per_page=20):
        """
        Get attachments for transaction.

        Args:
            transaction_id (str): The id code of the specific transaction
                to retrieve.
            page (int, optional): The page number, for paginated results.
                Defaults to the first (1) page.
            per_page (int, optional): Number of results per page. Defaults
                to 20 records per page, maximum value of 100.

        Returns:
            Dictionary with keys 'per_page', 'page', 'total', 'count', and
                'items' which is itself a dict with 'id', '_url', and 'type'.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.client.get(
            "transaction/{}/attachments?page={};per_page={}".format(
                transaction_id,
                page,
                per_page
            )
        )


class AttachmentManager(LimitedRecordManager):
    record_type = 'attachment'

    def __init__(self, client):
        self.client = client

    def file_url(self, attachment_id, ticket_id=None):
        """
        Retrieve direct link to attachment file.

        Args:
            attatchment_id (str): The id code of the specific attachment
                to retrieve.
            ticket_id (str, optional): The id code of the ticket the attatchment
                is connected to.

        Returns:
            String URL for the file location.
        """
        if not ticket_id:
            attach_data = self.attachment_data(attachment_id)
            transaction_id = attach_data['TransactionId']['id']
            ticket_id = self.transaction_get(transaction_id)['Object']['id']
        url = self.base_host
        url += 'Ticket/Attachment/{}/{}'.format(ticket_id, attachment_id)
        return url


class CustomFieldManager(LimitedRecordManager):
    record_type = 'customfield'

    def __init__(self, client):
        self.client = client

    def get_id(self, customfield_name):
        search = self.search(
            [{ "field":    "Name",
               "value":    customfield_name }],
            page=1,
            per_page=1
        )
        if search['count'] != 0:
            return search['items'][0]
        else:
            return None
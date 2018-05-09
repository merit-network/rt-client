# RT Client using Requests

import json
import re
from collections import OrderedDict
from io import StringIO
from tempfile import NamedTemporaryFile

import requests


class InvalidRecordException(Exception):
    """Raised by the :class:`RTClient` when
    an invalid record_type is discovered."""
    pass


class RTClient(object):

    def __init__(self, username, password, base_url, auth_endpoint='NoAuth/Login.html',
                 api_endpoint='REST/2.0/', auth_token=None):
        """
        Args:
            username (str): The user's login username.
            password (str): The user's login password.
            base_url (str): The base URL of the host RT system. e.g 'rt.host.com/'
            auth_endpoint (str): The endpoint to POST Authorization. e.g 'login/'
            api_endpoint (str, optional): The endpoint for the REST API.
                Defaults to 'REST/2.0/'
            auth_token (str, optional): Authentication token from
                the RT::Authen::Token extension. Defaults to None.
        """
        self.sess = requests.Session()
        if auth_token:
            token = 'token {}'.format(auth_token)
            self.sess.post(base_url + auth_endpoint,
                           data={'Authentication': token}, verify=False)
        else:
            self.sess.post(
                base_url + auth_endpoint,
                data={
                    'user': username,
                    'pass': password
                },
                verify=False)

        self.base_host = base_url
        self.host = base_url + api_endpoint
        self.RECORD_TYPES = ('ticket', 'queue', 'asset', 'user', 'group',
                             'attachment', 'customfield', 'customrole')
        self.STATUS_TYPES = ('new', 'open', 'stalled', 'resolved',
                             'rejected', 'deleted')

    # REST V2

    def get(self, url, *args, **kwargs):
        """ Generic GET request to specified URL """
        url = self.host + url
        response = self.sess.get(url, verify=False, *args, **kwargs)
        response.raise_for_status()
        return response.json()

    def post(self, url, content, files=None, *args, **kwargs):
        """ Generic POST request to specified URL """
        url = self.host + url
        response = self.sess.post(
            url,
            json=content,
            files=files,
            headers={"Content-Type": "application/json"},
            *args,
            **kwargs
        )
        response.raise_for_status()
        return response.json()

    def put(self, url,  content, files=None, *args, **kwargs):
        """ Generic PUT request to specified URL """
        url = self.host + url
        response = self.sess.put(
            url,
            json=content,
            files={'file': files},
            headers={"Content-Type": "application/json"},
            *args,
            **kwargs
        )
        response.raise_for_status()
        return response.json()

    def delete(self, url, *args, **kwargs):
        """ Generic DELETE request to specified URL """
        url = self.host + url
        response = self.sess.delete(url, *args, **kwargs)
        response.raise_for_status()
        return response.json()

    # Rest V1

    def post_v1(self, url, content, attachments=[], *args, **kwargs):
        url = self.base_host + '/REST/1.0/' + url

        multipart_form_data = {}

        if attachments:
            attachment_name = ''
            i = 1
            for attachment in attachments:
                # Attachment is file like object
                attachment_name += "%s\n " % attachment.name
                multipart_form_data['attachment_%s' % i] = attachment
                i += 1

            content['Attachment'] = attachment_name

        content_data = ""
        for k, v in content.items():
            v = str(v).replace('\n', '\n  ')
            content_data = content_data + ("{}: {}\n".format(k, v))

        multipart_form_data['content'] = (None, content_data)

        response = self.sess.post(url, files=multipart_form_data,
                                  *args, **kwargs)
        response.parsed = RTParser.parse(response.text)
        response.rt_status = RTParser.parse_status_code(response.text)
        return response

    # Generic REST

    def record_get(self, record_type, record_id):
        """
        Generic record retrieval.

        Args:
            record_type (str): Record type from self.RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group'.
            record_id (str): The id code of the specific record to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            InvalidRecordException: If the record type is not
                in self.RECORD_TYPES.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if record_type in self.RECORD_TYPES:
            return self.get("{}/{}".format(record_type, record_id))
        else:
            err_message = "{} is not a valid record type.".format(record_type)
            raise InvalidRecordException(err_message)

    def record_create(self, record_type, attrs, attachments=None):
        """
        Generic record creation.

        Args:
            record_type (str): Record type from self.RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group'.
            attrs (dict): A dictionary of attributes for the record.
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            json dict of attributes.

        Raises:
            InvalidRecordException: If the record type is not
                in self.RECORD_TYPES.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if record_type in self.RECORD_TYPES:
            if attatchments:
                return self.post_v1(
                    "{}/new".format(record_type),
                    content=attrs,
                    attatchments=attatchments
                )
            else:
                return self.post(
                    record_type,
                    content=attrs,
                )
        else:
            err_message = "{} is not a valid record type.".format(record_type)
            raise InvalidRecordException(err_message)

    def record_delete(self, record_type, record_id):
        """
        Generic record deletion.

        Args:
            record_type (str): Record type from self.RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group'.
            record_id (str): The id code of the specific record to delete.

        Returns:
            Array containing a string with confirmation of deletion.

        Raises:
            InvalidRecordException: If the record type is not
                in self.RECORD_TYPES.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if record_type in self.RECORD_TYPES:
            return self.delete(
                "{}/{}".format(record_type, record_id)
            )
        else:
            err_message = "{} is not a valid record type.".format(record_type)
            raise InvalidRecordException(err_message)

    def record_update(self, record_type, record_id, attrs, attachments=None):
        """"
        Generic record update.

        Args:
            record_type (str): Record type from self.RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group'.
            record_id (str): The id code of the specific record to update.
            attrs (dict): A dictionary of attributes with updated values.
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            Array containing a string with confirmation of update.

        Raises:
            InvalidRecordException: If the record type is not
                in self.RECORD_TYPES.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if record_type in self.RECORD_TYPES:
            # Attatchments are only supported in REST V1
            if attachments:
                return self.post_v1(
                    "{}/{}/edit".format(record_type, record_id),
                    content=attrs,
                    files=attachments
                )
            else:
                return self.put(
                    "{}/{}".format(record_type, record_id),
                    content=attrs
                )
        else:
            err_message = "{} is not a valid record type.".format(record_type)
            raise InvalidRecordException(err_message)

    def record_search(self, record_type, search_terms, page=1, per_page=20):
        """
        Generic record search.

        Args:
            record_type (str): Record type from self.RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group', 'attachment'
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
            InvalidRecordException: If the record type is not
                in self.RECORD_TYPES.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        search_terms.update({'page': page, 'per_page': per_page})
        if record_type in self.RECORD_TYPES:
            return self.post("{}s".format(record_type), content=search_terms)
        else:
            err_message = "{} is not a valid record type.".format(record_type)
            raise InvalidRecordException(err_message)

    # Utility functions

    def _name_or_id(self, the_id, the_name):
        """ Function to validate the presence of a value """
        if not the_name and not the_id:
            raise ValueError("The id and name params cannot both be None.")
        return the_id if the_id else the_name

    # Ticket functionality

    def ticket_get(self, ticket_id, history=False):
        """
        Retrieve a ticket.

        Args:
            record_id (str): The id code of the specific record to delete.
            history (bool, optional): Optional parameter to include the
                ticket history.

        Returns:
            JSON dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/

        Example Output:

        {
           "id":12345,
           "Owner":{
              "id":"Nobody",
              "type":"user",
              "_url":"https://rt.host.com/REST/2.0/user/Nobody"
           },
           "LastUpdatedBy":{
              "id":"tester",
              "type":"user",
              "_url":"https://rt.host.com/REST/2.0/user/tester"
           },
           "Status":"new",
           "TimeLeft":"0",
           "InitialPriority":"0",
           "Due":"1970-01-01T00:00:00Z",
           "Created":"2017-09-28T05:49:28Z",
           "Resolved":"1970-01-01T00:00:00Z",
           "AdminCc":[

           ],
           "FinalPriority":"0",
           "Creator":{
              "id":"tester",
              "type":"user",
              "_url":"https://rt.host.com/REST/2.0/user/tester"
           },
           "Started":"1970-01-01T00:00:00Z",
           "Type":"ticket",
           "EffectiveId":{
              "id":"12345",
              "type":"ticket",
              "_url":"https://rt.host.com/REST/2.0/ticket/12345"
           },
           "CustomFields":{

           },
           "Requestor":[
              {
                 "id":"tester",
                 "type":"user",
                 "_url":"https://rt.host.com/REST/2.0/user/tester"
              }
           ],
           "_hyperlinks":[
              {
                 "ref":"self",
                 "id":"12345",
                 "type":"ticket",
                 "_url":"https://rt.host.com/REST/2.0/ticket/12345"
              },
              {
                 "ref":"history",
                 "_url":"https://rt.host.com/REST/2.0/ticket/12345/history"
              },
              {
                 "ref":"correspond",
                 "_url":"https://rt.host.com/REST/2.0/ticket/12345/correspond"
              },
              {
                 "ref":"comment",
                 "_url":"https://rt.host.com/REST/2.0/ticket/12345/comment"
              }
           ],
           "Subject":"signup notification",
           "TimeEstimated":"0",
           "Starts":"1970-01-01T00:00:00Z",
           "LastUpdated":"2017-09-28T05:49:29Z",
           "TimeWorked":"0",
           "Queue":{
              "id":"34",
              "type":"queue",
              "_url":"https://rt.host.com/REST/2.0/queue/34"
           },
           "Cc":[

           ],
           "Priority":"0"
        }
        """
        resp = self.get("ticket/{}".format(ticket_id))
        if history:
            resp["History"] = self.ticket_history(ticket_id)
        return resp

    def ticket_reply(self, ticket_id, attrs, attachments=None):
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
            response = self.post_v1('ticket/{}/comment'.format(ticket_id),
                                    content, attachments)
            return response.text
        else:
            content = {"Action": "Correspond", "ContentType": "text/plain"}
            content.update(attrs)
            return self.post('ticket/{}/correspond'.format(ticket_id), content)

    def ticket_comment(self, ticket_id, comment, attachments=None):
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
            response = self.post_v1('ticket/{}/comment'.format(ticket_id),
                                    content, attachments)
            return response.text
        else:
            # Because this endpoint needs a text/plain content type,
            # it calls self.sess.post directly, rather than going through
            # self.post like most other methods.
            url = self.host + 'ticket/{}/comment'.format(ticket_id)
            response = self.sess.post(url, data=comment, files={'file': attachments},
                                      headers={"Content-Type": "text/plain"})
            response.raise_for_status()
            return response.json()

    def ticket_create(self, attrs, attachments=None):
        """
        create a ticket; provide JSON content.

        Args:
            attrs (dict): Dictionary of string attributes for the new ticket.
                Example:
                {
                    "Queue": "General",
                    "Subject": "Create ticket test",
                    "From": "user1@example.com",
                    "To": "rt@example.com",
                    "Content": "Testing a create",
                    "CustomFields": {"Severity": "Low"}
                }
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            A JSON dictionary containing "type", "_url", and "id" keys/values
                for the new ticket.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if attatchments:
            return self.post_v1('ticket/new', attrs, attatchments)
        else:
            return self.post("ticket", content=attrs)

    def ticket_update(self, ticket_id, attrs, attachments=None):
        """ update a ticket's metadata; provide JSON content """
        if attatchments:
            return self.post_v1("ticket/{}/edit".format(ticket_id),
                                content=attrs, attachments=attachments)
        else:
            return self.put("ticket/{}".format(ticket_id), content=attrs)

    def ticket_close(self, ticket_id):
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
        return self.ticket_update(ticket_id, {"Status": "resolved"})

    def ticket_reopen(self, ticket_id):
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
        return self.ticket_update(ticket_id, {"Status": "open"})

    def ticket_status(self, ticket_id, status):
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
        if status in self.STATUS_TYPES:
            return self.ticket_update(ticket_id, {"Status": status})
        else:
            raise ValueError('Invalid ticket status type {}.'.format(status))

    def ticket_delete(self, ticket_id):
        """
        Set ticket status to deleted.

        Args:
            ticket_id (str): The id code of the specific ticket to delete.

        Returns:
            Array containing a string with confirmation of status update.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.delete("ticket/{}".format(ticket_id))

    def ticket_history(self, ticket_id, page=1, per_page=20):
        """
        Retrieve list of transactions for ticket.

        Args:
            ticket_id (str): The id code of the ticket history to retrieve.
            page (int, optional): The page number, for paginated results.
                Defaults to the first (1) page.
            per_page (int, optional): Number of results per page. Defaults
                to 20 records per page, maximum value of 100.

        Returns:
            Dictionary containing transactions belonging to the ticket.
            Example:
            {
                "per_page": 20,
                "page": 1,
                "total": 5,
                "count": 5,
                "items": [
                    {
                        "id": "12345",
                        "type": "transaction",
                        "_url": "https://rt.test.com/REST/2.0/transaction/12345"
                    },
                    ...
                ]
            }

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.history_get("ticket", ticket_id, page, per_page)

    def ticket_search(self, search_query, simple_search=False, page=1, per_page=20):
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
        response = self.sess.post(
            self.host + 'tickets',
            {
                "query": search_query,
                "simple": 1 if simple_search else 0,
                "page": page,
                "per_page": per_page  # maximum value is 100
            }
        )
        return response.json()

    # History functionality

    def history_get(self, record_type, the_id, page=1, per_page=20):
        """
        Generic history retrieval.

        Args:
            record_type (str): Record type from self.RECORD_TYPES,
                e.g. 'ticket', 'queue', 'asset', 'user', 'group'.
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
        return self.get("{}/{}/history?page={};per_page={}".format(
                        record_type, the_id, page, per_page))

    def transaction_get(self, transaction_id):
        """
        Get metadata for a transaction.

        Args:
            transaction_id (str): The id code of the specific transaction
                to retrieve.

        Returns:
            Dictionary with keys "Data", "Type", "_hyperlinks", "TimeTaken",
                "Created", and "Object"

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.get("transaction/{}".format(transaction_id))

    def transaction_get_attachments(self, transaction_id, page=1, per_page=20):
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
        return self.get(
            "transaction/{}/attachments?page={};per_page={}".format(
                transaction_id,
                page,
                per_page
            )
        )

    def attachment_data(self, attachment_id):
        """
        Retrieve attachment metadata.

        Args:
            attatchment_id (str): The id code of the specific attachment
                to retrieve.

        Returns:
            A dictionary with keys 'ContentType', 'Headers', 'TransactionId',
                'Subject', 'Parent', 'Creator', 'Created', 'MessageId', 'id',
                'Content' and '_hyperlinks'

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.get("attachment/{}".format(attachment_id))

    def attachment_url(self, attachment_id, ticket_id=None):
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

    # def attachment_download(self, attachment_id, ticket_id=None):
    #     """
    #     Download and serve attachment file.
    #
    #     Args:
    #         attatchment_id (str): The id code of the specific attachment
    #             to retrieve.
    #         ticket_id (str, optional): The id code of the ticket the attatchment
    #             is connected to.
    #
    #     Returns:
    #         The reqested attatchment file for download.
    #     """
    #     download_url = self.attachment_url(attachment_id, ticket_id=ticket_id)
    #     r = self.sess.get(download_url, stream=True)
    #     with NamedTemporaryFile(mode='wb') as the_file:
    #         # Download the attachment
    #         for chunk in r.iter_content(chunk_size=1024):
    #             if chunk: # filter out keep-alive new chunks
    #                 the_file.write(chunk)
    #         # Serve the attachment




    def attatchement_search(self, search_query, page=1, per_page=20):
        """
        Search for attachments matching query.

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
        return self.record_search(
            "attachment",
            search_query,
            page=page,
            per_page=per_page
        )

    # Queue functionality

    def queue_get_all(self, page=1, per_page=20):
        """
        Retrieve list of all queues you can see.

        Args:
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
        return self.get("queues/all?page={};per_page={}")

    def queue_search(self, search_terms, page=1, per_page=20):
        """
        Search for queues using JSON searches syntax.

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
        return self.record_search(
            'queue',
            search_terms,
            page=page,
            per_page=per_page
        )

    def queue_create(self, attrs):
        """
        Create a queue; provide JSON content.

        Args:
            attrs (dict): A dictionary of attributes for the queue.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.post("queue", content=attrs)

    def queue_get(self, queue_id=None, queue_name=None):
        """
        Retrieve a queue by numeric id or name.

        Args:
            queue_id (str, optional): The id code of the specific queue
                to retrieve.
            queue_name (str, optional): The name code of the specific
                queue to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            InvalidRecordException: If the record type is not
                in self.RECORD_TYPES.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_queue = self._name_or_id(queue_id, queue_name)
        return self.get("queue/{}".format(the_queue))

    def queue_update(self, attrs, queue_id=None, queue_name=None):
        """
        Update a queue's metadata; provide JSON content.

        Args:
            queue_id (str, optional): The id code of the specific queue
                to update.
            queue_name (str, optional): The name code of the specific
                queue to update.

        Returns:
            json dict of attributes.

        Raises:
            ValueError: Raised when both queue_id and queue_name have no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_queue = self._name_or_id(queue_id, queue_name)
        return self.put(
            "queue/{}".format(the_queue),
            content=attrs
        )

    def queue_disable(self,  queue_id=None, queue_name=None):
        """
        Disable a queue.

        Args:
            queue_id (str, optional): The id code of the specific queue
                to disable.
            queue_name (str, optional): The name code of the specific
                queue to disable.

        Returns:
            Array containing message with confirmation of deletion.

        Raises:
            ValueError: Raised when both queue_id and queue_name have no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_queue = self._name_or_id(queue_id, queue_name)
        return self.delete("queue/{}".format(the_queue))

    def queue_history(self,  queue_id=None, queue_name=None, page=1, per_page=20):
        """
        Retrieve list of transactions for a given queue.

        Args:
            queue_id (str, optional): The id code of the specific queue
                to retrieve history.
            queue_name (str, optional): The name code of the specific
                queue to retrieve history.
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
            ValueError: Raised when both queue_id and queue_name have no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_queue = self._name_or_id(queue_id, queue_name)
        return self.history_get("queue", the_queue, page, per_page)

    # Catalog functionality

    def catalog_get_all(self, page = 1, per_page = 20):
        """
        Retrieve list of all catalogs you can see.

        Args:
                            ]
            page (int, optional): The page number, for paginated results.
                Defaults to the first (1) page.
            per_page (int, optional): Number of results per page. Defaults
                to 20 catalogs per page.

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
        return self.get("catalogs/all?page={};per_page={}".format(page, per_page))

    def catalog_search(self, search_terms, page = 1, per_page = 20):
        """
        Search for catalogs using JSON searches syntax

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
        return self.record_search(
            'catalog',
            search_terms,
            page = page,
            per_page = per_page  # maximum value is 100
        )

    def catalog_create(self, attrs):
        """
        Create a catalog; provide JSON content.

        Args:
            attrs (dict): A dictionary of attributes for the catalog.

        Returns:
            Array containing message with confirmation of creation.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.post("catalog", content = attrs)

    def catalog_get(self, catalog_id = None, catalog_name = None):
        """
        Retrieve a catalog by numeric id or name.

        Args:
            catalog_id (str, optional): The id code of the specific catalog
                to retrieve.
            catalog_name (str, optional): The name code of the specific
                catalog to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            ValueError: Raised when both catalog_id and catalog_name have
                no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_catalog=self._name_or_id(catalog_id, catalog_name)
        return self.get("catalog/{}".format(the_catalog))

    def catalog_update(self,  attrs, catalog_id = None,
                       catalog_name = None):
        """
        Update a catalog's metadata; provide JSON content.

        Args:
            attrs (dict): A dictionary of attribute changes for the catalog.
            catalog_id (str, optional): The id code of the specific catalog
                to retrieve.
            catalog_name (str, optional): The name code of the specific
                catalog to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            ValueError: Raised when both catalog_id and catalog_name have
                no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_catalog=self._name_or_id(catalog_id, catalog_name)
        return self.put(
            "catalog/{}".format(the_catalog),
            content=attrs
        )

    def catalog_disable(self,  catalog_id=None, catalog_name=None):
        """
        Disable a catalog.

        Args:
            catalog_id (str, optional): The id code of the specific catalog
                to retrieve.
            catalog_name (str, optional): The name code of the specific
                catalog to retrieve.

        Returns:
            Array containing message with confirmation of deletion.

        Raises:
            ValueError: Raised when both catalog_id and catalog_name have
                no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_catalog = self._name_or_id(catalog_id, catalog_name)
        return self.delete("catalog/{}".format(the_catalog))

    # Asset functionality

    def asset_search(self, search_terms, page=1, per_page=20):
        """
        Search for assets using JSON searches syntax .

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
        return self.record_search(
            'asset',
            search_terms,
            page=page,
            per_page=per_page  # maximum value is 100
        )

    def asset_create(self, attrs, attachments):
        """
        Create a asset; provide JSON content.

        Args:
            attrs (dict): A dictionary of attributes for the asset.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/

        """
        if attachment:
            return self.post_v1(
                "asset/new",
                content=attrs,
                files=attachments
            )
        else:
            return self.post("asset", content=attrs)

    def asset_get(self, asset_id):
        """
        Retrieve an asset.

        Args:
            asset_id (str): The id code of the specific asset to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.get("asset/{}".format(asset_id))

    def asset_update(self,  asset_id, attrs, attachments=None):
        """
        Update a asset's metadata; provide JSON content.

        Args:
            asset_id (str): The id code of the specific asset to delete.
            attrs (dict): A dictionary of attributes with updated values.
            attachments (array, optional): Files to attach. Defaults to None.

        Returns:
            Array containing a string with confirmation of update.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        if attatchments:
            return self.post_v1(
                "asset/{}/edit".format(asset_id),
                content=attrs,
                attachments=attachments
            )
        else:
            return self.put(
                "asset/{}".format(asset_id),
                content=attrs,
                files=attachments
            )

    def asset_delete(self,  asset_id):
        """
        Set status to deleted.

        Args:
            asset_id (str): The id code of the specific asset to delete.

        Returns:
            Array containing a string with confirmation of deletion.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/

        """
        return self.delete("asset/{}".format(asset_id))

    def asset_history(self, asset_id, page=1, per_page=20):
        """
        Retrieve list of transactions for asset.

        Args:
            asset_id (str): The id code of the specific asset
                to retrieve history.
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
        return self.history_get("asset", asset_id, page, per_page)

    # User functionality

    def user_search(self, search_terms, page=1, per_page=20):
        """
        Search for users using JSON searches syntax.

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
        return self.record_search(
            'user',
            search_terms,
            page=page,
            per_page=per_page
        )

    def user_create(self, attrs):
        """
        Create a user; provide JSON content.

        Args:
            attrs (dict): A dictionary of attributes for the user.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/

        """
        return self.post(
            "user",
            content=attrs
        )

    def user_get(self, user_id=None, user_name=None):
        """
        Retrieve a user by numeric id or name.

        Args:
            user_id (str, optional): The id code of the specific user
                to retrieve.
            user_name (str, optional): The name code of the specific
                user to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            ValueError: Raised when both user_id and user_name have no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_user = self._name_or_id(user_id, user_name)
        return self.get("user/{}".format(the_user))

    def user_update(self,  attrs, user_id=None, user_name=None):
        """
        Update a user's metadata; provide JSON content.

        Args:
            attrs (dict): A dictionary of attributes with updated values.
            user_id (str, optional): The id code of the specific user
                to retrieve.
            user_name (str, optional): The name code of the specific
                user to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            ValueError: Raised when both user_id and user_name have no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_user = self._name_or_id(user_id, user_name)
        return self.put(
            "user/{}".format(the_user),
            content=attrs
        )

    def user_disable(self,  user_id=None, user_name=None):
        """
        Disable a user.

        Args:
            user_id (str, optional): The id code of the specific user
                to delete.
            user_name (str, optional): The name code of the specific
                user to delete.

        Returns:
            Array containing message with confirmation of deletion.

        Raises:
            ValueError: Raised when both user_id and user_name have no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_user = self._name_or_id(user_id, user_name)
        return self.delete("user/{}".format(the_user))

    def user_history(self, user_id=None, user_name=None, page=1, per_page=20):
        """
        Retrieve list of transactions for user.

        Args:
            user_id (str, optional): The id code of the specific user
                to retrieve history.
            user_name (str, optional): The name code of the specific
                user to retrieve history.
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
            ValueError: Raised when both user_id and user_name have no value.
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        the_user = self._name_or_id(user_id, user_name)
        return self.history_get("user", the_user, page, per_page)

    # Groups functionality

    def group_search(self, search_terms, page=1, per_page=20):
        """
        Search for groups using JSON searches syntax.

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
        return self.record_search(
            'group',
            search_terms,
            page=page,
            per_page=per_page  # maximum value is 100
        )

    def group_get(self, group_id):
        """
        Retrieve a group.

        Args:
            group_id (str): The id code of the specific group to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.get("group/{}".format(group_id))

    def group_history(self,  group_id, page=1, per_page=20):
        """
        Retrieve list of transactions for group.

        Args:
            group_id (str, optional): The id code of the specific group
                to retrieve history.
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
        return self.history_get("group", group_id, page, per_page)

    # Custom Field functionality

    def customfield_search(self, search_terms, page=1, per_page=20):
        """
        Search for custom fields using JSON searches syntax.

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
        return self.record_search(
            'customfield',
            search_terms,
            page=page,
            per_page=per_page  # maximum value is 100
        )

    def customfield_get(self, customfield_id):
        """
        Retrieve a custom field.

        Args:
            customfield_id (str): The id code of the specific field to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.get("customfield/{}".format(customfield_id))

    # Custom Roles functionality

    def customrole_search(self, search_terms, page=1, per_page=20):
        """
        Search for custom roles using JSON searches syntax.

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
        return self.record_search(
            'customrole',
            search_terms,
            page=page,
            per_page=per_page  # maximum value is 100
        )

    def customrole_get(self, customrole_id):
        """
        Retrieve a custom role.

        Args:
            customrole_id (str): The id code of the specific role to retrieve.

        Returns:
            json dict of attributes.

        Raises:
            See Python Requests docs at
                http://docs.python-requests.org/en/master/_modules/requests/exceptions/
        """
        return self.get("customrole/{}".format(customrole_id))

    # System Information functionality

    def rt_info(self):
        """
        General Information about the RT system, including RT version and
        plugins
        """
        response = self.sess.get('rt')
        response.raise_for_status()
        return response.json()

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


class RTParser(object):
    """ Modified version from python-rtkit.
        Apache Licensed, Copyright 2011 Andrea De Marco.
        See: https://github.com/z4r/python-rtkit/blob/master/rtkit/parser.py"""
    """ RFC5322 Parser - see https://tools.ietf.org/html/rfc5322"""

    HEADER = re.compile(r'^RT/(?P<v>.+)\s+(?P<s>(?P<i>\d+).+)')
    COMMENT = re.compile(r'^#\s+.+$')
    SYNTAX_COMMENT = re.compile(r'^>>\s+.+$')
    SECTION = re.compile(r'^--', re.M | re.U)

    @classmethod
    def parse(cls, body):
        """ :returns: A list of RFC5322-like section
        """
        section = cls.build(body)
        return [cls.decode(lines) for lines in section]

    @classmethod
    def parse_status_code(cls, body):
        try:
            header = body.splitlines()[0]
            status_code = header.split(' ')[1]
            return int(status_code)
        except:
            return False

    @classmethod
    def decode(cls, lines):
        """:return: A dict parsing 'k: v' and skipping comments """
        # try:
        data_dict = OrderedDict()
        key = None
        for line in lines:
            if not cls.COMMENT.match(line):
                print(line)
                if ':' not in line:
                    value = line.strip(' ')
                    data_dict[key] = data_dict[key] + value
                else:
                    key, value = line.split(':', 1)
                    value = value.strip(' ')
                    data_dict[key] = value
        return data_dict
        # except (ValueError, IndexError):
        #    return {}

    @classmethod
    def build(cls, body):
        """Build logical lines from a RFC5322-like string"""
        def build_section(section):
            logic_lines = []
            for line in section.splitlines():
                # Nothing in line or line in header
                if not line or cls.HEADER.match(line):
                    continue
                if line[0].isspace():
                    logic_lines[-1] += '\n' + line.strip(' ')
                else:
                    logic_lines.append(line)
            return logic_lines

        section_list = []
        for section in cls.SECTION.split(body):
            section_list.append(build_section(section))
        return section_list

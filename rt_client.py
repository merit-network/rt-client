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

import json
import re
from collections import OrderedDict
from io import StringIO
from tempfile import NamedTemporaryFile

import requests

from rt_record_manager import (AttachmentManager, CustomFieldManager,
                               LimitedRecordManager, RecordManager,
                               TicketManager, TransactionManager)

# Client Class -----------------------

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

        # Special Records
        self.ticket = TicketManager(self)
        self.transaction = TransactionManager(self)
        self.attachment = AttachmentManager(self)
        self.customfield = CustomFieldManager(self)

        # Fully supported records
        for full_record in ['queue', 'catalog', 'asset', 'user']:
            setattr(self, full_record,  RecordManager(self, full_record))

        # Partially supported records
        for limited_record in ['group', 'customrole']:
            setattr(self, limited_record,
                    LimitedRecordManager(self, limited_record))

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

    def post_v1(self, url, content, attachments=None, *args, **kwargs):
        """
        POST using the v1 RT REST API - this is only necessary for attachments
        """
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

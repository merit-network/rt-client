rt-client
#########

The RT Client is a python library for interfacing with RT's REST API. The
client uses `python-requests <http://docs.python-requests.org/en/master/>`_
and talks to the `V2 <https://github.com/bestpractical/rt-extension-rest2>`_ API.

In the future we also intend to add a CLI which will use the library and offer
a nice way of interacting with RT from the commandline based on the features
the V2 API gives us.

Getting Started
***************

.. code-block:: python

  from rt_client.client import Client

  rt = Client(
      username="jsmith",
      password="supersecret",
      endpoint="https://rt.acme.org/",
  )

  tickets = rt.ticket.search("Queue='urgent'")

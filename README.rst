rt-client
#########

The RT Client is a python library for interfacing with RT's REST API. The
client uses `python-requests <http://docs.python-requests.org/en/master/>`_
and talks to the `V2 <https://github.com/bestpractical/rt-extension-rest2>`_ API.

Sadly though the base API at present isn't feature complete and is in fact
lacking some major functionality, as such we actually have based this client
on our fork, which contains a collection of pull requests for the main API
extension that have not yet been merged:
https://github.com/catalyst-cloud/rt-extension-rest2/tree/catalyst-v1.06b

We will update the client as and when the official extension is updated to
match but until then know that our fork (and this client) are more feature
complete.

In the future we also intend to add a CLI which will use the library and offer
a nice way of interacting with RT from the commandline based on the features
the V2 API gives us.
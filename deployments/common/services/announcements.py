import argparse
import datetime
import json
import os
import sys
from collections import defaultdict
import re
import uuid

from tornado import escape, ioloop, web

from jupyterhub.services.auth import HubOAuthenticated, HubOAuthCallbackHandler

# ----------------------------------------------------------------------

# Inline HTML styling functions to avoid need to use client-side CSS
# and image update workflows.  Styling can be changed just by editing
# this code and restarting the announcement service / jupyterhub
# vs. updating the client package and then
# rebuilding/pushing/restarting the notebook image and server.


def level(s):
    return style_str(f"font-weight: bold; align: center; color: {s};")


def style_str(s):
    return f'style="{s}"'


def lstyle(klass):
    return STYLE.get(klass, "")


STYLE = {
    ".stsci.debug": level("brown"),
    ".stsci.info": level("#5c85d6"),
    ".stsci.warning": level("orange"),
    ".stsci.error": level("darkred"),
    ".stsci.critical": level("red"),
    ".stsci.time": style_str("color: darkgreen;"),
    ".stsci.message": style_str("color: black;"),
    ".stsci.header": style_str("color: black; font-size: 1.2em; text-align: left;"),
}

# ----------------------------------------------------------------------

# HTML funcs which are used to create a multi-part tabular announcement string.
# This keeps the announcement formatting here where it is easier to change.


def div(s):
    return "".join(["<div>"] + s + ["</div>"])


def table(s):
    return "".join(["<table>"] + s + ["</table>"])


def th(*s, style=".stsci.header"):
    return ["<th>"] + [td(i, style) for i in s] + ["</th>"]


def tr(*s):
    return ["<tr>"] + [td(i) for i in s] + ["</tr>"]


def td(s, style=""):
    return f"<td {lstyle(style)}>{s}</td>"


def p(s, style=""):
    return f"<p {lstyle(style)}>{s}</p>"


def br():
    return "<br/>"


# ----------------------------------------------------------------------


def now():
    return datetime.datetime.now().isoformat()


def wlog(*args):
    return  # logging is disabled because it is blocking and will stall tornado
    print(*args)
    sys.stdout.flush()


# ----------------------------------------------------------------------

ANNOUNCEMENTS = defaultdict(list)

SYSTEM_USERS = ["efs-quota", "announcement"]

MESSAGE_Q_LEN = 5


class AnnouncementRequestHandler(HubOAuthenticated, web.RequestHandler):
    """Dynamically manage page announcements"""

    def _check_admin_user(self):
        username = self.get_current_user()["name"]
        if username not in SYSTEM_USERS:
            raise web.HTTPError(404)

    @web.authenticated  # but only accessible to the service user
    def post(self):
        """Update announcement"""
        self._check_admin_user()
        doc = escape.json_decode(self.request.body)
        username = doc["username"]
        timestamp = doc.get("timestamp", now())
        replace = doc.get("replace", None)
        if replace:
            user_messages = list(ANNOUNCEMENTS[username])
            for message in user_messages:
                if re.search(replace, message[3]):
                    ANNOUNCEMENTS[username].remove(message)
        message = (username, timestamp, doc["level"], doc["announcement"])
        ANNOUNCEMENTS[username].append(message)
        if len(ANNOUNCEMENTS[username]) > MESSAGE_Q_LEN:
            ANNOUNCEMENTS[username] = ANNOUNCEMENTS[username][1:]  # drop oldest message
        self.write_to_json(message)

    def prepare(self):
        wlog(self.request)

    @web.authenticated
    def get(self):
        """Retrieve announcement"""
        g_popup, global_table_str = self._announcements("system", "System")

        # From notebook or cmd line client API token
        username = self.get_current_user()["name"]

        # cmd line client can specify which user to pull
        if username in SYSTEM_USERS:
            username = self.request.uri.split("/")[-1]
        if username == "all":
            raise web.HTTPError(
                status_code=400,
                log_message="Bad request:  username==all is not supported for GET",
            )

        u_popup, user_table_str = self._announcements(username, f"User {username}")

        wlog("global_table_str:", global_table_str)
        wlog("user_table_str:", user_table_str)

        if global_table_str and user_table_str:
            global_table_str += "<br/>"

        storage = dict(
            announcement=global_table_str + user_table_str,
            timestamp=now(),
            user=username,
            popup=g_popup or u_popup,
        )

        self.write_to_json(storage)

    def _announcements(self, user, title):
        messages = []
        popup = False
        for message in ANNOUNCEMENTS[user]:
            if message[2].lower() in ["warning", "error", "critical"]:
                popup = True
            messages.extend(self._format_message(*message))
        if messages:
            return popup, table([p(title, style=".stsci.header")] + messages)
        else:
            return popup, ""

    def _format_message(self, username, time, level, msg):
        return tr(
            td(time.split(".")[0], style=".stsci.time"),
            td(f"{level.upper()}", style=f".stsci.{level.lower()}"),
            td(msg, style=".stsci.message"),
        )

    @web.authenticated
    def delete(self):
        """Clear announcement"""
        global ANNOUNCEMENTS
        self._check_admin_user()
        username = self.request.uri.split("/")[-1]
        if username == "all":
            ANNOUNCEMENTS = defaultdict(list)
        else:
            ANNOUNCEMENTS[username] = []
        self.write_to_json([username])

    def write_to_json(self, doc):
        """Write dictionary document as JSON"""
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        s = escape.utf8(json.dumps(doc))
        self.write(s)
        wlog(s)


# ----------------------------------------------------------------------


def main():
    args = parse_arguments()
    application = create_application(**vars(args))
    application.listen(args.port)
    ioloop.IOLoop.current().start()


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-prefix",
        "-a",
        default=os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/"),
        help="application API prefix",
    )
    parser.add_argument(
        "--port", "-p", default=8888, help="port for API to listen on", type=int
    )
    return parser.parse_args()


def create_application(api_prefix=r"/", handler=AnnouncementRequestHandler, **kwargs):
    return web.Application(
        [
            (api_prefix, handler),
            (api_prefix + r"oauth_callback/?.*", HubOAuthCallbackHandler),
            (api_prefix + r"latest/?.*", handler),
        ],
        cookie_secret=str(uuid.uuid4()).encode("utf-8"),
    )


if __name__ == "__main__":
    main()

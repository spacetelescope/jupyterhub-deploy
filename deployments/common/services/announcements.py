import os
import sys
import asyncio
import argparse
import datetime
import json
import re
import uuid
import time
import pickle
from collections import defaultdict
from functools import partial

from tornado import escape, web

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

SYSTEM_USERS = ["efs-quota", "announcement"]

MESSAGE_Q_LEN = 5


class Message:
    def __init__(self, username, timestamp, expires, level, message):
        self.username = username
        self.timestamp = timestamp
        self.expires = expires
        self.level = level
        self.message = message


def dt_from_iso(iso):
    return datetime.datetime.fromisoformat(iso.split(".")[0])


def delta_from_spec(spec):
    days = int(spec.split("-")[0], 10) if "-" in spec else 0
    hms = spec.split("-")[1] if "-" in spec else spec
    hours, minutes, seconds = map(int, hms.split(":"))
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


class Announcements:
    def __init__(self, savefile):
        self.savefile = savefile
        self.store = None
        self.dirty = False
        self.load()

    def load(self):
        try:
            wlog(f"Loading {self.savefile}...")
            with open(self.savefile, "rb") as file:
                self.store = pickle.load(file)  # nosec
            wlog(f"Loaded {self.savefile}.")
            self.dirty = False
        except Exception:
            wlog(f"Loading {self.savefile} failed.  Clearing all.")
            self.store = defaultdict(list)
            self.dirty = True

    def save(self):
        wlog(f"Saving {self.savefile}...")
        with open(self.savefile, "wb+") as file:
            pickle.dump(self.store, file)
        wlog(f"Saved {self.savefile}.")
        self.dirty = False

    def clear(self, username, clear_regex=".*"):
        usernames = self.store.keys() if username == "all" else [username]
        for username in usernames:
            for msg in list(self.store[username]):
                if re.search(clear_regex, msg.message):
                    self.store[username].remove(msg)
                    self.dirty = True

    def put(self, username, message):
        self.store[username].append(message)
        self.rotate(username)
        self.dirty = True

    def rotate(self, username, q_len=MESSAGE_Q_LEN):
        if len(self.store[username]) > q_len:
            self.store[username] = self.store[username][1:]  # drop oldest message
            self.dirty = True

    def remove_expired(self):
        now = datetime.datetime.now()
        for user, messages in self.store.items():
            for msg in list(messages):
                timestamp = dt_from_iso(msg.timestamp)
                expires = delta_from_spec(msg.expires)
                if timestamp + expires <= now:
                    messages.remove(msg)
                    self.dirty = True

    def get(self, username):
        g_popup, global_table_html = self.html("system", "System")
        u_popup, user_table_html = self.html(username, f"User {username}")
        if global_table_html and user_table_html:
            global_table_html += "<br/>"
        return g_popup or u_popup, global_table_html + user_table_html

    def html(self, user, title):
        messages = []
        popup = False
        for msg in self.store[user]:
            if msg.level.lower() in ["warning", "error", "critical"]:
                popup = True
            messages.extend(self._format_message(msg.timestamp, msg.level, msg.message))
        html = table([p(title, style=".stsci.header")] + messages) if messages else ""
        wlog(f"announcement{title}: {popup} - {html}")
        return popup, html

    def _format_message(self, time, level, msg):
        return tr(
            td(time.split(".")[0], style=".stsci.time"),
            td(f"{level.upper()}", style=f".stsci.{level.lower()}"),
            td(msg, style=".stsci.message"),
        )


# ----------------------------------------------------------------------

ANNOUNCEMENTS = Announcements("/announcements/messages.pkl")


class AnnouncementRequestHandler(HubOAuthenticated, web.RequestHandler):
    """Dynamically manage page announcements"""

    def prepare(self):
        wlog(self.request)

    def _check_admin_user(self):
        username = self.get_current_user()["name"]
        if username not in SYSTEM_USERS:
            raise web.HTTPError(404)

    @property
    def username(self):
        return self.request.uri.split("/")[-1]

    @web.authenticated  # but only accessible to the service user
    def post(self):
        """Update announcement"""
        self._check_admin_user()
        doc = escape.json_decode(self.request.body)
        username = doc["username"]
        timestamp = doc.get("timestamp", now())
        expires = doc.get("expires", "2-00:00:00")
        replace = doc.get("replace", None)
        if replace:
            ANNOUNCEMENTS.clear(username, replace)
        msg = Message(username, timestamp, expires, doc["level"], doc["announcement"])
        ANNOUNCEMENTS.put(username, msg)
        self.write_to_json(msg.__dict__)

    @web.authenticated
    def get(self):
        """Retrieve announcement"""
        # From notebook or cmd line client API token
        username = self.get_current_user()["name"]
        # cmd line client can specify which user to pull
        if username in SYSTEM_USERS:
            username = self.username
        if username == "all":
            raise web.HTTPError(
                status_code=400,
                log_message="Bad request:  username==all is not supported for GET",
            )
        popup, html = ANNOUNCEMENTS.get(username)
        storage = dict(
            announcement=html,
            timestamp=now(),
            user=username,
            popup=popup,
        )
        self.write_to_json(storage)

    @web.authenticated
    def delete(self):
        """Clear announcement"""
        self._check_admin_user()
        ANNOUNCEMENTS.clear(self.username)
        self.write_to_json([self.username])

    def write_to_json(self, doc):
        """Write dictionary document as JSON"""
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        s = escape.utf8(json.dumps(doc))
        self.write(s)
        wlog(s)


# ----------------------------------------------------------------------


def persist_thread():
    """Periodically check to see if any messages should expire or the contents
    of ANNOUNCEMENTS have otherwise changed.   This function is blocking on
    sleep and a write to disk so it will stall whatever event loop it runs
    in.
    """
    while True:
        time.sleep(10)
        ANNOUNCEMENTS.remove_expired()
        if ANNOUNCEMENTS.dirty:
            ANNOUNCEMENTS.save()


async def call_blocking(func, *args, **keys):
    """Run the specified synchronous function in a background thread
    so that it doesn't stall the main thread during its blocks.
    """
    binding = partial(func, *args, **keys)
    binding.__doc__ = f"partial: {func.__doc__}"
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, binding)


async def announce_persist():
    """Create a simple async function which can be called by gather()."""
    await call_blocking(persist_thread)


# ----------------------------------------------------------------------


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


async def announce_handler_main():
    args = parse_arguments()
    app = create_application(**vars(args))
    app.listen(args.port)
    shutdown = asyncio.Event()
    await shutdown.wait()


# ----------------------------------------------------------------------


async def main():
    await asyncio.gather(announce_handler_main(), announce_persist())


if __name__ == "__main__":
    asyncio.run(main())

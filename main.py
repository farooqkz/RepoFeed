import hmac
import codecs
import pickle
from dataclasses import dataclass
from typing import Union
from datetime import datetime

from flask import Flask
from flask import request
from flask import Response
from flask import g
import lmdb
import rfeed

app = Flask(__name__)

LATEST_N = 12


@dataclass(eq=False)
class GitEvent:
    json: dict
    type_: Union[str, None] = None
    link: str = ""

    def __post_init__(self):
        self.type_ = self._detectType()
        self.type_func = dict(
            issue=self.generate_for_issue, pull_request=self.generate_for_pr
        )
        self.pubDate = datetime.now()

    def _detectType(self):
        if "issue" in self.json:
            return "issue"
        elif "pull_request" in self.json:
            return "pull_request"
        return None  # means unsupported type

    @property
    def text(self):
        if self.type_:
            return self.type_func[self.type_]()
        return None

    @property
    def author(self):
        if self.type_:
            return self.json[self.type_]["user"]["login"]
        return None

    @property
    def avatar(self):
        return self.json["sender"]["avatar_url"]

    def generate_for_issue(self):
        user = self.json["issue"]["user"]["login"]
        action = self.json["action"]
        issue_title = self.json["issue"]["title"]
        body = ""
        comment = ""
        if "comment" in self.json:
            body = self.json["comment"].get("body", "")
            comment = "comment"
            self.link = self.json["comment"]["html_url"]
        else:
            body = self.json["issue"].get("body", "")
            self.link = self.json["issue"]["html_url"]

        return f"{user} {action} {comment} for issue {issue_title}: {body}"

    def generate_for_pr(self):
        user = self.json["pull_request"]["user"]["login"]
        action = self.json["action"]
        if action == "closed" and self.json.get("merged", False):
            action = "merged"
        title = self.json["pull_request"].get("title", "")
        body = self.json["pull_request"].get("body", "")
        self.link = self.json["pull_request"]["html_url"]

        return f'{user} {action} "{title}": {body}'


def get_secret():
    secret = getattr(g, "_secret", None)
    if secret is None:
        with open("secret") as fp:
            secret = g._secret = fp.read().encode()
    return secret


def get_latest():
    with get_env().begin() as txn:
        count = txn.stat()["entries"]
        start = max(count - LATEST_N, 0)
        for i in range(start, count):
            yield pickle.loads(txn.get(str(i).encode()))


def get_env():
    env = getattr(g, "_env", None)
    if env is None:
        env = g._env = lmdb.open("db")
    return env


def add_event(json):
    event = GitEvent(json)
    if event.type_ is None:
        return

    with get_env().begin(write=True) as txn:
        count = txn.stat()["entries"]
        txn.put(str(count).encode(), pickle.dumps(event))
        txn.delete(str(count - LATEST_N).encode())


@app.route("/ghrss", methods=("POST",))
def hook():
    if not request.is_json:
        print("Request is not JSON :(")
        abort(404)
    if request.headers.get("X-Hub-Signature-256"):
        hex_digest0 = request.headers.get("X-Hub-Signature-256").split("=")[1]
        hex_digest1 = codecs.encode(
            hmac.digest(get_secret(), request.get_data(), "sha256"), "hex"
        ).decode()
        if hex_digest1 == hex_digest0:
            add_event(request.json)
        else:
            print("digests are not equal:", hex_digest1, hex_digest0)

    return dict(ok="O.K.")


@app.route("/ghrss/feed", methods=("GET",))
def feed():
    return Response(
        rfeed.Feed(
            title="Github",
            description="Github",
            link="https://github.com/smal1378/Bank-3992",
            items=(
                rfeed.Item(
                    title=x.text,
                    description=x.text,
                    author=x.author,
                    link=x.link,
                    pubDate=x.pubDate,
                )
                for x in get_latest()
            ),
        ).rss(),
        mimetype="text/xml",
    )

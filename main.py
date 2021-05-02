import hmac
import codecs

from flask import Flask
from flask import request
from flask import g
import lmdb

app = Flask(__name__)


class Event2HR:
    def __init__(self, json):
        self.json = json
        self.type = self._detectType()

    def _detectType(self):
        types = (
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
            "issues",
            "fork",
            "issue_comment",
        )
        for type_ in types:
            if type_ in self.json:
                return type_
        return None

    def generate_HR_text(self):
        ...

    def generate_for_issues(self):
        user = self.json["issue"]["user"]["login"]
        action = self.json["action"]
        title = self.json["issue"]["title"]
        body = self.json["issue"]["body"]

        return f'{user} {action} "{title}": {body}'

    def generate_for_prs(self):
        user = self.json["pull_request"]["user"]["login"]
        action = self.json["action"]
        if action == "closed" and self.json["merged"]:
            action = "merged"
        title = self.json["pull_request"]["title"]
        title = self.json["pull_request"]["body"]

        return f'{user} {action} "{title}": {body}'

    def generate_for_prs_review(self):
        ...

    def generate_for_prs_review_comment(self):
        ...

    def generate_for_fork(self):
        return ""


def get_secret():
    secret = getattr(g, "_secret", None)
    if secret is None:
        with open("secret") as fp:
            secret = g._secret = fp.read().encode()
    return secret


def get_latest(n=10):
    with get_env().begin() as txn:
        cursor = txn.cursor()
        count = txn.stat()["entries"]
        start = max(count - n, 0)
        for i in range(start, count):
            yield txn.get(f"{i}")


def get_env():
    env = getattr(g, "_env", None)
    if env is None:
        env = g._env = lmdb.open("db")
    return env


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
            print(request.json)
        else:
            print("digests are not equal:", hex_digest1, hex_digest0)

    return dict(ok="O.K.")

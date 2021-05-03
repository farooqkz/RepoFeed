import hmac
import codecs
from dataclasses import dataclass
from typing import Union

from flask import Flask
from flask import request
from flask import g
import lmdb

app = Flask(__name__)

LATEST_N = 12

def detectType(json):

@dataclass(eq=False)
class Event2HumanReadable:
    json: dict
    type_: Union[str, NoneType]
    type_func: dict = dict(issue=self.generate_for_issue, pull_request=self.generate_for_pr)

    def __post_init__(self):
        self.type_ = self._detectType()

    def _detectType(self):
        if "issue" in self.json:
            return "issue"
        elif "pull_request" in self.json:
            return "pull_request"
        return None # means unsupported type

    def generate_HR_text(self):
        if self.type_:
            return self.type_func[self.type]()
        return None
    
    def generate_for_issue(self):
        user = self.json["issue"]["user"]["login"]
        action = self.json["action"]
        issue_title = self.json["issue"]["title"]
        body = ""
        comment = ""
        if "comment" in self.json:
            body = self.json["comment"].get("body", "")
            comment = "comment"
        else:
            body = self.json["issue"].get("body", "")

        return f'{user} {action} {comment} for issue {issue_title}: {body}'

    def generate_for_pr(self):
        user = self.json["pull_request"]["user"]["login"]
        action = self.json["action"]
        if action == "closed" and self.json.get("merged", False):
            action = "merged"
        title = self.json["pull_request"].get("title", "")
        title = self.json["pull_request"].get("body", "")

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
            yield txn.get(f"{i}")


def get_env():
    env = getattr(g, "_env", None)
    if env is None:
        env = g._env = lmdb.open("db")
    return env

def add_action(json):
    text = Event2HumanReadable(json).get_HR_text()
    if not text:
        return
    
    text = text.encode()
    with get_env().begin() as txn:
        count = txn.stat()["entries"]
        txn.put(str(count+1).encode(), text)
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
            add_action(request.json)    
        else:
            print("digests are not equal:", hex_digest1, hex_digest0)

    return dict(ok="O.K.")

@app.route("/ghrss/feed", methods=("GET",))
def feed():


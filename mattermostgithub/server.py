import json
import hmac
import hashlib
import requests
from flask import request

try:
    from mattermostgithub import config
except ImportError:
    print("Could not import config. Using test-config instead.")
    from tests import config

from mattermostgithub.payload import (
    PullRequest, PullRequestReview, PullRequestComment, Issue, IssueComment,
    Repository, Branch, Push, Tag, CommitComment, Wiki, Status
)

from mattermostgithub import app

SECRET = hmac.new(config.SECRET.encode('utf8'), digestmod=hashlib.sha1) if config.SECRET else None
EVENTS = {'git:push:0.1': 'Git push', 'merge-proposal:0.1': 'Merge proposal', 'bug:0.1': 'Bug', 'bug:comment:0.1': 'Bug Comment'}
MP_ATTRIBUTES = ['registrant', 'source_branch', 'source_git_repository', 'source_git_path', 'target_branch', 'target_git_repository', 'target_git_path', 'prerequisite_branch', 'prerequisite_git_repository', 'prerequisite_git_path', 'queue_status', 'commit_message', 'whiteboard', 'description', 'preview_diff', 'preview_diff']

@app.route(config.SERVER['hook'] or "/", methods=['POST'])
def root():
    if request.json is None:
        print('Invalid Content-Type')
        return 'Content-Type must be application/json and the request body must contain valid JSON', 400

    # if SECRET:
    #     signature = request.headers.get('X-Hub-Signature', None)
    #     sig2 = SECRET.copy()
    #     sig2.update(request.data)
    #
    #     print('secret:', sig2.hexdigest())
    #     print('signature:', signature)
    #
    #     if signature is None or sig2.hexdigest() != signature.split('=')[1]:
    #         return 'Invalid or missing X-Hub-Signature', 400

    data = request.json
    headers = request.headers
    # print(headers)
    print(data)
    
    event = EVENTS.get(headers.get('X-Launchpad-Event-Type'))
    if event is None:
        event = "Unknown"
    print(event)

    msg = ""
    if event == 'Git push':
        path = data.get("git_repository_path", None)
        ref = data.get("ref_changes", None)
        if path is None or ref is None:
            return "Invalid event"
        repo_url = 'https://launchpad.net/' + path
        branch = list(ref.keys())[0].split('/')[-1]
        branch_url = repo_url + '/+ref/' + branch
        commit_hash = ref.get(f'refs/heads/{branch}').get('new').get('commit_sha1')
        commit_url = 'https://git.launchpad.net/~mstepan/+git/tmp/commit/?id=' + commit_hash
        msg = f'[Changes]({commit_url}) pushed to [`{branch}`]({branch_url}) at [`{path}`]({repo_url})'
    elif event == 'Merge proposal':
        mp_url = 'https://code.launchpad.net' + data.get('merge_proposal')
        if data.get('action') == 'created':
            attributes = data.get('new')
            registrant = attributes.get('registrant')
            registrant_url = 'https://launchpad.net' + registrant
            source_repo = attributes.get('source_git_repository')
            source_branch = attributes.get('source_git_path').split('/')[-1]
            source_url = 'https://launchpad.net' + source_repo + '/+ref/' + source_branch
            target_repo = attributes.get('target_git_repository')
            target_branch = attributes.get('target_git_path').split('/')[-1]
            target_url = 'https://launchpad.net' + target_repo + '/+ref/' + target_branch
            msg = f'[`{registrant[1:]}`]({registrant_url}) has [proposed merging]({mp_url}) [`{source_repo[1:]}`]({source_url}) into [`{target_repo[1:]}`]({target_url})'
        elif data.get('action') == 'modified':
            # Todo: get diff between new and old -> print it
            diff = []
            new = data.get('new')
            old = data.get('old')
            for attribute in MP_ATTRIBUTES:
                if new[attribute] != old[attribute]:
                    diff.append(f'{attribute}: {old[attribute]} -> {new[attribute]}')
            diff_str = '\n\t-' + '\n\t-'.join(diff)
            msg = f'[`{data.get("merge_proposal")[1:]}`]({mp_url}) modified: {diff_str}'
            # msg = 'modified'
        elif data.get('action') == 'deleted':
            msg = f'{mp_url} has been deleted'
        else:
            msg = 'Merge proposal'

    if msg:
        url, channel = config.MATTERMOST_WEBHOOK_URLS['default']
        post(msg, url, channel)
        return "Notification successfully posted to Mattermost"
    return ""

def post(text, url, channel):
    data = {}
    data['text'] = text
    data['channel'] = channel
    data['username'] = config.USERNAME
    data['icon_url'] = config.ICON_URL

    headers = {'Content-Type': 'application/json'}
    r = requests.post(url, headers=headers, data=json.dumps(data), verify=False)

    if r.status_code is not requests.codes.ok:
        print('Encountered error posting to Mattermost URL %s, status=%d, response_body=%s' % (url, r.status_code, r.json()))

if __name__ == "__main__":
    app.run(
        host=config.SERVER['address'] or "127.0.0.1",
        port=config.SERVER['port'] or 5000,
        debug=False
    )

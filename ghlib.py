# library of GitHub related functions
import datetime
import json

import requests

from error_handling import error
import repoinfo
from repoinfo import RepoInfo


def valid_gh_token(token: str = None, query: bool = True) -> bool:
  """
  Check to make sure token might be a GitHub token, function can't verify for sure
  that a token is valid, just that it is not valid
  :param token: string with token
  :param query: query GitHub to really valid
  :return: false if token is not valid, true if it might be
  """
  if token and token.startswith('ghp'):
    if query:
      resp = get("https://api.github.com/")
      if resp.status_code == 200:
        return True
      else:
        return False
    else:
      return True
  return False


def get(url: str, token: str = None) -> requests.Response:
  """
  Send a GET request to GitHub
  :param url: url to GET
  :param token: GitHub personal access token
  :return: results from request
  """
  get_headers = {'Accept': 'application/vnd.github.v3+json'}
  if token:
    get_headers['Authorization'] = f"token {token}"
  return requests.get(url, headers=get_headers)


def post(url: str, data: dict, token: str = None) -> requests.Response:
  """
  Send POST to GitHub
  :param url: url to POST to
  :param data:  dictionary with body of POST request
  :param token: GitHub personal access token
  :return: results from request
  """
  headers = {'Accept': 'application/vnd.github.v3+json'}
  if token:
    headers['Authorization'] = f"token {token}"
  return requests.post(url, data=data, headers=headers)


def verify_commit(repo_url: str, commit: str, token: str = None) -> bool:
  """
  Check and verify specified commit exists in a repository
  :param repo_url: GitHub URL to repo
  :param commit: hash of commit to check
  :param token: GitHub token to use for authentication
  :return: True if branch is present
  """
  if not commit:
    return False

  commit_url = f"{repo_url}/commits/{commit}"
  r = get(commit_url, token)
  match r.status_code:
    case 404:
      return False
    case 422:
      return False
    case 200:
      return True
    case _:
      error(f"Got {r.status_code} when accessing github: {commit_url}")
  return False


def tag_repo(repo_config: RepoInfo, token: str = None) -> bool:
  """
  Tag a repo branch
  :param repo_config: configuration for repo
  :param token: GitHub token for authentication
  :return: None
  """

  if not valid_gh_token(token):
    error("Must provide a valid github token for authentication", abort=False)
    return False

  if not repo_config.commit:
    error(f"No commit information found for {repo_config.name}", abort=False)
    return False
  if not verify_commit(repoinfo.generate_repo_url(repo_config), repo_config.commit, token):
    error(f"Can't verify commit {repo_config.commit} exists for {repo_config.name}", abort=False)
    return False
  r = requests.post(repoinfo.generate_repo_url(repo_config) + "/git/tags",
                    data=json.dumps({"owner": "ssl-hep",
                                     "repo": repo_config.name,
                                     "tag": repo_config.tag,
                                     "message": "Tagged using release_tool.py",
                                     "object": repo_config.commit,
                                     "type": "commit"}),
                    headers={'Accept': 'application/vnd.github.v3+json',
                             'Authorization': f"token {token}"})

  if r.status_code != 201:
    if r.status_code == 404:
      error(f"Got a 404 while creating a tag for a {repo_config.name}, check to see if you have write access "
            f"to this repo",
            abort=False)
      error(f"Error while creating a tag for a {repo_config.name} "
            f"commit: {repo_config.commit}: {r.json()}")

    error(f"Error while creating a tag for a {repo_config.name} "
          f"commit: {repo_config.commit}: {r.json()}")
    return False
  resp = r.json()
  tag_sha = resp["sha"]
  r = requests.post(repoinfo.generate_repo_url(repo_config) + "/git/refs",
                    data=json.dumps({"ref": f"refs/tags/{repo_config.tag}",
                                     "sha": tag_sha}),
                    headers={'Accept': 'application/vnd.github.v3+json',
                             'Authorization': f"token {token}"})
  if r.status_code != 201:
    error(f"Error while creating a ref for a {repo_config.name} commit: {tag_sha}: {r.json()}")
    return False
  return True


def get_repo_workflow_by_tag(repo_config: RepoInfo, tag: str, token: str = None) -> list[str]:
  """
  Get a list of workflows to monitor for a given tag and repo
  :param repo_config: repo configurations
  :param tag: string with tag to monitor
  :param token: github token
  :return: list of workflows for a given tag
  """
  if tag == "":
    return []

  repo_url = repoinfo.generate_repo_url(repo_config) + f"/actions/runs?event=push&branch={tag}"
  r = get(repo_url, token)
  resp = r.json()
  if r.status_code != 200:
    if r.status_code == 404:
      error(f"Got a 404 while looking for workflow runs {repo_config.name}, check to see if you have access "
            f"to this repo",
            abort=False)
      return []
    else:
      error(f"Got a {r.status_code} while looking workflow runs {repo_config.name}",
            abort=True)
      return []
  urls = []
  for run in resp['workflow_runs']:
    urls.append(run['url'])
  return urls


def get_repo_workflow_by_time(repo_config: RepoInfo, time: datetime.datetime, token: str = None) -> list[str]:
  """
  Get a list of workflows to monitor for a given tag and repo
  :param repo_config: repo configurations
  :param time: approximate time of workflow creation
  :param token: github token
  :return: list of workflows for a given tag
  """

  workflow_start = time - datetime.timedelta(minutes=5)
  workflow_stop = time + datetime.timedelta(minutes=5)
  workflow_url = repoinfo.generate_repo_url(repo_config) + \
                 f"/actions/runs/?created={workflow_start.isoformat()}.." \
                 f"{workflow_stop.isoformat()}"
  r = get(workflow_url, token)
  resp = r.json()
  match r.status_code:
    case 200:
      urls = []
      for run in resp['workflow_runs']:
        urls.append(run['url'])
      return urls
    case 404:
      error(f"Got a 404 while looking for workflow runs {repo_config.name}, check to see if you have access "
            f"to this repo",
            abort=False)
      return []
    case _:
      error(f"Got a {r.status_code} while looking workflow runs {repo_config.name}",
            abort=True)
      return []


def get_workflow_status(workflow_url: str, token: str) -> dict[str, str]:
  """
  Query GitHub for the status of a given workflow\
  :param workflow_url: json from querying actions/runs for a given repo
  :param token: github token
  :return: dict with status of workflow
  """
  r = get(workflow_url, token)
  match r.status_code:
    case 200:
      resp = r.json()
      workflow_info = {'workflow_id': resp['workflow_id'],
                       'status': resp['status'],
                       'url': resp['html_url']}
      job_resp = get(resp['jobs_url'], token)
      if job_resp.status_code != 200:
        error(f"Can't get job information for workflow {resp['workflow_id']}", abort=False)
        return {}
      job_json = job_resp.json()
      workflow_info['job_name'] = job_json["jobs"][-1]["name"]
      workflow_info['job_status'] = job_json["jobs"][-1]["status"]
      return workflow_info
    case 404:
      error(f"Got a 404 while looking for workflow info, check to see if you have access "
            f"to this repo",
            abort=False)
      return {}
    case _:
      error(f"Got a {r.status_code} while looking for workflow info",
            abort=True)
      return {}


def workflows_complete(workflow_info: dict[str, list[str]], token: str) -> bool:
  """
  Query GitHub for the status of a given workflow\
  :param workflow_info: dictionary with workflow information
  :param token: github token
  :return: True if all workflows completed
  """
  completed = True
  for repo, workflows in workflow_info.items():
    for workflow_url in workflows:
      r = get(workflow_url, token)
      match r.status_code:
        case 200:
          resp = r.json()
          if resp['conclusion'] not in ['success', 'completed', 'cancelled', 'failure',
                                        'action_required', 'timed_out', 'skipped']:
            completed = False
        case _:
          print(f"workflow: {workflow_url} default not completed")
          completed = False
  return completed

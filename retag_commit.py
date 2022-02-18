#!/usr/bin/env python3
import json
import sys
import pathlib
import time
import logging
from dataclasses import dataclass

import requests
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich.logging import RichHandler
import toml
import click

GITHUB_BASE_URL = "https://api.github.com"
GITHUB_ORGANIZATION = "ssl-hep"


@dataclass
class RepoInfo:
  name: str
  label: str
  tagtype: str
  semver: str = ""
  new_tag: str = ""
  old_tag: str = ""
  commit: str = ""


def error(message: str = None, abort: bool = True) -> None:
  """
  Print an optional error message and exit

  :param message: message to print
  :param abort: if true, exit program
  :return: None
  """
  if not message:
    message = "Unknown fatal error occurred"
  logging.error(message)
  if abort:
    sys.exit(1)


def warn(message: str = None) -> None:
  """
  Print an optional warning message and exit

  :param message: message to print
  :return: None
  """
  if not message:
    message = "Unknown warning occurred"
  logging.warning(message)


def ingest_config(config_file: pathlib.Path) -> list[RepoInfo]:
  """
  Ingest configuration information

  :param config_file: name of file with configuration
  :return: dictionary with repo information (key -> dict with repo values)
  """
  parsed = toml.load(config_file)
  repos = []
  for key in parsed.keys():
    if 'repos' not in parsed[key]:
      error(f"Section {key} missing repos setting")
    for repo in parsed[key]['repos'].split(','):
      label = None
      tagtype = None
      newtag = ""
      commit = ""
      for setting in ['label', 'tagtype', 'commit']:
        match setting:
          case 'label': label = parsed[key][setting]
          case 'tagtype':
            tagtype = parsed[key][setting].lower()
            if tagtype == 'semver':
              newtag = parsed[key]['semver']
          case 'commit':
            if 'commit' in parsed[key]:
              commit = parsed[key][setting]
          case _: warn(f"Unknown setting {setting} in section {key}")
      if label is None:
        error(f"Section {key} missing label setting")
      if tagtype is None:
        error(f"Section {key} missing tagtype setting")
      if tagtype not in ['semver', 'calver']:
        error(f"In section {key}, tagtype must be 'semver' or 'calver', got {tagtype}")
      repos.append(RepoInfo(name=repo, old_tag=key, label=label, tagtype=tagtype, new_tag=newtag,
                            commit=commit))
  return repos


def generate_calver(date: time.struct_time = None) -> str:
  """
  Generate and return a calver (YYYYMMDD-HHMM)
  :param date: optional date
  :return: string with calver
  """
  if date:
    target_date = date
  else:
    target_date = time.localtime()
  return f"{target_date.tm_year:04}{target_date.tm_mon:02}{target_date.tm_mday:02}-" \
         f"{target_date.tm_hour:02}{target_date.tm_min:02}"


def generate_tag(repo: RepoInfo) -> str:
  """
  Given repo information, create a tag for it
  :param repo: repo what will be tagged
  :return: a tag for the repo
  """
  match repo.tagtype:
    case 'calver': return f"{generate_calver()}-{repo.label}"
    case 'semver': return f"{repo.new_tag}-{repo.label}"


def get_confirmation(tagged_repos: list[RepoInfo]) -> bool:
  """
  Get user confirmation of repo tags
  :param tagged_repos: list with repo configs
  :return: true if user confirms, false otherwise
  """
  console = Console()
  table = Table(title="Repo tags to be applied")
  table.add_column("Repository")
  table.add_column("URL")
  table.add_column("Commit")
  table.add_column("Old Tag")
  table.add_column("New Tag")
  for repo in tagged_repos:
    table.add_row(repo.name, generate_repo_url(repo), repo.commit, repo.old_tag, repo.new_tag)
  console.print(table)
  console.print("Apply tags (y/N)? ")
  resp = input().lower()
  if resp == 'y':
    return True
  else:
    return False


def generate_repo_url(repo_config: RepoInfo) -> str:
  """
  Using repo_config get url for the repo
  :param repo_config: information for repo
  :return: url for the repo string
  """
  return f"{GITHUB_BASE_URL}/repos/{GITHUB_ORGANIZATION}/{repo_config.name}"


def verify_commit(repo_config: RepoInfo, github_token: str = None) -> bool:
  """
  Check and verify specified commit exists in a repository
  :param repo_config:  repo config
  :param github_token: github token to use for authentication
  :return: True if branch is present
  """
  if not repo_config.commit:
    error(f"Can't verify commit to {repo_config.name} without a commit hash")
    return False
  commit_url = generate_repo_url(repo_config) + f"/commits/{repo_config.commit}"
  get_headers = {'Accept': 'application/vnd.github.v3+json'}
  if github_token:
    get_headers['Authorization'] = f"token {github_token}"
  r = requests.get(commit_url, headers=get_headers)
  match r.status_code:
    case 404: return False
    case 422: return False
    case 200: return True
    case _: error(f"Got {r.status_code} when accessing github commit {commit_url}: {r.json()}")
  return False


def check_repos(repo_configs: list[RepoInfo], github_token: str = None) -> bool:
  """
  Check a list of repos to verify that information provided is accurate
  :param repo_configs: list of RepoInfo to check
  :param github_token: github token to use for authentication
  :return: None
  """
  for repo in repo_configs:
    if not verify_commit(repo, github_token):
      error(f"Can't find commit {repo.commit} in {repo.name}", abort=False)
      return False
  return True


def generate_repo_tags(repo_configs: list[RepoInfo]) -> None:
  """
  Given a list of repo configs, update the configs to include a new tag
  :param repo_configs: list of repo configs
  :return: same list with tags defined
  """
  for repo in repo_configs:
    repo.new_tag = generate_tag(repo)


def set_commit(repo_config: RepoInfo, github_token: str = None) -> None:
  """
  Lookup tag specified in the RepoInfo object and use that to
  set the commit for that object
  :param repo_config: RepoInfo object to update
  :return: None
  """
  if not repo_config.old_tag:
    error(f"Must give a tag for {repo_config.name}")
  get_headers = {'Accept': 'application/vnd.github.v3+json'}
  if github_token:
    get_headers['Authorization'] = f"token {github_token}"
  tag_url = generate_repo_url(repo_config) + f"/git/refs/tags/{repo_config.old_tag}"
  # get info on the tag
  r = requests.get(tag_url, headers=get_headers)
  match r.status_code:
    case 404: error(f"Can't get tag {repo_config.old_tag} for {repo_config.name}: {r.json()}")
    case 200: tag_url = r.json()["object"]["url"]
    case _: error(f"Got {r.status_code} when accessing github: {tag_url}")
  # lookup tag to get associated commit
  r = requests.get(tag_url, headers=get_headers)
  match r.status_code:
    case 404: error(f"Can't get tag {repo_config.old_tag} for {repo_config.name}: {r.json()}")
    case 200: repo_config.commit = r.json()["object"]["sha"]
    case _: error(f"Got {r.status_code} when accessing github: {tag_url}")


def tag_repos(repo_configs: list[RepoInfo], github_token: str = None) -> None:
  """
  Tag repos with specified tags
  :param repo_configs: list of repo configurations
  :param github_token: github token for authentication
  :return:  None
  """
  check_repos(repo_configs, github_token)
  generate_repo_tags(repo_configs)
  if not get_confirmation(repo_configs):
    error("Tagging operation was not confirmed", abort=True)
  Console().print("Starting tagging operations:")
  for repo in track(repo_configs, description="Tagging.."):
    if not tag_repo(repo, github_token):
      error(f"Can't tag {repo.name}")


def tag_repo(repo_config: RepoInfo, github_token: str = None) -> bool:
  """
  Tag a repo branch
  :param repo_config: configuration for repo
  :param github_token: github token for authentication
  :return: None
  """

  if not github_token or not github_token.startswith('ghp'):
    error("Must provide a valid github token for authentication", abort=False)
    return False

  if not repo_config.commit:
    error(f"No commit information found for {repo_config.name}", abort=False)
    return False
  if not verify_commit(repo_config, github_token):
    error(f"Can't verify commit {repo_config.commit} exists for {repo_config.name}", abort=False)
    return False
  r = requests.post(generate_repo_url(repo_config) + "/git/tags",
                    data=json.dumps({"owner": "ssl-hep",
                                     "repo": repo_config.name,
                                     "tag": repo_config.new_tag,
                                     "message": f"Retagging from {repo_config.old_tag} to "
                                                f"{repo_config.new_tag}",
                                     "object": repo_config.commit,
                                     "type": "commit"}),
                    headers={'Accept': 'application/vnd.github.v3+json',
                             'Authorization': f"token {github_token}"})
  if r.status_code != 201:
    error(f"Error while creating a tag for a {repo_config.name} "
          f"commit: {repo_config.commit}: {r.json()}")
    return False
  resp = r.json()
  tag_sha = resp["sha"]
  r = requests.post(generate_repo_url(repo_config) + "/git/refs",
                    data=json.dumps({"ref": f"refs/tags/{repo_config.new_tag}",
                                     "sha": tag_sha}),
                    headers={'Accept': 'application/vnd.github.v3+json',
                             'Authorization': f"token {github_token}"})
  if r.status_code != 201:
    error(f"Error while creating a ref for a {repo_config.name} commit: {tag_sha}: {r.json()}")
    return False
  return True


@click.command()
@click.option("--config", default="retag.toml", help="Configuration file for toml")
@click.option("--debug", default=False, help="Enable debugging")
def entry(config: str, debug: bool) -> None:
  """
  Run command and do all processing
  :param config: path to configuration file
  :param debug: output debugging information
  :return: None
  """
  if debug:
    log_level = "DEBUG"
  else:
    log_level = "INFO"
  logging.basicConfig(
    level=log_level,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
  )
  config_path = pathlib.Path(config)
  token = input("Enter your github token (PAT): ")
  if token == "" or not token.startswith('ghp'):
    warn("Token seems to be invalid, continuing without one")
    token = None
  if pathlib.Path.is_file(config_path):
    repo_configs = ingest_config(config_path)
  else:
    error(f"Config file {config} not present\n")
  if not check_repos(repo_configs, token):
    error("Can't verify that all repos and branches exist")
  tag_repos(repo_configs, token)
  sys.exit(0)


if __name__ == "__main__":
  entry()

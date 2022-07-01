#!/usr/bin/env python3
import json
import sys
import pathlib
import logging

import requests
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich.logging import RichHandler
import click

from error_handling import error, warn
from repoinfo import RepoInfo
import util

GITHUB_BASE_URL = "https://api.github.com"
GITHUB_ORGANIZATION = "ssl-hep"


def generate_tag(repo: RepoInfo) -> str:
  """
  Given repo information, create a tag for it
  :param repo: repo what will be tagged
  :return: a tag for the repo
  """
  match repo.tagtype:
    case 'calver': return f"{util.generate_calver()}-{repo.label}"
    case 'semver': return f"{repo.newtag}-{repo.label}"
    case _: return ""


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
    table.add_row(repo.name, generate_repo_url(repo), repo.commit, repo.old_tag, repo.newtag)
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
  :param github_token: ghlib token to use for authentication
  :return: True if branch is present
  """
  if not repo_config.commit:
    error(f"Can't verify commit to {repo_config.name} without a commit hash")
    return False
  commit_url = generate_repo_url(repo_config) + f"/commits/{repo_config.commit}"
  get_headers = {'Accept': 'application/vnd.ghlib.v3+json'}
  if github_token:
    get_headers['Authorization'] = f"token {github_token}"
  r = requests.get(commit_url, headers=get_headers)
  match r.status_code:
    case 404: return False
    case 422: return False
    case 200: return True
    case _: error(f"Got {r.status_code} when accessing ghlib commit {commit_url}: {r.json()}")
  return False


def check_repos(repo_configs: list[RepoInfo], github_token: str = None) -> bool:
  """
  Check a list of repos to verify that information provided is accurate
  :param repo_configs: list of RepoInfo to check
  :param github_token: ghlib token to use for authentication
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
    repo.newtag = generate_tag(repo)


def set_commit(repo_config: RepoInfo, github_token: str = None) -> None:
  """
  Lookup tag specified in the RepoInfo object and use that to
  set the commit for that object
  :param repo_config: RepoInfo object to update
  :return: None
  """
  if not repo_config.old_tag:
    error(f"Must give a tag for {repo_config.name}")
  get_headers = {'Accept': 'application/vnd.ghlib.v3+json'}
  if github_token:
    get_headers['Authorization'] = f"token {github_token}"
  tag_url = generate_repo_url(repo_config) + f"/git/refs/tags/{repo_config.old_tag}"
  # get info on the tag
  r = requests.get(tag_url, headers=get_headers)
  match r.status_code:
    case 404: error(f"Can't get tag {repo_config.old_tag} for {repo_config.name}: {r.json()}")
    case 200: tag_url = r.json()["object"]["url"]
    case _: error(f"Got {r.status_code} when accessing ghlib: {tag_url}")
  # lookup tag to get associated commit
  r = requests.get(tag_url, headers=get_headers)
  match r.status_code:
    case 404: error(f"Can't get tag {repo_config.old_tag} for {repo_config.name}: {r.json()}")
    case 200: repo_config.commit = r.json()["object"]["sha"]
    case _: error(f"Got {r.status_code} when accessing ghlib: {tag_url}")


def tag_repos(repo_configs: list[RepoInfo], github_token: str = None) -> None:
  """
  Tag repos with specified tags
  :param repo_configs: list of repo configurations
  :param github_token: ghlib token for authentication
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
  :param github_token: ghlib token for authentication
  :return: None
  """

  if not github_token or not github_token.startswith('ghp'):
    error("Must provide a valid ghlib token for authentication", abort=False)
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
                                     "tag": repo_config.newtag,
                                     "message": f"Retagging from {repo_config.old_tag} to "
                                                f"{repo_config.newtag}",
                                     "object": repo_config.commit,
                                     "type": "commit"}),
                    headers={'Accept': 'application/vnd.ghlib.v3+json',
                             'Authorization': f"token {github_token}"})
  if r.status_code != 201:
    error(f"Error while creating a tag for a {repo_config.name} "
          f"commit: {repo_config.commit}: {r.json()}")
    return False
  resp = r.json()
  tag_sha = resp["sha"]
  r = requests.post(generate_repo_url(repo_config) + "/git/refs",
                    data=json.dumps({"ref": f"refs/tags/{repo_config.newtag}",
                                     "sha": tag_sha}),
                    headers={'Accept': 'application/vnd.ghlib.v3+json',
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
  token = input("Enter your ghlib token (PAT): ")
  if token == "" or not token.startswith('ghp'):
    warn("Token seems to be invalid, continuing without one")
    token = ""
  if pathlib.Path.is_file(config_path):
    repo_configs = util.ingest_config(config_path)
  else:
    error(f"Config file {config} not present\n")
  if not check_repos(repo_configs, token):
    error("Can't verify that all repos and branches exist")
  tag_repos(repo_configs, token)
  sys.exit(0)


if __name__ == "__main__":
  entry()

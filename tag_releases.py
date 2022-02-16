#!/usr/bin/env python3
import json
import sys
import pathlib
import time
from dataclasses import dataclass

import requests
import rich
from rich.console import Console
from rich.table import Table
from rich.progress import track
import toml
import click

GITHUB_BASE_URL = "https://api.github.com"
GITHUB_ORGANIZATION = "ssl-hep"


@dataclass
class RepoInfo:
  name: str
  branch: str
  label: str
  tagtype: str
  semver: str = ""
  tag: str = ""


def error(message: str = None, quit: bool = True) -> None:
  """
  Print an optional error message and exit

  :param message: message to print
  :param quit: if true, exit program
  :return: None
  """
  if not message:
    message = "Unknown fatal error occurred"
  Console().print(message, style="bold red")
  if quit:
    sys.exit(1)


def ingest_config(config_file: pathlib.Path) -> list[RepoInfo]:
  """
  Ingest configuration information

  :param config_file: name of file with configuration
  :return: dictionary with repo information (key -> dict with repo values)
  """
  parsed = toml.load(config_file)
  repos = []
  for key in parsed.keys():
    if 'branch' in parsed[key]:
      branch = parsed[key]['branch']
    else:
      error(f"Section {key} missing branch setting")
    if 'label' in parsed[key]:
      label = parsed[key]['label']
    else:
      error(f"Section {key} missing label setting")
    if 'tagtype' in parsed[key]:
      tagtype = parsed[key]['tagtype'].lower()
      if tagtype not in ['semver', 'calver']:
        error(f"In section {key}, tagtype must be 'semver' or 'calver', got {tagtype}")
    else:
      error(f"Section {key} missing tagtype setting")
    if 'semver' in parsed[key]:
      semver = parsed[key]['semver']
    else:
      semver = ""
    repos.append(RepoInfo(key, branch, label, tagtype, semver))
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
  return f"{target_date.tm_year:04}{target_date.tm_mon:02}{target_date.tm_mday:02}-{target_date.tm_hour:02}{target_date.tm_min:02}"


def generate_tag(repo: RepoInfo) -> str:
  """
  Given repo information, create a tag for it
  :param repo: repo what will be tagged
  :return: a tag for the repo
  """
  match repo.tagtype:
    case 'calver': return f"{generate_calver()}-{repo.label}"
    case 'semver': return f"{repo.semver}-{repo.label}"


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
  table.add_column("Tag")
  for repo in tagged_repos:
    table.add_row(repo.name, generate_repo_url(repo), repo.tag)
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


def verify_branch(repo_config: RepoInfo, github_token: str = None) -> bool:
  """
  Check and verify a branch exists in a repository
  :param repo_config:  repo config
  :param github_token: github token to use for authentication
  :return: True if branch is present
  """
  branch_url = generate_repo_url(repo_config) + f"/branches/{repo_config.branch}"
  r = requests.get(branch_url, headers={'Accept': 'application/vnd.github.v3+json'})
  match r.status_code:
    case 404: return False
    case 200: return True
    case _: error(f"Got {r.status_code} when accessing github: {branch_url}")
  return False


def check_repos(repo_configs: list[RepoInfo], github_token: str = None) -> bool:
  """
  Check a list of repos to verify that information provided is accurate
  :param repo_configs: list of RepoInfo to check
  :param github_token: github token to use for authentication
  :return: None
  """
  for repo in repo_configs:
    if not verify_branch(repo, github_token):
      error(f"Can't verify that {repo.branch} exists in {repo.name}", quit=False)
      return False
  return True


def generate_repo_tags(repo_configs: list[RepoInfo]) -> list[RepoInfo]:
  """
  Given a list of repo configs, create a dictionary of repo url with associated tags

  :param repo_configs: list of repo configs
  :return: same list with tags defined
  """

  new_configs = []
  for repo in repo_configs:
    repo.tag = generate_tag(repo)
    new_configs.append(repo)
  return new_configs


def tag_repos(repo_configs: list[RepoInfo], github_token = None) -> None:
  """
  Tag repos with specified tags
  :param repo_configs: list of repo configurations
  :return:  None
  """
  check_repos(repo_configs, github_token)
  tagged_configs = generate_repo_tags(repo_configs)
  if not get_confirmation(tagged_configs):
    error("Tagging operation was not confirmed", quit=True)
  Console().print("Starting tagging operations:")
  for repo in track(tagged_configs, description="Tagging.."):
    if not tag_repo(repo, github_token):
      error(f"Can't tag {repo.name}")


def tag_repo(repo_config: RepoInfo, github_token: str = None) -> bool:
  """
  Tag a repo branch
  :param repo_config: configuration for repo
  :param github_token: github token for authentication
  :return: None
  """

  if not github_token or not github_token.startswith('ghp') :
    error("Must provide a valid github token for authentication", quit=False)
    print(github_token)
    return False

  branch_url = generate_repo_url(repo_config) + f"/branches/{repo_config.branch}"
  r = requests.get(branch_url,
                   headers={'Accept': 'application/vnd.github.v3+json',
                            'Authorization': f"token {github_token}"})
  match r.status_code:
    case 200: json_body = r.json()
    case _: return False
  commit = json_body['commit']['sha']

  r = requests.post(generate_repo_url(repo_config) + "/git/tags",
                    data=json.dumps({"owner": "ssl-hep",
                                     "repo": repo_config.name,
                                     "tag": repo_config.tag,
                                     "message": "Tagged using tag_releases.py",
                                     "object": commit,
                                     "type": "commit"}),
                    headers={'Accept': 'application/vnd.github.v3+json',
                             'Authorization': f"token {github_token}"})
  if r.status_code != 201:
    error(f"Error while creating a tag for a {repo_config.name} commit: {commit}: {r.json()}")
    return False
  resp = r.json()
  tag_sha = resp["sha"]
  r = requests.post(generate_repo_url(repo_config) + "/git/refs",
                    data=json.dumps({"ref": f"refs/tags/{repo_config.tag}",
                                     "sha": tag_sha}),
                    headers={'Accept': 'application/vnd.github.v3+json',
                             'Authorization': f"token {github_token}"})
  if r.status_code != 201:
    error(f"Error while creating a ref for a {repo_config.name} commit: {tag_sha}: {r.json()}")
    return False
  return True


@click.command()
@click.option("--config", default="repos.toml", help="Configuration file for toml")
def entry(config: str) -> None:
  """
  Run command and do all processing
  :param config: path to configuration file
  :return: None
  """
  console = Console()
  config_path = pathlib.Path(config)
  token = input("Enter your github token (PAT):")
  if token == "" or not token.startswith('ghp'):
    console.print("Token seems to be invalid, continuing without one", style="yellow")
    token = None
  if pathlib.Path.is_file(config_path):
    repo_configs = ingest_config(config_path)
  else:
    error(f"Config file {config} not present\n")
  if not check_repos(repo_configs, token):
    error(f"Can't verify that all repos and branches exist")
  tag_repos(repo_configs, token)
  sys.exit(0)


if __name__ == "__main__":
  entry()
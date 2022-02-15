#!/usr/bin/env python3

import sys
import pathlib
import time
from dataclasses import dataclass

import requests
from rich.console import Console
from rich.table import Table
import toml
import click

GITHUB_BASE_URL = "https://api.github.com/"
GITHUB_ORGANIZATION = "ssl-hep"


@dataclass
class RepoInfo:
  name: str
  branch: str
  label: str
  tagtype: str
  semver: str
  tag: str


def error_exit(message: str = None) -> None:
  """
  Print an optional error message and exit

  :param message: message to print
  :return: None
  """
  if not message:
    message = "Unknown fatal error occurred"
    Console().print(message, style="bold red")
    sys.exit(1)


def ingest_config(config_file: pathlib.Path) -> list[RepoInfo]:
  """
  Ingest configuration information

  :param config_file: name of file with configuration
  :return: dictionary with repo information (key -> dict with repo values)
  """
  parsed = toml.load(config_file)
  repos = []
  for k,val in parsed:
    if 'branch' in val:
      branch = val['branch']
    else:
      error_exit(f"Section {k} missing branch setting")
    if 'label' in val:
      label = val['label']
    else:
      error_exit(f"Section {k} missing label setting")
    if 'tagtype' in val:
      tagtype = val['tagtype'].lower()
      if tagtype not in ['semvar', 'calver']:
        error_exit(f"In section {k}, tagtype must be 'semver' or 'calver', got {tagtype}")
    else:
      error_exit(f"Section {k} missing tagtype setting")
    if 'semver' in val:
      semver = val['semver']
    else:
      semver = ""
    repos.append(RepoInfo(k, branch, label, tagtype, semver, ""))
  return repos


def generate_calver() -> str:
  """
  Generate and return a calver (YYYYMMDD-HHMM)
  """
  now = time.localtime()
  return f"{now.tm_year:04}{now.tm_mon:02}{now.tm_mday:02}-{now.tm_hour}{now.tm_min}"


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
  table = Table("Repo tags to be applied")
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


def verify_branch(repo_config: RepoInfo) -> bool:
  """
  Check and verify a branch exists in a repository
  :param repo_config:  repo config
  :return: True if branch is present
  """
  branch_url = generate_repo_url(repo_config) + "/branches"
  r = requests.get(branch_url)
  if r.status_code != 200:
    error_exit(f"Got {r.status_code} when accessing github: {branch_url}")
  resp_json = r.json()
  for branch in resp_json:
    if branch['name'] == repo_config.branch:
      return True
  return False


def check_repos(repo_configs: list[RepoInfo]) -> None:
  """
  Check a list of repos to verify that information provided is accurate
  :param repo_configs: list of RepoInfo to check
  :return: None
  """
  for repo in repo_configs:
    if not verify_branch(repo):
      error_exit(f"Can't verify that {repo.branch} exists in {repo.name}")


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


def tag_repos(repo_configs: list[RepoInfo]) -> None:
  """
  Tag repos with specified tags
  :param repo_configs: list of repo configurations
  :return:  None
  """
  check_repos(repo_configs)
  tagged_configs = generate_tag(repo_configs)
  if not get_confirmation(tagged_configs):
    error_exit("Tagging operation was not confirmed")
  for repo in tagged_configs:
    pass


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
  if pathlib.Path.is_file(config_path):
    repo_configs = ingest_config(config_path)
  else:
    console.print(f"Config file {config} not present\n", style="bold red")
    sys.exit(1)
  check_repos(repo_configs)
  # tag_repos(repo_config)
  sys.exit(0)


if __name__ == "__main__":
  entry()
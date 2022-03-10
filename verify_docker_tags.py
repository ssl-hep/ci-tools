#!/usr/bin/env python3
import logging
import pathlib
import sys
from dataclasses import dataclass

import requests
import toml
from rich.logging import RichHandler
import click

DOCKER_REGISTRY_URL = "https://hub.docker.com"


@dataclass
class RepoInfo:
  name: str
  docker_repo: str = ""

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
    branch = None
    label = None
    tagtype = None
    commit = ""
    semver = ""
    docker_repo = None
    for setting in ['branch', 'label', 'tagtype', 'commit', 'docker_repo']:
      match setting:
        case 'branch': branch = parsed[key][setting]
        case 'label': label = parsed[key][setting]
        case 'docker_repo': docker_repo = parsed[key].get(setting, None)
        case 'tagtype':
          tagtype = parsed[key][setting].lower()
          if tagtype == 'semver':
            semver = parsed[key]['semver']
        case 'commit':
          if 'commit' in parsed[key]:
            commit = parsed[key][setting].lower()
        case _: warn(f"Unknown setting {setting} in section {key}")
    if branch is None:
      error(f"Section {key} missing branch setting")
    if label is None:
      error(f"Section {key} missing label setting")
    if tagtype is None:
      error(f"Section {key} missing tagtype setting")
    if tagtype not in ['semver', 'calver']:
      error(f"In section {key}, tagtype must be 'semver' or 'calver', got {tagtype}")
    if branch and commit:
      warn(f"In section {key}, branch and commit both set, using commit")
    repos.append(RepoInfo(name=key, docker_repo=docker_repo))
  return repos

def verify_tag(repo_config: RepoInfo, tag: str=None) -> bool:
  """
  Check that a specific tag exists for a docker repo

  :param repo_config: A single repo config object
  :param tag: The tag name to check for
  :return: True of the tag exists
  """
  query = f'{DOCKER_REGISTRY_URL}/v2/repositories/{repo_config.docker_repo}/tags/{tag}'
  r = requests.get(query)
  if r.status_code == 404:
    return False
  return True


def check_repos(repo_configs: list[RepoInfo], tag: str = None) -> bool:
  """
  Check a list of repos to verify that the given tag exists for each repo
  :param repo_configs: list of RepoInfo to check
  :param tag: Name of the tag to check
  :return: True if all of the repos have the requested tag
  """
  for repo in repo_configs:
    if repo.docker_repo and not verify_tag(repo, tag):
      error(f"Can't find tag {tag} for {repo.docker_repo}", abort=False)
      return False
  return True



@click.command()
@click.option("--config", default="repos.toml", help="Configuration file for toml")
@click.option("--debug", default=False, help="Enable debugging")
@click.option("--tag", default="", help="Docker tag to check for")
def entry(config: str, debug: bool, tag: str) -> None:
  """
  Run command and do all processing
  :param config: path to configuration file
  :parm debug: output debugging information
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
  if pathlib.Path.is_file(config_path):
    repo_configs = ingest_config(config_path)
  else:
    error(f"Config file {config} not present\n")
  if not check_repos(repo_configs, tag):
    error("Can't verify that all repos and branches exist")
  else:
    logging.info(f"All images have been published for {tag}")
  sys.exit(0)


if __name__ == "__main__":
  entry()

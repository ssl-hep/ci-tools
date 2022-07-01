#!/usr/bin/env python3
import datetime
import json
import sys
import pathlib
import logging
import typing
import time

import click
import requests
import rich
import rich.align


from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich.logging import RichHandler
from rich.live import Live


import ghlib
import repoinfo
import util
from error_handling import error, warn
from repoinfo import RepoInfo


def get_token() -> str:
  """
  Prompt user for github token and do a quick verification
  :return: str with github token
  """
  token = input("Enter your github token (PAT):")
  if not ghlib.valid_gh_token(token):
    warn("Token seems to be invalid")
    resp = input("Continue [y/N]? ")
    if resp.lower().strip() != 'y':
      return ""
  return token


def generate_tag(repo: RepoInfo) -> str:
  """
  Given repo information, create a tag for it
  :param repo: repo what will be tagged
  :return: a tag for the repo
  """
  match repo.tagtype:
    case 'calver': return f"{util.generate_calver()}-{repo.label}"
    case 'semver': return f"{repo.semver}-{repo.label}"
  return ""


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
    table.add_row(repo.name, repoinfo.generate_repo_url(repo), repo.tag)
  console.print(table)
  console.print("Apply tags (y/N)? ")
  resp = input().lower()
  if resp == 'y':
    return True
  else:
    return False


def update_branch_config(repo_config: RepoInfo, github_token: str = None) -> bool:
  """
  Check and verify a branch exists in a repository, if it exists update
  config to include the last commit made on the branch
  :param repo_config:  repo config
  :param github_token: github token to use for authentication
  :return: True if branch is present
  """
  if not repo_config.branch:
    error(f"Can't verify branch in {repo_config.name} without a branch being given")
    return False
  branch_url = repoinfo.generate_repo_url(repo_config) + f"/branches/{repo_config.branch}"
  get_headers = {'Accept': 'application/vnd.github.v3+json'}
  if github_token:
    get_headers['Authorization'] = f"token {github_token}"
  r = requests.get(branch_url, headers=get_headers)
  match r.status_code:
    case 404: return False
    case 200:
      repo_config.commit = r.json()['commit']['sha']
      return True
    case _: error(f"Got {r.status_code} when accessing github: {branch_url}")
  return False


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
  return ghlib.verify_commit(repoinfo.generate_repo_url(repo_config), repo_config.commit, github_token)


def check_repos(repo_configs: list[RepoInfo], github_token: str = None) -> bool:
  """
  Check a list of repos to verify that information provided is accurate
  :param repo_configs: list of RepoInfo to check
  :param github_token: github token to use for authentication
  :return: None
  """
  for repo in repo_configs:
    if not update_branch_config(repo, github_token):
      error(f"Can't find branch {repo.branch} in {repo.name}", abort=False)
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


def tag_repos(repo_configs: list[RepoInfo], github_token: str = None) -> None:
  """
  Tag repos with specified tags
  :param repo_configs: list of repo configurations
  :param github_token: github token for authentication
  :return:  None
  """
  check_repos(repo_configs, github_token)
  tagged_configs = generate_repo_tags(repo_configs)
  if not get_confirmation(tagged_configs):
    error("Tagging operation was not confirmed", abort=True)
  Console().print("Starting tagging operations:")
  for repo in track(tagged_configs, description="Tagging.."):
    if not ghlib.tag_repo(repo, github_token):
      error(f"Can't tag {repo.name}")


@click.command(help="Verify that workflows for given tags have completed successfully")
@click.option('--tag', type=str, default="", help="Check workflows associated with a tag")
@click.option("workflow_time", '--time', type=str, default="",
              help="Check for workflows started within 5 minutes of specified time (YYYY-MM-DDTHH:MM:SS)")
@click.pass_obj
def monitor_workflows(config: dict[str, typing.Any], tag: str, workflow_time: str) -> None:
  """
  Verify that workflows for given tags have completed successfully

  :param config: dictionary with option information
  :param tag: tag to use when finding workflows to monitor
  :param workflow_time: ISO8601 time (YYYY-MM-DDTHH:MM:SS) giving the approximate time for monitored workflows
  """
  token = get_token()
  if not ghlib.valid_gh_token(token):
    error("Must provide a valid github token for authentication to get workflow information")

  if workflow_time != "":
    workflow_datetime = datetime.datetime.strptime("%Y-%m-%dT%H:%M:%S", workflow_time)
  if tag == "" and workflow_time == "":
    resp = input("Get workflows started around the current time? [Y/n]")
    if resp.lower().strip() != "y":
      error("Need a tag or time to monitor workflows")
    workflow_datetime = datetime.datetime.utcnow()

  workflow_info = {}
  if tag != "":
    for repo in config['repo_configs']:
      workflow_info[repo.name] = ghlib.get_repo_workflow_by_tag(repo, tag, token)
  elif workflow_time != "":
    for repo in config['repo_configs']:
      workflow_info[repo.name] = ghlib.get_repo_workflow_by_time(repo, workflow_datetime, token)
  console = Console()
  with Live(console=console, auto_refresh=False) as live_table:
    while True:
      table = generate_table(workflow_info, token)
      live_table.update(rich.align.Align.center(table), refresh=True)
      if ghlib.workflows_complete(workflow_info, token):
        sys.exit(0)
      time.sleep(30)


def generate_table(workflow_info: dict[str, list[str]], token: str) -> rich.table.Table:
  """
  Generate a rich table with workflow information
  :param workflow_info: dictionary with workflow information
  :param token: github token
  :return: a rich table with workflow information
  """
  table = Table(title="Workflow Status")
  table.add_column("Repo")
  table.add_column("Workflow")
  table.add_column("Workflow URL")
  table.add_column("Workflow Status")
  table.add_column("Current Job")
  table.add_column("Job Status")
  for repo, workflows in workflow_info.items():
    for workflow_url in workflows:
      status = ghlib.get_workflow_status(workflow_url, token)
      if status == {}:
        table.add_row(repo, None, None, None, None)
        continue
      table.add_row(repo,
                    status['url'],
                    f"{status['workflow_id']}",
                    status['status'],
                    status['job_name'],
                    status['job_status'])
  return table


@click.command(help="Tag repos using settings from config file")
@click.option("--verify", default=True, help="Verify that images were generated and published")
@click.pass_obj
def tag(config: dict[str, typing.Any], verify: bool) -> None:
  """
  Tag repos
  :param config: dictionary with configuration parameters
  :param verify: bool indicating whether to verify generation of containers
  :return:
  """
  token = get_token()
  repo_configs = get_config(config['repo_configs'])
  if not check_repos(repo_configs, token):
    error("Can't verify that all repos and branches exist")
  tag_repos(repo_configs, token)
  if not verify:
    user = input("Verify container creation? [y/N]")
    if user.lower().strip() != 'y':
      sys.exit(0)
  monitor_workflows(repo_configs, token)
  verify_containers(config)
  sys.exit(0)


@click.command(help="Verify containers have been published at sources given in config file")
@click.option("--tag", type=str, default="", required=True, prompt=True)
@click.pass_obj
def verify_containers(config: dict[str, typing.Any], tag: str) -> None:
  """
  Tag repos

  :param config: dictionary with configuration parameters
  :param tag: container tag to check
  :return: None
  """
  if tag == "":
    error("Must specify a valid tag")

  repo_configs = config['repo_configs']
  Console().print("Checking for docker containers:")
  registry_repos = [repo for repo in repo_configs if repo.container_registry != ""]
  for repo in track(registry_repos, description="Checking.."):
    if not find_container(repo, tag):
      error(f"Can't find container in {repo.container_repo} tagged as {tag} for {repo.name} ")


def find_container(repo: RepoInfo, tag) -> bool:
  """
  Check for containers
  :param repo: RepoInfo object with information for repo
  :param tag: tag for container image
  :return: True if container found, false otherwise
  """
  container_url = repoinfo.container_url(repo, tag)
  r = requests.get(container_url)
  if r.status_code == 200:
    return True
  return False


@click.command(help="Generate and publish chart")
def release() -> None:
  pass


def setup_logging(debug: bool) -> None:
  """
  Setup logging with rich

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


def get_config(config: str) -> list[RepoInfo]:
  config_path = pathlib.Path(config)
  if pathlib.Path.is_file(config_path):
    repo_configs = util.ingest_config(config_path)
    return repo_configs
  else:
    error(f"Config file {config} not present\n")
    return list()


@click.group()
@click.option("--config", default="repos.toml", type=str, help="Configuration file for toml", required=True)
@click.option("--debug", default=False, type=bool, help="Enable debugging")
@click.pass_context
def entry(ctx: click.Context, config: str, debug: bool) -> None:
  """
  Do various release tasks for ServiceX
  """
  setup_logging(debug)
  repo_configs = get_config(config)
  ctx.obj = {'config': config,
             'repo_configs': repo_configs}

  # tag_repos(repo_configs, token)
  # verify_workflows(repo_configs, token)
  # verify_containers(config)


entry.add_command(tag)
entry.add_command(verify_containers)
entry.add_command(monitor_workflows)
entry.add_command(release)

if __name__ == "__main__":
  entry()

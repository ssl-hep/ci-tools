#!/usr/bin/env python3
import datetime
import os
import sys
import pathlib
import logging
import tempfile
import typing
import time

import click
import requests
import rich
import rich.align

from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.progress import track
from rich.logging import RichHandler
from rich.live import Live
from rich.layout import Layout


import ghlib
import git
import repoinfo
import util
from error_handling import error, warn
from repoinfo import RepoInfo


def get_token() -> str:
  """
  Prompt user for GitHub token and do a quick verification
  :return: str with GitHub token
  """
  token = input("Enter your github token (PAT):")
  if not ghlib.valid_gh_token(token):
    warn("Token seems to be invalid")
    resp = input("Continue [y/N]? ")
    if resp.lower().strip() != 'y':
      error("Exiting due to missing github PAT")
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
    table.add_row(repo.name,
                  Text(repoinfo.generate_repo_url(repo), style=f"link {repoinfo.generate_repo_url(repo)}"),
                  repo.tag)
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
  :param github_token: GitHub token to use for authentication
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
  :param github_token: GitHub token to use for authentication
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
  :param github_token: GitHub token to use for authentication
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


def tag_repos(repo_configs: list[RepoInfo], github_token: str = None) -> str:
  """
  Tag repos with specified tags
  :param repo_configs: list of repo configurations
  :param github_token: GitHub token for authentication
  :return:  None
  """
  check_repos(repo_configs, github_token)
  tagged_configs = generate_repo_tags(repo_configs)
  if not get_confirmation(tagged_configs):
    error("Tagging operation was not confirmed", abort=True)
  Console().print("Starting tagging operations:")
  tag = ""
  for repo in track(tagged_configs, description="Tagging.."):
    tag = repo.tag
    if not ghlib.tag_repo(repo, github_token):
      error(f"Can't tag {repo.name}")
  return tag


@click.command(help="Verify that workflows for given tags have completed successfully")
@click.option('--tag', type=str, default="", help="Check workflows associated with a tag")
@click.option("workflow_time", '--time', type=str, default="",
              help="Check for workflows started within 5 minutes of specified time (YYYY-MM-DDTHH:MM:SS)")
@click.pass_obj
@click.pass_context
def monitor_workflows(ctx: click.Context, config: dict[str, typing.Any], tag: str, workflow_time: str) -> None:
  """
  Verify that workflows for given tags have completed successfully
  :param ctx: click.Context with information about invocation
  :param config: dictionary with option information
  :param tag: tag to use when finding workflows to monitor
  :param workflow_time: ISO8601 time (YYYY-MM-DDTHH:MM:SS) giving the approximate time for monitored workflows
  """
  if 'token' not in ctx.obj:
    token = get_token()
    ctx.obj['token'] = token
  else:
    token = ctx.obj['token']
  if not ghlib.valid_gh_token(token):
    error("Must provide a valid github token for authentication to get workflow information")

  if workflow_time != "" and not isinstance(workflow_time, datetime.datetime):
    workflow_datetime = datetime.datetime.fromisoformat(workflow_time)
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
        table = generate_table(workflow_info, token)
        live_layout = Layout()
        live_layout.split_column(Layout(name="upper"), Layout(name="lower"))
        live_layout['upper'].ratio = 1
        live_layout['upper'].update(table)
        live_layout['lower'].update("All workflows completed")
        live_table.update(live_layout, refresh=True)
        return
      time.sleep(30)


def generate_table(workflow_info: dict[str, list[str]], token: str) -> rich.table.Table:
  """
  Generate a rich table with workflow information
  :param workflow_info: dictionary with workflow information
  :param token: GitHub token
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
      if status['status'] in ['success', 'completed']:
        status_text = Text(status['status'], style="bold green")
      elif status['status'] in ['cancelled', 'failure', 'action_required', 'timed_out']:
        status_text = Text(status['status'], style="blink red")
      else:
        status_text = Text(status['status'], style="dim green")
      if status['job_status'] in ['success', 'completed']:
        job_text = Text(status['status'], style="bold green")
      elif status['job_status'] in ['cancelled', 'failure', 'action_required', 'timed_out']:
        job_text = Text(status['job_status'], style="blink red")
      else:
        job_text = Text(status['job_status'], style="dim green")

      status_url = Text(status['url'], style=f"link {status['url']} blue")
      table.add_row(repo,
                    f"{status['workflow_id']}",
                    status_url,
                    status_text,
                    status['job_name'],
                    job_text)
  return table


@click.command(help="Tag repos using settings from config file")
@click.option("--verify", default=True, help="Verify that images were generated and published")
@click.option("--publish", default=False, help="Publish helm chart")
@click.pass_obj
@click.pass_context
def tag(ctx: click.Context, config: dict[str, typing.Any], verify: bool, publish: bool) -> None:
  """
  Tag repos
  :param ctx: click.Context with information about invocation
  :param config: dictionary with configuration parameters
  :param verify: bool indicating whether to verify generation of containers
  :param publish: bool indicating whether to publish chart
  :return:
  """
  if 'token' not in ctx.obj:
    token = get_token()
    ctx.obj['token'] = token
  else:
    token = ctx.obj['token']
  repo_configs = config['repo_configs']
  if not check_repos(repo_configs, token):
    error("Can't verify that all repos and branches exist")
  tag = tag_repos(repo_configs, token)
  if not verify:
    user = input("Verify container creation? [y/N]")
    if user.lower().strip() != 'y':
      sys.exit(0)
  workflow_time = datetime.datetime.utcnow()

  ctx.obj['config'] = repo_configs
  ctx.invoke(monitor_workflows, tag=tag, workflow_time=workflow_time)
  ctx.obj['config'] = config
  ctx.invoke(verify_containers, tag=tag)
  if publish:
    chart_version = input("Chart version to publish? ")
    user = input(f"Publish chart {chart_version} [y/N]? ")
    if user.lower().strip() != 'y':
      Console().print("Exiting since no chart version given")
      sys.exit(0)
    ctx.invoke(release, tag=tag, chart_version=chart_version)
    Console().print("Release tagged and published")
  else:
    Console().print("Release tagged")
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
  console = Console()
  console.print("\nChecking for docker containers:")
  registry_repos = [repo for repo in repo_configs if repo.container_registry != ""]
  for repo in track(registry_repos, description="Checking.."):
    if not find_container(repo, tag):
      print(dir(repo))
      error(f"Can't find container in {repo.container_repo} tagged as {tag} for {repo.name}")
  console.print("All containers verified successfully")


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
@click.option("--tag", type=str, default="", required=True, prompt=True)
@click.option("--chart-version", type=str, default="", required=True, prompt=True)
@click.option("--verify", default=True, help="Verify that images were generated and published")
@click.pass_obj
@click.pass_context
def release(ctx: click.Context, config: dict[str, typing.Any], tag: str, chart_version: str, verify: bool) -> None:
  """
  Tag repos
  :param ctx: click.Context with information about invocation
  :param config: dictionary with configuration parameters
  :param tag: tag to use for images
  :param chart_version: version string to use for released chart
  :param verify: bool indicating whether to verify generation of containers
  :return: None
  """
  if 'token' not in ctx.obj:
    token = get_token()
    ctx.obj['token'] = token
  else:
    token = ctx.obj['token']
  if not ghlib.valid_gh_token(token):
    error("Must provide a valid github token for authentication to get workflow information")
  if verify:
    ctx.obj['config'] = config
    ctx.invoke(verify_containers, tag=tag)
  temp_dir = ""
  try:
    temp_dir = tempfile.mkdtemp()
  except IOError as err:
    error(f"Can't create temporary directory in order to publish chart: {err}")

  orig_dir = ""
  try:
    orig_dir = os.getcwd()
    os.chdir(temp_dir)
    print(f"Checking out in {temp_dir}")
    console = Console()
    servicex_repo = git.checkout_repo("ssh://git@github.com/ssl-hep/ServiceX.git", f"{temp_dir}/ServiceX", console)
    if servicex_repo is None:
      error("Can't checkout ServiceX repo")
    else:
      service_repo_dir = pathlib.Path(servicex_repo.workdir)
    if not git.checkout_branch(servicex_repo, "develop"):
      error("Can't checkout develop branch from ServiceX repo")
    util.replace_appver(service_repo_dir / "servicex" / "Chart.yaml", tag, chart_version)
    util.replace_tags(service_repo_dir / "servicex" / "values.yaml", tag)
    git.add_file(servicex_repo, "servicex/Chart.yaml")
    git.add_file(servicex_repo, "servicex/values.yaml")
    git.commit(servicex_repo)
    chart_repo = git.checkout_repo("ssh://git@github.com/ssl-hep/ssl-helm-charts.git", f"{temp_dir}/ssl-helm-charts", console)
    if chart_repo is None:
      error("Can't checkout ssl-helm-charts repo")
    else:
      chart_repo_dir = pathlib.Path(chart_repo.workdir)
    if not git.checkout_branch(chart_repo, "gh-pages"):
      error("Can't checkout gh-pages branch from ssl-helm-charts repo")
    util.generate_helm_package(service_repo_dir, chart_repo_dir)
    git.add_file(chart_repo, "index.yaml")
    git.add_file(chart_repo, f"servicex-{chart_version}.tgz")
    git.commit(chart_repo)
    if not git.push(servicex_repo):
      error("Can't push changes to ServiceX repo")
    if not git.push(chart_repo):
      error("Can't push changes to ssl-helm-charts repo")

  except IOError:
    pass
  finally:
    if orig_dir is not None:
      os.chdir(orig_dir)
    #shutil.rmtree(temp_dir)


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
  token = get_token()
  ctx.obj = {'config': config,
             'repo_configs': repo_configs,
             'token': token}


entry.add_command(tag)
entry.add_command(verify_containers)
entry.add_command(monitor_workflows)
entry.add_command(release)

if __name__ == "__main__":
  entry()
